from pathlib import Path

from intelligence_briefing.config import load_retention_rules


def test_retention_rules_match_the_approved_four_bands() -> None:
    config_path = Path("config/event-retention-v1.yml")

    rules = load_retention_rules(config_path)

    assert rules == {"hot": (0, 14), "warm": (15, 30), "cold": (31, 60), "archive": (61, 90)}
