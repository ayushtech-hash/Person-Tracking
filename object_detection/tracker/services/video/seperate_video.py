from pathlib import Path
import cv2
from django.conf import settings
import subprocess
from ...models import TrackFrameEvent
from .video_writer import VideoWriter


class SeparateVideoGenerator:

    RED = (0, 0, 255)  # OpenCV uses BGR rather than RGB.
    WHITE = (255, 255, 255)
    LABEL = "Tracked Person"

    @staticmethod
    def _draw_tracked_person(frame, event, source_width, source_height):
        """Draw the selected person's persisted box on one exported frame."""
        coordinates = (
            event.bbox_x1,
            event.bbox_y1,
            event.bbox_x2,
            event.bbox_y2,
        )
        if any(value is None for value in coordinates):
            # Videos processed before bounding boxes were persisted cannot be
            # annotated reliably. Newly processed videos always have them.
            return

        scale_x = frame.shape[1] / source_width
        scale_y = frame.shape[0] / source_height
        x1, y1, x2, y2 = (
            int(value * scale)
            for value, scale in zip(coordinates, (scale_x, scale_y, scale_x, scale_y))
        )
        x1 = max(0, min(x1, frame.shape[1] - 1))
        y1 = max(0, min(y1, frame.shape[0] - 1))
        x2 = max(x1 + 1, min(x2, frame.shape[1] - 1))
        y2 = max(y1 + 1, min(y2, frame.shape[0] - 1))

        cv2.rectangle(frame, (x1, y1), (x2, y2), SeparateVideoGenerator.RED, 6)

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 2
        text_thickness = 5
        (text_width, text_height), baseline = cv2.getTextSize(
            SeparateVideoGenerator.LABEL,
            font,
            font_scale,
            text_thickness,
        )
        padding = 6
        label_left = x1
        # Keep the label just above the box whenever possible; otherwise
        # place it inside the top edge so it is never clipped off-screen.
        label_top = max(0, y1 - text_height - baseline - (padding * 2))
        label_bottom = label_top + text_height + baseline + (padding * 2)
        label_right = min(frame.shape[1] - 1, label_left + text_width + (padding * 2))
        text_x = label_left + padding
        text_y = label_top + padding + text_height

        cv2.rectangle(
            frame,
            (label_left, label_top),
            (label_right, label_bottom),
            SeparateVideoGenerator.WHITE,
            cv2.FILLED,
        )
        cv2.putText(
            frame,
            SeparateVideoGenerator.LABEL,
            (text_x, text_y),
            font,
            font_scale,
            SeparateVideoGenerator.RED,
            text_thickness,
            cv2.LINE_AA,
        )

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
        if not frame_events.exclude(
            bbox_x1__isnull=False,
            bbox_y1__isnull=False,
            bbox_x2__isnull=False,
            bbox_y2__isnull=False,
        ).exists():
            raise ValueError(
                "Bounding boxes are unavailable for this existing report. "
                "Process the upload again before generating a highlighted video."
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
            f"report_{report_id}_track_{track_id}_highlighted.mp4"
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

                source_height, source_width = frame.shape[:2]

                if (
                    frame.shape[1] != width
                    or frame.shape[0] != height
                ):
                    frame = cv2.resize(
                        frame,
                        (width, height),
                    )

                SeparateVideoGenerator._draw_tracked_person(
                    frame, event, source_width, source_height
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
    def generate_merged(
        report_id,
        track_ids=None,
        video_version=None,
        fps=25.0,
        segment_ids=None,
    ):
        """Generate one video from segments (or legacy raw IDs), in frame order."""
        if segment_ids is not None:
            segment_ids = sorted({int(segment_id) for segment_id in segment_ids})
            if not segment_ids:
                raise ValueError("At least one track segment is required.")
            frame_events = list(
                TrackFrameEvent.objects.filter(
                    segment__report_id=report_id,
                    segment_id__in=segment_ids,
                ).select_related("track", "segment").order_by(
                    "frame_number", "segment__raw_track_id", "id"
                )
            )
            selection_label = "segments"
            selection_suffix = "_".join(str(segment_id) for segment_id in segment_ids)
        else:
            track_ids = sorted({int(track_id) for track_id in (track_ids or [])})
            if not track_ids:
                raise ValueError("At least one track ID is required.")
            frame_events = list(
                TrackFrameEvent.objects.filter(
                    track__report_id=report_id,
                    track__track_id__in=track_ids,
                ).select_related("track", "segment").order_by(
                    "frame_number", "track__track_id", "id"
                )
            )
            selection_label = "tracks"
            selection_suffix = "_".join(str(track_id) for track_id in track_ids)

        # This must be one combined query, rather than an outer loop over
        # selected segments: several fragments must be interleaved in real
        # video order. Raw IDs remain only as a legacy fallback.
        if not frame_events:
            raise ValueError("No frames were found for the selected selection.")
        if not any(
            all(
                value is not None
                for value in (
                    event.bbox_x1,
                    event.bbox_y1,
                    event.bbox_x2,
                    event.bbox_y2,
                )
            )
            for event in frame_events
        ):
            raise ValueError(
                "Bounding boxes are unavailable for this existing report. "
                "Process the upload again before generating a highlighted video."
            )

        output_dir = (
            Path(settings.MEDIA_ROOT)
            / "videos"
            / video_version
            / "separate_video"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        output_filename = (
            f"report_{report_id}_{selection_label}_{selection_suffix}_highlighted.mp4"
        )
        output_path = output_dir / output_filename

        video_url = (
            f"{settings.MEDIA_URL.rstrip('/')}"
            f"/videos/{video_version}/separate_video/{output_filename}"
        )

        # The filename includes the ordered IDs, so it can safely serve as a
        # cache for the same report and selection.
        if output_path.exists():
            return {
                "video_url": video_url,
                "track_ids": track_ids,
                "segment_ids": segment_ids,
                "report_id": report_id,
                "source": "filesystem",
            }

        first_frame = None
        for event in frame_events:
            first_frame = cv2.imread(
                str(SeparateVideoGenerator._get_frame_path(event.full_frame_url))
            )
            if first_frame is not None:
                break

        if first_frame is None:
            raise ValueError("No valid frames were found for the selected tracks.")

        height, width = first_frame.shape[:2]
        writer = VideoWriter(
            output_path=str(output_path), fps=fps, width=width, height=height
        )
        frames_written = 0

        try:
            for event in frame_events:
                frame = cv2.imread(
                    str(SeparateVideoGenerator._get_frame_path(event.full_frame_url))
                )
                if frame is None:
                    continue
                source_height, source_width = frame.shape[:2]
                if frame.shape[1] != width or frame.shape[0] != height:
                    frame = cv2.resize(frame, (width, height))
                SeparateVideoGenerator._draw_tracked_person(
                    frame, event, source_width, source_height
                )
                writer.write(frame)
                frames_written += 1
                print(
                    f"[MERGED VIDEO] track_id={event.track.track_id} "
                    f"segment_id={event.segment_id} "
                    f"frame_number={event.frame_number} written"
                )
        finally:
            writer.release()

        if frames_written == 0:
            raise ValueError("No valid frames were written.")

        SeparateVideoGenerator.convert_to_browser_format(str(output_path))

        return {
            "video_url": video_url,
            "track_ids": track_ids,
            "segment_ids": segment_ids,
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
