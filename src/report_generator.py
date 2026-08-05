from src.presence_tracker import PresenceReport


class ReportGenerator:
    """
    Generates reports for tracked persons.
    """

    @staticmethod
    def print_report(
        report: PresenceReport,
        output_video: str,
    ) -> None:

        print("\n" + "=" * 40)
        print("      PERSON TRACKING REPORT")
        print("=" * 40)

        print(f"Track ID         : {report.track_id}")
        print(f"First Seen       : {report.first_seen:.2f} sec")
        print(f"Last Seen        : {report.last_seen:.2f} sec")
        print(f"Visible Duration : {report.visible_duration:.2f} sec")

        print(f"Output Video     : {output_video}")

        print("=" * 40)