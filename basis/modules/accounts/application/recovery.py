"""Password recovery delegates tokens, active-user filtering and mail to a provider."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

from basis.shared.identifiers import AccountId


@dataclass(frozen=True)
class RecoverPassword:
    email: str
    secure: bool


class PasswordRecovery(Protocol):
    def send(self, command: RecoverPassword) -> None: ...


class Recovery:
    def __init__(self, provider: PasswordRecovery) -> None:
        self.provider = provider

    def request(self, command: RecoverPassword) -> None:
        # Same outward result for unknown, inactive and active addresses.
        self.provider.send(command)


@dataclass(frozen=True)
class ConfirmPasswordReset:
    account: AccountId
    token: str | None = field(repr=False)


ResetOutcome = Literal["updated", "invalid", "invalid-password"]


class ResetAuthority(Protocol):
    def confirm(self, command: ConfirmPasswordReset) -> ResetOutcome: ...


class ResetConfirmation:
    def __init__(self, authority: ResetAuthority) -> None:
        self.authority = authority

    def confirm(self, command: ConfirmPasswordReset) -> ResetOutcome:
        return self.authority.confirm(command)
