from tracker.services.tracking.presence_tracker import PresenceReport
from typing import Dict, List, Optional, Union
from tracker.models import (
    PersonIdentityGroup,
    PersonTrackStats,
    TrackingReport,
    TrackFrameEvent,
)


class ReportGenerator:
    """
    Generates reports for tracked persons.
    """ 

    @staticmethod
    def create_processing_report(
        output_video_url: str,
        input_video_url: str = "",
        selected_track_id: Optional[int] = None,
    ) -> TrackingReport:

        return TrackingReport.objects.create(
            input_video=input_video_url,
            output_video=output_video_url,
            peak_persons_detected=0,
            total_visible_time=0,
            selected_track_id=selected_track_id,
        )


    @staticmethod
    def generate_report(
        report: PresenceReport,
        output_video: str,
        peak_persons_detected: int = 0,
    ):

        return {
            "track_id": report.track_id,
            "first_seen": round(report.first_seen, 2),
            "last_seen": round(report.last_seen, 2),
            "visible_duration": round(report.visible_duration, 2),
            "frames_seen": report.frames_seen,
            "peak_persons_detected": peak_persons_detected,
            "output_video": output_video,
        }

    @staticmethod
    def generate_all_reports(
        reports: List[PresenceReport],
        output_video: str,
        peak_persons_detected: int = 0,
    ):

        report_list = []

        for report in reports:

            report_list.append(
                {
                    "track_id": report.track_id,
                    "first_seen": round(report.first_seen, 2),
                    "last_seen": round(report.last_seen, 2),
                    "visible_duration": round(report.visible_duration, 2),
                    "frames_seen": report.frames_seen,
                }
            )

        total_visible_time = sum(
            report.visible_duration
            for report in reports
        )

        return {
            "reports": report_list,
            "peak_persons_detected": peak_persons_detected,
            "total_visible_time": round(total_visible_time, 2),
            "output_video": output_video,
        }

    @staticmethod
    def save_to_database(
        report_data: Dict,
        output_video_url: str,
        input_video_url: str = "",
        selected_track_id: Optional[int] = None,
        frame_events: Optional[List[Dict]] = None,
        identity_groups: Optional[List[Dict]] = None,
        tracking_report: Optional[TrackingReport] = None,
    ) -> TrackingReport:

        frame_events = frame_events or []
        identity_groups = identity_groups or []

        # =========================================================
        # 1. Create or finalize TrackingReport + PersonTrackStats
        # =========================================================

        if "reports" in report_data:
            report_items = report_data["reports"]
            peak_persons_detected = report_data["peak_persons_detected"]
            total_visible_time = report_data["total_visible_time"]
            final_selected_track_id = None
        else:
            report_items = [report_data]
            peak_persons_detected = report_data["peak_persons_detected"]
            total_visible_time = report_data["visible_duration"]
            final_selected_track_id = selected_track_id or report_data["track_id"]

        if tracking_report is not None:
            # The processing report already owns every TrackFrameEvent saved
            # while frames were being processed.  Finalize it in place rather
            # than creating a second report that would contain only snapshots.
            tracking_report.input_video = input_video_url
            tracking_report.output_video = output_video_url
            tracking_report.peak_persons_detected = peak_persons_detected
            tracking_report.total_visible_time = total_visible_time
            tracking_report.selected_track_id = final_selected_track_id
            tracking_report.save(
                update_fields=[
                    "input_video",
                    "output_video",
                    "peak_persons_detected",
                    "total_visible_time",
                    "selected_track_id",
                ]
            )

            for item in report_items:
                PersonTrackStats.objects.update_or_create(
                    report=tracking_report,
                    track_id=item["track_id"],
                    defaults={
                        "first_seen": item["first_seen"],
                        "last_seen": item["last_seen"],
                        "visible_duration": item["visible_duration"],
                        "frames_seen": item["frames_seen"],
                    },
                )

        if "reports" in report_data:
            if tracking_report is None:
                tracking_report = TrackingReport.objects.create(
                    input_video=input_video_url,
                    output_video=output_video_url,
                    peak_persons_detected=peak_persons_detected,
                    total_visible_time=total_visible_time,
                )

                PersonTrackStats.objects.bulk_create(
                    [
                        PersonTrackStats(
                            report=tracking_report,
                            track_id=item["track_id"],
                            first_seen=item["first_seen"],
                            last_seen=item["last_seen"],
                            visible_duration=item["visible_duration"],
                            frames_seen=item["frames_seen"],
                        )
                        for item in report_items
                    ]
                )

        else:
            if tracking_report is None:
                tracking_report = TrackingReport.objects.create(
                    input_video=input_video_url,
                    output_video=output_video_url,
                    peak_persons_detected=peak_persons_detected,
                    total_visible_time=total_visible_time,
                    selected_track_id=final_selected_track_id,
                )

                PersonTrackStats.objects.create(
                    report=tracking_report,
                    track_id=report_data["track_id"],
                    first_seen=report_data["first_seen"],
                    last_seen=report_data["last_seen"],
                    visible_duration=report_data["visible_duration"],
                    frames_seen=report_data["frames_seen"],
                )

        # =========================================================
        # 2. Get the PersonTrackStats we just created
        # =========================================================

        track_stats = tracking_report.track_stats.all()

        track_stats_by_id = {
            stat.track_id: stat
            for stat in track_stats
        }

        # =========================================================
        # 3. Persist OSNet identity groups and connect their tracks
        # =========================================================

        # The OSNet index is scoped to one upload.  Its numeric group key is
        # meaningful only inside this report, which is why the model enforces
        # uniqueness on (report, group_key).
        for group in identity_groups:
            group_key = group.get("identity_group_id")
            representative_track_id = group.get("representative_track_id")
            if group_key is None or representative_track_id is None:
                continue

            PersonIdentityGroup.objects.update_or_create(
                report=tracking_report,
                group_key=int(group_key),
                defaults={
                    "representative_track_id": int(representative_track_id),
                },
            )

        if identity_groups:
            persisted_groups = {
                group.group_key: group
                for group in tracking_report.identity_groups.all()
            }
            tracks_to_update = []

            for group in identity_groups:
                group_key = group.get("identity_group_id")
                persisted_group = persisted_groups.get(group_key)
                if persisted_group is None:
                    continue

                for track_id in group.get("track_ids", []):
                    track_stat = track_stats_by_id.get(int(track_id))
                    if track_stat is None:
                        print(
                            f"WARNING: No PersonTrackStats found for "
                            f"identity-group track_id={track_id}"
                        )
                        continue
                    track_stat.identity_group = persisted_group
                    tracks_to_update.append(track_stat)

            if tracks_to_update:
                PersonTrackStats.objects.bulk_update(
                    tracks_to_update,
                    ["identity_group"],
                )

        # =========================================================
        # 4. Create TrackFrameEvent records
        # =========================================================

        for event in frame_events:

            track_id = event.get("track_id")

            if track_id is None:
                continue

            track_stat = track_stats_by_id.get(
                int(track_id)
            )

            if track_stat is None:
                print(
                    f"WARNING: No PersonTrackStats found "
                    f"for track_id={track_id}"
                )
                continue

            # The per-frame callback has normally already created this row.
            # Update the snapshot URLs without replacing its full-frame URL,
            # which is the frame stream used for generated videos.
            frame_event, created = TrackFrameEvent.objects.update_or_create(
                track=track_stat,
                frame_number=int(event.get("frame", 0)),
                defaults={
                    "timestamp": float(
                        event.get("time_sec", event.get("time", 0))
                    ),
                    "cropped_image_url": event.get("person_crop_url", ""),
                    "thumbnail_url": event.get("image_url", ""),
                },
            )
            if created:
                frame_event.full_frame_url = event.get("full_frame_url", "")
                frame_event.save(update_fields=["full_frame_url"])

        # =========================================================
        # 5. Save all frame events at once
        # =========================================================

        return tracking_report

    @staticmethod
    def serialize_tracking_report(
        tracking_report: TrackingReport,
    ) -> Dict[str, Union[int, float, str, List[Dict]]]:
        track_stats = list(tracking_report.track_stats.all())

        if tracking_report.selected_track_id is not None:
            stat = track_stats[0]
            return {
                "id": tracking_report.id,
                "track_id": stat.track_id,
                "first_seen": stat.first_seen,
                "last_seen": stat.last_seen,
                "visible_duration": stat.visible_duration,
                "frames_seen": stat.frames_seen,
                "peak_persons_detected": tracking_report.peak_persons_detected,
                "output_video": tracking_report.output_video,
            }

        return {
            "id": tracking_report.id,
            "reports": [
                {
                    "track_id": stat.track_id,
                    "first_seen": stat.first_seen,
                    "last_seen": stat.last_seen,
                    "visible_duration": stat.visible_duration,
                    "frames_seen": stat.frames_seen,
                }
                for stat in track_stats
            ],
            "peak_persons_detected": tracking_report.peak_persons_detected,
            "total_visible_time": tracking_report.total_visible_time,
            "output_video": tracking_report.output_video,
        }

    # ===========================
    # EXISTING CLI METHODS
    # ===========================

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
        reports: List[PresenceReport],
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
