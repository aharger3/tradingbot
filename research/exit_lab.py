"""OMEN 5.2 — T3 exit lab.

Replays exit policies over 1-min RTH bars and returns realised R per trade per
policy. **No look-ahead**: every decision at bar ``i`` only reads bars at index
``<= i``. ATR and trailing stops for bar ``i`` are set from bars ``<= i-1``
(known before bar ``i`` opens) and then tested against bar ``i``'s range.

Policies (tranche weights sum to 1.0):

    flat_1r        100% at 1.0R
    flat_2r        100% at 2.0R
    hod_only       100% at the causal-HOD rule
    30_30_30_10    30% causal-HOD, 70% on the runner trail
    50_20_20_10    50% causal-HOD, 50% on the runner trail

Causal-HOD rule (see omen-5.2.md §T3): after entry, wait for a bar whose high
exceeds every high since 09:30 (a new HOD); tranche 1 then exits at the **close
of the first subsequent bar that does not make a higher high** (high <= prev
high). Mirror for shorts (new LOD, exit on first bar that does not make a lower
low). If no new extreme prints before the 11:00 ET clock, tranche 1 exits at
the clock along with the rest.

Runner rule (shared by both scale-outs): after tranche 1 the stop moves to
entry (break-even); the remaining tranches ride a trail — either **1.0x
ATR14** (highest_high - 1.0*ATR14 for longs / lowest_low + 1.0*ATR14 for
shorts) or the **prior bar's low/high**. Force flat at 11:00 ET; force flat
early on a structure break (a lower low on longs / higher high on shorts,
against the trade) or on consolidation (no new extreme in the trade's
direction for 5 consecutive bars).

Entry and stop are fixed inputs; only the exit varies.

Bars come from ``research.levels.load_rth_bars`` (see research/v52_paths.md):
a list of ``{t, o, h, l, c}`` dicts for the RTH window (>= 09:30), index 0 =
the 09:30 bar. ``entry_i`` is an index into that list, matching the marks.
"""

from __future__ import annotations
import json
import os
import sys

# 11:00 ET force-flat clock. RTH bars start at 09:30 (index 0), so 11:00 is
# 90 minutes later = index 90. Mirrors the marks' entry_i/exit_i convention.
CLOCK_BAR = 90
CONSOLIDATION_BARS = 5  # no new extreme in the trade's direction for N bars
ATR_WINDOW = 14

# --- Austin's stop rule, rule ballot q1 (2026-08-23) ------------------------
# "a 1m candle close below is exit, max slippage -1.25r which is 1.25k based on
#  current position sizing"
# The CLOSE is the trigger, the fill is that close, and the loss floors at
# -1.25R. Settled 2026-08-11 and marked never-re-elicit; backtest_week.py:245
# has always obeyed it and this module never did (OMEN 6 ticket 17).
MAX_LOSS_R = 1.25

# OPEN, deliberately shipped at 0. The 2026-08-23 Q&A settled "25% of the
# previous candle's range" as one tolerance unit and listed stop slippage as one
# of the three places it applies -- but ballot q1 describes a plain close beyond
# the stop with no buffer. Two readings, materially different. This ships on the
# literal q1 reading and the other is a one-line flip, not a rewrite.
STOP_TRIGGER_BUFFER_FRAC = 0.0
MARKS_FILES = [
    os.path.join(os.path.dirname(__file__), "marks", "deck_marks_tsla_2026-08-20.jsonl"),
    os.path.join(os.path.dirname(__file__), "marks", "deck_marks_index_2026-08-19.jsonl"),
]

# Re-use the verified bar loader from the path map (research/v52_paths.md).
# Support both ``python -m research.exit_lab`` and ``python research/exit_lab.py``.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from research.levels import load_rth_bars  # noqa: E402


# ---------------------------------------------------------------------------
# Bar math (all causal)
# ---------------------------------------------------------------------------

def atr(bars, i, n=ATR_WINDOW):
    """ATR over the ``n`` TRs ending at bar ``i`` (inclusive). Causal: uses
    only bars ``<= i``. Returns None if fewer than 2 bars."""
    if i < 1:
        return None
    trs = []
    for j in range(1, i + 1):
        h, l, pc = bars[j]["h"], bars[j]["l"], bars[j - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    window = trs[-n:]
    return sum(window) / len(window) if window else None


def realised_r(entry, stop, exit_price, side):
    """R-multiple of an exit given a fixed entry/stop. risk = |entry-stop|."""
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    if side == "L":
        return (exit_price - entry) / risk
    return (entry - exit_price) / risk


def causal_hod_exit_bar(bars, entry_i, side):
    """Bar index at which tranche 1 exits under the causal-HOD rule.

    Pure structural rule — ignores the stop, which is what the T3 selftest
    calibrates against Austin's marked exit_i. Returns the clock bar
    (CLOCK_BAR, or the last bar if shorter) when no new session extreme prints
    before the clock.
    """
    n = len(bars)
    if entry_i >= n:
        return None
    limit = min(CLOCK_BAR + 1, n)  # clock is the hard backstop
    if side == "L":
        # Session high established through the entry bar.
        cur = max(b["h"] for b in bars[: entry_i + 1])
        hod_bar = None
        for j in range(entry_i + 1, limit):
            if bars[j]["h"] > cur:
                hod_bar = j
                cur = bars[j]["h"]
                break
        if hod_bar is None:
            return CLOCK_BAR if n > CLOCK_BAR else n - 1
        # first subsequent bar that does not make a higher high
        for j in range(hod_bar + 1, limit):
            if bars[j]["h"] <= bars[j - 1]["h"]:
                return j
        return CLOCK_BAR if n > CLOCK_BAR else n - 1
    else:  # short — mirror
        cur = min(b["l"] for b in bars[: entry_i + 1])
        lod_bar = None
        for j in range(entry_i + 1, limit):
            if bars[j]["l"] < cur:
                lod_bar = j
                cur = bars[j]["l"]
                break
        if lod_bar is None:
            return CLOCK_BAR if n > CLOCK_BAR else n - 1
        for j in range(lod_bar + 1, limit):
            if bars[j]["l"] >= bars[j - 1]["l"]:
                return j
        return CLOCK_BAR if n > CLOCK_BAR else n - 1


def _ref_range(bars, i):
    """The previous bar's range -- the only range known before bar ``i`` closes."""
    j = i - 1 if i > 0 else i
    return max(0.0, bars[j]["h"] - bars[j]["l"])


def _stop_hit_first(bars, i, entry, stop, side):
    """Did the protective stop fire on bar ``i`` (before any target)?

    The CLOSE is the trigger, not the wick. Austin, five times in one batch of
    marks and again in rule ballot q1: a 1-minute candle close beyond the level
    is the exit, and a wick through it stops nothing out.

    Pessimistic same-bar convention survives: if the close is beyond the stop
    and a target also traded in that bar, the stop still wins.
    """
    buf = STOP_TRIGGER_BUFFER_FRAC * _ref_range(bars, i)
    if side == "L":
        return bars[i]["c"] <= stop - buf
    return bars[i]["c"] >= stop + buf


def _stop_fill(bars, i, entry, stop, side, risk):
    """What a close-triggered stop actually fills at.

    You are out at market once the bar closes beyond the stop, so the fill is
    that close -- which is worse than the stop price, by however far the bar ran.
    Floored at Austin's stated worst case of -1.25R (ballot q1).

    This is where the left tail comes from. Filling at the stop price instead
    (what this module did before) is the same optimism that left the 03 baseline
    with 32 of 40 slices sitting at exactly -0.30R and no distribution at all.
    """
    close = bars[i]["c"]
    if side == "L":
        return max(close, entry - MAX_LOSS_R * risk)
    return min(close, entry + MAX_LOSS_R * risk)


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

def flat_target(bars, entry_i, entry, stop, side, target_r):
    """100% flat at ``target_r`` R, with the fixed stop always live.

    Scan from entry_i+1. Stop hit -> -1.0R (pessimistic same-bar). Target hit
    -> +target_r. Neither by the clock -> exit at the clock bar's close.
    """
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    target = entry + target_r * risk if side == "L" else entry - target_r * risk
    end = min(CLOCK_BAR + 1, n)
    for i in range(entry_i + 1, end):
        b = bars[i]
        if _stop_hit_first(bars, i, entry, stop, side):
            return realised_r(entry, stop, _stop_fill(bars, i, entry, stop, side, risk), side)
        hit = (b["h"] >= target) if side == "L" else (b["l"] <= target)
        if hit:
            return realised_r(entry, stop, target, side)
    clock_i = CLOCK_BAR if n > CLOCK_BAR else n - 1
    return realised_r(entry, stop, bars[clock_i]["c"], side)


def flat_1r(bars, entry_i, entry, stop, side, trail_method="atr"):
    return flat_target(bars, entry_i, entry, stop, side, 1.0)


def flat_2r(bars, entry_i, entry, stop, side, trail_method="atr"):
    return flat_target(bars, entry_i, entry, stop, side, 2.0)


def hod_only(bars, entry_i, entry, stop, side, trail_method="atr"):
    """100% at the causal-HOD exit bar's close, with the fixed stop live.

    If the stop fires before the HOD exit bar, exit at the stop (-1.0R).
    """
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    hod_i = causal_hod_exit_bar(bars, entry_i, side)
    if hod_i is None:
        return 0.0
    end = min(hod_i, n)
    for i in range(entry_i + 1, end):
        if _stop_hit_first(bars, i, entry, stop, side):
            return realised_r(entry, stop, _stop_fill(bars, i, entry, stop, side, risk), side)
    return realised_r(entry, stop, bars[hod_i]["c"], side)


def scale_out(bars, entry_i, entry, stop, side, weights, trail_method="atr"):
    """Scale-out policy: tranche 1 at the causal-HOD rule, rest on the runner.

    ``weights`` is a 4-list like ``[0.30, 0.30, 0.30, 0.10]``. Tranche 1 rides
    the fixed stop until the HOD exit; the remaining tranches (summed) ride
    the trail with the stop at break-even, force-flat at the clock, on a
    structure break, or on consolidation. All remaining tranches exit together
    at the trail exit price (the 30/30/10 vs 20/20/10 split only weights
    tranche 1 vs the runner; the spec says "remaining tranches exit on a
    trail" — one trail, one exit point).
    """
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    hod_i = causal_hod_exit_bar(bars, entry_i, side)
    if hod_i is None:
        return 0.0

    w1 = weights[0]
    w_rest = sum(weights[1:]) or 1.0

    # --- tranche 1: fixed stop until the HOD exit bar, INCLUSIVE ---
    # The stop is live on the HOD bar itself. A bar can print a new extreme and
    # then reverse through the stop in the same minute; the module's pessimistic
    # same-bar convention (see _stop_hit_first) says the stop filled first, so
    # the range must include hod_i. Excluding it let tranche 1 book that bar's
    # close no matter how far below the stop it was.
    t1_exit_i = hod_i
    t1_price = bars[hod_i]["c"]
    stopped_out = False
    for i in range(entry_i + 1, min(hod_i + 1, n)):
        if _stop_hit_first(bars, i, entry, stop, side):
            t1_exit_i = i
            t1_price = _stop_fill(bars, i, entry, stop, side, risk)
            stopped_out = True
            break
    r1 = realised_r(entry, stop, t1_price, side)

    # The ORIGINAL stop fired before tranche 1 ever reached its HOD rung, so
    # NO tranche has taken profit and 100% of the position is out at that
    # close. There is no runner to move to break-even -- moving one books the
    # rally that follows a full stop-out as a partial loss or a profit.
    # Third instance of ticket 02's bug class: a stop computed and then not
    # applied to the tranche it governs. research/test_runner_stop.py's
    # `stop_then_rally` is red before this line and green after.
    if stopped_out:
        return r1

    # --- runner: stop to break-even, trail the rest ---
    # The runner starts at whichever bar tranche 1 actually left on.
    rest_i, rest_price = _runner_exit(
        bars, t1_exit_i, entry, side, trail_method, start_stop=entry, risk=risk
    )
    r_rest = realised_r(entry, stop, rest_price, side)
    return w1 * r1 + w_rest * r_rest


def _runner_exit(bars, from_i, entry, side, trail_method, start_stop, risk):
    """Pick the exit bar/price for the remaining tranches after tranche 1.

    Causal: the trail stop for bar ``i`` is set from bars ``<= i-1`` and then
    tested against bar ``i``. Force-flat on the clock, a structure break, or
    consolidation is evaluated at bar ``i``'s close.

    ``start_stop`` is the break-even stop the module docstring promises: once
    tranche 1 is out, the stop moves to entry and never moves back. It is a
    FLOOR under the trail, not an alternative to it -- the effective stop is
    whichever of the two is tighter (higher on longs, lower on shorts). Without
    this the ATR trail can sit far below entry on a wide-range day and the
    runner books tens of R against a break-even stop that was never applied.
    See ``research/test_runner_stop.py``.
    """
    n = len(bars)
    end = min(CLOCK_BAR + 1, n)
    if from_i + 1 >= end:
        i = CLOCK_BAR if n > CLOCK_BAR else n - 1
        # the break-even stop is live on this bar too -- and it is close-based,
        # per ballot q3: "if the structure doesn't break you don't want to stop
        # out, that's why you wait for candle closes for stops"
        if _stop_hit_first(bars, i, entry, start_stop, side):
            return i, _stop_fill(bars, i, entry, start_stop, side, risk)
        return i, bars[i]["c"]

    # running extremes for the trail (through bar i-1)
    if side == "L":
        highest = max(b["h"] for b in bars[: from_i + 1])
    else:
        lowest = min(b["l"] for b in bars[: from_i + 1])
    bars_since_extreme = 0  # consolidation counter

    for i in range(from_i + 1, end):
        b = bars[i]
        # set the trail stop from bars <= i-1, then test against bar i
        if trail_method == "atr":
            a = atr(bars, i - 1) or atr(bars, i) or 0.0
            if side == "L":
                trail_stop = highest - 1.0 * a
            else:
                trail_stop = lowest + 1.0 * a
        else:  # prior-bar low/high
            if side == "L":
                trail_stop = bars[i - 1]["l"]
            else:
                trail_stop = bars[i - 1]["h"]

        # the break-even stop floors the trail -- take whichever is tighter
        if side == "L":
            trail_stop = max(trail_stop, start_stop)
        else:
            trail_stop = min(trail_stop, start_stop)

        # 1. protective trail stop -- close-based, same as every other stop.
        # A wick through break-even is exactly the case ballot q3 says does not
        # take Austin out. The ATR trail is a machine rule rather than one of
        # his, but it is floored by the break-even stop, so treating it any other
        # way would reintroduce wick stop-outs through the back door.
        if _stop_hit_first(bars, i, entry, trail_stop, side):
            return i, _stop_fill(bars, i, entry, trail_stop, side, risk)

        # update extremes / consolidation counter using bar i (causal at close)
        made_new = False
        if side == "L":
            if b["h"] > highest:
                highest = b["h"]
                made_new = True
        else:
            if b["l"] < lowest:
                lowest = b["l"]
                made_new = True
        bars_since_extreme = 0 if made_new else bars_since_extreme + 1

        # 2. structure break: lower low on longs / higher high on shorts
        if side == "L" and b["l"] < bars[i - 1]["l"]:
            return i, b["c"]
        if side == "S" and b["h"] > bars[i - 1]["h"]:
            return i, b["c"]

        # 3. consolidation: no new extreme for N consecutive bars
        if bars_since_extreme >= CONSOLIDATION_BARS:
            return i, b["c"]

        # 4. clock
        if i >= CLOCK_BAR:
            return i, b["c"]

    i = CLOCK_BAR if n > CLOCK_BAR else n - 1
    return i, bars[i]["c"]


def policy_30_30_30_10(bars, entry_i, entry, stop, side, trail_method="atr"):
    return scale_out(bars, entry_i, entry, stop, side, [0.30, 0.30, 0.30, 0.10], trail_method)


def policy_50_20_20_10(bars, entry_i, entry, stop, side, trail_method="atr"):
    return scale_out(bars, entry_i, entry, stop, side, [0.50, 0.20, 0.20, 0.10], trail_method)


POLICIES = {
    "flat_1r": flat_1r,
    "flat_2r": flat_2r,
    "hod_only": hod_only,
    "30_30_30_10": policy_30_30_30_10,
    "50_20_20_10": policy_50_20_20_10,
}


def run_trade(trade, policies=None, trail_method="atr"):
    """Run every policy over one trade dict.

    ``trade`` keys: ``symbol, date, entry_i, entry, stop, side`` (entry/stop
    optional — fall back to the bar close at entry_i / None). Returns
    ``{policy_id: realised_R}``.
    """
    policies = policies or POLICIES
    bars = load_rth_bars(trade["symbol"], trade["date"])
    if not bars:
        return {pid: None for pid in policies}
    entry_i = trade["entry_i"]
    entry = trade.get("entry")
    if entry is None:
        entry = trade.get("entry_p")  # marks use entry_p
    if entry is None:
        entry = bars[entry_i]["c"] if entry_i < len(bars) else None
    stop = trade.get("stop")
    if stop is None:
        stop = trade.get("stop_p")  # marks use stop_p
    side = trade["side"]
    out = {}
    for pid, fn in policies.items():
        if entry is None or stop is None or entry_i >= len(bars):
            out[pid] = None
        else:
            out[pid] = fn(bars, entry_i, entry, stop, side, trail_method)
    return out


# ---------------------------------------------------------------------------
# selftest / calibration
# ---------------------------------------------------------------------------

def load_marks():
    trades = []
    for path in MARKS_FILES:
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("type") == "trade":
                trades.append(d)
    return trades


def selftest():
    """Replay the 64 marks, assert the causal-HOD exit bar lands within 5 bars
    of Austin's marked exit_i on at least half of them. Fail loudly otherwise.
    """
    trades = load_marks()
    total = len(trades)
    assert total == 64, f"expected 64 trade marks, got {total}"
    within = 0
    misses = []
    for t in trades:
        bars = load_rth_bars(t["symbol"], t["date"])
        if bars is None:
            misses.append((t, "no bars"))
            continue
        rule_i = causal_hod_exit_bar(bars, t["entry_i"], t["side"])
        austin_i = t.get("exit_i")
        if austin_i is None:
            misses.append((t, "no marked exit_i"))
            continue
        if rule_i is None:
            misses.append((t, "rule returned None"))
            continue
        if abs(rule_i - austin_i) <= 5:
            within += 1
        else:
            misses.append((t, f"rule={rule_i} austin={austin_i} diff={rule_i - austin_i}"))

    frac = within / total
    _write_calibration(frac, within, total, misses)

    # Loud failure when the rule cannot reproduce what his eye did.
    threshold = 0.5
    if frac < threshold:
        msg = selftest_failure_message(frac, threshold, misses)
        print(msg, file=sys.stderr)
        sys.exit(1)
    print(f"t3 selftest ok: hod_rule_within_5_bars = {frac:.4f} ({within}/{total})")


def selftest_failure_message(frac, threshold, misses):
    lines = [
        f"T3 SELFTEST FAILED: hod_rule_within_5_bars = {frac:.4f} < {threshold}",
        f"  {len(misses)} marks not within 5 bars of Austin's exit_i:",
    ]
    for t, why in misses[:20]:
        lines.append(f"    {t.get('symbol')} {t.get('date')} entry_i={t.get('entry_i')} "
                     f"side={t.get('side')} -> {why}")
    return "\n".join(lines)


def _write_calibration(frac, within, total, misses):
    path = os.path.join(os.path.dirname(__file__), "exit_lab_calibration.md")
    lines = [
        "# Exit-lab calibration (T3)",
        "",
        f"Replay of the {total} marked trades. The causal-HOD exit bar is compared",
        f"to Austin's marked `exit_i`; a hit is within 5 bars. Threshold to pass: 0.5.",
        "",
        f"hod_rule_within_5_bars: {frac:.6f}",
        "",
        f"hits: {within}",
        f"total: {total}",
        f"misses: {len(misses)}",
        "",
        "## Misses (rule exit bar vs Austin exit_i)",
        "",
    ]
    if not misses:
        lines.append("_(none)_")
    else:
        lines.append("| symbol | date | entry_i | side | rule | austin | diff | reason |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for t, why in misses:
            austin = t.get("exit_i")
            rule = None
            bars = load_rth_bars(t["symbol"], t["date"])
            if bars is not None:
                rule = causal_hod_exit_bar(bars, t["entry_i"], t["side"])
            diff = (rule - austin) if (rule is not None and austin is not None) else ""
            lines.append(f"| {t.get('symbol')} | {t.get('date')} | {t.get('entry_i')} | "
                         f"{t.get('side')} | {rule} | {austin} | {diff} | {why} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        print(__doc__)
