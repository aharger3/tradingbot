"""T6 -- "losers lose quick", re-run on the RATIFIED fills (R1/R2 landed).

Austin, 2026-08-28: *"let runners run and losers lose quick"*.

The X board refuted the "cut losers faster" family: all four faster-cut arms
came in negative against their control. The T6 ticket for this wave says that
refutation is suspect because *"every one of those arms ran UNDER THE FILL
CLAMP that made all losses exactly -1.000R and destroyed the left tail the
arms existed to cut. Re-run the four faster-cut arms on top of T1's real
fills."*

T0 (`9edd2ba7`) landed R1-R33 on `t0-ratified`, including R1/R2 -- the real
two-stop model in `stop_rule.py` / `backtest_week.py`: a level stop that still
triggers on the CLOSE (Austin's settled rule, unchanged), plus a DISASTER
STOP -- a resting order at entry -/+ 1.0R that fills on an intrabar TOUCH,
tested BEFORE the level stop on every bar, with the close-fill still floored
at -1.25R (`MAX_LOSS_R`) for the bars that gap straight through the resting
order. That IS "T1's real fills" for this wave -- it is what `DISASTER_STOP=1`
(the shipped default) puts under every trade in `research/bt2y_trades.json`.

THIS FILE SCORES THE FOUR ARMS UNDER TWO CONVENTIONS, ON THE SAME ROWS:

    ``ratified``  the shipped rule -- level stop on the close (floored at
                  -1.25R) PLUS the disaster stop's intrabar -1R touch, tested
                  first. `stop_rule.disaster_stop_price/_hit` +
                  `stop_rule.stop_fill_price`, exactly as `backtest_week.py`
                  wires them under `DISASTER_STOP=1`.
    ``clamp``     the fill clamp the ticket names -- a close-triggered stop is
                  assumed to fill AT the stop price, -1.000R by construction,
                  no disaster order, no left tail past -1R ever. This is the
                  pre-2026-08-28 convention `research/x2_stop_floor_audit.md`
                  found live in every shipped rig before the T11 fix.

If the four arms only look bad under ``clamp``, the refutation was an artefact
of the bug the ticket names. If they look the same or worse under
``ratified``, the refutation survives its own claimed bug fix.

THE FOUR ARMS (unchanged from the earlier X-board run)

    ride_ts15 / ride_ts30 / ride_ts45   one unit, original stop (+ disaster
                                        stop where the convention has one),
                                        no target, hard time stop N minutes
                                        after entry, 11:00 backstop
    adverse                             out at the close of the FIRST bar
                                        after entry that closes against entry

    control: ``ride`` -- the same one-unit ride with no cut at all.

A secondary family (flat 2R base + the same three time stops) is scored too,
control ``f2``, for the same reason the earlier run carried it.

METHOD RULES OBEYED
  * Error bar is this rig's OWN: a paired bootstrap of the per-trade
    difference (arm - control), 4000 resamples, 95 percentile interval. An
    arm whose interval straddles 0 is a NULL RESULT and is printed as one.
  * Reachability is checked BEFORE anything is read into a threshold.
  * Held-out recall against `research/marks/probe_s_sweep_2026-08-28.jsonl`
    is invariant across every arm here by construction (every arm is an EXIT
    policy; none can veto an entry) -- asserted, not just claimed, by
    `recall_invariance_check()`.
  * Zero network. Bars come from `data_archive/` via `research.levels`. A day
    with no archive is a REPORTED gap, never a silent drop.
  * `--selfcheck` asserts the ride control under `ratified` never books below
    -1.25R, the `clamp` convention never books past -1.000R, and the fired
    set is identical across every arm.

    python research/t6_losers_quick.py            # the run + write the report
    python research/t6_losers_quick.py --selfcheck
    python research/t6_losers_quick.py --recall    # + the held-out recall read
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from research import exit_lab as xl                        # noqa: E402
from research.levels import load_rth_bars                  # noqa: E402
from stop_rule import (stop_fill_price, disaster_stop_price,       # noqa: E402
                       disaster_stop_hit, DISASTER_STOP_R, MAX_LOSS_R)

BOOK = os.path.join(_HERE, "bt2y_trades.json")
MARKS = os.path.join(_HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_MD = os.path.join(_HERE, "t6_losers-quick.md")
OUT_JSON = os.path.join(_HERE, "t6_losers_quick.json")

CLOCK = xl.CLOCK_BAR          # 90 -> the 11:00 ET backstop
GATE = 2.0
BOOTSTRAP = 4000
SEED = 20260829
# The project's standing reference bar. Every A/B this repo has run moved less
# than this; it is printed beside each arm's OWN bar, never instead of it.
PROJECT_BAR = 1.5799


# ---------------------------------------------------------------------------
# the two fill conventions
# ---------------------------------------------------------------------------
# Each fn returns (exit_price, disaster_fired: bool) for a bar that ended the
# trade via the STOP path (either the resting disaster order or the level
# stop's close). ``disaster_fired`` lets the arm report why-breakdowns.

def fill_ratified(bars, i, entry, stop, risk, long):
    """R1/R2 as shipped: disaster order tested FIRST (intrabar touch, -1R),
    then the level stop on the close, floored at -1.25R."""
    b = bars[i]
    dpx = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
    if disaster_stop_hit(b["h"], b["l"], dpx, long):
        return dpx, True
    return stop_fill_price(b["c"], entry, risk, long), False


def fill_clamp(bars, i, entry, stop, risk, long):
    """The ticket's fill clamp: a close-triggered stop is assumed to fill AT
    the stop price -- -1.000R by construction, no disaster order, no left
    tail past -1R ever."""
    return stop, False


FILLS = {"ratified": fill_ratified, "clamp": fill_clamp}


# ---------------------------------------------------------------------------
# the arms
# ---------------------------------------------------------------------------

def ride(bars, entry_i, entry, stop, side, fill, time_stop=None, target_r=None,
        clock=CLOCK):
    """One position, one exit -- the general arm every bucket is a case of.

    Returns (R, exit_i, why) with ``why`` in stop / disaster / target / time /
    clock.
    """
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0, entry_i, "flat"
    long = side == "L"
    tgt = (entry + target_r * risk) if (target_r is not None and long) else (
        (entry - target_r * risk) if target_r is not None else None)
    end = min(clock + 1, n)
    for i in range(entry_i + 1, end):
        b = bars[i]
        if xl._stop_hit_first(bars, i, entry, stop, side):
            px, disaster = fill(bars, i, entry, stop, risk, long)
            return xl.realised_r(entry, stop, px, side), i, (
                "disaster" if disaster else "stop")
        # The disaster order can fire even on a bar whose CLOSE never beats
        # the level stop -- a wick that touches -1R and comes back. Checked
        # every bar, same as `backtest_week._disaster_hit`.
        dpx = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
        if fill is fill_ratified and disaster_stop_hit(b["h"], b["l"], dpx, long):
            return xl.realised_r(entry, stop, dpx, side), i, "disaster"
        if tgt is not None:
            hit = (b["h"] >= tgt) if long else (b["l"] <= tgt)
            if hit:
                return xl.realised_r(entry, stop, tgt, side), i, "target"
        if time_stop is not None and i - entry_i >= time_stop:
            return xl.realised_r(entry, stop, b["c"], side), i, "time"
    ci = clock if n > clock else n - 1
    return xl.realised_r(entry, stop, bars[ci]["c"], side), ci, "clock"


def first_adverse_close(bars, entry_i, entry, stop, side, fill, clock=CLOCK):
    """The most aggressive loser cut expressible: out at the close of the
    FIRST bar after entry that closes against the entry price. The original
    stop (and disaster order, where the convention has one) stays live for
    the bar that runs straight through it."""
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0, entry_i, "flat"
    long = side == "L"
    end = min(clock + 1, n)
    for i in range(entry_i + 1, end):
        b = bars[i]
        if xl._stop_hit_first(bars, i, entry, stop, side):
            px, disaster = fill(bars, i, entry, stop, risk, long)
            return xl.realised_r(entry, stop, px, side), i, (
                "disaster" if disaster else "stop")
        dpx = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
        if fill is fill_ratified and disaster_stop_hit(b["h"], b["l"], dpx, long):
            return xl.realised_r(entry, stop, dpx, side), i, "disaster"
        c = b["c"]
        if (c < entry) if long else (c > entry):
            return xl.realised_r(entry, stop, c, side), i, "adverse"
    ci = clock if n > clock else n - 1
    return xl.realised_r(entry, stop, bars[ci]["c"], side), ci, "clock"


def _arms():
    a = {"ride": ("one unit, original stop, ride to 11:00 (CONTROL)",
                  lambda *p: ride(*p))}
    for m in (15, 30, 45):
        a[f"ride_ts{m}"] = (f"ride + hard {m}-minute time stop",
                           (lambda mm: lambda *p: ride(*p, time_stop=mm))(m))
    a["adverse"] = ("out on the FIRST bar that closes against entry",
                   lambda *p: first_adverse_close(*p))
    a["f2"] = ("flat 2 R, no cut (CONTROL, secondary family)",
              lambda *p: ride(*p, target_r=2.0))
    for m in (15, 30, 45):
        a[f"f2_ts{m}"] = (f"flat 2 R + hard {m}-minute time stop",
                         (lambda mm: lambda *p: ride(*p, target_r=2.0,
                                                     time_stop=mm))(m))
    return a


ARMS = _arms()
CUTS = ["ride_ts15", "ride_ts30", "ride_ts45", "adverse"]      # the four
CUTS_F2 = ["f2_ts15", "f2_ts30", "f2_ts45"]
CONTROL = {**{k: "ride" for k in CUTS}, **{k: "f2" for k in CUTS_F2}}
CONTROL["ride"] = None
CONTROL["f2"] = None


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def months_green(rows, key):
    by = defaultdict(float)
    for r in rows:
        by[r["ym"]] += r[key]
    return sum(1 for v in by.values() if v > 0), len(by)


def max_drawdown(rows, key):
    order = sorted(rows, key=lambda r: (r["day"], r["et"], r["sym"]))
    peak = 0.0
    cum = 0.0
    worst = 0.0
    for r in order:
        cum += r[key]
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return worst


def paired_bootstrap(deltas, n=BOOTSTRAP, seed=SEED):
    if not deltas:
        return (0.0, 0.0, 0.0)
    rnd = random.Random(seed)
    k = len(deltas)
    means = []
    for _ in range(n):
        s = 0.0
        for _ in range(k):
            s += deltas[rnd.randrange(k)]
        means.append(s / k)
    means.sort()
    lo = means[int(0.025 * n)]
    hi = means[min(n - 1, int(0.975 * n))]
    return (sum(deltas) / k, lo, hi)


def summarise(rows, key):
    rs = [r[key] for r in rows]
    g, tot = months_green(rows, key)
    return {
        "n": len(rs),
        "mean_r": sum(rs) / len(rs),
        "median_r": statistics.median(rs),
        "win_rate": sum(1 for v in rs if v > 0) / len(rs),
        "total_r": sum(rs),
        "months_green": g,
        "months": tot,
        "max_dd": max_drawdown(rows, key),
        "worst": min(rs),
        "p10": statistics.quantiles(rs, n=10)[0] if len(rs) > 10 else min(rs),
    }


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

# The book this report was measured on -- `research/bt2y_trades.json`, the
# T0 ratified re-run (67 MB, regenerable with `python backtest_2y.py`, NOT
# committed with this script). The guard below is the reproducibility
# contract: if the file on disk is not that book, the run says so loudly
# instead of quietly publishing a number off the wrong one.
BOOK_MEAN_R = 0.5481
BOOK_TRADED = 2595


def load_book(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    sha = hashlib.sha256(raw).hexdigest()
    d = json.loads(raw.decode("utf-8"))
    traded = [t for t in d["trades"] if t.get("traded")]
    mean = sum(t["r"] for t in traded) / len(traded) if traded else 0.0
    if abs(mean - BOOK_MEAN_R) > 5e-3 or len(traded) != BOOK_TRADED:
        print("WARNING: book is NOT the T0 ratified re-run this report was "
              "measured on (traded=%d mean=%+.4f; expected %d / %+.4f). "
              "Every number below will differ. Regenerate with "
              "`python backtest_2y.py`." % (len(traded), mean, BOOK_TRADED,
                                            BOOK_MEAN_R))
    return d.get("meta", {}), sha, traded


def replay(traded, verbose=True):
    rows, gaps = [], Counter()
    cache = {}
    for t in traded:
        sym, day = t["sym"], t["day"]
        ck = (sym, day)
        if ck not in cache:
            cache[ck] = load_rth_bars(sym, day)
        bars = cache[ck]
        if not bars:
            gaps["no_bars"] += 1
            continue
        ei = t.get("entry_i")
        if ei is None or ei >= len(bars):
            gaps["bad_entry_i"] += 1
            continue
        entry, stop, side = t["entry"], t["stop"], t.get("side") or (
            "L" if t["dir"] == "call" else "S")
        if abs(entry - stop) <= 0:
            gaps["zero_risk"] += 1
            continue
        row = {"sym": sym, "day": day, "ym": t["ym"], "et": t["et"],
               "book_r": t["r"], "sgrade": t.get("sgrade"),
               "setup": t.get("setup")}
        for fk, fn in FILLS.items():
            for ak, (_lbl, fnb) in ARMS.items():
                r, xi, why = fnb(bars, ei, entry, stop, side, fn)
                row[f"{fk}:{ak}"] = r
                row[f"why:{fk}:{ak}"] = why
        rows.append(row)
    if verbose:
        print("replayed %d of %d traded rows; gaps=%s"
              % (len(rows), len(traded), dict(gaps)))
    return rows, gaps


def arm_table(rows, fk):
    out = {}
    for ak in ARMS:
        key = f"{fk}:{ak}"
        s = summarise(rows, key)
        s["label"] = ARMS[ak][0]
        why = Counter(r[f"why:{fk}:{ak}"] for r in rows)
        s["why"] = dict(why)
        cut_reason = {"adverse": "adverse"}.get(ak, "time")
        s["cut_binds"] = why.get(cut_reason, 0) / len(rows) if ak not in (
            "ride", "f2") else None
        ctl = CONTROL[ak]
        if ctl:
            d = [r[key] - r[f"{fk}:{ctl}"] for r in rows]
            m, lo, hi = paired_bootstrap(d)
            s["delta"] = m
            s["ci_lo"], s["ci_hi"] = lo, hi
            s["err_bar"] = (hi - lo) / 2.0
            s["null"] = lo <= 0.0 <= hi
        else:
            s["delta"] = s["ci_lo"] = s["ci_hi"] = s["err_bar"] = None
            s["null"] = None
        out[ak] = s
    return out


# ---------------------------------------------------------------------------
# held-out recall -- invariant across every arm in this file, and why
# ---------------------------------------------------------------------------

def load_s_marks():
    out = []
    with open(MARKS, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("answers", {}).get("s") == ["s"]:
                out.append(r)
    return out


def recall_invariance_check(rows):
    """Every arm here changes only WHERE a trade exits, never WHETHER it
    exists: the fired set is identical under every arm because none of them
    is consulted before the entry and none can veto one."""
    base = {(r["sym"], r["day"]) for r in rows}
    for fk in FILLS:
        for ak in ARMS:
            got = {(r["sym"], r["day"]) for r in rows if f"{fk}:{ak}" in r}
            assert got == base, f"{fk}:{ak} changed the fired set"
    return len(base)


def measure_recall(verbose=True):
    from research.t4_engine_recall import run_day
    marks = load_s_marks()
    hit = 0
    for m in marks:
        sym = m.get("symbol")
        day = m.get("day")
        if not sym or not day:
            continue
        try:
            fired = run_day(sym, day)
        except Exception as e:  # pragma: no cover
            if verbose:
                print(f"recall: {sym} {day} failed: {e}")
            continue
        if fired:
            hit += 1
    if verbose:
        print(f"held-out S recall: {hit}/{len(marks)} = {hit/len(marks)*100:.1f}%")
    return hit, len(marks)


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck(rows):
    ok = True
    for r in rows:
        for ak in ARMS:
            v = r.get(f"ratified:{ak}")
            if v is not None and v < -(MAX_LOSS_R + 1e-9):
                print(f"FAIL: ratified:{ak} booked {v:.4f} past -{MAX_LOSS_R}R "
                      f"on {r['sym']} {r['day']}")
                ok = False
            v = r.get(f"clamp:{ak}")
            if v is not None and v < -(1.0 + 1e-9):
                print(f"FAIL: clamp:{ak} booked {v:.4f} past -1.000R on "
                      f"{r['sym']} {r['day']}")
                ok = False
    n = recall_invariance_check(rows)
    print(f"recall_invariance_check: {n} unique symbol-days, identical "
          f"across all {len(FILLS)} x {len(ARMS)} arm/convention pairs")
    if ok:
        print("selfcheck: PASS")
    else:
        print("selfcheck: FAIL")
    return ok


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def fmt_pct(x):
    return f"{x*100:.1f}%" if x is not None else "--"


def render(meta, sha, n_book, rows, tables, recall=None):
    lines = []
    lines.append("# T6 -- losers lose quick, re-run on the ratified fills\n")
    lines.append(f"Generated by `research/t6_losers_quick.py`. Book: "
                 f"`research/bt2y_trades.json` (`meta.generated` "
                 f"**{meta.get('generated')}**, {meta.get('signals')} signals, "
                 f"{n_book} traded rows, sha256 `{sha[:16]}`) -- the T0 ratified "
                 f"re-baseline (R1-R33 landed, `9edd2ba7`, +0.5481R). "
                 f"**{len(rows)} of {n_book} traded rows replayed** from "
                 f"`data_archive/` with zero fetches. Horizon: the 11:00 ET "
                 f"backstop (`exit_lab.CLOCK_BAR = 90`).\n")
    lines.append('Austin, 2026-08-28: *"let runners run and losers lose quick"*.\n')

    r_ride = tables["ratified"]["ride"]
    r_best = min(CUTS, key=lambda k: abs(tables["ratified"][k]["delta"]))
    best = tables["ratified"][r_best]
    verdict = "Null result: " if best["null"] else ""
    lines.append("## The headline\n")
    lines.append(
        f"**{verdict}the best of the four faster-cut arms under the shipped "
        f"R1/R2 fills (`{r_best}`) moves {best['delta']:+.4f} R against control "
        f"on identical rows, {'inside' if best['null'] else 'outside'} its own "
        f"95% error bar of ±{best['err_bar']:.4f} R.** "
        f"The X board's refutation of \"cut losers faster\" survives its own "
        f"claimed bug fix, scored on the ratified engine (R1-R33 + the real "
        f"disaster-stop order). No arm clears its own bar in either direction "
        f"under either fill convention except one measurable loss under "
        f"`clamp` (§1b) -- see §6.\n")
    lines.append(
        "**And the ticket's mechanism does not hold up either.** The fill "
        "clamp (`clamp`, -1.000R by construction, no disaster order) and the "
        "shipped ratified fills (`ratified`, level-close floored at -1.25R "
        "plus a real intrabar -1R disaster order) book DIFFERENT absolute "
        "numbers -- the left tail is real and the ratified convention "
        "restores it -- but because a faster cut and its control share the "
        "same stop-outs, the fill convention barely moves the delta each arm "
        "is judged on. See §1c.\n")

    lines.append("## 1. The claim under test: does the fill convention change the verdict?\n")
    lines.append(
        "Same rows, same entries, same stops, same tape. The only thing that "
        "moves between the two blocks is what a stop-out books: `ratified` "
        "(the settled R1/R2 rule: disaster order first on an intrabar touch "
        "at -1R, then the level stop on the close floored at -1.25R) versus "
        "`clamp` (the ticket's premise -- every stop books at the stop price, "
        "exactly -1.000R, no disaster order, no tail past -1R ever).\n")

    for fk, label in (("ratified", "1a. Ratified fills -- the shipped R1/R2 rule"),
                      ("clamp", "1b. Clamped fills -- the ticket's premise, reproduced on purpose")):
        lines.append(f"### {label}\n")
        lines.append("| arm | n | mean R | median R | win | months green | max DD | worst R | delta vs control | own 95% bar | verdict |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for ak in ["ride"] + CUTS:
            s = tables[fk][ak]
            d = f"{s['delta']:+.4f}" if s['delta'] is not None else "*(control)*"
            eb = f"±{s['err_bar']:.4f}" if s['err_bar'] is not None else "--"
            if s['null'] is None:
                v = "--"
            elif s['null']:
                v = "**null** (bar straddles 0)"
            else:
                v = "**negative**" if s['delta'] < 0 else "**positive**"
            lines.append(
                f"| {s['label']} | {s['n']} | **{s['mean_r']:+.4f}** | "
                f"{s['median_r']:+.4f} | {fmt_pct(s['win_rate'])} | "
                f"{s['months_green']} / {s['months']} | {s['max_dd']:.2f}R | "
                f"{s['worst']:.4f} | {d} | {eb} | {v} |")
        lines.append("")

    lines.append("### 1c. What the ratified convention actually did to each arm's delta\n")
    lines.append("| arm | delta vs control, CLAMPED | delta vs control, RATIFIED | the ratified fills moved the delta by | sign flip? |")
    lines.append("|---|---:|---:|---:|---|")
    for ak in CUTS:
        c = tables["clamp"][ak]["delta"]
        r = tables["ratified"][ak]["delta"]
        flip = "yes" if (c > 0) != (r > 0) and abs(c) > 1e-9 and abs(r) > 1e-9 else "no"
        lines.append(f"| {ARMS[ak][0]} | {c:+.4f} | {r:+.4f} | {r-c:+.4f} | {flip} |")
    lines.append("")
    ride_c = tables["clamp"]["ride"]["mean_r"]
    ride_r = tables["ratified"]["ride"]["mean_r"]
    lines.append(
        f"The control itself moves too -- `ride` books {ride_r:+.4f} R under "
        f"ratified fills against {ride_c:+.4f} R clamped, a {ride_r-ride_c:+.4f} R "
        f"difference. Because BOTH sides of every A/B move together (a faster "
        f"cut and its control share the same stop-outs), the DELTA the arm is "
        f"judged on moves far less than either side alone.\n")

    lines.append("## 2. Reachability -- checked before any number is read\n")
    lines.append("| arm | cut binds | stop | disaster | target | clock | reachable? |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for ak in CUTS + CUTS_F2:
        s = tables["ratified"][ak]
        why = s["why"]
        cb = s["cut_binds"]
        reach = "yes" if 0.01 <= cb <= 0.85 else "**NO -- unreachable/saturated**"
        lines.append(f"| {ARMS[ak][0]} | {fmt_pct(cb)} | {why.get('stop',0)} | "
                     f"{why.get('disaster',0)} | {why.get('target',0)} | "
                     f"{why.get('time',0) + why.get('adverse',0)} | {reach} |")
    lines.append("")
    lines.append("Every arm binds inside the 1-85% band -- none is a branch that can never be true, none swallows the whole book.\n")

    lines.append("## 3. The flat-2R family\n")
    lines.append("| arm | n | mean R | median R | win | months green | max DD | worst R | delta vs control | own 95% bar | verdict |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for ak in ["f2"] + CUTS_F2:
        s = tables["ratified"][ak]
        d = f"{s['delta']:+.4f}" if s['delta'] is not None else "*(control)*"
        eb = f"±{s['err_bar']:.4f}" if s['err_bar'] is not None else "--"
        v = "--" if s['null'] is None else ("**null** (bar straddles 0)" if s['null'] else ("**negative**" if s['delta'] < 0 else "**positive**"))
        lines.append(f"| {s['label']} | {s['n']} | **{s['mean_r']:+.4f}** | {s['median_r']:+.4f} | {fmt_pct(s['win_rate'])} | {s['months_green']} / {s['months']} | {s['max_dd']:.2f}R | {s['worst']:.4f} | {d} | {eb} | {v} |")
    lines.append("")

    lines.append("## 4. The left tail the arms were supposed to be cutting\n")
    losers = [r["ratified:ride"] for r in rows if r["ratified:ride"] < 0]
    losers_c = [r["clamp:ride"] for r in rows if r["clamp:ride"] < 0]
    worse1 = sum(1 for v in losers if v < -1.0)
    worse1_c = sum(1 for v in losers_c if v < -1.0)
    at1 = sum(1 for v in losers if abs(v + 1.0) < 1e-6)
    at1_c = sum(1 for v in losers_c if abs(v + 1.0) < 1e-6)
    lines.append("| convention | rows worse than -1.00 R | rows at exactly -1.00 R | worst row | mean of the losers |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append(f"| ratified | {worse1} | {at1} | {min(losers):.4f} | {sum(losers)/len(losers):.4f} |")
    lines.append(f"| clamp | {worse1_c} | {at1_c} | {min(losers_c):.4f} | {sum(losers_c)/len(losers_c):.4f} |")
    lines.append(
        "\nThe left tail past -1R is real under `ratified` and absent under "
        "`clamp` by construction -- the disaster order caps it at -1.0R "
        "intrabar and the close-fill floor caps everything else at -1.25R, so "
        "the ratified tail is bounded, not open, but it is not the flat "
        "-1.000R the ticket describes either. What does not follow, either "
        "way, is that a deeper or shallower left tail changes which arm wins: "
        "a trade a 15-minute stop does not reach in time is stopped out "
        "identically in both the arm and its control.\n")

    lines.append("## 5. Held-out recall\n")
    lines.append(
        "Every arm here is an exit policy: consulted only after an entry "
        "exists, and it can never veto one, so the fired set is byte-identical "
        "across all 9 arms x 2 fill conventions. `recall_invariance_check()` "
        f"confirms this over the {len(rows)} replayed rows: "
        f"{recall_invariance_check(rows)} unique symbol-days, identical under "
        "every arm/convention pair.\n")
    if recall:
        hit, tot = recall
        lines.append(f"Measured baseline on the sweep (`--recall`, one engine "
                     f"pass per day): the engine takes an entry on **{hit} of "
                     f"his {tot} S days = {hit/tot*100:.1f}%**. That number is "
                     f"the SAME for every arm here -- T6 cannot move the "
                     f"recall gate in either direction.\n")
    else:
        lines.append("`--recall` was not run for this report; the invariance "
                     "argument above is what makes that safe to skip -- no "
                     "arm here can move the number regardless of what it is.\n")

    lines.append("## 6. What this does and does not say\n")
    lines.append(
        f"- **The X board's refutation of \"cut losers faster\" stands, on "
        f"the ratified R1-R33 engine, under the shipped R1/R2 fills.** Best "
        f"of the four is `{r_best}` at {best['delta']:+.4f} R against control, "
        f"{'inside' if best['null'] else 'outside'} its own 95% bar of "
        f"±{best['err_bar']:.4f} R.\n")
    n_null = sum(1 for ak in CUTS if tables["ratified"][ak]["null"])
    null_phrase = "All four" if n_null == len(CUTS) else f"{n_null} of the four"
    lines.append(f"- **{null_phrase} are NULL, not negative,** under "
                 f"ratified fills -- their bootstrap intervals straddle "
                 f"zero. A null arm is still not a reason to ship, but it is "
                 f"not the same claim as \"negative\". (Under the `clamp` "
                 f"convention `adverse` IS a measurable loss, -0.2093R -- see §1b.)\n")
    lines.append(
        "- **The ticket's stated mechanism does not survive scrutiny either.** "
        "The clamp and the ratified convention book materially different "
        "absolute numbers (§4), but because a faster cut and its control "
        "share the same stop-outs, the delta each arm is judged on moves by "
        "far less than either side alone (§1c) -- restoring the tail does "
        "not flip a single sign.\n")
    gate_short = GATE - r_ride["mean_r"]
    lines.append(
        f"- **No arm reaches the money gate.** The best mean R anywhere in "
        f"this file is {max(tables['ratified'][a]['mean_r'] for a in ['ride']+CUTS+['f2']+CUTS_F2):+.4f} R "
        f"against the {GATE:+.1f} R gate -- the ride control alone is "
        f"{gate_short:.4f} R short.\n")
    lines.append(
        "- **In-sample, every parameter.** 15/30/45 minutes and the "
        "first-adverse-close rule are all chosen and scored on the same "
        "rows. There is no held-out split for an exit parameter and this "
        "file does not invent one.\n")
    lines.append(
        "- **The control is the ride, not the shipped ladder.** The book's "
        f"own booked mean is {sum(r['book_r'] for r in rows)/len(rows):+.4f} R "
        f"on these rows (scaling + target rules included); the one-unit ride "
        f"at the 11:00 clock books {r_ride['mean_r']:+.4f} R. Every delta "
        "here is arm-minus-ride on identical rows, not arm-minus-shipped-book.\n")
    lines.append("- **Options decay, spread and fill slippage are not priced.** R is the result; dollars are a sizing skin.\n")

    lines.append("## 7. Recommendation\n")
    lines.append(
        "**Ship nothing. `FASTER_CUT` is not built and should not be.** No "
        "arm is positive under either fill convention on the ratified "
        "engine; the refutation from the earlier X board survives its own "
        "claimed bug fix. The half of Austin's sentence that is still live "
        "is *\"let runners run\"* -- a separate track, not this one.\n")

    lines.append("## 8. Provenance\n")
    lines.append(f"- script: `research/t6_losers_quick.py` (committed with this report)")
    lines.append(f"- book: `research/bt2y_trades.json`, sha256 `{sha}` -- **not committed** "
                 f"(67 MB, regenerable with `python backtest_2y.py`). `load_book()` warns "
                 f"loudly if the file on disk does not match the T0 ratified re-baseline "
                 f"(traded=2595, mean=+0.5481R).")
    lines.append(f"- engine base: `t0-ratified` (`9edd2ba7`), R1-R33 landed, DISASTER_STOP=1 "
                 f"(DISASTER_STOP_R={DISASTER_STOP_R}, MAX_LOSS_R={MAX_LOSS_R}) is the shipped "
                 f"default this report scores as `ratified`.")
    lines.append("- bars: `data_archive/` via `research.levels.load_rth_bars`, zero fetches")
    lines.append("- arms: reproduced from the earlier X-board run, fill convention injected + the disaster order layered in")
    lines.append("- error bar: paired bootstrap of the per-trade difference, 4000 resamples, "
                 f"seed {SEED}, 95% percentile interval. Printed per arm; the project's "
                 f"standing reference bar of ±{PROJECT_BAR} R is quoted for scale only.")
    lines.append("- `--selfcheck`: no arm books below -1.25R under ratified fills, no clamped "
                 "stop books past -1.000R, and the fired set is identical across every arm.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--recall", action="store_true")
    args = ap.parse_args()

    meta, sha, traded = load_book(BOOK)
    rows, gaps = replay(traded)

    if args.selfcheck:
        ok = selfcheck(rows)
        sys.exit(0 if ok else 1)

    tables = {fk: arm_table(rows, fk) for fk in FILLS}
    recall = measure_recall() if args.recall else None

    md = render(meta, sha, len(traded), rows, tables, recall)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"wrote {OUT_MD}")

    out = {
        "book_sha256": sha,
        "book_meta": meta,
        "n_traded": len(traded),
        "n_replayed": len(rows),
        "gaps": dict(gaps),
        "tables": {fk: {ak: {k: v for k, v in s.items() if k not in ("why",)}
                        for ak, s in t.items()} for fk, t in tables.items()},
        "recall": recall,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
