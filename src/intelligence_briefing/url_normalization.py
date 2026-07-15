"""Canonicalize public source URLs before exact matching."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid"}


def normalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.casefold()
    host = (parsed.hostname or "").casefold()
    port = parsed.port
    netloc = host if port in (None, 80 if scheme == "http" else 443 if scheme == "https" else None) else f"{host}:{port}"
    path = parsed.path.rstrip("/") or "/"
    parameters = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in TRACKING_KEYS
    ]
    return urlunsplit((scheme, netloc, path, urlencode(sorted(parameters)), ""))
