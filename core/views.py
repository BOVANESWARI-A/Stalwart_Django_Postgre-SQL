from functools import wraps
from pathlib import Path
import re



from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404, JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme


from .models import (
    AgentClient,
    AppSetting,
    CandidateDocument,
    Company,
    ApplicationFile,
    Candidate,
    EmailLog,
    Feedback,
    Invitation,
    JobApplication,
    Notification,
    Subscription,
    UserProfile,
    EmploymentHistory,
)

User = get_user_model()

ROLE_GROUPS = {
    "candidate": {"candidate", "Candidate"},
    "agent": {"agent", "Agent"},
    "hr": {"hr", "HR"},
    "administration": {"administration", "Administration", "admin", "Admin"},
}

APPLICATION_SECTIONS = {
    "personal_information",
    "iq_test",
    "consent",
    "documents",
    "employment_expectations",
    "reference",
    "declaration",
    "employment_history",
    "education",
    "general_information",
    "background_check",
    "general_assignment",
    "pdpa_consent",
}

IGNORED_POST_FIELDS = {"csrfmiddlewaretoken", "section", "save_section", "next", "final_submit"}

ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".webp"
}
MAX_UPLOAD_SIZE = 1 * 1024 * 1024


def get_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return "administration"
    groups = set(user.groups.values_list("name", flat=True))
    for role, names in ROLE_GROUPS.items():
        if groups.intersection(names):
            return role
    if user.is_staff:
        return "hr"
    return "candidate"

def get_insitemy_company():
    return get_object_or_404(
        Company,
        name__iexact="InsiteMy",
        is_active=True,
    )


def get_macro_kiosk_company():
    return get_object_or_404(
        Company,
        name__iexact="Macro Kiosk",
        is_active=True,
    )


def user_application_type(user):
    if not user or not user.is_authenticated:
        return None
    if get_role(user) == "hr":
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return profile.application_type or "macro_kiosk"
    return None


def active_candidate_application(user):
    candidate = candidate_for_user(user)
    if not candidate:
        return None
    return (
        JobApplication.objects
        .filter(
            candidate=candidate,
            invitation__active=True,
            status__in={"draft", "invited"},
        )
        .select_related("invitation", "company")
        .order_by("-updated_at", "-id")
        .first()
    )


def role_landing_url(user):
    role = get_role(user)
    if role == "hr":
        return "/applications/insitemy/" if user_application_type(user) == "insitemy" else "/applications/macro-kiosk/"
    if role == "candidate":
        app = active_candidate_application(user)
        if app and hasattr(app, "invitation"):
            return reverse("candidate_application", kwargs={"token": app.invitation.token})
    return reverse("dashboard")


def is_insitemy_application(app):
    return (
        app.company
        and app.company.name.strip().lower() == "insitemy"
    )


def is_macro_kiosk_application(app):
    return (
        app.company
        and app.company.name.strip().lower() == "macro kiosk"
    )


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        @login_required(login_url="/login/")
        def wrapped(request, *args, **kwargs):
            if get_role(request.user) not in allowed_roles:
                messages.error(request, "You are not authorized to access this page.")
                return redirect("dashboard")
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def safe_next_url(request, value):
    value = (value or "").strip()
    if not value:
        return ""
    allowed_hosts = {request.get_host()}
    return value if url_has_allowed_host_and_scheme(value, allowed_hosts=allowed_hosts, require_https=request.is_secure()) else ""


def candidate_for_user(user):
    if not user or not user.is_authenticated:
        return None
    candidate = getattr(user, "candidate_profile", None)
    if candidate:
        return candidate
    if user.email:
        return Candidate.objects.filter(email__iexact=user.email).first()
    return None


def candidate_queryset_for_user(user):
    role = get_role(user)
    if role in {"administration", "hr"}:
        return Candidate.objects.all()
    if role == "agent":
        ids = AgentClient.objects.filter(agent=user).values_list("candidate_id", flat=True)
        return Candidate.objects.filter(pk__in=ids)
    candidate = candidate_for_user(user)
    return Candidate.objects.filter(pk=candidate.pk) if candidate else Candidate.objects.none()


def dashboard_metrics(user):
    role = get_role(user)
    if role == "candidate":
        candidate = candidate_for_user(user)
        if not candidate:
            return {"role": "candidate", "account_type": "Free", "valid_till": None, "remaining_days": 0, "application_submitted": 0}
        subscription = Subscription.objects.filter(candidate=candidate).first()
        return {
            "role": "candidate",
            "account_type": subscription.account_type if subscription else "Free",
            "valid_till": subscription.valid_till.isoformat() if subscription and subscription.valid_till else None,
            "remaining_days": subscription.remaining_days if subscription else 0,
            "application_submitted": JobApplication.objects.filter(candidate=candidate, status="submitted").count(),
        }
    if role == "agent":
        ids = AgentClient.objects.filter(agent=user).values_list("candidate_id", flat=True)
        return {
            "role": "agent",
            "client_count": Candidate.objects.filter(pk__in=ids).count(),
            "submitted_count": JobApplication.objects.filter(candidate_id__in=ids, status="submitted").count(),
        }
    if role == "hr":
        return {
            "role": "hr",
            "received_count": JobApplication.objects.filter(status="submitted").count(),
            "invite_count": Invitation.objects.filter(sent_at__isnull=False).count(),
        }
    return {
        "role": "administration",
        "total_candidates": Candidate.objects.count(),
        "paid_subscriptions": Subscription.objects.filter(paid=True).count(),
        "received_count": JobApplication.objects.filter(status="submitted").count(),
        "feedback_count": Feedback.objects.count(),
    }


@ensure_csrf_cookie
def login_view(request):
    if request.user.is_authenticated:
        next_url = safe_next_url(request, request.GET.get("next") or request.POST.get("next"))
        return redirect(next_url or role_landing_url(request.user))
    next_url = safe_next_url(request, request.GET.get("next"))
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        next_url = safe_next_url(request, request.POST.get("next"))
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        authenticated = None
        if user:
            authenticated = authenticate(request, username=user.get_username(), password=password)
            if authenticated is None and user.check_password(password):
                authenticated = user
        if authenticated:
            auth_login(request, authenticated)
            request.session.set_expiry(1209600 if request.POST.get("remember") == "true" else 0)
            return redirect(next_url or role_landing_url(authenticated))
        messages.error(request, "Invalid email or password.")
    return render(request, "core/login.html", {"next": next_url})

def reset_password(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        if not email:
            messages.error(request, "Please enter your email address.")
            return render(request, "core/reset-password.html")

        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()

        # Always show the same message so we don't reveal
        # whether an email address exists in the system.
        if user:
            token = default_token_generator.make_token(user)

            request.session["password_reset_user_id"] = user.pk
            request.session["password_reset_token"] = token
            request.session["password_reset_email"] = user.email

            reset_url = request.build_absolute_uri(
                reverse(
                    "password_reset_confirm",
                    kwargs={"uid": user.pk, "token": token},
                )
            )

            email_html = render_to_string(
                "core/email-reset-password.html",
                {
                    "reset_url": reset_url,
                    "email": user.email,
                },
                request=request,
            )

            send_mail(
                subject="Reset your Stalwart Business Solutions password",
                message=(
                    "A password reset was requested for your Stalwart Business "
                    "Solutions account.\n\n"
                    f"Reset your password here: {reset_url}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=email_html,
                fail_silently=False,
            )

        messages.success(
            request,
            "If an account exists with that email address, "
            "password reset instructions have been sent.",
        )
        return render(request, "core/reset-password.html")

    return render(request, "core/reset-password.html")


def password_reset_confirm(request, uid, token):
    if request.user.is_authenticated:
        return redirect("dashboard")

    try:
        user = User.objects.get(
            pk=uid,
            is_active=True,
        )
    except User.DoesNotExist:
        messages.error(request, "This password reset link is invalid or expired.")
        return redirect("reset_password")

    if not default_token_generator.check_token(user, token):
        messages.error(request, "This password reset link is invalid or expired.")
        return redirect("reset_password")

    if request.method == "POST":
        otp = request.POST.get("otp", "").strip()
        password = request.POST.get("pass", "")
        confirm = request.POST.get("cpass", "")

        # OTP is optional for the first implementation because
        # the secure Django token is already validating the link.
        # If the form sends an OTP, validate it against the session.
        stored_otp = request.session.get("password_reset_otp")

        if stored_otp and otp != stored_otp:
            messages.error(request, "The OTP entered is incorrect.")
            return render(
                request,
                "core/password-set-page.html",
                {"email": user.email},
            )

        if len(password) < 8:
            messages.error(
                request,
                "Password must be at least 8 characters long.",
            )
        elif password != confirm:
            messages.error(
                request,
                "Passwords do not match.",
            )
        else:
            user.set_password(password)
            user.save(update_fields=["password"])

            request.session.pop("password_reset_user_id", None)
            request.session.pop("password_reset_token", None)
            request.session.pop("password_reset_email", None)
            request.session.pop("password_reset_otp", None)

            messages.success(
                request,
                "Your password has been updated successfully. "
                "You can now log in.",
            )
            return redirect("login")

    return render(
        request,
        "core/password-set-page.html",
        {"email": user.email},
    )


@login_required(login_url="/login/")
def logout_view(request):
    # The existing UI uses a normal link, while newer forms may use POST.
    # Support both so logout always works from every page.
    auth_logout(request)
    if request.method == "POST":
        messages.success(request, "You have been logged out successfully.")
    return redirect("login")


def signup(request):
    if request.user.is_authenticated:
        return redirect(role_landing_url(request.user))

    next_url = safe_next_url(request, request.GET.get("next"))
    invitation = None
    invitation_token = request.GET.get("invitation", "").strip()

    # Recover an invitation from a candidate application URL.
    if next_url and "/candidate/application/" in next_url:
        token = next_url.rstrip("/").split("/")[-1]
        try:
            invitation = Invitation.objects.select_related(
                "application__candidate",
                "application__company",
            ).get(token=token, active=True)
            invitation_token = str(invitation.token)
        except (Invitation.DoesNotExist, ValueError):
            invitation = None

    if invitation is None and invitation_token:
        invitation = (
            Invitation.objects.select_related(
                "application__candidate",
                "application__company",
            )
            .filter(token=invitation_token, active=True)
            .first()
        )

    if request.method == "POST":
        full_name = request.POST.get("address", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("pass", "")
        confirm = request.POST.get("cpass", "")
        next_url = safe_next_url(request, request.POST.get("next"))
        selected_role = request.POST.get("userRole", "jobSeeker").strip()

        if invitation:
            # An invited candidate can only create a candidate account with
            # the email address to which the invitation was sent.
            invited_email = invitation.application.candidate.email.strip().lower()
            if email != invited_email:
                messages.error(request, "Please use the email address that received this invitation.")
            elif User.objects.filter(email__iexact=email).exists():
                messages.error(request, "You are an existing user. Please login instead.")
            elif not full_name or not email or not password:
                messages.error(request, "Please fill in all required fields.")
            elif len(password) < 8:
                messages.error(request, "Password must be at least 8 characters long.")
            elif password != confirm:
                messages.error(request, "Password and Confirm Password don't match.")
            elif request.POST.get("accept") != "true":
                messages.error(request, "Please accept the terms and conditions.")
            else:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                        first_name=full_name,
                    )
                    candidate = invitation.application.candidate
                    candidate.user = user
                    candidate.full_name = full_name
                    candidate.email = email
                    candidate.save()
                    Subscription.objects.get_or_create(candidate=candidate)
                    group, _ = Group.objects.get_or_create(name="candidate")
                    user.groups.add(group)
                auth_login(request, user)
                return redirect("candidate_application", token=invitation.token)

        else:
            role_map = {
                "jobSeeker": "candidate",
                "employer": "hr",
                "agency": "agent",
            }
            role = role_map.get(selected_role)
            application_type = request.POST.get("application_type", "").strip().lower()

            if not role:
                messages.error(request, "Please choose a valid account role.")
            elif role == "hr" and application_type not in {"macro_kiosk", "insitemy"}:
                messages.error(request, "Please choose Macro Kiosk or InsiteMy for the HR account.")
            elif not full_name or not email or not password:
                messages.error(request, "Please fill in all required fields.")
            elif len(password) < 8:
                messages.error(request, "Password must be at least 8 characters long.")
            elif password != confirm:
                messages.error(request, "Password and Confirm Password don't match.")
            elif User.objects.filter(email__iexact=email).exists():
                messages.error(request, "You are an existing user. Please login instead.")
            elif User.objects.filter(username__iexact=email).exists():
                messages.error(request, "An account already exists for this email. Please login instead.")
            elif request.POST.get("accept") != "true":
                messages.error(request, "Please accept the terms and conditions.")
            else:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                        first_name=full_name,
                    )
                    group, _ = Group.objects.get_or_create(name=role)
                    user.groups.add(group)

                    profile, _ = UserProfile.objects.get_or_create(user=user)
                    if role == "hr":
                        profile.application_type = application_type
                        profile.save(update_fields=["application_type", "updated_at"])

                    if role == "candidate":
                        candidate = Candidate.objects.create(
                            user=user,
                            full_name=full_name,
                            email=email,
                        )
                        Subscription.objects.get_or_create(candidate=candidate)

                auth_login(request, user)
                return redirect(next_url or role_landing_url(user))

    return render(
        request,
        "core/signup.html",
        {
            "next": next_url,
            "invitation": invitation,
            "invitation_token": invitation_token,
        },
    )

@login_required(login_url="/login/")
def dashboard(request):
    role = get_role(request.user)
    metrics = dashboard_metrics(request.user)
    app_type = user_application_type(request.user) if role == "hr" else ""
    context = {
        "role": role,
        **metrics,
        "hr_application_type": app_type,
        "hr_company_name": (
            "InsiteMy" if app_type == "insitemy"
            else "Macro Kiosk" if app_type == "macro_kiosk"
            else ""
        ),
        "notifications": Notification.objects.filter(is_read=False).order_by("-created_at")[:8],
    }
    return render(request, "core/index.html", context)


@login_required(login_url="/login/")
def dashboard_data(request):
    return JsonResponse(dashboard_metrics(request.user), safe=True)


@role_required("hr", "administration")
def company_page(request, company_name):
    company_name = company_name.strip().lower()
    if company_name not in {"insitemy", "macro kiosk"}:
        raise Http404("Application workflow not found.")

    if get_role(request.user) == "hr":
        expected = user_application_type(request.user)
        if (company_name == "insitemy" and expected != "insitemy") or (
            company_name == "macro kiosk" and expected != "macro_kiosk"
        ):
            return redirect("insitemy" if expected == "insitemy" else "macro_kiosk")

    display_name = "InsiteMy" if company_name == "insitemy" else "Macro Kiosk"
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(
        request,
        "core/hr-invite.html",
        {
            "hr_entry": True,
            "company": display_name,
            "application_type": company_name.replace(" ", "_"),
            "hr_profile": profile,
        },
    )


@role_required("hr", "administration")
def insitemy(request):
    return company_page(request, "InsiteMy")


@role_required("hr", "administration")
def macro_kiosk(request):
    return company_page(request, "Macro Kiosk")




def _send_invitation_email(request, invitation):
    app = invitation.application
    candidate = app.candidate

    link = request.build_absolute_uri(
        reverse(
            "candidate_invitation",
            kwargs={"token": invitation.token},
        )
    )

    sender_name = (
        request.user.get_full_name()
        or request.user.email
        or "HR Team"
    )

    subject = f"{app.company.name} - Job Application Invitation"

    body = (
        f"Dear {candidate.full_name or 'Candidate'},\n\n"
        f"{sender_name} from {app.company.name} has invited you "
        "to complete your job application.\n\n"
        "Secure application link:\n"
        f"{link}\n\n"
        "Please do not share this link with anyone.\n\n"
        "Stalwart Business Solutions"
    )

    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [candidate.email],
            fail_silently=False,
        )

        EmailLog.objects.create(
            recipient=candidate.email,
            subject=subject,
            success=True,
        )

        invitation.sent_at = timezone.now()
        invitation.save(update_fields=["sent_at"])

        app.status = "invited"
        app.save(update_fields=["status", "updated_at"])

        return True

    except Exception as exc:
        EmailLog.objects.create(
            recipient=candidate.email,
            subject=subject,
            success=False,
            error=str(exc),
        )

        return False




@role_required("hr", "administration")
def send_invitation(request):
    if request.method != "POST":
        return redirect(role_landing_url(request.user))

    role = get_role(request.user)

    # HR derives the company entirely from its account. Administration can
    # choose a company explicitly when using the dashboard.
    if role == "hr":
        application_type = user_application_type(request.user)
        company = (
            get_insitemy_company()
            if application_type == "insitemy"
            else get_macro_kiosk_company()
        )
    else:
        raw_company = request.POST.get("company", "").strip().lower()
        company = (
            get_insitemy_company()
            if raw_company == "insitemy"
            else get_macro_kiosk_company()
            if raw_company == "macro kiosk"
            else None
        )
        if company is None:
            messages.error(request, "Please select a valid company.")
            return redirect("dashboard")

    raw_emails = request.POST.get("emails", "") or request.POST.get("email", "")
    emails = list(dict.fromkeys(
        email.strip().lower()
        for email in re.split(r"[,;\s]+", raw_emails)
        if email.strip()
    ))
    name = request.POST.get("name", "").strip()
    phone = request.POST.get("phone", "").strip()

    if not emails:
        messages.error(request, "Please enter at least one candidate email address.")
        return redirect(role_landing_url(request.user))

    from django.core.validators import validate_email
    invalid = []
    for email in emails:
        try:
            validate_email(email)
        except ValidationError:
            invalid.append(email)
    if invalid:
        messages.error(request, f"Invalid email address: {invalid[0]}")
        return redirect(role_landing_url(request.user))

    sent = failed = 0

    for email in emails:
        try:
            with transaction.atomic():
                candidate = Candidate.objects.filter(email__iexact=email).order_by("id").first()
                if not candidate:
                    candidate = Candidate.objects.create(
                        email=email,
                        full_name=name,
                        phone=phone,
                    )
                else:
                    changed = False
                    if name and not candidate.full_name:
                        candidate.full_name = name
                        changed = True
                    if phone and not candidate.phone:
                        candidate.phone = phone
                        changed = True
                    if changed:
                        candidate.save()

                Subscription.objects.get_or_create(candidate=candidate)

                # If an application already exists for this company and the
                # candidate has a user account, create a fresh invitation but
                # never create a second user account.
                Invitation.objects.filter(
                    application__candidate=candidate,
                    application__company=company,
                    active=True,
                ).update(active=False)

                application = JobApplication.objects.create(
                    candidate=candidate,
                    company=company,
                    status="draft",
                    data={},
                )
                invitation = Invitation.objects.create(
                    application=application,
                    invited_by=request.user,
                )

            if _send_invitation_email(request, invitation):
                sent += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            EmailLog.objects.create(
                recipient=email,
                subject=f"{company.name} - Job Application Invitation",
                success=False,
                error=str(exc),
            )

    if sent:
        messages.success(request, f"{sent} invitation(s) sent successfully.")
    if failed:
        messages.error(request, f"{failed} invitation(s) could not be sent. Check EmailLog and SMTP settings.")

    return redirect(role_landing_url(request.user))



def candidate_invitation(request, token):
    invitation = get_object_or_404(Invitation.objects.select_related("application__candidate"), token=token, active=True)
    app = invitation.application
    if request.user.is_authenticated:
        role = get_role(request.user)
        if role != "candidate":
            messages.error(request, "This invitation is for a candidate account.")
            return redirect("dashboard")
        candidate = candidate_for_user(request.user)
        if not candidate or candidate.pk != app.candidate_id:
            messages.error(request, "Please use the candidate account associated with this invitation.")
            return redirect("dashboard")
        return redirect("candidate_application", token=invitation.token)
    next_url = reverse("candidate_application", kwargs={"token": invitation.token})
    return render(request, "core/candidate_invitation.html", {"invitation": invitation, "application": app, "company": app.company, "next": next_url})


def _section_from_request(request):
    section = (request.POST.get("save_section") or request.POST.get("section") or "").strip().lower()
    aliases = {
        "personal": "personal_information", "personal_info": "personal_information", "address": "personal_information",
        "iq": "iq_test", "documents_submission": "documents", "employment": "employment_expectations",
        "expectations": "employment_expectations", "references": "reference", "declaration_form": "declaration",
    }
    return aliases.get(section, section)


def _collect_post_data(request):
    data = {}
    for key, values in request.POST.lists():
        if key in IGNORED_POST_FIELDS:
            continue
        key = key.strip()
        if not key:
            continue
        data[key] = values[0] if len(values) == 1 else values
    return data


def _section_field_names(section, request):
    keys = set(request.POST.keys()) - IGNORED_POST_FIELDS
    if section == "personal_information":
        exact = {
            "position_applied", "others", "name", "passportnumber", "nationality", "dob", "age",
            "gender", "marital_status", "marital", "height", "weight", "bms", "email", "phone",
            "medical_condition", "medical_condition_details", "criminal_offence", "criminal_offence_details",
            "same_as_residential",
        }
        prefixes = ("residential_", "permanent_")
    elif section == "iq_test":
        exact, prefixes = set(), ("iq_",)
    elif section == "consent":
        exact, prefixes = {"consentname", "appname", "nric", "date"}, ("consent_attachment_",)
    elif section == "documents":
        exact, prefixes = set(), (
            "personality_test_result", "updated_resume", "identity_document",
            "academic_certificate", "payslips",
        )
    elif section == "employment_expectations":
        exact = {
            "willing_to_travel", "willing_to_relocate", "own_transport",
            "lastsalary", "lastsalary_2", "expectedsalary", "notice_period", "stalwart_referral",
        }
        prefixes = ()
    elif section == "reference":
        exact = {
            "ref1name", "ref1pos", "ref1com", "ref1email", "ref1phn",
            "ref2name", "ref2pos", "ref2com", "ref2email", "ref2phn",
        }
        prefixes = ()
    elif section == "declaration":
        exact = {"declaration_appname", "appplace", "dateapplied"}
        prefixes = ("applicant_signature",)
    elif section.startswith("macro_section_"):
        macro_fields = {
            "macro_section_1": {
                "macro_1_checkbox_1","macro_1_checkbox_2","macro_1_checkbox_3","macro_1_checkbox_4",
                "macro_1_checkbox_5","macro_1_checkbox_6","macro_1_checkbox_7","macro_1_checkbox_8",
                "macro_1_checkbox_9","macro_1_checkbox_10","macro_1_checkbox_11","macro_1_checkbox_12",
                "others","others_2","macro_doc_1_1","name","address","address_2","dob","age","gender",
                "dob_2","email","passportnumber","marital","nationality","nationality_2","nationality_3",
                "nationality_4","father","mother","spouse","children","brothers","sisters"
            },
            "macro_section_2": {
                "datefrom","dateto","height","location","superior","position","ssalary","esalary",
                "reasons","macro_2_text_1"
            },
            "macro_section_3": {
                "height","location","yearfrom","yearto","qualification","height_2","location_2",
                "yearfrom_2","yearto_2","qualification_2","height_3","height_4","height_5",
                "lang","lang_2","lang_3","lang_4","lang_5","lang_6","lang_7","lang_8","lang_9",
                "lang_10","lang_11","lang_12","lang_13","lang_14","lang_15","lang_16","lang_17","lang_18",
                "others","others_2"
            },
            "macro_section_4": {
                "macro_4_checkbox_1","macro_4_checkbox_2","macro_4_checkbox_3","macro_4_checkbox_4",
                "macro_4_checkbox_5","macro_4_checkbox_6","macro_4_checkbox_7","macro_4_checkbox_8",
                "macro_4_checkbox_9","macro_4_checkbox_10","macro_4_checkbox_11","macro_4_checkbox_12",
                "macro_4_checkbox_13","macro_4_checkbox_14","macro_4_checkbox_15","macro_4_checkbox_16",
                "macro_4_checkbox_17","macro_4_checkbox_18","macro_4_checkbox_19","macro_4_checkbox_20",
                "elaborate","elaborate_2","elaborate_3","elaborate_4","elaborate_5","elaborate_6",
                "elaborate_7","elaborate_8","elaborate_9","elaborate_10","lastsalary","lastsalary_2",
                "expectedsalary","ref1name","ref1pos","ref1com","ref1email","ref1phn",
                "ref1name_2","ref1pos_2","ref1com_2","ref1email_2","ref1phn_2","appname","dateapplied"
            },
            "macro_section_5": {"macro_5_yourname","macro_5_nric","macro_doc_5_1","name","date","nric"},
            "macro_section_6": {"macro_6_text_1"},
            "macro_section_7": {"name","nric","date"},
        }
        exact, prefixes = macro_fields.get(section, set()), ()
    else:
        exact, prefixes = keys, ()
    return {
        key for key in keys
        if key in exact or any(key.startswith(prefix) for prefix in prefixes)
    }



def _save_uploaded_file(app, field_name, uploaded_file):
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise ValidationError(f"{uploaded_file.name} is larger than 1 MB.")
    ext = Path(uploaded_file.name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError(f"File type {ext or 'unknown'} is not allowed.")
    return ApplicationFile.objects.create(application=app, file=uploaded_file, field_name=field_name)


def _merge_section(saved_data, section, data):
    if section:
        old = saved_data.get(section)
        if not isinstance(old, dict):
            old = {}
        old.update(data)
        saved_data[section] = old
    else:
        saved_data.update(data)
    return saved_data


def _candidate_defaults(app):
    candidate = app.candidate
    saved = app.data if isinstance(app.data, dict) else {}
    personal = saved.get("personal_information", {})
    if not isinstance(personal, dict):
        personal = {}
    personal.setdefault("name", candidate.full_name or "")
    personal.setdefault("email", candidate.email or "")
    personal.setdefault("phone", candidate.phone or "")
    saved["personal_information"] = personal

    macro = saved.get("macro_section_1", {})
    if not isinstance(macro, dict):
        macro = {}
    macro.setdefault("name", candidate.full_name or "")
    macro.setdefault("email", candidate.email or "")
    saved["macro_section_1"] = macro
    return saved


def _validate_final_application(app, data):
    errors = []
    personal = data.get("personal_information", {}) if isinstance(data.get("personal_information"), dict) else {}
    consent = data.get("consent", {}) if isinstance(data.get("consent"), dict) else {}
    declaration = data.get("declaration", {}) if isinstance(data.get("declaration"), dict) else {}
    reference = data.get("reference", {}) if isinstance(data.get("reference"), dict) else {}
    expectations = data.get("employment_expectations", {}) if isinstance(data.get("employment_expectations"), dict) else {}
    if not (personal.get("name") or personal.get("full_name")):
        errors.append("Personal Information: Name is required.")
    if not personal.get("email"):
        errors.append("Personal Information: Email is required.")
    if is_insitemy_application(app):
        if not consent.get("consentname") and not consent.get("appname"):
            errors.append("Consent Form: applicant name is required.")
        if not declaration.get("declaration_appname") or not declaration.get("dateapplied"):
            errors.append("Applicant Declaration: applicant name and date are required.")
        if not reference.get("ref1name"):
            errors.append("Reference Details: at least one reference is required.")
        expectation_values = [str(value).strip().lower() for value in expectations.values() if value is not None]
        if not expectation_values or all(value in {"", "please select"} for value in expectation_values):
            errors.append("Employment Expectations: please complete the section.")
        if not app.files.exists():
            errors.append("Document Submission: at least one document is required.")
    return errors

@login_required(login_url="/login/")
def candidate_application(request, token):
    invitation = get_object_or_404(
        Invitation.objects.select_related(
            "application__candidate",
            "application__company",
        ),
        token=token,
    )

    app = invitation.application

    # ============================================================
    # CANDIDATE ACCESS CHECK
    # ============================================================

    if get_role(request.user) != "candidate":
        messages.error(
            request,
            "Only a candidate account can complete this application.",
        )
        return redirect("dashboard")

    candidate = candidate_for_user(request.user)

    if not candidate or candidate.pk != app.candidate_id:
        messages.error(
            request,
            "This invitation is not assigned to your candidate account.",
        )
        return redirect("dashboard")

    # ============================================================
    # ALREADY SUBMITTED
    # ============================================================

    if app.status == "submitted":
        return render(
            request,
            "core/submitted-application.html",
            {
                "candidate_submission": True,
                "application": app,
            },
        )

    # ============================================================
    # MARK INVITATION AS OPENED
    # ============================================================

    if not invitation.opened_at:
        invitation.opened_at = timezone.now()
        invitation.save(
            update_fields=["opened_at"]
        )

    # ============================================================
    # SELECT APPLICATION TEMPLATE
    #
    # Company is a ForeignKey.
    # DO NOT use:
    # JobApplication.INSITEMY
    # JobApplication.MACRO
    # ============================================================

    if is_insitemy_application(app):
        template = "core/insitemy.html"

    elif is_macro_kiosk_application(app):
        template = "core/macro-kiosk.html"

    else:
        raise Http404(
            "Application company template not found."
        )

    saved_data = _candidate_defaults(app)

    # ============================================================
    # POST
    # ============================================================

    if request.method == "POST":

        # --------------------------------------------------------
        # CURRENT SECTION
        # --------------------------------------------------------

        section = _section_from_request(request)

        # --------------------------------------------------------
        # FINAL SUBMISSION FLAG
        # --------------------------------------------------------

        is_final = (
            request.POST.get(
                "final_submit",
                "",
            ).lower()
            in {"true", "1", "yes", "on"}
        )

        # --------------------------------------------------------
        # COLLECT POST DATA
        # --------------------------------------------------------

        all_post_data = _collect_post_data(request)

        allowed_names = (
            _section_field_names(
                section,
                request,
            )
            if section
            else set(all_post_data)
        )

        section_data = {
            key: value
            for key, value in all_post_data.items()
            if key in allowed_names
        }

        # ========================================================
        # INSITEMY FINAL SUBMISSION
        #
        # Insitemy has one visual form containing multiple
        # logical sections.
        # ========================================================

        if (
            is_final
            and is_insitemy_application(app)
        ):

            for final_section in (
                "personal_information",
                "iq_test",
                "consent",
                "documents",
                "employment_expectations",
                "reference",
                "declaration",
            ):

                names = _section_field_names(
                    final_section,
                    request,
                )

                section_values = {
                    key: value
                    for key, value in all_post_data.items()
                    if key in names
                }

                if section_values:

                    saved_data = _merge_section(
                        saved_data,
                        final_section,
                        section_values,
                    )

            # Final validation is based on declaration
            section = "declaration"

            section_data = {
                key: value
                for key, value in all_post_data.items()
                if key in _section_field_names(
                    "declaration",
                    request,
                )
            }

        if is_final and is_macro_kiosk_application(app):
            for final_section in (
                "macro_section_1","macro_section_2","macro_section_3",
                "macro_section_4","macro_section_5","macro_section_6","macro_section_7",
            ):
                names = _section_field_names(final_section, request)
                values = {k: value for k, value in all_post_data.items() if k in names}
                if values:
                    saved_data = _merge_section(saved_data, final_section, values)
            section = "macro_section_7"
            section_data = {
                k: value for k, value in all_post_data.items()
                if k in _section_field_names(section, request)
            }

        # ========================================================
        # FILE VALIDATION
        # ========================================================

        for uploaded in request.FILES.values():

            if uploaded.size > MAX_UPLOAD_SIZE:

                messages.error(
                    request,
                    (
                        f"{uploaded.name} is larger than 1 MB. "
                        "Please choose a smaller file."
                    ),
                )

                target = reverse(
                    "candidate_application",
                    kwargs={
                        "token": invitation.token,
                    },
                )

                return redirect(
                    f"{target}?section={section}"
                )

            if (
                Path(
                    uploaded.name
                ).suffix.lower()
                not in ALLOWED_UPLOAD_EXTENSIONS
            ):

                messages.error(
                    request,
                    (
                        f"{uploaded.name} is not an "
                        "allowed file type."
                    ),
                )

                target = reverse(
                    "candidate_application",
                    kwargs={
                        "token": invitation.token,
                    },
                )

                return redirect(
                    f"{target}?section={section}"
                )

        # ========================================================
        # PERSONAL INFORMATION
        # ========================================================

        if section == "personal_information":

            same = (
                request.POST.get(
                    "same_as_residential",
                    "",
                )
                in {"on", "true", "1", "yes"}
            )

            section_data[
                "same_as_residential"
            ] = same

            if same:

                for suffix in (
                    "address",
                    "city",
                    "state",
                    "country",
                    "pincode",
                ):

                    value = request.POST.get(
                        f"residential_{suffix}",
                        "",
                    )

                    if value:

                        section_data[
                            f"permanent_{suffix}"
                        ] = value

        # ========================================================
        # SAVE APPLICATION
        # ========================================================

        with transaction.atomic():

            saved_data = _merge_section(
                saved_data,
                section,
                section_data,
            )

            # ----------------------------------------------------
            # SAVE UPLOADED FILES
            # ----------------------------------------------------

            uploaded_records = []

            for (
                field_name,
                uploaded,
            ) in request.FILES.items():

                if uploaded:

                    saved_file = _save_uploaded_file(
                        app,
                        field_name,
                        uploaded,
                    )

                    uploaded_records.append(
                        {
                            "id": saved_file.id,
                            "field_name": field_name,
                            "filename": saved_file.file.name,
                        }
                    )

            # ----------------------------------------------------
            # ADD UPLOADED FILES TO SAVED DATA
            # ----------------------------------------------------

            if uploaded_records:

                existing_documents = saved_data.get(
                    "documents",
                    [],
                )

                if not isinstance(
                    existing_documents,
                    list,
                ):

                    existing_documents = []

                existing_documents.extend(
                    uploaded_records
                )

                saved_data[
                    "documents"
                ] = existing_documents

            app.data = saved_data

            # ====================================================
            # UPDATE CANDIDATE INFORMATION
            # ====================================================

            if section == "personal_information":

                name = (
                    section_data.get("name")
                    or section_data.get("full_name")
                )

                phone = section_data.get(
                    "phone"
                )

                email = section_data.get(
                    "email"
                )

                if name:

                    candidate.full_name = (
                        str(name).strip()
                    )

                if phone:

                    candidate.phone = (
                        str(phone).strip()
                    )

                if email:

                    new_email = str(email).strip().lower()

                    if User.objects.exclude(
                        pk=request.user.pk
                    ).filter(email__iexact=new_email).exists():
                        messages.error(
                            request,
                            "That email address is already in use.",
                        )
                    else:
                        candidate.email = new_email
                        request.user.email = new_email
                        request.user.username = new_email
                        request.user.save(
                            update_fields=["email", "username"]
                        )

                candidate.save()

            # ====================================================
            # FINAL SUBMISSION
            # ====================================================

            if is_final:

                errors = _validate_final_application(
                    app,
                    saved_data,
                )

                if errors:

                    messages.error(
                        request,
                        (
                            "Please complete the required "
                            "sections before submitting."
                        ),
                    )

                    for error in errors:

                        messages.error(
                            request,
                            error,
                        )

                    app.save(
                        update_fields=[
                            "data",
                            "updated_at",
                        ]
                    )

                    return redirect(
                        "candidate_application",
                        token=invitation.token,
                    )

                # ------------------------------------------------
                # MARK APPLICATION AS SUBMITTED
                # ------------------------------------------------

                app.status = "submitted"

                app.submitted_at = timezone.now()

                app.save(
                    update_fields=[
                        "data",
                        "status",
                        "submitted_at",
                        "updated_at",
                    ]
                )

                # ------------------------------------------------
                # COMPLETE INVITATION
                # ------------------------------------------------

                invitation.completed_at = timezone.now()

                invitation.active = False

                invitation.save(
                    update_fields=[
                        "completed_at",
                        "active",
                    ]
                )

                # ------------------------------------------------
                # CREATE NOTIFICATION
                # ------------------------------------------------

                Notification.objects.create(
                    title="New job application received",
                    message=(
                        f"{app.company.name} application from "
                        f"{candidate.full_name or candidate.email} "
                        "has been completed."
                    ),
                    application=app,
                )

                # ------------------------------------------------
                # SEND HR EMAIL
                # ------------------------------------------------

                hr_email = getattr(
                    settings,
                    "HR_NOTIFICATION_EMAIL",
                    "",
                )

                if hr_email:

                    try:

                        send_mail(
                            (
                                f"New {app.company.name} "
                                "application received"
                            ),
                            (
                                f"Candidate: "
                                f"{candidate.full_name or 'Candidate'}\n"
                                f"Email: {candidate.email}\n"
                                f"Application ID: {app.id}"
                            ),
                            settings.DEFAULT_FROM_EMAIL,
                            [hr_email],
                            fail_silently=True,
                        )

                    except Exception:

                        pass

                # ------------------------------------------------
                # SHOW SUBMITTED PAGE
                # ------------------------------------------------

                return render(
                    request,
                    "core/submitted-application.html",
                    {
                        "candidate_submission": True,
                        "application": app,
                    },
                )

            # ====================================================
            # NORMAL SAVE = DRAFT
            # ====================================================

            app.status = "draft"

            app.save(
                update_fields=[
                    "data",
                    "status",
                    "updated_at",
                ]
            )

        # ========================================================
        # SUCCESS
        # ========================================================

        messages.success(
            request,
            "Your information has been saved successfully.",
        )

        target = reverse(
            "candidate_application",
            kwargs={
                "token": invitation.token,
            },
        )

        return redirect(
            f"{target}?section={section}"
        )

    # ============================================================
    # GET
    # ============================================================

    return render(
        request,
        template,
        {
            "candidate_application": True,
            "application": app,
            "saved_data": saved_data,
            "uploaded_files": (
                app.files
                .all()
                .order_by("-uploaded_at")
            ),
        },
    )
@login_required(login_url="/login/")
def submitted_applications(request):

    role = get_role(request.user)

    apps = (
        JobApplication.objects
        .filter(status__in={"submitted", "reviewed", "shortlisted", "rejected"})
        .select_related(
            "candidate",
            "company",
        )
        .order_by("-submitted_at")
    )

    if role == "candidate":

        candidate = candidate_for_user(
            request.user
        )

        if candidate:

            apps = apps.filter(
                candidate=candidate
            )

        else:

            apps = apps.none()

    elif role == "agent":

        apps = apps.filter(
            candidate__agent_links__agent=request.user
        )

    elif role not in {
        "hr",
        "administration",
    }:

        return redirect("dashboard")

    return render(
        request,
        "core/submitted-application.html",
        {
            "applications": apps,
            "role": role,
        },
    )

@role_required("hr", "administration")
def received_applications(request):

    apps = (
        JobApplication.objects
        .filter(status__in={"submitted", "reviewed", "shortlisted", "rejected"})
        .select_related(
            "candidate",
            "company",
        )
        .prefetch_related("files")
        .order_by("-submitted_at")
    )

    return render(
        request,
        "core/received-application.html",
        {
            "applications": apps,
            "role": get_role(request.user),
        },
    )

    

def _application_pdf_response(app):
    """Create a simple downloadable PDF containing the saved application data."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
        title=f"Application {app.id}",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle('AppTitle', parent=styles['Title'], alignment=TA_CENTER, spaceAfter=10)
    heading = ParagraphStyle('SectionHeading', parent=styles['Heading2'], spaceBefore=8, spaceAfter=5)
    normal = styles['BodyText']
    story = [Paragraph('Stalwart Business Solutions', title),
             Paragraph(f'{app.company.name} - Job Application', styles['Heading1']),
             Paragraph(f'Application ID: {app.id} &nbsp;&nbsp; Candidate: {app.candidate.full_name or "Candidate"}', normal),
             Paragraph(f'Email: {app.candidate.email or ""} &nbsp;&nbsp; Status: {app.get_status_display()}', normal), Spacer(1, 8)]

    data = app.data if isinstance(app.data, dict) else {}
    labels = {
        'personal_information':'Personal Particulars','macro_section_1':'Personal Particulars / Family Information',
        'macro_section_2':'Employment History','macro_section_3':'Education / Continuing Education / Languages',
        'macro_section_4':'General Information / Availability / References','macro_section_5':'Personal Data Consent',
        'macro_section_6':'General Assignment','macro_section_7':'HR PDPA Consent',
        'employment_expectations':'Employment Expectations','reference':'References','declaration':'Applicant Declaration',
        'consent':'Consent','documents':'Documents'
    }
    def text(v):
        if isinstance(v, list): return ', '.join(text(x) for x in v)
        if isinstance(v, dict): return '; '.join(f'{k}: {text(x)}' for k,x in v.items())
        if v is True: return 'Yes'
        if v is False: return 'No'
        return '' if v is None else str(v)
    for section, values in data.items():
        if not values: continue
        story.append(Paragraph(labels.get(section, section.replace('_',' ').title()), heading))
        rows=[]
        if isinstance(values, dict):
            for key,val in values.items():
                if key == 'documents': continue
                rows.append([Paragraph(str(key).replace('_',' ').title(), normal), Paragraph(text(val).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'), normal)])
        else:
            rows.append(['', Paragraph(text(values), normal)])
        if rows:
            table=Table(rows, colWidths=[55*mm, 115*mm], repeatRows=0)
            table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.35,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(0,-1),colors.whitesmoke),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
            story.append(table)
    files=list(app.files.all().order_by('-uploaded_at'))
    if files:
        story.append(Paragraph('Uploaded Documents / Images', heading))
        for f in files:
            story.append(Paragraph(f'- {f.field_name or "Document"}: {f.file.name}', normal))
    doc.build(story)
    response=HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition']=f'attachment; filename="application_{app.id}.pdf"'
    return response


@role_required("hr", "administration", "agent", "candidate")
def application_detail(request, pk):
    app = get_object_or_404(
        JobApplication.objects
        .select_related("candidate", "company")
        .prefetch_related("files"),
        pk=pk,
    )

    role = get_role(request.user)

    if role == "agent":
        if not AgentClient.objects.filter(
            agent=request.user,
            candidate=app.candidate,
        ).exists():
            raise Http404

    if role == "candidate":
        candidate = candidate_for_user(request.user)

        if not candidate or app.candidate_id != candidate.pk:
            raise Http404

    if request.GET.get("download", "").lower() == "pdf":
        return _application_pdf_response(app)

    company_name = (app.company.name or "").strip().lower()

    if "insite" in company_name:
        template = "core/insitemy-application.html"
    elif "macro" in company_name:
        template = "core/macrokiosk-application.html"
    else:
        raise Http404("Application company template not found.")

    return render(
        request,
        template,
        {
            "application": app,
            "role": role,
            "saved_data": app.data if isinstance(app.data, dict) else {},
            "uploaded_files": app.files.all().order_by("-uploaded_at"),
        },
    )

@role_required("hr", "administration")
def update_application_status(request, pk):
    """Allow HR/Admin to move an application through its review lifecycle."""
    if request.method != "POST":
        return redirect("application_detail", pk=pk)

    app = get_object_or_404(JobApplication, pk=pk)
    status = request.POST.get("status", "").strip().lower()

    allowed_statuses = {
        "submitted",
        "reviewed",
        "shortlisted",
        "rejected",
    }

    if status not in allowed_statuses:
        messages.error(request, "Invalid application status.")
        return redirect("application_detail", pk=pk)

    app.status = status
    app.save(update_fields=["status", "updated_at"])

    messages.success(
        request,
        f"Application status updated to {app.get_status_display()}.",
    )
    return redirect("application_detail", pk=pk)


@role_required("hr", "administration")
def delete_application(request, pk):

    if request.method == "POST":

        app = get_object_or_404(
            JobApplication,
            pk=pk,
        )

        app.delete()

        messages.success(
            request,
            "Application deleted successfully.",
        )

    return redirect(
        "received_applications"
    )


@role_required("hr", "administration", "agent")
def candidate_list(request):
    candidates = candidate_queryset_for_user(request.user).select_related("user").order_by("-id")
    return render(request, "core/candidate_list.html", {"candidates": candidates, "role": get_role(request.user)})


@role_required("hr", "administration")
def add_candidate(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        if not full_name or not email:
            messages.error(request, "Name and email are required.")
            return render(request, "core/candidate_add.html")
        candidate, created = Candidate.objects.get_or_create(email=email, defaults={"full_name": full_name, "phone": phone})
        if not created:
            candidate.full_name = full_name; candidate.phone = phone; candidate.save()
        Subscription.objects.get_or_create(candidate=candidate)
        messages.success(request, "Candidate saved successfully.")
        return redirect("candidate_list")
    return render(request, "core/candidate_add.html")


@role_required("hr", "administration", "agent")
def candidate_detail(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    role = get_role(request.user)
    if role == "agent" and not AgentClient.objects.filter(agent=request.user, candidate=candidate).exists():
        raise Http404
    return render(request, "core/candidate-detail.html", {"candidate": candidate, "role": role})


@role_required("hr", "administration")
def delete_candidate(request, pk):
    if request.method == "POST":
        get_object_or_404(Candidate, pk=pk).delete()
        messages.success(request, "Candidate deleted successfully.")
    return redirect("candidate_list")


@login_required(login_url="/login/")
def settings_view(request):
    """Administrative settings: company details, users, assignments and legal content."""

    # ================================================================
    # POST
    # ================================================================
    if request.method == "POST":

        action = request.POST.get("action", "").strip()

        # ============================================================
        # CURRENT USER ACCOUNT SETTINGS
        # Available to every authenticated role.
        # ============================================================
        if action == "account":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip().lower()

            if not first_name:
                messages.error(request, "First name is required.")
            elif not email:
                messages.error(request, "Email address is required.")
            elif User.objects.exclude(pk=request.user.pk).filter(email__iexact=email).exists():
                messages.error(request, "That email address is already in use.")
            else:
                request.user.first_name = first_name
                request.user.last_name = last_name
                request.user.email = email
                request.user.username = email
                request.user.save(update_fields=["first_name", "last_name", "email", "username"])
                messages.success(request, "Account settings updated successfully.")
            return redirect("settings")

        # ============================================================
        # COMPANY
        # ============================================================
        if action == "company":

            company_name = request.POST.get(
                "company_name",
                ""
            ).strip()

            company_email = request.POST.get(
                "company_email",
                ""
            ).strip()

            company_phone = request.POST.get(
                "company_phone",
                ""
            ).strip()

            if not company_name:

                messages.error(
                    request,
                    "Company name is required."
                )

            elif Company.objects.filter(
                name__iexact=company_name
            ).exists():

                messages.error(
                    request,
                    f"Company '{company_name}' already exists."
                )

            else:

                Company.objects.create(
                    name=company_name,
                    email=company_email,
                    phone=company_phone,
                )

                messages.success(
                    request,
                    f"{company_name} created successfully."
                )

        # ============================================================
        # CREATE USER
        # ============================================================
        elif action == "create_user":

            name = request.POST.get(
                "name",
                ""
            ).strip()

            email = request.POST.get(
                "email",
                ""
            ).strip().lower()

            password = request.POST.get(
                "newpass",
                ""
            )

            confirm_password = request.POST.get(
                "confirmnewpass",
                ""
            )

            role = request.POST.get(
                "role",
                "candidate"
            ).strip().lower()

            allowed_roles = {
                "candidate",
                "agent",
                "hr",
                "administration",
            }

            if role not in allowed_roles:

                messages.error(
                    request,
                    "Please select a valid role."
                )

            elif not name:

                messages.error(
                    request,
                    "Name is required."
                )

            elif not email:

                messages.error(
                    request,
                    "Email address is required."
                )

            elif len(password) < 8:

                messages.error(
                    request,
                    "Password must contain at least 8 characters."
                )

            elif password != confirm_password:

                messages.error(
                    request,
                    "Passwords do not match."
                )

            elif User.objects.filter(
                email__iexact=email
            ).exists():

                messages.error(
                    request,
                    "A user with this email already exists."
                )

            elif User.objects.filter(
                username__iexact=email
            ).exists():

                messages.error(
                    request,
                    "A user with this username already exists."
                )

            elif role == "hr" and not request.POST.get("company", "").strip():

                messages.error(
                    request,
                    "Please select the company for the HR account."
                )

            else:

                with transaction.atomic():

                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                        first_name=name,
                    )

                    # Administration users are staff
                    if role == "administration":

                        user.is_staff = True

                        user.save(
                            update_fields=[
                                "is_staff"
                            ]
                        )

                    # Remove old role groups if any
                    user.groups.clear()

                    group, _ = Group.objects.get_or_create(
                        name=role
                    )

                    user.groups.add(group)

                    profile, _ = UserProfile.objects.get_or_create(user=user)

                    if role == "hr":
                        company_id = request.POST.get("company", "").strip()
                        selected_company = Company.objects.filter(
                            pk=company_id,
                            is_active=True,
                        ).first()

                        if not selected_company:
                            raise ValidationError(
                                "Invalid company selected for HR account."
                            )

                        profile.application_type = (
                            "insitemy"
                            if selected_company.name.strip().lower() == "insitemy"
                            else "macro_kiosk"
                        )
                        profile.save(
                            update_fields=[
                                "application_type",
                                "updated_at",
                            ]
                        )

                    # Candidate profile
                    if role == "candidate":

                        candidate, _ = Candidate.objects.get_or_create(
                            user=user,
                            defaults={
                                "full_name": name,
                                "email": email,
                            },
                        )

                        # If candidate already exists, keep details updated
                        if (
                            candidate.full_name != name
                            or candidate.email != email
                        ):

                            candidate.full_name = name
                            candidate.email = email

                            candidate.save(
                                update_fields=[
                                    "full_name",
                                    "email",
                                ]
                            )

                        Subscription.objects.get_or_create(
                            candidate=candidate
                        )

                messages.success(
                    request,
                    f"{name} was created successfully as {role.title()}."
                )

        # ============================================================
        # DELETE USER
        # ============================================================
        elif action == "delete_user":

            user_id = request.POST.get(
                "user_id"
            )

            try:

                user = User.objects.get(
                    pk=user_id
                )

                # Do not delete currently logged-in admin
                if user.pk == request.user.pk:

                    messages.error(
                        request,
                        "You cannot delete your own logged-in account."
                    )

                else:

                    user.delete()

                    messages.success(
                        request,
                        "User deleted successfully."
                    )

            except User.DoesNotExist:

                messages.error(
                    request,
                    "User not found."
                )

        # ============================================================
        # DELETE COMPANY
        # ============================================================
        elif action == "delete_company":

            company_id = request.POST.get(
                "company_id"
            )

            try:

                company = Company.objects.get(
                    pk=company_id
                )

                if JobApplication.objects.filter(
                    company=company
                ).exists():

                    messages.error(
                        request,
                        f"Company '{company.name}' cannot be deleted because it has existing job applications."
                    )

                else:

                    company.delete()

                    messages.success(
                        request,
                        f"Company '{company.name}' deleted successfully."
                    )

            except Company.DoesNotExist:

                messages.error(
                    request,
                    "Company not found."
                )

        # ============================================================
        # ASSIGN AGENT TO CANDIDATE
        # ============================================================
        elif action == "assign_agent":

            agent_id = request.POST.get(
                "agent_id"
            )

            # Support both single and multiple candidate fields
            candidate_id = request.POST.get(
                "candidate_id"
            )

            candidate_ids = request.POST.getlist(
                "candidate_ids[]"
            )

            if not candidate_ids and candidate_id:
                candidate_ids = [candidate_id]

            if not agent_id:

                messages.error(
                    request,
                    "Please select an agent."
                )

            elif not candidate_ids:

                messages.error(
                    request,
                    "Please select at least one candidate."
                )

            else:

                try:

                    agent = User.objects.get(
                        pk=agent_id
                    )

                    if get_role(agent) != "agent":

                        raise ValueError(
                            "Selected user is not an agent."
                        )

                    valid_count = 0

                    for selected_candidate_id in candidate_ids:

                        try:

                            candidate = Candidate.objects.get(
                                pk=selected_candidate_id
                            )

                            AgentClient.objects.get_or_create(
                                agent=agent,
                                candidate=candidate,
                            )

                            valid_count += 1

                        except Candidate.DoesNotExist:

                            continue

                    if valid_count:

                        messages.success(
                            request,
                            f"{valid_count} candidate(s) assigned successfully."
                        )

                    else:

                        messages.error(
                            request,
                            "No valid candidates were selected."
                        )

                except User.DoesNotExist:

                    messages.error(
                        request,
                        "Selected agent was not found."
                    )

                except ValueError:

                    messages.error(
                        request,
                        "Please select a valid agent."
                    )

        # ============================================================
        # REMOVE ASSIGNMENT
        # ============================================================
        elif action == "remove_assignment":

            assignment_id = request.POST.get(
                "assignment_id"
            )

            deleted, _ = AgentClient.objects.filter(
                pk=assignment_id
            ).delete()

            if deleted:

                messages.success(
                    request,
                    "Agent assignment removed successfully."
                )

            else:

                messages.error(
                    request,
                    "Assignment not found."
                )

        # ============================================================
        # TERMS
        # ============================================================
        elif action == "update_terms":

            terms_content = request.POST.get(
                "terms_content",
                ""
            ).strip()

            AppSetting.objects.update_or_create(
                key="terms_content",
                defaults={
                    "value": terms_content
                },
            )

            messages.success(
                request,
                "Terms and Conditions updated successfully."
            )

        # ============================================================
        # PRIVACY
        # ============================================================
        elif action == "update_privacy":

            privacy_content = request.POST.get(
                "privacy_content",
                ""
            ).strip()

            AppSetting.objects.update_or_create(
                key="privacy_content",
                defaults={
                    "value": privacy_content
                },
            )

            messages.success(
                request,
                "Privacy Policy updated successfully."
            )

        # ============================================================
        # INVALID ACTION
        # ============================================================
        else:

            messages.error(
                request,
                "Invalid settings action."
            )

        # ============================================================
        # AFTER POST
        # ============================================================
        return redirect("settings")

    # ================================================================
    # LOAD APP SETTINGS
    # ================================================================
    settings_map = {
        item.key: item.value
        for item in AppSetting.objects.filter(
            key__in=[
                "company_name",
                "company_email",
                "company_phone",
                "terms_content",
                "privacy_content",
            ]
        )
    }

    # ================================================================
    # LOAD COMPANIES
    # ================================================================
    companies = Company.objects.all().order_by("-id")

    # ================================================================
    # LOAD USERS
    # ================================================================
    users = (
        User.objects
        .prefetch_related("groups")
        .all()
        .order_by("-date_joined")
    )

    # ================================================================
    # LOAD AGENTS
    # ================================================================
    agents = [
        user
        for user in users
        if get_role(user) == "agent"
    ]

    # ================================================================
    # LOAD CANDIDATES
    # ================================================================
    candidates = (
        Candidate.objects
        .select_related("user")
        .all()
        .order_by("-id")
    )

    # ================================================================
    # LOAD ASSIGNMENTS
    # ================================================================
    assignments = (
        AgentClient.objects
        .select_related(
            "agent",
            "candidate",
        )
        .order_by("-created_at")
    )

    # ================================================================
    # RENDER
    # ================================================================
    return render(
        request,
        "core/settings.html",
        {
            "role": get_role(request.user),

            "settings_map": settings_map,

            "companies": companies,

            "users": users,

            "agents": agents,

            "candidates": candidates,

            "assignments": assignments,
        },
    )

@login_required
def myprofile(request):
    """Persist the existing My Profile UI without changing its design."""
    candidate = Candidate.objects.filter(user=request.user).first()
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    employment_history = None
    if candidate:
        employment_history = EmploymentHistory.objects.filter(
            candidate=candidate
        ).order_by("-id").first()

    if request.method == "POST":
        uploaded_photo = request.FILES.get("profile_photo") or request.FILES.get("file")
        if uploaded_photo:
            if uploaded_photo.size > 5 * 1024 * 1024:
                messages.error(request, "Profile image must be 5 MB or smaller.")
                return redirect("myprofile")
            if Path(uploaded_photo.name).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                messages.error(request, "Profile image must be JPG, JPEG, PNG or WEBP.")
                return redirect("myprofile")
            profile.profile_photo = uploaded_photo

        # The existing page contains several independent modal forms.  They
        # all POST back to this endpoint, so determine the modal by its field
        # names instead of requiring a new hidden action field in the UI.
        if "employer_name" in request.POST:
            if not candidate:
                messages.error(request, "Candidate profile was not found.")
                return redirect("myprofile")

            from datetime import date
            from decimal import Decimal, InvalidOperation

            def parse_date(value):
                try:
                    return date.fromisoformat(value) if value else None
                except ValueError:
                    return None

            def parse_decimal(value):
                try:
                    return Decimal(value) if value else None
                except (InvalidOperation, ValueError):
                    return None

            EmploymentHistory.objects.update_or_create(
                candidate=candidate,
                defaults={
                    "date_from": parse_date(request.POST.get("employment_date_from", "").strip()),
                    "date_to": parse_date(request.POST.get("employment_date_to", "").strip()),
                    "employer_name": request.POST.get("employer_name", "").strip(),
                    "location": request.POST.get("employment_location", "").strip(),
                    "immediate_superior": request.POST.get("superior", "").strip(),
                    "position": request.POST.get("position", "").strip(),
                    "start_salary": parse_decimal(request.POST.get("ssalary", "").strip()),
                    "end_salary": parse_decimal(request.POST.get("esalary", "").strip()),
                    "reason_for_leaving": request.POST.get("reasons", "").strip(),
                    "job_description": request.POST.get("job_description", "").strip(),
                },
            )
            messages.success(request, "Employment history has been updated successfully.")
            return redirect("myprofile")

        # Always persist the account identity fields when present.
        first_name = request.POST.get("fname")
        middle_name = request.POST.get("mname")
        last_name = request.POST.get("lname")
        email = request.POST.get("email")
        phone = request.POST.get("phone")

        if email is not None:
            email = email.strip().lower()
            if not email:
                messages.error(request, "Email address is required.")
                return redirect("myprofile")
            if User.objects.exclude(pk=request.user.pk).filter(email__iexact=email).exists():
                messages.error(request, "That email address is already in use.")
                return redirect("myprofile")
            request.user.email = email
            request.user.username = email

        if first_name is not None:
            request.user.first_name = first_name.strip()
        if last_name is not None:
            request.user.last_name = last_name.strip()
        request.user.save(update_fields=["first_name", "last_name", "email", "username"])

        if middle_name is not None:
            profile.middle_name = middle_name.strip()
        if phone is not None:
            profile.phone = phone.strip()

        # Persist every other field from the current modal. This keeps the
        # existing HTML field names/content intact and makes the values survive
        # refresh/login instead of being only front-end values.
        ignored = {"csrfmiddlewaretoken", "fname", "mname", "lname", "email", "phone"}
        posted_profile = dict(profile.profile_data or {})
        for key, values in request.POST.lists():
            if key in ignored or key.startswith("save_"):
                continue
            if key in {"employer_name", "employment_location", "superior", "position", "ssalary", "esalary", "reasons", "job_description", "employment_date_from", "employment_date_to"}:
                continue
            posted_profile[key] = values[0] if len(values) == 1 else values

        profile.profile_data = posted_profile
        profile.save()

        if candidate:
            if first_name is not None or last_name is not None:
                candidate.full_name = " ".join(
                    part for part in [request.user.first_name, request.user.last_name]
                    if part
                ).strip()
            if email is not None:
                candidate.email = email
            if phone is not None:
                candidate.phone = phone.strip()
            candidate.profile_data = {
                **(candidate.profile_data or {}),
                **posted_profile,
            }
            candidate.save()

        messages.success(request, "Your profile has been updated successfully.")
        return redirect("myprofile")

    # The template historically reads candidate.profile_data. Provide the
    # same shape for non-candidate accounts through a lightweight fallback.
    if candidate:
        profile_data = candidate.profile_data or {}
    else:
        profile_data = profile.profile_data or {}

    context = {
        "candidate": candidate,
        "profile": profile,
        "employment_history": employment_history,
        "profile_data": profile_data,
    }
    return render(request, "core/myprofile.html", context)

@role_required("administration", "hr", "agent", "candidate")
def security(request):
    if request.method == "POST":
        old_password = request.POST.get("oldpass", "")
        new_password = request.POST.get("newpass", "")
        confirm = request.POST.get("confirmnewpass", "")
        if not request.user.check_password(old_password):
            messages.error(request, "Old password is incorrect.")
        elif len(new_password) < 8:
            messages.error(request, "New password must be at least 8 characters long.")
        elif new_password != confirm:
            messages.error(request, "New passwords do not match.")
        else:
            request.user.set_password(new_password)
            request.user.save(update_fields=["password"])
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password updated successfully.")
            return redirect("security")
    return render(request, "core/security.html", {"role": get_role(request.user)})


@role_required("candidate")
def mydata(request):
    candidate = candidate_for_user(request.user)
    if not candidate:
        messages.error(request, "Candidate profile was not found.")
        return redirect("dashboard")
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "upload":
            name = request.POST.get("dcname", "").strip()
            uploaded = request.FILES.get("document")
            if not name or not uploaded:
                messages.error(request, "Document name and file are required.")
            elif uploaded.size > MAX_UPLOAD_SIZE:
                messages.error(request, "Maximum file size is 1 MB.")
            elif Path(uploaded.name).suffix.lower() not in ALLOWED_UPLOAD_EXTENSIONS:
                messages.error(request, "This file type is not allowed.")
            else:
                CandidateDocument.objects.create(candidate=candidate, name=name, file=uploaded)
                messages.success(request, "Document uploaded successfully.")
        elif action == "delete":
            CandidateDocument.objects.filter(pk=request.POST.get("document_id"), candidate=candidate).delete()
            messages.success(request, "Document deleted successfully.")
        return redirect("mydata")
    return render(
        request,
        "core/mydata.html",
        {"role": get_role(request.user), "candidate": candidate, "documents": candidate.documents.order_by("-uploaded_at")},
    )


def simple_page(request, page):
    allowed = {
        "faqs": "faqs.html",
        "terms": "terms-conditions.html",
        "privacy": "privacy-policy.html",
        "feedback": "feedback.html",
    }
    if page not in allowed:
        raise Http404
    if not request.user.is_authenticated:
        return redirect(f"/login/?next={request.path}")
    if page == "feedback" and request.method == "POST":
        message = request.POST.get("message", "").strip()
        try:
            rating = max(0, min(int(request.POST.get("rating", "0")), 5))
        except ValueError:
            rating = 0
        if not message:
            messages.error(request, "Please enter your feedback message.")
        else:
            Feedback.objects.create(
                candidate=candidate_for_user(request.user),
                message=message,
                rating=rating,
            )
            messages.success(request, "Feedback submitted successfully.")
            return redirect("feedback")
    return render(request, "core/" + allowed[page], {"role": get_role(request.user)})



