"""Public shell assets and private, account-scoped preparation contracts."""

import json
import re

from django.test import TestCase

from .factories import account, session


class PwaContractsTests(TestCase):
    def test_manifest_and_local_dependencies_are_available_anonymously(self) -> None:
        manifest = self.client.get("/manifest.webmanifest")
        self.assertEqual(manifest["Content-Type"], "application/manifest+json")
        self.assertEqual(manifest.json()["scope"], "/")
        worker = self.client.get("/service-worker.js")
        self.assertEqual(worker["Service-Worker-Allowed"], "/")
        source = worker.content.decode()
        match = re.search(r"const ASSETS = (\[.*?\]);", source)
        assert match is not None
        assets = json.loads(match.group(1))
        self.assertTrue(all(url.startswith(("/static/", "/offline/")) for url in assets))
        for asset in (
            "vendor/htmx.min.js",
            "vendor/alpine.min.js",
            "django_cotton_ui/cotton-ui.min.js",
        ):
            self.assertIn("/static/" + asset, assets)
        self.assertNotIn("__BASIS_SHELL_", source)

    def test_public_shell_omits_authenticated_identity(self) -> None:
        user = account("pwa-private")
        self.client.force_login(user)
        private = self.client.get("/profile/")
        self.assertContains(private, str(user.athlete.public_id))
        self.client.logout()
        public = self.client.get("/offline/")
        self.assertNotContains(public, str(user.athlete.public_id))
        self.assertNotContains(public, user.email)
        self.assertContains(public, "Añadir a pantalla de inicio")
        self.assertContains(public, "20 sesiones")
        self.assertContains(public, 'name="apple-mobile-web-app-capable"')

    def test_preparation_and_cookie_identity_are_private_and_scoped(self) -> None:
        first, other = account("pwa-first"), account("pwa-other")
        item = session(first)
        url = f"/api/sessions/{item.pk}/snapshot/"
        self.client.force_login(first)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["account"], str(first.athlete.public_id))
        self.assertIn("no-store", response["Cache-Control"])
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)
        identity = self.client.get("/api/csrf/")
        self.assertEqual(identity.json()["account"], str(other.athlete.public_id))
        self.assertIn("no-store", identity["Cache-Control"])
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
