"""futures_signal.py -- live/paper signal generator + ntfy alert, NQ break-and-retest.

*** EXPERIMENTAL -- PAPER ONLY. NO CONFIRMED EDGE. ***
The NQ break-and-retest cell (t02-break-retest/bt.py, levels=PRE, stop=LVL,
target=3R) is a single post-hoc cell -- 1 of 42 tested combinations in that
grid -- with both halves positive and a real shuffled-vs-zero gap, but it has
NOT cleared:
  (a) the out-of-sample 2010-2024 NQ check (ship-plan build ticket B1), or
  (b) the 40-paper-session go/no-go in OMEN-SHIP-PLAN.md Sec.3.
Every push and every journal line this module writes is flagged PAPER and
EXPERIMENTAL. This module never places, or could place, a live order -- there
is no broker/order-submission code path here at all, by construction.

Rule shipped here (frozen, ship-plan Sec.3 -- do not re-tune without a new
gate run):
  instrument   NQ front month, sized in MNQ ($2/pt). Not ES.
  levels       PRE only: PDH/PDL (prior RTH) + ONH/ONL (18:00->09:29 ET).
               No opening-range levels (lose in every cell in the t02 grid).
               Long only at highs, short only at lows.
  break        1m close through the level by > 10% of the trailing avg 1m
               range.
  retest       price leaves, returns within 25%-of-prev-bar tolerance,
               <= 10 bars after the break; any close back through voids it.
  confirm      <= 3 bars after the retest: close beyond the level, candle in
               the trade direction, adverse wick <= 1.5x body.
  entry        next 1m bar's open (honest fill, no look-ahead).
  stop         hard stop-market at level - 0.25 x avg range ("LVL" stop
               mode). Never a close-based stop (that produced the phantom
               edge in u10 #2).
  target       3R limit. Flat at 11:00 open.
  window       one signal per day, 09:30-10:30 ET.
  size         n = floor(200 / (stop_pt*2 + commission)), capped at 50 MNQ
               (bt.MAXN) -- identical formula to the studied backtest.

This module does NOT reimplement the detector: it loads
research/agent_runs/t02-break-retest/bt.py unchanged (by file path, not by
copy) and calls its own sessions()/signals()/trade() functions. That is a
deliberate anti-drift measure -- the paper book this ships and the backtest
Austin was shown can never silently diverge, because they are the same code.

Usage:
    python research/futures_signal.py replay --date 2026-08-15
    python research/futures_signal.py replay --date 2026-08-15 --push
    python research/futures_signal.py replay-range --start 2026-06-01 --end 2026-09-01
    python research/futures_signal.py live              # see LiveFeed below

Live mode (Q5, OMEN-SHIP-PLAN.md Sec.5, is still open -- no live 1-min NQ
feed has been chosen or wired). Rather than fake a feed, `live()` uses a
pluggable LiveFeed and, with none configured, logs exactly that and exits 0
-- never crashing a scheduled run, same contract as notify_ntfy.push().
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import date as date_cls, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
BT_PATH = HERE / "agent_runs" / "t02-break-retest" / "bt.py"
JOURNAL = HERE.parent / "journal" / "paper_nq.jsonl"
ET = ZoneInfo("America/New_York")

# Frozen rule (ship-plan Sec.3). Not a config surface -- changing these
# values is re-tuning a post-hoc cell and goes back through the gate.
ROOT = "NQ"
LEVELSET = "PRE"
STOPMODE = "LVL"
TARGET_K = 3

FLAG_TITLE = "EXPERIMENTAL"
FLAG_FOOTER = (
    "PAPER -- EXPERIMENTAL, no confirmed edge. 1 of 42 t02 cells; "
    "OOS + 40-session paper gate both still open (OMEN-SHIP-PLAN.md Sec.3)."
)


def _load_bt():
    """Load t02's bt.py by file path -- the studied script, unmodified."""
    if not BT_PATH.exists():
        raise FileNotFoundError(
            f"t02 bt.py not found at {BT_PATH}. futures_signal.py reuses its "
            f"detector on purpose; it does not reimplement one."
        )
    spec = importlib.util.spec_from_file_location("t02_bt", BT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # our own repo's script, not third-party input
    return mod


def find_signal_for_day(bt, S: dict):
    """First signal on this session that yields a sizable trade, or None.

    Mirrors bt.main()'s own selection exactly: `for s in sigs: t =
    trade(...); if t: break`. Returns (sig, trade_dict) or None.
    """
    for sig in bt.signals(S, LEVELSET):
        t = bt.trade(S, sig, STOPMODE, TARGET_K, ROOT, net=True)
        if t:
            return sig, t
    return None


def price_levels(S: dict, sig, t: dict):
    """Entry/stop/target prices for the push, derived algebraically from
    trade()'s own returned `dist` -- no re-derivation of the stop/target
    business rule, so this can never disagree with the honest-fill sim.
    """
    i, d, level, ri, name = sig
    j = i + 1
    fill = float(S["o"][j])
    dist = t["dist"]
    stop = fill - d * dist
    tgt = fill + d * TARGET_K * dist
    return dict(entry=round(fill, 2), stop=round(stop, 2), target=round(tgt, 2),
                level_name=name, level=round(float(level), 2),
                signal_tod=int(S["tod"][i]), entry_tod=int(S["tod"][j]))


def _hhmm(tod_minutes: int) -> str:
    return f"{tod_minutes // 60:02d}{tod_minutes % 60:02d}"


def build_push(session_date: str, S: dict, sig, t: dict) -> dict:
    """Pure function: session + signal + trade -> ntfy push fields.
    No network call in here -- kept separate from notify_ntfy.push() so it
    can be unit-tested without a topic or a socket.
    """
    i, d, level, ri, name = sig
    px = price_levels(S, sig, t)
    direction = "LONG" if d == 1 else "SHORT"
    hhmm = _hhmm(px["signal_tod"])
    title = f"[{FLAG_TITLE}] OMEN BR {ROOT} {direction} #S{hhmm}-1"
    valid_until_min = px["entry_tod"]
    body = (
        f"{ROOT} break-and-retest off {name.upper()} {px['level']}\n"
        f"entry {px['entry']} (next 1m open) | stop {px['stop']} | "
        f"target {px['target']} (3R)\n"
        f"size {t['n']} MNQ | valid until {_hhmm(valid_until_min)} bar open, "
        f"else void\n"
        f"flat 11:00 if untouched\n\n{FLAG_FOOTER}"
    )
    return dict(
        title=title, body=body, priority="high", tags="warning,chart",
        click=f"https://www.tradingview.com/chart/?symbol=CME_MINI%3A{ROOT}1%21",
        date=session_date, direction=direction, **px,
        size_mnq=t["n"], stop_pts=round(t["dist"], 2),
    )


def journal_line(session_date: str, S: dict, sig, t: dict, source: str) -> dict:
    """The record written to journal/paper_nq.jsonl -- signal + the same
    honest-fill resolution bt.trade() already computed (stop/target/time
    exit, next-bar-open fill, commission+slippage included).
    """
    px = price_levels(S, sig, t)
    return dict(
        ts=datetime.now(ET).isoformat(), date=session_date, root=ROOT,
        source=source, flag="EXPERIMENTAL_PAPER_ONLY", **px,
        direction="LONG" if sig[1] == 1 else "SHORT",
        size_mnq=t["n"], stop_pts=round(t["dist"], 2), r_multiple=round(t["R"], 4),
        usd=round(t["usd"], 2), exit_reason=t["why"],
    )


def append_journal(record: dict, path: Path = JOURNAL) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=float) + "\n")


def run_replay_day(bt, session_date: str, sessions_cache: dict, push: bool,
                   journal_path: Path = JOURNAL):
    """Evaluate one already-loaded session date. Returns the journal record,
    or None if nothing fired that day (most days -- 1-3 signals/week is the
    honest rate in the t02 book).
    """
    S = sessions_cache.get(session_date)
    if S is None:
        print(f"  futures_signal: no {ROOT} session data for {session_date}")
        return None
    found = find_signal_for_day(bt, S)
    if found is None:
        return None
    sig, t = found
    rec = journal_line(session_date, S, sig, t, source="replay")
    append_journal(rec, journal_path)
    print(f"  futures_signal [{FLAG_TITLE}] {session_date} {rec['direction']} "
          f"{rec['level_name']} entry={rec['entry']} stop={rec['stop']} "
          f"target={rec['target']} size={rec['size_mnq']} R={rec['r_multiple']:+.2f} "
          f"({rec['exit_reason']})")
    if push:
        from notify_ntfy import push as ntfy_push
        pmsg = build_push(session_date, S, sig, t)
        ntfy_push(pmsg["title"], pmsg["body"], priority=pmsg["priority"],
                  tags=pmsg["tags"], click=pmsg["click"])
    return rec


def cmd_replay(args):
    bt = _load_bt()
    sessions_cache = bt.sessions(ROOT)
    run_replay_day(bt, args.date, sessions_cache, push=args.push)


def cmd_replay_range(args):
    bt = _load_bt()
    sessions_cache = bt.sessions(ROOT)
    dates = [d for d in sorted(sessions_cache) if args.start <= d <= args.end]
    fired = 0
    for d in dates:
        if run_replay_day(bt, d, sessions_cache, push=args.push) is not None:
            fired += 1
    print(f"  futures_signal: {fired}/{len(dates)} sessions fired "
          f"({args.start}..{args.end})")


class LiveFeed:
    """Pluggable source of live 1-min NQ bars. OMEN-SHIP-PLAN.md Sec.5 (Q5)
    has not been answered -- no live feed is wired here. Subclass this and
    pass an instance to live() once a feed is chosen (Tradovate demo,
    Massive Advanced, Databento Live, or the eval platform's own feed).
    """

    def bars_today(self):
        """Return today's bars so far in bt.sessions()'s per-day dict shape,
        or raise NotImplementedError if unconfigured.
        """
        raise NotImplementedError


def cmd_live(args):
    feed = LiveFeed()
    try:
        feed.bars_today()
    except NotImplementedError:
        print("  futures_signal: NO LIVE FEED CONFIGURED -- Sec.5 (Q5) of "
              "OMEN-SHIP-PLAN.md is still open. Not sending any push, not "
              "writing to the paper journal. Run `replay` against Massive "
              "bars instead until a feed is chosen.")
        return
    # A real feed would drive the same find_signal_for_day()/journal_line()/
    # ntfy_push() path used by run_replay_day() above, on a growing intraday
    # bar set instead of a whole finished session.
    raise NotImplementedError("live feed wired but the live loop is not "
                              "implemented yet")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("replay", help="evaluate one historical session")
    p1.add_argument("--date", required=True, help="YYYY-MM-DD")
    p1.add_argument("--push", action="store_true", help="also send the ntfy push")
    p1.set_defaults(func=cmd_replay)

    p2 = sub.add_parser("replay-range", help="evaluate a range of sessions")
    p2.add_argument("--start", required=True)
    p2.add_argument("--end", required=True)
    p2.add_argument("--push", action="store_true")
    p2.set_defaults(func=cmd_replay_range)

    p3 = sub.add_parser("live", help="live paper mode (needs Q5 answered)")
    p3.set_defaults(func=cmd_live)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
