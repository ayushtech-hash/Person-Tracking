from ultralytics import YOLO
from tracker.services.tracking.schemas import Detection

class PersonDetector:
    """
    Detects only persons in a video frame using YOLOv8.
    """

    PERSON_CLASS_ID = 0

    def __init__(self, model_path: str = "tracker/models/yolov8n.pt"):
        """
        Load the YOLO model once.
        """
        self.model = YOLO(model_path)

    def detect(self, frame, conf: float = 0.4, iou: float = 0.70):
        """
        Detect persons in a frame.

        Returns:
            List[Detection]
        """
        results = self.model(frame, conf=conf,iou=iou,verbose=False)

        detections = []

        boxes = results[0].boxes

        if boxes is None:
            return detections

        for box in boxes:

            class_id = int(box.cls[0])

            if class_id != self.PERSON_CLASS_ID:
                continue

            x1, y1, x2, y2 = map(float, box.xyxy[0])

            confidence = float(box.conf[0])
            detections.append(
                Detection(
                    bbox=(x1, y1, x2, y2),
                    confidence=confidence,
                    class_id=class_id,
                )
            )
        
        return detections