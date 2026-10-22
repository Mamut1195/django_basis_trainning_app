"""Commercial policy and immutable provider-independent billing values."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

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
    checkout_context: str = ""
    checkout_attempt: UUID | None = None
    checkout_created_at: datetime | None = None


@dataclass(frozen=True)
class Price:
    archived: bool
    amount_cents: Decimal | None
    currency: str
    tax_behavior: str
    id: str = ""
    amount_type: str = "fixed"


@dataclass(frozen=True)
class Product:
    archived: bool
    recurring_interval: str
    prices: tuple[Price, ...]
    trial_interval: str
    trial_days: Decimal | None
    recurring_interval_count: int | None = None


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
    ends_at: datetime | None = None
    invalid_ends_at: bool = False


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
        and period_start.utcoffset() is not None
        and period_end.utcoffset() is not None
        and now.utcoffset() is not None
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
        or product.recurring_interval_count != 1
        or len(prices) != 1
        or prices[0].amount_cents != Decimal(500)
        or prices[0].currency != "usd"
        or prices[0].amount_type != "fixed"
        or not prices[0].id
        or len(prices[0].id) > 100
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
    if (
        customer.external_id != external_id
        or not customer.id
        or (previous.customer_id is not None and previous.customer_id != customer.id)
    ):
        raise ProviderUnavailable("La identidad de Polar no coincide.")
    relevant = tuple(
        subscription
        for subscription in customer.subscriptions
        if subscription.product_id == product_id and subscription.status in ("active", "trialing")
    )
    eligible: list[Subscription] = []

    def effective_end(value: Subscription) -> datetime | None:
        end = value.trial_end if value.status == "trialing" else value.period_end
        return min(end, value.ends_at) if end is not None and value.ends_at is not None else end

    for candidate in relevant:
        end = candidate.trial_end if candidate.status == "trialing" else candidate.period_end
        if (
            candidate.invalid_period_start
            or candidate.invalid_ends_at
            or (
                candidate.invalid_trial_end
                if candidate.status == "trialing"
                else candidate.invalid_period_end
            )
            or (candidate.period_start is not None and candidate.period_start.utcoffset() is None)
            or (end is not None and end.utcoffset() is None)
            or (candidate.ends_at is not None and candidate.ends_at.utcoffset() is None)
        ):
            raise ProviderUnavailable("Polar devolvió un período inválido; conciliación pendiente.")
        if entitled(candidate.status, candidate.period_start, effective_end(candidate), False, now):
            if not candidate.id or len(candidate.id) > 100:
                raise ProviderUnavailable("Polar devolvió una suscripción inválida.")
            eligible.append(candidate)

    def cutoff(value: Subscription) -> tuple[datetime, str]:
        end = effective_end(value)
        assert end is not None
        return end.astimezone(timezone.utc), value.id

    subscription = max(eligible, key=cutoff, default=None)
    result = replace(
        previous,
        customer_id=customer.id,
        subscription_id=subscription.id if subscription else "",
        status=subscription.status if subscription else "inactive",
        period_start=(
            subscription.period_start.astimezone(timezone.utc)
            if subscription and subscription.period_start
            else None
        ),
        period_end=(cutoff(subscription)[0]) if subscription else None,
        cancel_at_period_end=subscription.cancel_at_period_end if subscription else False,
        trial_used=previous.trial_used
        or any(value.status == "trialing" or value.trial_started for value in relevant),
        reconciled_at=now,
        needs_reconciliation=False,
    )
    changed = any(
        getattr(previous, field) != getattr(result, field)
        for field in (
            "customer_id",
            "subscription_id",
            "status",
            "period_start",
            "period_end",
            "trial_used",
        )
    )
    # An ambiguous POST needs BOTH a fresh authoritative read and the same finite
    # maximum checkout-cache window. An ordinary unchanged poll keeps valid links.
    ambiguity_elapsed = bool(
        previous.checkout_attempt
        and not previous.checkout_url
        and previous.checkout_created_at
        and now >= previous.checkout_created_at + timedelta(minutes=30)
    )
    if (
        previous.checkout_attempt
        and not previous.checkout_url
        and not ambiguity_elapsed
        and not state_entitled(result, now)
    ):
        return result
    if changed or ambiguity_elapsed:
        return replace(
            result,
            checkout_url="",
            checkout_expires_at=None,
            checkout_context="",
            checkout_attempt=None,
            checkout_created_at=None,
        )
    return result
