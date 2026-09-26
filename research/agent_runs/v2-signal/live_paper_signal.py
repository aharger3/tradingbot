"""OMEN v2 -- live paper signal, delivery only (PAPER, no orders ever placed).

Runs the frozen ORB5 detection engine (signal_engine.py -> orb1m.py) bar-by-bar
and pushes an ntfy card (discord_format.py, s06 template) the moment a signal's
retest+trigger bar closes. Every card is labeled PAPER / EXPERIMENTAL: the
OMEN-SHIP-PLAN-v2.md section 4 go/no-go gate has not cleared (OOS + a month of
live paper are still open), so no edge counts as proven yet.

Bar source is pluggable (`BarSource` protocol: one method, `next_bar()`,
returning (minute_idx, o, h, l, c) or None when the session is over). This
ships two sources:

  - `ReplayBarSource`: reads a day's 1-min bars from a local JSON/CSV file in
    the same shape as orb1m.py's own trades_*/day arrays. Use this for Lane R
    (T+1 replay) today.
  - `DemoBarSource`: orb1m.py's own synthetic fixture (its `if __main__ test`
    block), so the whole pipeline (detect -> format -> push) can be proven
    end to end with zero external dependencies.

A REAL intraday feed (Lane L, TopstepX practice / Tradovate demo) is NOT wired
here -- OMEN-SHIP-PLAN-v2.md section 7 Q3/Q4 (which feed, ~$65/mo) is still an
open question for Austin. yfinance is explicitly excluded (dead for OMEN, see
vault memory) so no feed was substituted silently. Point `BarSource` at the
chosen feed once Q3/Q4 are answered; nothing else in this file changes.
"""
from __future__ import annotations

import argparse
import json
import sys
import os
from datetime import datetime, date
from typing import Iterator, Optional, Protocol

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from signal_engine import BarWindow, check_for_signal, CUTOFF_MINUTES  # noqa: E402
from discord_format import build_card, SizedCard, PAPER_LABEL  # noqa: E402

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT)
try:
    from notify_ntfy import push as ntfy_push  # noqa: E402
except ImportError as _e:  # pragma: no cover - only if repo layout changes
    _import_err = _e

    def ntfy_push(*a, **k):
        safe = str((a, k)).encode("ascii", "replace").decode("ascii")
        print(f"  ntfy: notify_ntfy.push unavailable ({_import_err}), would have sent {safe}")
        return False


class BarSource(Protocol):
    def next_bar(self) -> Optional[tuple]:
        ...


class DemoBarSource:
    """orb1m.py's own synthetic day: OR 100-101, break to 103, pin retest at
    101 (bar 7), entry at bar 8 open. Proves the pipeline with no data feed."""

    def __init__(self):
        import numpy as np
        n = 91
        O = [100.5] * n; H = [101.0] * n; L = [100.0] * n; C = [100.5] * n
        O[5], H[5], L[5], C[5] = 100.9, 103.0, 100.9, 102.9
        O[6], H[6], L[6], C[6] = 102.9, 103.0, 102.0, 102.5
        O[7], H[7], L[7], C[7] = 102.0, 102.1, 101.0, 102.05
        for j in range(8, min(n, 20)):
            O[j] = 102.0 + (j - 8) * 0.5
            H[j] = 102.5 + (j - 8) * 0.5
            L[j] = 101.9 + (j - 8) * 0.5
            C[j] = 102.4 + (j - 8) * 0.5
        self._bars = list(zip(range(n), O, H, L, C))
        self._i = 0

    def next_bar(self):
        if self._i >= len(self._bars):
            return None
        b = self._bars[self._i]
        self._i += 1
        return b


class ReplayBarSource:
    """Reads {"open":[...], "high":[...], "low":[...], "close":[...]} (91 each,
    index 0 = 09:30) from a JSON file -- Lane R replay of one past session."""

    def __init__(self, path: str):
        with open(path) as f:
            self._arr = json.load(f)
        self._i = 0
        self._n = len(self._arr["open"])

    def next_bar(self):
        if self._i >= self._n:
            return None
        i = self._i
        self._i += 1
        o, h, l, c = (self._arr[k][i] for k in ("open", "high", "low", "close"))
        if o is None:
            return (i, float("nan"), float("nan"), float("nan"), float("nan"))
        return (i, o, h, l, c)


def minute_to_et_clock(minute_idx: int) -> str:
    total = 9 * 60 + 30 + minute_idx
    return f"{total // 60:02d}:{total % 60:02d}:00"


def run(source: BarSource, symbol: str = "MNQ", cutoff: str = "10:30",
        contracts: Optional[dict] = None, topic: Optional[str] = None,
        session_date: Optional[str] = None) -> list:
    """Feeds every bar from `source` into the engine; pushes + returns every
    Signal fired as a list of the card dicts sent (for tests/inspection)."""
    contracts = contracts or {"Lucid 50K": 12, "Topstep 50K": 12}
    session_date = session_date or date.today().isoformat()
    window = BarWindow()
    sent = []
    fired = False  # 1 signal per session, frozen engine finds the first valid setup only
    while True:
        bar = source.next_bar()
        if bar is None:
            break
        i, o, h, l, c = bar
        window.update(i, o, h, l, c)
        if fired:
            continue
        sig = check_for_signal(window, cutoff=cutoff)
        if sig is None:
            continue
        fired = True
        entry_hint = window.open[sig.entry_minute] if sig.entry_minute < len(window.open) else None
        target = None
        if entry_hint is not None and entry_hint == entry_hint:  # not NaN
            dist = abs(entry_hint - sig.stop)
            target = entry_hint + sig.side * 2 * dist
        card_src = SizedCard(
            symbol=symbol,
            contract=f"{symbol}Z6",
            side=sig.side,
            setup_grade="S",
            time_et=minute_to_et_clock(sig.retest_minute),
            entry=entry_hint if entry_hint is not None else float("nan"),
            stop=sig.stop,
            target=target if target is not None else float("nan"),
            contracts=contracts,
            stop_level_desc=f"OR5 {'high' if sig.side > 0 else 'low'} retest wick",
            reason=f"[{symbol}] ORB5 break+displacement, wick retest, strong/pin trigger candle",
            valid_until_et=minute_to_et_clock(sig.entry_minute),
            cutoff_et=cutoff,
            signal_id=f"S{minute_to_et_clock(sig.retest_minute).replace(':', '')[:4]}-1",
        )
        card = build_card(card_src)
        assert PAPER_LABEL in card["title"], "every OMEN v2 push must be labeled PAPER / EXPERIMENTAL"
        ntfy_push(card["title"], card["body"], priority=card["priority"], tags=card["tags"], topic=topic)
        sent.append(card)
    return sent


def main():
    ap = argparse.ArgumentParser(description="OMEN v2 live paper signal (PAPER only, no orders)")
    ap.add_argument("--mode", choices=["demo", "replay"], default="demo")
    ap.add_argument("--bars", help="JSON bar file for --mode replay")
    ap.add_argument("--symbol", default="MNQ")
    ap.add_argument("--cutoff", default="10:30", choices=list(CUTOFF_MINUTES))
    ap.add_argument("--topic", default=None, help="overrides OMEN_NTFY_TOPIC")
    a = ap.parse_args()
    if a.mode == "demo":
        source = DemoBarSource()
    else:
        if not a.bars:
            ap.error("--mode replay requires --bars <path.json>")
        source = ReplayBarSource(a.bars)
    sent = run(source, symbol=a.symbol, cutoff=a.cutoff, topic=a.topic)
    print(f"{len(sent)} signal(s) sent, all labeled {PAPER_LABEL}")


if __name__ == "__main__":
    main()
