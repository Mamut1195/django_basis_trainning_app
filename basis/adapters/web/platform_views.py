from __future__ import annotations

import hashlib
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone

from basis.adapters.web.framework import owner, public_id


@login_required
def export_data(request: HttpRequest) -> HttpResponse:
    from basis.bootstrap.exports import export_readers
    from basis.shared.identifiers import AccountId

    result: dict[str, object] = {
        "schema": "basis-export-v1",
        "exported_at": timezone.now().isoformat(),
    }
    account = AccountId(owner(request).pk)
    for reader in export_readers():
        for section in reader.read(account):
            result[section.key] = list(section.rows)
    response = JsonResponse(result)
    response["Content-Disposition"] = 'attachment; filename="basis-entrenamiento.json"'
    return response


@login_required
def csrf_api(request: HttpRequest) -> HttpResponse:
    return JsonResponse({"account": str(public_id(request)), "token": get_token(request)})


def manifest(request: HttpRequest) -> HttpResponse:
    from basis.adapters.web.brand import IDENTITY

    return JsonResponse(
        {
            "id": "/",
            "name": "BASIS Training",
            "short_name": "BASIS",
            "lang": "es",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": IDENTITY["colors"]["background"],
            "theme_color": IDENTITY["colors"]["primary"],
            "icons": [
                {
                    "src": "/static/basis/icons/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                },
                {
                    "src": "/static/basis/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
        },
        content_type="application/manifest+json",
    )


def service_worker(request: HttpRequest) -> HttpResponse:
    from pathlib import Path

    from django.contrib.staticfiles import finders

    common = settings.BASE_DIR / "basis/adapters/web"
    critical = [
        common / "templates/shared/base.html",
        common / "templates/cotton/basis/brand.html",
        settings.BASE_DIR / "basis/modules/sync/adapters/templates/sync/offline/index.html",
        common / "static/basis/js/service-worker.js",
        settings.BASE_DIR / "requirements.txt",
    ]
    for path in critical:
        if not path.is_file():
            raise FileNotFoundError(f"Critical offline source missing: {path.name}")
    required_assets = (
        "basis/css/tokens.css",
        "basis/css/app.css",
        "basis/js/theme.js",
        "basis/js/app.js",
        "basis/js/offline.js",
        "basis/js/forms.js",
        "basis/js/timer.js",
        "basis/js/updates.js",
        "basis/icons/icon-192.png",
        "basis/icons/icon-512.png",
        "basis/icons/icon.svg",
        "basis/brand/logo.svg",
        "vendor/htmx.min.js",
        "vendor/alpine.min.js",
        "vendor/alpine-focus.min.js",
        "vendor/alpine-collapse.min.js",
        "django_cotton_ui/cotton-ui.css",
        "django_cotton_ui/cotton-ui.min.js",
    )
    files = set(critical)
    for asset in required_assets:
        located = finders.find(asset)
        if not isinstance(located, str):
            raise FileNotFoundError(f"Critical offline asset missing: {asset}")
        files.add(Path(located))
    for directory in [
        common / "templates",
        common / "static/basis",
        *(settings.BASE_DIR / "basis/modules").glob("*/adapters/templates"),
    ]:
        files.update(path for path in directory.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    from django.templatetags.static import static

    source = (common / "static/basis/js/service-worker.js").read_text(encoding="utf-8")
    rendered = source.replace("__BASIS_SHELL_VERSION__", digest.hexdigest()[:16]).replace(
        "__BASIS_SHELL_ASSETS__",
        json.dumps(["/offline/", *(static(asset) for asset in required_assets)]),
    )
    response = HttpResponse(rendered, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def health(request: HttpRequest) -> HttpResponse:
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
