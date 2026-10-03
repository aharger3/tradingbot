"""A failed ntfy push must not latch the once-per-day flags (retry next time)."""
import live_scanner as ls

REC = {"symbol": "TSLA", "level_tf": "intraday", "direction": "call", "ts": "09:45",
       "setup": "x_y", "entry": 1.0, "stop": 0.5, "target": 2.0, "contracts": 1,
       "tier": "S", "level": "PDH"}


def _reset():
    ls._session_push.update(date="2026-10-02", pushed=False, exit_pushed=False,
                            summary_pushed=False, push_rec=None, veto_first=None,
                            trades=[], exits=[])


def test_s_alert_retried_after_failed_push():
    _reset()
    orig = ls.notify_ntfy.push
    try:
        ls.notify_ntfy.push = lambda *a, **k: False
        assert ls._note_s_trade(dict(REC)) and not ls._push_s_signal(REC)
        assert ls._session_push["pushed"] is False
        assert ls._note_s_trade(dict(REC))      # still eligible: retry
    finally:
        ls.notify_ntfy.push = orig


def test_summary_retried_after_failed_push():
    _reset()
    orig = ls.notify_ntfy.push
    try:
        ls.notify_ntfy.push = lambda *a, **k: False
        assert ls.push_summary() is False
        assert ls._session_push["summary_pushed"] is False
        ls.notify_ntfy.push = lambda *a, **k: True
        assert ls.push_summary() is True
        assert ls._session_push["summary_pushed"] is True
        assert ls.push_summary() is False       # once only after success
    finally:
        ls.notify_ntfy.push = orig


def test_exit_push_latches_only_on_success():
    _reset()
    ls._session_push["push_rec"] = dict(REC)
    ev = {"symbol": "TSLA", "outcome": "stop", "r": -1.0, "ts": "10:00",
          "entry_premium": 1, "exit_premium": 0.5, "pnl": -50}
    orig_exit = ls._push_exit

    class R:  # no discord
        pass
    try:
        ls._push_exit = lambda rec, e: False
        ls._on_paper_exit(R(), dict(ev))
        assert ls._session_push["exit_pushed"] is False
        ls._push_exit = lambda rec, e: True
        ls._on_paper_exit(R(), dict(ev))
        assert ls._session_push["exit_pushed"] is True
    finally:
        ls._push_exit = orig_exit
