from pathlib import Path

import pytest

from intelligence_briefing.config import load_enabled_sources, load_model_route, load_retention_rules


def test_retention_rules_match_the_approved_four_bands() -> None:
    config_path = Path("config/event-retention-v1.yml")

    rules = load_retention_rules(config_path)

    assert rules == {"hot": (0, 14), "warm": (15, 30), "cold": (31, 60), "archive": (61, 90)}


def test_kimi_coding_route_overrides_the_shared_client_temperature() -> None:
    route = load_model_route(Path("config/model-routing-v1.yml"), "kimi")

    assert route["base_url"] == "https://api.kimi.com/coding/v1"
    assert route["preferred_models"] == ["kimi-for-coding"]
    assert route["request_options"] == {"temperature": 1, "max_tokens": 512}


def test_enabled_sources_reject_non_https_urls(tmp_path) -> None:
    path = tmp_path / "sources.yml"
    path.write_text(
        "version: 1\nsources:\n  - id: local-file\n    url: file:///etc/passwd\n    enabled: true\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="HTTPS"):
        load_enabled_sources(path)


def test_model_route_rejects_non_https_api_endpoint(tmp_path) -> None:
    path = tmp_path / "models.yml"
    path.write_text(
        "minimax:\n  secret_name: TEST_KEY\n  base_url: http://api.example/v1\n  preferred_models: [test]\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="HTTPS"):
        load_model_route(path, "minimax")
