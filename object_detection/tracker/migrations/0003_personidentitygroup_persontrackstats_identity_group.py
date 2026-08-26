# Generated manually for OSNet identity-group persistence.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        # The project already has a 0003 migration for separate_video_url.
        # Depend on it so these migrations form one chain rather than two
        # competing leaves.
        ("tracker", "0003_persontrackstats_separate_video_url"),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonIdentityGroup",
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
                ("group_key", models.PositiveIntegerField()),
                ("representative_track_id", models.IntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="identity_groups",
                        to="tracker.trackingreport",
                    ),
                ),
            ],
            options={
                "ordering": ["group_key"],
            },
        ),
        migrations.AddField(
            model_name="persontrackstats",
            name="identity_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tracks",
                to="tracker.personidentitygroup",
            ),
        ),
        migrations.AddConstraint(
            model_name="personidentitygroup",
            constraint=models.UniqueConstraint(
                fields=("report", "group_key"),
                name="unique_report_identity_group",
            ),
        ),
    ]
