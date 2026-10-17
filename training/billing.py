"""Polar boundary. Signed events trigger authoritative state reconciliation."""

from datetime import timedelta
from urllib.parse import quote, urlparse

import httpx
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import BillingAccount


class ProviderUnavailable(Exception):
    pass


def polar_request(method, path, **kwargs):
    if not settings.POLAR_ACCESS_TOKEN or not settings.POLAR_PRODUCT_ID:
        raise ProviderUnavailable("Los pagos aún no están configurados.")
    base = "https://sandbox-api.polar.sh" if settings.POLAR_SANDBOX else "https://api.polar.sh"
    try:
        with httpx.Client(timeout=20) as client:
            response = client.request(
                method,
                base + "/v1/" + path,
                headers={"Authorization": "Bearer " + settings.POLAR_ACCESS_TOKEN},
                **kwargs,
            )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        # Never expose provider responses, tokens or personally identifying payloads.
        raise ProviderUnavailable("Polar no está disponible. Inténtalo más tarde.") from None


def safe_provider_url(url):
    parsed = urlparse(url or "")
    if parsed.scheme != "https" or not (
        parsed.hostname == "polar.sh" or (parsed.hostname or "").endswith(".polar.sh")
    ):
        raise ProviderUnavailable("Polar devolvió un enlace inválido.")
    return url


@transaction.atomic
def checkout(owner):
    profile = owner.athlete
    if not profile.email_verified:
        raise ValidationError("Verifica tu correo antes de iniciar la prueba.")
    billing, _ = BillingAccount.objects.get_or_create(owner=owner)
    billing = BillingAccount.objects.select_for_update().get(pk=billing.pk)
    if billing.entitled:
        return portal(owner)
    if (
        billing.checkout_url
        and billing.checkout_expires_at
        and timezone.now() < billing.checkout_expires_at
    ):
        return safe_provider_url(billing.checkout_url)
    # Price/product and native 7-day/card-upfront trial must be configured in Polar.
    # No client-supplied product, price, success URL or customer ID is accepted.
    product = polar_request("GET", "products/" + settings.POLAR_PRODUCT_ID)
    prices = [price for price in product.get("prices", []) if not price.get("is_archived", False)]
    if (
        product.get("is_archived")
        or product.get("recurring_interval") != "month"
        or len(prices) != 1
        or prices[0].get("price_amount") != 500
        or prices[0].get("price_currency") != "usd"
    ):
        raise ProviderUnavailable("El producto debe tener el precio aprobado de USD 5 al mes.")
    if not billing.trial_used and (
        product.get("trial_interval") != "day" or product.get("trial_interval_count") != 7
    ):
        raise ProviderUnavailable("Configura la prueba nativa de siete días en Polar.")
    if prices[0].get("tax_behavior") != "exclusive":
        raise ProviderUnavailable("Configura el precio con impuestos añadidos al importe base.")
    result = polar_request(
        "POST",
        "checkouts/",
        json={
            "products": [settings.POLAR_PRODUCT_ID],
            "external_customer_id": str(profile.public_id),
            "customer_email": owner.email,
            "success_url": settings.PUBLIC_URL + "/billing/?checkout=returned",
            "return_url": settings.PUBLIC_URL + "/billing/",
            "allow_trial": not billing.trial_used,
        },
    )
    billing.checkout_url = safe_provider_url(result.get("url"))
    billing.checkout_expires_at = (
        parse_datetime(result["expires_at"])
        if result.get("expires_at")
        else timezone.now() + timedelta(minutes=30)
    )
    billing.save(update_fields=["checkout_url", "checkout_expires_at"])
    return billing.checkout_url


def portal(owner):
    result = polar_request(
        "POST",
        "customer-sessions/",
        json={
            "external_customer_id": str(owner.athlete.public_id),
            "return_url": settings.PUBLIC_URL + "/billing/",
        },
    )
    return safe_provider_url(result.get("customer_portal_url"))


@transaction.atomic
def reconcile(owner):
    # Holding this row lock across the bounded GET serializes out-of-order events.
    billing, _ = BillingAccount.objects.get_or_create(owner=owner)
    billing = BillingAccount.objects.select_for_update().get(pk=billing.pk)
    state = polar_request(
        "GET", "customers/external/" + quote(str(owner.athlete.public_id), safe="") + "/state"
    )
    if state.get("external_id") != str(owner.athlete.public_id) or not state.get("id"):
        raise ProviderUnavailable("La identidad de Polar no coincide.")
    candidates = [
        s
        for s in state.get("active_subscriptions", [])
        if s.get("product_id") == settings.POLAR_PRODUCT_ID
        and s.get("status") in ("active", "trialing")
    ]
    subscription = max(candidates, key=lambda s: s.get("current_period_end") or "", default={})
    billing.polar_customer_id = state["id"]
    billing.subscription_id = subscription.get("id", "")
    billing.status = subscription.get("status", "inactive")
    billing.period_start = (
        parse_datetime(subscription["current_period_start"])
        if subscription.get("current_period_start")
        else None
    )
    end = (
        subscription.get("trial_end")
        if billing.status == "trialing"
        else subscription.get("current_period_end")
    )
    billing.period_end = parse_datetime(end) if end else None
    billing.cancel_at_period_end = subscription.get("cancel_at_period_end", False)
    billing.trial_used = (
        billing.trial_used or billing.status == "trialing" or bool(subscription.get("trial_start"))
    )
    billing.reconciled_at = timezone.now()
    billing.needs_reconciliation = False
    billing.save()
    return billing
