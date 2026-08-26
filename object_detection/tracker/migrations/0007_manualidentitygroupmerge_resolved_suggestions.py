# Generated manually for precise manual-group merge undo.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0006_personidentitygroup_merge_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="manualidentitygroupmerge",
            name="resolved_suggestion_ids",
            field=models.TextField(default="[]"),
        ),
    ]
