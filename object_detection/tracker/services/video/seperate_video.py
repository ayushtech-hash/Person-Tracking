from pathlib import Path
import cv2
from django.conf import settings
import subprocess
from ...models import TrackFrameEvent
from .video_writer import VideoWriter


class SeparateVideoGenerator:

    @staticmethod
    def convert_to_browser_format(video_path: str):
        base, ext = video_path.rsplit(".", 1)

        temp_output = f"{base}_browser.mp4"

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

        Path(temp_output).replace(video_path)

    @staticmethod
    def generate(
        report_id,
        track_id,
        video_version,
        fps=25.0,
    ):
        # -----------------------------------------------------
        # Get all stored frames for this track
        # -----------------------------------------------------

        frame_events = (
            TrackFrameEvent.objects
            .filter(
                track__report_id=report_id,
                track__track_id=track_id,
            )
            .order_by("frame_number")
        )

        if not frame_events.exists():
            raise ValueError(
                f"No frames found for Track ID {track_id}."
            )

        # -----------------------------------------------------
        # Output directory
        # -----------------------------------------------------

        output_dir = (
            Path(settings.MEDIA_ROOT)
            / "videos"
            / video_version
            / "separate_video"
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_filename = (
            f"report_{report_id}_track_{track_id}.mp4"
        )

        output_path = (
            output_dir / output_filename
        )

        # -----------------------------------------------------
        # Read first frame
        # -----------------------------------------------------

        first_event = frame_events.first()

        first_frame_path = (
            SeparateVideoGenerator._get_frame_path(
                first_event.full_frame_url
            )
        )

        first_frame = cv2.imread(
            str(first_frame_path)
        )

        if first_frame is None:
            raise ValueError(
                f"Unable to read frame: "
                f"{first_frame_path}"
            )

        height, width = first_frame.shape[:2]

        # -----------------------------------------------------
        # Use existing VideoWriter
        # -----------------------------------------------------

        writer = VideoWriter(
            output_path=str(output_path),
            fps=fps,
            width=width,
            height=height,
        )

        frames_written = 0

        try:
            for event in frame_events:

                frame_path = (
                    SeparateVideoGenerator._get_frame_path(
                        event.full_frame_url
                    )
                )

                frame = cv2.imread(
                    str(frame_path)
                )

                if frame is None:
                    print(
                        f"WARNING: Could not read "
                        f"{frame_path}"
                    )
                    continue

                if (
                    frame.shape[1] != width
                    or frame.shape[0] != height
                ):
                    frame = cv2.resize(
                        frame,
                        (width, height),
                    )

                writer.write(frame)

                frames_written += 1

        finally:
            writer.release()

        if frames_written == 0:
            raise ValueError(
                "No valid frames were written."
            )

        # Convert OpenCV output to browser-compatible H.264 MP4
        SeparateVideoGenerator.convert_to_browser_format(
            str(output_path)
        )

        # -----------------------------------------------------
        # Frontend URL
        # -----------------------------------------------------

        video_url = (
        f"{settings.MEDIA_URL.rstrip('/')}"
        f"/videos/"
        f"{video_version}/"
        f"separate_video/"
        f"{output_filename}"
    )

        return {
            "video_url": video_url,
            "track_id": track_id,
            "report_id": report_id,
            "frames": frames_written,
            
        }

    @staticmethod
    def _get_frame_path(full_frame_url):

        media_url = settings.MEDIA_URL.rstrip("/")

        relative_path = (
            full_frame_url
            .replace(media_url, "")
            .lstrip("/")
        )

        return (
            Path(settings.MEDIA_ROOT)
            / relative_path
        )
    