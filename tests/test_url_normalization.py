from intelligence_briefing.url_normalization import normalize_url


def test_normalize_url_drops_tracking_fragment_and_sorts_remaining_query() -> None:
    url = "HTTPS://Example.COM:443/release/?b=2&utm_source=newsletter&a=1#details"

    assert normalize_url(url) == "https://example.com/release?a=1&b=2"


def test_normalize_url_preserves_meaningful_query_parameters() -> None:
    assert normalize_url("https://example.com/x?id=42&ref=release") == "https://example.com/x?id=42&ref=release"
