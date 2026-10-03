"""One trading morning: fetch the bars known at `now`, find new candidates, decide, log, send (or dry-run).

The same Scan.step() runs live (Alpaca bars, real clock) and in replay (a stored day revealed one minute at a time),
so a dry run on a past session exercises exactly the code that will run on Monday.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from . import alpaca_bars, cards, context, detect, ledger, policy
from .config import DATA_DIR, ET, MAX_CARDS_PER_DAY, WINDOW_FIRST, WINDOW_LAST

BAR_LAG_SECONDS = 6          # wait this long after the minute closes before asking for its bar


def floor_minute(now: datetime) -> str:
    return now.astimezone(ET).strftime("%H:%M:00")


def _tie(c: dict) -> str:
    return hashlib.sha1(c["key"].encode()).hexdigest()      # no alphabetical bias when the cap binds


class LiveFetcher:
    """Incremental IEX fetch: the whole premarket once, then the last 20 minutes each call (late prints overwrite)."""

    def __init__(self, day: str, syms: list[str], *, fetch=alpaca_bars.fetch_bars, hdrs: dict | None = None):
        self.day, self.syms, self.fetch, self.hdrs = day, syms, fetch, hdrs
        self.store: dict[str, dict[str, object]] = {s: {} for s in syms}
        self.first = True

    def __call__(self, now: datetime) -> dict[str, list]:
        open_ = datetime.fromisoformat(self.day + "T04:00:00").replace(tzinfo=ET)
        start = open_ if self.first else max(open_, now - timedelta(minutes=20))
        kw = {"hdrs": self.hdrs} if self.hdrs is not None else {}
        raw = self.fetch(self.syms, start, now, **kw)
        for s in self.syms:
            for c in alpaca_bars.to_candles(raw.get(s) or []):
                self.store[s][c.timestamp] = c
        self.first = False
        cut = floor_minute(now)                               # the in-progress minute is not a bar yet
        return {s: [self.store[s][t] for t in sorted(self.store[s]) if t < cut] for s in self.syms}


class ReplayFetcher:
    """A stored day (full candles per symbol) shown only up to the minute before `now`."""

    def __init__(self, full: dict[str, list]):
        self.full = full

    def __call__(self, now: datetime) -> dict[str, list]:
        cut = floor_minute(now)
        return {s: [c for c in cs if c.timestamp < cut] for s, cs in self.full.items()}


class Scan:
    def __init__(self, day: str, syms: list[str], ctxs: dict, fetcher: Callable, *, live: bool,
                 data_dir: Path = DATA_DIR, out_dir: Path | None = None, session=None, cap: int = MAX_CARDS_PER_DAY,
                 cfg: dict | None = None, log: Callable[[str], None] = print, check_schedule: bool = True):
        self.day, self.syms, self.ctxs, self.fetcher = day, syms, ctxs, fetcher
        self.live, self.data_dir, self.session, self.cap, self.log = live, Path(data_dir), session, cap, log
        self.out_dir = Path(out_dir) if out_dir else self.data_dir / "charts"
        self.cfg = cfg
        self.check_schedule = check_schedule
        self.mode = "live" if live else "dry"
        self.last_bars: dict[str, list] = {}

    def _qqq(self, bars: dict[str, list]):
        if "QQQ" not in bars or "QQQ" not in self.ctxs:
            return None
        pmh, pml, _ = detect.split_session(bars["QQQ"])
        return context.qqq_breaks(bars["QQQ"], self.ctxs["QQQ"], pmh, pml)

    def step(self, now: datetime) -> list[dict]:
        """Returns the ledger rows for cards sent (or would-be sent) on this step."""
        if self.check_schedule:
            ok, why = policy.schedule_ok(now)
            if not ok:
                self.log(f"{now:%H:%M:%S} skip: {why}")
                return []
        bars = self.fetcher(now)
        self.last_bars = bars
        qqq = self._qqq(bars)
        seen = ledger.seen_keys(self.day, self.data_dir)
        new: list[dict] = []
        for s in self.syms:
            cs = bars.get(s) or []
            ctx = self.ctxs.get(s)
            if not cs or ctx is None or ctx.pdh is None:
                continue
            for c in detect.detect_all(s, self.day, cs, ctx, qqq):
                if c["key"] not in seen:
                    new.append(c)
        new.sort(key=lambda c: (c["sig_t"], _tie(c)))
        sent: list[dict] = []
        stamp = now.astimezone(ET).isoformat(timespec="seconds")
        for c in new:
            prev = ledger.cards(self.mode, self.day, self.data_dir)
            n = len(prev)
            verdict = policy.decide(c, now, n, seen, cap=self.cap, prev_cards=prev)
            seen.add(c["key"])
            if verdict != "send":
                ledger.log_candidate(c, verdict, stamp, self.data_dir)
                continue
            try:
                rth = [k for k in bars[c["sym"]] if "09:30:00" <= k.timestamp < "16:00:00"]
                row = cards.deliver(c, rth, n + 1, now, live=self.live, out_dir=self.out_dir, session=self.session,
                                    cfg=self.cfg)
            except Exception as e:                                  # one bad card must not stop the morning
                ledger.log_candidate(c, f"error:{type(e).__name__}", stamp, self.data_dir)
                self.log(f"{now:%H:%M:%S} card error {c['key']}: {type(e).__name__}")
                continue
            ledger.log_card(self.mode, row, self.data_dir)
            ledger.log_candidate(c, "sent" if self.live else "dry", stamp, self.data_dir)
            sent.append(row)
            self.log(f"{now:%H:%M:%S} {'SENT' if self.live else 'WOULD SEND'} {row['card_id']} "
                     f"{c['sym']} {c['side']} {c['sig_t']} stop {c['stop']} ({n + 1}/{self.cap})")
        return sent


def minute_times(day: str, first: str = WINDOW_FIRST, last: str = WINDOW_LAST) -> list[datetime]:
    """Simulated 'now' for each decision bar: the bar closes at sig_t+1 min, the scan runs BAR_LAG_SECONDS later."""
    out = []
    h, m = map(int, first.split(":"))
    t = datetime.fromisoformat(f"{day}T{h:02d}:{m:02d}:00").replace(tzinfo=ET)
    end = datetime.fromisoformat(f"{day}T{last}:00").replace(tzinfo=ET)
    while t <= end:
        out.append(t + timedelta(minutes=1, seconds=BAR_LAG_SECONDS))
        t += timedelta(minutes=1)
    return out


def run_live(scan: Scan, *, until: str = "11:01", sleeper=time.sleep, now_fn=lambda: datetime.now(ET)) -> int:
    """Poll once a minute (BAR_LAG_SECONDS after the close) from just before 09:36 until `until` ET."""
    steps = 0
    while True:
        now = now_fn()
        if now.strftime("%H:%M") >= until:
            return steps
        if now.strftime("%H:%M") < WINDOW_FIRST:                     # wait for the first decision bar to close (09:36)
            sleeper(max(1.0, (now.replace(hour=9, minute=36, second=BAR_LAG_SECONDS, microsecond=0) - now).total_seconds()))
            continue
        try:
            scan.step(now_fn())
            steps += 1
        except Exception as e:                                       # network blip, bad page: log and keep going
            scan.log(f"{now:%H:%M:%S} step error: {type(e).__name__}: {str(e)[:120]}")
        nxt = now.replace(second=BAR_LAG_SECONDS, microsecond=0) + timedelta(minutes=1)
        sleeper(max(1.0, (nxt - now_fn()).total_seconds()))
