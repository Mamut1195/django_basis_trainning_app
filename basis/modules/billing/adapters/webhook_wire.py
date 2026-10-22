"""Authenticate provider bytes before turning the event into an application command."""

import base64
from collections.abc import Mapping

from standardwebhooks.webhooks import Webhook, WebhookVerificationError

from ..application.service import WebhookEvent, WebhookResult
from .polar import API_VERSION


class InvalidWebhook(ValueError):
    pass


def _event_object(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise InvalidWebhook()
    return {str(key): item for key, item in value.items()}


def decode_event(
    secret: str,
    body: bytes,
    headers: Mapping[str, str],
    *,
    secret_format: str = "standard",
    expected_version: str | None = None,
) -> WebhookEvent:
    try:
        lowered = {key.lower(): value for key, value in headers.items()}
        if secret_format == "legacy":
            secret = base64.b64encode(secret.encode()).decode()
        elif secret_format != "standard":
            raise InvalidWebhook()
        raw: object = Webhook(secret).verify(body, lowered)
        event = _event_object(raw)
        if expected_version is not None and (
            expected_version != API_VERSION
            or lowered.get("webhook-api-version") != expected_version
            or event.get("api_version") != expected_version
        ):
            raise InvalidWebhook()
        data = _event_object(event["data"])
        kind = event["type"]
        if not isinstance(kind, str):
            raise InvalidWebhook()
        customer = _event_object(data.get("customer") or {})
        external = (
            data.get("external_id")
            if kind == "customer.state_changed"
            else customer.get("external_id")
        )
        customer_id = (
            data.get("id")
            if kind == "customer.state_changed"
            else data.get("customer_id") or customer.get("id")
        )
        organization = data.get("organization_id") or customer.get("organization_id")
        if (
            not lowered["webhook-id"]
            or len(lowered["webhook-id"]) > 200
            or len(kind) > 100
            or len(str(customer_id or "")) > 100
            or len(str(organization or "")) > 100
        ):
            raise InvalidWebhook()
        return WebhookEvent(
            lowered["webhook-id"],
            kind,
            str(external) if external is not None else None,
            str(customer_id) if customer_id else None,
            str(organization) if organization else None,
        )
    except (WebhookVerificationError, ValueError, KeyError, TypeError):
        raise InvalidWebhook() from None


def encode_result(result: WebhookResult) -> tuple[int, dict[str, str | bool]]:
    status = {"processed": 200, "queued": 202, "unlinked": 202, "reconciliation_pending": 503}[
        result.outcome
    ]
    if result.outcome in ("queued", "unlinked"):
        return status, {"accepted": True}
    payload: dict[str, str | bool] = (
        {"detail": result.detail} if result.detail is not None else {"ok": True}
    )
    return status, payload
