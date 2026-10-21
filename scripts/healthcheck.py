"""Loopback readiness probe with a deliberately allowed Host; no response/log leakage."""

import os
import sys
import urllib.request


def main() -> int:
    request = urllib.request.Request(
        "http://127.0.0.1:8000/health/",
        headers={"Host": os.environ.get("DJANGO_HEALTH_HOST", "localhost")},
    )
    try:
        # Never send a local health probe through an inherited HTTP proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=5) as response:
            return 0 if response.status == 200 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
