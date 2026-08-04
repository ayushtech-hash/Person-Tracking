import numpy as np
import supervision as sv

from src.schemas import Detection, TrackedDetection


class PersonTracker:
    """
    Tracks detected persons using ByteTrack.
    """

    def __init__(self):
        self.tracker = sv.ByteTrack()

    def update(self, detections: list[Detection]) -> list[TrackedDetection]:

        if len(detections) == 0:
            return []

        xyxy = np.array([d.bbox for d in detections], dtype=np.float32)

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
                    confidence=float(tracked.confidence[i]),
                    class_id=int(tracked.class_id[i]),
                    track_id=int(tracked.tracker_id[i]),
                )

            )

        return tracked_detections