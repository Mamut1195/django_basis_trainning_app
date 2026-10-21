"""BASIS-025: real endpoints, failures, lifecycle and PostgreSQL serialization."""

from __future__ import annotations

import io
import logging
import re
import socketserver
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from email import policy
from email.parser import BytesParser
from typing import Iterator, cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.views import INTERNAL_RESET_SESSION_TOKEN, PasswordResetConfirmView
from django.core import mail, signing
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponse
from django.test import (
    Client,
    RequestFactory,
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
    skipUnlessDBFeature,
)
from django.urls import resolve
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from basis.adapters.web.operational_logging import SafeHTTPFilter
from basis.modules.accounts.adapters.django import DjangoAccounts
from basis.modules.accounts.adapters.models import EmailVerification, RateWindow
from basis.modules.accounts.adapters.recovery import BasisSetPasswordForm
from basis.modules.accounts.adapters.web.client_address import client_address
from basis.modules.accounts.application.identity import RegisterAccount
from basis.modules.accounts.domain.identity import Account, VerificationClaim
from basis.modules.athletes.adapters.models import AthleteSettings
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.billing.adapters.models import BillingAccount


def signup_data(email: str = "alias-a@example.test") -> dict[str, str]:
    return {
        "email": email,
        "name": "Synthetic adult",
        "adult": "on",
        "password1": "Synthetic-Strong-2026!",
        "password2": "Synthetic-Strong-2026!",
    }


def verification_path() -> str:
    match = re.search(r"https?://[^/]+([^\s]+)", str(mail.outbox[-1].body))
    assert match is not None
    return match.group(1)


def public_body(content: bytes) -> bytes:
    # Django masks the same CSRF secret differently on every response.
    return re.sub(rb'(name="csrf-token" content=")[^"]+', rb"\1[CSRF]", content)


def reset_view_class(path: str) -> type[PasswordResetConfirmView]:
    return cast(type[PasswordResetConfirmView], getattr(resolve(path).func, "view_class"))


class AccountAcceptanceTests(TestCase):
    def enroll(self, email: str = "alias-a@example.test") -> str:
        response = self.client.post("/accounts/signup/", signup_data(email))
        self.assertEqual(response.status_code, 200)
        return verification_path()

    def test_verified_then_disabled_cannot_replay_or_resend(self) -> None:
        path = self.enroll()
        self.assertEqual(self.client.post(path).status_code, 302)
        user = get_user_model().objects.get()
        user.is_active = False
        user.save(update_fields=["is_active"])
        before = len(mail.outbox)
        self.assertEqual(self.client.post(path).status_code, 400)
        self.assertEqual(
            self.client.post("/accounts/verification/", {"email": user.email}).status_code, 200
        )
        self.assertEqual(len(mail.outbox), before)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(user.emailverification.state, EmailVerification.State.DISABLED)

    def test_disabling_pending_account_revokes_first_link(self) -> None:
        path = self.enroll()
        user = get_user_model().objects.get()
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assertEqual(self.client.post(path).status_code, 400)
        self.assertFalse(Athlete.objects.get().email_verified)

    def test_administratively_created_inactive_account_is_not_an_enrollment(self) -> None:
        user = get_user_model().objects.create_user(
            username="disabled@example.test", email="disabled@example.test", is_active=False
        )
        Athlete.objects.create(
            account=user,
            nombre="Disabled synthetic",
            email=user.email,
            fecha_inicio=timezone.localdate(),
        )
        token = signing.dumps({"uid": user.pk, "email": user.email}, salt="basis-verify")
        self.assertEqual(self.client.post(f"/accounts/verify/{token}/").status_code, 400)
        self.client.post("/accounts/verification/", {"email": user.email})
        self.assertEqual(len(mail.outbox), 0)

    def test_pending_login_has_no_authenticated_session(self) -> None:
        self.enroll()
        self.assertFalse(
            self.client.login(username="alias-a@example.test", password=signup_data()["password1"])
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_queryset_deactivation_of_verified_account_cannot_reactivate(self) -> None:
        path = self.enroll()
        self.client.post(path)
        get_user_model().objects.update(is_active=False)
        self.assertEqual(self.client.post(path).status_code, 400)
        self.assertFalse(get_user_model().objects.get().is_active)

    def test_expired_tampered_and_consumed_verification(self) -> None:
        path = self.enroll()
        with patch(
            "django.core.signing.time.time", return_value=timezone.now().timestamp() + 86401
        ):
            self.assertEqual(self.client.post(path).status_code, 400)
        self.assertEqual(self.client.post(path[:-1] + "tampered/").status_code, 400)
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertFalse(get_user_model().objects.get().is_active)
        self.assertEqual(self.client.post(path).status_code, 302)
        self.assertEqual(self.client.post(path).status_code, 400)

    def test_adult_password_and_legacy_collision_do_not_create_or_link(self) -> None:
        for update in (
            {"adult": ""},
            {"password2": "different"},
            {"password1": "short", "password2": "short"},
        ):
            response = self.client.post("/accounts/signup/", {**signup_data(), **update})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(get_user_model().objects.exists())
        legacy = Athlete.objects.create(
            nombre="Synthetic legacy",
            email="alias-a@example.test",
            fecha_inicio=timezone.localdate(),
        )
        self.client.post("/accounts/signup/", signup_data())
        legacy.refresh_from_db()
        self.assertIsNone(legacy.account_id)
        self.assertFalse(legacy.email_verified)
        self.assertFalse(get_user_model().objects.exists())

    def test_delivery_failure_and_duplicate_have_equivalent_recoverable_signup(self) -> None:
        with patch(
            "basis.modules.accounts.adapters.django.send_mail",
            side_effect=OSError("PRIVATE_DIAGNOSTIC"),
        ):
            failed = self.client.post("/accounts/signup/", signup_data())
        self.assertEqual(failed.status_code, 200)
        for model in (
            get_user_model(),
            Athlete,
            AthleteSettings,
            BillingAccount,
            EmailVerification,
        ):
            self.assertEqual(model.objects.count(), 0)
        successful = self.client.post("/accounts/signup/", signup_data())
        duplicate = self.client.post("/accounts/signup/", signup_data())
        self.assertEqual(public_body(failed.content), public_body(successful.content))
        self.assertEqual(public_body(duplicate.content), public_body(successful.content))
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertNotContains(failed, "PRIVATE_DIAGNOSTIC")

    def test_resend_transport_failure_does_not_enumerate(self) -> None:
        self.enroll()
        with patch(
            "basis.modules.accounts.adapters.django.send_mail",
            side_effect=OSError("PRIVATE_DIAGNOSTIC"),
        ):
            known = self.client.post("/accounts/verification/", {"email": "alias-a@example.test"})
            unknown = self.client.post("/accounts/verification/", {"email": "missing@example.test"})
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(public_body(known.content), public_body(unknown.content))
        self.assertEqual(known.status_code, 200)

    def test_reset_failure_logs_only_countable_safe_event(self) -> None:
        path = self.enroll()
        self.client.post(path)
        stream = io.StringIO()
        logger = logging.getLogger("django.contrib.auth")
        handler = logger.handlers[0]
        self.assertIsInstance(handler, logging.StreamHandler)
        assert isinstance(handler, logging.StreamHandler)
        old = handler.setStream(stream)
        try:
            with patch(
                "django.core.mail.EmailMultiAlternatives.send",
                side_effect=OSError("PRIVATE_SMTP_DIAGNOSTIC"),
            ):
                known = self.client.post(
                    "/accounts/password_reset/", {"email": "alias-a@example.test"}
                )
                unknown = self.client.post(
                    "/accounts/password_reset/", {"email": "missing@example.test"}
                )
        finally:
            handler.setStream(old)
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.headers["Location"], unknown.headers["Location"])
        self.assertEqual(
            stream.getvalue().strip(), "account event=password_recovery_delivery_failed"
        )

    def test_csrf_signup_verification_recovery_logout_and_session_reset(self) -> None:
        client = Client(enforce_csrf_checks=True)
        for path in ("/accounts/signup/", "/accounts/password_reset/", "/accounts/verification/"):
            self.assertEqual(client.post(path, signup_data()).status_code, 403)
        client.get("/accounts/signup/")
        csrf = client.cookies["csrftoken"].value
        client.post("/accounts/signup/", signup_data(), HTTP_X_CSRFTOKEN=csrf)
        path = verification_path()
        self.assertEqual(client.post(path).status_code, 403)
        self.assertEqual(client.post(path, HTTP_X_CSRFTOKEN=csrf).status_code, 302)
        self.assertTrue(
            client.login(username="alias-a@example.test", password=signup_data()["password1"])
        )
        self.assertIn("_auth_user_id", client.session)
        self.assertEqual(client.post("/accounts/logout/").status_code, 403)
        reset = Client(enforce_csrf_checks=True)
        reset.get("/accounts/password_reset/")
        reset_csrf = reset.cookies["csrftoken"].value
        reset.post(
            "/accounts/password_reset/",
            {"email": "alias-a@example.test"},
            HTTP_X_CSRFTOKEN=reset_csrf,
        )
        reset_link = verification_path()
        with patch(
            "django.contrib.auth.tokens.PasswordResetTokenGenerator._now",
            return_value=timezone.now().replace(tzinfo=None) + timedelta(days=4),
        ):
            self.assertFalse(reset.get(reset_link).context["validlink"])
        confirmation = reset.get(reset_link)
        target = confirmation.headers["Location"]
        reset.get(target)
        self.assertEqual(
            reset.post(
                target,
                {"new_password1": "Synthetic-New-2026!", "new_password2": "Synthetic-New-2026!"},
            ).status_code,
            403,
        )
        self.assertEqual(
            reset.post(
                target,
                {"new_password1": "Synthetic-New-2026!", "new_password2": "Synthetic-New-2026!"},
                HTTP_X_CSRFTOKEN=reset.cookies["csrftoken"].value,
            ).status_code,
            302,
        )
        self.assertFalse(reset.get(reset_link).context["validlink"])
        client.get("/profile/")
        self.assertNotIn("_auth_user_id", client.session)
        self.assertTrue(
            client.login(username="alias-a@example.test", password="Synthetic-New-2026!")
        )
        client.get("/accounts/login/")
        self.assertEqual(
            client.post(
                "/accounts/logout/", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
            ).status_code,
            302,
        )
        self.assertNotIn("_auth_user_id", client.session)

    def test_attempt_limits_login_signup_reset_resend(self) -> None:
        for path, maximum, data in (
            ("/accounts/login/", 10, {"username": "missing", "password": "invalid"}),
            ("/accounts/signup/", 5, {"adult": ""}),
            ("/accounts/password_reset/", 5, {"email": "missing@example.test"}),
            ("/accounts/verification/", 5, {"email": "missing@example.test"}),
        ):
            for _ in range(maximum):
                self.assertNotEqual(self.client.post(path, data).status_code, 429)
            self.assertEqual(self.client.post(path, data).status_code, 429)


class ProxyIdentityTests(SimpleTestCase):
    def resolve(self, peer: str, chain: str) -> str:
        return client_address(
            RequestFactory().get("/", REMOTE_ADDR=peer, HTTP_X_FORWARDED_FOR=chain)
        )

    @override_settings(BASIS_TRUSTED_PROXY_CIDRS=[])
    def test_untrusted_peer_cannot_spoof_identity(self) -> None:
        self.assertEqual(self.resolve("192.0.2.1", "198.51.100.2"), "192.0.2.1")

    @override_settings(BASIS_TRUSTED_PROXY_CIDRS=["192.0.2.0/24", "2001:db8::/32"])
    def test_trusted_chain_stops_at_last_untrusted_hop(self) -> None:
        self.assertEqual(
            self.resolve("192.0.2.1", "203.0.113.99, 198.51.100.2, 192.0.2.2"), "198.51.100.2"
        )
        self.assertEqual(self.resolve("2001:db8::1", "2001:db9::2"), "2001:db9::2")
        for invalid in ("bad-address", ",", ",".join(["192.0.2.2"] * 17)):
            self.assertEqual(self.resolve("192.0.2.1", invalid), "192.0.2.1")


class AccountLifecycleMigrationTests(TransactionTestCase):
    def test_existing_inactive_accounts_are_not_inferred_to_be_pending(self) -> None:
        old = [
            ("basis_accounts", "0001_initial"),
            ("auth", "0012_alter_user_first_name_max_length"),
        ]
        new = [("basis_accounts", "0002_emailverification")]
        executor = MigrationExecutor(connection)
        executor.migrate(old)
        try:
            historical_user = executor.loader.project_state(old).apps.get_model("auth", "User")
            disabled = historical_user.objects.create(username="legacy-disabled", is_active=False)
            active = historical_user.objects.create(username="legacy-active", is_active=True)
            MigrationExecutor(connection).migrate(new)
            self.assertEqual(
                EmailVerification.objects.get(account_id=disabled.pk).state, "disabled"
            )
            self.assertEqual(EmailVerification.objects.get(account_id=active.pk).state, "verified")
            self.assertFalse(get_user_model().objects.get(pk=disabled.pk).is_active)
        finally:
            MigrationExecutor(connection).migrate(new)


@skipUnlessDBFeature("has_select_for_update")
class AccountConcurrencyTests(TransactionTestCase):
    def request(self, path: str, data: dict[str, str], peer: str) -> int:
        connections.close_all()
        try:
            return Client().post(path, data, REMOTE_ADDR=peer).status_code
        finally:
            connections.close_all()

    def test_duplicate_signup_race_is_one_complete_enrollment(self) -> None:
        barrier = threading.Barrier(2)
        original = DjangoAccounts.create_inactive

        def together(adapter: DjangoAccounts, command: RegisterAccount) -> Account:
            barrier.wait(timeout=10)
            return original(adapter, command)

        with (
            patch.object(DjangoAccounts, "create_inactive", together),
            ThreadPoolExecutor(2) as pool,
        ):
            jobs = [
                pool.submit(self.request, "/accounts/signup/", signup_data(), f"192.0.2.{n}")
                for n in (1, 2)
            ]
            self.assertEqual([job.result(timeout=20) for job in jobs], [200, 200])
        for model in (
            get_user_model(),
            Athlete,
            AthleteSettings,
            BillingAccount,
            EmailVerification,
        ):
            self.assertEqual(model.objects.count(), 1)
        self.assertFalse(get_user_model().objects.get().is_active)
        self.assertEqual(len(mail.outbox), 1)

    def test_verification_consumed_once_under_concurrent_posts(self) -> None:
        self.client.post("/accounts/signup/", signup_data())
        path = verification_path()
        barrier = threading.Barrier(2)

        def verify() -> int:
            barrier.wait(timeout=10)
            return self.request(path, {}, "192.0.2.1")

        with ThreadPoolExecutor(2) as pool:
            jobs = [pool.submit(verify) for _ in range(2)]
            self.assertEqual(sorted(job.result(timeout=20) for job in jobs), [302, 400])
        self.assertTrue(get_user_model().objects.get().is_active)
        self.assertTrue(Athlete.objects.get().email_verified)

    def test_quota_serializes_initial_row_and_counts_denied_attempts(self) -> None:
        barrier = threading.Barrier(8)

        def attempt() -> int:
            barrier.wait(timeout=10)
            return self.request(
                "/accounts/password_reset/", {"email": "missing@example.test"}, "192.0.2.1"
            )

        with ThreadPoolExecutor(8) as pool:
            jobs = [pool.submit(attempt) for _ in range(8)]
            statuses = [job.result(timeout=30) for job in jobs]
        self.assertEqual(statuses.count(302), 5)
        self.assertEqual(statuses.count(429), 3)
        self.assertEqual(RateWindow.objects.get().count, 8)

    def test_administrative_disable_waits_for_verification_without_lost_disable(self) -> None:
        self.client.post("/accounts/signup/", signup_data())
        path = verification_path()
        user_id = get_user_model().objects.get().pk
        locked, release, disabling = threading.Event(), threading.Event(), threading.Event()
        original = DjangoAccounts.by_claim

        def hold(adapter: DjangoAccounts, claim: VerificationClaim) -> Account:
            result = original(adapter, claim)
            locked.set()
            if not release.wait(timeout=10):
                raise AssertionError("Verification release timed out")
            return result

        def disable() -> None:
            connections.close_all()
            try:
                row = get_user_model().objects.get(pk=user_id)
                row.is_active = False
                disabling.set()
                row.save(update_fields=["is_active"])
            finally:
                connections.close_all()

        with patch.object(DjangoAccounts, "by_claim", hold), ThreadPoolExecutor(2) as pool:
            verification = pool.submit(self.request, path, {}, "192.0.2.1")
            self.assertTrue(locked.wait(timeout=10))
            disable_job = pool.submit(disable)
            self.assertTrue(disabling.wait(timeout=10))
            release.set()
            self.assertEqual(verification.result(timeout=20), 302)
            disable_job.result(timeout=20)
        self.assertFalse(get_user_model().objects.get(pk=user_id).is_active)
        self.assertEqual(EmailVerification.objects.get(account_id=user_id).state, "disabled")

    @override_settings(BASIS_TRUSTED_PROXY_CIDRS=["192.0.2.1/32"])
    def test_proxy_clients_have_independent_persistent_quotas(self) -> None:
        for index in range(1, 7):
            self.assertEqual(
                self.client.post(
                    "/accounts/password_reset/",
                    {"email": "missing@example.test"},
                    REMOTE_ADDR="192.0.2.1",
                    HTTP_X_FORWARDED_FOR=f"198.51.100.{index}",
                ).status_code,
                302,
            )
        self.assertEqual(RateWindow.objects.count(), 6)


@skipUnlessDBFeature("has_select_for_update")
class AccountResetConcurrencyTests(TransactionTestCase):
    def prepare_reset(self) -> tuple[str, str]:
        self.client.post("/accounts/signup/", signup_data())
        self.client.post(verification_path())
        self.client.post("/accounts/password_reset/", {"email": signup_data()["email"]})
        link = verification_path()
        return link, self.client.get(link).headers["Location"]

    def submit(self, client: Client, target: str, password: str) -> tuple[int, int]:
        connections.close_all()
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend = int(cursor.fetchone()[0])
            response = client.post(target, {"new_password1": password, "new_password2": password})
            return response.status_code, backend
        finally:
            connections.close_all()

    def test_completed_admin_disable_survives_inflight_reset(self) -> None:
        _, target = self.prepare_reset()
        view_class = reset_view_class(target)
        original = view_class.form_valid
        ready, release = threading.Event(), threading.Event()
        user = get_user_model().objects.get()
        original_password = user.password

        def before_lock(
            view: PasswordResetConfirmView, form: SetPasswordForm[User]
        ) -> HttpResponse:
            self.assertTrue(form.user.is_active)
            ready.set()
            if not release.wait(timeout=10):
                raise AssertionError("Reset did not leave the pre-lock barrier")
            return original(view, form)

        with patch.object(view_class, "form_valid", before_lock), ThreadPoolExecutor(1) as pool:
            future = pool.submit(self.submit, self.client, target, "Synthetic-Rejected-2026!")
            try:
                self.assertTrue(ready.wait(timeout=10))
                user.is_active = False
                user.save(update_fields=["is_active"])
                user.refresh_from_db()
                self.assertFalse(user.is_active)
                self.assertEqual(user.emailverification.state, "disabled")
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    admin_backend = int(cursor.fetchone()[0])
            finally:
                release.set()
            status, reset_backend = future.result(timeout=20)
        self.assertNotEqual(reset_backend, admin_backend)
        user.refresh_from_db()
        self.assertEqual(status, 200)
        self.assertEqual(user.password, original_password)
        self.assertFalse(user.is_active)
        self.assertEqual(user.emailverification.state, "disabled")
        self.assertFalse(
            Client().login(username=user.username, password="Synthetic-Rejected-2026!")
        )
        self.assertNotIn(INTERNAL_RESET_SESSION_TOKEN, self.client.session)

    def test_same_token_is_consumed_once_between_two_sessions(self) -> None:
        link, _ = self.prepare_reset()
        clients = [Client(), Client()]
        targets = [client.get(link).headers["Location"] for client in clients]
        view_class = reset_view_class(targets[0])
        original = view_class.form_valid
        barrier = threading.Barrier(2)

        def before_lock(
            view: PasswordResetConfirmView, form: SetPasswordForm[User]
        ) -> HttpResponse:
            barrier.wait(timeout=10)
            return original(view, form)

        passwords = ["Synthetic-First-2026!", "Synthetic-Second-2026!"]
        with patch.object(view_class, "form_valid", before_lock), ThreadPoolExecutor(2) as pool:
            jobs = [
                pool.submit(self.submit, clients[i], targets[i], passwords[i]) for i in range(2)
            ]
            results = [job.result(timeout=20) for job in jobs]
        self.assertEqual(sorted(result[0] for result in results), [200, 302])
        self.assertEqual(len({result[1] for result in results}), 2)
        user = get_user_model().objects.get()
        for index, (status, _) in enumerate(results):
            self.assertEqual(user.check_password(passwords[index]), status == 302)
            self.assertNotIn(INTERNAL_RESET_SESSION_TOKEN, clients[index].session)
        self.assertTrue(user.is_active)
        self.assertEqual(user.emailverification.state, "verified")

    def test_reset_writes_only_password_and_preserves_completed_admin_changes(self) -> None:
        _, target = self.prepare_reset()
        view_class = reset_view_class(target)
        original = view_class.form_valid
        ready, release = threading.Event(), threading.Event()
        user = get_user_model().objects.get()

        def before_lock(
            view: PasswordResetConfirmView, form: SetPasswordForm[User]
        ) -> HttpResponse:
            ready.set()
            if not release.wait(timeout=10):
                raise AssertionError("Pre-lock release timed out")
            return original(view, form)

        with patch.object(view_class, "form_valid", before_lock), ThreadPoolExecutor(1) as pool:
            future = pool.submit(self.submit, self.client, target, "Synthetic-Authorized-2026!")
            try:
                self.assertTrue(ready.wait(timeout=10))
                user.first_name, user.is_staff = "Explicit admin change", True
                user.save(update_fields=["first_name", "is_staff"])
            finally:
                release.set()
            self.assertEqual(future.result(timeout=20)[0], 302)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Explicit admin change")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertEqual(user.emailverification.state, "verified")
        self.assertTrue(user.check_password("Synthetic-Authorized-2026!"))

    def test_authority_uses_loaded_database_alias_for_lock_check_and_save(self) -> None:
        _, target = self.prepare_reset()
        view_class = reset_view_class(target)
        original_get = view_class.get_user
        original_valid = view_class.form_valid
        alias = "reset_authority"
        self.assertNotIn(alias, connections.databases)
        # A second connection alias to this runner's already-created test database.
        configuration = connections["default"].settings_dict.copy()
        self.assertIn("test", configuration["NAME"])
        connections.databases[alias] = configuration

        def load(view: PasswordResetConfirmView, uid: str) -> User | None:
            row = original_get(view, uid)
            return get_user_model().objects.using(alias).get(pk=row.pk) if row is not None else None

        def authority(view: PasswordResetConfirmView, form: SetPasswordForm[User]) -> HttpResponse:
            self.assertEqual(form.user._state.db, alias)
            with (
                patch("django.db.router.db_for_write", return_value="default"),
                patch.object(
                    connections["default"],
                    "cursor",
                    side_effect=AssertionError("Reset authority used the wrong alias"),
                ),
            ):
                return original_valid(view, form)

        try:
            with (
                patch.object(type(self), "databases", frozenset({"default", alias})),
                patch.object(view_class, "get_user", load),
                patch.object(view_class, "form_valid", authority),
            ):
                response = self.client.post(
                    target,
                    {
                        "new_password1": "Synthetic-Alias-2026!",
                        "new_password2": "Synthetic-Alias-2026!",
                    },
                )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(get_user_model().objects.get().check_password("Synthetic-Alias-2026!"))
        finally:
            connections[alias].close()
            del connections[alias]
            connections.databases.pop(alias)


class AccountResetProtocolTests(TestCase):
    def setUp(self) -> None:
        self.client.post("/accounts/signup/", signup_data())
        self.client.post(verification_path())
        self.client.post("/accounts/password_reset/", {"email": signup_data()["email"]})
        self.link = verification_path()
        self.user = get_user_model().objects.get()
        self.original_password = self.user.password

    def test_django_session_redirect_get_and_success_cleanup_are_preserved(self) -> None:
        redirect = self.client.get(self.link)
        self.assertEqual(redirect.status_code, 302)
        target = redirect.headers["Location"]
        self.assertIn("/set-password/", target)
        self.assertIn(INTERNAL_RESET_SESSION_TOKEN, self.client.session)
        shown = self.client.get(target)
        self.assertTrue(shown.context["validlink"])
        self.assertTemplateUsed(shown, "accounts/auth/password_reset_confirm.html")
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, self.original_password)
        self.assertTrue(self.user.is_active)
        result = self.client.post(
            target,
            {
                "new_password1": "Synthetic-Protocol-2026!",
                "new_password2": "Synthetic-Protocol-2026!",
            },
        )
        self.assertRedirects(result, "/accounts/reset/done/", fetch_redirect_response=False)
        self.assertNotIn(INTERNAL_RESET_SESSION_TOKEN, self.client.session)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(self.client.get(self.link).context["validlink"])

    def test_each_ineligible_lifecycle_is_rejected_after_form_validation(self) -> None:
        target = self.client.get(self.link).headers["Location"]
        view_class = reset_view_class(target)
        original = view_class.form_valid
        for state in (EmailVerification.State.PENDING, EmailVerification.State.DISABLED):
            with self.subTest(state=state):
                self.client.get(self.link)
                EmailVerification.objects.filter(account=self.user).update(state="verified")

                def revoke(
                    view: PasswordResetConfirmView, form: SetPasswordForm[User]
                ) -> HttpResponse:
                    EmailVerification.objects.filter(account=self.user).update(state=state)
                    return original(view, form)

                with patch.object(view_class, "form_valid", revoke):
                    result = self.client.post(
                        target,
                        {
                            "new_password1": "Synthetic-Rejected-2026!",
                            "new_password2": "Synthetic-Rejected-2026!",
                        },
                    )
                self.assertEqual(result.status_code, 200)
                self.assertFalse(result.context["validlink"])
                self.user.refresh_from_db()
                self.assertEqual(self.user.password, self.original_password)
                self.assertNotIn(INTERNAL_RESET_SESSION_TOKEN, self.client.session)

    def test_session_token_cannot_authorize_a_different_uid(self) -> None:
        self.client.get(self.link)
        other = get_user_model().objects.create_user(
            username="other", password="Synthetic-Other-2026!"
        )
        uid = urlsafe_base64_encode(force_bytes(other.pk))
        result = self.client.post(
            f"/accounts/reset/{uid}/set-password/",
            {
                "new_password1": "Synthetic-Rejected-2026!",
                "new_password2": "Synthetic-Rejected-2026!",
            },
        )
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.context["validlink"])
        other.refresh_from_db()
        self.assertTrue(other.check_password("Synthetic-Other-2026!"))

    def test_saving_the_password_does_not_persist_stale_active_or_privilege_fields(self) -> None:
        form = BasisSetPasswordForm(
            self.user,
            data={
                "new_password1": "Synthetic-Fields-2026!",
                "new_password2": "Synthetic-Fields-2026!",
            },
        )
        self.assertTrue(form.is_valid())
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False, is_staff=True)
        # The field-limited form is deliberately only one layer: the view authority
        # additionally denies changing a disabled account's password.
        form.save()
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(self.user.is_staff)

    @override_settings(DEBUG=False)
    def test_new_form_exception_rolls_back_and_has_no_private_http_diagnostic(self) -> None:
        target = self.client.get(self.link).headers["Location"]
        stream = io.StringIO()
        logger = logging.getLogger("django.request")
        previous = logger.handlers[:], logger.propagate, logger.level
        handler = logging.StreamHandler(stream)
        handler.addFilter(SafeHTTPFilter())
        logger.handlers, logger.propagate, logger.level = [handler], False, logging.ERROR
        original_save = BasisSetPasswordForm.save

        def fail_after_write(form: BasisSetPasswordForm, commit: bool = True) -> User:
            original_save(form, commit=commit)
            raise OSError("PRIVATE_RESET_FORM_DIAGNOSTIC")

        try:
            with patch.object(BasisSetPasswordForm, "save", fail_after_write):
                response = Client(raise_request_exception=False)
                response.cookies = self.client.cookies
                failure = response.post(
                    target,
                    {
                        "new_password1": "Synthetic-Failure-2026!",
                        "new_password2": "Synthetic-Failure-2026!",
                    },
                )
            self.assertEqual(failure.status_code, 500)
            self.assertNotContains(failure, "PRIVATE_RESET_FORM_DIAGNOSTIC", status_code=500)
            self.assertEqual(stream.getvalue().strip(), "HTTP failure status=500")
            self.user.refresh_from_db()
            self.assertEqual(self.user.password, self.original_password)
            self.assertTrue(self.user.is_active)
        finally:
            logger.handlers, logger.propagate, logger.level = previous


class SMTPHandler(socketserver.StreamRequestHandler):
    messages: list[bytes] = []

    def handle(self) -> None:
        self.connection.settimeout(10)
        self.wfile.write(b"220 reference.local ESMTP\r\n")
        while line := self.rfile.readline():
            command = line.split(b" ", 1)[0].strip().upper()
            if command in (b"EHLO", b"HELO", b"MAIL", b"RCPT", b"RSET", b"NOOP"):
                self.wfile.write(b"250 reference.local\r\n")
            elif command == b"DATA":
                self.wfile.write(b"354 send data\r\n")
                data = bytearray()
                while (part := self.rfile.readline()) not in (b".\r\n", b""):
                    data.extend(part)
                self.messages.append(bytes(data))
                self.wfile.write(b"250 accepted locally\r\n")
            elif command == b"QUIT":
                self.wfile.write(b"221 closing\r\n")
                return
            else:
                self.wfile.write(b"502 unsupported\r\n")


@contextmanager
def smtp_sink() -> Iterator[tuple[int, list[bytes]]]:
    class OwnedHandler(SMTPHandler):
        messages: list[bytes] = []

    with socketserver.TCPServer(("127.0.0.1", 0), OwnedHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield int(server.server_address[1]), OwnedHandler.messages
        finally:
            server.shutdown()
            thread.join(timeout=5)


class ReferenceSMTPTests(TestCase):
    def test_real_django_smtp_transport_to_owned_loopback_sink(self) -> None:
        with (
            smtp_sink() as (port, messages),
            override_settings(
                EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                EMAIL_HOST="127.0.0.1",
                EMAIL_PORT=port,
                EMAIL_USE_TLS=False,
                EMAIL_HOST_USER="",
                EMAIL_HOST_PASSWORD="",
                DEFAULT_FROM_EMAIL="reference@example.test",
            ),
        ):
            self.assertEqual(self.client.post("/accounts/signup/", signup_data()).status_code, 200)
            self.assertEqual(len(messages), 1)
            self.assertIn(b"To: alias-a@example.test", messages[0])
            body = str(BytesParser(policy=policy.default).parsebytes(messages[0]).get_content())
            match = re.search(r"https?://[^/]+([^\s]+)", body)
            assert match is not None
            self.assertEqual(self.client.post(match.group(1)).status_code, 302)
            self.assertEqual(
                self.client.post(
                    "/accounts/password_reset/", {"email": "alias-a@example.test"}
                ).status_code,
                302,
            )
            self.assertEqual(len(messages), 2)
            recovery_body = str(
                BytesParser(policy=policy.default).parsebytes(messages[1]).get_content()
            )
            self.assertIn("/accounts/reset/", recovery_body)
