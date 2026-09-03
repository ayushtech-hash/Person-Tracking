from pathlib import Path
import subprocess
import cv2


class VideoPreprocessor:
    """
    Validates a video for OpenCV compatibility.
    If the video cannot be decoded properly, it is converted
    to an OpenCV-friendly format using FFmpeg.
    """

    @staticmethod
    def preprocess(video_path: str) -> str:
        """
        Returns a video path that can be safely processed by OpenCV.

        Parameters
        ----------
        video_path : str
            Path to the input video.

        Returns
        -------
        str
            Original video path if compatible,
            otherwise path to the converted video.
        """

        video = Path(video_path)

        if not video.exists():
            raise FileNotFoundError(
                f"Video not found: {video}"
            )

        # Try reading the first frame with OpenCV
        cap = cv2.VideoCapture(str(video))
        ret, _ = cap.read()
        cap.release()

        if ret:
            print("✅ Video is OpenCV compatible.")
            return str(video)

        print("⚠️ Video is not OpenCV compatible.")
        print("Converting video using FFmpeg...")

        converted_video = (
            video.parent /
            f"{video.stem}_converted.mp4"
        )

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(converted_video),
        ]

        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        except FileNotFoundError:
            raise RuntimeError(
                "FFmpeg is not installed or not available in your system PATH."
            )

        except subprocess.CalledProcessError:
            raise RuntimeError(
                "FFmpeg failed to convert the video."
            )

        print(f"✅ Converted video saved to: {converted_video}")

        return str(converted_video)