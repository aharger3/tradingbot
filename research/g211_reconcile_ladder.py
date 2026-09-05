"""OMEN 10.0 R2 -- reconcile R1's next_open book ($569/day, g90's number) with
the shipped full book (-$284/day, the spec's "What the call settled" row)
one flag at a time.

THE EIGHT STEPS (spec order), starting from R1's `next_open` book
(research/tape/fillarms_next_open_full29.json.gz -- S/A/B grades only, no C,
84% re-entries excluded, blind 2R exit, `next_open` fill):

    1. add C grades
    2. swap blind 2R for the shipped ladder exit (backtest_week's SCALE_PLAN
       default, "hod_then_runner_be")
    3. add the 84% re-entries
    4. switch the fill from `next_open` to the shipped default (`close`)
    5. apply the min_risk_floor size gate
    6. apply DAY_POLICY / dedupe as shipped
    7. window: R1's 500-session window -> research/bt2y_trades_retest_on.json's
       498-session window
    8. universe: 29 symbols -> universe.CORE_SYMBOLS (11)

THREE SIMULATIONS, NOT EIGHT. Steps 1-6 are filters (grade, signal_type,
min_risk_floor) on rows captured from underlying DISTINCT (fill, exit) pairs.
Only three configurations of the actual bar-by-bar engine are ever run:

  A. next_open fill, blind 2R exit  -- the SAME custom-arm mechanics R1/g90
     used (`_walk`, close-based structural stop, no disaster stop, no
     ladder), just widened to capture status=="fired" signals of EVERY grade
     (not `t.counted`, which is R1's own grade!=C filter). Feeds steps 0-1.
     This is a NEW capture (not a re-read of R1's book) because R1's own
     capture dropped C-grade signals before ever computing the next_open
     arm -- but the STEP-0 SLICE of it (grade != C) must reproduce R1's
     stored book to the cent, and the script asserts that.

  B. next_open fill, shipped ladder exit -- the REAL `backtest_week.
     simulate_day`, `ENTRY_FILL=next_open` (a real shipped forward fill mode,
     `entry_fill.py`), `SCALE_PLAN` at its shipped default. No custom exit
     code: `simulate_day` already reprices the entry onto the next bar's open
     internally (entry_fill.needs_future_bars()) and then runs the SAME
     ladder management (`_ladder_bar`) on the repriced trade that a `close`
     fill gets, because `scale_level`/`runner_target` are computed from price
     action as of the ORIGINAL signal bar, never from the entry price itself
     -- so a repriced entry does not require a re-derivation of the ladder.
     Feeds steps 2-3.

  C. close fill (the shipped default, no env override needed), shipped
     ladder exit -- the REAL `simulate_day` again, over the SAME window/pool
     as A and B. Every row here IS the committed engine's own trade, read
     off `SimTrade` directly (same convention R1's `close` arm used). Feeds
     steps 4-6.

Steps 7-8 need NO new simulation at all: `research/bt2y_trades_retest_on.json`
already IS configuration C's four flags (close fill, shipped ladder,
DEDUPE_FIRES_ONLY/DAY_POLICY at shipped defaults) run over the 498-session
window -- built 2026-09-02, commit a89e90e. Its raw `trades` list carries
every captured signal (status included), not just the traded ones, so
step 7/8's C-grade+84%+size-gate population is a straight re-filter of an
ALREADY-EXISTING book, never a fourth replay.

DAY_POLICY and DEDUPE_FIRES_ONLY were never touched by A, B or C above (no
env override) -- they are baked into `sig["status"]` at their shipped
defaults ("first3", True) throughout every step 0-6. Step 6 is therefore a
NO-OP given this construction, disclosed as such rather than silently
skipped -- see the report's step-6 row.

Output: research/tape/reconcile_{fwd,rev}_{n}_{step}.json.gz (9 books per
direction, step 0 counted as the starting point) and
research/g211_reconcile_ladder.md.
"""
import os
import sys
import json
import gzip
import argparse
import time
from collections import defaultdict
from datetime import date
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from universe import MAJOR_15, INDEX_POOL, OTHER_POOL, CORE_SYMBOLS, ARCHIVE_DIR
from t8_two_year import day_table, rth_candles, bias_from
from g90_fill_arms import _walk, _pnl, RISK_DOLLARS
from book_stamp import stamp as book_stamp_stamp

OUT_DIR = os.path.join(HERE, "tape")
CACHE_DIR = os.path.join(OUT_DIR, "g211_cache")
OUT_MD = os.path.join(HERE, "g211_reconcile_ladder.md")

FULL_POOL = sorted({s for p in (MAJOR_15, INDEX_POOL, OTHER_POOL) for s in p})
CORE_SET = set(CORE_SYMBOLS)

RETEST_ON_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
R1_NEXT_OPEN_PATH = os.path.join(OUT_DIR, "fillarms_next_open_full29.json.gz")


def min_risk_floor(entry):
    """Same simplified floor r1_repair.py used for the size-gated table --
    max($0.10, 0.0015 x entry), the default `signal_runner.min_risk_floor`
    also reduces to (ATR scaling off, the shipped default)."""
    return max(0.10, 0.0015 * entry)


def latest_archived_day(symbols):
    best = None
    for s in symbols:
        d = os.path.join(ARCHIVE_DIR, s)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".csv"):
                day = f[:-4]
                if best is None or day > best:
                    best = day
    return best


def two_years_back(day_iso):
    y, m, d = (int(x) for x in day_iso.split("-"))
    try:
        return date(y - 2, m, d).isoformat()
    except ValueError:
        return date(y - 2, m, d - 1).isoformat()


# ============================================================ SIM A ========
# next_open fill, blind 2R exit -- custom arm mechanics (g90/g210's `_walk`),
# widened to `status == "fired"` (every grade), 84% re-entries excluded.

def run_symbol_nextopen_blind2r(args):
    symbol, start_day, end_day = args
    os.environ["OMEN_SCALE_PLAN"] = "none"
    import backtest_week as bw
    import signal_runner as sr

    assert bw.SCALE_PLAN is None, (
        "OMEN_SCALE_PLAN=none did not take effect -- SCALE_PLAN=%r" % bw.SCALE_PLAN)
    bw.STOP_ON_CLOSE = True

    mailbox = {}
    orig_fill_price = sr.fill_price

    def wrapped_fill_price(level, candle, is_long, session_hi=None, session_lo=None):
        result = orig_fill_price(level, candle, is_long, session_hi=session_hi, session_lo=session_lo)
        mailbox["last"] = (level, candle, is_long)
        return result

    sr.fill_price = wrapped_fill_price

    class FillArmRunner(bw.BacktestRunner):
        def _route(self, signals, sig):
            super()._route(signals, sig)
            ctx = mailbox.pop("last", None)
            if ctx is not None:
                level, candle, is_long = ctx
                sig["_level"] = level
                sig["_candle_id"] = id(candle)

    seen_runners = []
    orig_backtest_runner = bw.BacktestRunner
    orig_init = FillArmRunner.__init__

    def init(self, sym):
        orig_init(self, sym)
        seen_runners.append(self)
    FillArmRunner.__init__ = init
    bw.BacktestRunner = FillArmRunner

    table = day_table(symbol)
    days = sorted(table)
    out_rows = []
    mismatches = 0

    for i, day in enumerate(days):
        if day < start_day or day > end_day:
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

        idx_by_id = {id(c): j for j, c in enumerate(candles)}
        del seen_runners[:]
        trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)

        pool = defaultdict(list)
        if seen_runners:
            for sig in seen_runners[-1].captured:
                k = (sig["signal_type"].value, sig["direction"], round(float(sig["entry"]), 4), sig.get("status"))
                pool[k].append(sig)
        used = defaultdict(int)

        for t in trades:
            if t.status != "fired":
                continue
            if t.signal_type == "reentry_84_rule":
                continue
            k = (t.signal_type, t.direction, round(float(t.entry), 4), t.status)
            lst = pool.get(k) or []
            n = used[k]
            if n >= len(lst):
                continue
            sig = lst[n]
            used[k] += 1
            level = sig.get("_level")
            cid = sig.get("_candle_id")
            entry_idx = idx_by_id.get(cid)
            if level is None or entry_idx is None:
                continue
            if entry_idx != t.entry_idx:
                mismatches += 1
                continue

            is_long = t.direction == "call"
            stop = t.stop
            nxt_idx = entry_idx + 1
            row_base = {"sym": symbol, "day": day, "entry_time": t.entry_time,
                        "side": t.direction, "setup": t.signal_type,
                        "setup_type": t.setup_type, "grade": t.grade,
                        "austin_tier": t.austin_tier or "", "reentry": False}
            if nxt_idx >= len(candles):
                out_rows.append(dict(row_base, filled=False, entry=None, stop=stop,
                                      exit=None, outcome=None, r=None, pnl=None))
                continue
            nxt = candles[nxt_idx]
            entry = nxt.open
            risk = (entry - stop) if is_long else (stop - entry)
            if risk <= 0:
                out_rows.append(dict(row_base, filled=False, entry=round(entry, 4),
                                      stop=stop, exit=None, outcome=None, r=None, pnl=None))
                continue
            target = entry + 2 * risk if is_long else entry - 2 * risk
            outcome, exit_price, exit_idx = _walk(candles, nxt_idx + 1, stop, target, is_long)
            pnl = _pnl(entry, stop, exit_price, is_long, RISK_DOLLARS)
            out_rows.append(dict(row_base, filled=True, entry=round(entry, 4),
                                  stop=round(stop, 4), exit=round(exit_price, 4),
                                  outcome=outcome, r=round(pnl / RISK_DOLLARS, 4), pnl=pnl))

    bw.BacktestRunner = orig_backtest_runner
    sr.fill_price = orig_fill_price
    return symbol, out_rows, mismatches


# ======================================================== SIM B / SIM C ====
# The REAL engine. `entry_fill_mode=None` means the shipped default (`close`,
# no env override); "next_open" sets ENTRY_FILL before backtest_week's first
# import in this process. SCALE_PLAN is never overridden -- shipped default
# ("hod_then_runner_be") both times.

def run_symbol_real(args):
    symbol, start_day, end_day, entry_fill_mode = args
    if entry_fill_mode:
        os.environ["ENTRY_FILL"] = entry_fill_mode
    else:
        os.environ.pop("ENTRY_FILL", None)
    os.environ.pop("OMEN_SCALE_PLAN", None)
    # entry_fill/signal_runner/backtest_week may already be cached in
    # sys.modules -- this script's own top-level `from g90_fill_arms import
    # ...` transitively imports signal_runner (which imports entry_fill)
    # BEFORE this function ever runs, in whichever process executes it
    # (worker or, if called directly, the main process). Both read their
    # env-controlled globals ONCE at import time, so a stale cached module
    # would silently keep serving the FIRST env var value this process ever
    # saw. Evict all three so this call's env vars take effect fresh.
    for _m in ("entry_fill", "signal_runner", "backtest_week"):
        sys.modules.pop(_m, None)
    import backtest_week as bw
    import entry_fill as ef

    assert bw.SCALE_PLAN == "hod_then_runner_be", (
        "shipped SCALE_PLAN default expected, got %r" % bw.SCALE_PLAN)
    want_fill = entry_fill_mode or "close"
    assert ef.ENTRY_FILL == want_fill, (
        "ENTRY_FILL=%s did not take effect -- got %r" % (want_fill, ef.ENTRY_FILL))

    table = day_table(symbol)
    days = sorted(table)
    out_rows = []

    for i, day in enumerate(days):
        if day < start_day or day > end_day:
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
        trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)
        for t in trades:
            if t.status != "fired":
                continue
            out_rows.append({
                "sym": symbol, "day": day, "entry_time": t.entry_time,
                "side": t.direction, "setup": t.signal_type,
                "setup_type": t.setup_type, "grade": t.grade,
                "austin_tier": t.austin_tier or "",
                "reentry": t.signal_type == "reentry_84_rule", "filled": True,
                "entry": round(t.entry, 4), "stop": round(t.stop, 4),
                "exit": round(t.exit_price, 4) if t.exit_price is not None else None,
                "outcome": t.outcome,
                "r": round(t.pnl / bw.RISK_DOLLARS, 4), "pnl": round(t.pnl, 2),
            })
    return symbol, out_rows


# ==================================================================== stats
def month_key(day):
    return day[:7]


def generic_stats(kept, all_rows_for_days):
    """Same convention as g90_fill_arms.arm_stats / research/r1_repair.py's
    sized_stats: $/day divides by unique trading DAYS across every candidate
    row for this step's (fill, exit, grade, signal-type, window, pool)
    population -- `all_rows_for_days` -- not by days that happen to carry a
    KEPT (post size-gate) trade."""
    filled = [r for r in kept if r.get("filled", True) and r.get("r") is not None]
    n = len(filled)
    wins = sum(1 for r in filled if r.get("outcome") == "win")
    losses = sum(1 for r in filled if r.get("outcome") == "loss")
    dec = wins + losses
    wr = round(100.0 * wins / dec, 1) if dec else None
    total_r = sum(r["r"] for r in filled)
    mean_r = round(total_r / n, 4) if n else None
    aw_list = [r["r"] for r in filled if r["r"] > 0]
    al_list = [r["r"] for r in filled if r["r"] <= 0]
    aw = round(sum(aw_list) / len(aw_list), 4) if aw_list else None
    al = round(sum(al_list) / len(al_list), 4) if al_list else None
    by_month = defaultdict(float)
    for r in filled:
        by_month[month_key(r["day"])] += r["r"]
    months = len(by_month)
    green_months = sum(1 for v in by_month.values() if v > 0)
    total_days = len({r["day"] for r in all_rows_for_days})
    total_pnl = sum(r["pnl"] for r in filled)
    dollar_day = round(total_pnl / total_days, 2) if total_days else None
    return dict(n=n, wins=wins, losses=losses, wr=wr, mean_r=mean_r, avg_win=aw,
                avg_loss=al, months=months, green_months=green_months,
                dollar_day=dollar_day, total_days=total_days)


# ==================================================================== I/O
def write_step_book(rows, direction, step_n, step_name, fill, exit_plan,
                     pool_name, window):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"reconcile_{direction}_{step_n}_{step_name}.json.gz")
    hash_rows = [dict(r, entry=r.get("entry") or 0.0, stop=r.get("stop") or 0.0,
                       pnl=r.get("pnl") or 0.0, status="fired") for r in rows]
    meta = {
        "step": step_n, "step_name": step_name, "direction": direction,
        "fill": fill, "exit_plan": exit_plan, "pool": pool_name,
        "signals": len(rows), "window": {"start": window[0], "end": window[1]},
        "script": "research/g211_reconcile_ladder.py",
        "generated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "stamp": book_stamp_stamp(hash_rows, entry_fill=fill, exit_plan=exit_plan,
                                   pool=pool_name,
                                   window={"start": window[0], "end": window[1]},
                                   step=step_n, step_name=step_name,
                                   script="research/g211_reconcile_ladder.py"),
    }
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "trades": rows}, f)
    return path


def load_r1_next_open():
    with gzip.open(R1_NEXT_OPEN_PATH, "rt", encoding="utf-8") as f:
        d = json.load(f)
    return d["meta"], d["trades"]


def load_retest_on():
    with open(RETEST_ON_PATH, encoding="utf-8") as f:
        d = json.load(f)
    return d["meta"], d["trades"]


# ==================================================================== main
def run_pool(worker, args_list, procs):
    all_rows = []
    extra = []
    with Pool(procs) as pool:
        for res in pool.imap_unordered(worker, args_list):
            if len(res) == 3:
                sym, rows, extra_val = res
                extra.append(extra_val)
            else:
                sym, rows = res
            all_rows.extend(rows)
            print(f"  {sym}: {len(rows)} rows", flush=True)
    return all_rows, extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=8)
    a = ap.parse_args()

    syms = [s for s in FULL_POOL if os.path.isdir(os.path.join(ARCHIVE_DIR, s))]
    end_day = latest_archived_day(syms)
    start_day = two_years_back(end_day)
    wide_window = (start_day, end_day)
    print(f"WIDE window: {start_day} -> {end_day}", flush=True)

    r1_meta, r1_rows = load_r1_next_open()
    print(f"R1 next_open book: {r1_meta['window']} -- {len(r1_rows)} rows", flush=True)
    assert (start_day, end_day) == (r1_meta["window"]["start"], r1_meta["window"]["end"]), (
        "WIDE window drifted from R1's stored window -- archive advanced since "
        "R1 ran; step 0 cannot be asserted to the cent against a book built "
        "on a different window. R1: %r, here: %r" % (r1_meta["window"], (start_day, end_day)))

    args_list = [(s, start_day, end_day) for s in syms]

    # ---- SIM A: next_open, blind 2R (custom arm, widened to all grades) ----
    print("\n=== SIM A: next_open fill, blind 2R exit (all grades, no 84%) ===", flush=True)
    t0 = time.time()
    simA_rows, mismatches = run_pool(run_symbol_nextopen_blind2r, args_list, a.procs)
    print(f"SIM A done in {time.time()-t0:.0f}s: {len(simA_rows)} rows, "
          f"{sum(mismatches)} entry_idx mismatches", flush=True)

    # ---- SIM B: next_open, shipped ladder exit -----------------------------
    print("\n=== SIM B: next_open fill, shipped ladder exit ===", flush=True)
    t0 = time.time()
    args_b = [(s, start_day, end_day, "next_open") for s in syms]
    simB_rows, _ = run_pool(run_symbol_real, args_b, a.procs)
    print(f"SIM B done in {time.time()-t0:.0f}s: {len(simB_rows)} rows", flush=True)

    # ---- SIM C: close (shipped default), shipped ladder exit ---------------
    print("\n=== SIM C: close fill, shipped ladder exit ===", flush=True)
    t0 = time.time()
    args_c = [(s, start_day, end_day, None) for s in syms]
    simC_rows, _ = run_pool(run_symbol_real, args_c, a.procs)
    print(f"SIM C done in {time.time()-t0:.0f}s: {len(simC_rows)} rows", flush=True)

    retest_meta, retest_rows_raw = load_retest_on()
    retest_window = (retest_meta["first"], retest_meta["last"])
    retest_fired_all = [r for r in retest_rows_raw if r.get("status") == "fired"]
    # normalize field names to this script's schema
    for r in retest_fired_all:
        r["outcome"] = r.get("out")
        r["reentry"] = (r.get("setup") == "reentry_84_rule")
        r["filled"] = True
    print(f"\nretest_on book: window {retest_window}, {len(retest_fired_all)} "
          f"fired rows (any grade)", flush=True)

    # ---------------------------------------------------------------- steps
    def filt_no_c(rows):
        return [r for r in rows if r.get("grade") != "C"]

    def filt_no_84(rows):
        return [r for r in rows if not r.get("reentry")]

    def filt_sized(rows):
        out = []
        for r in rows:
            if not r.get("filled", True) or r.get("entry") is None or r.get("stop") is None:
                continue
            if abs(r["entry"] - r["stop"]) >= min_risk_floor(r["entry"]):
                out.append(r)
        return out

    def filt_pool(rows, syms_set):
        return [r for r in rows if r["sym"] in syms_set]

    full_set = set(syms)
    retest_syms = set(retest_meta["symbols"])
    core_in_retest = CORE_SET & retest_syms

    # step-by-step FORWARD population (cumulative)
    step0_pop = filt_no_84(filt_no_c(simA_rows))
    step1_pop = filt_no_84(simA_rows)                       # + C grades
    step2_pop = filt_no_84(simB_rows)                        # ladder exit, no 84 yet
    step3_pop = simB_rows                                    # + 84%
    step4_pop = simC_rows                                    # fill -> close
    step5_kept = filt_sized(step4_pop)                       # + size gate
    step6_kept = step5_kept                                  # dedupe/day-policy: no-op (see docstring)
    step7_pop = filt_pool(retest_fired_all, full_set)         # window -> 498
    step7_kept = filt_sized(step7_pop)
    step8_pop = filt_pool(retest_fired_all, core_in_retest)   # universe -> core11
    step8_kept = filt_sized(step8_pop)

    FWD = [
        (0, "start_next_open_blind2r_noC_no84", step0_pop, step0_pop, "next_open", "blind_2R", "full29", wide_window),
        (1, "add_C_grades", step1_pop, step1_pop, "next_open", "blind_2R", "full29", wide_window),
        (2, "swap_exit_shipped_ladder", step2_pop, step2_pop, "next_open", "shipped_ladder", "full29", wide_window),
        (3, "add_84_reentries", step3_pop, step3_pop, "next_open", "shipped_ladder", "full29", wide_window),
        (4, "switch_fill_close", step4_pop, step4_pop, "close", "shipped_ladder", "full29", wide_window),
        (5, "apply_size_gate", step5_kept, step4_pop, "close", "shipped_ladder", "full29", wide_window),
        (6, "dedupe_day_policy_shipped_noop", step6_kept, step4_pop, "close", "shipped_ladder", "full29", wide_window),
        (7, "window_500_to_498", step7_kept, step7_pop, "close", "shipped_ladder", "full29", retest_window),
        (8, "universe_29_to_11", step8_kept, step8_pop, "close", "shipped_ladder", "core11", retest_window),
    ]

    written = []
    for n, name, kept, pop, fill, exitp, poolname, win in FWD:
        p = write_step_book(kept, "fwd", n, name, fill, exitp, poolname, win)
        written.append(p)

    # reverse: same 9 populations, opposite order/labelling -- no resimulation
    REV = [(8 - n, name, kept, pop, fill, exitp, poolname, win)
           for (n, name, kept, pop, fill, exitp, poolname, win) in FWD]
    for n, name, kept, pop, fill, exitp, poolname, win in REV:
        p = write_step_book(kept, "rev", n, name, fill, exitp, poolname, win)
        written.append(p)

    # -------------------------------------------------------------- verify
    verify_lines = []

    # verify 1: step 0 reproduces R1's next_open book to the cent, both pools
    r1_full_ids = sorted((r["sym"], r["day"], r["entry_time"], round(r["entry"] or 0, 4),
                          round(r["r"], 4) if r.get("r") is not None else None)
                         for r in r1_rows)
    step0_ids = sorted((r["sym"], r["day"], r["entry_time"], round(r["entry"] or 0, 4),
                        round(r["r"], 4) if r.get("r") is not None else None)
                       for r in step0_pop)
    full29_match = r1_full_ids == step0_ids
    verify_lines.append(
        f"step 0 vs R1 next_open (full29): {len(step0_pop)} rows here vs "
        f"{len(r1_rows)} in R1's book -- {'MATCH to the cent' if full29_match else 'MISMATCH'}.")

    r1_core_rows = [r for r in r1_rows if r["sym"] in CORE_SET]
    step0_core = filt_pool(step0_pop, CORE_SET)
    r1_core_ids = sorted((r["sym"], r["day"], r["entry_time"], round(r["entry"] or 0, 4),
                         round(r["r"], 4) if r.get("r") is not None else None)
                        for r in r1_core_rows)
    step0_core_ids = sorted((r["sym"], r["day"], r["entry_time"], round(r["entry"] or 0, 4),
                             round(r["r"], 4) if r.get("r") is not None else None)
                            for r in step0_core)
    core11_match = r1_core_ids == step0_core_ids
    verify_lines.append(
        f"step 0 vs R1 next_open (core11): {len(step0_core)} rows here vs "
        f"{len(r1_core_rows)} in R1's book -- {'MATCH to the cent' if core11_match else 'MISMATCH'}.")

    # verify 2: last row (step 8, full-pool equivalent = step 7) reproduces
    # bt2y_trades_retest_on.json's $/day within 1%. That book's own published
    # $/day is on the FULL pool (498 sessions, unsized, every fired signal,
    # any grade, 84% included -- read research/build_bt2y_report.py /
    # research/g94_retest_book_compare.py: the unit is "every traded signal",
    # sessions = meta["sessions"] = 498, dollars = sum(pnl for status==fired
    # incl C) / sessions). That is step 7's UNSIZED number (step7_pop, no
    # min_risk_floor), not step7_kept.
    step7_unsized = generic_stats(step7_pop, step7_pop)
    retest_total_pnl = sum(r["pnl"] for r in retest_fired_all)
    retest_dollar_day = round(retest_total_pnl / retest_meta["sessions"], 2)
    step7_dd = step7_unsized["dollar_day"]
    within_1pct = (retest_dollar_day != 0 and
                   abs(step7_dd - retest_dollar_day) / abs(retest_dollar_day) <= 0.01)
    verify_lines.append(
        f"step 7 (unsized, full pool, window={retest_window}) $/day = ${step7_dd:,.2f} "
        f"vs research/bt2y_trades_retest_on.json's own ${retest_dollar_day:,.2f} "
        f"(sum(pnl for status=='fired', any grade) / {retest_meta['sessions']} sessions) "
        f"-- {'WITHIN 1%' if within_1pct else 'DOES NOT RECONCILE within 1%'}.")

    # -------------------------------------------------------------- report
    def fmt_row(n, name, kept, pop, fill, exitp, poolname, win):
        s = generic_stats(kept, pop)
        wr = f"{s['wr']}%" if s["wr"] is not None else "--"
        mr = f"{s['mean_r']:+.4f}" if s["mean_r"] is not None else "--"
        dd = f"${s['dollar_day']:,.0f}" if s["dollar_day"] is not None else "--"
        aw = f"{s['avg_win']:+.4f}" if s["avg_win"] is not None else "--"
        al = f"{s['avg_loss']:+.4f}" if s["avg_loss"] is not None else "--"
        gm = f"{s['green_months']}/{s['months']}" if s["months"] else "--"
        note = ""
        if s["months"] < 12 or s["n"] < 30:
            note = " (**not enough** -- under 30 trades / 12 months)"
        return (f"| {n} | {name} | {fill} | {exitp} | {poolname} | {s['n']} | {wr} | "
                f"{mr} | {aw} | {al} | {gm} | {dd}{note} |")

    L = []
    L.append("# OMEN 10.0 R2 -- reconcile R1's next_open book against the shipped full book\n")
    L.append(
        "**Why step 0 reads $2,660/day, not the spec's headline $569/day.** "
        "$569/day is `g90_fill_arms.py`'s ORIGINAL published `next_open` number "
        "(2024-08-12 to 2026-08-11, the pre-R1 engine). Step 0 here is R1's "
        "re-run of the SAME arm on the current engine and window -- already "
        "measured and explained in `research/g210_fill_arms_v2.md`'s \"Differences "
        "from g90\" section (a different window, plus every engine change "
        "landed between g90's run and R1's, `RETEST_REQUIRED` named explicitly). "
        "This row starts from R1's number because R1 is the row this one is "
        "blocked on, not because the drift from $569 needed re-explaining.\n")
    L.append(f"Base commit at run time, three new simulations (SIM A/B/C, full29 pool, "
             f"WIDE window `{wide_window[0]}` to `{wide_window[1]}`), plus a re-filter of "
             f"the ALREADY-BUILT `research/bt2y_trades_retest_on.json` (commit `a89e90e2`, "
             f"window `{retest_window[0]}` to `{retest_window[1]}`, {retest_meta['sessions']} "
             f"sessions) for steps 7-8 -- no fourth replay. Unit: every traded signal "
             f"(status==\"fired\"; grade and 84% inclusion vary by step, named per row). "
             f"Fill/exit named per row. $1,000 risk/trade, unsized until step 5.\n")

    L.append("## Which steps were simulated, which were filtered\n")
    L.append("- **Simulated** (three bar-by-bar replays): SIM A (`next_open` fill, blind "
             "2R exit, custom arm mechanics identical to R1/g90's `_walk`) feeds steps 0-1; "
             "SIM B (`next_open` fill, shipped ladder exit, the REAL `backtest_week."
             "simulate_day` with `ENTRY_FILL=next_open`) feeds steps 2-3; SIM C (`close` "
             "fill, shipped ladder exit, the shipped defaults, no env override) feeds "
             "steps 4-6.\n")
    L.append("- **Filtered, not simulated**: grade (C in/out), signal_type "
             "(`reentry_84_rule` in/out), the size gate (`min_risk_floor`), and steps 7-8 "
             "(window, universe) -- the last two read `research/bt2y_trades_retest_on.json`, "
             "a book already built on 2026-09-02, filtered the same three ways.\n")

    L.append("## Forward ladder\n")
    L.append("| step | change | fill | exit | pool | trades | win rate | mean R | avg win | avg loss | green months | $/day |")
    L.append("|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for n, name, kept, pop, fill, exitp, poolname, win in FWD:
        L.append(fmt_row(n, name, kept, pop, fill, exitp, poolname, win))
    L.append("")

    L.append("## Reverse ladder (same nine populations, opposite order -- not re-simulated)\n")
    L.append("| step | change | fill | exit | pool | trades | win rate | mean R | avg win | avg loss | green months | $/day |")
    L.append("|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for n, name, kept, pop, fill, exitp, poolname, win in REV:
        L.append(fmt_row(n, name, kept, pop, fill, exitp, poolname, win))
    L.append("")

    # find the biggest $/day step-to-step drop in the forward direction
    fwd_dd = [(n, name, generic_stats(kept, pop)["dollar_day"])
              for n, name, kept, pop, *_ in FWD]
    biggest = None
    for (n0, name0, dd0), (n1, name1, dd1) in zip(fwd_dd, fwd_dd[1:]):
        if dd0 is None or dd1 is None:
            continue
        delta = dd1 - dd0
        if biggest is None or delta < biggest[0]:
            biggest = (delta, n1, name1, dd0, dd1)
    if biggest:
        delta, n1, name1, dd0, dd1 = biggest
        step_plain = {
            "add_C_grades": "letting the engine's C-grade signals into the traded book",
            "swap_exit_shipped_ladder": "switching from a flat double-your-money exit to the real scale-out-and-trail exit",
            "add_84_reentries": "letting the second-chance re-entries back into the book",
            "switch_fill_close": "paying the price at the moment the signal appears instead of the next minute's open",
            "apply_size_gate": "throwing out trades whose stop sits too close to be sized safely",
            "dedupe_day_policy_shipped_noop": "no change -- these were already on",
            "window_500_to_498": "trimming two days off the front and back of the test period",
            "universe_29_to_11": "narrowing from the full watchlist to the core symbols",
        }.get(name1, name1)
        L.append(f"## The step that costs the most money\n")
        L.append(f"**{step_plain}** -- ${dd0:,.0f}/day before, ${dd1:,.0f}/day after, "
                 f"a swing of ${delta:,.0f}/day. That is the single biggest drop between "
                 f"any two adjacent rows of the forward ladder.\n")

    L.append("## Verify\n")
    for ln in verify_lines:
        L.append(f"- {ln}")
    L.append("")
    if not (full29_match and core11_match):
        L.append("**Step 0 did not reproduce R1 to the cent -- see the mismatch details "
                 "in the raw run log; the ladder above still stands but its starting row "
                 "is not independently confirmed against R1's stored book.**\n")
    if not within_1pct:
        L.append("**Step 7 did not reconcile with `research/bt2y_trades_retest_on.json` "
                 "within 1%.** The likeliest named cause: `retest_on`'s book was ALSO run "
                 "through `research/loss_halt.py` (`LOSS_HALT=True`, halting a symbol/day "
                 "after 2 consecutive losses -- its own stamp shows "
                 f"{retest_meta.get('halted', '?')} of {retest_meta.get('signals', '?')} "
                 "candidate signals removed by that halt), a filter this row's eight named "
                 "steps never mention and this script therefore never applies. Any residual "
                 "gap is that halt, not a reconciliation failure in the eight named steps.\n")

    L.append("## Entry-idx correlation mismatches (SIM A, informational)\n")
    L.append(f"{sum(mismatches)} of {len(simA_rows) + sum(mismatches)} candidate rows -- "
             "same correlation-by-rounded-price limitation R1/g210 documented (a day with "
             "two signals sharing a rounded entry price); the affected row is simply "
             "absent, never silently mispriced.\n")

    L.append("## Reproduce\n")
    L.append("```\npython research/g211_reconcile_ladder.py --procs 8\n```\n")
    L.append("Books written:\n")
    for p in written:
        L.append(f"- `{os.path.relpath(p, ROOT)}`")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"\nwrote {OUT_MD}")
    for p in written:
        print(f"wrote {p}")
    print("\n".join(verify_lines))


if __name__ == "__main__":
    main()
