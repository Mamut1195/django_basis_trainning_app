"""Transactional billing commands, access policy and durable webhook phases."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Callable, Literal, Protocol
from uuid import UUID, uuid4

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
    def owner_for_customer(self, customer_id: str) -> AccountId | None: ...


class Gateway(Protocol):
    def product(self) -> Product: ...
    def checkout(
        self, public_id: UUID, email: str, allow_trial: bool, attempt: UUID | None = None
    ) -> CheckoutLink: ...
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
        checkout_scope: str = "",
        organization_id: str = "",
    ) -> None:
        self.repository = repository
        self.profiles = profiles
        self.gateway = gateway
        self.uow_factory = uow_factory
        self.clock = clock
        self.product_id = product_id
        self.development_access = development_access
        self.checkout_scope = checkout_scope
        self.organization_id = organization_id

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
        # Commit the opaque attempt BEFORE a potentially ambiguous POST. A timeout
        # must not roll the intent back and silently permit another paid request.
        with self.uow_factory() as uow:
            state = self.repository.lock(command.owner)
            profile = self.profile(command.owner)
            if not profile.email_verified:
                raise VerificationRequired("Verifica tu correo antes de iniciar la prueba.")
            if state_entitled(state, self.clock.now()):
                result = self.gateway.portal(profile.public_id)
                uow.commit()
                return result
            if state.needs_reconciliation:
                raise ProviderUnavailable(
                    "La suscripción requiere conciliación antes de continuar."
                )
            product = self.gateway.product()
            validate_product(product, state.trial_used)
            context = sha256(
                repr(
                    (
                        str(profile.public_id),
                        self.product_id,
                        self.checkout_scope,
                        product,
                        state.trial_used,
                        state.subscription_id,
                        state.status,
                        state.period_start,
                        state.period_end,
                    )
                ).encode()
            ).hexdigest()
            now = self.clock.now()
            current = (
                state.checkout_context == context
                and state.checkout_created_at is not None
                and state.checkout_created_at
                <= now
                < state.checkout_created_at + timedelta(minutes=30)
                and state.checkout_expires_at is not None
                and now < state.checkout_expires_at
            )
            if current and state.checkout_url:
                result = self.gateway.validate_link(state.checkout_url)
                uow.commit()
                return result
            if state.checkout_attempt is not None and not state.checkout_url:
                raise ProviderUnavailable(
                    "El intento de pago sigue pendiente. No se repetirá automáticamente."
                )
            attempt = uuid4()
            self.repository.save(
                replace(
                    state,
                    checkout_url="",
                    checkout_context=context,
                    checkout_attempt=attempt,
                    checkout_created_at=now,
                    checkout_expires_at=now + timedelta(minutes=30),
                )
            )
            uow.commit()

        with self.uow_factory() as uow:
            current_state = self.repository.lock(command.owner)
            profile = self.profile(command.owner)
            if (
                not profile.email_verified
                or current_state.checkout_attempt != attempt
                or current_state.needs_reconciliation
                or current_state.trial_used != state.trial_used
            ):
                raise ProviderUnavailable(
                    "El estado cambió; comprueba la suscripción antes de continuar."
                )
            try:
                link = self.gateway.checkout(
                    profile.public_id, command.email, not current_state.trial_used, attempt
                )
                result = self.gateway.validate_link(link.url)
                expires = (
                    min(link.expires_at, now + timedelta(minutes=30)) if link.expires_at else now
                )
                if expires <= self.clock.now():
                    raise ProviderUnavailable("Polar devolvió un enlace caducado.")
                self.repository.save(
                    replace(current_state, checkout_url=result, checkout_expires_at=expires)
                )
            except ProviderUnavailable:
                self.repository.save(replace(current_state, needs_reconciliation=True))
                result = ""
            uow.commit()
        if not result:
            raise ProviderUnavailable(
                "Intento de pago pendiente; actualiza el estado antes de volver a intentarlo."
            )
        return result

    def portal(self, command: OwnerBilling) -> str:
        with self.uow_factory() as uow:
            self.repository.lock(command.owner)
            profile = self.profile(command.owner)
            if not profile.email_verified:
                raise VerificationRequired("Verifica tu correo antes de abrir el portal.")
            result = self.gateway.portal(profile.public_id)
            uow.commit()
            return result

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
    customer_id: str | None = None
    organization_id: str | None = None


@dataclass(frozen=True)
class WebhookResult:
    outcome: Literal["processed", "queued", "unlinked", "reconciliation_pending"]
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
        "subscription.active",
        "subscription.past_due",
        "subscription.cycled",
        "subscription.paused",
        "subscription.resumed",
        "subscription.canceled",
        "subscription.revoked",
        "subscription.uncanceled",
        "order.refunded",
        "refund.updated",
        "refund.created",
        "order.paid",
        "order.updated",
    )
)


class Webhooks:
    def __init__(self, billing: Billing, receipts: Receipts) -> None:
        self.billing = billing
        self.receipts = receipts

    def resolve_owner(self, event: WebhookEvent) -> AccountId | None:
        if event.organization_id and event.organization_id != self.billing.organization_id:
            return None
        linked = (
            self.billing.repository.owner_for_customer(event.customer_id)
            if event.customer_id
            else None
        )
        if event.external_id is None:
            return linked
        try:
            public_id = UUID(event.external_id)
        except ValueError:
            return None
        owner = self.billing.profiles.owner_for(public_id)
        if owner is None or (linked is not None and linked != owner):
            return None
        state = self.billing.repository.get(owner)
        if (
            event.customer_id
            and state
            and state.customer_id
            and state.customer_id != event.customer_id
        ):
            return None
        return owner

    def enqueue(self, event: WebhookEvent) -> WebhookResult:
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
        owner = self.resolve_owner(event)
        if owner is None:
            return WebhookResult("unlinked", "Evento pendiente de conciliación.")
        with self.billing.uow_factory() as uow:
            self.billing.repository.mark_pending(owner)
            uow.commit()
        return WebhookResult("queued")

    def process(self, event: WebhookEvent) -> WebhookResult:
        prepared = self.enqueue(event)
        if prepared.outcome != "queued":
            return prepared
        owner = self.resolve_owner(event)
        assert owner is not None
        try:
            self.billing.reconcile(OwnerBilling(owner))
        except ProviderUnavailable:
            return WebhookResult("reconciliation_pending", "Conciliaci\u00f3n pendiente")
        with self.billing.uow_factory() as uow:
            self.receipts.complete(
                event.id, self.billing.clock.now(), self.billing.profile(owner).public_id
            )
            uow.commit()
        return WebhookResult("processed")
