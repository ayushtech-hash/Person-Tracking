"""Conservative appearance validation for active ByteTrack segments."""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from tracker.services.reidentification import OSNetFeatureExtractor


logger = logging.getLogger(__name__)


@dataclass
class SegmentObservation:
    status: str
    similarity: Optional[float] = None
    embedding: Optional[np.ndarray] = None


class SegmentAppearanceValidator:
    """Detect sustained, strong changes in the appearance of one raw ID.

    Checks are intentionally sparse during normal tracking, then run on every
    usable frame after a strong mismatch.  A segment only splits after two
    consecutive strong mismatches, keeping a single poor crop from causing a
    false ID-switch split.
    """

    def __init__(
        self,
        check_interval_frames=2,
        same_person_threshold=0.80,
        switch_threshold=0.55,
        confirmations_required=2,
        max_references=5,
    ):
        self.check_interval_frames = check_interval_frames
        self.same_person_threshold = same_person_threshold
        self.switch_threshold = switch_threshold
        self.confirmations_required = confirmations_required
        self.max_references = max_references
        self._states: Dict[int, Dict] = {}

    def observe(self, segment, crop_bgr, frame_number):
        """Assess one crop before its frame event is persisted."""
        if not self._is_usable_crop(crop_bgr):
            return SegmentObservation(status="skip")

        state = self._states.setdefault(
            segment.pk,
            {
                "references": [],
                "last_checked_frame": None,
                "mismatch_count": 0,
                "pending_event_ids": [],
            },
        )
        last_checked_frame = state["last_checked_frame"]
        should_check = (
            not state["references"]
            or state["mismatch_count"] > 0
            or last_checked_frame is None
            or frame_number - last_checked_frame >= self.check_interval_frames
        )
        if not should_check:
            return SegmentObservation(status="skip")

        try:
            embedding = OSNetFeatureExtractor.embed_bgr(crop_bgr)
        except Exception as exc:
            # ReID is a safety enhancement: model/GPU/crop failures must never
            # interrupt normal ByteTrack processing.
            logger.warning("Segment appearance check skipped: %s", exc)
            return SegmentObservation(status="skip")

        state["last_checked_frame"] = frame_number
        if not state["references"]:
            self._add_reference(state, embedding)
            return SegmentObservation(status="same", embedding=embedding)

        similarity = max(
            float(np.dot(embedding, reference))
            for reference in state["references"]
        )
        if similarity >= self.same_person_threshold:
            state["mismatch_count"] = 0
            state["pending_event_ids"] = []
            self._add_reference(state, embedding)
            return SegmentObservation(
                status="same", similarity=similarity, embedding=embedding
            )

        if similarity <= self.switch_threshold:
            state["mismatch_count"] += 1
            if state["mismatch_count"] >= self.confirmations_required:
                return SegmentObservation(
                    status="switch", similarity=similarity, embedding=embedding
                )
            return SegmentObservation(
                status="pending", similarity=similarity, embedding=embedding
            )

        # Ambiguous changes are not a safe basis for an automatic split.
        state["mismatch_count"] = 0
        state["pending_event_ids"] = []
        return SegmentObservation(status="same", similarity=similarity)

    def remember_pending_event(self, segment, event_id):
        self._states[segment.pk]["pending_event_ids"].append(event_id)

    def should_buffer_event(self, segment):
        """Whether this frame belongs to an unresolved switch-candidate run."""
        state = self._states.get(segment.pk)
        return bool(state and state["mismatch_count"] > 0)

    def take_pending_event_ids(self, segment):
        state = self._states.get(segment.pk)
        if state is None:
            return []
        event_ids = state["pending_event_ids"]
        state["pending_event_ids"] = []
        state["mismatch_count"] = 0
        return event_ids

    def start_replacement_segment(self, previous_segment, new_segment, embedding):
        """Make the confirmed current person the reference for the new segment."""
        self._states.pop(previous_segment.pk, None)
        state = {
            "references": [],
            "last_checked_frame": None,
            "mismatch_count": 0,
            "pending_event_ids": [],
        }
        if embedding is not None:
            self._add_reference(state, embedding)
        self._states[new_segment.pk] = state

    def _add_reference(self, state, embedding):
        references: List[np.ndarray] = state["references"]
        references.append(embedding)
        if len(references) > self.max_references:
            del references[0]

    @staticmethod
    def _is_usable_crop(crop_bgr):
        if crop_bgr is None or crop_bgr.size == 0:
            return False
        height, width = crop_bgr.shape[:2]
        return width >= 32 and height >= 64
