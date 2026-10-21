"""Resolve a proxy chain right-to-left, only behind explicitly trusted CIDRs."""

from ipaddress import ip_address, ip_network

from django.conf import settings
from django.http import HttpRequest


def client_address(request: HttpRequest) -> str:
    peer = str(request.META.get("REMOTE_ADDR", "unknown"))
    networks = [ip_network(value) for value in settings.BASIS_TRUSTED_PROXY_CIDRS]
    try:
        current = ip_address(peer)
        if not any(current in network for network in networks):
            return str(current)
        chain = str(request.META.get("HTTP_X_FORWARDED_FOR", "")).split(",")
        if len(chain) > 16:
            return peer
        for value in reversed(chain):
            if not any(current in network for network in networks):
                break
            current = ip_address(value.strip())
        return str(current)
    except ValueError:
        return peer
