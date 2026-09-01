from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_employmenthistory"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="profile_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="jobapplication",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("invited", "Invitation Sent"),
                    ("submitted", "Submitted"),
                    ("reviewed", "Reviewed"),
                    ("shortlisted", "Shortlisted"),
                    ("rejected", "Rejected"),
                ],
                default="draft",
                max_length=20,
            ),
        ),
    ]
