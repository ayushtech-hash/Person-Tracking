from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0008_trackframeevent_bounding_box"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrackSegment",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("raw_track_id", models.IntegerField()),
                ("segment_number", models.PositiveIntegerField()),
                ("first_frame", models.PositiveIntegerField()),
                ("last_frame", models.PositiveIntegerField()),
                ("first_seen", models.FloatField()),
                ("last_seen", models.FloatField()),
                ("frames_seen", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("switch_reason", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="track_segments",
                        to="tracker.trackingreport",
                    ),
                ),
            ],
            options={
                "ordering": ["raw_track_id", "segment_number"],
            },
        ),
        migrations.AddIndex(
            model_name="tracksegment",
            index=models.Index(
                fields=["report", "raw_track_id"],
                name="tracker_tra_report__cf2e4e_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="tracksegment",
            constraint=models.UniqueConstraint(
                fields=("report", "raw_track_id", "segment_number"),
                name="unique_report_raw_track_segment",
            ),
        ),
        migrations.AddField(
            model_name="trackframeevent",
            name="segment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="frame_events",
                to="tracker.tracksegment",
            ),
        ),
    ]
