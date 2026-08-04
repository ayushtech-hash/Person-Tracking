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
        selected_track_id: int | None = None,

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

            """detecting multiple persons"""

            detections = self.detector.detect(frame)
            
            """tracking multiple persons"""

            tracked = self.tracker.update(detections)
            
            """tracking person by id """
            
            if selected_track_id is not None:
                tracked = [
                    person
                    for person in tracked
                    if person.track_id == selected_track_id]

            Visualizer.draw_tracks(frame, tracked)


            writer.write(frame)

        loader.release()
        writer.release()

   