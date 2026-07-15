"""Read small versioned configuration files."""

from __future__ import annotations

from pathlib import Path

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
    return [
        {key: str(value) for key, value in source.items() if key != "enabled"}
        for source in sources
        if source.get("enabled", False)
    ]


def load_model_route(path: Path, provider: str) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    route = payload[provider]
    if not isinstance(route, dict):
        raise ValueError(f"invalid {provider} route")
    return route
