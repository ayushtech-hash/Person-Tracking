from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0009_tracksegment_trackframeevent_segment"),
    ]

    operations = [
        migrations.AddField(
            model_name="tracksegment",
            name="identity_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="segments",
                to="tracker.personidentitygroup",
            ),
        ),
    ]
