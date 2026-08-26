# Generated manually for manual suggestion dismissal/grouping state.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0004_manualgroupingsuggestion"),
    ]

    operations = [
        migrations.AddField(
            model_name="manualgroupingsuggestion",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("dismissed", "Dismissed"),
                    ("grouped", "Grouped"),
                ],
                default="pending",
                max_length=10,
            ),
        ),
    ]
