from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

ROLE_NAMES = ["candidate", "agent", "hr", "administration"]

class Command(BaseCommand):
    help = "Create the four application role groups."

    def handle(self, *args, **options):
        for role in ROLE_NAMES:
            group, created = Group.objects.get_or_create(name=role)
            state = "created" if created else "already exists"
            self.stdout.write(self.style.SUCCESS(f"{role}: {state}"))
