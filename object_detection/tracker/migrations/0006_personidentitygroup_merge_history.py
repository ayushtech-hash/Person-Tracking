# Generated manually for reversible manual identity-group merges.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0005_manualgroupingsuggestion_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="personidentitygroup",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="personidentitygroup",
            name="merged_into",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="merged_groups",
                to="tracker.personidentitygroup",
            ),
        ),
        migrations.CreateModel(
            name="ManualIdentityGroupMerge",
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
                ("moved_track_ids", models.TextField(default="[]")),
                ("is_undone", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("undone_at", models.DateTimeField(blank=True, null=True)),
                (
                    "duplicate_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="merges_absorbed",
                        to="tracker.personidentitygroup",
                    ),
                ),
                (
                    "primary_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="merges_kept",
                        to="tracker.personidentitygroup",
                    ),
                ),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="manual_identity_group_merges",
                        to="tracker.trackingreport",
                    ),
                ),
                (
                    "source_suggestion",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="merge_history",
                        to="tracker.manualgroupingsuggestion",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
