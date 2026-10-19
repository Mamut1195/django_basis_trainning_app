"""Immutable identity and original result of an offline operation."""

from dataclasses import dataclass

from basis.modules.training.public import SessionState
from basis.shared.identifiers import AccountId, MutationId, PayloadDigest, SessionId


@dataclass(frozen=True)
class MutationIdentity:
    mutation: MutationId
    session: SessionId
    digest: PayloadDigest


@dataclass(frozen=True)
class Receipt:
    owner: AccountId
    mutation: MutationId
    digest: PayloadDigest
    result: SessionState


class InvalidSynchronization(Exception):
    pass


def replay(receipt: Receipt, digest: PayloadDigest) -> SessionState:
    if receipt.digest != digest:
        raise InvalidSynchronization("La misma operaci\u00f3n no puede contener datos diferentes.")
    return receipt.result
