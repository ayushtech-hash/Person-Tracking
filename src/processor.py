from src import video_writer
import cv2
from src.visualizer import Visualizer
from src.video_loader import VideoLoader
from src.video_writer import VideoWriter
from src.detector import PersonDetector
from src.tracker import PersonTracker


class VideoProcessor:

    def __init__(self):
        self.detector = PersonDetector()
        self.tracker = PersonTracker()

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

            tracked = self.tracker.update(detections)

            Visualizer.draw_tracks(frame, tracked)


            writer.write(frame)

        loader.release()
        writer.release()

   