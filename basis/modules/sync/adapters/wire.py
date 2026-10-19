"""Deferred conversion of existing offline payloads at the infrastructure edge."""

import hashlib
import json
from collections.abc import Mapping
from typing import Protocol, cast
from uuid import UUID

from django.core.exceptions import ValidationError

from basis.modules.training.public import SessionChanges
from basis.shared.identifiers import AccountId, MutationId, PayloadDigest, Revision, SessionId

from ..public import MutationIdentity


class Conflict(Exception):
    def __init__(self, current: dict[str, object] | None) -> None:
        self.current = current
        super().__init__(current)


class WireSource:
    def __init__(self, mutation: object, payload: object, owner: AccountId,
                 decode_changes: "ChangesDecoder") -> None:
        self.mutation = mutation
        self.payload = payload
        self.owner = owner
        self.decode_changes = decode_changes

    def identity(self) -> MutationIdentity:
        try:
            mutation = MutationId(UUID(str(self.mutation)))
            payload = mapping(self.payload)
            session = SessionId(UUID(str(payload["id"])))
        except (ValueError, KeyError, TypeError):
            raise ValidationError("Identificador de sincronizaci\u00f3n inv\u00e1lido.") from None
        digest = PayloadDigest(hashlib.sha256(
            json.dumps(self.payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest())
        return MutationIdentity(mutation, session, digest)

    def revision(self) -> Revision:
        payload = mapping(self.payload)
        allowed = {"id", "revision", "title", "date", "status", "duration_seconds",
                   "duration_protocol", "reported_rpe", "notes", "planned", "blocks"}
        if set(payload) - allowed or type(payload.get("revision")) is not int:
            raise ValidationError("Formato o revisi\u00f3n de sesi\u00f3n inv\u00e1lida.")
        revision = payload["revision"]
        assert isinstance(revision, int)
        return Revision(revision)

    def changes(self) -> SessionChanges:
        return self.decode_changes(self.owner, mapping(self.payload))


class ChangesDecoder(Protocol):
    def __call__(self, owner: AccountId, payload: Mapping[str, object]) -> SessionChanges: ...


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("Expected an offline session object")
    return cast(dict[str, object], value)
