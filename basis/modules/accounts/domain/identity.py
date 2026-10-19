"""Identity values and fixed-window policy, independent of authentication providers."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from basis.shared.identifiers import AccountId


class InvalidVerification(Exception):
    pass


class AccountUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Account:
    id: AccountId
    email: str
    name: str
    active: bool


@dataclass(frozen=True)
class VerificationClaim:
    account: AccountId
    email: str


@dataclass(frozen=True)
class RateState:
    count: int
    expires_at: datetime


def consume_attempt(state: RateState, now: datetime, duration: timedelta) -> RateState:
    if state.expires_at <= now:
        return RateState(1, now + duration)
    return RateState(state.count + 1, state.expires_at)
