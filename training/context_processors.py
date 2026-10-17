from .access import can_write
from .brand import IDENTITY


def app_context(request):
    profile = getattr(request.user, "athlete", None) if request.user.is_authenticated else None
    return {
        "basis_brand": IDENTITY,
        "athlete": profile,
        "write_access": can_write(request.user),
        "account_scope": str(profile.public_id) if profile else "",
    }
