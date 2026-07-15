import os
import json
from pathlib import Path
import subprocess
import sys

from intelligence_briefing.cli import main


def test_cli_can_run_an_offline_sample_batch(tmp_path) -> None:
    exit_code = main(["--root", str(tmp_path), "--batch", "noon", "--sample"])

    assert exit_code == 0
    assert (tmp_path / "delivery/current/noon-candidates.json").exists()


def test_source_checkout_can_run_an_offline_sample_batch(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "intelligence_briefing.cli", "--root", str(tmp_path), "--batch", "morning", "--sample"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(Path("src").resolve())},
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "delivery/current/morning-candidates.json").exists()


def test_cli_can_simulate_a_failed_batch_without_replacing_current(tmp_path) -> None:
    main(["--root", str(tmp_path), "--batch", "morning", "--sample"])

    exit_code = main(["--root", str(tmp_path), "--batch", "noon", "--simulate", "failed"])

    manifest = json.loads((tmp_path / "delivery/archive/" / "2026-07" / next(
        path.name for path in (tmp_path / "delivery/archive/2026-07").iterdir() if path.name.startswith("noon-")
    ) / "manifest.json").read_text(encoding="utf-8"))
    current = json.loads((tmp_path / "delivery/current/manifest.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert manifest["status"] == "failed"
    assert current["kind"] == "morning"
