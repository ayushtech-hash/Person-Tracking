import json

from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

import numpy as np

from .services.reidentification import OSNetFeatureExtractor, PersonSimilarityIndex
from .services.reporting.report_generator import ReportGenerator
from .models import (
    ManualGroupingSuggestion,
    ManualIdentityGroupMerge,
    PersonTrackStats,
    TrackFrameEvent,
    TrackingReport,
)


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

    def test_manual_review_range_creates_suggestion_between_groups(self):
        index = PersonSimilarityIndex(
            threshold=0.8,
            manual_review_threshold=0.7,
        )
        events = [self._event(track_id=1, frame=1), self._event(track_id=2, frame=40)]
        with patch.object(
            OSNetFeatureExtractor,
            "embed_bgr",
            side_effect=[
                np.array([1.0, 0.0], dtype=np.float32),
                np.array([0.75, 0.6614378], dtype=np.float32),
            ],
        ):
            for event in events:
                index.add_and_find_similar(np.ones((2, 2, 3)), event)

        suggestions = index.get_manual_grouping_suggestions()
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["first_identity_group_id"], 1)
        self.assertEqual(suggestions[0]["second_identity_group_id"], 2)
        self.assertEqual(suggestions[0]["first_track_id"], 1)
        self.assertEqual(suggestions[0]["second_track_id"], 2)
        self.assertAlmostEqual(suggestions[0]["similarity"], 0.75, places=4)

    def test_manual_review_suggestion_is_persisted(self):
        report_data = {
            "reports": [
                {
                    "track_id": track_id,
                    "first_seen": 0,
                    "last_seen": 1,
                    "visible_duration": 1,
                    "frames_seen": 1,
                }
                for track_id in [1, 2]
            ],
            "peak_persons_detected": 2,
            "total_visible_time": 1,
        }
        report = ReportGenerator.save_to_database(
            report_data=report_data,
            output_video_url="/media/output.mp4",
            identity_groups=[
                {"identity_group_id": 1, "representative_track_id": 1, "track_ids": [1]},
                {"identity_group_id": 2, "representative_track_id": 2, "track_ids": [2]},
            ],
            manual_grouping_suggestions=[
                {
                    "first_identity_group_id": 1,
                    "second_identity_group_id": 2,
                    "first_track_id": 1,
                    "first_frame": 1,
                    "first_image_url": "/first.jpg",
                    "second_track_id": 2,
                    "second_frame": 40,
                    "second_image_url": "/second.jpg",
                    "similarity": 0.75,
                }
            ],
        )

        suggestion = ManualGroupingSuggestion.objects.get(report=report)
        self.assertEqual(suggestion.first_group.group_key, 1)
        self.assertEqual(suggestion.second_group.group_key, 2)
        self.assertEqual(suggestion.first_track_id, 1)
        self.assertEqual(suggestion.second_frame_number, 40)

    def test_manual_group_endpoint_merges_tracks_into_earliest_group(self):
        report = ReportGenerator.save_to_database(
            report_data={
                "reports": [
                    {
                        "track_id": track_id,
                        "first_seen": 0,
                        "last_seen": 1,
                        "visible_duration": 1,
                        "frames_seen": 1,
                    }
                    for track_id in [1, 2]
                ],
                "peak_persons_detected": 2,
                "total_visible_time": 1,
            },
            output_video_url="/media/output.mp4",
            identity_groups=[
                {"identity_group_id": 1, "representative_track_id": 1, "track_ids": [1]},
                {"identity_group_id": 2, "representative_track_id": 2, "track_ids": [2]},
            ],
            manual_grouping_suggestions=[
                {
                    "first_identity_group_id": 1,
                    "second_identity_group_id": 2,
                    "first_track_id": 1,
                    "first_frame": 1,
                    "first_image_url": "/first.jpg",
                    "second_track_id": 2,
                    "second_frame": 40,
                    "second_image_url": "/second.jpg",
                    "similarity": 0.75,
                }
            ],
        )
        suggestion = ManualGroupingSuggestion.objects.get(report=report)

        response = self.client.post(
            reverse("merge_manual_identity_groups"),
            {"report_id": report.id, "suggestion_id": suggestion.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["identity_group_id"], 1)
        self.assertEqual(response.json()["duplicate_identity_group_id"], 2)
        self.assertEqual(response.json()["identity_groups"][0]["crops"], [])
        self.assertEqual(report.identity_groups.count(), 2)
        remaining_group = report.identity_groups.get(group_key=1)
        self.assertEqual(remaining_group.group_key, 1)
        self.assertEqual(remaining_group.representative_track_id, 1)
        self.assertEqual(
            list(remaining_group.tracks.order_by("track_id").values_list("track_id", flat=True)),
            [1, 2],
        )
        absorbed_group = report.identity_groups.get(group_key=2)
        self.assertFalse(absorbed_group.is_active)
        self.assertEqual(absorbed_group.merged_into_id, remaining_group.id)
        merge_history = ManualIdentityGroupMerge.objects.get(report=report)
        self.assertEqual(json.loads(merge_history.moved_track_ids), [2])

        restored_track = PersonTrackStats.objects.get(report=report, track_id=2)
        TrackFrameEvent.objects.create(
            track=restored_track,
            frame_number=40,
            timestamp=1.6,
            full_frame_url="/full.jpg",
            cropped_image_url="/person.jpg",
            thumbnail_url="/second.jpg",
        )
        undo_response = self.client.post(
            reverse("undo_manual_identity_group_merge"),
            {"report_id": report.id, "manual_merge_id": merge_history.id},
        )
        self.assertEqual(undo_response.status_code, 200)
        self.assertEqual(undo_response.json()["restored_event"]["track_id"], 2)

        remaining_group.refresh_from_db()
        absorbed_group.refresh_from_db()
        merge_history.refresh_from_db()
        suggestion.refresh_from_db()
        self.assertEqual(
            list(remaining_group.tracks.values_list("track_id", flat=True)), [1]
        )
        self.assertEqual(
            list(absorbed_group.tracks.values_list("track_id", flat=True)), [2]
        )
        self.assertTrue(absorbed_group.is_active)
        self.assertIsNone(absorbed_group.merged_into_id)
        self.assertTrue(merge_history.is_undone)
        self.assertEqual(suggestion.status, ManualGroupingSuggestion.Status.PENDING)
        self.assertFalse(suggestion.is_resolved)

    def test_dismissed_manual_suggestion_does_not_change_groups(self):
        report = ReportGenerator.save_to_database(
            report_data={
                "reports": [
                    {
                        "track_id": track_id,
                        "first_seen": 0,
                        "last_seen": 1,
                        "visible_duration": 1,
                        "frames_seen": 1,
                    }
                    for track_id in [1, 2]
                ],
                "peak_persons_detected": 2,
                "total_visible_time": 1,
            },
            output_video_url="/media/output.mp4",
            identity_groups=[
                {"identity_group_id": 1, "representative_track_id": 1, "track_ids": [1]},
                {"identity_group_id": 2, "representative_track_id": 2, "track_ids": [2]},
            ],
            manual_grouping_suggestions=[
                {
                    "first_identity_group_id": 1,
                    "second_identity_group_id": 2,
                    "first_track_id": 1,
                    "first_frame": 1,
                    "first_image_url": "/first.jpg",
                    "second_track_id": 2,
                    "second_frame": 40,
                    "second_image_url": "/second.jpg",
                    "similarity": 0.75,
                }
            ],
        )
        suggestion = ManualGroupingSuggestion.objects.get(report=report)

        response = self.client.post(
            reverse("dismiss_manual_grouping_suggestion"),
            {"report_id": report.id, "suggestion_id": suggestion.id},
        )

        self.assertEqual(response.status_code, 200)
        suggestion.refresh_from_db()
        self.assertEqual(
            suggestion.status,
            ManualGroupingSuggestion.Status.DISMISSED,
        )
        self.assertTrue(suggestion.is_resolved)
        self.assertEqual(report.identity_groups.count(), 2)
        self.assertEqual(response.json()["remaining_suggestions"], [])

    def test_each_manual_merge_can_be_undone_independently(self):
        """Undoing groups 1/2 must not undo an unrelated groups 3/4 merge."""
        report = ReportGenerator.save_to_database(
            report_data={
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
                "peak_persons_detected": 4,
                "total_visible_time": 1,
            },
            output_video_url="/media/output.mp4",
            identity_groups=[
                {
                    "identity_group_id": track_id,
                    "representative_track_id": track_id,
                    "track_ids": [track_id],
                }
                for track_id in [1, 2, 3, 4]
            ],
            manual_grouping_suggestions=[
                {
                    "first_identity_group_id": 1,
                    "second_identity_group_id": 2,
                    "first_track_id": 1,
                    "first_frame": 1,
                    "first_image_url": "/one.jpg",
                    "second_track_id": 2,
                    "second_frame": 40,
                    "second_image_url": "/two.jpg",
                    "similarity": 0.75,
                },
                {
                    "first_identity_group_id": 3,
                    "second_identity_group_id": 4,
                    "first_track_id": 3,
                    "first_frame": 80,
                    "first_image_url": "/three.jpg",
                    "second_track_id": 4,
                    "second_frame": 120,
                    "second_image_url": "/four.jpg",
                    "similarity": 0.76,
                },
            ],
        )
        first_suggestion = report.manual_grouping_suggestions.get(
            first_group__group_key=1,
            second_group__group_key=2,
        )
        second_suggestion = report.manual_grouping_suggestions.get(
            first_group__group_key=3,
            second_group__group_key=4,
        )

        first_merge = self.client.post(
            reverse("merge_manual_identity_groups"),
            {"report_id": report.id, "suggestion_id": first_suggestion.id},
        )
        second_merge = self.client.post(
            reverse("merge_manual_identity_groups"),
            {"report_id": report.id, "suggestion_id": second_suggestion.id},
        )
        self.assertEqual(first_merge.status_code, 200)
        self.assertEqual(second_merge.status_code, 200)

        first_merge_id = first_merge.json()["manual_merge_id"]
        second_merge_id = second_merge.json()["manual_merge_id"]
        undo_first = self.client.post(
            reverse("undo_manual_identity_group_merge"),
            {"report_id": report.id, "manual_merge_id": first_merge_id},
        )
        self.assertEqual(undo_first.status_code, 200)

        group_one = report.identity_groups.get(group_key=1)
        group_two = report.identity_groups.get(group_key=2)
        group_three = report.identity_groups.get(group_key=3)
        group_four = report.identity_groups.get(group_key=4)
        self.assertEqual(list(group_one.tracks.values_list("track_id", flat=True)), [1])
        self.assertEqual(list(group_two.tracks.values_list("track_id", flat=True)), [2])
        self.assertTrue(group_two.is_active)
        self.assertEqual(
            list(group_three.tracks.order_by("track_id").values_list("track_id", flat=True)),
            [3, 4],
        )
        self.assertFalse(group_four.is_active)

        first_suggestion.refresh_from_db()
        second_suggestion.refresh_from_db()
        self.assertEqual(first_suggestion.status, ManualGroupingSuggestion.Status.PENDING)
        self.assertEqual(second_suggestion.status, ManualGroupingSuggestion.Status.GROUPED)

        undo_second = self.client.post(
            reverse("undo_manual_identity_group_merge"),
            {"report_id": report.id, "manual_merge_id": second_merge_id},
        )
        self.assertEqual(undo_second.status_code, 200)
        group_four.refresh_from_db()
        self.assertTrue(group_four.is_active)

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
