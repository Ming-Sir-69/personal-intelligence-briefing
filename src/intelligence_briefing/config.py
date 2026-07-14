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
