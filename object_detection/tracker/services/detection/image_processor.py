import os
import cv2
from tracker.services.detection.detector import PersonDetector
from tracker.services.video.visualizer import Visualizer



_detector = None


def get_detector():
    global _detector
    if _detector is None:
        _detector = PersonDetector()
    return _detector


class ImageProcessor:
    @staticmethod
    def process(input_path: str, output_path: str) -> dict:
        frame = cv2.imread(input_path)

        if frame is None:
            raise ValueError("Could not read the uploaded image.")

        detector = get_detector()
        detections = detector.detect(frame,conf= 0.25,iou = 0.70)

        annotated = frame.copy()
        Visualizer.draw_detections(annotated, detections)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, annotated)

        detection_list = []
        for index, detection in enumerate(detections, start=1):
            x1, y1, x2, y2 = detection.bbox
            detection_list.append(
                {
                    "person_number": index,
                    "confidence": round(detection.confidence, 2),
                    "bbox": [round(x1), round(y1), round(x2), round(y2)],
                }
            )

        return {
            "total_persons_detected": len(detections),
            "detections": detection_list,
            "output_image": output_path,
        }
