from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0010_tracksegment_identity_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="manualidentitygroupmerge",
            name="moved_segment_ids",
            field=models.TextField(default="[]"),
        ),
    ]
