from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from core.models import Candidate, Subscription

class Command(BaseCommand):
    help = "Create local-only demo users for the four roles."

    USERS = [
        ("candidate@stalwart.local", "Candidate@123", "Candidate Demo", "candidate"),
        ("agent@stalwart.local", "Agent@123", "Agent Demo", "agent"),
        ("hr@stalwart.local", "Hr@123", "HR Demo", "hr"),
        ("admin@stalwart.local", "Admin@123", "Administration Demo", "administration"),
    ]

    def handle(self, *args, **options):
        User = get_user_model()
        for email, password, name, role in self.USERS:
            user, _ = User.objects.get_or_create(username=email, defaults={"email": email, "first_name": name})
            user.email = email
            user.first_name = name
            user.is_active = True
            user.set_password(password)
            if role == "administration":
                user.is_staff = True
                user.is_superuser = False
            user.save()
            group, _ = Group.objects.get_or_create(name=role)
            user.groups.set([group])
            if role == "candidate":
                candidate, _ = Candidate.objects.get_or_create(email=email)
                candidate.user = user
                candidate.full_name = name
                candidate.save()
                Subscription.objects.get_or_create(candidate=candidate)
            self.stdout.write(self.style.SUCCESS(f"{role}: {email}"))
