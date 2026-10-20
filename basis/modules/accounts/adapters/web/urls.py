"""Module-owned HTTP routes; public paths remain stable."""

from django.urls import path

from basis.modules.accounts.adapters.web import views as accounts

urlpatterns = [
    path("accounts/signup/", accounts.signup, name="signup"),
    path("accounts/verify/<str:token>/", accounts.verify_email, name="verify-email"),
    path("accounts/verification/", accounts.resend_verification, name="resend-verification"),
]
