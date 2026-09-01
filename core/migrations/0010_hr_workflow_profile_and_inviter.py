from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_companies(apps, schema_editor):
    Company = apps.get_model("core", "Company")

    Company.objects.get_or_create(
        name="InsiteMy",
        defaults={
            "email": "hr@insitemy.example",
            "phone": "N/A",
            "address": "",
            "description": "InsiteMy application workflow",
            "is_active": True,
        },
    )

    Company.objects.get_or_create(
        name="Macro Kiosk",
        defaults={
            "email": "hr@macrokiosk.example",
            "phone": "N/A",
            "address": "",
            "description": "Macro Kiosk application workflow",
            "is_active": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "core",
            "0009_backend_profile_and_application_status",
        ),
        migrations.swappable_dependency(
            settings.AUTH_USER_MODEL
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="profile_photo",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="profile_photos/%Y/%m/",
            ),
        ),

        migrations.AddField(
            model_name="invitation",
            name="invited_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sent_invitations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),

        migrations.RunPython(
            seed_companies,
            migrations.RunPython.noop,
        ),
    ]