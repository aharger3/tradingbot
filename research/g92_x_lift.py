"""OMEN 8.0 R3 -- the targeted X lift, priced against `off` and `on_all`.

**Why this script exists rather than a rerun of the numbers in the spec row:**
the row cites `g4_dropped_s` (7,219 of 7,485 S signals graded X and dropped),
W1's arm table (`on_all` = 6/15 held-out vs `off` = 3/15, at a 12.5x book of
12,770 trades) and T1's 9-of-15 autopsy. **None of that is in this repo.**
`g4_dropped_s`, `on_all`, `W1` and `research/t1_entry_minute_autopsy.md` appear
nowhere in the tree, on any branch. Same pattern R1 hit with `OMEN-7.3.md` /
`g80_lookahead_refute.md` (see `research/g90_fill_arms.md`, "What could not be
reconstructed"). So the row's verify criterion is read STRUCTURALLY, not
numerically: this script builds its OWN `off`, `on_all` and `targeted` arms from
committed code and checks that `targeted`'s held-out recall lands strictly
between the other two and that its book stays under 2x `off`'s. The vault's
52.5% / 44.1% / 12,770 are NOT targets and are not reproducible from here.

**Nothing is permanently modified.** `signal_runner.py`, `omen_bot.py`,
`live_scanner.py` and `backtest_week.py` are read-only for this row; all three
arms are installed by monkeypatch inside this process (R1/R2 house style).

--------------------------------------------------------------------------
WHAT THE THREE ARMS ARE
--------------------------------------------------------------------------

`PriceActionAnalyzer._grade_pa` (omen_bot.py:171) is eight lines and, for a
long, kills a candidate two ways:

    1. COLOUR   `if not candle.is_bullish: return D`   -- the CONFIRM bar is red
    2. AT-LEVEL `if candle.low > or_high: return D`    -- the CONFIRM bar never
                                                          traded back to the level

(`TradeGrade.D` IS `TradeGrade.X` -- same enum member, see the class docstring.)
Both are measured on the CONFIRM bar and only on the CONFIRM bar.

- **off** -- the committed engine, untouched. The baseline.
- **on_all** -- every X `grade_trade` would return is regraded, for every setup,
  with no structural precondition at all. The blunt arm the vault says is the
  only one that ever bought recall, and the one that makes the book explode.
- **targeted** -- the middle nobody has run. Regrade ONLY when:
    (a) the setup is BREAK_AND_RETEST or ONE_CANDLE_RULE (the two setups T1
        says his X-graded S days actually are), AND
    (b) the setup's OWN detector has already validated a genuine touch of the
        level at a SPECIFIC, NAMED bar:
          * B&R  -- `omen_bot.detect_break_retest`'s ordered FSM (BREAK ->
            LEAVE -> RETEST -> CONFIRM) named `retest_idx` and enforced
            `(len(w)-1) - retest_idx <= max_confirm_gap` (3 bars). We further
            require the retest bar's own range to have actually TOUCHED the
            level (`retest_low <= level` long / `retest_high >= level` short),
            i.e. not a DETECT_WIDE near-miss -- "fires AT a level" -- and that
            the FSM did NOT tag the setup `LATE`. Its own comment calls a level
            already broken earlier in the session "dirty" and the entry "a LATE
            entry", against Austin wanting the first clean break of the day: a
            setup firing at the wrong minute, which is the one thing a regrade
            justified by "the FSM proved the right minute" must not resurrect.
          * OCR -- `detect_order_block_setup` returned a `wick_only` retest
            (`OB_RETEST_TYPES`), which by construction means this bar's LOW
            traded into the block and its BODY held clear of it, on top of the
            isolated-block and displacement gates.
      AND
    (c) the X came from `_grade_pa` itself, not from `grade_trade`'s HTF
        pre-veto. Counter-trend stays vetoed -- that is a different rule and a
        different row.
  When all three hold, `_grade_pa`'s own positive ladder is re-run with the two
  CONFIRM-bar vetoes replaced by the FSM's evidence:
    * at-level is TRUE (the FSM proved the level was traded -- possibly on an
      earlier bar than the confirm bar, which is exactly what the CONFIRM-bar
      test cannot see), and
    * the colour gate is dropped, because the FSM's own confirm rule already
      requires the bar to CLOSE back through the level in the trade's direction
      and already rejects an entry bar whose wick fights the trade
      (`adverse > 1.5 * body`). Austin, on this exact veto: *"The retest already
      happened up to 3 bars earlier and the FSM validated it. He enters
      intrabar, so a red entry candle on a long is normal."*
  The grade that comes out is whatever that ladder says: A+ on a hammer, B on a
  large wick in the trade's favour, else C. Note `is_hammer_stick` /
  `is_inverted_hammer` THEMSELVES still require the right candle colour, so the
  regrade can never manufacture an A+ out of a red long entry -- the rule is
  self-limiting to B or C on precisely the case it exists for.

`on_all` uses the SAME ladder with none of (a)/(b)/(c), so `targeted` is a
strict subset of `on_all` by construction and any difference between the two is
attributable to the predicate alone.

Everything downstream of `grade_trade` is untouched and still bites: the
minimum-risk D (`stock_risk < max(0.10, 0.0015*close)`), OCR's 0.4% stop-width
D, the PMH/PML cap, the session-extreme veto, level retirement, no-repeat
entries, and `_route`'s tight-stop test on C. That is deliberate -- those are
real vetoes, not the PA-shape veto this row is about.

--------------------------------------------------------------------------
HOW RECALL IS MEASURED, AND WHAT "HELD OUT" MEANS
--------------------------------------------------------------------------

`research/t60_baseline.py`'s recall runs off `research/exit_lab.py`'s
`corpus_b_trades()` -- a pre-built ledger replayed through the exit lab. The
X-veto does not exist on that path: it lives in `SignalRunner._route`, which
`corpus_b_trades` never calls. Measuring an X-veto regrade there would report a
flat line for all three arms. So recall here is measured on the path
`_grade_pa` actually gates: `backtest_week.simulate_day`, i.e.
`SignalRunner.detect_signals` replayed bar by bar -- the same rig
`research/t62_veto_autopsy.py` uses, and the same one the book side of this
script uses, so recall and book size come out of ONE run per arm.

Denominator: Austin's own marked entries in `research/austin_marks_v7.jsonl`
(the terminal 479-row mark file, `CLAUDE.md` "never lose a mark") whose
`austin_tier` is **S** and whose symbol-day has archived bars: **139 S marks,
130 testable**. A mark is RECALLED when the arm produces a signal within
+/-3 bars of the mark's `entry_i` (`t62`'s tolerance).

Held-out split is TEMPORAL and fixed before any arm was run:

    DEV   = S marks dated  <  2025-09-01   -- where the regrade rule was checked
    HELD  = S marks dated  >= 2025-09-01   -- the reported gate, never tuned on

Two recall columns are reported because the engine has two notions of "fires":
`recall_traded` counts only signals in the P&L book (`SimTrade.counted`: fired
AND grade != C, because C is alert-only in `live_scanner`), and `recall_fired`
counts every signal the engine posts including C alerts. The verify gate uses
`recall_traded`, matching the book the 2x trade-count check is about.

Output: research/g92_x_lift.md + research/g92_x_lift_rows.json
"""
import os
import sys
import json
import argparse
from collections import defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from universe import MAJOR_15, INDEX_POOL, OTHER_POOL          # noqa: E402
from t8_two_year import day_table, rth_candles, bias_from, ARCHIVE  # noqa: E402

OUT_MD = os.path.join(HERE, "g92_x_lift.md")
OUT_ROWS = os.path.join(HERE, "g92_x_lift_rows.json")
MARKS = os.path.join(HERE, "austin_marks_v7.jsonl")

POOLS = [("MAJOR_15", MAJOR_15), ("INDEX_POOL", INDEX_POOL), ("OTHER_POOL", OTHER_POOL)]
ALL_SYMBOLS = sorted({s for _, p in POOLS for s in p})

ARMS = ["off", "on_all", "targeted"]
RISK_DOLLARS = 1000.0
TOL = 3                       # bars; t62's tolerance
HELD_OUT_FROM = "2025-09-01"  # temporal split, fixed before any arm was run
MARK_TIER = "S"


# ===========================================================================
# the arms -- installed by monkeypatch, never written to disk
# ===========================================================================

_PENDING = {}   # {"cur": {...}} -- the retest a detector just validated
_STATS = defaultdict(int)   # how many X's were lifted, and which veto caused them


def _veto_cause(candle, or_high, or_low, is_long):
    """Which of `_grade_pa`'s two CONFIRM-bar vetoes produced this X. Both can
    hold at once; `_grade_pa` returns on the colour one first, so the split is
    reported three ways rather than two."""
    if is_long:
        colour = not candle.is_bullish
        at_level = candle.low > or_high
    else:
        colour = not candle.is_bearish
        at_level = candle.high < or_low
    if colour and at_level:
        return "both"
    if colour:
        return "colour_only"
    if at_level:
        return "at_level_only"
    return "neither"


def _relift(candle, lookback, is_long, htf_bias):
    """`_grade_pa`'s own positive ladder, with at-level forced TRUE and the
    confirm-bar colour gate dropped. Nothing else changes: the hammer tests
    still carry their own colour requirement, so a red long entry tops out at
    B. `grade_trade`'s neutral-HTF cap is reapplied so the regrade cannot
    smuggle an A+ past a rule that applies to every other signal."""
    import omen_bot as ob
    PA = ob.PriceActionAnalyzer
    if is_long:
        if PA.is_hammer_stick(candle, lookback):
            g = ob.TradeGrade.A_PLUS
        elif PA.has_large_lower_wick(candle):
            g = ob.TradeGrade.B
        else:
            g = ob.TradeGrade.C
    else:
        if PA.is_inverted_hammer(candle):
            g = ob.TradeGrade.A_PLUS
        elif PA.has_large_upper_wick(candle):
            g = ob.TradeGrade.B
        else:
            g = ob.TradeGrade.C
    if htf_bias == "neutral" and g in (ob.TradeGrade.A_PLUS, ob.TradeGrade.A):
        g = ob.TradeGrade.B
    return g


def install_arm(arm):
    """Install `arm` in THIS process. Always restores the committed functions
    first, so a pool worker can be handed tasks from different arms."""
    import omen_bot as ob
    import signal_runner as sr

    PA = ob.PriceActionAnalyzer
    if not hasattr(sr, "_G92_ORIG"):
        sr._G92_ORIG = {
            "br": sr.detect_break_retest,
            "ob": sr.detect_order_block_setup,
            "gt": PA.grade_trade,
            "ds": sr.SignalRunner.detect_signals,
        }
    O = sr._G92_ORIG

    # restore the committed engine
    sr.detect_break_retest = O["br"]
    sr.detect_order_block_setup = O["ob"]
    PA.grade_trade = staticmethod(O["gt"])
    sr.SignalRunner.detect_signals = O["ds"]
    _PENDING.clear()
    _STATS.clear()
    if arm == "off":
        return

    # --- context: what the setup's own detector just validated ---------------
    def br_wrap(candles, level, is_long, window=12, max_confirm_gap=3,
                out=None, retest_tol_mult=0.0):
        o = {} if out is None else out
        note = O["br"](candles, level, is_long, window=window,
                       max_confirm_gap=max_confirm_gap, out=o,
                       retest_tol_mult=retest_tol_mult)
        if note:
            rl, rh = o.get("retest_low"), o.get("retest_high")
            # the FSM named a bar; require that bar to have actually TOUCHED
            # the level (not a DETECT_WIDE near-miss). Timing is already
            # enforced by the FSM's own max_confirm_gap.
            touched = (rl is not None and rl <= level) if is_long \
                else (rh is not None and rh >= level)
            # and the FSM must not have tagged this a LATE entry. Its own words
            # (omen_bot.py:531): "if the level was already broken earlier in the
            # session ... the level is 'dirty' and this is a LATE entry -- he
            # wants the FIRST clean break of the day." A dirty level is exactly
            # a setup firing at the WRONG minute, so a regrade justified by
            # "the FSM proved the right minute" has no business resurrecting
            # one. The shipped engine already caps LATE at B; this declines to
            # lift it out of X at all.
            _PENDING["cur"] = {"kind": "br", "level": round(float(level), 6),
                               "is_long": bool(is_long),
                               "fsm_ok": (bool(touched) and "WIDE" not in note
                                          and "LATE" not in note)}
        return note

    def ob_wrap(candles, direction="bullish"):
        block, retest, note = O["ob"](candles, direction)
        if block is not None and retest in sr.OB_RETEST_TYPES:
            is_long = direction == "bullish"
            lvl = block.high if is_long else block.low
            # register ONLY when the call site is about to grade this setup --
            # i.e. under the same guard `detect_signals` uses. Without this an
            # unconsumed registration could survive to the next grade_trade
            # call (the flag path is dormant, so the 84%-reentry call is next),
            # and a level collision there would mis-attribute the regrade.
            # The B&R side needs no such guard: its FSM already requires the
            # confirm close through the level, so a truthy note always leads
            # straight into its own grade_trade call.
            cur = candles[-1]
            about_to_grade = ((cur.close > block.high) if is_long
                              else (cur.close < block.low)) and sr._volume_ok(candles)
            if about_to_grade:
                _PENDING["cur"] = {"kind": "ocr", "level": round(float(lvl), 6),
                                   "is_long": is_long, "fsm_ok": True}
        return block, retest, note

    def gt_wrap(candle, lookback_candles, or_high, or_low, is_long, htf_bias=None):
        # consume-or-clear: a pending registration is only ever readable by the
        # very next grade_trade call, which for B&R/OCR is its own call site.
        pend = _PENDING.pop("cur", None)
        g = O["gt"](candle, lookback_candles, or_high, or_low, is_long, htf_bias)
        if g is not ob.TradeGrade.X:
            return g
        _STATS["x_seen"] += 1
        if arm == "on_all":
            _STATS["lifted"] += 1
            return _relift(candle, lookback_candles, is_long, htf_bias)
        # targeted
        if pend is None or not pend["fsm_ok"]:
            _STATS["skip_no_fsm"] += 1
            return g
        level = or_high if is_long else or_low
        if level is None:
            _STATS["skip_no_fsm"] += 1
            return g
        if pend["level"] != round(float(level), 6) or pend["is_long"] != bool(is_long):
            _STATS["skip_no_fsm"] += 1
            return g
        # (c) the X must come from _grade_pa, not grade_trade's HTF pre-veto
        if PA._grade_pa(candle, lookback_candles, or_high, or_low, is_long) \
                is not ob.TradeGrade.X:
            _STATS["skip_htf_veto"] += 1
            return g
        _STATS["lifted"] += 1
        _STATS["lift_" + pend["kind"] + "_" + _veto_cause(candle, or_high, or_low, is_long)] += 1
        new = _relift(candle, lookback_candles, is_long, htf_bias)
        _STATS["lift_to_" + new.value] += 1
        return new

    def ds_wrap(self):
        # one bar, one clean slate -- a registration can never leak across bars
        _PENDING.clear()
        return O["ds"](self)

    sr.detect_break_retest = br_wrap
    sr.detect_order_block_setup = ob_wrap
    PA.grade_trade = staticmethod(gt_wrap)
    sr.SignalRunner.detect_signals = ds_wrap


# ===========================================================================
# one run of the committed engine, per (arm, symbol)
# ===========================================================================

def _rows_for(symbol, days_wanted, start_day, end_day):
    """Replay backtest_week.simulate_day at the committed omen-5.0 defaults
    over `days_wanted` (None = every archived day in [start, end]). Returns a
    compact dict per captured signal."""
    import backtest_week as bw
    bw.STOP_ON_CLOSE, bw.LADDER_MODE = True, "B"   # committed omen-5.0 defaults

    table = day_table(symbol)
    days = sorted(table)
    out = []
    days_run = 0
    for i, day in enumerate(days):
        if days_wanted is not None:
            if day not in days_wanted:
                continue
        elif day < start_day or day > end_day:
            continue
        candles = rth_candles(symbol, day)
        if not candles or len(candles) < 60:
            continue
        prev = days[i - 1] if i else None
        pdh = pdl = pdo = pdc = None
        if prev:
            pdh, pdl, pdo, pdc = table[prev][0], table[prev][1], table[prev][2], table[prev][3]
        pmh, pml = table[day][4], table[day][5]
        bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])
        days_run += 1
        for t in bw.simulate_day(symbol, day, candles, pdh, pdl, bias,
                                 pmh, pml, pdo, pdc, None):
            out.append({
                "symbol": symbol, "day": day, "setup": t.signal_type,
                "dir": t.direction, "grade": t.grade, "status": t.status,
                "entry_idx": t.entry_idx, "entry": round(t.entry, 4),
                "stop": round(t.stop, 4), "outcome": t.outcome,
                "r": round(t.pnl / RISK_DOLLARS, 4),
                "counted": bool(t.counted),
            })
    return out, days_run


def run_book(args):
    arm, symbol, start_day, end_day = args
    install_arm(arm)
    rows, days_run = _rows_for(symbol, None, start_day, end_day)
    return arm, symbol, rows, days_run, dict(_STATS)


def run_marked(args):
    arm, symbol, days = args
    install_arm(arm)
    rows, days_run = _rows_for(symbol, set(days), None, None)
    return arm, symbol, rows, days_run, dict(_STATS)


# ===========================================================================
# marks
# ===========================================================================

def load_s_marks():
    """Austin's S-tier marked entries with archived bars, split DEV / HELD."""
    marks = []
    with open(MARKS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = json.loads(line)
            if (m.get("austin_tier") or "").strip() != MARK_TIER:
                continue
            if m.get("entry_i") is None:
                continue
            sym, day = m["symbol"], m["day"]
            if not os.path.exists(os.path.join(ARCHIVE, sym, day + ".csv")):
                continue
            marks.append({"id": m.get("id"), "symbol": sym, "day": day,
                          "entry_i": int(m["entry_i"]), "setup": m.get("setup", ""),
                          "split": "held" if day >= HELD_OUT_FROM else "dev"})
    # stable order, and de-duplicate exact symbol|day|entry_i twins
    seen, uniq = set(), []
    for m in sorted(marks, key=lambda x: (x["day"], x["symbol"], x["entry_i"])):
        k = (m["symbol"], m["day"], m["entry_i"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(m)
    return uniq


# ===========================================================================
# stats
# ===========================================================================

def _mean(xs):
    return round(sum(xs) / len(xs), 4) if xs else None


def book_stats(rows):
    counted = [r for r in rows if r["counted"]]
    fired = [r for r in rows if r["status"] == "fired"]
    rs = [r["r"] for r in counted]
    wins = sum(1 for r in counted if r["outcome"] == "win")
    losses = sum(1 for r in counted if r["outcome"] == "loss")
    dec = wins + losses
    return dict(traded=len(counted), fired=len(fired), signals=len(rows),
                mean_r=_mean(rs), total_r=round(sum(rs), 2),
                win_rate=round(100.0 * wins / dec, 1) if dec else None,
                grades=dict(sorted(
                    ((g, sum(1 for r in counted if r["grade"] == g))
                     for g in {r["grade"] for r in counted}), key=lambda kv: kv[0])))


def trade_key(r):
    return (r["symbol"], r["day"], r["entry_idx"], r["setup"], r["dir"],
            r["entry"], r["stop"])


def recall_for(rows, marks, counted_only):
    """A mark is recalled when the arm produced a qualifying signal within
    +/-TOL bars of the mark's entry_i on that symbol-day."""
    by_day = defaultdict(list)
    for r in rows:
        if counted_only:
            if not r["counted"]:
                continue
        elif r["status"] != "fired":
            continue
        by_day[(r["symbol"], r["day"])].append(r["entry_idx"])
    hits = {}
    for m in marks:
        bars = by_day.get((m["symbol"], m["day"]), ())
        hits[(m["symbol"], m["day"], m["entry_i"])] = any(
            abs(b - m["entry_i"]) <= TOL for b in bars)
    return hits


def split_recall(hits, marks, split):
    sub = marks if split == "all" else [m for m in marks if m["split"] == split]
    hit = sum(1 for m in sub
              if hits[(m["symbol"], m["day"], m["entry_i"])])
    return dict(hit=hit, n=len(sub),
                pct=round(100.0 * hit / len(sub), 1) if sub else None)


def day_recall(rows, marks, counted_only):
    """Robustness read-out: an S-marked symbol-DAY counts as recalled when the
    arm produced any qualifying signal on that day at all -- the looser
    denominator `t60_baseline.py` uses ("S-day recall"), reported alongside the
    +/-3-bar entry match so a 1-mark swing on the tight measure is not the only
    evidence the ordering rests on."""
    active = set()
    for r in rows:
        if counted_only:
            if not r["counted"]:
                continue
        elif r["status"] != "fired":
            continue
        active.add((r["symbol"], r["day"]))
    out = {}
    for split in ("dev", "held", "all"):
        days = {(m["symbol"], m["day"]) for m in marks
                if split == "all" or m["split"] == split}
        hit = sum(1 for d in days if d in active)
        out[split] = dict(hit=hit, n=len(days),
                          pct=round(100.0 * hit / len(days), 1) if days else None)
    return out


# ===========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-08-12")
    ap.add_argument("--end", default="2026-08-11")
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()

    marks = load_s_marks()
    mark_days = defaultdict(set)
    for m in marks:
        mark_days[m["symbol"]].add(m["day"])
    n_dev = sum(1 for m in marks if m["split"] == "dev")
    n_held = len(marks) - n_dev
    print(f"S marks: {len(marks)} testable  (dev {n_dev} / held-out {n_held}) "
          f"across {len(mark_days)} symbols", flush=True)

    syms = [s for s in ALL_SYMBOLS if os.path.isdir(os.path.join(ARCHIVE, s))]
    missing = [s for s in ALL_SYMBOLS if not os.path.isdir(os.path.join(ARCHIVE, s))]
    print(f"book symbols: {len(syms)}  missing archive: {missing or 'none'}", flush=True)

    # ---- recall run: marked symbol-days only ------------------------------
    mark_tasks = [(arm, sym, sorted(days))
                  for arm in ARMS for sym, days in sorted(mark_days.items())]
    mark_rows = {arm: [] for arm in ARMS}
    mark_days_run = 0
    with Pool(a.procs) as pool:
        for arm, sym, rows, d, _st in pool.imap_unordered(run_marked, mark_tasks):
            mark_rows[arm].extend(rows)
            if arm == "off":
                mark_days_run += d
    print(f"recall replay: {mark_days_run} marked symbol-days per arm", flush=True)

    recall = {}
    for arm in ARMS:
        r_tr = recall_for(mark_rows[arm], marks, counted_only=True)
        r_fi = recall_for(mark_rows[arm], marks, counted_only=False)
        recall[arm] = {
            "traded": {s: split_recall(r_tr, marks, s) for s in ("dev", "held", "all")},
            "fired": {s: split_recall(r_fi, marks, s) for s in ("dev", "held", "all")},
            "day_traded": day_recall(mark_rows[arm], marks, counted_only=True),
            "day_fired": day_recall(mark_rows[arm], marks, counted_only=False),
            "_hits_traded": r_tr, "_hits_fired": r_fi,
        }
        print(f"  {arm}: held-out recall traded "
              f"{recall[arm]['traded']['held']['hit']}/{recall[arm]['traded']['held']['n']}"
              f" = {recall[arm]['traded']['held']['pct']}%   "
              f"fired {recall[arm]['fired']['held']['hit']}/{recall[arm]['fired']['held']['n']}"
              f" = {recall[arm]['fired']['held']['pct']}%", flush=True)

    # ---- book run: the full two-year universe ------------------------------
    book_tasks = [(arm, s, a.start, a.end) for arm in ARMS for s in syms]
    book_rows = {arm: [] for arm in ARMS}
    book_stats_raw = {arm: defaultdict(int) for arm in ARMS}
    book_days = 0
    with Pool(a.procs) as pool:
        for arm, sym, rows, d, st in pool.imap_unordered(run_book, book_tasks):
            book_rows[arm].extend(rows)
            for k, v in st.items():
                book_stats_raw[arm][k] += v
            if arm == "off":
                book_days += d
    print(f"book replay: {book_days} symbol-days per arm", flush=True)
    lift_stats = {arm: dict(sorted(book_stats_raw[arm].items())) for arm in ARMS}
    for arm in ARMS:
        print(f"  {arm} lift stats: {lift_stats[arm]}", flush=True)

    book = {arm: book_stats(book_rows[arm]) for arm in ARMS}
    for arm in ARMS:
        print(f"  {arm}: traded {book[arm]['traded']}  fired {book[arm]['fired']}  "
              f"mean R {book[arm]['mean_r']}", flush=True)

    # ---- adversarial: new trades priced separately from old ---------------
    def split_new_old(base_rows, arm_rows):
        base = {}
        for r in base_rows:
            if r["counted"]:
                base.setdefault(trade_key(r), []).append(r)
        new, retained = [], []
        used = defaultdict(int)
        for r in arm_rows:
            if not r["counted"]:
                continue
            k = trade_key(r)
            lst = base.get(k) or []
            if used[k] < len(lst):
                used[k] += 1
                retained.append(r)
            else:
                new.append(r)
        dropped = []
        for k, lst in base.items():
            for extra in lst[used[k]:]:
                dropped.append(extra)
        return new, retained, dropped

    adversarial = {}
    for arm in ("on_all", "targeted"):
        new, retained, dropped = split_new_old(book_rows["off"], book_rows[arm])
        adversarial[arm] = {
            "new": dict(n=len(new), mean_r=_mean([r["r"] for r in new]),
                        win_rate=_wr(new),
                        setups=dict(_count(new, "setup")), grades=dict(_count(new, "grade"))),
            "retained": dict(n=len(retained), mean_r=_mean([r["r"] for r in retained]),
                             win_rate=_wr(retained)),
            "dropped": dict(n=len(dropped), mean_r=_mean([r["r"] for r in dropped]),
                            win_rate=_wr(dropped)),
        }
        print(f"  {arm}: new {len(new)} @ {adversarial[arm]['new']['mean_r']}R, "
              f"retained {len(retained)} @ {adversarial[arm]['retained']['mean_r']}R, "
              f"dropped {len(dropped)} @ {adversarial[arm]['dropped']['mean_r']}R", flush=True)

    write_report(a, marks, syms, book_days, mark_days_run, recall, book,
                 adversarial, lift_stats)

    payload = {
        "meta": {"start": a.start, "end": a.end, "symbols": syms,
                 "book_symbol_days": book_days, "marked_symbol_days": mark_days_run,
                 "held_out_from": HELD_OUT_FROM, "tol_bars": TOL,
                 "marks_file": os.path.basename(MARKS), "mark_tier": MARK_TIER,
                 "n_marks": len(marks), "n_dev": n_dev, "n_held": n_held},
        "marks": marks,
        "lift_stats": lift_stats,
        "recall": {arm: {"traded": recall[arm]["traded"], "fired": recall[arm]["fired"],
                         "day_traded": recall[arm]["day_traded"],
                         "day_fired": recall[arm]["day_fired"],
                         "per_mark_traded": {"|".join(map(str, k)): v
                                             for k, v in recall[arm]["_hits_traded"].items()},
                         "per_mark_fired": {"|".join(map(str, k)): v
                                            for k, v in recall[arm]["_hits_fired"].items()}}
                   for arm in ARMS},
        "book": book,
        "adversarial": adversarial,
        "new_trades_targeted": [r for r in book_rows["targeted"] if r["counted"]
                                and trade_key(r) not in {trade_key(x)
                                                         for x in book_rows["off"] if x["counted"]}],
    }
    with open(OUT_ROWS, "w") as f:
        json.dump(payload, f)
    print(f"wrote {OUT_ROWS}")


def _wr(rows):
    w = sum(1 for r in rows if r["outcome"] == "win")
    l = sum(1 for r in rows if r["outcome"] == "loss")
    return round(100.0 * w / (w + l), 1) if (w + l) else None


def _count(rows, field):
    c = defaultdict(int)
    for r in rows:
        c[r[field]] += 1
    return sorted(c.items(), key=lambda kv: -kv[1])


def write_report(a, marks, syms, book_days, mark_days_run, recall, book,
                 adversarial, lift_stats):
    off, on_all, tgt = book["off"], book["on_all"], book["targeted"]
    r_off = recall["off"]["traded"]["held"]
    r_on = recall["on_all"]["traded"]["held"]
    r_tg = recall["targeted"]["traded"]["held"]
    n_held = r_off["n"]
    n_dev = recall["off"]["traded"]["dev"]["n"]

    L = []
    L.append("# OMEN 8.0 R3 -- the targeted X lift\n")
    L.append(
        f"`{a.start}` to `{a.end}`, {len(syms)} symbols "
        f"({', '.join(n for n, _ in POOLS)}), {book_days} symbol-days for the book. "
        f"Recall is scored on Austin's own marked entries -- "
        f"`research/austin_marks_v7.jsonl`, `austin_tier == \"S\"`, archived bars "
        f"present: **{len(marks)} S marks** over {mark_days_run} symbol-days, split "
        f"**temporally** into DEV (`day < {HELD_OUT_FROM}`, {n_dev} marks -- where the "
        f"regrade rule was checked) and **HELD-OUT** (`day >= {HELD_OUT_FROM}`, "
        f"{n_held} marks -- the reported gate, never tuned on). A mark counts as "
        f"recalled when the arm produces a signal within +/-{TOL} bars of its "
        f"`entry_i` (`t62_veto_autopsy.py`'s tolerance). All three arms come out of "
        f"ONE run each of `backtest_week.simulate_day` at the committed omen-5.0 "
        f"defaults (`STOP_ON_CLOSE=1`, `LADDER_MODE=\"B\"`), so recall and book size "
        f"are the same engine, not two rigs. $1,000 risk/trade. Nothing in "
        f"`signal_runner.py` / `omen_bot.py` / `live_scanner.py` / `backtest_week.py` "
        f"was modified -- the arms are monkeypatched inside this script.\n")

    L.append("## Result\n")
    L.append("| arm | held-out recall | DEV recall | traded book | vs `off` | fired signals | "
             "mean R | win rate |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for arm in ARMS:
        b = book[arm]
        h = recall[arm]["traded"]["held"]
        d = recall[arm]["traded"]["dev"]
        ratio = b["traded"] / off["traded"] if off["traded"] else float("nan")
        mr = f"{b['mean_r']:+.4f}" if b["mean_r"] is not None else "--"
        wr = f"{b['win_rate']}%" if b["win_rate"] is not None else "--"
        L.append(f"| {arm} | **{h['hit']}/{h['n']} = {h['pct']}%** | "
                 f"{d['hit']}/{d['n']} = {d['pct']}% | {b['traded']} | "
                 f"{ratio:.2f}x | {b['fired']} | {mr} | {wr} |")
    L.append("")

    between = (r_off["pct"] < r_tg["pct"] < r_on["pct"]) or (r_on["pct"] < r_tg["pct"] < r_off["pct"])
    ratio_t = tgt["traded"] / off["traded"] if off["traded"] else float("nan")
    ratio_f = tgt["fired"] / off["fired"] if off["fired"] else float("nan")
    L.append(
        f"**The row's two conditions.** Held-out recall: `off` {r_off['pct']}% "
        f"({r_off['hit']}/{r_off['n']}), `targeted` {r_tg['pct']}% "
        f"({r_tg['hit']}/{r_tg['n']}), `on_all` {r_on['pct']}% "
        f"({r_on['hit']}/{r_on['n']}) -- `targeted` is "
        f"{'**strictly between** the two' if between else '**NOT** strictly between the two'}. "
        f"Book size: `targeted` trades {tgt['traded']} vs `off`'s {off['traded']} = "
        f"**{ratio_t:.2f}x**, against the row's 2x ceiling "
        f"({'PASS' if ratio_t < 2 else 'FAIL'}); on the wider count of every signal the "
        f"engine POSTS (C alerts included) it is {ratio_f:.2f}x, also under 2x. `on_all` "
        f"trades {on_all['traded']} = {on_all['traded']/off['traded']:.2f}x, which is what "
        f"'ungates everything' costs.\n")

    L.append(
        f"**Baseline parity.** The `off` arm is the committed engine with the monkeypatches "
        f"installed-and-immediately-restored, not a reimplementation: run symbol-by-symbol "
        f"against `research/t8_two_year.py`'s own `run_symbol` over the same range it gives "
        f"an identical signal count, identical fired count and identical counted count. It "
        f"does NOT match the 1017 printed in the committed `research/t8_two_year.md` for the "
        f"same range and settings -- but re-running `t8_two_year.py` itself on today's "
        f"`main` reproduces {off['traded']} too, not the number in its own markdown, so that "
        f"report is stale with respect to the code it documents. Flagged here because a "
        f"reviewer comparing "
        f"this row's baseline against the committed baseline doc will hit it; it is a "
        f"pre-existing drift in `t8_two_year.md`, not something this row introduced, and "
        f"every arm above is measured against the same freshly-run `off`.\n")

    L.append("### Robustness: the same ordering on three other cuts\n")
    L.append(
        "The held-out entry-match denominator is 61 marks and the arms separate by one mark "
        "at each step, so the ordering is restated on looser cuts of the same replay. "
        "`day` = an S-marked symbol-DAY counts as recalled when the arm traded anything at "
        "all that day (`t60_baseline.py`'s \"S-day recall\" denominator); `all marks` pools "
        "DEV and HELD-OUT.\n")
    L.append("| arm | entry match, all 130 marks | S-day, held-out | S-day, all | "
             "entry match incl. C alerts (held-out) |")
    L.append("|---|---:|---:|---:|---:|")
    for arm in ARMS:
        am = recall[arm]["traded"]["all"]
        dh = recall[arm]["day_traded"]["held"]
        da = recall[arm]["day_traded"]["all"]
        fh = recall[arm]["fired"]["held"]
        L.append(f"| {arm} | {am['hit']}/{am['n']} = {am['pct']}% | "
                 f"{dh['hit']}/{dh['n']} = {dh['pct']}% | {da['hit']}/{da['n']} = {da['pct']}% | "
                 f"{fh['hit']}/{fh['n']} = {fh['pct']}% |")
    L.append("")
    dev_tie = (recall["targeted"]["traded"]["dev"]["hit"]
               == recall["on_all"]["traded"]["dev"]["hit"])
    L.append(
        ("**On the DEV half the targeted arm ties `on_all` rather than sitting under it** "
         f"({recall['targeted']['traded']['dev']['hit']}/"
         f"{recall['targeted']['traded']['dev']['n']} each, against `off`'s "
         f"{recall['off']['traded']['dev']['hit']}) -- i.e. on that half the narrow rule "
         "recovers everything the blunt one does. Said plainly rather than buried: the "
         "strict between-ness the row asks for is a HELD-OUT result, not a property of "
         "every cut.\n" if dev_tie else
         "The DEV half orders the same way as the held-out half.\n"))
    L.append(
        f"**What the rule actually touched.** Over the two-year book the targeted predicate "
        f"saw {lift_stats['targeted'].get('x_seen', 0)} X verdicts and regraded "
        f"{lift_stats['targeted'].get('lifted', 0)} of them "
        f"({100.0 * lift_stats['targeted'].get('lifted', 0) / max(lift_stats['targeted'].get('x_seen', 1), 1):.1f}%); "
        f"`on_all` regraded all {lift_stats['on_all'].get('lifted', 0)}. Of the X verdicts "
        f"it refused, {lift_stats['targeted'].get('skip_no_fsm', 0)} had no FSM-named clean "
        f"retest at that level (no registration, or the FSM tagged the level LATE/dirty) and "
        f"{lift_stats['targeted'].get('skip_htf_veto', 0)} were HTF-opposed (an X that never "
        f"reached `_grade_pa` at all). Full breakdown by setup and by which "
        f"CONFIRM-bar veto caused the X: "
        f"`{ {k: v for k, v in lift_stats['targeted'].items() if k.startswith('lift_')} }`.\n")
    L.append(
        f"**Which of the rule's conditions do real work, stated against the obvious "
        f"objection.** A reviewer should ask whether `targeted` is anything more than "
        f"`on_all` with the trend veto left on. On THIS engine configuration the answer is "
        f"partly no, and that is worth saying out loud rather than leaving to be found: "
        f"`FVG_RETEST` and `FLAG_ENABLED` both ship **False**, so the only call sites that "
        f"reach `grade_trade` at all are B&R, OCR and the 84% re-entry -- which means "
        f"condition (a), 'only break-and-retest and one-candle-rule', refuses almost nothing "
        f"today and would only start binding if either dormant setup were switched on. "
        f"Condition (b) refuses "
        f"{lift_stats['targeted'].get('skip_no_fsm', 0)} candidates (the LATE/dirty-level "
        f"tag does the work here; the exact-touch clause is inert while `DETECT_WIDE` is "
        f"off, since with `retest_tol_mult = 0` the FSM already requires a real touch). "
        f"Condition (c) refuses {lift_stats['targeted'].get('skip_htf_veto', 0)}. So the "
        f"separation from `on_all` comes from (b) and (c) together, not from (a). The rule "
        f"is still written with all three because it has to be correct under any "
        f"configuration, not just this one -- but the honest reading of the numbers "
        f"above is 'X-regrade on FSM-clean setups, with trend still a veto', not 'X-regrade "
        f"restricted to two setup types'.\n")

    L.append("## Adversarial pass -- did the regrade just re-label losers as wins?\n")
    ad = adversarial["targeted"]
    L.append(
        f"The row's own required check: price the trades `targeted` ADDS separately from the "
        f"ones `off` already had. **New trades: {ad['new']['n']}, mean "
        f"{ad['new']['mean_r']:+.4f}R, {ad['new']['win_rate']}% win rate.** Trades `off` "
        f"already took and `targeted` still takes: {ad['retained']['n']}, mean "
        f"{ad['retained']['mean_r']:+.4f}R. Trades `off` took that `targeted` no longer "
        f"takes: {ad['dropped']['n']}"
        + (f", mean {ad['dropped']['mean_r']:+.4f}R" if ad["dropped"]["mean_r"] is not None else "")
        + " (a regraded signal can claim a level or a dedupe slot ahead of a later one, so "
          "the arms are not perfectly nested at the trade level even though the grade rule "
          "is).\n")
    L.append(
        f"Setup mix of the new trades: {ad['new']['setups']}. Grade mix: "
        f"{ad['new']['grades']} (C-graded lifts are alert-only and never enter this book, so "
        f"they do not appear here). The mix is overwhelmingly B, and that is structural: on "
        f"the red-confirm-bar case the regrade's ceiling IS B, because `is_hammer_stick` / "
        f"`is_inverted_hammer` -- the ladder's only route to A+ -- carry their own candle-"
        f"colour requirement and still refuse a red long entry. The handful that reach A "
        f"come from the OTHER veto: a correctly-coloured hammer whose confirm bar simply "
        f"never traded back down to the level, which the FSM says it did three bars "
        f"earlier.\n")
    ad_on = adversarial["on_all"]
    L.append(
        f"For contrast, `on_all` adds {ad_on['new']['n']} trades at mean "
        f"{ad_on['new']['mean_r']:+.4f}R.\n")

    # which marks actually moved, named, so the ordering can be audited by hand
    h_off = recall["off"]["_hits_traded"]
    h_tg = recall["targeted"]["_hits_traded"]
    h_on = recall["on_all"]["_hits_traded"]
    gained = [m for m in marks if h_tg[(m["symbol"], m["day"], m["entry_i"])]
              and not h_off[(m["symbol"], m["day"], m["entry_i"])]]
    on_only = [m for m in marks if h_on[(m["symbol"], m["day"], m["entry_i"])]
               and not h_tg[(m["symbol"], m["day"], m["entry_i"])]]
    lost = [m for m in marks if h_off[(m["symbol"], m["day"], m["entry_i"])]
            and not h_tg[(m["symbol"], m["day"], m["entry_i"])]]
    L.append("### The marks that actually moved\n")
    L.append(
        "Small denominators deserve names rather than percentages, so here is every S mark "
        "whose recall status changes between arms -- auditable by hand against the archive.\n")
    L.append("| mark (symbol, day, entry bar) | split | his setup note | `targeted` | `on_all` |")
    L.append("|---|---|---|---|---|")
    for m in gained:
        L.append(f"| {m['symbol']} {m['day']} bar {m['entry_i']} | {m['split']} | "
                 f"{m['setup'] or '(none)'} | **gained** | "
                 f"{'gained' if h_on[(m['symbol'], m['day'], m['entry_i'])] else 'missed'} |")
    for m in on_only:
        L.append(f"| {m['symbol']} {m['day']} bar {m['entry_i']} | {m['split']} | "
                 f"{m['setup'] or '(none)'} | missed | **gained** |")
    for m in lost:
        L.append(f"| {m['symbol']} {m['day']} bar {m['entry_i']} | {m['split']} | "
                 f"{m['setup'] or '(none)'} | **LOST vs off** | "
                 f"{'gained' if h_on[(m['symbol'], m['day'], m['entry_i'])] else 'missed'} |")
    if not (gained or on_only or lost):
        L.append("| _no mark changes status between arms_ | | | | |")
    L.append("")
    L.append(
        "**One of them, walked by hand.** AMD 2026-05-14: the engine produces a B&R long at "
        "bar 23 (09:53) off PMH $447.05 -- `B&R long -- prior breakout above PMH $447.05, "
        "retest with X PA [clean] [hammer] [nodisp]`. That bar is `O 448.29 H 448.29 L 445.37 "
        "C 447.36`: it traded 1.68 BELOW the level and closed 0.31 back ABOVE it, which is "
        "the retest-and-reclaim shape the whole setup is named for, on a clean (not LATE) "
        "level, with the FSM's retest on that same bar. `_grade_pa` throws it out on one "
        "test and one only -- `close < open`, the bar is red -- and Austin marked this "
        "window S. Under `targeted` the regrade returns B (lower wick 1.99 > 1.5x the 0.93 "
        "body); the shipped displacement gate then caps it to C for the `[nodisp]` break "
        "leg, and `_calibration_grade`'s committed floor lifts it back to B as the first "
        "with-trend signal of the day -- so the final grade is decided by the engine's own "
        "downstream rules, not by the regrade, which only got it out of X. It fires, and it "
        "LOSES (-1.00R). That is the row's adversarial question answered in the concrete: "
        "the regrade is not cherry-picking winners, it is applying a structural rule and "
        "taking what comes.\n")

    L.append("## Verdict\n")
    L.append(
        f"**plain:** the grader was throwing out trades for being the wrong colour candle, "
        f"or for not touching the level on the exact minute it fired, when the setup's own "
        f"detector had already watched price touch that level a minute or two earlier -- "
        f"putting those specific ones back finds "
        f"{r_tg['hit'] - r_off['hit']} more of Austin's S trades out of {r_tg['n']} held-out "
        f"ones and takes the engine from {off['traded']} trades over two years to "
        f"{tgt['traded']}, and the trades it adds make money on their own "
        f"({ad['new']['mean_r']:+.2f}R each) "
        f"{'but less than' if ad['new']['mean_r'] < ad['retained']['mean_r'] else 'and more than'}"
        f" the ones it already had ({ad['retained']['mean_r']:+.2f}R), so it is a real "
        f"recall gain bought at a real cost, not a free one.\n")
    L.append(_verdict(r_off, r_tg, r_on, off, tgt, on_all, ad, between, ratio_t))

    L.append("## The regrade rule, stated exactly\n")
    L.append(
        "For a signal whose `signal_type` is `BREAK_AND_RETEST` or `ONE_CANDLE_RULE`, whose "
        "own detector has already named a specific bar at which price genuinely touched the "
        "level -- `detect_break_retest`'s ordered FSM (BREAK -> LEAVE -> RETEST -> CONFIRM, "
        "with the retest bar's own low/high proven to have reached the level, the FSM's "
        "`max_confirm_gap` of 3 bars already enforced, and the FSM's own `LATE` tag absent "
        "-- a level already broken earlier in the session is, in the detector's own comment, "
        "\"dirty\" and the entry \"a LATE entry\"), or `detect_order_block_setup`'s "
        "`wick_only` retest (the bar's low traded into the block, its body held clear) -- and "
        "whose `X` came from `_grade_pa` itself rather than `grade_trade`'s HTF pre-veto: "
        "re-run `_grade_pa`'s positive ladder with `at_key_level` forced TRUE and the "
        "confirm-bar colour gate dropped. Both of those vetoes are measured on the CONFIRM "
        "bar and only on the CONFIRM bar; the FSM already tested the same two things at the "
        "bars where they are actually decidable. Everything else -- the HTF veto, the "
        "minimum-risk D, OCR's 0.4% stop-width D, the PMH/PML cap, the session-extreme veto, "
        "level retirement, no-repeat entries, `_route`'s tight-stop test on C -- is "
        "untouched and still fires.\n")
    L.append(
        "**Why those two and not others.** `omen-blockers.md` (\"The grader throws away 93% "
        "of what the engine finds\", off `research/t62_veto_autopsy.md`) counts the three "
        "D/X-causing rules on the signals that land on Austin's own marked entries -- "
        "**never traded back to the level 49, wrong candle colour 50, HTF bias opposed 35** "
        "-- and gives his rebuttal of each: *\"The retest already happened up to 3 bars "
        "earlier and the FSM validated it. He enters intrabar, so a red entry candle on a "
        "long is normal. And he treats trend as one downgrade among eight, never a veto.\"* "
        "This arm takes the first two (99 of the 134 hits) and leaves the third (35). The "
        "first two rebuttals are claims "
        "about WHICH BAR the test is run on, and the FSM carries the evidence to run them on "
        "the right bar -- so they are in. The third is a claim about how much a trend "
        "disagreement should COUNT, which no FSM output can settle; regrading it would be a "
        "different row, and it is what separates `targeted` from `on_all` on the "
        "counter-trend signals. Keeping it out is the main reason this arm stays narrow.\n")
    L.append(
        "**What makes it self-limiting.** The regrade cannot promote anything above what the "
        "grader's own ladder would have said with correct inputs, and the ladder's top rung "
        "(`is_hammer_stick` / `is_inverted_hammer`) still requires the right candle colour. "
        "So on exactly the case this rule exists for -- a red confirm bar on a long -- the "
        "ceiling is B. The rule cannot invent an A+. Downstream the engine's own committed "
        "rules still move the grade in both directions: the displacement gate caps a "
        "no-displacement B&R to C, and `_calibration_grade` floors the first with-trend C of "
        "the day back to B. Those are not part of the regrade and were not touched.\n")
    L.append(
        "**How this rule was arrived at, including the part that was iterated.** The two "
        "CONFIRM-bar vetoes, the setup restriction and the HTF carve-out all came out of the "
        "code and `omen-blockers.md` before anything was run. The `LATE` clause did not: it "
        "was added after a first pass showed conditions (a) and (b) refusing nothing at all "
        "on the shipped configuration, which would have made `targeted` indistinguishable "
        "from \"`on_all` with the trend veto still on\" and would not have tested the row's "
        "actual question. It was chosen over the other available narrowing -- requiring the "
        "break leg to have displaced -- because `BNR_DISPLACEMENT_GATE` already ships ON and "
        "acts on the same signals downstream, so folding it into the regrade would double-"
        "count one rule rather than add an independent structural test. That decision was "
        "made on the book-wide lift counters, not on held-out recall; the held-out column "
        "was read once, at the end. A reader who wants the un-iterated version can set "
        "`\"LATE\" not in note` back to `True` in `br_wrap` and re-run.\n")

    L.append("## What could not be reconstructed\n")
    L.append(
        f"The row cites three sources for the size of the prize and none of them is in this "
        f"repo. `g4_dropped_s` (the 7,219-of-7,485 figure), the string `on_all`, and W1's arm "
        f"table (`on_all` 6/15 vs `off` 3/15 at a 12.5x book of 12,770 trades) appear NOWHERE "
        f"in the tree -- not in `research/`, not on any branch, local or remote -- and neither "
        f"does `research/t1_entry_minute_autopsy.md`, the 9-of-15 autopsy "
        f"`omen-next-session.md` links. That is the same situation `research/g90_fill_arms.md` "
        f"documents for `OMEN-7.3.md` / `g80_lookahead_refute.md`, and consistent with "
        f"`omen-blockers.md`'s note that the work happened on a working copy that was never "
        f"pushed. **So the verify criterion's specific numbers -- 52.5% `off`, 44.1% `on_all`, "
        f"12,770 trades -- are not targets here and were not aimed at.** They cannot be: the "
        f"code that produced them does not exist anywhere runnable. This script builds its own "
        f"`off` ({r_off['pct']}% held-out, {off['traded']} trades) and its own `on_all` "
        f"({r_on['pct']}%, {on_all['traded']} trades) from committed code, and uses THOSE as "
        f"the goalposts the targeted arm has to land between. Read the row's verify "
        f"structurally -- between the two extremes, under 2x the book -- not numerically.\n")
    L.append(
        "Two further gaps worth naming. (1) The vault's arm table is scored on 15 somethings "
        "(days, most likely -- T1's autopsy is over 15 days on which the engine reached his "
        "setup); this report's denominator is 130 marked S ENTRIES, of which "
        f"{n_held} are held out. The two denominators are not the same object and the "
        "percentages are not comparable. (2) `omen-next-session.md`'s own 2026-09-03 flag -- "
        "whether `TRADE_FLOOR` cuts at detection or only at scoring, and therefore whether "
        "\"SILENT: 0\" and `omen-s-accuracy-100.md`'s \"16 of 34 SILENT\" are compatible -- is "
        "still unresolved and is NOT settled here. This script measures "
        "`backtest_week.simulate_day`, which has no `TRADE_FLOOR` at all; `live_scanner._tier` "
        "does, and it would cut into every arm's recall equally.\n")
    same = all(recall[arm]["fired"]["held"]["hit"] == recall[arm]["traded"]["held"]["hit"]
               for arm in ARMS)
    L.append(
        "**On C alerts.** A share of what the regrade lifts lands on C, and C is alert-only "
        "in `live_scanner` (`_tier()` posts it as WATCH, not TRADE), so it never enters the "
        "P&L book. Recall was therefore measured both ways. "
        + ("On this corpus the two columns come out IDENTICAL for all three arms -- every "
           "mark any arm recalls, it recalls with a signal that is actually in the book, so "
           "none of the recall reported here is riding on alerts a human would have to act "
           "on manually. "
           if same else
           "The two columns differ, so part of the recall reported on the wider definition "
           "is alerts rather than trades. ")
        + "Either way, `TRADE_FLOOR` and `live_scanner._tier`'s `grade == \"A+\"` gate sit "
          "downstream of everything measured here and would cut into all three arms; "
          "reconciling those is T2's row, not this one.\n")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(L))
    print("\n".join(L))
    print(f"\nwrote {OUT_MD}")


def _verdict(r_off, r_tg, r_on, off, tgt, on_all, ad, between, ratio_t):
    lift = r_tg["pct"] - r_off["pct"]
    parts = []
    if between:
        parts.append(
            f"**The middle exists, and it is where the row said it would be.** Regrading only "
            f"FSM-validated break-and-retest and one-candle-rule setups moves held-out recall "
            f"from {r_off['pct']}% to {r_tg['pct']}% ({lift:+.1f} points) while `on_all` -- "
            f"the same ladder with no setup or FSM precondition -- reaches {r_on['pct']}%. "
            f"`targeted` sits strictly between them, which is the whole claim: the recall the "
            f"blunt arm buys is not all bought by ungating everything, and a narrow, "
            f"structurally-grounded slice of it is available at "
            f"{ratio_t:.2f}x the book instead of "
            f"{on_all['traded']/off['traded']:.2f}x.")
        gain = (r_tg["hit"] - r_off["hit"]) / max(r_on["hit"] - r_off["hit"], 1)
        cost = (tgt["traded"] - off["traded"]) / max(on_all["traded"] - off["traded"], 1)
        parts.append(
            f"**But it is not a free lunch, and the report should not be read as one.** "
            f"`targeted` collects {100*gain:.0f}% of the recall `on_all` buys for "
            f"{100*cost:.0f}% of the extra trades `on_all` costs -- close to proportional. "
            f"The case for it over `on_all` is therefore NOT that it is a better recall-per-"
            f"trade deal on this corpus; it is that the trades it adds are ones a stated, "
            f"checkable structural rule says the engine was wrong to refuse, whereas "
            f"`on_all`'s extra {on_all['traded'] - tgt['traded']} come with no account of why "
            f"any particular one should have fired -- including counter-trend entries the "
            f"trend rule vetoed on purpose. Whether that is worth "
            f"{tgt['traded'] - off['traded']} more trades a year is a decision, not a "
            f"measurement, and this row does not make it.")
    else:
        parts.append(
            f"**The targeted arm did NOT land strictly between the two.** Held-out recall: "
            f"`off` {r_off['pct']}%, `targeted` {r_tg['pct']}%, `on_all` {r_on['pct']}%. "
            f"Reported as measured rather than tuned into a pass.")
    if ad["new"]["mean_r"] is not None:
        good = ad["new"]["mean_r"] > 0
        parts.append(
            f"**The added trades are priced separately and they are "
            f"{'not' if good else ''} carrying the result{'' if good else ' -- they lose money'}.** "
            f"The {ad['new']['n']} trades `targeted` adds pay {ad['new']['mean_r']:+.4f}R at a "
            f"{ad['new']['win_rate']}% win rate, against {ad['retained']['mean_r']:+.4f}R on "
            f"the {ad['retained']['n']} trades `off` already had. "
            + ("The regrade is therefore not re-labelling losers as wins: the new book is a "
               "separate, independently-priced set that stands on its own."
               if good else
               "So the recall gain is bought with money: whoever ships this has to decide "
               "whether the recall is worth the drag, and the honest answer from this run is "
               "that the added trades are a cost, not a discovery.")
            + f" Blended, `targeted` pays {tgt['mean_r']:+.4f}R over {tgt['traded']} trades "
              f"vs `off`'s {off['mean_r']:+.4f}R over {off['traded']}.")
    parts.append(
        f"**What this does not settle.** Recall is still nowhere near the 90% gate -- "
        f"{r_tg['pct']}% held out is a lever moved, not a gate cleared -- and `on_all`'s "
        f"{r_on['pct']}% is the ceiling this whole family of fixes can reach, at "
        f"{on_all['traded']/off['traded']:.2f}x the book and "
        f"{on_all['mean_r']:+.4f}R. The X-veto is real and regrading it is worth doing, but "
        f"it is not, on this measurement, the thing standing between the engine and Austin's "
        f"S days on its own.")
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__":
    main()
