"""Transactional billing commands, access policy and durable webhook phases."""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Callable, Literal, Protocol
from uuid import UUID

from basis.modules.athletes.public import BillingProfile, BillingProfiles
from basis.shared.identifiers import AccountId
from basis.shared.ports import Clock, UnitOfWork

from ..domain.records import (
    BillingState,
    CheckoutLink,
    CustomerState,
    Product,
    ProviderUnavailable,
    VerificationRequired,
    reconcile_state,
    state_entitled,
    validate_product,
)


@dataclass(frozen=True)
class OwnerBilling:
    owner: AccountId


@dataclass(frozen=True)
class Checkout(OwnerBilling):
    email: str


class BillingRepository(Protocol):
    def lock(self, owner: AccountId) -> BillingState: ...
    def get(self, owner: AccountId) -> BillingState | None: ...
    def save(self, state: BillingState) -> None: ...
    def mark_pending(self, owner: AccountId) -> None: ...


class Gateway(Protocol):
    def product(self) -> Product: ...
    def checkout(self, public_id: UUID, email: str, allow_trial: bool) -> CheckoutLink: ...
    def portal(self, public_id: UUID) -> str: ...
    def customer(self, public_id: UUID) -> CustomerState: ...
    def validate_link(self, url: str) -> str: ...


class Billing:
    def __init__(
        self,
        repository: BillingRepository,
        profiles: BillingProfiles,
        gateway: Gateway,
        uow_factory: Callable[[], UnitOfWork],
        clock: Clock,
        product_id: str,
        development_access: bool = False,
    ) -> None:
        self.repository = repository
        self.profiles = profiles
        self.gateway = gateway
        self.uow_factory = uow_factory
        self.clock = clock
        self.product_id = product_id
        self.development_access = development_access

    def profile(self, owner: AccountId) -> BillingProfile:
        profile = self.profiles.get(owner)
        if profile is None:
            raise VerificationRequired("Verifica tu correo antes de iniciar la prueba.")
        return profile

    def mark_pending(self, command: OwnerBilling) -> None:
        with self.uow_factory() as work:
            self.repository.mark_pending(command.owner)
            work.commit()

    def ensure(self, command: OwnerBilling) -> BillingState:
        with self.uow_factory() as work:
            result = self.repository.lock(command.owner)
            work.commit()
            return result

    def checkout(self, command: Checkout) -> str:
        with self.uow_factory() as uow:
            profile = self.profile(command.owner)
            if not profile.email_verified:
                raise VerificationRequired("Verifica tu correo antes de iniciar la prueba.")
            state = self.repository.lock(command.owner)
            if state_entitled(state, self.clock.now()):
                result = self.gateway.portal(profile.public_id)
            elif (
                state.checkout_url
                and state.checkout_expires_at
                and self.clock.now() < state.checkout_expires_at
            ):
                result = self.gateway.validate_link(state.checkout_url)
            else:
                validate_product(self.gateway.product(), state.trial_used)
                link = self.gateway.checkout(profile.public_id, command.email, not state.trial_used)
                result = self.gateway.validate_link(link.url)
                self.repository.save(
                    replace(state, checkout_url=result, checkout_expires_at=link.expires_at)
                )
            uow.commit()
            return result

    def portal(self, command: OwnerBilling) -> str:
        return self.gateway.portal(self.profile(command.owner).public_id)

    def reconcile(self, command: OwnerBilling) -> BillingState:
        with self.uow_factory() as uow:
            state = self.repository.lock(command.owner)
            profile = self.profile(command.owner)
            result = reconcile_state(
                state,
                self.gateway.customer(profile.public_id),
                str(profile.public_id),
                self.product_id,
                self.clock.now(),
            )
            self.repository.save(result)
            uow.commit()
            return result

    def can_write(self, owner: AccountId) -> bool:
        profile = self.profiles.get(owner)
        if profile is None or not profile.email_verified:
            return False
        if self.development_access:
            return True
        state = self.repository.get(owner)
        return state is not None and state_entitled(state, self.clock.now())


@dataclass(frozen=True)
class WebhookEvent:
    id: str
    kind: str
    external_id: str | None


@dataclass(frozen=True)
class WebhookResult:
    outcome: Literal["processed", "unlinked", "reconciliation_pending"]
    detail: str | None = None


class Receipts(Protocol):
    def received(self, event: WebhookEvent) -> bool:
        """Create if absent; return whether already processed."""
        ...

    def complete(self, event_id: str, now: datetime, public_id: UUID | None = None) -> None: ...


SUPPORTED_EVENTS = frozenset(
    (
        "customer.state_changed",
        "subscription.created",
        "subscription.updated",
        "subscription.canceled",
        "subscription.revoked",
        "subscription.uncanceled",
        "order.refunded",
        "refund.updated",
    )
)


class Webhooks:
    def __init__(self, billing: Billing, receipts: Receipts) -> None:
        self.billing = billing
        self.receipts = receipts

    def process(self, event: WebhookEvent) -> WebhookResult:
        with self.billing.uow_factory() as uow:
            processed = self.receipts.received(event)
            uow.commit()
        if processed:
            return WebhookResult("processed")
        if event.kind not in SUPPORTED_EVENTS:
            with self.billing.uow_factory() as uow:
                self.receipts.complete(event.id, self.billing.clock.now())
                uow.commit()
            return WebhookResult("processed")
        try:
            public_id = UUID(str(event.external_id))
        except (ValueError, TypeError):
            return WebhookResult("unlinked", "Cliente no vinculado; requiere conciliaci\u00f3n")
        owner = self.billing.profiles.owner_for(public_id)
        if owner is None:
            return WebhookResult("unlinked", "Cliente no vinculado; requiere conciliaci\u00f3n")
        with self.billing.uow_factory() as uow:
            self.billing.repository.mark_pending(owner)
            uow.commit()
        try:
            self.billing.reconcile(OwnerBilling(owner))
        except ProviderUnavailable:
            return WebhookResult("reconciliation_pending", "Conciliaci\u00f3n pendiente")
        with self.billing.uow_factory() as uow:
            self.receipts.complete(event.id, self.billing.clock.now(), public_id)
            uow.commit()
        return WebhookResult("processed")
