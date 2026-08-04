import cv2

from src.video_loader import VideoLoader
from src.video_writer import VideoWriter
from src.detector import PersonDetector


class VideoProcessor:

    def __init__(self):
        self.detector = PersonDetector()

    def process(
        self,
        input_video: str,
        output_video: str,
    ):
        """
        Process the input video and save the output video.
        """

        loader = VideoLoader(input_video)

        info = loader.get_info()

        writer = VideoWriter(
            output_path=output_video,
            fps=info["fps"],
            width=info["width"],
            height=info["height"],
        )

        while True:

            ret, frame = loader.read()

            if not ret:
                break

            detections = self.detector.detect(frame)

            self.draw_detections(frame, detections)

            writer.write(frame)

        loader.release()
        writer.release()

    @staticmethod
    def draw_detections(frame, detections):

        for det in detections:

            x1, y1, x2, y2 = map(int, det.bbox)

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2,
            )

            cv2.putText(
                frame,
                f"{det.confidence:.2f}",
                (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )