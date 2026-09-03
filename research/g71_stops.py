"""G71 / OMEN 7.1 blocker 1 -- WHERE THE STOP GOES, and what to risk on it.

Austin, 2026-08-29:

    "stops go where they make sense. you know what makes sense from my marks,
     the rules. from my head right now the answer is level, bottom of candle
     entered on, pivot structure, and you decide which one based on the best
     risk to reward tradable. you pick a disaster stop. if im not trading fixed
     2:1 on every single trade, then maybe i have the wrong idea risking 1k
     everytime or 1.25k."

Four families, one selector, one disaster sweep, one sizing answer.

    S1  broken_level      the level the setup broke and retested
    S2  candle_entered    the bottom of the candle entered on (top for puts)
    S3  pivot_structure   the nearest live swing low under the entry (high, puts)
    S4  best_rr           whichever of S1-S3 gives the best RR to the NEAREST
                          REAL target, subject to a disaster-stop ceiling and a
                          tradability floor

S1 and S2 already exist in the engine as `signal_runner.STOP_PLACEMENT`
(`broken_level` / `candle_entered`, T24, default `entry_bar`). S3 and S4 do NOT
-- T24 closed with "his `stop_src` vocabulary is a FOURTH placement ... that is
a ticket, not a finding". This script is that ticket, and it adds them by
MONKEYPATCHING `signal_runner.placed_stop` inside a child process. Nothing in
the shipped engine is edited: `STOP_PLACEMENT` still defaults to `entry_bar`,
and an arm that does not ask for a patch does not get one.

WHY placed_stop IS THE RIGHT SEAM
---------------------------------
It is called BEFORE the fill is priced and before the grade is computed, so a
placement flows through `min_risk_floor`, the tight-stop skip, the no-repeat
level key and the R denominator -- which is the whole point. `intrabar_stop`
still runs behind every arm, exactly as it does on the shipped book.

THE ONE THING THAT IS NOT REIMPLEMENTED
---------------------------------------
The stop FILL. Every arm books through `stop_rule.stop_fill_price()` via
`backtest_week._stop_fill_px`, and the resting disaster stop through
`stop_rule.disaster_stop_price` / `disaster_stop_hit`. This script never
computes an exit price.

USAGE
-----
    python research/g71_stops.py child --arm S3_pivot --out research/_g71s_S3_pivot.json
    python research/g71_stops.py run            # launch every arm (parallel)
    python research/g71_stops.py spread         # Corwin-Schultz 1-min spread
    python research/g71_stops.py analyse        # the tables
    python research/g71_stops.py report         # write research/g71_stops.md
    python research/g71_stops.py --selfcheck

REUSED, NEVER REIMPLEMENTED
---------------------------
    backtest_2y.main                      the replay
    research.a2_bt2y_summary.book         the whole-book money read
    signal_runner.pivot_levels            the swing-structure definition (T10)
    stop_rule.*                           the trigger, the fill, the floor
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT_MD = os.path.join(HERE, "g71_stops.md")
DIAG_SUFFIX = "_diag.json"

# ---------------------------------------------------------------------------
# Tradability constants. BOTH are assumptions and both are swept in the report.
# ---------------------------------------------------------------------------
# "too tight to be tradable": Austin's own worry. Two readings, both reported.
#
# (1) THE REPO'S OWN TOLERANCE UNIT. CLAUDE.md: "One tolerance unit: 25% of the
#     previous candle's range (BAR_EXTREME_FRAC)". A stop closer to the entry
#     than the noise band the engine already treats as "the same price" is not
#     a stop, it is a coin flip. This is the PRIMARY definition because it is
#     the project's own number, not one invented here.
#
# (2) THE MECHANICAL ONE. One average spread + one tick of slippage. The tick
#     is $0.01. The spread is measured per symbol from the archive with the
#     Corwin-Schultz (2012) high-low estimator on consecutive 1-minute RTH
#     bars -- `spread` subcommand -- so it is a number off the tape rather than
#     a guess. The instrument is OPTIONS, so the underlying move has to also
#     cover the option's own spread: at delta d and an option spread of $s the
#     equivalent underlying distance is s/d, and the report sweeps that ladder
#     rather than picking one.
MIN_TRADABLE_ABS = float(os.getenv("G71_MIN_STOP_ABS", "0.05"))
# S4's disaster-stop CEILING: no candidate stop may sit further from the entry
# bar's close than this fraction of price. T24 put the shipped book's p90
# |entry-stop| at 0.405% of entry, so 0.60% is a real ceiling that still admits
# the wide tail. Swept in the report.
MAX_STOP_PCT = float(os.getenv("G71_MAX_STOP_PCT", "0.0060"))

# arm -> (env overrides, custom placement or None)
ARMS = {
    # --- the four families -------------------------------------------------
    "S0_shipped": ({}, None),
    "S1_level":   ({"STOP_PLACEMENT": "broken_level"}, None),
    "S2_candle":  ({"STOP_PLACEMENT": "candle_entered"}, None),
    "S3_pivot":   ({}, "pivot_structure"),
    "S4_bestrr":  ({}, "best_rr"),
    # --- the disaster-stop sweep (all on the shipped placement) ------------
    "D_off":      ({"DISASTER_STOP": "0"}, None),
    "D_075":      ({"DISASTER_STOP_R": "0.75"}, None),
    "D_125":      ({"DISASTER_STOP_R": "1.25"}, None),
    "D_150":      ({"DISASTER_STOP_R": "1.50"}, None),
    "D_200":      ({"DISASTER_STOP_R": "2.00"}, None),
}
FAMILY_ARMS = ["S0_shipped", "S1_level", "S2_candle", "S3_pivot", "S4_bestrr"]
DISASTER_ARMS = ["D_off", "D_075", "S0_shipped", "D_125", "D_150", "D_200"]
DISASTER_LABEL = {"D_off": "no resting order (clamp only, -1.25R)",
                  "D_075": "resting at -0.75R", "S0_shipped": "resting at -1.00R (shipped)",
                  "D_125": "resting at -1.25R", "D_150": "resting at -1.50R",
                  "D_200": "resting at -2.00R"}


def arm_out(arm):
    return os.path.join(HERE, "_g71s_%s.json" % arm)


# ---------------------------------------------------------------------------
# The two new placements. Installed by monkeypatch, in the CHILD only.
# ---------------------------------------------------------------------------
_RUNNER = [None]
PICKS = Counter()      # which family S4 chose
REASONS = Counter()    # why a candidate was rejected


def _valid(cand, close, is_long):
    """A stop must sit on the LOSING side of the bar's close -- the same test
    `signal_runner.placed_stop` applies, copied so the arms agree."""
    if cand is None:
        return False
    return (cand < close) if is_long else (cand > close)


def _pivot_stop(runner, candle, is_long):
    """S3. The nearest LIVE swing low below the close (high above, for puts).

    `signal_runner.pivot_levels` is the engine's own T10 definition of a swing,
    including its no-lookahead `as_of` guarantee -- a pivot needs
    PIVOT_STRENGTH bars to its RIGHT before it exists. Not reimplemented here."""
    import signal_runner as sr
    if runner is None or candle is None:
        return None
    cs = runner.candles
    here = len(cs) - 1
    ps = sr.pivot_levels(cs, as_of=here, lookback=sr.PIVOT_LOOKBACK)
    want = "low" if is_long else "high"
    px = [p["price"] for p in ps if p["kind"] == want]
    px = [p for p in px if _valid(p, candle.close, is_long)]
    if not px:
        return None
    return max(px) if is_long else min(px)


def _nearest_target(runner, candle, is_long):
    """The nearest REAL level beyond the entry bar's close, in the direction of
    the trade. Same level set `backtest_week` builds its runner target from:
    the named levels, the live pivots, and the next psychological whole dollar.

    This is what makes "best risk to reward" a measurable phrase. The engine's
    own target is `entry +/- 2 x risk` (backtest_week.py:836) -- a blind 2R that
    moves with the stop, so under it EVERY stop scores exactly 2.00 RR and the
    words have no content. That is Austin's own complaint, in code."""
    if runner is None or candle is None:
        return None
    c = candle.close
    pool = [l for l in getattr(runner, "_active_levels", []) if l]
    pool += [p for p in getattr(runner, "_pivot_prices", []) if p]
    pool.append(math.floor(c) + 1.0 if is_long else math.ceil(c) - 1.0)
    beyond = [p for p in pool if ((p > c) if is_long else (p < c))]
    if not beyond:
        return None
    return min(beyond) if is_long else max(beyond)


def _best_rr(runner, candle, is_long, level_stop, structural_stop):
    """S4. "you decide which one based on the best risk to reward tradable."

    Candidates: S1 (the broken level), S2 (the candle entered on), S3 (pivot
    structure). A candidate must be
        * on the losing side of the close                     -- it is a stop
        * at least MIN_TRADABLE_ABS away                      -- TRADABLE
        * no further than MAX_STOP_PCT of price               -- the DISASTER
                                                                 CEILING
    and among the survivors the winner maximises

        RR = (nearest real target - close) / (close - stop)

    With a FIXED target the numerator is shared, so this is arithmetically
    "the tightest stop that is still tradable". That is not a bug in the
    selector, it is the answer: RR-maximising and stop-tightening are the same
    operation once the target stops moving with the stop. The report says so
    rather than hiding it behind a scoring function."""
    if candle is None:
        return structural_stop
    c = candle.close
    cands = {"level": level_stop,
             "candle": candle.low if is_long else candle.high,
             "pivot": _pivot_stop(runner, candle, is_long)}
    ceiling = MAX_STOP_PCT * c
    ok = {}
    for k, v in cands.items():
        if not _valid(v, c, is_long):
            REASONS[k + ":wrong_side"] += 1
            continue
        d = abs(c - v)
        if d < MIN_TRADABLE_ABS:
            REASONS[k + ":too_tight"] += 1
            continue
        if d > ceiling:
            REASONS[k + ":past_ceiling"] += 1
            continue
        ok[k] = v
    if not ok:
        PICKS["fallback_structural"] += 1
        return structural_stop
    tgt = _nearest_target(runner, candle, is_long)
    if tgt is None:
        PICKS["no_target_tightest"] += 1
        return max(ok.values()) if is_long else min(ok.values())
    num = abs(tgt - c)
    best = max(ok.items(), key=lambda kv: num / abs(c - kv[1]))
    PICKS[best[0]] += 1
    return best[1]


def install(placement):
    """Monkeypatch `signal_runner.placed_stop`. CHILD PROCESS ONLY."""
    import signal_runner as sr
    orig_detect = sr.SignalRunner.detect_signals

    def detect(self):
        _RUNNER[0] = self
        return orig_detect(self)
    sr.SignalRunner.detect_signals = detect

    orig_placed = sr.placed_stop

    def patched(setup, structural_stop, candle, is_long,
                level_stop=None, ocr_stop=None):
        r = _RUNNER[0]
        if placement == "pivot_structure":
            cand = _pivot_stop(r, candle, is_long)
            if cand is None or candle is None:
                PICKS["fallback_structural"] += 1
                return structural_stop
            PICKS["pivot"] += 1
            return cand
        if placement == "best_rr":
            return _best_rr(r, candle, is_long, level_stop, structural_stop)
        return orig_placed(setup, structural_stop, candle, is_long,
                           level_stop=level_stop, ocr_stop=ocr_stop)
    sr.placed_stop = patched
    # The detectors imported the name at module scope? No -- they call
    # `placed_stop(...)` by global lookup inside signal_runner, so rebinding the
    # module attribute is enough. Asserted by --selfcheck.


# ---------------------------------------------------------------------------
# child
# ---------------------------------------------------------------------------
def child(arm, out):
    env_over, placement = ARMS[arm]
    for k, v in env_over.items():
        os.environ[k] = v
    if placement:
        install(placement)
    import backtest_2y
    sys.argv = ["backtest_2y.py", "--out", out]
    backtest_2y.main()
    diag = {"arm": arm, "picks": dict(PICKS), "reasons": dict(REASONS),
            "min_tradable_abs": MIN_TRADABLE_ABS, "max_stop_pct": MAX_STOP_PCT}
    with open(out.replace(".json", "") + DIAG_SUFFIX, "w") as f:
        json.dump(diag, f, indent=1)


def run(arms, jobs=5):
    todo = [a for a in arms if not os.path.exists(arm_out(a))]
    print("running %d arms, %d already on disk" % (len(todo), len(arms) - len(todo)))
    procs = []
    for a in todo:
        cmd = [sys.executable, os.path.join(HERE, "g71_stops.py"), "child",
               "--arm", a, "--out", arm_out(a)]
        log = open(os.path.join(HERE, "_g71s_%s.log" % a), "w")
        procs.append((a, subprocess.Popen(cmd, cwd=ROOT, stdout=log,
                                          stderr=subprocess.STDOUT), log))
        while sum(1 for _, p, _ in procs if p.poll() is None) >= jobs:
            procs[0][1].wait(timeout=1200)
    for a, p, log in procs:
        p.wait()
        log.close()
        print("%-12s rc=%s" % (a, p.returncode))


# ---------------------------------------------------------------------------
# the money read
# ---------------------------------------------------------------------------
def load(arm):
    with open(arm_out(arm)) as f:
        return json.load(f)["trades"]


def iso_week(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return "%d-W%02d" % (y, w)


def drawdown(rs):
    """Max peak-to-trough of the cumulative-R curve, in R."""
    peak = cum = 0.0
    dd = 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    return dd


def pct(xs, p):
    if not xs:
        return 0.0
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))
    return s[i]


def book(rows, spreads=None):
    """Whole-book money read + the stop-geometry read this ticket adds.

    The money half is `research.a2_bt2y_summary.book`, imported not copied."""
    from research.a2_bt2y_summary import book as money
    b = money(rows)
    tr = sorted((r for r in rows if r["traded"]), key=lambda r: (r["day"], r["et"]))
    rs = [r["r"] for r in tr]
    by_w = defaultdict(float)
    for r in tr:
        by_w[iso_week(r["day"])] += r["r"]
    dist = [abs(r["entry"] - r["stop"]) for r in tr]
    dpct = [abs(r["entry"] - r["stop"]) / r["entry"] * 100 for r in tr if r["entry"]]
    b.update({
        "weeks_green": sum(1 for v in by_w.values() if v > 0), "weeks": len(by_w),
        "maxdd_r": round(drawdown(rs), 2),
        "maxdd_usd": round(drawdown(rs) * 1000),
        "stop_p10": round(pct(dist, 10), 3), "stop_med": round(pct(dist, 50), 3),
        "stop_p90": round(pct(dist, 90), 3),
        "stop_mean": round(statistics.fmean(dist), 4) if dist else 0.0,
        "stoppct_p10": round(pct(dpct, 10), 3), "stoppct_med": round(pct(dpct, 50), 3),
        "stoppct_p90": round(pct(dpct, 90), 3),
    })
    if spreads is not None:
        b.update(tightness(tr, spreads))
    return b


def tightness(tr, spreads):
    """How often the stop is TOO TIGHT to be tradable. Two readings.

    (1) noise: |entry-stop| < BAR_EXTREME_FRAC x the entry bar's own range.
        The repo's ONE tolerance unit. Needs the bar, so it is computed in
        `bar_tightness` off the archive, not here.
    (2) mech:  |entry-stop| < (one average spread + one tick), the spread from
        Corwin-Schultz per symbol."""
    n = len(tr)
    out = {}
    tick = 0.01
    hit = 0
    for r in tr:
        s = spreads.get(r["sym"], {}).get("spread_abs")
        if s is None:
            continue
        if abs(r["entry"] - r["stop"]) < s + tick:
            hit += 1
    out["tight_mech"] = hit
    out["tight_mech_pct"] = round(hit / n * 100, 2) if n else 0.0
    # the OPTIONS ladder: an option spread of $s at delta d needs s/d of
    # underlying to cross, and a round trip needs twice that.
    for lab, need in (("0.05", 0.20), ("0.10", 0.40), ("0.15", 0.60)):
        k = sum(1 for r in tr if abs(r["entry"] - r["stop"]) < need)
        out["tight_opt_" + lab] = k
        out["tight_opt_%s_pct" % lab] = round(k / n * 100, 2) if n else 0.0
    return out


# ---------------------------------------------------------------------------
# Corwin-Schultz spread, off the archive. No quotes exist in this repo; this is
# the standard high-low estimator, on consecutive 1-minute RTH bars.
# Corwin & Schultz (2012), "A Simple Way to Estimate Bid-Ask Spreads from Daily
# High and Low Prices", Journal of Finance 67(2).
# ---------------------------------------------------------------------------
SPREAD_JSON = os.path.join(HERE, "_g71s_spread.json")


def corwin_schultz(bars):
    """Per-day estimate from consecutive 1-min bars. Returns proportional
    spread (a fraction of price), or None."""
    k1 = 4 * math.log(2)
    k2 = math.sqrt(8 / math.pi)
    est = []
    for i in range(len(bars) - 1):
        a, b = bars[i], bars[i + 1]
        hi2, lo2 = max(a.high, b.high), min(a.low, b.low)
        if lo2 <= 0 or a.low <= 0 or b.low <= 0:
            continue
        beta = math.log(a.high / a.low) ** 2 + math.log(b.high / b.low) ** 2
        gamma = math.log(hi2 / lo2) ** 2
        den = 3 - 2 * math.sqrt(2)
        alpha = (math.sqrt(2 * beta) - math.sqrt(beta)) / den - math.sqrt(gamma / den)
        s = 2 * (math.exp(alpha) - 1) / (1 + math.exp(alpha))
        # Corwin-Schultz produces negative point estimates whenever the
        # two-bar range is small relative to the single-bar ranges. The paper's
        # own treatment is to set those to zero rather than discard them --
        # discarding keeps only the upward noise and biases the estimate up.
        est.append(max(0.0, s))
    _ = (k1, k2)
    return statistics.fmean(est) if est else None


def spread_scan(days=90):
    import polygon_feed as pf
    import signal_runner as sr
    from universe import ALL_SYMS, has_archive
    out = {}
    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    for sym in syms:
        d = os.path.join(ROOT, "data_archive", sym)
        if not os.path.isdir(d):
            continue
        ds = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv"))[-days:]
        ests, px = [], []
        for day in ds:
            try:
                rth = pf.rth(pf.fetch_day(sym, day))
            except Exception:
                continue
            w = [c for c in rth
                 if "09:30" <= sr.bar_time(c.timestamp)[:5] < "11:00"]
            if len(w) < 30:
                continue
            e = corwin_schultz(w)
            if e:
                ests.append(e)
                px.append(statistics.fmean([c.close for c in w]))
        if ests:
            p = statistics.median(px)
            out[sym] = {"spread_prop": round(statistics.median(ests), 6),
                        "px": round(p, 2),
                        "spread_abs": round(statistics.median(ests) * p, 4),
                        "n_days": len(ests)}
        print("%-6s %s" % (sym, out.get(sym)))
    with open(SPREAD_JSON, "w") as f:
        json.dump(out, f, indent=1)
    return out


def load_spreads():
    if os.path.exists(SPREAD_JSON):
        with open(SPREAD_JSON) as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# noise-band tightness: |entry-stop| against 25% of the entry bar's own range
# ---------------------------------------------------------------------------
def bar_tightness(rows, cache={}):
    """Fraction of traded rows whose stop sits inside the repo's ONE tolerance
    unit -- BAR_EXTREME_FRAC (25%) of the entry bar's own high-low range."""
    import polygon_feed as pf
    import signal_runner as sr
    tr = [r for r in rows if r["traded"]]
    hit = tot = 0
    ratios = []
    for r in tr:
        key = (r["sym"], r["day"])
        if key not in cache:
            try:
                cache[key] = pf.rth(pf.fetch_day(r["sym"], r["day"]))
            except Exception:
                cache[key] = []
        bars = cache[key]
        i = r.get("entry_i")
        if not bars or i is None or i >= len(bars):
            continue
        rng = bars[i].high - bars[i].low
        if rng <= 0:
            continue
        d = abs(r["entry"] - r["stop"])
        ratios.append(d / rng)
        tot += 1
        if d < sr.BAR_EXTREME_FRAC * rng:
            hit += 1
    return {"n": tot, "tight_noise": hit,
            "tight_noise_pct": round(hit / tot * 100, 2) if tot else 0.0,
            "barrange_p10": round(pct(ratios, 10), 3),
            "barrange_med": round(pct(ratios, 50), 3),
            "barrange_p90": round(pct(ratios, 90), 3)}


# ---------------------------------------------------------------------------
# HIS OWN MARKED STOPS, classified against the four families.
# "you know what makes sense from my marks, the rules."
# ---------------------------------------------------------------------------
HIS_JSON = os.path.join(HERE, "_g71s_his.json")


def his_marks():
    """For every mark Austin left that carries an entry bar AND a stop PRICE,
    which of S1/S2/S3 is that stop actually sitting on?

    Corpora, loader and the "is this a price or a typed note" test are
    `research.p25_midcandle_entry` -- the same ones T24 used, imported not
    reimplemented, so the two reports are comparable. Read-only.

    MATCH TOLERANCE is the repo's ONE tolerance unit: BAR_EXTREME_FRAC (25%) of
    the ENTRY BAR's own range. Inside that band two prices are the same price
    everywhere else in this engine, so they are the same price here."""
    import polygon_feed as pf
    import signal_runner as sr
    from omen_bot import OpeningRangeAnalyzer
    from research import p25_midcandle_entry as p25
    from research.t4_engine_recall import rth_candles

    rows, skipped = [], Counter()
    for row in p25.iter_marks():
        if not p25.usable(row):
            skipped["no_entry"] += 1
            continue
        stop = p25.clean_stop(row)
        if stop is None:
            skipped["stop_is_a_note"] += 1
            continue
        sym, day, i = row["symbol"], row["date"], row["entry_i"]
        bars = rth_candles(sym, day)
        if not bars or i < 0 or i >= len(bars):
            skipped["no_bars"] += 1
            continue
        bar = bars[i]
        rng = bar.high - bar.low
        if rng <= 0:
            skipped["flat_bar"] += 1
            continue
        entry = float(row["entry_p"])
        long_side = (row.get("side") or "L").upper().startswith("L")
        # S2 -- the candle entered on
        s2 = bar.low if long_side else bar.high
        # S3 -- live pivot structure, the engine's own T10 definition, no lookahead
        ps = sr.pivot_levels(bars, as_of=i, lookback=sr.PIVOT_LOOKBACK)
        want = "low" if long_side else "high"
        cand = [p["price"] for p in ps if p["kind"] == want]
        cand = [p for p in cand if (p < entry if long_side else p > entry)]
        s3 = (max(cand) if long_side else min(cand)) if cand else None
        # S1 -- the six named levels
        try:
            raw = pf.fetch_day(sym, day)
            pmh, pml = pf.premarket_hi_lo(raw)
        except Exception:
            pmh = pml = None
        orh, orl = OpeningRangeAnalyzer.get_opening_range(bars)
        levels = [l for l in (pmh, pml, orh, orl) if l]
        s1 = None
        side_ok = [l for l in levels if (l < entry if long_side else l > entry)]
        if side_ok:
            s1 = max(side_ok) if long_side else min(side_ok)
        tol = sr.BAR_EXTREME_FRAC * rng
        d = {"sym": sym, "day": day, "side": "L" if long_side else "S",
             "entry": entry, "stop": stop,
             "risk": round(abs(entry - stop), 4),
             "risk_pct": round(abs(entry - stop) / entry * 100, 4),
             "risk_barrange": round(abs(entry - stop) / rng, 3),
             "setup": row.get("setup") or row.get("setup_type") or "?",
             "stop_src": row.get("stop_src") or "",
             "d_s1": round(abs(stop - s1), 4) if s1 is not None else None,
             "d_s2": round(abs(stop - s2), 4),
             "d_s3": round(abs(stop - s3), 4) if s3 is not None else None,
             "tol": round(tol, 4)}
        hits = [k for k in ("d_s1", "d_s2", "d_s3")
                if d[k] is not None and d[k] <= tol]
        near = [(d[k], k) for k in ("d_s1", "d_s2", "d_s3") if d[k] is not None]
        d["matches"] = hits
        d["nearest"] = min(near)[1] if near else None
        rows.append(d)
    out = {"n": len(rows), "skipped": dict(skipped), "rows": rows,
           "match_counts": dict(Counter(m for r in rows for m in r["matches"])),
           "none_matched": sum(1 for r in rows if not r["matches"]),
           "nearest_counts": dict(Counter(r["nearest"] for r in rows)),
           "risk_med": round(statistics.median([r["risk"] for r in rows]), 4) if rows else 0,
           "risk_pct_med": round(statistics.median([r["risk_pct"] for r in rows]), 4) if rows else 0,
           "risk_barrange_med": round(statistics.median([r["risk_barrange"] for r in rows]), 3) if rows else 0}
    with open(HIS_JSON, "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
    return out


# ---------------------------------------------------------------------------
# HELD-OUT S RECALL. DIRECTION.md: recall is the governing gate, and every
# in-sample gain this project has recorded bought zero held-out recall. So this
# runs before any money number is acted on.
#
# Cards, scorer and counting rule are `research.t70_test1_score` and
# `research.t24_stop_taxonomy.test1_counts`, imported not reimplemented, so this
# table is directly comparable to T24's.
# ---------------------------------------------------------------------------
TEST1_JSON = os.path.join(HERE, "_g71s_test1.json")


def test1_child(arm):
    env_over, placement = ARMS[arm]
    for k, v in env_over.items():
        os.environ[k] = v
    if placement:
        install(placement)
    from research import t70_test1_score as t70
    print(json.dumps(t70.score_all(t70.load_cards())))


def run_test1(arms=None):
    from research.t24_stop_taxonomy import test1_counts
    out = {}
    if os.path.exists(TEST1_JSON):
        with open(TEST1_JSON) as f:
            out = json.load(f)
    for arm in (arms or list(ARMS)):
        if arm in out:
            continue
        res = subprocess.run(
            [sys.executable, os.path.join(HERE, "g71_stops.py"),
             "test1child", "--arm", arm],
            cwd=ROOT, capture_output=True, text=True)
        line = [l for l in res.stdout.splitlines() if l.startswith("[")]
        if not line:
            print("%-12s FAILED: %s" % (arm, res.stderr[-400:]))
            continue
        out[arm] = json.loads(line[-1])
        with open(TEST1_JSON, "w") as f:
            json.dump(out, f)
        print("%-12s %s" % (arm, test1_counts(out[arm])))
    return out


# ---------------------------------------------------------------------------
# PAIRED A/B. The arms share most of their rows, so an unpaired mean-R error
# bar (+/-0.17R on this book) is the wrong bar -- it prices variance the two
# arms have IN COMMON. Rows are matched on (symbol, day, entry time, setup),
# and the statistic is the mean of the per-row difference with its own SE.
# ---------------------------------------------------------------------------
def paired(a_rows, b_rows):
    key = lambda r: (r["sym"], r["day"], r["et"], r["setup"], r["dir"])
    A = {key(r): r["r"] for r in a_rows if r["traded"]}
    B = {key(r): r["r"] for r in b_rows if r["traded"]}
    both = set(A) & set(B)
    d = [B[k] - A[k] for k in both]
    if len(d) < 2:
        return {"n_pair": len(both), "delta": 0.0, "se": 0.0, "t": 0.0}
    m = statistics.fmean(d)
    se = statistics.stdev(d) / math.sqrt(len(d))
    return {"n_pair": len(both), "only_a": len(set(A) - set(B)),
            "only_b": len(set(B) - set(A)),
            "delta": round(m, 4), "se": round(se, 4),
            "t": round(m / se, 2) if se else 0.0}


# ---------------------------------------------------------------------------
# ROBUST money read. A tight stop inflates R by construction.
#
# signal_runner.py:889-892 already names this failure mode: a book "full of
# 2-cent stops on $100 stocks ... is an arithmetic artefact of R = |entry-stop|
# and not a tradeable edge". Any arm that MOVES the stop must be read with that
# in mind, so every family below is reported four ways:
#
#   meanr      the raw mean, as every other OMEN report computes it
#   medr       the median R -- immune to the tail
#   trim       the mean after dropping the top and bottom 1% of rows
#   cap10      the mean after clamping every R at +10.0. A 0DTE option cannot
#              actually return 192x the risk on a 90-minute intraday move; the
#              cap says "a 10-bagger is the most this instrument gives you"
#              and prices the arm under that assumption.
#   tradable   the raw mean over ONLY the rows whose stop sits outside the
#              repo's tolerance unit (>= BAR_EXTREME_FRAC x the entry bar's own
#              range). This is Austin's "too tight rr" worry, priced.
# ---------------------------------------------------------------------------
def robust(rows, tradable_ids=None):
    tr = [r for r in rows if r["traded"]]
    rs = sorted(r["r"] for r in tr)
    n = len(rs)
    k = max(1, n // 100)
    trim = rs[k:n - k] if n > 2 * k else rs
    out = {"n": n,
           "medr": round(statistics.median(rs), 4) if rs else 0.0,
           "trim": round(statistics.fmean(trim), 4) if trim else 0.0,
           "cap10": round(statistics.fmean([min(r, 10.0) for r in rs]), 4) if rs else 0.0,
           "zero_risk": sum(1 for r in tr if abs(r["entry"] - r["stop"]) < 1e-9),
           "top10_share": round(sum(rs[-10:]) / sum(rs) * 100, 1) if sum(rs) else 0.0,
           "maxr": round(rs[-1], 2) if rs else 0.0}
    if tradable_ids is not None:
        sub = [r for r in tr if (r["sym"], r["day"], r["et"], r["setup"]) in tradable_ids]
        srs = [r["r"] for r in sub]
        w = sum(1 for r in sub if r["out"] == "win")
        l = sum(1 for r in sub if r["out"] == "loss")
        out["tradable_n"] = len(sub)
        out["tradable_meanr"] = round(statistics.fmean(srs), 4) if srs else 0.0
        out["tradable_medr"] = round(statistics.median(srs), 4) if srs else 0.0
        out["tradable_wr"] = round(w / (w + l) * 100, 1) if (w + l) else 0.0
    return out


def tradable_set(rows, cache={}):
    """Row ids whose stop sits OUTSIDE the tolerance unit. Same bar read as
    `bar_tightness`, so the two numbers cannot disagree."""
    import polygon_feed as pf
    import signal_runner as sr
    ids = set()
    for r in rows:
        if not r["traded"]:
            continue
        key = (r["sym"], r["day"])
        if key not in cache:
            try:
                cache[key] = pf.rth(pf.fetch_day(r["sym"], r["day"]))
            except Exception:
                cache[key] = []
        bars = cache[key]
        i = r.get("entry_i")
        if not bars or i is None or i >= len(bars):
            continue
        rng = bars[i].high - bars[i].low
        if rng <= 0:
            continue
        if abs(r["entry"] - r["stop"]) >= sr.BAR_EXTREME_FRAC * rng:
            ids.add((r["sym"], r["day"], r["et"], r["setup"]))
    return ids


# ---------------------------------------------------------------------------
# SIZING. "maybe i have the wrong idea risking 1k everytime or 1.25k"
# ---------------------------------------------------------------------------
def sizing(rows, budget=1000.0):
    """Does R outcome depend on how wide the stop is?

    That is the whole sizing question. With FIXED $ risk, dollar P&L = R x $1k
    and stop width cancels out. Variable risk only beats it if R covaries with
    stop width -- so this measures the covariance directly, then prices three
    policies at EQUAL TOTAL DOLLARS RISKED so the comparison is not just
    leverage.

        fixed     $1,000 on every trade                (the shipped policy)
        contracts one fixed CONTRACT count -- risk in dollars is proportional
                  to |entry-stop|, which is what "size to the stop" does NOT
                  mean and what a trader who forgets to resize actually does
        inverse   risk inversely proportional to stop width (over-risk the
                  tight stops)
    """
    tr = sorted((r for r in rows if r["traded"]), key=lambda r: (r["day"], r["et"]))
    n = len(tr)
    dist = [abs(r["entry"] - r["stop"]) for r in tr]
    rs = [r["r"] for r in tr]
    # decile table
    order = sorted(range(n), key=lambda i: dist[i])
    dec = []
    for k in range(10):
        lo, hi = k * n // 10, (k + 1) * n // 10
        idx = order[lo:hi]
        sub = [rs[i] for i in idx]
        sd = [dist[i] for i in idx]
        w = sum(1 for i in idx if tr[i]["out"] == "win")
        l = sum(1 for i in idx if tr[i]["out"] == "loss")
        dec.append({"decile": k + 1, "n": len(idx),
                    "stop_lo": round(min(sd), 3), "stop_hi": round(max(sd), 3),
                    "meanr": round(statistics.fmean(sub), 4),
                    "wr": round(w / (w + l) * 100, 1) if (w + l) else 0.0})
    # correlation of R against stop width (Pearson; both are noisy, so the
    # decile table above is the one to read -- this is the one-number summary)
    try:
        corr = statistics.correlation(dist, rs)
    except Exception:
        corr = float("nan")
    pol = {}
    for name in ("fixed", "contracts", "inverse"):
        if name == "fixed":
            wts = [1.0] * n
        elif name == "contracts":
            m = statistics.fmean(dist)
            wts = [d / m for d in dist]
        else:
            m = statistics.fmean([1.0 / d for d in dist if d > 0])
            wts = [(1.0 / d) / m if d > 0 else 1.0 for d in dist]
        # cap leverage at 3x so one 2-cent stop cannot own the book
        wts = [min(w, 3.0) for w in wts]
        pnl = [rs[i] * wts[i] * budget for i in range(n)]
        risked = sum(wts) * budget
        cum, peak, dd = 0.0, 0.0, 0.0
        for p in pnl:
            cum += p
            peak = max(peak, cum)
            dd = min(dd, cum - peak)
        pol[name] = {"total_usd": round(sum(pnl)),
                     "risked_usd": round(risked),
                     "return_on_risk_pct": round(sum(pnl) / risked * 100, 2),
                     "maxdd_usd": round(dd),
                     "worst_trade_usd": round(min(pnl)),
                     "mean_usd": round(statistics.fmean(pnl), 2)}
    return {"n": n, "corr_r_vs_stopwidth": round(corr, 4), "deciles": dec,
            "policies": pol}


# ---------------------------------------------------------------------------
def analyse():
    spreads = load_spreads()
    out = {"spread_symbols": len(spreads), "arms": {}}
    for arm in ARMS:
        if not os.path.exists(arm_out(arm)):
            continue
        rows = load(arm)
        b = book(rows, spreads)
        d = arm_out(arm).replace(".json", "") + DIAG_SUFFIX
        if os.path.exists(d):
            with open(d) as f:
                b["diag"] = json.load(f)
        out["arms"][arm] = b
    for arm in ARMS:
        if arm not in out["arms"]:
            continue
        rows = load(arm)
        out["arms"][arm]["noise"] = bar_tightness(rows)
        out["arms"][arm]["robust"] = robust(rows, tradable_set(rows))
    if "S0_shipped" in out["arms"]:
        out["sizing"] = sizing(load("S0_shipped"))
    with open(os.path.join(HERE, "_g71s_analysis.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: {kk: vv for kk, vv in v.items()
                          if kk not in ("by_month", "diag", "noise")}
                      for k, v in out["arms"].items()}, indent=1))
    return out


def selfcheck():
    """Cheap invariants. No replay."""
    import signal_runner as sr
    from omen_bot import Candle
    ok = []
    # 1. rebinding the module attribute is enough -- the detectors look it up
    #    by global name, they do not hold a reference.
    src = open(os.path.join(ROOT, "signal_runner.py"), encoding="utf-8").read()
    ok.append(("placed_stop called by global lookup",
               "from signal_runner import placed_stop" not in src
               and src.count("placed_stop(") >= 7))
    # 2. _valid agrees with the shipped placed_stop's own side test
    ok.append(("_valid long", _valid(9.0, 10.0, True) and not _valid(11.0, 10.0, True)))
    ok.append(("_valid short", _valid(11.0, 10.0, False) and not _valid(9.0, 10.0, False)))
    # 3. best_rr picks the tightest tradable candidate when the target is fixed
    # close 100.00, ceiling = MAX_STOP_PCT x 100 = $0.60, floor = $0.05
    c = Candle(timestamp="2026-01-02 09:40:00", open=100.0, high=100.2,
               low=99.5, close=100.0, volume=1000)

    class R:
        candles = [c]
        _active_levels = [101.0]
        _pivot_prices = []
    got = _best_rr(R(), c, True, 99.7, 99.5)
    ok.append(("best_rr picks tightest tradable (99.7 over 99.5)", abs(got - 99.7) < 1e-9))
    # 4. a candidate inside the tradability floor is skipped, the other wins
    got2 = _best_rr(R(), c, True, 99.99, 99.5)
    ok.append(("best_rr skips a 1c stop, takes 99.5", abs(got2 - 99.5) < 1e-9))
    # 5. every candidate past the ceiling -> the structural stop stands
    c2 = Candle(timestamp="2026-01-02 09:40:00", open=100.0, high=100.2,
                low=98.0, close=100.0, volume=1000)

    class R2:
        candles = [c2]
        _active_levels = [101.0]
        _pivot_prices = []
    got3 = _best_rr(R2(), c2, True, 98.5, 97.0)
    ok.append(("best_rr rejects every stop past the ceiling", abs(got3 - 97.0) < 1e-9))
    # 6. pivot_levels no-lookahead is the engine's, not ours
    ok.append(("pivot_levels takes as_of", "as_of" in sr.pivot_levels.__code__.co_varnames))
    # 7. drawdown
    ok.append(("drawdown", abs(drawdown([1, -3, 2]) + 3) < 1e-9))
    bad = [n for n, v in ok if not v]
    for n, v in ok:
        print("%s  %s" % ("ok  " if v else "FAIL", n))
    return 0 if not bad else 1


def _paired_cap(a_rows, b_rows, cap):
    key = lambda r: (r["sym"], r["day"], r["et"], r["setup"], r["dir"])
    A = {key(r): r["r"] for r in a_rows if r["traded"]}
    B = {key(r): r["r"] for r in b_rows if r["traded"]}
    both = set(A) & set(B)
    d = [min(B[k], cap) - min(A[k], cap) for k in both]
    if len(d) < 2:
        return {"n": len(d), "delta": 0.0, "se": 0.0, "t": 0.0}
    m = statistics.fmean(d)
    se = statistics.stdev(d) / math.sqrt(len(d))
    return {"n": len(d), "delta": round(m, 4), "se": round(se, 4),
            "t": round(m / se, 2) if se else 0.0}


def report():
    """Regenerate every table in research/g71_stops.md from the JSON artefacts.

    Prints them; the prose around them is written by hand. "If you publish a
    number, commit the script that made it" -- this is that script."""
    with open(os.path.join(HERE, "_g71s_analysis.json")) as f:
        an = json.load(f)
    A = an["arms"]
    base = load("S0_shipped")

    def row(k):
        b = A[k]
        r = b["robust"]
        n = b["noise"]
        return ("| `%s` | %d | %+0.4f | %+0.4f | %+0.4f | %.1f%% | %d/%d | %d/%d | %.1fR | %.3f | %.3f%% | %.2f%% | %.2f%% |"
                % (k, b["traded"], b["meanr"], r["medr"], r["cap10"], b["wr"],
                   b["months_green"], b["months"], b["weeks_green"], b["weeks"],
                   b["maxdd_r"], b["stop_mean"], b["stoppct_med"],
                   n["tight_noise_pct"], b["tight_opt_0.10_pct"]))

    print("\n### families\n")
    print("| arm | traded | mean R | med R | mean R capped at +10 | win% | months | weeks | maxDD | mean stop $ | med stop % | too tight (noise) | too tight (opt $0.05) |")
    print("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for k in FAMILY_ARMS:
        print(row(k))
    print("\n### disaster stop\n")
    print("| arm | where the order rests | traded | mean R | med R | win% | worst R | months | weeks | maxDD |")
    print("|---|---|--:|--:|--:|--:|--:|--:|--:|--:|")
    for k in DISASTER_ARMS:
        b = A[k]
        print("| `%s` | %s | %d | %+0.4f | %+0.4f | %.1f%% | %.2f | %d/%d | %d/%d | %.1fR |"
              % (k, DISASTER_LABEL[k], b["traded"], b["meanr"], b["robust"]["medr"],
                 b["wr"], b["worst"], b["months_green"], b["months"],
                 b["weeks_green"], b["weeks"], b["maxdd_r"]))
    print("\n### paired vs the shipped book\n")
    print("| arm | shared rows | delta mean R | SE | t | delta capped at +10R | SE | t |")
    print("|---|--:|--:|--:|--:|--:|--:|--:|")
    for k in [a for a in ARMS if a != "S0_shipped"]:
        if k not in A:
            continue
        rows = load(k)
        raw = _paired_cap(base, rows, 1e9)
        cap = _paired_cap(base, rows, 10.0)
        print("| `%s` | %d | %+0.4f | %0.4f | %+0.2f | %+0.4f | %0.4f | %+0.2f |"
              % (k, raw["n"], raw["delta"], raw["se"], raw["t"],
                 cap["delta"], cap["se"], cap["t"]))
    if os.path.exists(TEST1_JSON):
        from research.t24_stop_taxonomy import test1_counts
        with open(TEST1_JSON) as f:
            t1 = json.load(f)
        print("\n### held-out S recall (the governing gate)\n")
        print("| arm | S recall | false fire | entry match | symbol-days fired on |")
        print("|---|--:|--:|--:|--:|")
        for k in list(ARMS):
            if k not in t1:
                continue
            c = test1_counts(t1[k])
            print("| `%s` | %d/%d | %d/%d | %d/%d | %d |"
                  % (k, c["s_hit"], c["s_n"], c["x_fire"], c["x_n"],
                     c["entry_match"], c["graded"], c["day_prec_n"]))
    if os.path.exists(HIS_JSON):
        with open(HIS_JSON) as f:
            h = json.load(f)
        print("\n### where HIS OWN marked stops sit (n=%d)\n" % h["n"])
        print("| family | matches within one tolerance unit | nearest of the three |")
        print("|---|--:|--:|")
        for k, lab in (("d_s1", "S1 broken level"), ("d_s2", "S2 candle entered on"),
                       ("d_s3", "S3 pivot structure")):
            print("| %s | %d/%d | %d |" % (lab, h["match_counts"].get(k, 0), h["n"],
                                           h["nearest_counts"].get(k, 0)))
        print("| none of the three | %d/%d | - |" % (h["none_matched"], h["n"]))
    s = an["sizing"]
    print("\n### sizing: is fixed $1,000 right?\n")
    print("corr(R, |entry-stop|) = %+0.4f over n=%d\n" % (s["corr_r_vs_stopwidth"], s["n"]))
    print("| stop-width decile | n | stop $ range | mean R | win% |")
    print("|--:|--:|---|--:|--:|")
    for x in s["deciles"]:
        print("| %d | %d | %.3f - %.3f | %+0.4f | %.1f%% |"
              % (x["decile"], x["n"], x["stop_lo"], x["stop_hi"], x["meanr"], x["wr"]))
    print("\n| policy | total $ | $ risked | return on risk | max DD $ | worst trade $ |")
    print("|---|--:|--:|--:|--:|--:|")
    for k, v in s["policies"].items():
        print("| %s | %+d | %d | %.2f%% | %d | %d |"
              % (k, v["total_usd"], v["risked_usd"], v["return_on_risk_pct"],
                 v["maxdd_usd"], v["worst_trade_usd"]))
    sp = load_spreads()
    if sp:
        vals = sorted(v["spread_abs"] for v in sp.values())
        props = sorted(v["spread_prop"] for v in sp.values())
        print("\nCorwin-Schultz 1-min effective spread over %d symbols: median $%.4f (%.1f bp), "
              "range $%.4f - $%.4f\n" % (len(sp), statistics.median(vals),
                                          statistics.median(props) * 10000,
                                          vals[0], vals[-1]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="analyse",
                    choices=["child", "test1child", "run", "test1", "spread", "his", "analyse", "report"])
    ap.add_argument("--arm")
    ap.add_argument("--out")
    ap.add_argument("--jobs", type=int, default=5)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        sys.exit(selfcheck())
    if a.cmd == "child":
        child(a.arm, a.out)
    elif a.cmd == "run":
        run(list(ARMS), jobs=a.jobs)
    elif a.cmd == "spread":
        spread_scan()
    elif a.cmd == "his":
        his_marks()
    elif a.cmd == "test1child":
        test1_child(a.arm)
    elif a.cmd == "test1":
        run_test1()
    elif a.cmd == "report":
        report()
    else:
        analyse()


if __name__ == "__main__":
    main()
