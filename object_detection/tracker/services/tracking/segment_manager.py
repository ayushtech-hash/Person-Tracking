"""Lifecycle management for continuous uses of ByteTrack IDs.

This module owns segment persistence and splitting mechanics.  The separate
appearance validator decides whether an ID has actually switched people.
"""

from typing import Dict

from django.db.models import Count, Max, Min

from tracker.models import TrackFrameEvent, TrackSegment, TrackingReport


class TrackSegmentManager:
    """Create and update the active segment for each raw tracker ID.

    One processing run owns one manager instance.  The in-memory cache avoids
    querying for the same active segment on every video frame, while the
    database rows make the assigned segment available to later workflows.
    """

    def __init__(self, report):
        if isinstance(report, TrackingReport):
            self.report = report
        else:
            self.report = TrackingReport.objects.get(pk=report)
        self._active_segments: Dict[int, TrackSegment] = {}

    def get_or_start_segment(self, raw_track_id, frame_number, timestamp):
        """Return the active segment for a raw ByteTrack ID, creating it once."""
        raw_track_id = int(raw_track_id)
        segment = self._active_segments.get(raw_track_id)
        if segment is not None:
            return segment

        # This lookup also makes the manager safe to reconstruct if processing
        # is resumed within the same report in a future workflow.
        segment = (
            TrackSegment.objects.filter(
                report=self.report,
                raw_track_id=raw_track_id,
                is_active=True,
            )
            .order_by("-segment_number")
            .first()
        )
        if segment is None:
            previous = TrackSegment.objects.filter(
                report=self.report,
                raw_track_id=raw_track_id,
            ).aggregate(max_number=Max("segment_number"))
            segment = TrackSegment.objects.create(
                report=self.report,
                raw_track_id=raw_track_id,
                segment_number=(previous["max_number"] or 0) + 1,
                first_frame=frame_number,
                last_frame=frame_number,
                first_seen=timestamp,
                last_seen=timestamp,
                frames_seen=0,
            )
            print(
                "===================== [SEGMENT CREATED] ================"
                f"report={self.report.id} raw_id={raw_track_id} "
                f"segment={segment.segment_number} frame={frame_number} "
                f"time={float(timestamp):.2f}s"
                "===================== [SEGMENT CREATED] ================"
            )

        self._active_segments[raw_track_id] = segment
        return segment

    @staticmethod
    def record_frame(segment, frame_number, timestamp):
        """Persist the latest frame metadata after a new frame event is stored."""
        segment.last_frame = int(frame_number)
        segment.last_seen = float(timestamp)
        segment.frames_seen += 1
        segment.save(update_fields=["last_frame", "last_seen", "frames_seen"])

    def split_segment(self, raw_track_id, frame_number, timestamp, reason):
        """Close the current segment and start its replacement immediately."""
        raw_track_id = int(raw_track_id)
        previous_segment = self.get_or_start_segment(
            raw_track_id=raw_track_id,
            frame_number=frame_number,
            timestamp=timestamp,
        )
        previous_segment.is_active = False
        previous_segment.switch_reason = reason
        previous_segment.save(update_fields=["is_active", "switch_reason"])

        highest_number = TrackSegment.objects.filter(
            report=self.report,
            raw_track_id=raw_track_id,
        ).aggregate(max_number=Max("segment_number"))["max_number"] or 0
        new_segment = TrackSegment.objects.create(
            report=self.report,
            raw_track_id=raw_track_id,
            segment_number=highest_number + 1,
            first_frame=frame_number,
            last_frame=frame_number,
            first_seen=timestamp,
            last_seen=timestamp,
            frames_seen=0,
        )

        # print(
        #     "==========================[ID SWITCH CONFIRMED]================ "
        #     f"report={self.report.id} raw_id={raw_track_id} "
        #     f"closed_segment={previous_segment.segment_number} "
        #     f"new_segment={new_segment.segment_number} "
        #     f"frame={frame_number} time={float(timestamp):.2f}s "
        #     f"reason={reason}"
        #     "==========================[ID SWITCH CONFIRMED]================ "
        # )
        self._active_segments[raw_track_id] = new_segment
        return previous_segment, new_segment

    @staticmethod
    def move_events_to_segment(previous_segment, new_segment, event_ids):
        """Move confirmed switch-candidate frames into the new segment."""
        if not event_ids:
            return

        TrackFrameEvent.objects.filter(
            pk__in=event_ids,
            segment=previous_segment,
        ).update(segment=new_segment)

        previous_summary = TrackFrameEvent.objects.filter(
            segment=previous_segment,
        ).aggregate(
            frames=Count("id"),
            first_frame=Min("frame_number"),
            last_frame=Max("frame_number"),
            first_seen=Min("timestamp"),
            last_seen=Max("timestamp"),
        )
        previous_segment.frames_seen = previous_summary["frames"]
        if previous_summary["frames"]:
            previous_segment.first_frame = previous_summary["first_frame"]
            previous_segment.last_frame = previous_summary["last_frame"]
            previous_segment.first_seen = previous_summary["first_seen"]
            previous_segment.last_seen = previous_summary["last_seen"]
        previous_segment.save(
            update_fields=[
                "frames_seen",
                "first_frame",
                "last_frame",
                "first_seen",
                "last_seen",
            ]
        )

        new_summary = TrackFrameEvent.objects.filter(segment=new_segment).aggregate(
            frames=Count("id"),
            first_frame=Min("frame_number"),
            last_frame=Max("frame_number"),
            first_seen=Min("timestamp"),
            last_seen=Max("timestamp"),
        )
        new_segment.frames_seen = new_summary["frames"]
        if new_summary["frames"]:
            new_segment.first_frame = new_summary["first_frame"]
            new_segment.last_frame = new_summary["last_frame"]
            new_segment.first_seen = new_summary["first_seen"]
            new_segment.last_seen = new_summary["last_seen"]
        new_segment.save(
            update_fields=[
                "frames_seen",
                "first_frame",
                "last_frame",
                "first_seen",
                "last_seen",
            ]
        )

    def print_segment_summary(self):
        """
        Print all segments grouped by their raw ByteTrack Track ID.
        """
        segments = (
            TrackSegment.objects
            .filter(report=self.report)
            .order_by("raw_track_id", "segment_number")
        )

        print("\n")
        print("=" * 55)
        print("              TRACK SEGMENT SUMMARY")
        print("=" * 55)

        if not segments.exists():
            print("No segments found.")
            print("=" * 55)
            return

        current_track_id = None
        segment_list = []

        for segment in segments:
            if current_track_id is None:
                current_track_id = segment.raw_track_id

            if segment.raw_track_id != current_track_id:
                print(
                    f"Track {current_track_id} → "
                    + ", ".join(segment_list)
                )

                current_track_id = segment.raw_track_id
                segment_list = []

            segment_list.append(
                f"Segment {segment.segment_number}"
            )

        # Print the final track
        if segment_list:
            print(
                f"Track {current_track_id} → "
                + ", ".join(segment_list)
            )

        print("=" * 55)
        print()

    def close_all(self):
        """Mark this run's remaining active segments as complete."""
        active_segments = list(self._active_segments.values())
        if active_segments:
            TrackSegment.objects.filter(
                pk__in=[segment.pk for segment in active_segments],
                is_active=True,
            ).update(is_active=False)
        self._active_segments.clear()
        self.print_segment_summary()
