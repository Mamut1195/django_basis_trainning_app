from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from basis.adapters.web import presentation
from basis.adapters.web.framework import owner
from basis.bootstrap.billing import webhooks
from basis.modules.billing.adapters import actions as polar
from basis.modules.billing.adapters.record_actions import account_row
from basis.modules.billing.adapters.webhook_wire import InvalidWebhook, decode_event, encode_result


@login_required
def billing_page(request: HttpRequest) -> HttpResponse:
    account = account_row(owner(request).pk)
    return render(
        request,
        "billing/subscription.html",
        {
            "billing": account,
            "usage": presentation.latest_usage(owner(request).pk),
            "payments_configured": bool(
                settings.POLAR_ACCESS_TOKEN
                and settings.POLAR_PRODUCT_ID
                and settings.POLAR_ORGANIZATION_ID
            ),
        },
    )


@login_required
@require_POST
def billing_action(request: HttpRequest, action: str) -> HttpResponse:
    try:
        if action == "checkout":
            return redirect(polar.checkout(owner(request)))
        if action == "portal":
            return redirect(polar.portal(owner(request)))
        if action == "refresh":
            polar.reconcile(owner(request))
        else:
            return HttpResponse(status=404)
    except (polar.ProviderUnavailable, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing")


@csrf_exempt
@require_POST
def polar_webhook(request: HttpRequest) -> HttpResponse:
    if not settings.POLAR_WEBHOOK_SECRET:
        return JsonResponse({"detail": "Webhook no configurado"}, status=503)
    try:
        event = decode_event(
            settings.POLAR_WEBHOOK_SECRET,
            request.body,
            request.headers,
            secret_format=settings.POLAR_WEBHOOK_SECRET_FORMAT,
            expected_version=settings.POLAR_WEBHOOK_API_VERSION,
        )
    except InvalidWebhook:
        return JsonResponse({"detail": "Firma o evento inv\u00e1lido"}, status=400)
    result = webhooks(polar.polar_request).enqueue(event)
    status, payload = encode_result(result)
    return JsonResponse(payload, status=status)
