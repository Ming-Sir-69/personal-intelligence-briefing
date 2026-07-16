#!/usr/bin/env python3
"""Build GitHub Pages-compatible public review HTML from delivery/current JSON."""

from __future__ import annotations

import argparse
from pathlib import Path

from intelligence_briefing.public_pages import build_public_pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    outputs = build_public_pages(args.root)
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
