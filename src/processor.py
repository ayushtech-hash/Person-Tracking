from src import video_loader
from src import video_loader
from src import video_loader
from src import video_loader
from src import video_loader
from src import video_writer
import cv2
from src.visualizer import Visualizer
from src.video_loader import VideoLoader
from src.video_writer import VideoWriter
from src.detector import PersonDetector
from src.tracker import PersonTracker
from src.time_selector import TimeSelector  

class VideoProcessor:

    def __init__(self):
        self.detector = PersonDetector()
        self.tracker = PersonTracker()

    def process(
        self,
        input_video: str,
        output_video: str,
        start_time: str = "00:00:00",
        end_time: str | None = None,
        selected_track_id: int | None = None,

    ):
        """
        Process the input video and save the output video.
        """

        loader = VideoLoader(input_video)

        info = loader.get_info()

        if end_time is None:
            total_seconds = int(info["duration"])

            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            end_time = f"{hours:02}:{minutes:02}:{seconds:02}"

        time_range = TimeSelector.get_frame_range(
            start_time=start_time,
            end_time=end_time,
            fps=info["fps"],
            duration=info["duration"],
)
        loader.set_frame(time_range.start_frame)

        writer = VideoWriter(
            output_path=output_video,
            fps=info["fps"],
            width=info["width"],
            height=info["height"],
        )

        # while True:
        current_frame = time_range.start_frame

        while current_frame < time_range.end_frame:

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

            Visualizer.draw_tracks(frame, tracked, selected_track_id=selected_track_id)


            writer.write(frame)
            current_frame+=1

        loader.release()
        writer.release()

   