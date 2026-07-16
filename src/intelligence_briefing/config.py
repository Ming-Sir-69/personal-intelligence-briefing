"""Read small versioned configuration files."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import yaml


def load_retention_rules(path: Path) -> dict[str, tuple[int, int]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    bands = payload["media_echo_bands"]
    return {
        name: (int(values["min_age_days"]), int(values["max_age_days"]))
        for name, values in bands.items()
    }


def load_enabled_sources(path: Path) -> list[dict[str, str]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = payload.get("sources", [])
    enabled = [
        {key: str(value) for key, value in source.items() if key != "enabled"}
        for source in sources
        if source.get("enabled", False)
    ]
    for source in enabled:
        _require_https_url(source.get("url", ""), f"source {source.get('id', 'unknown')}")
    return enabled


def load_candidate_selection(path: Path) -> dict[str, int]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    selection = payload.get("candidate_selection", {})
    max_items_per_source = int(selection.get("max_items_per_source", 20))
    if max_items_per_source < 1:
        raise ValueError("max_items_per_source must be positive")
    return {"max_items_per_source": max_items_per_source}


def load_model_route(path: Path, provider: str) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    route = payload[provider]
    if not isinstance(route, dict):
        raise ValueError(f"invalid {provider} route")
    _require_https_url(str(route.get("base_url", "")), f"{provider} API")
    return route


def _require_https_url(value: str, label: str) -> None:
    parsed = urlsplit(value.strip())
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{label} must use an HTTPS URL without embedded credentials")
