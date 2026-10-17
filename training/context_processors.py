from .access import can_write


def app_context(request):
    profile = getattr(request.user, "athlete", None) if request.user.is_authenticated else None
    return {
        "athlete": profile,
        "write_access": can_write(request.user),
        "account_scope": str(profile.public_id) if profile else "",
    }
