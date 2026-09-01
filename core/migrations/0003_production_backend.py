from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_candidate_user_subscription_feedback_agentclient_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="candidate",
            name="profile_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="CandidateDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("file", models.FileField(upload_to="candidate-documents/%Y/%m/")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("candidate", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="core.candidate")),
            ],
        ),
        migrations.CreateModel(
            name="AppSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=100, unique=True)),
                ("value", models.TextField(blank=True)),
            ],
        ),
    ]
