"""Public brand identity for HTML and PWA metadata."""

import json
from typing import TypedDict, cast

from django.conf import settings


class BrandIdentity(TypedDict):
    name: str
    product: str
    colors: dict[str, str]
    logo: str
    source: str


IDENTITY = cast(BrandIdentity, json.loads(
    (settings.BASE_DIR / "assets/brand/identity.json").read_text(encoding="utf-8")
))
