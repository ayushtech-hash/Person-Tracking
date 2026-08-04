from dataclasses import dataclass


@dataclass
class TimeRange:
    start_frame: int
    end_frame: int
    start_seconds: float
    end_seconds: float


class TimeSelector:

    @staticmethod
    def time_to_seconds(time_str: str) -> float:
        """
        Convert HH:MM:SS into seconds.
        """
        h, m, s = map(int, time_str.split(":"))
        return h * 3600 + m * 60 + s

    @staticmethod
    def seconds_to_frame(seconds: float, fps: float) -> int:
        return int(seconds * fps)

    @classmethod
    def get_frame_range(
        cls,
        start_time: str,
        end_time: str,
        fps: float,
        duration: float,
    ) -> TimeRange:

        start_seconds = cls.time_to_seconds(start_time)
        end_seconds = cls.time_to_seconds(end_time)

        if start_seconds >= end_seconds:
            raise ValueError(
                "Start time must be before end time."
            )

        if end_seconds > duration:
            raise ValueError(
                "End time exceeds video duration."
            )

        return TimeRange(
            start_frame=cls.seconds_to_frame(start_seconds, fps),
            end_frame=cls.seconds_to_frame(end_seconds, fps),
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )