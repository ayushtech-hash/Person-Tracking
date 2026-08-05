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
        print(f"Frames Seen      : {report.frames_seen}")
        print(f"Output Video     : {output_video}")

        print("=" * 40)

    @staticmethod
    def print_all_reports(
        reports: list[PresenceReport],
        output_video: str,
    ) -> None:

        print("\n" + "=" * 50)
        print("          PERSON TRACKING REPORT")
        print("=" * 50)

        print(
            f"{'Track ID':<12}"
            f"{'Frames Seen':<18}"
            f"{'Visible Duration (sec)':<25}"
        )

        print("-" * 50)

        for report in reports:

            print(
                f"{report.track_id:<12}"
                f"{report.frames_seen:<18}" 
                f"{report.visible_duration:<25.2f}"
            )

        total_visible_time = sum(
        report.visible_duration
        for report in reports
)

        print("-" * 50)

        print(f"Total Persons Tracked : {len(reports)}")
        print(f"Total Visible Time    : {total_visible_time:.2f} sec")
        print(f"Output Video          : {output_video}")

        print("=" * 50)