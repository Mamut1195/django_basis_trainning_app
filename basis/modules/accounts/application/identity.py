"""Identity workflows. Password hashing and token cryptography belong to adapters."""

from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import Callable, Protocol

from basis.modules.athletes.public import AthleteEnrollment
from basis.modules.billing.public import BillingEnrollment
from basis.shared.identifiers import AccountId, AthleteId
from basis.shared.ports import Clock, UnitOfWork

from ..domain.identity import (
    Account,
    RateState,
    RegistrationConflict,
    VerificationClaim,
    consume_attempt,
)


@dataclass(frozen=True)
class RegisterAccount:
    email: str
    name: str
    encoded_password: str = field(repr=False)


@dataclass(frozen=True)
class VerifyAccount:
    token: str = field(repr=False)
    confirm: bool = False


@dataclass(frozen=True)
class ConsumeAttempt:
    action: str
    address: str
    maximum: int = 10
    minutes: int = 15


@dataclass(frozen=True)
class LinkLegacyProfile:
    account: AccountId
    profile: AthleteId


class Accounts(Protocol):
    def lock(self, account: AccountId) -> Account: ...
    def create_inactive(self, command: RegisterAccount) -> Account: ...
    def by_claim(self, claim: VerificationClaim) -> Account: ...
    def pending(self, email: str) -> Account | None: ...
    def activate(self, account: AccountId) -> None: ...
    def username_exists(self, email: str) -> bool: ...


class Verification(Protocol):
    def decode(self, token: str) -> VerificationClaim: ...
    def send(self, account: Account) -> None: ...


class RateWindows(Protocol):
    def lock(self, action: str, address: str, initial: RateState) -> RateState: ...
    def save(self, action: str, address: str, state: RateState) -> None: ...


class Identity:
    def __init__(
        self,
        accounts: Accounts,
        athletes: AthleteEnrollment,
        billing: BillingEnrollment,
        verification: Verification,
        windows: RateWindows,
        uow: Callable[[], UnitOfWork],
        clock: Clock,
    ) -> None:
        self.accounts = accounts
        self.athletes = athletes
        self.billing = billing
        self.verification = verification
        self.windows = windows
        self.uow = uow
        self.clock = clock

    def email_in_use(self, email: str) -> bool:
        return self.accounts.username_exists(email) or self.athletes.email_exists(email)

    def register(self, command: RegisterAccount) -> Account:
        # Form validation/hashing stays in Django. Mail failure must roll back all rows.
        with self.uow() as work:
            if self.email_in_use(command.email):
                raise RegistrationConflict
            account = self.accounts.create_inactive(command)
            self.athletes.enroll(account.id, account.name, account.email, self.clock.today())
            self.billing.enroll(account.id)
            self.verification.send(account)
            work.commit()
            return account

    def verify(self, command: VerifyAccount) -> Account:
        claim = self.verification.decode(command.token)
        with self.uow() as work:
            account = self.accounts.by_claim(claim)
            if command.confirm:
                self.accounts.activate(account.id)
                self.athletes.verify_email(account.id)
            work.commit()
            return replace(account, active=True) if command.confirm else account

    def resend(self, email: str) -> None:
        account = self.accounts.pending(email)
        if account is not None and self.athletes.exists(account.id):
            self.verification.send(account)

    def allow_attempt(self, command: ConsumeAttempt) -> bool:
        duration = timedelta(minutes=command.minutes)
        with self.uow() as work:
            current = self.windows.lock(
                command.action, command.address, RateState(0, self.clock.now() + duration)
            )
            updated = consume_attempt(current, self.clock.now(), duration)
            self.windows.save(command.action, command.address, updated)
            work.commit()
            return updated.count <= command.maximum

    def link_legacy(self, command: LinkLegacyProfile) -> None:
        with self.uow() as work:
            current = self.accounts.lock(command.account)
            self.athletes.link_legacy(current.id, current.email, command.profile)
            work.commit()
