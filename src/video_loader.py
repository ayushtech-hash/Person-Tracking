from pathlib import Path
import cv2


class VideoLoader:
    def __init__(self, video_path: str):
        self.video_path = Path(video_path)

        if not self.video_path.exists():
            raise FileNotFoundError(
                f"Video not found: {self.video_path}"
            )

        self.cap = cv2.VideoCapture(str(self.video_path))

        if not self.cap.isOpened():
            raise ValueError(
                f"Unable to open video: {self.video_path}"
            )

        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self.duration = (
            self.frame_count / self.fps
            if self.fps > 0 else 0
        )

    def get_info(self):
        """Return video metadata."""
        return {
            "name": self.video_path.name,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "frame_count": self.frame_count,
            "duration": self.duration,
        }

    def read(self):
        """Read the next frame."""
        return self.cap.read()

    def set_frame(self, frame_number: int):
        """Jump to a specific frame."""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    def release(self):
        """Release video resources."""
        self.cap.release()