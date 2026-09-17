"""The 11:00 ntfy says WHY nothing traded (referee check 4, 2026-09-17).

Austin's complaint: "no setup today" on a day the scanner halted itself for FOMC.
"""
import live_scanner as ls


def _line():
    return ls.build_summary_text().splitlines()[2]


def test_summary_names_the_real_reason():
    ls._session_push.update(date="2026-09-16", trades=[], bars_total=19, bars_fetched=19)
    ls.NEWS_HALT.update(active=True, kind="FOMC")
    assert _line().startswith("NEWS DAY (FOMC)")
    ls.NEWS_HALT.update(active=False, kind=None)
    ls._session_push["bars_fetched"] = 0
    assert _line().startswith("Bars failed to fetch (0/19")
    ls._session_push["bars_fetched"] = 19
    assert _line() == "No S setup today. Nothing traded."


if __name__ == "__main__":
    test_summary_names_the_real_reason(); print("ok")
