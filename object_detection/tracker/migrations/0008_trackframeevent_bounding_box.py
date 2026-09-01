from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0007_manualidentitygroupmerge_resolved_suggestions"),
    ]

    operations = [
        migrations.AddField(
            model_name="trackframeevent",
            name="bbox_x1",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="trackframeevent",
            name="bbox_y1",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="trackframeevent",
            name="bbox_x2",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="trackframeevent",
            name="bbox_y2",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
