"""Polar transport and typed response conversion; no commercial policy lives here."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol
from urllib.parse import quote, urlparse
from uuid import UUID

import httpx
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ..domain.records import (
    CheckoutLink,
    CustomerState,
    Price,
    Product,
    ProviderUnavailable,
    Subscription,
)


class Requester(Protocol):
    def __call__(
        self, method: str, path: str, *, json: Mapping[str, object] | None = None
    ) -> object: ...


def safe_provider_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not (
        parsed.hostname == "polar.sh" or (parsed.hostname or "").endswith(".polar.sh")
    ):
        raise ProviderUnavailable("Polar devolvi\u00f3 un enlace inv\u00e1lido.")
    return url


def request(
    method: str,
    path: str,
    *,
    token: str,
    product_id: str,
    sandbox: bool,
    json: Mapping[str, object] | None = None,
) -> object:
    if not token or not product_id:
        raise ProviderUnavailable("Los pagos a\u00fan no est\u00e1n configurados.")
    base = "https://sandbox-api.polar.sh" if sandbox else "https://api.polar.sh"
    try:
        with httpx.Client(timeout=20) as client:
            response = client.request(
                method,
                base + "/v1/" + path,
                headers={"Authorization": "Bearer " + token},
                json=json,
            )
        response.raise_for_status()
        result: object = response.json()
        return result
    except (httpx.HTTPError, ValueError):
        raise ProviderUnavailable("Polar no est\u00e1 disponible. Int\u00e9ntalo m\u00e1s tarde.") from None


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProviderUnavailable("Polar devolvi\u00f3 una respuesta inv\u00e1lida.")
    return {str(key): item for key, item in value.items()}


def _rows(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        raise ProviderUnavailable("Polar devolvi\u00f3 una respuesta inv\u00e1lida.")
    return tuple(_mapping(item) for item in value)


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _date(value: object) -> datetime | None:
    return parse_datetime(value) if isinstance(value, str) and value else None


def _subscription_date(value: object) -> tuple[datetime | None, bool]:
    try:
        return _date(value), False
    except ValueError:
        # Legacy only parsed the chosen subscription. Retain invalidity until selection.
        return None, True


def _subscription(row: Mapping[str, object]) -> Subscription:
    start, invalid_start = _subscription_date(row.get("current_period_start"))
    end, invalid_end = _subscription_date(row.get("current_period_end"))
    trial_end, invalid_trial_end = _subscription_date(row.get("trial_end"))
    return Subscription(
        id=_text(row.get("id")),
        product_id=_text(row.get("product_id")),
        status=_text(row.get("status")),
        period_start=start,
        period_end=end,
        period_end_key=_text(row.get("current_period_end")),
        trial_end=trial_end,
        trial_started=bool(row.get("trial_start")),
        cancel_at_period_end=bool(row.get("cancel_at_period_end", False)),
        invalid_period_start=invalid_start,
        invalid_period_end=invalid_end,
        invalid_trial_end=invalid_trial_end,
    )


def _number(value: object) -> Decimal | None:
    # Strings must not turn an invalid provider price/trial count into an accepted one.
    return Decimal(str(value)) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class PolarGateway:
    def __init__(self, requester: Requester, product_id: str, public_url: str) -> None:
        self.requester, self.product_id, self.public_url = requester, product_id, public_url

    def validate_link(self, url: str) -> str:
        return safe_provider_url(url)

    def product(self) -> Product:
        data = _mapping(self.requester("GET", "products/" + self.product_id))
        return Product(
            archived=bool(data.get("is_archived")),
            recurring_interval=_text(data.get("recurring_interval")),
            prices=tuple(
                Price(
                    archived=bool(row.get("is_archived", False)),
                    amount_cents=_number(row.get("price_amount")),
                    currency=_text(row.get("price_currency")),
                    tax_behavior=_text(row.get("tax_behavior")),
                )
                for row in _rows(data.get("prices", []))
            ),
            trial_interval=_text(data.get("trial_interval")),
            trial_days=_number(data.get("trial_interval_count")),
        )

    def checkout(self, public_id: UUID, email: str, allow_trial: bool) -> CheckoutLink:
        data = _mapping(self.requester("POST", "checkouts/", json={
            "products": [self.product_id],
            "external_customer_id": str(public_id),
            "customer_email": email,
            "success_url": self.public_url + "/billing/?checkout=returned",
            "return_url": self.public_url + "/billing/",
            "allow_trial": allow_trial,
        }))
        expires = data.get("expires_at")
        return CheckoutLink(
            safe_provider_url(_text(data.get("url"))),
            _date(expires) if expires else timezone.now() + timedelta(minutes=30),
        )

    def portal(self, public_id: UUID) -> str:
        data = _mapping(self.requester("POST", "customer-sessions/", json={
            "external_customer_id": str(public_id),
            "return_url": self.public_url + "/billing/",
        }))
        return safe_provider_url(_text(data.get("customer_portal_url")))

    def customer(self, public_id: UUID) -> CustomerState:
        data = _mapping(self.requester(
            "GET", "customers/external/" + quote(str(public_id), safe="") + "/state"
        ))
        return CustomerState(
            id=_text(data.get("id")),
            external_id=_text(data.get("external_id")),
            subscriptions=tuple(
                _subscription(row)
                for row in _rows(data.get("active_subscriptions", []))
            ),
        )
