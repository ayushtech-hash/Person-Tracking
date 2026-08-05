from dataclasses import dataclass

@dataclass
class PresenceInfo:
    """
    Stores when a tracked person first and last appears.
    """
    first_frame: int
    last_frame: int
    total_frames_seen: int = 1


@dataclass
class PresenceReport:
    """
    Human-readable presence information.
    """
    track_id: int
    first_seen: float
    last_seen: float
    visible_duration: float


class PresenceTracker:

    def __init__(self):
        # {track_id: PresenceInfo}
        self.presence: dict[int, PresenceInfo] = {}

    def update(
        self,
        tracked_detections,
        current_frame: int,
    ) -> None:
        """
        Update presence information for all tracked persons
        in the current frame.
        """

        for detection in tracked_detections:

            track_id = detection.track_id

            if track_id not in self.presence:

                self.presence[track_id] = PresenceInfo(
                    first_frame=current_frame,
                    last_frame=current_frame,
                    total_frames_seen=1,
                )

            else:

                # self.presence[track_id].last_frame = current_frame
                info = self.presence[track_id]

                info.last_frame = current_frame
                info.total_frames_seen += 1

    def get_presence(
        self,
        track_id: int,
        fps: float,
    ) -> PresenceReport | None:
        """
        Return presence information for a single person.
        """

        if track_id not in self.presence:
            return None

        info = self.presence[track_id]

        first_seen = info.first_frame / fps
        last_seen = info.last_frame / fps

        # duration = (
        #     info.last_frame
        #     - info.first_frame
        #     + 1
        # ) / fps
        duration = info.total_frames_seen / fps

        return PresenceReport(
            track_id=track_id,
            first_seen=first_seen,
            last_seen=last_seen,
            visible_duration=duration,
        )

    def get_all_presence(
        self,
        fps: float,
    ) -> list[PresenceReport]:
        """
        Return presence information for every tracked person.
        """

        reports = []

        for track_id in sorted(self.presence.keys()):

            report = self.get_presence(track_id, fps)

            if report is not None:
                reports.append(report)

        return reports