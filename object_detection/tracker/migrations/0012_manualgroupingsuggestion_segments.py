from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0011_manualidentitygroupmerge_moved_segment_ids"),
    ]

    operations = [
        migrations.AddField(
            model_name="manualgroupingsuggestion",
            name="first_segment",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="manual_suggestions_as_first",
                to="tracker.tracksegment",
            ),
        ),
        migrations.AddField(
            model_name="manualgroupingsuggestion",
            name="second_segment",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="manual_suggestions_as_second",
                to="tracker.tracksegment",
            ),
        ),
    ]
