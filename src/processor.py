import cv2
from src.visualizer import Visualizer
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

            Visualizer.draw_detections(frame, detections)

            writer.write(frame)

        loader.release()
        writer.release()

   