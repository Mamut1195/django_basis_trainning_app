"""Public brand identity shared by HTML, design tokens and PWA metadata."""

import json

from django.conf import settings

IDENTITY = json.loads(
    (settings.BASE_DIR / "assets/brand/identity.json").read_text(encoding="utf-8")
)
