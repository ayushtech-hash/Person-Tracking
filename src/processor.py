from src import video_loader
from src import video_loader
from src import video_loader
from src import video_loader
from src import video_loader
from src import video_loader
from src import video_loader
from src import video_loader
from src.video_loader import VideoLoader
from src.video_writer import VideoWriter
from src.detector import PersonDetector
from src.tracker import PersonTracker
from src.visualizer import Visualizer
from src.time_selector import TimeSelector
from src.presence_tracker import PresenceTracker
from src.report_generator import ReportGenerator

class VideoProcessor:

    def __init__(self):
        self.detector = PersonDetector()
        self.tracker = PersonTracker()
        self.presence_tracker = PresenceTracker()

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
            self.presence_tracker.update(tracked,current_frame,)
                    

            Visualizer.draw_tracks(frame, tracked, selected_track_id=selected_track_id)


            writer.write(frame)
            current_frame+=1

            if current_frame % 100 == 0:
                print(f"Processed {current_frame}/{time_range.end_frame} frames")

        loader.release()
        writer.release()

        if selected_track_id is not None:
            report = self.presence_tracker.get_presence(
                selected_track_id,
                info["fps"],
            )

            if report is not None:
                ReportGenerator.print_report(
                    report,
                    output_video,
                )
            else:
                print(f"Track ID {selected_track_id} was not found.")

   