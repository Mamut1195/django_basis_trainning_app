"""Exercise the development catalog through Django's real CSRF middleware."""

import re

from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(DEBUG=True)
class ComponentCatalogTests(TestCase):
    def test_anonymous_catalog_is_synthetic_and_does_not_query_or_write(self) -> None:
        with self.assertNumQueries(0):
            response = self.client.get(reverse("component-catalog"))
        self.assertContains(response, "Datos ficticios")
        self.assertContains(response, 'id="kit-input"')
        self.assertContains(response, 'id="catalog-dialog"')
        self.assertContains(response, "rounded-box")
        self.assertContains(response, "bg-accent")
        self.assertNotContains(response, "<c-ui.")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.client.session.items(), dict().items())

    def test_kit_alerts_expose_all_tone_and_appearance_role_mappings(self) -> None:
        response = self.client.get(reverse("component-catalog"))
        self.assertTemplateUsed(response, "shared/component_catalog.html")
        tags = re.findall(r'<[^>]+\brole="alert"[^>]*>', response.content.decode())
        mapped = [tag for tag in tags if "data-basis-tone=" in tag]
        self.assertEqual(len(mapped), 12)
        pairs = []
        for tag in mapped:
            tone = re.search(r'data-basis-tone="([^"]+)"', tag)
            appearance = re.search(r'data-basis-appearance="([^"]+)"', tag)
            self.assertIsNotNone(tone)
            self.assertIsNotNone(appearance)
            assert tone is not None and appearance is not None
            pairs.append((tone.group(1), appearance.group(1)))
            self.assertIn('class="', tag)
        self.assertCountEqual(
            pairs,
            [
                (tone, appearance)
                for tone in ("info", "success", "warning", "error")
                for appearance in ("soft", "solid", "outline")
            ],
        )
        self.assertNotContains(response, "<c-ui.alert")

    def test_real_csrf_rejection_error_summary_and_valid_nonpersistent_post(self) -> None:
        client = Client(enforce_csrf_checks=True)
        path = reverse("component-catalog")
        self.assertEqual(client.post(path, {"nombre": "Ficticio"}).status_code, 403)
        html = client.get(path).content.decode()
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
        self.assertIsNotNone(match)
        assert match is not None
        token = match.group(1)
        response = client.post(path, {"csrfmiddlewaretoken": token, "correo": "incorrecto"})
        self.assertContains(response, "data-error-summary")
        self.assertContains(response, 'href="#id_nombre"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertNotContains(response, 'id="catalog-accepted"')
        with self.assertNumQueries(0):
            accepted = client.post(
                path,
                {
                    "csrfmiddlewaretoken": token,
                    "nombre": "Ejemplo ficticio",
                    "correo": "ejemplo@example.test",
                },
            )
        self.assertContains(accepted, 'id="catalog-accepted"')
        self.assertContains(accepted, "No se ha guardado nada")
        self.assertEqual(client.post(path, {"csrfmiddlewaretoken": "x" * 64}).status_code, 403)

    def test_fragment_is_get_only_cache_disabled_and_same_structure(self) -> None:
        path = reverse("component-fragment")
        for _ in range(3):
            with self.assertNumQueries(0):
                response = self.client.get(path, HTTP_HX_REQUEST="true")
            self.assertContains(response, 'id="component-fragment"', count=1)
            self.assertContains(response, 'x-data="{ clicks: 0 }"')
            self.assertContains(response, "x-collapse")
            self.assertNotContains(response, "<!DOCTYPE")
            self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.client.post(path).status_code, 405)
        self.assertEqual(self.client.put(reverse("component-catalog")).status_code, 405)

    @override_settings(DEBUG=False)
    def test_both_routes_are_unavailable_without_debug(self) -> None:
        for name in ("component-catalog", "component-fragment"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 404)
        self.assertEqual(self.client.post(reverse("component-catalog")).status_code, 404)
