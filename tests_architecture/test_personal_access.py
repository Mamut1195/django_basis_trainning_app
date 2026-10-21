"""Free personal policy has no dependency on commercial entitlement."""

from dataclasses import replace
from unittest import TestCase

from basis.modules.athletes.public import (
    PersonalAccessDenied,
    PersonalAuthorization,
    PersonalIdentity,
)
from basis.shared.identifiers import AccountId


class IdentityPort:
    def __init__(self, state: PersonalIdentity | None) -> None:
        self.state = state

    def get(self, owner: AccountId) -> PersonalIdentity | None:
        return self.state


class PersonalAccessTests(TestCase):
    def test_active_verified_linked_owner_is_allowed_without_billing_port(self) -> None:
        PersonalAuthorization(IdentityPort(PersonalIdentity(AccountId(1), True, True))).require(
            AccountId(1)
        )

    def test_missing_inactive_unverified_or_foreign_projection_are_denied(self) -> None:
        state = PersonalIdentity(AccountId(1), True, True)
        for candidate in (
            None,
            replace(state, active=False),
            replace(state, email_verified=False),
            replace(state, owner=AccountId(2)),
        ):
            with self.subTest(candidate=candidate), self.assertRaises(PersonalAccessDenied):
                PersonalAuthorization(IdentityPort(candidate)).require(AccountId(1))
