from pathlib import Path

from intelligence_briefing.config import load_model_route, load_retention_rules


def test_retention_rules_match_the_approved_four_bands() -> None:
    config_path = Path("config/event-retention-v1.yml")

    rules = load_retention_rules(config_path)

    assert rules == {"hot": (0, 14), "warm": (15, 30), "cold": (31, 60), "archive": (61, 90)}


def test_kimi_coding_route_overrides_the_shared_client_temperature() -> None:
    route = load_model_route(Path("config/model-routing-v1.yml"), "kimi")

    assert route["base_url"] == "https://api.kimi.com/coding/v1"
    assert route["preferred_models"] == ["kimi-for-coding"]
    assert route["request_options"] == {"temperature": 1, "max_tokens": 512}
