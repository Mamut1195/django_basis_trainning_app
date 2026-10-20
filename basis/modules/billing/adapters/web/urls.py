"""Module-owned HTTP routes; public paths remain stable."""

from django.urls import path

from basis.modules.billing.adapters.web import views as billing

urlpatterns = [
    path("billing/", billing.billing_page, name="billing"),
    path("billing/<str:action>/", billing.billing_action, name="billing-action"),
    path("webhooks/polar/", billing.polar_webhook, name="polar-webhook"),
]
