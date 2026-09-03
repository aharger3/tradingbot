"""test_ntfy_push.py — the phone lane sends exactly what it promises.

omen-8 ticket 01. The contract this file holds, in Austin's terms: ONE trade
alert a day, ITS exit, and ONE 11:00 summary. Never two alerts. Never a push
from a box that was never told where to send.

It proves that by replaying a real archived session (2026-09-02) through the
REAL `live_scanner.scan_once` with `requests.post` monkeypatched, so the
assertions are about the whole path -- detector, tier gate, governor, paper
book, exit, summary -- and not about a hand-built signal dict.

    python -m pytest -q test_ntfy_push.py
    python test_ntfy_push.py

NOTE on `python -m pytest -q` at the repo root: collection currently dies on
`research/test_entry_scratch.py`, which calls `sys.exit()` at module scope.
Several `test_*.py` files in this repo are standalone scripts, not pytest
modules; that is pre-existing and unrelated to this file, which is both.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import live_scanner                                  # noqa: E402
import notify_ntfy                                   # noqa: E402

REPLAY_DAY = "2026-09-02"
# QQQ rides along because `compute_qqq_breaks` asks for its levels every cycle;
# without it in the feed the scanner falls through to the yfinance path and a
# unit test starts making network calls.
REPLAY_SYMBOLS = ["AAPL", "QQQ"]


class _FakeResponse:
    ok = True
    status_code = 200


def _reset_scanner_state() -> None:
    """Every per-session global the scan loop accumulates into.

    These are module-level dicts by design (the process is one trading day and
    the schtask restarts it daily), so a second replay inside one interpreter
    has to clear them or it inherits the first replay's day.
    """
    live_scanner._session_push.update(
        date=None, pushed=False, exit_pushed=False, summary_pushed=False,
        push_rec=None, veto_first=None, trades=[], exits=[], last_close={})
    live_scanner._daily_ctx.clear()
    live_scanner._qqq_state.update(date=None, up=None, dn=None)
    live_scanner._s_trades_today.clear()
    live_scanner._last_alert.clear()
    live_scanner._watch_dings["n"] = 0
    live_scanner._account_streak["n"] = 0
    live_scanner.NEWS_HALT["active"] = False


def _replay_capturing(topic, tmpdir) -> list:
    """Run the replay with `requests.post` captured. Returns the pushes."""
    sent: list = []

    def fake_post(url, data=None, headers=None, timeout=None, **kw):
        sent.append({
            "url": url,
            "title": (headers or {}).get("Title", ""),
            "body": (data or b"").decode("utf-8", "replace"),
        })
        return _FakeResponse()

    real_post = notify_ntfy.requests.post
    real_yf = live_scanner._yf_daily_context
    prior = os.environ.get(notify_ntfy.TOPIC_ENV)
    try:
        notify_ntfy.requests.post = fake_post
        # Belt and braces: no test may reach the network even if a symbol's
        # archive is missing and the daily-context path falls back.
        live_scanner._yf_daily_context = lambda s: (None,) * 7
        if topic is None:
            os.environ.pop(notify_ntfy.TOPIC_ENV, None)
        else:
            os.environ[notify_ntfy.TOPIC_ENV] = topic
        _reset_scanner_state()
        live_scanner.run_replay(REPLAY_DAY, REPLAY_SYMBOLS, paper_on=True,
                                ledger_path=Path(tmpdir) / "replay.jsonl")
    finally:
        notify_ntfy.requests.post = real_post
        live_scanner._yf_daily_context = real_yf
        os.environ.pop(notify_ntfy.TOPIC_ENV, None)
        if prior is not None:
            os.environ[notify_ntfy.TOPIC_ENV] = prior
    return sent


def _classify(sent):
    """(s_pushes, exit_pushes, summary_pushes) by title shape."""
    s = [p for p in sent if p["title"].startswith("OMEN S ")]
    summ = [p for p in sent if p["title"].startswith("OMEN 11:00")]
    exits = [p for p in sent if p not in s and p not in summ]
    return s, exits, summ


def test_replay_sends_exactly_one_s_one_exit_one_summary(tmp_path):
    sent = _replay_capturing("test-omen-unit", tmp_path)
    s, exits, summ = _classify(sent)

    assert len(s) == 1, f"expected exactly 1 S push, got {len(s)}: {[p['title'] for p in s]}"
    assert len(exits) <= 1, f"expected at most 1 exit push, got {len(exits)}"
    assert len(summ) == 1, f"expected exactly 1 summary push, got {len(summ)}"

    # The alert has to be actionable on a lock screen: the four numbers he needs
    # to place the trade, plus which level it retested.
    body = s[0]["body"]
    for field in ("Entry", "Stop", "Target", "Size", "Tier", "Level"):
        assert field in body, f"S push body is missing {field!r}:\n{body}"
    assert " AAPL " in s[0]["title"], s[0]["title"]

    # Both arms, every day, so the 1D veto gets compared without asking him.
    sbody = summ[0]["body"]
    assert "taken   (any level):" in sbody, sbody
    assert "would-be (no prior-day levels):" in sbody, sbody

    if exits:
        assert "R" in exits[0]["title"] or "STOP" in exits[0]["title"].upper()


def test_no_pushes_when_topic_unset(tmp_path):
    sent = _replay_capturing(None, tmp_path)
    assert sent == [], f"{len(sent)} push(es) sent with {notify_ntfy.TOPIC_ENV} unset"


def test_resolve_topic_prefers_argument_then_env():
    prior = os.environ.get(notify_ntfy.TOPIC_ENV)
    try:
        os.environ.pop(notify_ntfy.TOPIC_ENV, None)
        assert notify_ntfy.resolve_topic() is None
        assert notify_ntfy.resolve_topic("  ") is None
        assert notify_ntfy.resolve_topic("from-arg") == "from-arg"
        os.environ[notify_ntfy.TOPIC_ENV] = "from-env"
        assert notify_ntfy.resolve_topic() == "from-env"
        assert notify_ntfy.resolve_topic("from-arg") == "from-arg"
    finally:
        os.environ.pop(notify_ntfy.TOPIC_ENV, None)
        if prior is not None:
            os.environ[notify_ntfy.TOPIC_ENV] = prior


def test_push_never_raises_when_ntfy_is_down():
    """A notification outage must never reach the scan loop."""
    def boom(*a, **kw):
        raise ConnectionError("ntfy unreachable")

    real_post = notify_ntfy.requests.post
    try:
        notify_ntfy.requests.post = boom
        os.environ[notify_ntfy.TOPIC_ENV] = "test-omen-unit"
        assert notify_ntfy.push("t", "b") is False
    finally:
        notify_ntfy.requests.post = real_post
        os.environ.pop(notify_ntfy.TOPIC_ENV, None)


def test_level_tf_agrees_with_the_book():
    """`_level_tf` must not drift from `backtest_2y.LEVEL_TF`, its one owner."""
    assert live_scanner._level_tf("PDH") == "1D"
    assert live_scanner._level_tf("PDL") == "1D"
    for name in ("PMH", "PML", "HOD", "LOD", "OR high", "pivot low",
                 "Order block high", "", None):
        assert live_scanner._level_tf(name) != "1D", name


if __name__ == "__main__":
    import tempfile
    import traceback

    fails = []
    with tempfile.TemporaryDirectory() as td:
        for name, fn in sorted(globals().items()):
            if not name.startswith("test_") or not callable(fn):
                continue
            try:
                fn(Path(td)) if fn.__code__.co_argcount else fn()
                print(f"  PASS  {name}")
            except Exception:
                fails.append(name)
                print(f"  FAIL  {name}\n{traceback.format_exc()}")
    print(f"\n{'FAILED: ' + ', '.join(fails) if fails else 'ntfy push selftest ok'}")
    sys.exit(1 if fails else 0)
