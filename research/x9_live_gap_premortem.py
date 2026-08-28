"""X9 — backtest-to-live gap pre-mortem. Every number in x9_live_gap_premortem.md
comes from this script.

Two sources, both already in the repo:
  research/g3_arm_ow1.json   the shipped 2-year book (45,193 signals, 1,017 traded)
  journal/scanner-*.log      every live scanner session the box has actually run

Nothing here hits the network and nothing here writes to the repo. Run:
    python research/x9_live_gap_premortem.py
"""

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "research" / "g3_arm_ow1.json"
JOURNAL = ROOT / "journal"

# Constants copied from the live path, not invented here.
DELTA = 0.5            # options_sizer.DEFAULT_DELTA
MIN_PREMIUM_RISK = 0.05  # options_sizer: "min tick guard"
MULT = 100             # options_sizer.CONTRACT_MULTIPLIER
MAX_LOSS = 1000.0      # options_sizer.DEFAULT_MAX_LOSS  (= 1R)
B_SIZE_PCT = 0.6       # options_sizer.GRADE_SIZE_PCT["B"]


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    i = min(len(xs) - 1, max(0, int(round((p / 100.0) * (len(xs) - 1)))))
    return xs[i]


def load_book():
    d = json.loads(BOOK.read_text())
    return d["meta"], d["trades"]


# ---------------------------------------------------------------- section A
def sizing(traded):
    """What options_sizer.build_options_plan would actually do to each row."""
    rows = []
    for t in traded:
        risk = abs(t["entry"] - t["stop"])
        raw = round(risk * DELTA, 2)
        clamped = raw < MIN_PREMIUM_RISK
        prem_risk = max(raw, MIN_PREMIUM_RISK)
        per_ct = prem_risk * MULT
        # live sizes a B-grade at 60% of max loss; the backtest sizes every row
        # at a flat 1R.
        budget_flat = MAX_LOSS
        budget_b = MAX_LOSS * B_SIZE_PCT
        ct_flat = int(budget_flat // per_ct)
        ct_b = int(budget_b // per_ct)
        rows.append({
            "sym": t["sym"], "d": t["day"], "r": t["r"], "grade": t["grade"],
            "sgrade": t["sgrade"], "entry": t["entry"], "risk": risk,
            "raw_prem_risk": raw, "clamped": clamped, "prem_risk": prem_risk,
            "per_ct": per_ct, "ct_flat": ct_flat, "ct_b": ct_b,
            "realised_risk_flat": ct_flat * per_ct,
            "realised_risk_b": ct_b * per_ct,
        })
    return rows


def spread_cost_r(rows, spread):
    """Round-trip bid/ask cost, in R, of `spread` dollars of option spread.

    The sim books entry AND exit at the mid (options_sizer takes snap['mid'];
    paper_trader exits at the precomputed stop_premium/target_premium, both
    derived from that mid). Live you buy the ask and sell the bid, so one full
    spread leaves the account per round trip. 1R in premium terms is
    prem_risk dollars per share, so cost_in_R = spread / prem_risk.
    """
    return [spread / r["prem_risk"] for r in rows]


# ---------------------------------------------------------------- section B
SCAN_RE = re.compile(r"=== (\d{2}):(\d{2}):(\d{2}) ET scan ===")


def read_log(p: Path) -> str:
    b = p.read_bytes()
    for enc in ("utf-16", "utf-8", "latin-1"):
        try:
            s = b.decode(enc)
            if s.count("\x00") < len(s) * 0.05:
                return s
        except Exception:
            continue
    return b.decode("latin-1", "replace")


def scanner_health():
    out = []
    for p in sorted(JOURNAL.glob("scanner-*.log")):
        s = read_log(p)
        scans = SCAN_RE.findall(s)
        secs = [int(x[2]) for x in scans]
        mins = [int(x[0]) * 60 + int(x[1]) for x in scans]
        gaps = [b - a for a, b in zip(mins, mins[1:])]
        secsabs = [int(x[0]) * 3600 + int(x[1]) * 60 + int(x[2]) for x in scans]
        # the loop is `scan_once(); sleep(60)`, so one cycle's wall time minus
        # the fixed 60s sleep is how long the scan itself took.
        durs = [b - a - 60 for a, b in zip(secsabs, secsabs[1:])]
        out.append({
            "day": p.stem.replace("scanner-", ""),
            "scans": len(scans),
            "secs": secs,
            "gaps_min": gaps,
            "durs": durs,
            "tasty_fail": s.count("tasty fetch failed"),
            "yf_fail": s.count("yfinance fallback failed"),
            "few_bars": len(re.findall(r"only \d+ bars, skipping", s)),
            "paper_open": s.count("PAPER OPEN"),
            "paper_close": s.count("PAPER CLOSE"),
            "trade_tier": s.count("TRADE "),
            "auth_fail": s.count("session auth failed"),
        })
    return out


# ---------------------------------------------------------------- report
def main():
    meta, trades = load_book()
    traded = [t for t in trades if t.get("traded")]
    print(f"book: {meta['first']}..{meta['last']}  {meta['signals']} signals  "
          f"{len(traded)} traded  {meta['sessions']} sessions")

    print("\n== A. legacy grade of the traded book (the live TRADE-tier gate) ==")
    g = Counter(t["grade"] for t in traded)
    for k, v in g.most_common():
        print(f"  grade {k:3s} {v:5d}  {100*v/len(traded):5.1f}%")
    ok_tier = [t for t in traded if t["grade"] in ("A+", "A") and t["et"] >= "09:40"]
    print(f"  rows that clear live _tier() TRADE gate (A/A+ and >=09:40): "
          f"{len(ok_tier)} / {len(traded)} = {100*len(ok_tier)/len(traded):.2f}%")
    days_with_tier = len({t["day"] for t in ok_tier})
    print(f"  distinct sessions with >=1 TRADE-tier row: {days_with_tier} / {meta['sessions']}")
    # live also caps at the FIRST such signal of the day
    first_per_day = {}
    for t in sorted(ok_tier, key=lambda x: (x["day"], x["et"])):
        first_per_day.setdefault(t["day"], t)
    fr = [t["r"] for t in first_per_day.values()]
    if fr:
        print(f"  first-TRADE-of-day only: {len(fr)} trades  mean R "
              f"{sum(fr)/len(fr):+.4f}  vs book mean "
              f"{sum(t['r'] for t in traded)/len(traded):+.4f}")

    rows = sizing(traded)

    print("\n== B. option sizing the live path would actually produce ==")
    risks = [r["risk"] for r in rows]
    print(f"  stock risk |entry-stop| $: p05 {pct(risks,5):.3f}  p25 {pct(risks,25):.3f} "
          f" median {pct(risks,50):.3f}  p75 {pct(risks,75):.3f}  p95 {pct(risks,95):.3f}"
          f"  max {max(risks):.3f}")
    prem = [r["prem_risk"] for r in rows]
    print(f"  premium risk (= 1R per share) $: p05 {pct(prem,5):.3f}  median "
          f"{pct(prem,50):.3f}  p95 {pct(prem,95):.3f}")
    nclamp = sum(1 for r in rows if r["clamped"])
    print(f"  rows hitting the $0.05 min-tick clamp: {nclamp} / {len(rows)} = "
          f"{100*nclamp/len(rows):.1f}%  (their option stop sits FURTHER than "
          f"1R of stock risk, so the stock stop fires first and the option stop never does)")
    ct = [r["ct_flat"] for r in rows]
    print(f"  contracts at 1R/flat: p05 {pct(ct,5)}  median {pct(ct,50)}  p95 "
          f"{pct(ct,95)}  max {max(ct)}")
    print(f"  rows sizing to >=100 contracts: "
          f"{sum(1 for c in ct if c>=100)} ({100*sum(1 for c in ct if c>=100)/len(ct):.1f}%)"
          f"  >=50: {sum(1 for c in ct if c>=50)}"
          f"  ==0 (live would print 'sizing skip'): {sum(1 for c in ct if c==0)}")
    ctb = [r["ct_b"] for r in rows]
    print(f"  at the B-grade 60% size: median {pct(ctb,50)} contracts, "
          f"{sum(1 for c in ctb if c==0)} rows size to zero")

    print("\n== C. round-trip option spread, priced in R ==")
    print("  cost_in_R = spread / premium_risk.  Nothing in the repo models this.")
    print(f"  {'spread':>8}  {'median R':>9}  {'mean R':>9}  {'p25 R':>8}  {'p75 R':>8}"
          f"  {'book mean R after':>18}")
    book_mean = sum(t["r"] for t in traded) / len(traded)
    for sp in (0.01, 0.02, 0.05, 0.10, 0.15, 0.25, 0.50):
        c = spread_cost_r(rows, sp)
        print(f"  ${sp:6.2f}  {pct(c,50):9.3f}  {sum(c)/len(c):9.3f}  {pct(c,25):8.3f}"
              f"  {pct(c,75):8.3f}  {book_mean - sum(c)/len(c):+18.4f}")
    # the spread that eats the entire measured edge
    for sp in [x / 1000 for x in range(1, 500)]:
        c = spread_cost_r(rows, sp)
        if sum(c) / len(c) >= book_mean:
            print(f"  --> the whole +{book_mean:.4f}R edge is gone at a round-trip "
                  f"spread of ${sp:.3f}")
            break

    print("\n== D. live scanner sessions actually run on this box ==")
    h = scanner_health()
    allsecs = [s for d in h for s in d["secs"]]
    print(f"  {len(h)} session logs, {sum(d['scans'] for d in h)} scan cycles")
    if allsecs:
        cs = Counter(allsecs)
        print(f"  second-of-minute the decision lands on: "
              f"{sorted(cs.items(), key=lambda kv: -kv[1])[:6]}")
        print(f"  offset from the bar close: min {min(allsecs)}s  median "
              f"{pct(allsecs,50)}s  p95 {pct(allsecs,95)}s  max {max(allsecs)}s")
    gaps = [g for d in h for g in d["gaps_min"]]
    if gaps:
        cg = Counter(gaps)
        print(f"  minutes between consecutive scans: {sorted(cg.items())[:6]} "
              f"(a gap of 2+ = a whole 1-min bar never looked at)")
        print(f"  cycles that skipped >=1 bar: {sum(v for k,v in cg.items() if k>=2)}"
              f" / {len(gaps)} = {100*sum(v for k,v in cg.items() if k>=2)/len(gaps):.1f}%")
    durs = [x for d in h for x in d["durs"] if -5 <= x < 3600]
    if durs:
        print(f"  scan-cycle duration (gap - the fixed 60s sleep): median "
              f"{pct(durs,50)}s  p75 {pct(durs,75)}s  p95 {pct(durs,95)}s  max {max(durs)}s")
        healthy = [x for d in h if d["yf_fail"] == 0 and d["tasty_fail"] == 0
                   for x in d["durs"] if -5 <= x < 3600]
        if healthy:
            print(f"  ... on sessions with NO feed failure at all: median "
                  f"{pct(healthy,50)}s  p95 {pct(healthy,95)}s  n={len(healthy)}")
    dead = [d for d in h if d["scans"] > 0 and d["tasty_fail"] + d["yf_fail"] > 0]
    print(f"  sessions with at least one feed failure: {len(dead)} / "
          f"{len([d for d in h if d['scans']>0])}")
    blind = [d for d in h if d["scans"] > 0 and d["yf_fail"] > 0]
    print(f"  sessions where the yfinance FALLBACK also failed (fully blind): "
          f"{len(blind)} -> {[d['day'] for d in blind]}")
    print(f"  sessions that ever opened a paper position: "
          f"{len([d for d in h if d['paper_open']>0])} / {len([d for d in h if d['scans']>0])}")
    print(f"  total PAPER OPEN events across every session ever run: "
          f"{sum(d['paper_open'] for d in h)}")
    print("\n  per-session detail (last 12 with scans):")
    print(f"  {'day':12s} {'scans':>5} {'tastyF':>7} {'yfF':>5} {'fewbar':>7} "
          f"{'open':>5} {'close':>6} {'authF':>6}")
    for d in [x for x in h if x["scans"] > 0][-12:]:
        print(f"  {d['day']:12s} {d['scans']:5d} {d['tasty_fail']:7d} {d['yf_fail']:5d} "
              f"{d['few_bars']:7d} {d['paper_open']:5d} {d['paper_close']:6d} {d['auth_fail']:6d}")

    print("\n== E. entry-clock exposure: what one bar of delay is worth ==")
    # every traded row's entry is the level; the live decision lands `offset`
    # seconds into the NEXT bar. Measure how far price travels in one bar by
    # using the book's own stop distance as the yardstick.
    n1 = sum(1 for t in traded if t["bars"] == 1)
    print(f"  traded rows that resolve in ONE bar: {n1} / {len(traded)} = "
          f"{100*n1/len(traded):.1f}%  (these are the rows a late decision loses outright)")
    fast = [t for t in traded if t["bars"] == 1 and t["out"] == "loss"]
    print(f"  ... of which losses: {len(fast)} ({100*len(fast)/max(n1,1):.1f}%)")
    print(f"  median bars held: {pct([t['bars'] for t in traded],50)}  "
          f"p95 {pct([t['bars'] for t in traded],95)}")


    print("\n== F. the retroactive ON WATCH fill, priced in R ==")
    fill_gap(traded)

    print("\n== G. the live governor vs the book's shape ==")
    byday = Counter(t["day"] for t in traded)
    cd = Counter(byday.values())
    print(f"  traded rows per session: {sorted(cd.items())}")
    print(f"  sessions in the book with >1 trade: "
          f"{sum(v for k,v in cd.items() if k>1)} / {len(byday)}")
    first = {}
    for t in sorted(traded, key=lambda x: (x["day"], x["et"])):
        first.setdefault(t["day"], t)
    firsts = [t["r"] for t in first.values()]
    rest = [t["r"] for t in traded if first[t["day"]] is not t]
    print(f"  live _tier() lets exactly ONE trade per session through "
          f"(signals_today == 0). First-of-day only: {len(firsts)} trades, mean R "
          f"{sum(firsts)/len(firsts):+.4f}")
    if rest:
        print(f"  everything the governor would drop: {len(rest)} trades, mean R "
              f"{sum(rest)/len(rest):+.4f} — "
              f"{100*len(rest)/len(traded):.1f}% of the book")
    ndays_over3 = sum(v for k, v in cd.items() if k > 3)
    print(f"  sessions over the MAX_TRADES_PER_DAY=3 cap: {ndays_over3}")

    print("\n== H. the three costs stacked ==")
    stacked(traded)


def stacked(traded):
    """Book -> pay the close -> pay the close AND the spread. Each step is the
    same 1,017 rows, so the deltas are comparable to every other W-report."""
    wins = sum(1 for t in traded if t["out"] == "win")
    print(f"  0. book as shipped:            {len(traded)} trades  mean R "
          f"{sum(t['r'] for t in traded)/len(traded):+.4f}  win {100*wins/len(traded):.1f}%")
    base = []
    for t in traded:
        bars = _rth_closes(t["sym"], t["day"])
        if not bars or t["entry_i"] >= len(bars):
            continue
        close = bars[t["entry_i"]][3]
        long = t["side"] == "L"
        nr = (close - t["stop"]) if long else (t["stop"] - close)
        if nr <= 0:
            continue
        r = ((t["exit"] - close) / nr) if long else ((close - t["exit"]) / nr)
        base.append((max(r, -1.25), nr))
    m = sum(x for x, _ in base) / len(base)
    w = sum(1 for x, _ in base if x > 0)
    print(f"  1. + pay the bar close:        {len(base)} trades  mean R {m:+.4f}"
          f"  win {100*w/len(base):.1f}%   delta {m - sum(t['r'] for t in traded)/len(traded):+.4f}")
    for sp in (0.02, 0.05, 0.10):
        adj = [x - sp / (nr * DELTA) for x, nr in base]
        ma = sum(adj) / len(adj)
        wa = sum(1 for x in adj if x > 0)
        print(f"  2. + ${sp:.2f} round-trip spread:  {len(adj)} trades  mean R "
              f"{ma:+.4f}  win {100*wa/len(adj):.1f}%   delta {ma - m:+.4f}")


# ---------------------------------------------------------------- section F
ARCHIVE = ROOT / "data_archive"


def _rth_closes(sym: str, day: str):
    """The day's RTH 1-min bars, read straight off the cached CSV. No network:
    a missing day is skipped rather than fetched, so this never spends an API
    call and never leaks the key into a traceback."""
    p = ARCHIVE / sym / f"{day}.csv"
    if not p.exists():
        return None
    import csv as _csv
    out = []
    with p.open(encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            t = row["Datetime"][11:19]
            if "09:30:00" <= t < "16:00:00":
                out.append((float(row["Open"]), float(row["High"]),
                            float(row["Low"]), float(row["Close"])))
    return out


def fill_gap(traded):
    """signal_runner.fill_price books the LEVEL, not the close, whenever the bar
    closed jammed against its own or the session's extreme. The level is a price
    that traded EARLIER inside that bar. A live process that decides at the close
    cannot reach back for it; the best it can do is pay the close.

    So: for every traded row, compare the booked entry against the entry bar's
    actual close, and express the difference in R (= that row's own stop distance).
    """
    got = miss = 0
    costs = []
    worse = 0
    per_r = []
    for t in traded:
        bars = _rth_closes(t["sym"], t["day"])
        if not bars or t["entry_i"] >= len(bars):
            miss += 1
            continue
        got += 1
        close = bars[t["entry_i"]][3]
        risk = abs(t["entry"] - t["stop"])
        if risk <= 0:
            continue
        # paying the close instead of the level: a long that fills higher is
        # worse, a short that fills lower is worse.
        signed = (close - t["entry"]) if t["side"] == "L" else (t["entry"] - close)
        if abs(signed) > 1e-9:
            worse += 1 if signed > 0 else 0
        costs.append(signed)
        per_r.append(signed / risk)
    if not per_r:
        print("  no cached bars matched — not measured")
        return
    print(f"  rows resolved against cached bars: {got}  (skipped, no CSV: {miss})")
    exact = sum(1 for x in per_r if abs(x) < 1e-9)
    print(f"  booked entry == the bar's close: {exact} ({100*exact/len(per_r):.1f}%)"
          f"  -> reachable live")
    print(f"  booked entry != the close (retroactive level fill): "
          f"{len(per_r)-exact} ({100*(len(per_r)-exact)/len(per_r):.1f}%)")
    adverse = [x for x in per_r if x > 1e-9]
    favor = [x for x in per_r if x < -1e-9]
    print(f"  ... of those, paying the close is WORSE on {len(adverse)} and BETTER "
          f"on {len(favor)}")
    print(f"  cost of paying the close, in R: mean {sum(per_r)/len(per_r):+.4f}  "
          f"median {pct(per_r,50):+.4f}  p95 {pct(per_r,95):+.4f}  max {max(per_r):+.4f}")
    print(f"  book mean R would move from "
          f"{sum(t['r'] for t in traded)/len(traded):+.4f} by roughly "
          f"{-sum(per_r)/len(per_r):+.4f} R/trade on entry price alone "
          f"(first-order: it also changes which trades stop out)")

    # Re-price properly: entering worse against the SAME stop widens the risk
    # unit, so 1R is bigger in dollars and the same exit is worth fewer R.
    # Exit price is held fixed, which is optimistic — the 2R target is measured
    # from the entry, so a worse entry also pushes the target further away.
    rr = []
    dead = 0
    for t in traded:
        bars = _rth_closes(t["sym"], t["day"])
        if not bars or t["entry_i"] >= len(bars):
            continue
        close = bars[t["entry_i"]][3]
        long = t["side"] == "L"
        new_risk = (close - t["stop"]) if long else (t["stop"] - close)
        if new_risk <= 0:
            # the close is already through the stop: live this trade is either
            # never taken or opens already losing.
            dead += 1
            continue
        r_new = ((t["exit"] - close) / new_risk) if long else ((close - t["exit"]) / new_risk)
        rr.append(max(r_new, -1.25))  # the -1.25R floor, per CLAUDE.md
    if rr:
        print(f"  re-priced at the close (same stop, same exit, -1.25R floor): "
              f"{len(rr)} trades, mean R {sum(rr)/len(rr):+.4f}, "
              f"win rate {100*sum(1 for x in rr if x>0)/len(rr):.1f}%")
        print(f"  {dead} rows ({100*dead/len(traded):.1f}%) close BEYOND their own stop — "
              f"live those are not trades at all, they are instant stop-outs")


if __name__ == "__main__":
    main()
