"""Authenticate provider bytes before turning the event into an application command."""

from collections.abc import Mapping

from standardwebhooks.webhooks import Webhook, WebhookVerificationError

from ..application.service import WebhookEvent, WebhookResult


class InvalidWebhook(ValueError):
    pass


def _event_object(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise InvalidWebhook()
    return {str(key): item for key, item in value.items()}


def decode_event(secret: str, body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
    try:
        lowered = {key.lower(): value for key, value in headers.items()}
        raw: object = Webhook(secret).verify(body, lowered)
        event = _event_object(raw)
        data = _event_object(event["data"])
        kind = event["type"]
        if not isinstance(kind, str):
            raise InvalidWebhook()
        external = (
            data.get("external_id") if kind == "customer.state_changed"
            else _event_object(data.get("customer") or {}).get("external_id")
        )
        return WebhookEvent(
            lowered["webhook-id"], kind, str(external) if external is not None else None
        )
    except (WebhookVerificationError, ValueError, KeyError, TypeError):
        raise InvalidWebhook() from None


def encode_result(result: WebhookResult) -> tuple[int, dict[str, str | bool]]:
    status = {"processed": 200, "unlinked": 422, "reconciliation_pending": 503}[result.outcome]
    payload: dict[str, str | bool] = (
        {"detail": result.detail} if result.detail is not None else {"ok": True}
    )
    return status, payload
