# from tracker.services import video_loader
# from tracker.services import video_loader
# from tracker.services import video_loader
from django.template import loader
from tracker.services.tracking import presence_tracker
from tracker.services.video.video_loader import VideoLoader
from tracker.services.video.video_writer import VideoWriter
from tracker.services.detection.detector import PersonDetector
from tracker.services.tracking.tracker import PersonTracker
from tracker.services.video.visualizer import Visualizer
from tracker.services.video.time_selector import TimeSelector
from tracker.services.tracking.presence_tracker import PresenceTracker
from tracker.services.reporting.report_generator import ReportGenerator
from typing import Optional
import subprocess
import cv2
import os, time


class VideoProcessor:

    def __init__(self):
        self.detector = PersonDetector()
        self.tracker = None
        self.presence_tracker = PresenceTracker()


    def convert_to_browser_format(self, video_path: str):
        """
        Convert OpenCV-generated video to H.264 so browsers can play it.
        """
        base, ext = os.path.splitext(video_path)
        temp_output = f"{base}_browser.mp4"
        # temp_output = video_path.replace(".mp4", "_browser.mp4")

        command = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            temp_output,
        ]

        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        os.replace(temp_output, video_path)

    def save_new_track_snapshot(
        self,
        frame,
        tracked,
        new_track_id,
        frame_number,
        fps,
        snapshot_dir,
            ):

        """
        Save the complete video frame when a new tracker ID appears.

        The frame contains all currently active tracker boxes,
        with the newly-created ID clearly marked.
        """

        os.makedirs(snapshot_dir, exist_ok=True)

        snapshot = frame.copy()

        # Draw all currently active tracks
        for track in tracked:
            x1, y1, x2, y2 = map(int, track.bbox)

            if track.track_id == new_track_id:
                thickness = 4
                label = f"NEW TRACK ID: {track.track_id}"
            else:
                thickness = 2
                label = f"ID: {track.track_id}"

            cv2.rectangle(
                snapshot,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                thickness,
            )

            cv2.putText(
                snapshot,
                label,
                (x1, max(25, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

        time_sec = frame_number / fps if fps else 0.0

        # Add frame/time information to the image
        cv2.putText(
            snapshot,
            f"Frame: {frame_number}  Time: {time_sec:.2f}s",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

        filename = f"track_{new_track_id}_frame_{frame_number}.jpg"
        filepath = os.path.join(snapshot_dir, filename)

        cv2.imwrite(filepath, snapshot)

        return filename, time_sec

    def process(
        self,
        input_video: str,
        output_video: str,
        start_time: Optional[str] = None,    
        end_time: Optional[str] = None,
        selected_track_id: Optional[int] = None,
        progress_callback=None,
        track_event_callback=None,
        track_frame_callback=None,
        video_version=None,
        report_id = None


    ):
        """
        Process the input video and save the output video.
        """

        loader = VideoLoader(input_video)

        info = loader.get_info()
        
        tracker_type = "deepsort"

        self.tracker = PersonTracker(fps=info["fps"], tracker_type=tracker_type,)

        if end_time is None:
            total_seconds = int(info["duration"])

            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            end_time = f"{hours:02}:{minutes:02}:{seconds:02}"
        
        if start_time is None:
            total_seconds = int(info["duration"])

            hours = 00
            minutes = 00
            seconds = 00
            # start_time = f"{hours:02}:{minutes:02}:{seconds:02}"
            start_time = f"{hours}:{minutes}:{seconds}"


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

        current_frame = time_range.start_frame
        peak_persons_detected = 0
        

        # IDs that have appeared anywhere in this processing job
        seen_track_ids = set()


        # Directory for snapshots belonging to this video
        snapshot_dir = os.path.join(
            os.path.dirname(output_video),
            "new_track_events",
            os.path.splitext(os.path.basename(output_video))[0],
        )

        os.makedirs(snapshot_dir, exist_ok=True)

        start_time = time.time()
        processed_frames = 0

        while current_frame < time_range.end_frame:

            ret, frame = loader.read()

            if not ret:
                break

            """detecting multiple persons"""

            detections = self.detector.detect(frame)

            processed_frames += 1
            
            elapsed = time.time() - start_time

            if elapsed >= 1.0:
                print(f"YOLO processing FPS: {processed_frames / elapsed:.2f}")
                start_time = time.time()
                processed_frames = 0


            # print("=====================detection=========================")
            for detection in detections:
                print(
                    f"frame={current_frame} "
                    f"conf={detection.confidence:.3f} "
                    f"bbox={detection.bbox}"
                   
                )
            # print("=====================detection=========================")
            persons_in_frame = len(detections)
            peak_persons_detected = max(peak_persons_detected, persons_in_frame)

            """tracking multiple persons"""

            tracked = self.tracker.update(detections,frame)

            

            # Save a snapshot for every NEW track ID
            # Track IDs already seen during this video
            if not hasattr(self, "_seen_track_ids"):
                self._seen_track_ids = set()

            for track in tracked:
                track_id = int(track.track_id)

                # Only create an event for a genuinely new ID
                if track_id not in self._seen_track_ids:
                    self._seen_track_ids.add(track_id)

                    # Create a clean copy of the current frame
                    event_frame = frame.copy()

                    # Bounding box of ONLY the newly created track
                    x1, y1, x2, y2 = map(int, track.bbox)

                    # Highlight the NEW person
                    cv2.rectangle(
                        event_frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 0, 0),          
                        4,
                    )

                    # Highlight label
                    label = f"NEW ID: {track_id}"

                    cv2.putText(
                        event_frame,
                        label,
                        (x1, max(30, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        2,
                        (0, 0, 0),
                        3,
                        cv2.LINE_AA,
                    )

                    print(
                        f"NEW TRACK ID={track_id} "
                        f"FRAME={current_frame}"
                    )

                    if track_event_callback:
                        track_event_callback(
                            frame=event_frame,
                            original_frame=frame,
                            bbox=(x1, y1, x2, y2),
                            track_id=track_id,
                            frame_number=current_frame,
                            fps=info["fps"],
                            video_version=video_version,
                            report_id=report_id
                        )

           
            print("===================TRACK ==========================")

            for track in tracked:
                print(
                    f"frame={current_frame} "
                    f"id={track.track_id} "
                    f"conf={track.confidence:.3f} "
                    f"bbox={track.bbox}"
                )

            print("===================TRACK ==========================")


            self.presence_tracker.update(tracked,current_frame,)
                    

            Visualizer.draw_tracks(frame, tracked, selected_track_id=selected_track_id)
            
            # ---------------------------------------------------------
            # Save full frame for every active track
            # ---------------------------------------------------------
            print(
                f"DEBUG: frame={current_frame}, "
                f"tracked={len(tracked)}, "
                f"callback={track_frame_callback is not None}"
            )
            if track_frame_callback and tracked:

                track_frame_callback(
                    frame=frame,
                    tracked=tracked,
                    frame_number=current_frame,
                    fps=info["fps"],
                )

            writer.write(frame)
            current_frame+=1

            if progress_callback:
                progress_callback(
                    current_frame,
                    time_range.end_frame,
                )

            if current_frame % 100 == 0:
                print(f"Processed {current_frame}/{time_range.end_frame} frames")

        loader.release()
        writer.release()

        print("Converting video for browser playback...")

        if progress_callback:
            progress_callback(
                time_range.end_frame,
                time_range.end_frame,
                status="Converting",
            )

        self.convert_to_browser_format(output_video)

        print("Conversion completed.")

        if selected_track_id is not None:

            report = self.presence_tracker.get_presence(
                selected_track_id,
                info["fps"],
            )

            if report is not None:

                # Keep terminal output
                ReportGenerator.print_report(
                    report,
                    output_video,
                )

                # Return data for Django
                return ReportGenerator.generate_report(
                    report,
                    output_video,
                    peak_persons_detected=peak_persons_detected,
                )

            else:
                print(f"Track ID {selected_track_id} was not found.")
                return None

        else:

            reports = self.presence_tracker.get_all_presence(
                info["fps"],
            )

            # Keep terminal output
            ReportGenerator.print_all_reports(
                reports,
                output_video,
            )

            # Return data for Django
            return ReportGenerator.generate_all_reports(
                reports,
                output_video,
                peak_persons_detected=peak_persons_detected,
            )

            

    