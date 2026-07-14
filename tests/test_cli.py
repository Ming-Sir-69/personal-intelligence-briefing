import os
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
