"""Template resolution, recovery and shell invalidation across presentation owners."""

import re
from pathlib import Path
from unittest.mock import patch

from django import forms
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.http import HttpRequest
from django.template.backends.django import Template as DjangoTemplate
from django.template.loader import get_template, render_to_string
from django.test import RequestFactory, TestCase

from basis.adapters.web.platform_views import service_worker
from basis.bootstrap.tests.test_execution import account


class PresentationOwnershipTests(TestCase):
    def test_every_authored_template_resolves_from_its_owner(self) -> None:
        roots = [
            settings.BASE_DIR / "basis/adapters/web/templates",
            *(settings.BASE_DIR / "basis/modules").glob("*/adapters/templates"),
        ]
        count = 0
        for root in roots:
            for source in root.rglob("*.html"):
                with self.subTest(source=source):
                    template = get_template(source.relative_to(root).as_posix())
                    assert isinstance(template, DjangoTemplate)
                    self.assertEqual(Path(template.origin.name).resolve(), source.resolve())
                    count += 1
        self.assertGreaterEqual(count, 39)

    def test_reset_form_mail_done_confirm_and_complete_use_accounts_templates(self) -> None:
        owner = account("recovery-owner")
        owner.set_password("Original-example-password-442!")
        owner.save(update_fields=["password"])
        self.assertTemplateUsed(
            self.client.get("/accounts/password_reset/"), "accounts/auth/password_reset_form.html"
        )
        response = self.client.post(
            "/accounts/password_reset/", {"email": owner.email}, follow=True
        )
        self.assertTemplateUsed(response, "accounts/auth/password_reset_done.html")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("BASIS", mail.outbox[0].subject)
        link = re.search(r"https?://[^/]+(/accounts/reset/[^\s]+)", str(mail.outbox[0].body))
        assert link is not None
        confirmation = self.client.get(link.group(1), follow=True)
        self.assertTemplateUsed(confirmation, "accounts/auth/password_reset_confirm.html")
        self.assertContains(confirmation, "Nueva contrase\u00f1a")
        invalid = self.client.post(
            confirmation.request["PATH_INFO"], {"new_password1": "one", "new_password2": "two"}
        )
        self.assertContains(invalid, "data-error-summary")
        changed = self.client.post(
            confirmation.request["PATH_INFO"],
            {
                "new_password1": "Changed-example-password-774!",
                "new_password2": "Changed-example-password-774!",
            },
            follow=True,
        )
        self.assertTemplateUsed(changed, "accounts/auth/password_reset_complete.html")
        owner.refresh_from_db()
        self.assertTrue(owner.check_password("Changed-example-password-774!"))

    def test_generic_and_extra_form_errors_preserve_field_labels_and_variants(self) -> None:
        class InputForm(forms.Form):
            title = forms.CharField(label="T\u00edtulo")

        primary = InputForm({})
        extra = InputForm({}, prefix="actual")
        self.assertFalse(primary.is_valid())
        self.assertFalse(extra.is_valid())
        request: HttpRequest = RequestFactory().get("/")
        request.user = AnonymousUser()
        rendered = render_to_string(
            "shared/form.html",
            {"title": "Variables", "form": primary, "extra_forms": [extra], "revision": 7},
            request=request,
        )
        for fragment in (
            "data-error-summary",
            "#id_title",
            "#id_actual-title",
            "Resultado real",
            'name="revision" value="7"',
            "data-submit-status",
        ):
            self.assertIn(fragment, rendered)

    def test_missing_critical_asset_fails_explicitly(self) -> None:
        with patch("django.contrib.staticfiles.finders.find", return_value=None):
            with self.assertRaisesRegex(FileNotFoundError, "Critical offline asset missing"):
                service_worker(RequestFactory().get("/service-worker.js"))

    def test_feature_partial_changes_invalidate_the_offline_shell(self) -> None:
        request = RequestFactory().get("/service-worker.js")
        before = service_worker(request).content
        original = Path.read_bytes

        def changed(path: Path) -> bytes:
            value = original(path)
            return value + b"<!--changed-->" if path.name == "_timer.html" else value

        with patch.object(Path, "read_bytes", changed):
            after = service_worker(request).content
        self.assertNotEqual(before, after)
        self.assertNotIn(b"__BASIS_SHELL_", before)
        self.assertIn(b"basis/js/forms.js", before)
