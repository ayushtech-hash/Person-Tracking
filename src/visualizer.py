import cv2


class Visualizer:
    """
    Responsible for drawing annotations on video frames.
    """

    @staticmethod
    def draw_detections(frame, detections):
        """
        Draw person detections on a frame.
        """

        for det in detections:

            x1, y1, x2, y2 = map(int, det.bbox)

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2,
            )

            label = f"{det.confidence:.2f}"

            cv2.putText(
                frame,
                label,
                (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

        return frame