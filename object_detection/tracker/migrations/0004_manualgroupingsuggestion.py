# Generated manually for persisted manual OSNet review suggestions.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0003_personidentitygroup_persontrackstats_identity_group"),
    ]

    operations = [
        migrations.CreateModel(
            name="ManualGroupingSuggestion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("first_track_id", models.IntegerField()),
                ("first_frame_number", models.PositiveIntegerField()),
                ("first_image_url", models.CharField(blank=True, max_length=1000)),
                ("second_track_id", models.IntegerField()),
                ("second_frame_number", models.PositiveIntegerField()),
                ("second_image_url", models.CharField(blank=True, max_length=1000)),
                ("similarity", models.FloatField()),
                ("is_resolved", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "first_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="manual_suggestions_as_first",
                        to="tracker.personidentitygroup",
                    ),
                ),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="manual_grouping_suggestions",
                        to="tracker.trackingreport",
                    ),
                ),
                (
                    "second_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="manual_suggestions_as_second",
                        to="tracker.personidentitygroup",
                    ),
                ),
            ],
            options={"ordering": ["-similarity", "id"]},
        ),
        migrations.AddConstraint(
            model_name="manualgroupingsuggestion",
            constraint=models.UniqueConstraint(
                fields=("report", "first_group", "second_group"),
                name="unique_manual_group_suggestion",
            ),
        ),
    ]
