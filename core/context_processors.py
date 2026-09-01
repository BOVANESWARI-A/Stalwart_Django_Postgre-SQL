from .views import get_role, user_application_type


def app_context(request):
    role = get_role(request.user)
    return {
        "app_role": role,
        "app_application_type": user_application_type(request.user) if role == "hr" else "",
    }
