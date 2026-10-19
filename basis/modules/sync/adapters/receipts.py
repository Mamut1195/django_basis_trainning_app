"""Existing owner-scoped receipt rows; snapshot codecs are injected by bootstrap."""

from typing import Callable

from basis.modules.training.public import SessionState
from basis.shared.identifiers import AccountId, MutationId, PayloadDigest
from training.models import SyncReceipt

from ..domain.operations import Receipt


class DjangoReceiptRepository:
    def __init__(
        self,
        decoder: Callable[[AccountId, object], SessionState],
        encoder: Callable[[SessionState], dict[str, object]],
    ) -> None:
        self.decoder = decoder
        self.encoder = encoder

    def get(self, owner: AccountId, mutation: MutationId) -> Receipt | None:
        row = SyncReceipt.objects.filter(owner_id=owner, mutation_id=mutation).first()
        if row is None:
            return None
        return Receipt(
            owner, mutation, PayloadDigest(row.payload_hash), self.decoder(owner, row.result)
        )

    def save(self, receipt: Receipt) -> None:
        SyncReceipt.objects.create(
            owner_id=receipt.owner,
            mutation_id=receipt.mutation,
            payload_hash=receipt.digest,
            result=self.encoder(receipt.result),
        )
