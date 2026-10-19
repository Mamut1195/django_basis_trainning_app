"""Password recovery delegates tokens, active-user filtering and mail to a provider."""

from dataclasses import dataclass
from typing import Protocol


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
