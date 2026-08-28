"""w6_tz_recall.py -- W6: engine recall against Austin's TradeZella book.

THE SECOND HELD-OUT SET
-----------------------
`research/marks/probe_omen_test1_2026-08-27.jsonl` (100 cards, scored by
`research/t70_test1_score.py`) is the project's only clean held-out sample and
it cost Austin a grading session. His TradeZella export is a second one that
costs him nothing: it is a book of trades he selected and sized himself, with a
real entry price, a real exit price and a real risk on every row.

WHERE THE FILE IS, AND WHY IT TOOK FINDING
------------------------------------------
The OMEN 6 H2 master spec says the CSV is "not currently on this machine". It is
-- it is in git history, not the working tree. It was added at `ce2a98d6`
("v2.8: commit loose work from v2.8 run") as `data/tradezella_trades.csv` and
deleted later. Recovered with:

    git show ce2a98d6:data/tradezella_trades.csv

`TZ_CSV` below points at the working-tree copy this script restores it to. Nothing
about the extract is fabricated; every row is read from that blob.

WHAT THE BOOK ACTUALLY IS -- READ THIS BEFORE READING A RECALL NUMBER
---------------------------------------------------------------------
The spec called this "his real executed trade journal ... the only non-hindsight
record in the whole project". **That is not what the file says, and the
difference is load-bearing.** All 350 rows carry `Account Name = "Backtesting"`.
This is Austin replaying the tape by hand and logging what he would have taken,
not a broker fill record. So it is:

  * NOT non-hindsight -- he could see the day when he logged it. Treat it as a
    held-out set because the ENGINE has never been shown it, which is still
    true and still worth a lot, not because it is live execution.
  * still his hand, at bar resolution, with an entry price, a derived stop and a
    realised R:R on every row -- which no other corpus in this project has.

Reported as a held-out ENGINE test. Not reported as live execution.

THE STYLE DIFFERENCE, WHICH IS THE FINDING
-------------------------------------------
Austin: the TradeZella book is "a much simpler omen trading style". The file
agrees, hard, and this script prints the evidence rather than averaging it away:
two symbols, one playbook, one window. See the STYLE section of the output.

THE MATCH CONVENTION IS t70's, IMPORTED
----------------------------------------
No second definition of "match" is invented here. `run_day` and `TOL` come from
`research/t4_engine_recall`, and `entry_match`, `best_tier`, `maps_to` and
`in_universe` are imported from `research/t70_test1_score` so that the numbers
below sit on the same axis as the published Test 1 numbers:

    fired        the engine produced at least one takeable entry on that
                 symbol-day at all
    entry match  some fired entry landed within +/-TOL (= 2) bars of his own
                 entry bar, where the bar index is into `rth_candles`

THE STOP, DERIVED NOT INVENTED
------------------------------
TradeZella has no stop column. It has `Trade Risk` (dollars at risk) and
`Quantity`, so risk-per-share = |Trade Risk| / Quantity and

    long   stop = Entry Price - risk_per_share
    short  stop = Entry Price + risk_per_share

`--selfcheck` verifies this against the rows where the trade was a loss and
therefore exited AT the stop: the derived stop must reproduce `Exit Price`.

READ-ONLY against the engine. No default changed, no flag added. Bars come from
the archive via `run_day`, which returns None on a miss; a missing day is
reported as a gap, never fetched, so this cannot touch POLYGON_API_KEY.

    python research/w6_tz_recall.py [--limit N]
    python research/w6_tz_recall.py --selfcheck

Writes nothing; prints the tables. They land in
`research/w6_tz_recall_and_odds.md`.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.t4_engine_recall import TOL, run_day, rth_candles      # noqa: E402
from research.t70_test1_score import (                               # noqa: E402
    best_tier, entry_match, frac, in_universe, maps_to, pct,
)

TZ_CSV = os.path.join(_ROOT, "data", "tradezella_trades.csv")
TZ_BLOB = "ce2a98d6:data/tradezella_trades.csv"

# Austin's side vocabulary -> the engine's.
SIDE_DIR = {"long": "call", "short": "put"}


# ---------------------------------------------------------------------------
# pure helpers -- everything --selfcheck exercises lives here
# ---------------------------------------------------------------------------

def derive_stop(entry: float, trade_risk: float, qty: float, side: str):
    """TradeZella has no stop column; it has dollars-at-risk and size."""
    if not qty:
        return None
    per_share = abs(trade_risk) / qty
    return entry - per_share if side == "long" else entry + per_share


def parse_rows(path=TZ_CSV):
    """One dict per TradeZella row. `hhmm` is the ET minute of the entry."""
    out = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            side = (r["Side"] or "").strip().lower()
            try:
                entry = float(r["Entry Price"])
                qty = float(r["Quantity"] or 0)
                risk = float(r["Trade Risk"] or 0)
            except ValueError:
                continue
            # "09:43:59 EST" -> "09:43". The suffix is already Eastern, which is
            # the clock the archive's candle timestamps are on.
            hhmm = (r["Open Time"] or "")[:5]
            out.append({
                "symbol": (r["Symbol"] or "").strip().upper(),
                "date": (r["Open Date"] or "").strip(),
                "hhmm": hhmm,
                "side": side,
                "dir": SIDE_DIR.get(side),
                "entry_p": entry,
                "exit_p": float(r["Exit Price"]) if r["Exit Price"] else None,
                "stop_p": derive_stop(entry, risk, qty, side),
                "qty": qty,
                "risk_usd": risk,
                "net_pnl": float(r["Net P&L"]) if r["Net P&L"] else None,
                "realized_rr": float(r["Realized RR"]) if r["Realized RR"] else None,
                "status": (r["Status"] or "").strip(),
                "playbook": (r["Playbook"] or "").strip(),
                "account": (r["Account Name"] or "").strip(),
                "close_time": (r["Close Time"] or "")[:5],
            })
    return out


def bar_index(candles, hhmm):
    """Index into `rth_candles` of the bar covering an ET HH:MM. None if the
    minute is outside the session the archive holds."""
    for i, c in enumerate(candles):
        if c.timestamp[:5] == hhmm:
            return i
    return None


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

def score(rows, limit=None):
    days = sorted({(r["symbol"], r["date"]) for r in rows})
    if limit:
        days = days[:limit]
        keep = set(days)
        rows = [r for r in rows if (r["symbol"], r["date"]) in keep]

    cache = {}
    scored = []
    for n, key in enumerate(days):
        try:
            entries, sigs, _raw = run_day(*key)
            cache[key] = (entries or [], sigs or [], entries is not None)
        except Exception as exc:
            cache[key] = ([], [], False)
            print("  ! %s %s: %s" % (key[0], key[1], str(exc)[:80]), flush=True)
        if n and n % 50 == 0:
            print("  %d/%d symbol-days" % (n, len(days)), flush=True)

    bars = {}
    for r in rows:
        key = (r["symbol"], r["date"])
        entries, sigs, has_bars = cache[key]
        if key not in bars:
            bars[key] = rth_candles(*key) or []
        ei = bar_index(bars[key], r["hhmm"]) if bars[key] else None
        tier = best_tier(entries)
        em = entry_match(entries, ei)
        # Which fired entry, if any, is the closest to his bar -- so direction
        # agreement is asked of the entry that actually matched.
        near = None
        if ei is not None and entries:
            near = min(entries, key=lambda e: abs(e["bar"] - ei))
        scored.append({
            **r,
            "in_universe": in_universe(r["symbol"]),
            "has_bars": has_bars,
            "entry_i": ei,
            "n_fires": len(entries),
            "n_signals": len(sigs),
            "tier": tier,
            "col": maps_to(tier),
            "fired": bool(entries),
            "signal_seen": bool(sigs),
            "entry_match": em,
            "signal_match": (any(abs(s["bar"] - ei) <= TOL for s in sigs)
                             if ei is not None else False),
            "dir_agree": (bool(near) and em and near["direction"] == r["dir"]),
            "near_bar_gap": (abs(near["bar"] - ei)
                             if (near and ei is not None) else None),
        })
    return scored, days


def report(scored, days, all_rows):
    print("=" * 92)
    print("W6 -- engine recall against the TradeZella book")
    print("source: git blob %s  (restored to data/tradezella_trades.csv)" % TZ_BLOB)
    print("=" * 92)

    # ---- STYLE: the finding, not a nuisance --------------------------------
    print("\n### STYLE -- what this book is, versus what the engine trades")
    acct = Counter(r["account"] for r in all_rows)
    pb = Counter(r["playbook"] for r in all_rows)
    sym = Counter(r["symbol"] for r in all_rows)
    ds = sorted(r["date"] for r in all_rows)
    hrs = Counter(r["hhmm"][:2] for r in all_rows)
    print("  rows                 %d over %d distinct symbol-days" % (len(all_rows), len(days)))
    print("  date range           %s -> %s" % (ds[0], ds[-1]))
    print("  ACCOUNT              %s   <-- NOT live execution" % dict(acct))
    print("  symbols              %s" % dict(sym))
    print("  playbooks            %s" % dict(pb))
    print("  entry hour (ET)      %s" % dict(sorted(hrs.items())))
    print("  side                 %s" % dict(Counter(r["side"] for r in all_rows)))
    print("  status               %s" % dict(Counter(r["status"] for r in all_rows)))
    rr = [r["realized_rr"] for r in all_rows if r["realized_rr"] is not None]
    if rr:
        srr = sorted(rr)
        print("  realized RR          n=%d  mean %+.4f  median %+.4f  min %+.2f  max %+.2f"
              % (len(rr), sum(rr) / len(rr), srr[len(srr) // 2], srr[0], srr[-1]))
        print("  months green         %s" % months_green(all_rows))
    trades_per_day = len(all_rows) / len(days) if days else 0
    print("  trades per traded day %.2f" % trades_per_day)

    # ---- HIS R:R distribution, against the engine's own 2-year book --------
    # The master spec's goal 0 is "raise the median R:R". His simpler book is a
    # direct read on whether a simpler setup already does that, so the shape of
    # his distribution is printed rather than summarised to one number.
    if rr:
        print("\n### HIS R:R distribution -- goal 0 is the MEDIAN, so read that row first")
        buckets = [(-99, -0.999, "= -1.00 R (stopped, exact)"),
                   (-0.999, 0.0, "between -1 R and 0"),
                   (0.0, 1.0, "0 to +1 R"),
                   (1.0, 2.0, "+1 to +2 R"),
                   (2.0, 3.0, "+2 to +3 R"),
                   (3.0, 99, "+3 R and up")]
        for lo, hi, label in buckets:
            k = sum(1 for x in rr if lo <= x < hi) if lo != -99 \
                else sum(1 for x in rr if x <= hi)
            print("  %-28s %4d  %5.1f%%" % (label, k, pct(k, len(rr))))
        srr = sorted(rr)
        print("  win rate                     %s" % frac(sum(1 for x in rr if x > 0), len(rr)))
        print("  mean of the winners          %+.4f R"
              % (sum(x for x in rr if x > 0) / max(1, sum(1 for x in rr if x > 0))))
        print("\n  against the engine's 2-year book (research/h1_2y_nowatch.md, f5ff006a,")
        print("  1,091 trades, ON WATCH off) -- DIFFERENT population, stated not merged:")
        print("  %-24s %12s %12s" % ("", "his TZ book", "engine 2y"))
        print("  %-24s %12d %12d" % ("trades", len(rr), 1091))
        print("  %-24s %12.4f %12.4f" % ("MEAN R", sum(rr) / len(rr), 0.8416))
        print("  %-24s %12.4f %12.4f" % ("MEDIAN R  <-- goal 0",
                                         srr[len(srr) // 2], 0.4120))
        print("  %-24s %12s %12s" % ("months green", months_green(all_rows), "24/25"))
        print("  %-24s %12s %12s" % ("symbols", len(sym), "~20"))
        print("  %-24s %12s %12s" % ("setups", len(pb), "6+"))

    if not scored:                          # --style-only: no engine replay ran
        return [], {}

    # ---- coverage ----------------------------------------------------------
    ok = [s for s in scored if s["in_universe"] and s["has_bars"] and s["entry_i"] is not None]
    print("\n### COVERAGE")
    print("  rows scored                  %d" % len(scored))
    print("  out of engine universe       %d" % sum(1 for s in scored if not s["in_universe"]))
    print("  no archived bars             %d" % sum(1 for s in scored if not s["has_bars"]))
    print("  entry minute not in session  %d"
          % sum(1 for s in scored if s["has_bars"] and s["entry_i"] is None))
    print("  --> scorable rows            %d" % len(ok))

    okdays = {}
    for s in ok:
        okdays.setdefault((s["symbol"], s["date"]), []).append(s)
    print("  --> scorable symbol-days     %d" % len(okdays))

    # ---- recall ------------------------------------------------------------
    print("\n### RECALL -- same convention as research/t70_test1_score.py (+/-%d bars)" % TOL)
    fired_days = sum(1 for k, v in okdays.items() if v[0]["fired"])
    seen_days = sum(1 for k, v in okdays.items() if v[0]["signal_seen"])
    print("  day-level: engine fired at all on his day     %s"
          % frac(fired_days, len(okdays)))
    print("  day-level: engine SAW a signal (any status)   %s"
          % frac(seen_days, len(okdays)))
    print("  trade-level: engine fired that day            %s"
          % frac(sum(1 for s in ok if s["fired"]), len(ok)))
    print("  trade-level: entry match within +/-%d bars     %s"
          % (TOL, frac(sum(1 for s in ok if s["entry_match"]), len(ok))))
    print("  trade-level: SIGNAL match within +/-%d bars    %s"
          % (TOL, frac(sum(1 for s in ok if s["signal_match"]), len(ok))))
    print("  of the entry matches, direction agrees        %s"
          % frac(sum(1 for s in ok if s["dir_agree"]),
                 sum(1 for s in ok if s["entry_match"])))

    gaps = [s["near_bar_gap"] for s in ok if s["near_bar_gap"] is not None]
    if gaps:
        g = sorted(gaps)
        print("  nearest fired entry, |bar gap|: median %d, mean %.1f, <=2 in %s"
              % (g[len(g) // 2], sum(g) / len(g),
                 frac(sum(1 for x in g if x <= TOL), len(g))))

    # ---- what he took that the engine graded how ---------------------------
    print("\n### On the days the engine DID fire, what tier did it give?")
    col = Counter(s["col"] for s in ok if s["fired"])
    print("  %s" % dict(col))

    # ---- recall split by his own outcome -----------------------------------
    print("\n### Recall split by HIS outcome (does the engine miss his winners?)")
    for st in ("Win", "Loss"):
        xs = [s for s in ok if s["status"] == st]
        if not xs:
            continue
        print("  %-5s n=%3d   fired %s   entry match %s"
              % (st, len(xs),
                 frac(sum(1 for s in xs if s["fired"]), len(xs)),
                 frac(sum(1 for s in xs if s["entry_match"]), len(xs))))

    print("\n### SIDE BY SIDE with Test 1 (research/t70_test1_score.py, 100 held-out cards)")
    print("  Test 1  S-day recall            3/15  = 20%")
    print("  Test 1  false fire on X days   12/42  = 29%")
    print("  Test 1  entry match             4/58  =  7%")
    print("  TZ      day recall             %s" % frac(fired_days, len(okdays)))
    print("  TZ      entry match            %s"
          % frac(sum(1 for s in ok if s["entry_match"]), len(ok)))
    print("  (TZ has no X rows -- every row is a trade he took, so there is no")
    print("   false-fire denominator on this set. That asymmetry is the point:")
    print("   TZ measures recall only, never precision.)")
    return ok, okdays


def months_green(rows):
    by = defaultdict(list)
    for r in rows:
        if r["net_pnl"] is not None:
            by[r["date"][:7]].append(r["net_pnl"])
    g = sum(1 for m in by if sum(by[m]) > 0)
    # The months he traded, NOT the calendar span -- the export has gaps and a
    # "10/10" that hid them would be a durability claim he never made.
    return "%d/%d [%s]" % (g, len(by), ",".join(sorted(by)))


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck():
    print("w6_tz_recall selfcheck")
    assert TOL == 2, "the join is +/-2 bars, imported from t4_engine_recall"

    # derive_stop, both sides, off the header row of the real file.
    s = derive_stop(480.37, -592.5, 750.0, "long")
    assert abs(s - 479.58) < 0.005, "long stop = entry - |risk|/qty; got %r" % s
    s2 = derive_stop(240.97, -427.5, 750.0, "short")
    assert abs(s2 - 241.54) < 0.005, "short stop = entry + |risk|/qty; got %r" % s2
    assert derive_stop(100.0, -100.0, 0, "long") is None, "zero size has no stop"

    if os.path.exists(TZ_CSV):
        rows = parse_rows()
        assert rows, "the CSV parsed to zero rows"
        # THE REAL CHECK: a Loss exits AT the stop, so the derived stop must
        # reproduce Exit Price. This is what makes the stop derived, not guessed.
        losses = [r for r in rows if r["status"] == "Loss"
                  and r["stop_p"] is not None and r["exit_p"] is not None]
        bad = [r for r in losses if abs(r["stop_p"] - r["exit_p"]) > 0.02]
        print("  losses checked: %d, stop != exit on %d" % (len(losses), len(bad)))
        assert len(bad) <= len(losses) * 0.02, \
            "derived stop should equal the exit on a loss; %d/%d disagree" \
            % (len(bad), len(losses))
        assert all(r["dir"] in ("call", "put") for r in rows), "unmapped side"
    else:
        print("  (CSV not in the tree; skipped the file-backed assertions)")

    # bar_index on a hand-built session.
    class _C:
        def __init__(self, t):
            self.timestamp = t
    day = [_C("09:3%d:00" % i) for i in range(10)]
    assert bar_index(day, "09:35") == 5
    assert bar_index(day, "10:15") is None
    print("  OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--style-only", action="store_true",
                    help="the STYLE and R:R sections only -- no engine replay")
    a = ap.parse_args()
    if a.selfcheck:
        selfcheck()
        return
    if not os.path.exists(TZ_CSV):
        print("data/tradezella_trades.csv is missing. Restore it with:")
        print("    git show %s > data/tradezella_trades.csv" % TZ_BLOB)
        sys.exit(2)
    rows = parse_rows()
    if a.style_only:
        report([], sorted({(r["symbol"], r["date"]) for r in rows}), rows)
        return
    scored, days = score(rows, a.limit)
    report(scored, days, rows if not a.limit else
           [r for r in rows if (r["symbol"], r["date"]) in set(days)])


if __name__ == "__main__":
    main()
