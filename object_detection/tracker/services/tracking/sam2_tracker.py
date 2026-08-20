# from __future__ import annotations

# import numpy as np
# import torch
# import supervision as sv
# from typing import List, Optional
# from sam2.build_sam import build_sam2_camera_predictor

# from tracker.services.tracking.schemas import (
#     Detection,
#     TrackedDetection,
# )


# class SAM2Tracker:
#     """
#     Person tracker using YOLO detections from the first frame
#     and SAM2 for tracking/propagation across subsequent frames.

#     Flow:

#         First frame
#             ↓
#         YOLO detections
#             ↓
#         Assign IDs
#             ↓
#         Prompt SAM2
#             ↓
#         SAM2 propagation
#             ↓
#         TrackedDetection objects
#     """

#     def __init__(
#         self,
#         config_path: str,
#         checkpoint_path: str,
#         device: str = "cuda",
#     ):
#         self.config_path = config_path
#         self.checkpoint_path = checkpoint_path
#         self.device = device

#         self.predictor = build_sam2_camera_predictor(
#             config_path,
#             checkpoint_path,
#         )

#         self._prompted = False

#         print(
#             "[SAM2] Tracker initialized"
#         )

#     # =========================================================
#     # INITIALIZE SAM2 USING FIRST-FRAME YOLO DETECTIONS
#     # =========================================================

#     def initialize(
#         self,
#         frame,
#         detections: List[Detection],
#     ):
#         """
#         Use YOLO detections from the first frame to initialize SAM2.

#         YOLO is expected to provide person detections.

#         IDs are assigned sequentially:

#             Person 1 → ID 1
#             Person 2 → ID 2
#             Person 3 → ID 3
#             ...
#         """

#         if frame is None:
#             raise ValueError(
#                 "SAM2 initialization requires the first frame."
#             )

#         if not detections:
#             raise ValueError(
#                 "SAM2 initialization requires at least "
#                 "one YOLO detection."
#             )

#         # -----------------------------------------------------
#         # Convert project Detection objects → supervision
#         # -----------------------------------------------------

#         xyxy = np.array(
#             [d.bbox for d in detections],
#             dtype=np.float32,
#         )

#         confidence = np.array(
#             [d.confidence for d in detections],
#             dtype=np.float32,
#         )

#         class_id = np.array(
#             [d.class_id for d in detections],
#             dtype=np.int32,
#         )

#         sv_detections = sv.Detections(
#             xyxy=xyxy,
#             confidence=confidence,
#             class_id=class_id,
#         )

#         # -----------------------------------------------------
#         # Assign initial IDs
#         # -----------------------------------------------------

#         sv_detections.tracker_id = np.arange(
#             1,
#             len(sv_detections) + 1,
#             dtype=np.int32,
#         )

#         print()
#         print("==============================")
#         print("[SAM2] First-frame YOLO")
#         print("==============================")
#         print(
#             f"Persons detected: {len(sv_detections)}"
#         )
#         print(
#             f"Assigned IDs: "
#             f"{sv_detections.tracker_id.tolist()}"
#         )
#         print("==============================")

#         # -----------------------------------------------------
#         # Load first frame and add prompts
#         # -----------------------------------------------------

#         with (
#             torch.inference_mode(),
#             torch.autocast(
#                 "cuda",
#                 dtype=torch.bfloat16,
#             ),
#         ):

#             self.predictor.load_first_frame(
#                 frame
#             )

#             for xyxy_box, object_id in zip(
#                 sv_detections.xyxy,
#                 sv_detections.tracker_id,
#             ):

#                 bbox = np.asarray(
#                     [xyxy_box],
#                     dtype=np.float32,
#                 )

#                 self.predictor.add_new_prompt(
#                     frame_idx=0,
#                     obj_id=int(object_id),
#                     bbox=bbox,
#                 )

#         self._prompted = True

#         print(
#             "[SAM2] First frame prompted successfully."
#         )

#     # =========================================================
#     # PROPAGATE SAM2
#     # =========================================================

#     def update(
#         self,
#         frame,
#     ) -> List[TrackedDetection]:
#         """
#         Propagate existing SAM2 objects through the current frame.

#         Returns the same TrackedDetection structure used by
#         ByteTrack and Deep SORT so the existing UI/backend
#         can consume SAM2 tracks.
#         """

#         if not self._prompted:
#             raise RuntimeError(
#                 "SAM2 tracker has not been initialized. "
#                 "Call initialize() using the first frame."
#             )

#         if frame is None:
#             return []

#         with (
#             torch.inference_mode(),
#             torch.autocast(
#                 "cuda",
#                 dtype=torch.bfloat16,
#             ),
#         ):

#             tracker_ids, mask_logits = (
#                 self.predictor.track(frame)
#             )

#         tracker_ids = np.asarray(
#             tracker_ids,
#             dtype=np.int32,
#         )

#         # -----------------------------------------------------
#         # Convert SAM2 logits → binary masks
#         # -----------------------------------------------------

#         masks = (
#             mask_logits > 0.0
#         ).cpu().numpy()

#         masks = np.squeeze(
#             masks
#         ).astype(bool)

#         if masks.ndim == 2:
#             masks = masks[None, ...]

#         # -----------------------------------------------------
#         # Clean mask edges
#         # Same logic as your Colab implementation.
#         # -----------------------------------------------------

#         masks = np.array(
#             [
#                 sv.filter_segments_by_distance(
#                     mask,
#                     relative_distance=0.03,
#                     mode="edge",
#                 )
#                 for mask in masks
#             ]
#         )

#         # -----------------------------------------------------
#         # SAM2 mask → bounding box
#         # -----------------------------------------------------

#         xyxy = sv.mask_to_xyxy(
#             masks=masks
#         )

#         # -----------------------------------------------------
#         # Convert to project TrackedDetection
#         # -----------------------------------------------------

#         tracked_detections = []

#         for bbox, track_id in zip(
#             xyxy,
#             tracker_ids,
#         ):

#             x1, y1, x2, y2 = map(
#                 float,
#                 bbox,
#             )

#             tracked_detections.append(
#                 TrackedDetection(
#                     bbox=(
#                         x1,
#                         y1,
#                         x2,
#                         y2,
#                     ),
#                     confidence=1.0,
#                     class_id=0,
#                     track_id=int(track_id),
#                 )
#             )

#         return tracked_detections

#     # =========================================================
#     # RESET
#     # =========================================================

#     def reset(self):
#         """
#         Reset the SAM2 tracker state.
#         """

#         self._prompted = False

#         print(
#             "[SAM2] Tracker reset."
#         )