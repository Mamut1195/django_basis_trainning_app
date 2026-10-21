"""Bind Django activity and the stable public athlete verification projection."""

from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied

from basis.modules.athletes.public import (
    BillingProfiles,
    PersonalAccessDenied,
    PersonalAuthorization,
    PersonalIdentity,
)
from basis.shared.identifiers import AccountId


class DjangoPersonalIdentities:
    def __init__(self, profiles: BillingProfiles) -> None:
        self.profiles = profiles

    def get(self, owner: AccountId) -> PersonalIdentity | None:
        profile = self.profiles.get(owner)
        if profile is None:
            return None
        active = get_user_model().objects.filter(pk=owner, is_active=True).exists()
        return PersonalIdentity(profile.owner, active, profile.email_verified)


class DjangoPersonalAuthorization:
    def __init__(self, authorization: PersonalAuthorization) -> None:
        self.authorization = authorization

    def require(self, owner: AccountId) -> None:
        try:
            self.authorization.require(owner)
        except PersonalAccessDenied as error:
            raise PermissionDenied(str(error)) from error
