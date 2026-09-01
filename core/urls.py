from django.urls import path
from . import views


urlpatterns = [
    # ============================================================
    # AUTHENTICATION
    # ============================================================
    path("", views.login_view, name="login"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("signup/", views.signup, name="signup"),

    # ============================================================
    # CUSTOM PASSWORD RESET
    # ============================================================
    path(
        "reset-password/",
        views.reset_password,
        name="reset_password",
    ),

    path(
        "password-reset/<int:uid>/<str:token>/",
        views.password_reset_confirm,
        name="password_reset_confirm",
    ),

    # ============================================================
    # DASHBOARD
    # ============================================================
    path(
        "dashboard/",
        views.dashboard,
        name="dashboard",
    ),

    path(
        "dashboard/data/",
        views.dashboard_data,
        name="dashboard_data",
    ),

    # ============================================================
    # CANDIDATES
    # ============================================================
    path(
        "candidates/",
        views.candidate_list,
        name="candidate_list",
    ),

    path(
        "candidates/add/",
        views.add_candidate,
        name="add_candidate",
    ),

    path(
        "candidates/<int:pk>/",
        views.candidate_detail,
        name="candidate_detail",
    ),

    path(
        "candidates/<int:pk>/delete/",
        views.delete_candidate,
        name="delete_candidate",
    ),

    # ============================================================
    # COMPANY APPLICATION ENTRY
    # ============================================================
    path(
        "applications/insitemy/",
        views.insitemy,
        name="insitemy",
    ),

    path(
        "applications/macro-kiosk/",
        views.macro_kiosk,
        name="macro_kiosk",
    ),

    # ============================================================
    # CANDIDATE INVITATIONS / APPLICATIONS
    # ============================================================
    path(
        "candidate/invitation/<uuid:token>/",
        views.candidate_invitation,
        name="candidate_invitation",
    ),

    path(
        "candidate/application/<uuid:token>/",
        views.candidate_application,
        name="candidate_application",
    ),

    # Legacy URL
    path(
        "candidate-application/<uuid:token>/",
        views.candidate_application,
        name="candidate_application_legacy",
    ),

    # ============================================================
    # SEND INVITATION
    # ============================================================
    path(
        "send-invitation/",
        views.send_invitation,
        name="send_invitation",
    ),

    # ============================================================
    # APPLICATIONS
    # ============================================================
    path(
        "submitted-applications/",
        views.submitted_applications,
        name="submitted_applications",
    ),

    path(
        "received-applications/",
        views.received_applications,
        name="received_applications",
    ),

    path(
        "application/<int:pk>/",
        views.application_detail,
        name="application_detail",
    ),

    path(
        "application/<int:pk>/status/",
        views.update_application_status,
        name="update_application_status",
    ),

    path(
        "application/<int:pk>/delete/",
        views.delete_application,
        name="delete_application",
    ),
]


# ================================================================
# ACCOUNT / STATIC PAGES
# ================================================================

urlpatterns += [

    # ============================================================
    # REAL BACKEND CONNECTED PAGES
    # ============================================================

    path(
        "myprofile/",
        views.myprofile,
        name="myprofile",
    ),

    path(
        "mydata/",
        views.mydata,
        name="mydata",
    ),

    path(
        "settings/",
        views.settings_view,
        name="settings",
    ),

    path(
        "security/",
        views.security,
        name="security",
    ),

    # ============================================================
    # STATIC / INFORMATION PAGES
    # ============================================================

    path(
        "faqs/",
        lambda request: views.simple_page(request, "faqs"),
        name="faqs",
    ),

    path(
        "terms/",
        lambda request: views.simple_page(request, "terms"),
        name="terms",
    ),

    path(
        "privacy/",
        lambda request: views.simple_page(request, "privacy"),
        name="privacy",
    ),

    path(
        "feedback/",
        lambda request: views.simple_page(request, "feedback"),
        name="feedback",
    ),

    path(
        "password_set/",
        lambda request: views.simple_page(request, "password_set"),
        name="password_set",
    ),

    path(
        "email_activation/",
        lambda request: views.simple_page(request, "email_activation"),
        name="email_activation",
    ),

    path(
        "email_reset/",
        lambda request: views.simple_page(request, "email_reset"),
        name="email_reset",
    ),
]