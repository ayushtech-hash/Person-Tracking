"""OSNet feature extraction and in-memory identity grouping for upper-body crops."""

import logging
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np


logger = logging.getLogger(__name__)
import cv2
from PIL import Image
import torch
import torch
import torchreid
from torchvision import transforms

class ReIdentificationUnavailable(RuntimeError):
    """Raised when the optional OSNet dependencies/model are unavailable."""


class OSNetFeatureExtractor:
    """Lazily loads one OSNet model per Django worker process."""

    _model = None
    _preprocess = None
    _device = None
    _load_error = None
    _load_lock = threading.Lock()

    @classmethod
    def _load(cls):
        if cls._model is not None:
            return
        if cls._load_error is not None:
            raise ReIdentificationUnavailable(cls._load_error)

        with cls._load_lock:
            if cls._model is not None:
                return
            if cls._load_error is not None:
                raise ReIdentificationUnavailable(cls._load_error)

            try: 
                cls._device = torch.device(
                    "cuda" if torch.cuda.is_available() else "cpu"
                )
                cls._model = torchreid.models.build_model(
                    name="osnet_x1_0",
                    num_classes=1000,
                    pretrained=True,
                ).to(cls._device)
                cls._model.eval()
                cls._preprocess = transforms.Compose([
                    transforms.Resize((256, 128)),
                    transforms.ToTensor(),
                    transforms.Normalize(
                        mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225],
                    ),
                ])
            except Exception as exc:
                cls._load_error = str(exc)
                raise ReIdentificationUnavailable(cls._load_error) from exc

    @classmethod
    def embed_bgr(cls, image_bgr: np.ndarray) -> np.ndarray:
        """Return a unit-length OSNet embedding for an OpenCV BGR crop."""
        if image_bgr is None or image_bgr.size == 0:
            raise ValueError("Cannot create an embedding from an empty person crop.")

        cls._load()

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(image_rgb)
        tensor = cls._preprocess(image).unsqueeze(0).to(cls._device)

        with torch.no_grad():
            embedding = cls._model(tensor)

        if isinstance(embedding, (tuple, list)):
            embedding = embedding[0]

        vector = embedding.detach().cpu().numpy().reshape(-1).astype(np.float32)
        norm = np.linalg.norm(vector)
        if norm == 0:
            raise ValueError("OSNet returned a zero-length embedding.")
        return vector / norm


@dataclass
class IndexedPerson:
    """One upper-half crop that participates in identity matching."""

    embedding: np.ndarray
    event: Dict
    node_id: int


@dataclass
class ManualMatchCandidate:
    """A below-auto-threshold OSNet comparison awaiting user review."""

    first_node_id: int
    second_node_id: int
    similarity: float


class PersonSimilarityIndex:
    """Groups matching upper-body snapshots from one uploaded video.

    The groups are deliberately transitive.  For example, when crop C matches
    crop B and B already matches A, all three crops have one identity group,
    even if C does not directly meet the threshold against A.

    This class is scoped to one processing run.  It also retains similarities
    in the manual-review range so they can be persisted after final automatic
    group resolution.
    """

    def __init__(
        self,
        threshold: float = 0.80,
        manual_review_threshold: float = 0.70,
        max_matches: int = 4,
    ):
        if manual_review_threshold >= threshold:
            raise ValueError(
                "manual_review_threshold must be below the automatic threshold."
            )
        self.threshold = threshold
        self.manual_review_threshold = manual_review_threshold
        self.max_matches = max_matches
        self._people: List[IndexedPerson] = []
        self._manual_match_candidates: List[ManualMatchCandidate] = []
        # A small union-find structure lets a new crop merge one or more
        # previously separate groups without losing transitive relationships.
        self._parents: List[int] = []
        self.error: Optional[str] = None

    def _find(self, node_id: int) -> int:
        """Return the canonical group node, with path compression."""
        parent = self._parents[node_id]
        if parent != node_id:
            self._parents[node_id] = self._find(parent)
        return self._parents[node_id]

    def _union(self, first_node_id: int, second_node_id: int) -> int:
        """Merge two groups, keeping the earliest snapshot as representative."""
        first_root = self._find(first_node_id)
        second_root = self._find(second_node_id)
        if first_root == second_root:
            return first_root

        representative_root = min(first_root, second_root)
        merged_root = max(first_root, second_root)
        self._parents[merged_root] = representative_root
        return representative_root

    def _sync_group_metadata(self) -> None:
        """Update every event after additions or group merges.

        Events are retained by reference so an earlier event receives the final
        canonical group ID if a later crop bridges two initially separate
        groups.  The caller can therefore use this metadata after processing
        without re-running OSNet.
        """
        members_by_root: Dict[int, List[IndexedPerson]] = {}
        for person in self._people:
            root = self._find(person.node_id)
            members_by_root.setdefault(root, []).append(person)

        for root, members in members_by_root.items():
            # Node IDs are allocated in video encounter order, therefore the
            # root is also the earliest group member/representative.
            representative = min(members, key=lambda member: member.node_id)
            member_track_ids = list(dict.fromkeys(
                member.event.get("track_id") for member in members
            ))
            group_id = root + 1

            for member in members:
                member.event["identity_group_id"] = group_id
                member.event["identity_group_track_ids"] = member_track_ids
                member.event["is_identity_representative"] = (
                    member.node_id == representative.node_id
                )
                member.event["identity_group_size"] = len(members)

    def get_groups(self) -> List[Dict]:
        """Return the current groups in encounter order for later persistence."""
        self._sync_group_metadata()
        groups: Dict[int, List[IndexedPerson]] = {}
        for person in self._people:
            groups.setdefault(self._find(person.node_id), []).append(person)

        return [
            {
                "identity_group_id": root + 1,
                "representative_track_id": members[0].event.get("track_id"),
                "track_ids": list(dict.fromkeys(
                    member.event.get("track_id") for member in members
                )),
                "events": [member.event for member in members],
            }
            for root, members in sorted(groups.items())
        ]

    def get_manual_grouping_suggestions(self) -> List[Dict]:
        """Return one best manual-review suggestion for each final group pair.

        A candidate is discarded when a later automatic match has already
        connected its two groups.  That prevents prompting the user to merge
        people who are already automatically grouped.
        """
        self._sync_group_metadata()
        best_candidates: Dict[tuple, ManualMatchCandidate] = {}

        for candidate in self._manual_match_candidates:
            first_root = self._find(candidate.first_node_id)
            second_root = self._find(candidate.second_node_id)
            if first_root == second_root:
                continue

            key = tuple(sorted((first_root, second_root)))
            previous = best_candidates.get(key)
            if previous is None or candidate.similarity > previous.similarity:
                best_candidates[key] = candidate

        suggestions = []
        for (first_root, second_root), candidate in sorted(best_candidates.items()):
            first_person = self._people[candidate.first_node_id]
            second_person = self._people[candidate.second_node_id]
            suggestions.append(
                {
                    "first_identity_group_id": first_root + 1,
                    "second_identity_group_id": second_root + 1,
                    "first_track_id": first_person.event.get("track_id"),
                    "first_segment_id": first_person.event.get("segment_id"),
                    "first_frame": first_person.event.get("frame"),
                    "first_image_url": first_person.event.get("image_url", ""),
                    "second_track_id": second_person.event.get("track_id"),
                    "second_segment_id": second_person.event.get("segment_id"),
                    "second_frame": second_person.event.get("frame"),
                    "second_image_url": second_person.event.get("image_url", ""),
                    "similarity": round(candidate.similarity, 4),
                }
            )
        return suggestions

    def add_and_find_similar(self, image_bgr: np.ndarray, event: Dict) -> List[Dict]:
        """Find prior matching snapshots, then add this snapshot to the index."""
        try:
            embedding = OSNetFeatureExtractor.embed_bgr(image_bgr)
        # ReID is an enhancement. A CUDA/model/image error must not stop the
        # video-processing worker from creating the normal tracking results.
        except Exception as exc:
            self.error = str(exc)
            logger.exception(
                "[ReID] Could not create embedding for track_id=%s: %s",
                event.get("track_id"),
                exc,
            )
            return []

        logger.info(
            "[ReID] Embedding created for track_id=%s; comparing with %s prior track(s) "
            "at threshold=%.2f.",
            event.get("track_id"),
            len(self._people),
            self.threshold,
        )

        matches = []
        matching_node_ids = []
        manual_match_node_scores = []
        for person in self._people:
            score = float(np.dot(embedding, person.embedding))
            logger.info(
                "[ReID] Compare track_id=%s with track_id=%s: cosine_similarity=%.4f",
                event.get("track_id"),
                person.event.get("track_id"),
                score,
            )
            if score >= self.threshold:
                logger.info(
                    "[ReID] SIMILAR PERSON FOUND: track_id=%s matches track_id=%s "
                    "(cosine_similarity=%.4f, threshold=%.2f)",
                    event.get("track_id"),
                    person.event.get("track_id"),
                    score,
                    self.threshold,
                )
                matches.append({
                    "track_id": person.event["track_id"],
                    "frame": person.event["frame"],
                    "time_sec": person.event["time_sec"],
                    "image_url": person.event["image_url"],
                    "person_crop_url": person.event["person_crop_url"],
                    "similarity": round(score, 4),
                })
                matching_node_ids.append(person.node_id)
            elif score >= self.manual_review_threshold:
                logger.info(
                    "[ReID] MANUAL REVIEW CANDIDATE: track_id=%s and "
                    "track_id=%s (cosine_similarity=%.4f, range=%.2f-%.2f)",
                    event.get("track_id"),
                    person.event.get("track_id"),
                    score,
                    self.manual_review_threshold,
                    self.threshold,
                )
                manual_match_node_scores.append((person.node_id, score))

        node_id = len(self._people)
        self._parents.append(node_id)
        self._people.append(
            IndexedPerson(embedding=embedding, event=event, node_id=node_id)
        )

        for matching_node_id, score in manual_match_node_scores:
            self._manual_match_candidates.append(
                ManualMatchCandidate(
                    first_node_id=matching_node_id,
                    second_node_id=node_id,
                    similarity=score,
                )
            )

        # A match to any prior crop assigns this crop to that identity.  If it
        # matches two groups, union them: this is what supports A <-> B <-> C
        # transitive identity chains.
        for matching_node_id in matching_node_ids:
            self._union(node_id, matching_node_id)

        self._sync_group_metadata()
        matches.sort(key=lambda match: match["similarity"], reverse=True)
        if not matches:
            logger.info(
                "[ReID] No similar person found for track_id=%s.",
                event.get("track_id"),
            )
        return matches[:self.max_matches]
