# # pyrefly: ignore [missing-import]

import numpy as np
import supervision as sv

from deep_sort_realtime.deepsort_tracker import DeepSort

from tracker.services.tracking.schemas import (
    Detection,
    TrackedDetection,
)

from typing import List


class PersonTracker:
    """
    Tracks detected persons using either ByteTrack or Deep SORT.
    """

    def __init__(
        self,
        fps: float,
        tracker_type: str = "deepsort",
    ):  

        self.tracker_type = tracker_type.lower()

        # =========================================================
        # BYTE TRACK
        # =========================================================
        if self.tracker_type == "bytetrack":

            self.tracker = sv.ByteTrack(
                track_activation_threshold=0.50,
                # track_high_thresh=0.60,
                # new_track_thresh=0.40,
                lost_track_buffer=int(round(fps * 2)),
                minimum_matching_threshold=0.9,
                frame_rate=fps,
                minimum_consecutive_frames=1,
            )

        # =========================================================
        # DEEP SORT
        # =========================================================
        elif self.tracker_type == "deepsort":

            # self.tracker = DeepSort(
            #     max_age=int(round(fps * 4)),
            #     n_init=4,
            #     max_cosine_distance=0.2,
            #     nn_budget=100,
            #     max_iou_distance=0.4,
            #     # embedder="torchreid",  
                
            # )
            self.tracker = DeepSort(
                max_age=int(round(fps * 4)),
                n_init=3,
                max_cosine_distance=0.35,
                nn_budget=100,
                max_iou_distance=0.6,   
            )

        else:

            raise ValueError(
                f"Unsupported tracker type: {tracker_type}. "
                f"Use 'bytetrack' or 'deepsort'."
            )


    def update(
        self,
        detections: List[Detection],
        frame=None,
    ) -> List[TrackedDetection]:

        # =========================================================
        # BYTE TRACK
        # =========================================================
        if self.tracker_type == "bytetrack":

            return self._update_bytetrack(detections)

        # =========================================================
        # DEEP SORT
        # =========================================================
        elif self.tracker_type == "deepsort":

            if frame is None:
                raise ValueError(
                    "Deep SORT requires the current video frame."
                )

            return self._update_deepsort(
                detections,
                frame,
            )

        return []


    # =============================================================
    # BYTE TRACK
    # =============================================================

    def _update_bytetrack(
        self,
        detections: List[Detection],
    ) -> List[TrackedDetection]:

        if len(detections) == 0:
            return []

        xyxy = np.array(
            [d.bbox for d in detections],
            dtype=np.float32,
        )

        confidence = np.array(
            [d.confidence for d in detections],
            dtype=np.float32,
        )

        class_id = np.array(
            [d.class_id for d in detections],
            dtype=np.int32,
        )

        sv_detections = sv.Detections(
            xyxy=xyxy,
            confidence=confidence,
            class_id=class_id,
        )

        tracked = self.tracker.update_with_detections(
            sv_detections
        )

        tracked_detections = []

        for i in range(len(tracked.xyxy)):

            tracked_detections.append(
                TrackedDetection(
                    bbox=tuple(tracked.xyxy[i]),
                    confidence=float(
                        tracked.confidence[i]
                    ),
                    class_id=int(
                        tracked.class_id[i]
                    ),
                    track_id=int(
                        tracked.tracker_id[i]
                    ),
                )
            )

        return tracked_detections


    # =============================================================
    # DEEP SORT
    # =============================================================

    def _update_deepsort(
        self,
        detections: List[Detection],
        frame,
    ) -> List[TrackedDetection]:

        deep_sort_detections = []

        for detection in detections:

            x1, y1, x2, y2 = detection.bbox

            width = x2 - x1
            height = y2 - y1

            if width <= 0 or height <= 0:
                continue

            deep_sort_detections.append(
                (
                    [x1, y1, width, height],
                    detection.confidence,
                    detection.class_id,
                )
            )

        tracks = self.tracker.update_tracks(
            deep_sort_detections,
            frame=frame,
        )

        tracked_detections = []

        for track in tracks:

            if not track.is_confirmed():
                continue

            x1, y1, x2, y2 = track.to_ltrb()

            confidence = track.det_conf

            class_id = track.det_class

            if confidence is None:
                confidence = 0.0

            if class_id is None:
                class_id = 0

            tracked_detections.append(
                TrackedDetection(
                    bbox=(
                        float(x1),
                        float(y1),
                        float(x2),
                        float(y2),
                    ),
                    confidence=float(confidence),
                    class_id=int(class_id),
                    track_id=int(track.track_id),
                )
            )

        return tracked_detections