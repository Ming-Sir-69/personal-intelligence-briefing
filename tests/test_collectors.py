from datetime import datetime
from zoneinfo import ZoneInfo

from intelligence_briefing.collectors import collect_feeds, collect_feeds_safely, fetch_url, select_recent_feed_items
from intelligence_briefing.models import SourceItem
from intelligence_briefing.time_window import SHANGHAI, ReportWindow


RSS = b"""<?xml version='1.0'?>
<rss><channel><item>
  <title>Codex release</title>
  <link>https://openai.com/news/codex?utm_source=rss</link>
  <pubDate>Mon, 14 Jul 2026 06:00:00 +0800</pubDate>
</item></channel></rss>"""

ATOM = b"""<?xml version='1.0'?>
<feed xmlns='http://www.w3.org/2005/Atom'><entry>
  <title>Claude Code update</title>
  <link href='https://github.com/anthropics/claude-code/releases/tag/v1?utm_source=atom'/>
  <updated>2026-07-14T01:00:00Z</updated>
</entry></feed>"""


def test_collect_feeds_extracts_public_metadata_without_article_body() -> None:
    sources = [{"id": "openai-news", "url": "https://openai.com/news/rss.xml", "source_type": "official"}]

    items = collect_feeds(sources, fetch=lambda _url: RSS)

    assert len(items) == 1
    assert items[0].source_id == "openai-news"
    assert items[0].url == "https://openai.com/news/codex"
    assert items[0].published_at == datetime(2026, 7, 14, 6, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert not hasattr(items[0], "article_body")


def test_collect_feeds_extracts_atom_metadata_from_configured_release_feed() -> None:
    sources = [{"id": "claude-code", "url": "https://github.com/anthropics/claude-code/releases.atom", "source_type": "official"}]

    items = collect_feeds(sources, fetch=lambda _url: ATOM)

    assert items[0].title == "Claude Code update"
    assert items[0].url == "https://github.com/anthropics/claude-code/releases/tag/v1"
    assert items[0].published_at == datetime(2026, 7, 14, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_fetch_url_uses_a_metadata_only_public_request() -> None:
    observed: dict[str, str] = {}

    class Response:
        def read(self) -> bytes:
            return b"<rss/>"

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def opener(request: object, *, timeout: int) -> Response:
        observed["url"] = request.full_url  # type: ignore[attr-defined]
        observed["user_agent"] = request.get_header("User-agent")  # type: ignore[attr-defined]
        assert timeout == 20
        return Response()

    assert fetch_url("https://example.com/feed", opener=opener) == b"<rss/>"
    assert observed == {"url": "https://example.com/feed", "user_agent": "personal-intelligence-briefing/0.1"}


def test_safe_collection_keeps_healthy_sources_when_one_source_fails() -> None:
    sources = [
        {"id": "unavailable", "url": "https://example.com/unavailable", "source_type": "official"},
        {"id": "openai-news", "url": "https://example.com/healthy", "source_type": "official"},
    ]

    def fetch(url: str) -> bytes:
        if "unavailable" in url:
            raise TimeoutError("feed timeout")
        return RSS

    items, errors = collect_feeds_safely(sources, fetch=fetch)

    assert [item.source_id for item in items] == ["openai-news"]
    assert errors == ("unavailable: TimeoutError: feed timeout",)


def test_select_recent_feed_items_keeps_window_items_and_caps_each_source() -> None:
    window = ReportWindow(
        "morning",
        datetime(2026, 7, 14, 13, 10, tzinfo=SHANGHAI),
        datetime(2026, 7, 15, 7, 10, tzinfo=SHANGHAI),
        datetime(2026, 7, 14, 7, 10, tzinfo=SHANGHAI),
    )
    items = [
        SourceItem("openai-news", "newest", "https://example.com/newest", datetime(2026, 7, 15, 6, 30, tzinfo=SHANGHAI), "official"),
        SourceItem("openai-news", "second", "https://example.com/second", datetime(2026, 7, 15, 6, 20, tzinfo=SHANGHAI), "official"),
        SourceItem("openai-news", "third", "https://example.com/third", datetime(2026, 7, 15, 6, 10, tzinfo=SHANGHAI), "official"),
        SourceItem("openai-news", "too old", "https://example.com/old", datetime(2026, 7, 13, 6, 0, tzinfo=SHANGHAI), "official"),
        SourceItem("codex", "undated", "https://example.com/undated", None, "official"),
    ]

    selected = select_recent_feed_items(items, window, max_items_per_source=2)

    assert [item.title for item in selected] == ["newest", "second"]
