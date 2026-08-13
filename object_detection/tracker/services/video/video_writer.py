from pathlib import Path
import cv2


class VideoWriter:
    """
    Writes processed frames to an output video.
    """

    def __init__(
        self,
        output_path: str,
        fps: float,
        width: int,
        height: int,
    ):
        self.output_path = Path(output_path)

        self.output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        self.writer = cv2.VideoWriter(
            str(self.output_path),
            fourcc,
            fps,
            (width, height),
        )

        if not self.writer.isOpened():
            raise RuntimeError(
                f"Unable to create output video: {self.output_path}"
            )

    def write(self, frame):
        self.writer.write(frame)

    def release(self):
        self.writer.release()