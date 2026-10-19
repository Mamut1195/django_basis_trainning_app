"""Identity workflows and business rules without Django, DB, network or settings."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import TracebackType
from typing import Self
from unittest import TestCase

from basis.modules.accounts.application.identity import RegisterAccount
from basis.modules.accounts.domain.identity import (
    Account,
    AccountUnavailable,
    RateState,
    VerificationClaim,
    consume_attempt,
)
from basis.modules.accounts.public import ConsumeAttempt, Identity
from basis.modules.athletes.public import (
    InvalidAthleteData,
    MeasuredRMData,
    MeasuredRMState,
    SportData,
    WellnessData,
    require_adult,
    require_legacy_link,
    require_unchanged_rm,
    valid_availability,
    validate_sport,
    validate_wellness,
)
from basis.modules.catalog.public import catalog_allowed, valid_muscle_names
from basis.shared.identifiers import AccountId, AthleteId, ExerciseId
from tests_architecture.identity_contract import IdentityContract

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


class Memory:
    def __init__(self) -> None:
        self.accounts: dict[AccountId, Account] = {}
        self.profiles: dict[AccountId, bool] = {}
        self.billing: set[AccountId] = set()
        self.windows: dict[tuple[str, str], RateState] = {}
        self.fail_mail = False
        self.delivered: list[Account] = []

    def lock(self, account: AccountId) -> Account:
        return self.accounts[account]

    def create_inactive(self, command: RegisterAccount) -> Account:
        account = Account(AccountId(len(self.accounts) + 1), command.email, command.name, False)
        self.accounts[account.id] = account
        return account

    def by_claim(self, claim: VerificationClaim) -> Account:
        account = self.accounts.get(claim.account)
        if account is None or account.email != claim.email:
            raise AccountUnavailable
        return account

    def pending(self, email: str) -> Account | None:
        return next(
            (
                a
                for a in self.accounts.values()
                if not a.active and a.email.casefold() == email.casefold()
            ),
            None,
        )

    def activate(self, account: AccountId) -> None:
        self.accounts[account] = replace(self.accounts[account], active=True)

    def username_exists(self, email: str) -> bool:
        return any(a.email == email for a in self.accounts.values())

    def enroll(self, account: AccountId, name: str, email: str, started_on: date) -> None:
        self.profiles[account] = False

    def verify_email(self, account: AccountId) -> None:
        if account in self.profiles:
            self.profiles[account] = True

    def exists(self, account: AccountId) -> bool:
        return account in self.profiles

    def email_exists(self, email: str) -> bool:
        return self.username_exists(email)

    def link_legacy(self, account: AccountId, email: str, profile: AthleteId) -> None:
        raise NotImplementedError

    def decode(self, token: str) -> VerificationClaim:
        account = self.accounts[AccountId(int(token))]
        return VerificationClaim(account.id, account.email)

    def send(self, account: Account) -> None:
        if self.fail_mail:
            raise OSError("mail unavailable")
        self.delivered.append(account)


class FakeBilling:
    def __init__(self, memory: Memory) -> None:
        self.memory = memory

    def enroll(self, account: AccountId) -> None:
        self.memory.billing.add(account)


class FakeWindows:
    def __init__(self, memory: Memory) -> None:
        self.memory = memory

    def lock(self, action: str, address: str, initial: RateState) -> RateState:
        return self.memory.windows.setdefault((action, address), initial)

    def save(self, action: str, address: str, state: RateState) -> None:
        self.memory.windows[(action, address)] = state


class FakeWork:
    def __init__(self, memory: Memory) -> None:
        self.memory = memory
        self.before = (
            dict(memory.accounts),
            dict(memory.profiles),
            set(memory.billing),
            dict(memory.windows),
        )
        self.committed = False

    def __enter__(self) -> Self:
        return self

    def commit(self) -> None:
        self.committed = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type or not self.committed:
            self.memory.accounts, self.memory.profiles, self.memory.billing, self.memory.windows = (
                self.before
            )


class Clock:
    def today(self) -> date:
        return NOW.date()

    def now(self) -> datetime:
        return NOW


class IdentityTests(IdentityContract, TestCase):
    def setUp(self) -> None:
        self.memory = Memory()
        self.service = Identity(
            self.memory,
            self.memory,
            FakeBilling(self.memory),
            self.memory,
            FakeWindows(self.memory),
            lambda: FakeWork(self.memory),
            Clock(),
        )
        self.counts = lambda: (
            len(self.memory.accounts),
            len(self.memory.profiles),
            len(self.memory.billing),
        )
        self.fail_delivery = lambda: setattr(self.memory, "fail_mail", True)
        self.token_for = lambda a: str(a.id)
        self.active = lambda id: self.memory.accounts[id].active
        self.verified = lambda id: self.memory.profiles[id]

    def test_attempts_count_denied_requests_and_isolate_addresses_and_actions(self) -> None:
        assert self.service.allow_attempt(ConsumeAttempt("login", "a", maximum=1))
        assert not self.service.allow_attempt(ConsumeAttempt("login", "a", maximum=1))
        assert self.memory.windows[("login", "a")].count == 2
        assert self.service.allow_attempt(ConsumeAttempt("login", "b", maximum=1))
        assert self.service.allow_attempt(ConsumeAttempt("signup", "a", maximum=1))

    def test_resend_only_pending_profile_without_exposing_existence(self) -> None:
        self.service.resend("missing@example.test")
        assert not self.memory.delivered
        account = self.service.register(RegisterAccount("new@example.test", "New", "encoded"))
        self.service.resend("NEW@example.test")
        assert len(self.memory.delivered) == 2
        self.memory.activate(account.id)
        self.service.resend(account.email)
        assert len(self.memory.delivered) == 2


class PolicyTests(TestCase):
    def test_fixed_window_resets_at_exact_expiry(self) -> None:
        assert consume_attempt(RateState(99, NOW), NOW, timedelta(minutes=15)) == RateState(
            1, NOW + timedelta(minutes=15)
        )

    def test_wellness_zero_is_observed_and_absence_is_not_zero(self) -> None:
        data = WellnessData(
            NOW.date(), Decimal(0), None, None, None, None, None, "", 0, None, None, "", ""
        )
        validate_wellness(data)
        with self.assertRaises(InvalidAthleteData):
            validate_wellness(replace(data, hrv_ms=Decimal(0)))
        with self.assertRaises(InvalidAthleteData):
            validate_wellness(replace(data, pain_score=1))

    def test_sport_requires_provenance_and_compatible_unit(self) -> None:
        data = SportData("running", "beginner", Decimal(150), "bpm", NOW.date(), "test")
        validate_sport(data)
        for invalid in (replace(data, method=""), replace(data, threshold_unit="watts")):
            with self.assertRaises(InvalidAthleteData):
                validate_sport(invalid)

    def test_adult_boundaries_and_optional_age(self) -> None:
        for age in (None, 18, 120):
            require_adult(age)
        for age in (17, 121):
            with self.assertRaises(InvalidAthleteData):
                require_adult(age)

    def test_rm_changes_including_owner_are_rejected(self) -> None:
        state = MeasuredRMState(
            AthleteId(5), MeasuredRMData(ExerciseId(2), Decimal(100), NOW.date())
        )
        require_unchanged_rm(state, state)
        for changed in (
            replace(state, athlete=AthleteId(6)),
            replace(state, data=replace(state.data, peso_maximo_rm=Decimal(101))),
        ):
            with self.assertRaises(InvalidAthleteData):
                require_unchanged_rm(state, changed)

    def test_explicit_link_checks_owner_other_profile_then_email(self) -> None:
        require_legacy_link(None, AccountId(2), False, "A@test.test", "a@test.test")
        for current, other, email in (
            (AccountId(3), False, "a@test.test"),
            (None, True, "a@test.test"),
            (None, False, "b@test.test"),
        ):
            with self.assertRaises(InvalidAthleteData):
                require_legacy_link(current, AccountId(2), other, email, "a@test.test")

    def test_catalog_permission_matrix(self) -> None:
        for authenticated in (False, True):
            for staff in (False, True):
                for read in (False, True):
                    assert catalog_allowed(authenticated, staff, read) == (
                        authenticated and (read or staff)
                    )

    def test_availability_rejects_duplicates_booleans_and_invalid_shapes(self) -> None:
        assert valid_availability([]) and valid_availability([1, 7])
        value: object
        for value in ([1, 1], [True], [0], [8], "1", {"day": 1}, [[]]):
            assert not valid_availability(value)

    def test_muscle_names_reject_scalar_objects_and_bounds(self) -> None:
        assert valid_muscle_names([]) and valid_muscle_names(["quads"])
        value: object
        for value in ("quads", {"quads": True}, [True], ["x" * 81], ["x"] * 31):
            assert not valid_muscle_names(value)
