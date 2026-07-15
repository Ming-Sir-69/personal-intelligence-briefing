"""Small, metadata-only collectors for configured public feeds."""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Callable, Iterable
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .models import SourceItem
from .time_window import SHANGHAI, ReportWindow
from .url_normalization import normalize_url


def fetch_url(url: str, *, opener: Callable[..., object] = urlopen) -> bytes:
    request = Request(url, headers={"User-Agent": "personal-intelligence-briefing/0.1"})
    with opener(request, timeout=20) as response:  # type: ignore[attr-defined]
        return response.read()  # type: ignore[attr-defined]


def _child_text(element: ElementTree.Element, name: str) -> str | None:
    child = element.find(name)
    return child.text.strip() if child is not None and child.text else None


def _published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    return parsedate_to_datetime(value).astimezone(SHANGHAI)


def _atom_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(SHANGHAI)


def collect_feeds(sources: Iterable[dict[str, str]], fetch: Callable[[str], bytes]) -> list[SourceItem]:
    """Collect RSS/Atom metadata. No page body is fetched or retained."""
    collected: list[SourceItem] = []
    for source in sources:
        collected.extend(_collect_feed(source, fetch))
    return collected


def collect_feeds_safely(
    sources: Iterable[dict[str, str]],
    fetch: Callable[[str], bytes],
) -> tuple[list[SourceItem], tuple[str, ...]]:
    """Collect each configured source independently, preserving usable results."""
    collected: list[SourceItem] = []
    errors: list[str] = []
    for source in sources:
        try:
            collected.extend(_collect_feed(source, fetch))
        except (KeyError, OSError, TimeoutError, ValueError, ElementTree.ParseError) as error:
            errors.append(f"{source.get('id', 'unknown')}: {type(error).__name__}: {error}")
    return collected, tuple(errors)


def select_recent_feed_items(
    items: Iterable[SourceItem],
    window: ReportWindow,
    *,
    max_items_per_source: int,
) -> list[SourceItem]:
    """Keep only dated feed entries in the discovery lookback and cap each source."""
    selected: list[SourceItem] = []
    by_source: dict[str, list[SourceItem]] = {}
    for item in items:
        if item.published_at is None:
            continue
        published_at = item.published_at.astimezone(SHANGHAI)
        if not window.lookback_start <= published_at <= window.end:
            continue
        by_source.setdefault(item.source_id, []).append(item)
    for source_items in by_source.values():
        selected.extend(
            sorted(source_items, key=lambda item: item.published_at or window.lookback_start, reverse=True)[:max_items_per_source]
        )
    return selected


def _collect_feed(source: dict[str, str], fetch: Callable[[str], bytes]) -> list[SourceItem]:
    collected: list[SourceItem] = []
    root = ElementTree.fromstring(fetch(source["url"]))
    for item in root.findall(".//item"):
        link = _child_text(item, "link")
        title = _child_text(item, "title")
        if not link or not title:
            continue
        collected.append(
            SourceItem(
                source_id=source["id"],
                title=title,
                url=normalize_url(link),
                published_at=_published_at(_child_text(item, "pubDate")),
                source_type=source.get("source_type", "discovery"),
            )
        )
    for entry in root.findall(".//{*}entry"):
        title = _child_text(entry, "{*}title")
        link_element = entry.find("{*}link")
        link = link_element.get("href") if link_element is not None else None
        if not link or not title:
            continue
        collected.append(
            SourceItem(
                source_id=source["id"],
                title=title,
                url=normalize_url(link),
                published_at=_atom_datetime(_child_text(entry, "{*}updated") or _child_text(entry, "{*}published")),
                source_type=source.get("source_type", "discovery"),
            )
        )
    return collected
