"""Personal setup is free for a persisted active, verified account/profile pair."""

from dataclasses import dataclass
from typing import Protocol

from basis.shared.identifiers import AccountId


class PersonalAccessDenied(Exception):
    pass


@dataclass(frozen=True)
class PersonalIdentity:
    owner: AccountId
    active: bool
    email_verified: bool


class PersonalIdentities(Protocol):
    def get(self, owner: AccountId) -> PersonalIdentity | None: ...


class PersonalAuthorization:
    def __init__(self, identities: PersonalIdentities) -> None:
        self.identities = identities

    def require(self, owner: AccountId) -> None:
        identity = self.identities.get(owner)
        if (
            identity is None
            or identity.owner != owner
            or not identity.active
            or not identity.email_verified
        ):
            raise PersonalAccessDenied(
                "Necesitas una cuenta activa con perfil vinculado y correo verificado. "
                "El perfil personal es gratuito; no requiere suscripción."
            )
