"""Template context composed from athlete identity and commercial access."""

from django.http import HttpRequest

from basis.modules.athletes.adapters.models import User
from basis.modules.billing.adapters.access import can_write

from .brand import IDENTITY


def app_context(request: HttpRequest) -> dict[str, object]:
    profile = (
        User.objects.filter(account_id=request.user.pk).first()
        if request.user.is_authenticated
        else None
    )
    return {
        "basis_brand": IDENTITY,
        "athlete": profile,
        "write_access": can_write(request.user),
        "account_scope": str(profile.public_id) if profile else "",
    }
