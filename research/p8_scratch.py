"""P8 / G2 — the dead entry-bar scratch: is it unreachable, and what replaces it?

Austin, 2026-08-11:

    an entry taken intrabar that then closes back beyond the level is not a
    loss — scratch out at close, no 84 percent, this rule and previous applys
    to BR and OCR as well.

`backtest_week.simulate_day` implemented that at the trade-creation site: after
a trade was built, if the ENTRY bar's close sat back through ``sig["stop"]`` the
trade was marked `scratch` on the spot. It never fired in two years.

This measures why, and what the rule is worth once it is asked on a bar where it
can be true. Three things come out of it:

  1. **the near-boundary distribution** — for every trade the engine ever
     created, where the ENTRY bar's close sits relative to the retested level
     and to the stop, signed so positive = through the line, scaled by the entry
     bar's own range. If the population never reaches 0 the branch is consumed
     upstream; if it crowds 0 the rule is expressible and merely mis-triggered.
  2. **the same offsets one bar later** (`d1_*`), which is the earliest bar on
     which "taken intrabar, then closes back" can be true on a close-driven
     engine, and the three bands it splits into.
  3. **the book**, off and on, so the cost of arming `ENTRY_SCRATCH=level` is a
     measured number and not an argument.

Arms:

    off     ENTRY_SCRATCH unset — the shipped book, plus the probe
    level   ENTRY_SCRATCH=level — scratch when the bar AFTER entry closes back
            through the RETESTED level, at that close, never worse than the stop
    stop    ENTRY_SCRATCH=stop  — the dead branch's own line, one bar later.
            Measured for the report only; it re-labels ordinary close-based
            stop-outs as scratches, which contradicts a settled rule.

Usage:
    python research/p8_scratch.py run --arm off   --out research/p8_off.json
    python research/p8_scratch.py run --arm level --out research/p8_level.json
    python research/p8_scratch.py report          # -> research/p8_scratch.md

RUN THE ARMS ONE AT A TIME — concurrent replays contend on the 1-minute archive.

Why this file has its own replay loop instead of calling backtest_2y.py: the
probe rows only exist inside the process that ran the replay, and backtest_2y.py
is owned elsewhere. Everything reusable is imported from it, following
research/p7_84_rule.py.
"""
import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ARMS = {"off": "", "level": "level", "stop": "stop"}
ARM_LABEL = {"off":   "off — ENTRY_SCRATCH unset (shipped)",
             "level": "level — ENTRY_SCRATCH=level",
             "stop":  "stop — ENTRY_SCRATCH=stop (measured, not shipped)"}
DEFAULT_OUT = {a: "research/p8_%s.json" % a for a in ARMS}

# The canonical book, research/bt2y_trades.json (generated 2026-08-26T12:28:00,
# 500 sessions). The off arm must reproduce every one of these or the change is
# not inert. NOTE the two win rates in circulation: 53.2% is 538/1011 DECIDED
# trades, which is how DIRECTION.md and every other OMEN report counts it and
# what `book()` returns; 52.95% is 538/1016 with the 5 scratches left in the
# denominator. A scratch is not a win and it is not a loss either.
CANON = {"signals": 45175, "traded": 1016, "w": 538, "l": 473, "scratch": 5,
         "wr": 53.2, "meanr": 0.9571, "totr": 972.38, "green": 23, "months": 25}


# ---------------------------------------------------------------- the replay

def run(arm: str, days: int, out_path: str) -> None:
    assert "bt2y_trades" not in out_path, "never write the canonical file"
    os.environ["ENTRY_SCRATCH"] = ARMS[arm]
    os.environ["SCRATCH_PROBE"] = "1"

    import polygon_feed as pf
    import backtest_2y as b2                      # imported, never edited
    import backtest_week as bw
    from backtest_week import simulate_day, htf_bias_for, RISK_DOLLARS
    from backtest_12mo import qqq_level_breaks, hourly_from_1m
    from universe import ALL_SYMS, has_archive
    from research import downgrade as dg

    bw.SCRATCH_PROBE.clear()
    bw.ARM84_FUNNEL.clear()

    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    last = max((b2.archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=days)).isoformat()
    window = sorted({d for s in syms for d in b2.archive_days(s) if d >= start})
    print("[%s] %d symbols, %d sessions %s..%s"
          % (arm, len(syms), len(window), window[0], window[-1]), flush=True)
    qqq_brk = qqq_level_breaks(window)

    rows, sessions = [], set()
    for sym in syms:
        day_bars, hourly = {}, []
        for d in [x for x in b2.archive_days(sym) if x >= start]:
            try:
                bars = pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            r = pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
            hourly += hourly_from_1m(d, r)

        n0, prev = len(rows), None
        for d in sorted(day_bars):
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = htf_bias_for(hourly, d)
            trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                                  qqq=qqq_brk.get(d))
            sessions.add(d)
            dbars = b2.dg_bars(rth) if trades else None

            for t in trades:
                # Austin's S/A/C attached alongside the legacy grade, exactly as
                # backtest_2y.py does it (the stop as the level proxy).
                rec = dg.score(dbars, t.entry_idx, t.stop, t.direction == "call", bias)
                rows.append({
                    "sym": sym, "day": d, "ym": d[:7],
                    "setup": t.signal_type, "dir": t.direction,
                    "grade": t.grade, "status": t.status,
                    "traded": bool(t.counted),
                    "et": t.entry_time[:5],
                    "entry": round(t.entry, 2), "stop": round(t.stop, 2),
                    "level": round(t.level_price or 0.0, 2),
                    "target": round(t.target, 2), "exit": round(t.exit_price, 2),
                    "out": t.outcome, "r": round(t.pnl / RISK_DOLLARS, 3),
                    "bars": max(0, t.exit_idx - t.entry_idx),
                    "sgrade": (rec or {}).get("grade", "n/a"),
                    "scaled": bool(t.scaled),
                })
            prev = d
        print("  [%s] %d sessions, %d signals" % (sym, len(day_bars), len(rows) - n0),
              flush=True)

    out = ROOT / out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {"arm": arm, "entry_scratch": ARMS[arm],
            "generated": datetime.now().isoformat(timespec="seconds"),
            "first": min(sessions), "last": max(sessions), "sessions": len(sessions),
            "risk_dollars": RISK_DOLLARS, "signals": len(rows),
            "traded": sum(1 for r in rows if r["traded"]),
            "arm84_funnel": dict(bw.ARM84_FUNNEL)}
    out.write_text(json.dumps({"meta": meta, "trades": rows,
                               "probe": list(bw.SCRATCH_PROBE)},
                              separators=(",", ":")), encoding="utf-8")
    print("wrote %s — %d signals, %d traded, %d probe rows"
          % (out, len(rows), meta["traded"], len(bw.SCRATCH_PROBE)), flush=True)


# --------------------------------------------------------------- the numbers

def book(rows):
    """Whole-book money read. Win rate is of DECIDED trades — a scratch is not a
    win, and it is not in the denominator either, which is how every other OMEN
    report counts it."""
    tr = [r for r in rows if r["traded"]]
    w = sum(1 for r in tr if r["out"] == "win")
    l = sum(1 for r in tr if r["out"] == "loss")
    rs = [r["r"] for r in tr]
    by_m = defaultdict(float)
    for r in tr:
        by_m[r["ym"]] += r["r"]
    return {"signals": len(rows), "traded": len(tr), "w": w, "l": l,
            "scratch": len(tr) - w - l,
            "wr": round(w / (w + l) * 100, 1) if (w + l) else 0.0,
            "meanr": round(statistics.fmean(rs), 4) if rs else 0.0,
            "totr": round(sum(rs), 2),
            "green": sum(1 for v in by_m.values() if v > 0), "months": len(by_m)}


BINS = [-1e9, -1.0, -0.5, -0.25, -0.10, -0.02, 0.0,
        0.02, 0.10, 0.25, 0.50, 1.00, 1e9]
BIN_LABEL = ["< -1.00", "-1.00..-0.50", "-0.50..-0.25", "-0.25..-0.10",
             "-0.10..-0.02", "-0.02..0", "0..+0.02", "+0.02..+0.10",
             "+0.10..+0.25", "+0.25..+0.50", "+0.50..+1.00", "> +1.00"]


def histo(vals):
    c = Counter()
    for v in vals:
        for k in range(len(BINS) - 1):
            if BINS[k] <= v < BINS[k + 1]:
                c[BIN_LABEL[k]] += 1
                break
    return c


def _hist_table(vals, title):
    n = len(vals)
    out = ["", "**%s** — n=%d, min %+.4f, p1 %+.4f, median %+.4f"
           % (title, n, min(vals), _pct(vals, 1), statistics.median(vals)), "",
           "| offset (entry-bar ranges) | signals | share | cumulative |",
           "|---|---:|---:|---:|"]
    c = histo(vals)
    cum = 0
    for lab in BIN_LABEL:
        k = c.get(lab, 0)
        if not k:
            continue
        cum += k
        out.append("| `%s` | %d | %.2f%% | %.2f%% |" % (lab, k, k / n * 100, cum / n * 100))
    return out


def _pct(vals, p):
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, int(round(p / 100 * (len(s) - 1)))))]


DIFF_KEYS = ["sym", "day", "et", "setup", "dir", "grade", "status", "traded",
             "entry", "stop", "target", "exit", "out", "r", "bars"]


def diff(a_path: str, b_path: str) -> int:
    """Row-by-row identity check between two books written in backtest_2y.py's
    schema. This is what proves the P8 code change is inert with the flag OFF:
    `python backtest_2y.py --days 730 --out research/p8_scratch.json` against the
    canonical research/bt2y_trades.json, every row, every field."""
    a, b = _load(a_path), _load(b_path)
    if a is None or b is None:
        sys.exit("missing: %s" % (a_path if a is None else b_path))
    ra, rb = a["trades"], b["trades"]
    ba, bb = book(ra), book(rb)
    print("%-10s %-28s %-28s" % ("field", Path(a_path).name, Path(b_path).name))
    bad = 0
    for k in ("signals", "traded", "w", "l", "scratch", "wr", "meanr", "totr",
              "green", "months"):
        same = ba[k] == bb[k]
        bad += 0 if same else 1
        print("%-10s %-28s %-28s %s" % (k, ba[k], bb[k], "" if same else "  <-- MOVED"))
    if len(ra) != len(rb):
        print("row counts differ: %d vs %d" % (len(ra), len(rb)))
        return 1
    ndiff = 0
    for i, (x, y) in enumerate(zip(ra, rb)):
        for k in DIFF_KEYS:
            if x.get(k) != y.get(k):
                if ndiff < 10:
                    print("row %d  %s: %r != %r" % (i, k, x.get(k), y.get(k)))
                ndiff += 1
    print("%d of %d rows x %d fields differ" % (ndiff, len(ra), len(DIFF_KEYS)))
    return 1 if (bad or ndiff) else 0


def _load(path):
    p = ROOT / path
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the report

def report(out_md: str) -> None:
    off = _load(DEFAULT_OUT["off"])
    if off is None:
        sys.exit("run the off arm first: python research/p8_scratch.py run --arm off")
    lvl = _load(DEFAULT_OUT["level"])
    probe = off["probe"]
    b_off = book(off["trades"])

    L = ["# P8 / G2 — the dead entry-bar scratch",
         "",
         "Generated by `research/p8_scratch.py` on %s. Off arm %s, %d sessions %s..%s."
         % (datetime.now().date().isoformat(), off["meta"]["generated"][:10],
            off["meta"]["sessions"], off["meta"]["first"], off["meta"]["last"]),
         "",
         "> Austin, 2026-08-11: *\"an entry taken intrabar that then closes back beyond",
         "> the level is not a loss — scratch out at close, no 84 percent, this rule and",
         "> previous applys to BR and OCR as well.\"*",
         ""]
    if lvl:
        bl0 = book(lvl["trades"])
        L += ["**Answer in three lines.** The branch is unreachable — over %d trades the"
              % len(probe),
              "entry bar's close is on the good side of the line **every single time**, closest",
              "approach %+.4f bar-ranges. It is unreachable because the backtest already has"
              % min(r["d0_stop"] for r in probe if r["d0_stop"] is not None),
              "the information Austin's rule exists to recover, so the branch was **deleted**.",
              "The nearest expressible rule — scratch when the bar AFTER entry closes back",
              "through the level — is built, measured and **shipped OFF**: it costs",
              "**%+.2fR** over two years, because it cuts %d eventual winners along with the"
              % (bl0["totr"] - b_off["totr"], b_off["w"] - bl0["w"]),
              "%d losses, while the printed win rate *rises* %.1f points on the shrunken"
              % (b_off["l"] - bl0["l"], bl0["wr"] - b_off["wr"]),
              "denominator. Read total R, not the percentage.",
              ""]

    # --- 1. the entry bar
    d0s = [r["d0_stop"] for r in probe if r["d0_stop"] is not None]
    d0l = [r["d0_level"] for r in probe if r["d0_level"] is not None]
    neg_s = sum(1 for v in d0s if v < 0)
    neg_l = sum(1 for v in d0l if v < 0)
    L += ["## 1. The entry bar, measured",
          "",
          "One row per trade the engine created over the replay (%d of them; %d had a"
          % (len(probe), len(probe) - len(d0s)),
          "zero-range entry bar and cannot say where in its range the close sat).",
          "Offsets are signed so **positive = the close is through the line, on the",
          "trade's side**, and scaled by the entry bar's own range.",
          "",
          "| line the close is measured against | signals below it | minimum offset |",
          "|---|---:|---:|",
          "| `sig[\"stop\"]` — what the dead branch tested | **%d** | **%+.4f** |" % (neg_s, min(d0s)),
          "| the retested level (`sig[\"level_price\"]`) | **%d** | **%+.4f** |" % (neg_l, min(d0l)),
          ""]
    L += _hist_table(d0s, "entry-bar close vs the stop (`d0_stop`)")
    L += _hist_table(d0l, "entry-bar close vs the retested level (`d0_level`)")

    # --- 2. one bar later
    d1s = [r["d1_stop"] for r in probe if r["d1_stop"] is not None]
    d1l = [r["d1_level"] for r in probe if r["d1_level"] is not None]
    L += ["", "## 2. One bar later", "",
          "The same two offsets on the bar AFTER entry — the earliest bar on which the",
          "rule can be true on a close-driven engine.", ""]
    L += _hist_table(d1s, "next-bar close vs the stop (`d1_stop`)")
    L += _hist_table(d1l, "next-bar close vs the retested level (`d1_level`)")

    tr = [r for r in probe if r["traded"] and r["d1_level"] is not None]
    band_both = [r for r in tr if r["d1_level"] < 0 and r["d1_stop"] < 0]
    band_mid = [r for r in tr if r["d1_level"] < 0 <= r["d1_stop"]]
    band_none = [r for r in tr if r["d1_level"] >= 0]
    L += ["", "### The three bands, traded signals only (n=%d)" % len(tr), "",
          "| band on the bar after entry | traded signals | share | mean R as booked today |",
          "|---|---:|---:|---:|"]
    for name, rs in (("back through the level AND the stop — a stop-out today", band_both),
                     ("back through the level, still above the stop — runs on today", band_mid),
                     ("holds the level — unaffected", band_none)):
        L.append("| %s | %d | %.1f%% | %+.4fR |"
                 % (name, len(rs), len(rs) / len(tr) * 100 if tr else 0,
                    statistics.fmean([r["r"] for r in rs]) if rs else 0.0))
    mr_hold = statistics.fmean([r["r"] for r in band_none]) if band_none else 0.0
    mr_back = statistics.fmean([r["r"] for r in band_mid + band_both]) if tr else 0.0
    L += ["",
          "**This is the finding worth keeping.** Whether the bar after entry holds the",
          "level sorts the book harder than anything the grader does: %+.4fR against %+.4fR,"
          % (mr_hold, mr_back),
          "a %.2fR spread on n=%d and n=%d. It is not an entry filter — it is only knowable"
          % (mr_hold - mr_back, len(band_none), len(band_mid) + len(band_both)),
          "one bar after the fill — but it says the first minute after entry carries real",
          "information, and the whole question below is whether ACTING on it beats holding.",
          ""]
    eq = sum(1 for r in probe if r["level_eq_stop"])
    ib = sum(1 for r in probe if r["intrabar_fill"])
    L += ["",
          "`level == stop` on %d of %d signals (%.1f%%) — the default `BNR_STOP_MODE=\"level\"`"
          % (eq, len(probe), eq / len(probe) * 100),
          "with `intrabar_stop()` leaving the stop alone. On the other %.1f%% the stop had"
          % (100 - eq / len(probe) * 100),
          "collapsed onto the entry bar's own extreme, or the setup was an order block, and",
          "the two lines are different prices — which is why the branch could not keep",
          "reusing `sig[\"stop\"]` as \"the level\".",
          "The fill was taken at the level rather than the close (`bar_extreme_veto` or",
          "ON WATCH — the engine's only model of \"taken intrabar\") on %d (%.1f%%)."
          % (ib, ib / len(probe) * 100), ""]

    # --- 3. the book
    L += ["", "## 3. The book", "",
          "| arm | signals | traded | W | L | scratch | win rate | mean R | total R | green months |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    arms = [("canonical `research/bt2y_trades.json`", CANON), (ARM_LABEL["off"], b_off)]
    if lvl:
        arms.append((ARM_LABEL["level"], book(lvl["trades"])))
    for name, b in arms:
        L.append("| %s | %d | %d | %d | %d | %d | %.1f%% | %+.4fR | %+.2fR | %d/%d |"
                 % (name, b["signals"], b["traded"], b["w"], b["l"],
                    b["scratch"], b["wr"], b["meanr"], b["totr"], b["green"], b["months"]))
    L += ["",
          "Win rate is of DECIDED trades — 538/1011 = 53.2%. The 52.95% that also",
          "circulates is 538/1016 with the scratches left in the denominator; a scratch",
          "is neither. Both move when scratches appear, in opposite directions, so this",
          "report prints the decided one and says so.", ""]
    if lvl:
        bl = book(lvl["trades"])
        d = {k: bl[k] - b_off[k] for k in ("traded", "w", "l", "scratch")}
        fo, fl = off["meta"]["arm84_funnel"], lvl["meta"]["arm84_funnel"]
        L += ["**Delta, level arm minus off:** %+d traded · %+d W · %+d L · %+d scratch · "
              "win rate %+.1f pt · mean R %+.4f · total R %+.2f."
              % (d["traded"], d["w"], d["l"], d["scratch"], bl["wr"] - b_off["wr"],
                 bl["meanr"] - b_off["meanr"], bl["totr"] - b_off["totr"]), "",
              "The win rate moves for a reason that is not a win: %d losses left the"
              % (-d["l"]),
              "denominator as scratches. Read total R.", "",
              "**The 84% side of the rule** (\"no 84 percent\") — `backtest_week.ARM84_FUNNEL`,",
              "counted in-process at the single arm point:", "",
              "| arm-gate stage | off | level |", "|---|---:|---:|"]
        for k, lab in (("stopouts_counted", "counted full stop-outs"),
                       ("arming_setup", "on an arming setup (B&R / OCR)"),
                       ("grade_gate", "past the grade gate"),
                       ("armed", "past the 11:00 check = ARMED")):
            L.append("| %s | %d | %d |" % (lab, fo.get(k, 0), fl.get(k, 0)))
        n84o = sum(1 for r in off["trades"] if r["setup"] == "reentry_84_rule")
        n84l = sum(1 for r in lvl["trades"] if r["setup"] == "reentry_84_rule")
        L += ["| **produced a re-entry signal** | **%d** | **%d** |" % (n84o, n84l), ""]
    # --- 4. the verdict
    L += ["", "## 4. Why the rule cannot be expressed here", "",
          "`Trading-Bot-Rulesets.md`, \"Austin's Trading Rules\", clause 2 — the rule as it",
          "was written down, and it is the whole answer:",
          "",
          "> **Entry is the close, except on an extreme close.** Normally enter on the",
          "> candle close. When a fast candle would close at the session high (long) or low",
          "> (short), enter intrabar at the level instead — *\"you want it to look like it",
          "> will close above that.\"* **If the bar then closes back beyond the level, scratch",
          "> out at that close**; a scratch is not a loss and does not arm the 84% rule.",
          "",
          "The scratch is the correction for a bet made *without* knowing the bar's close.",
          "Austin commits mid-candle on a guess about where it will settle; when the guess is",
          "wrong he pays a scratch. **The backtest never makes that guess.** It reads bar `i`",
          "complete, requires a close through the level before it will enter, and only then",
          "back-dates the FILL to the level via `fill_price`. It gets, for free, the exact",
          "information the scratch exists to correct — so the losing branch of Austin's bet",
          "never appears in the book. `detect_break_retest`'s `no_confirm_close` return IS",
          "the scratch, taken before the fill instead of after it.",
          "",
          "That is what the section-1 table says numerically. It is not a threshold that",
          "wants widening and there is no near-miss population to recover: the condition is",
          "consumed upstream, exactly the way `break_then_rejection` is consumed by",
          "`_break_bar` in `research/p2_threshold_sweep.md`.",
          "",
          "**So the branch is not fixable — it is answering a question the backtest does not",
          "have.** It was deleted. Two consequences worth writing down:",
          "",
          "1. **The backtest is optimistic on ON WATCH entries, in count.** %d of %d created"
          % (ib, len(probe)),
          "   trades (%.1f%%) were filled at the level rather than the close. Live, some"
          % (ib / len(probe) * 100),
          "   share of those commitments would have closed back and scratched; the replay",
          "   simply never opens them. The omission is roughly R-neutral (a scratch is near",
          "   flat) but it means the live fire count will exceed the backtest's.",
          "2. **Nothing in the live path implements the rule either.** `paper_trader.py`",
          "   marks positions on wicks against `stock_stop` and has no scratch outcome at",
          "   all, and `live_scanner.py` only reacts to `stop` / target. If Austin wants this",
          "   rule obeyed, that is where it has to go — and it needs an intrabar quote, not a",
          "   1-minute bar. Queued, not done here.",
          "",
          "## 5. What `ENTRY_SCRATCH` is, and what it is not", "",
          "It is **not** Austin's rule. It is the nearest question this engine can actually",
          "ask: *the bar AFTER entry closes back through the retested level.* That is a",
          "one-bar failure exit, not a fill correction, and it is shipped **OFF**. It exists",
          "so the deletion above costs no information — the numbers in section 3 are what a",
          "one-bar failure exit is worth over two years, and whether to want one is Austin's",
          "call, not the engine's.",
          "",
          "Two readings of \"the level\" were built. `ENTRY_SCRATCH=level` reads",
          "`sig[\"level_price\"]`, the structure that was actually retested — a new reported",
          "field, added because the dead branch had been reusing `sig[\"stop\"]`, which is the",
          "level only under `BNR_STOP_MODE=\"level\"` and never for the order block (stop = the",
          "far side of the block) or when `intrabar_stop()` collapsed the stop onto the entry",
          "bar's own low. `ENTRY_SCRATCH=stop` reads the stop, which is the dead branch's own",
          "line: it is measured but **not recommended**, because with the shipped stop mode",
          "the stop IS the level, so it does nothing but re-label ordinary close-based",
          "stop-outs as scratches — flatly against the settled rule that a stop-out happens",
          "when a candle closes beyond the stop.",
          "",
          "**And the measurement says leave it off.** The bar-1 close-back is a strong",
          "*descriptor* and a bad *trigger*: 70 of the 257 traded signals that close back",
          "through the level go on to win anyway, and cutting them at that close — clamped",
          "at the stop, so never worse than the stop-out it replaced — still costs more than",
          "the 47 first-bar stop-outs it tidies up. The band it targets earns +0.1205R by",
          "being left alone; scratching it books roughly −0.50R apiece. This is the same",
          "shape G7 and G9 found on the exit side: the incumbent management is already at",
          "the top of its family, and the constraint is information at entry.",
          "",
          "`research/test_entry_scratch.py` pins all of it on synthetic bars: the entry bar",
          "closing through both lines on each side, the shipped default booking the",
          "close-back bar as a −1.00R stop-out, and each band of the armed flag.",
          "",
          "## 6. What this does not say", "",
          "1. **The rule is not wrong.** Austin's clause 2 is a live-execution rule and it is",
          "   correct as stated. Only the backtest cannot hold it.",
          "2. **A scratch is not a win.** It leaves the win-rate denominator, which lifts the",
          "   printed win rate without a single extra winner. Read the mean R and total R",
          "   columns in section 3, not the percentage.",
          "3. **Nothing here is ratified.** `ENTRY_SCRATCH` ships OFF and the book is",
          "   unchanged — `python backtest_2y.py --days 730 --out research/p8_scratch.json`",
          "   against `research/bt2y_trades.json` differs on 0 of 45,175 rows across 15",
          "   fields (`python research/p8_scratch.py diff`).",
          ""]
    return "\n".join(L), out_md


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--arm", choices=sorted(ARMS), required=True)
    r.add_argument("--days", type=int, default=730)
    r.add_argument("--out")
    p = sub.add_parser("report")
    p.add_argument("--out", default="research/p8_scratch.md")
    d = sub.add_parser("diff")
    d.add_argument("--a", default="research/bt2y_trades.json")
    d.add_argument("--b", default="research/p8_scratch.json")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.arm, a.days, a.out or DEFAULT_OUT[a.arm])
    elif a.cmd == "diff":
        sys.exit(diff(a.a, a.b))
    else:
        text, path = report(a.out)
        (ROOT / path).write_text(text + "\n", encoding="utf-8")
        print("wrote %s (%d lines)" % (path, text.count("\n") + 1))


if __name__ == "__main__":
    main()
