"""Polar transport and typed response conversion; no commercial policy lives here."""

from collections.abc import Mapping
from datetime import datetime
from datetime import timezone as datetime_timezone
from decimal import Decimal
from typing import Protocol
from urllib.parse import quote, urlparse
from uuid import UUID

import httpx
from django.utils.dateparse import parse_datetime

from ..domain.records import (
    CheckoutLink,
    CustomerState,
    Price,
    Product,
    ProviderUnavailable,
    Subscription,
)

API_VERSION = "2026-10"
REQUEST_TIMEOUT = httpx.Timeout(4.0, connect=2.0, pool=1.0)


class Requester(Protocol):
    def __call__(
        self, method: str, path: str, *, json: Mapping[str, object] | None = None
    ) -> object: ...


def safe_provider_url(url: str, sandbox: bool | None = None) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        raise ProviderUnavailable("Polar devolvió un enlace inválido.") from None
    hosts = {"sandbox.polar.sh"} if sandbox is True else {"polar.sh", "checkout.polar.sh"}
    if sandbox is None:
        hosts.add("sandbox.polar.sh")
    try:
        valid = parsed.port in (None, 443)
    except ValueError:
        valid = False
    if (
        parsed.scheme != "https"
        or parsed.hostname not in hosts
        or parsed.username is not None
        or parsed.password is not None
        or not valid
        or any(ord(c) < 32 for c in url)
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
        with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=False) as client:
            response = client.request(
                method,
                base + "/v1/" + path,
                headers={"Authorization": "Bearer " + token, "Polar-Version": API_VERSION},
                json=json,
            )
        response.raise_for_status()
        if response.headers.get("Polar-Version") != API_VERSION:
            raise ProviderUnavailable("Polar devolvió una versión incompatible.")
        result: object = response.json()
        return result
    except (httpx.HTTPError, ValueError):
        raise ProviderUnavailable(
            "Polar no est\u00e1 disponible. Int\u00e9ntalo m\u00e1s tarde."
        ) from None


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
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid date")
    result = parse_datetime(value)
    if result is None or result.utcoffset() is None:
        raise ValueError("Invalid date")
    return result.astimezone(datetime_timezone.utc)


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
    ends_at, invalid_ends_at = _subscription_date(row.get("ends_at"))
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
        ends_at=ends_at,
        invalid_ends_at=invalid_ends_at,
    )


def _number(value: object) -> Decimal | None:
    # Strings must not turn an invalid provider price/trial count into an accepted one.
    return (
        Decimal(str(value))
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )


def _price(row: Mapping[str, object]) -> Price:
    # Legacy recurring prices can repeat interval information. A conflicting
    # legacy price must not bypass the product-level monthly contract.
    if not row.get("is_archived", False) and (
        ("recurring_interval" in row and row["recurring_interval"] != "month")
        or (
            "recurring_interval_count" in row
            and (
                row["recurring_interval_count"] != 1
                or isinstance(row["recurring_interval_count"], bool)
            )
        )
    ):
        raise ProviderUnavailable("El precio recurrente no coincide con la mensualidad aprobada.")
    return Price(
        archived=bool(row.get("is_archived", False)),
        amount_cents=_number(row.get("price_amount")),
        currency=_text(row.get("price_currency")),
        tax_behavior=_text(row.get("tax_behavior")),
        id=_text(row.get("id")),
        amount_type=_text(row.get("amount_type")),
    )


class PolarGateway:
    def __init__(
        self,
        requester: Requester,
        product_id: str,
        public_url: str,
        sandbox: bool | None = None,
        organization_id: str = "",
    ) -> None:
        self.requester, self.product_id, self.public_url = requester, product_id, public_url
        self.sandbox, self.organization_id = sandbox, organization_id

    def _identity(self, data: Mapping[str, object]) -> None:
        if (
            not self.organization_id
            or data.get("organization_id") != self.organization_id
            or not _text(data.get("id"))
            or len(_text(data.get("id"))) > 100
        ):
            raise ProviderUnavailable("La organización de Polar no coincide con la configuración.")

    def _configured(self) -> None:
        if self.sandbox is not None and not self.organization_id:
            raise ProviderUnavailable("Configura la organización de pagos antes de continuar.")

    def _public_origin(self) -> None:
        try:
            origin = urlparse(self.public_url)
            port = origin.port
        except ValueError:
            raise ProviderUnavailable("Configura un PUBLIC_URL seguro.") from None
        if (
            origin.scheme not in ("https", "http")
            or not origin.hostname
            or origin.username is not None
            or origin.password is not None
            or port == 0
            or any(ord(c) < 32 for c in self.public_url)
            or origin.query
            or origin.fragment
            or origin.path not in ("", "/")
            or (
                origin.scheme == "http" and origin.hostname not in ("localhost", "127.0.0.1", "::1")
            )
        ):
            raise ProviderUnavailable("Configura un PUBLIC_URL seguro.")

    def validate_link(self, url: str) -> str:
        return safe_provider_url(url, self.sandbox)

    def product(self) -> Product:
        self._configured()
        data = _mapping(self.requester("GET", "products/" + self.product_id))
        self._identity(data)
        if data.get("id") != self.product_id:
            raise ProviderUnavailable("El producto de Polar no coincide.")
        count = data.get("recurring_interval_count")
        return Product(
            archived=bool(data.get("is_archived")),
            recurring_interval=_text(data.get("recurring_interval")),
            prices=tuple(_price(row) for row in _rows(data.get("prices", []))),
            trial_interval=_text(data.get("trial_interval")),
            trial_days=_number(data.get("trial_interval_count")),
            recurring_interval_count=count
            if isinstance(count, int) and not isinstance(count, bool)
            else None,
        )

    def checkout(
        self, public_id: UUID, email: str, allow_trial: bool, attempt: UUID | None = None
    ) -> CheckoutLink:
        self._configured()
        self._public_origin()
        data = _mapping(
            self.requester(
                "POST",
                "checkouts/",
                json={
                    "products": [self.product_id],
                    "external_customer_id": str(public_id),
                    "customer_email": email,
                    "success_url": self.public_url + "/billing/?checkout=returned",
                    "return_url": self.public_url + "/billing/",
                    "allow_trial": allow_trial,
                    "allow_discount_codes": False,
                    "metadata": {"basis_checkout_attempt": str(attempt)} if attempt else {},
                },
            )
        )
        expires = data.get("expires_at")
        try:
            cutoff = _date(expires)
        except ValueError:
            raise ProviderUnavailable("Polar devolvió una caducidad inválida.") from None
        if cutoff is None:
            raise ProviderUnavailable("Polar devolvió una caducidad inválida.")
        return CheckoutLink(self.validate_link(_text(data.get("url"))), cutoff)

    def portal(self, public_id: UUID) -> str:
        self._configured()
        self._public_origin()
        data = _mapping(
            self.requester(
                "POST",
                "customer-sessions/",
                json={
                    "external_customer_id": str(public_id),
                    "return_url": self.public_url + "/billing/",
                },
            )
        )
        return self.validate_link(_text(data.get("customer_portal_url")))

    def customer(self, public_id: UUID) -> CustomerState:
        self._configured()
        data = _mapping(
            self.requester("GET", "customers/external/" + quote(str(public_id), safe="") + "/state")
        )
        self._identity(data)
        return CustomerState(
            id=_text(data.get("id")),
            external_id=_text(data.get("external_id")),
            subscriptions=tuple(
                _subscription(row) for row in _rows(data.get("active_subscriptions", []))
            ),
        )
