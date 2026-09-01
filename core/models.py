from django.conf import settings
from django.db import models
import uuid
from django.utils import timezone
from django.contrib.auth.models import User


class Candidate(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_profile",
    )

    full_name = models.CharField(
        max_length=200,
        blank=True,
    )

    email = models.EmailField()

    phone = models.CharField(
        max_length=50,
        blank=True,
    )

    profile_data = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"{self.full_name or 'Candidate'} <{self.email}>"

class EmploymentHistory(models.Model):

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="employment_history"
    )

    date_from = models.DateField(
        null=True,
        blank=True
    )

    date_to = models.DateField(
        null=True,
        blank=True
    )

    employer_name = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )

    location = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )

    immediate_superior = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )

    position = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )

    start_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    end_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    reason_for_leaving = models.TextField(
        blank=True,
        default=""
    )

    job_description = models.TextField(
        blank=True,
        default=""
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.employer_name} - {self.position}"

class CandidateDocument(models.Model):
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    name = models.CharField(
        max_length=255,
    )

    file = models.FileField(
        upload_to="candidate_documents/%Y/%m/",
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"{self.candidate.email} - {self.name}"


# ============================================================
# COMPANY
# ============================================================

class Company(models.Model):
    name = models.CharField(
        max_length=150,
        unique=True,
    )

    email = models.EmailField()

    phone = models.CharField(
        max_length=50,
    )

    address = models.TextField(
        blank=True,
        default="",
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.name

    #------userprofile -----#

class UserProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    middle_name = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        default=""
    )

    # Extra profile fields used by the existing My Profile UI.
    # Keeping them as JSON preserves the current design/field names while
    # allowing every authenticated user to save the values on the server.
    profile_data = models.JSONField(
        default=dict,
        blank=True,
    )

    application_type = models.CharField(
        max_length=30,
        choices=[
            ("macro_kiosk", "Macro Kiosk"),
            ("insitemy", "InsiteMy"),
        ],
        default="macro_kiosk",
    )

    profile_photo = models.ImageField(
        upload_to="profile_photos/%Y/%m/",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.user.username

# ============================================================
# JOB APPLICATION
# ============================================================

class JobApplication(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("invited", "Invitation Sent"),
        ("submitted", "Submitted"),
        ("reviewed", "Reviewed"),
        ("shortlisted", "Shortlisted"),
        ("rejected", "Rejected"),
    ]

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="applications",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="applications",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    data = models.JSONField(default=dict, blank=True)

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.company.name} - {self.candidate.email}"
    
class CandidateCompanyPermission(models.Model):
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="company_permissions",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="candidate_permissions",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "company"],
                name="unique_candidate_company_permission",
            )
        ]

    def __str__(self):
        return f"{self.candidate.email} - {self.company.name}"

class ApplicationFile(models.Model):
    application = models.ForeignKey(
        JobApplication, on_delete=models.CASCADE, related_name="files"
    )
    file = models.FileField(upload_to="applications/%Y/%m/")
    field_name = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class Invitation(models.Model):
    application = models.OneToOneField(
        JobApplication, on_delete=models.CASCADE, related_name="invitation"
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)


class Subscription(models.Model):
    ACCOUNT_CHOICES = [
        ("Free", "Free"),
        ("Paid", "Paid"),
        ("Premium", "Premium"),
    ]
    candidate = models.OneToOneField(
        Candidate, on_delete=models.CASCADE, related_name="subscription"
    )
    account_type = models.CharField(max_length=30, choices=ACCOUNT_CHOICES, default="Free")
    valid_till = models.DateField(null=True, blank=True)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def remaining_days(self):
        if not self.valid_till:
            return None
        return max((self.valid_till - timezone.localdate()).days, 0)

    @property
    def is_active(self):
        return self.valid_till is None or self.valid_till >= timezone.localdate()


class AgentClient(models.Model):
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_clients"
    )
    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="agent_links"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "candidate"], name="unique_agent_candidate"
            )
        ]


class Feedback(models.Model):
    candidate = models.ForeignKey(
        Candidate, on_delete=models.SET_NULL, null=True, blank=True, related_name="feedback"
    )
    application = models.ForeignKey(
        JobApplication, on_delete=models.SET_NULL, null=True, blank=True, related_name="feedback"
    )
    rating = models.PositiveSmallIntegerField(default=0)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    application = models.ForeignKey(
        JobApplication, null=True, blank=True, on_delete=models.CASCADE
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class EmailLog(models.Model):
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    success = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AppSetting(models.Model):
    key = models.CharField(
        max_length=100,
        unique=True,
    )

    value = models.TextField(
        blank=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.key
    
class SystemSettings(models.Model):
    terms_and_conditions = models.TextField(blank=True)
    privacy_policy = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "System Settings"

   