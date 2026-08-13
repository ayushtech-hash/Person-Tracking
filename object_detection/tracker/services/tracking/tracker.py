# pyrefly: ignore [missing-import]
import numpy as np
import supervision as sv
from tracker.services.video.video_loader import VideoLoader
from tracker.services.tracking.schemas import Detection,TrackedDetection
from typing import List

class PersonTracker:
    """
    Tracks detected persons using ByteTrack.
    """
# VideoLoader.get_info("fps")
    def __init__(self,fps=30 ):
        self.tracker = sv.ByteTrack(
            track_activation_threshold=0.50,
            # track_high_thresh= 0.60,
            # new_track_thresh= 0.40,
            lost_track_buffer=(fps*2),
            minimum_matching_threshold=0.9,
            frame_rate=fps,
            minimum_consecutive_frames=1,)

    # def update(self, detections: list[Detection]) -> list[TrackedDetection]:
    def update(self, detections: List[Detection]) -> List[TrackedDetection]:

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