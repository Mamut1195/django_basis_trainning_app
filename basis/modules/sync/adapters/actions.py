"""Django entry binding for offline synchronization."""

from django.contrib.auth.base_user import AbstractBaseUser

from basis.modules.sync.adapters.input_actions import synchronize
from basis.shared.identifiers import AccountId

from .wire import Conflict as Conflict


def sync_session(
    owner: AbstractBaseUser, mutation_id: object, payload: object
) -> dict[str, object]:
    return synchronize(AccountId(owner.pk), mutation_id, payload)
