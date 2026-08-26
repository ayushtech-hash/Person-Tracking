from django.test import TestCase
from unittest.mock import patch

import numpy as np

from .services.reidentification import OSNetFeatureExtractor, PersonSimilarityIndex
from .services.reporting.report_generator import ReportGenerator
from .models import PersonTrackStats, TrackFrameEvent, TrackingReport


class PersonSimilarityIndexTests(TestCase):
    def _event(self, track_id, frame):
        return {
            "track_id": track_id,
            "frame": frame,
            "time_sec": frame / 25,
            "image_url": f"/thumbnail-{frame}.jpg",
            "person_crop_url": f"/person-{frame}.jpg",
        }

    def test_indirect_upper_half_matches_form_one_group(self):
        """A later match inherits its earlier crop's identity group."""
        embeddings = [
            np.array([1.0, 0.0, 0.0], dtype=np.float32),  # frame 1
            np.array([0.0, 0.0, 1.0], dtype=np.float32),  # frame 40
            np.array([0.8660254, 0.5, 0.0], dtype=np.float32),  # frame 80
            np.array([0.5, 0.8660254, 0.0], dtype=np.float32),  # frame 130
        ]
        events = [
            self._event(track_id=1, frame=1),
            self._event(track_id=2, frame=40),
            self._event(track_id=3, frame=80),
            self._event(track_id=4, frame=130),
        ]
        index = PersonSimilarityIndex(threshold=0.8)

        with patch.object(
            OSNetFeatureExtractor,
            "embed_bgr",
            side_effect=embeddings,
        ):
            for event in events:
                index.add_and_find_similar(np.ones((2, 2, 3)), event)

        self.assertEqual(events[0]["identity_group_id"], events[2]["identity_group_id"])
        self.assertEqual(events[2]["identity_group_id"], events[3]["identity_group_id"])
        self.assertNotEqual(events[0]["identity_group_id"], events[1]["identity_group_id"])
        self.assertTrue(events[0]["is_identity_representative"])
        self.assertTrue(events[1]["is_identity_representative"])
        self.assertFalse(events[2]["is_identity_representative"])
        self.assertFalse(events[3]["is_identity_representative"])
        self.assertEqual(events[0]["identity_group_track_ids"], [1, 3, 4])

    def test_identity_groups_are_persisted_with_their_tracks(self):
        report_data = {
            "reports": [
                {
                    "track_id": track_id,
                    "first_seen": 0,
                    "last_seen": 1,
                    "visible_duration": 1,
                    "frames_seen": 1,
                }
                for track_id in [1, 2, 3, 4]
            ],
            "peak_persons_detected": 2,
            "total_visible_time": 1,
        }
        report = ReportGenerator.save_to_database(
            report_data=report_data,
            output_video_url="/media/output.mp4",
            identity_groups=[
                {
                    "identity_group_id": 1,
                    "representative_track_id": 1,
                    "track_ids": [1, 3, 4],
                },
                {
                    "identity_group_id": 2,
                    "representative_track_id": 2,
                    "track_ids": [2],
                },
            ],
        )

        groups = list(report.identity_groups.all())
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].representative_track_id, 1)
        self.assertEqual(
            list(groups[0].tracks.order_by("track_id").values_list("track_id", flat=True)),
            [1, 3, 4],
        )
        self.assertEqual(
            list(groups[1].tracks.values_list("track_id", flat=True)),
            [2],
        )

    def test_existing_processing_report_keeps_all_frame_events(self):
        processing_report = TrackingReport.objects.create(
            input_video="/media/uploads/input.mp4",
            output_video="/media/videos/pending.mp4",
        )
        track = PersonTrackStats.objects.create(
            report=processing_report,
            track_id=1,
            first_seen=0,
            last_seen=0,
            visible_duration=0,
            frames_seen=0,
        )
        for frame_number in [1, 2, 3]:
            TrackFrameEvent.objects.create(
                track=track,
                frame_number=frame_number,
                timestamp=frame_number / 25,
                full_frame_url=f"/media/frame-{frame_number}.jpg",
            )

        finalized_report = ReportGenerator.save_to_database(
            report_data={
                "reports": [{
                    "track_id": 1,
                    "first_seen": 0.04,
                    "last_seen": 0.12,
                    "visible_duration": 0.12,
                    "frames_seen": 3,
                }],
                "peak_persons_detected": 1,
                "total_visible_time": 0.12,
            },
            output_video_url="/media/videos/output.mp4",
            tracking_report=processing_report,
        )

        self.assertEqual(finalized_report.id, processing_report.id)
        self.assertEqual(finalized_report.track_stats.count(), 1)
        self.assertEqual(
            finalized_report.track_stats.get(track_id=1).frame_events.count(),
            3,
        )
