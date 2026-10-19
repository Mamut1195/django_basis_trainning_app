"""The same registration/verification transaction contract for fake and Django adapters."""

from typing import Callable

from basis.modules.accounts.public import Account, Identity, RegisterAccount, VerifyAccount
from basis.shared.identifiers import AccountId


class IdentityContract:
    service: Identity
    counts: Callable[[], tuple[int, int, int]]
    fail_delivery: Callable[[], None]
    token_for: Callable[[Account], str]
    active: Callable[[AccountId], bool]
    verified: Callable[[AccountId], bool]

    def test_contract_registration_commits_all_three_rows_inactive(self) -> None:
        created = self.service.register(RegisterAccount("new@example.test", "New", "encoded"))
        assert self.counts() == (1, 1, 1)
        assert not self.active(created.id)
        assert not self.verified(created.id)

    def test_contract_delivery_error_rolls_back_all_three_rows(self) -> None:
        self.fail_delivery()
        try:
            self.service.register(RegisterAccount("new@example.test", "New", "encoded"))
        except OSError:
            pass
        else:
            raise AssertionError("Expected delivery error")
        assert self.counts() == (0, 0, 0)

    def test_contract_read_claim_does_not_activate_but_confirmation_does(self) -> None:
        created = self.service.register(RegisterAccount("new@example.test", "New", "encoded"))
        token = self.token_for(created)
        assert not self.service.verify(VerifyAccount(token)).active
        assert not self.active(created.id) and not self.verified(created.id)
        assert self.service.verify(VerifyAccount(token, confirm=True)).active
        assert self.active(created.id) and self.verified(created.id)
