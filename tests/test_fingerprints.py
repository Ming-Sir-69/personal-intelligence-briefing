from datetime import date

from intelligence_briefing.fingerprints import event_fingerprint


def test_event_fingerprint_is_stable_across_title_or_whitespace_changes() -> None:
    first = event_fingerprint(
        subject="OpenAI",
        object_name="Codex",
        action="release",
        event_date=date(2026, 7, 14),
        core_change="Parallel agents available",
    )
    second = event_fingerprint(
        subject=" openai ",
        object_name="CODEX",
        action="release",
        event_date=date(2026, 7, 14),
        core_change="parallel   agents available",
    )

    assert first == second


def test_event_fingerprint_changes_for_a_substantive_change() -> None:
    preview = event_fingerprint("OpenAI", "Codex", "release", date(2026, 7, 14), "preview")
    released = event_fingerprint("OpenAI", "Codex", "release", date(2026, 7, 14), "generally available")

    assert preview != released
