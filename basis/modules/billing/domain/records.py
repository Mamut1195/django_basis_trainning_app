"""Commercial policy and immutable provider-independent billing values."""

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from basis.shared.identifiers import AccountId


class ProviderUnavailable(Exception):
    pass


class VerificationRequired(Exception):
    pass


@dataclass(frozen=True)
class BillingState:
    owner: AccountId
    customer_id: str | None = None
    subscription_id: str = ""
    status: str = "inactive"
    period_start: datetime | None = None
    period_end: datetime | None = None
    cancel_at_period_end: bool = False
    trial_used: bool = False
    reconciled_at: datetime | None = None
    needs_reconciliation: bool = False
    checkout_url: str = ""
    checkout_expires_at: datetime | None = None


@dataclass(frozen=True)
class Price:
    archived: bool
    amount_cents: Decimal | None
    currency: str
    tax_behavior: str


@dataclass(frozen=True)
class Product:
    archived: bool
    recurring_interval: str
    prices: tuple[Price, ...]
    trial_interval: str
    trial_days: Decimal | None


@dataclass(frozen=True)
class Subscription:
    id: str
    product_id: str
    status: str
    period_start: datetime | None
    period_end: datetime | None
    period_end_key: str
    trial_end: datetime | None
    trial_started: bool
    cancel_at_period_end: bool
    invalid_period_start: bool = False
    invalid_period_end: bool = False
    invalid_trial_end: bool = False


@dataclass(frozen=True)
class CustomerState:
    id: str
    external_id: str
    subscriptions: tuple[Subscription, ...]


@dataclass(frozen=True)
class CheckoutLink:
    url: str
    expires_at: datetime | None


def entitled(
    status: str,
    period_start: datetime | None,
    period_end: datetime | None,
    needs_reconciliation: bool,
    now: datetime,
) -> bool:
    return (
        status in ("active", "trialing")
        and period_start is not None
        and period_end is not None
        and period_start <= now < period_end
        and not needs_reconciliation
    )


def state_entitled(state: BillingState, now: datetime) -> bool:
    return entitled(
        state.status, state.period_start, state.period_end, state.needs_reconciliation, now
    )


def status_label(status: str) -> str:
    return {
        "active": "Activa",
        "trialing": "Prueba activa",
        "inactive": "Sin acceso activo",
        "past_due": "Pago pendiente",
        "canceled": "Cancelada",
    }.get(status, "Pendiente de comprobar")


def validate_product(product: Product, trial_used: bool) -> None:
    prices = tuple(price for price in product.prices if not price.archived)
    if (
        product.archived
        or product.recurring_interval != "month"
        or len(prices) != 1
        or prices[0].amount_cents != Decimal(500)
        or prices[0].currency != "usd"
    ):
        raise ProviderUnavailable("El producto debe tener el precio aprobado de USD 5 al mes.")
    if not trial_used and (product.trial_interval != "day" or product.trial_days != Decimal(7)):
        raise ProviderUnavailable("Configura la prueba nativa de siete d\u00edas en Polar.")
    if prices[0].tax_behavior != "exclusive":
        raise ProviderUnavailable(
            "Configura el precio con impuestos a\u00f1adidos al importe base."
        )


def reconcile_state(
    previous: BillingState,
    customer: CustomerState,
    external_id: str,
    product_id: str,
    now: datetime,
) -> BillingState:
    if customer.external_id != external_id or not customer.id:
        raise ProviderUnavailable("La identidad de Polar no coincide.")
    candidates = tuple(
        subscription
        for subscription in customer.subscriptions
        if subscription.product_id == product_id and subscription.status in ("active", "trialing")
    )
    subscription = max(candidates, key=lambda value: value.period_end_key, default=None)
    if subscription and (
        subscription.invalid_period_start
        or (
            subscription.invalid_trial_end
            if subscription.status == "trialing"
            else subscription.invalid_period_end
        )
    ):
        # Provider adapters defer invalid-calendar errors until the chosen subscription.
        # Foreign or older subscriptions must not invalidate authoritative state.
        raise ValueError("Invalid selected subscription date")
    return replace(
        previous,
        customer_id=customer.id,
        subscription_id=subscription.id if subscription else "",
        status=subscription.status if subscription else "inactive",
        period_start=subscription.period_start if subscription else None,
        period_end=(
            subscription.trial_end if subscription.status == "trialing" else subscription.period_end
        )
        if subscription
        else None,
        cancel_at_period_end=subscription.cancel_at_period_end if subscription else False,
        trial_used=previous.trial_used
        or bool(subscription and (subscription.status == "trialing" or subscription.trial_started)),
        reconciled_at=now,
        needs_reconciliation=False,
    )
