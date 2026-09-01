from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import Company, Invitation, JobApplication, UserProfile


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="system@example.com",
)
class CompanyWorkflowTests(TestCase):
    def setUp(self):
        self.macro = Company.objects.create(
            name="Macro Kiosk",
            email="macro@example.com",
            phone="N/A",
        )
        self.insite = Company.objects.create(
            name="InsiteMy",
            email="insite@example.com",
            phone="N/A",
        )
        self.hr_group = Group.objects.create(name="hr")

    def create_hr(self, email, application_type):
        user = User.objects.create_user(
            username=email,
            email=email,
            password="StrongPass123!",
            first_name="HR",
        )
        user.groups.add(self.hr_group)
        UserProfile.objects.create(
            user=user,
            application_type=application_type,
        )
        return user

    def test_hr_login_is_company_aware(self):
        self.create_hr("macro.hr@example.com", "macro_kiosk")
        self.client.post(
            "/login/",
            {"email": "macro.hr@example.com", "password": "StrongPass123!"},
        )
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/applications/macro-kiosk/", response["Location"])

    def test_existing_email_cannot_register_again(self):
        self.create_hr("existing@example.com", "insitemy")
        response = self.client.post(
            "/signup/",
            {
                "userRole": "employer",
                "application_type": "macro_kiosk",
                "address": "Another Person",
                "email": "existing@example.com",
                "pass": "StrongPass123!",
                "cpass": "StrongPass123!",
                "accept": "true",
            },
        )
        self.assertEqual(User.objects.filter(email__iexact="existing@example.com").count(), 1)
        self.assertContains(response, "existing user", status_code=200)

    def test_hr_sends_company_specific_bulk_invites(self):
        self.create_hr("macro.hr@example.com", "macro_kiosk")
        self.client.login(username="macro.hr@example.com", password="StrongPass123!")
        response = self.client.post(
            "/send-invitation/",
            {
                "emails": "one@example.com\ntwo@example.com",
                "name": "Candidate",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(JobApplication.objects.filter(company=self.macro).count(), 2)
        self.assertEqual(Invitation.objects.filter(invited_by__email="macro.hr@example.com").count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_profile_photo_upload(self):
        user = self.create_hr("photo@example.com", "insitemy")
        self.client.login(username="photo@example.com", password="StrongPass123!")
        png = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\x0dIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01"
            b"\xff\x89\x99=\x1c\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        response = self.client.post(
            "/myprofile/",
            {"fname": "HR", "email": "photo@example.com", "profile_photo": SimpleUploadedFile("photo.png", png, content_type="image/png")},
        )
        self.assertEqual(response.status_code, 302)
        profile = UserProfile.objects.get(user=user)
        self.assertTrue(profile.profile_photo)
