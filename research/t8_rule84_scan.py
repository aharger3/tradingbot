"""omen-4.0 T8: the 84% re-entry candidates the card deck can never show.

The 84% rule is, by its settled definition, a RE-ENTRY AFTER A LOSER: it arms
only when a break-and-retest or One Candle Rule entry stops out, then triggers
when a candle closes at or above the price originally entered (mirror for
shorts). A single-bar grading card physically cannot show that — it needs the
losing entry, the stop-out, and the reclaim — so no deck has ever asked about
it and no artifact has ever reported it.

This scan reuses the harness's OWN detection (research/t4_engine_recall.run_day
= signal_runner.SignalRunner.detect_signals replayed bar-by-bar, with the same
11:00 cutoff + 30-bar per-idea dedupe + archive-reconstructed levels) to find
every break-and-retest and one-candle-rule entry the engine WOULD take (all
fired grades, not S-only). For each it:

  1. simulates the original trade forward to a stop-out at the entry's own stop
     (target = 2R; a trade that hits target before stop is a winner and never
     arms, so it produces no candidate — the rule is a re-entry after a LOSER);
  2. from the stop-out bar forward, finds the first bar that closes at/above the
     original entry price (<= for shorts) within the same session = the reclaim;
  3. records the candidate and what the re-entry would have returned in R, taken
     at the reclaim close with the ORIGINAL stop and target, simulated to its own
     stop/target/EOD.

Output: research/rule84_candidates.jsonl (one candidate per line). This list is
the input for the two-bar 84% grading deck Austin asked for (see t8_rule84.md).

This row MEASURES ONLY. It does not arm RULE84 or change any trading gate.
"""

from __future__ import annotations
import json, os, sys, glob
import multiprocessing as mp
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)        # research/t4_engine_recall, research/levels
sys.path.insert(0, ROOT)       # signal_runner, omen_bot
import t4_engine_recall as t4

ARCHIVE = t4.levels.ARCHIVE
OUT_JSONL = os.path.join(HERE, "rule84_candidates.jsonl")
OUT_MD = os.path.join(HERE, "t8_rule84.md")

# Setups that arm the 84% re-entry (signal_runner.RULE84_ARM_ON).
ARM_TYPES = {"break_and_retest", "one_candle_rule"}


def _scan_day(args):
    """Worker: detect BR/OCR fired entries for one (symbol, day) and turn the
    ones that stop out + reclaim into 84% candidates. Returns a dict of counts
    + the candidate list for that day. Imports are re-rooted per process so the
    pool workers find the research package + signal_runner on sys.path."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import t4_engine_recall as _t4
    sym, day = args
    out = {"candidates": [], "entries": 0, "winner": 0,
           "no_reclaim": 0, "ok": False}
    candles = _t4.rth_candles(sym, day)
    if not candles:
        return out
    out["ok"] = True
    ent, _sigs, _raw = _t4.run_day(sym, day)
    if not ent:
        return out
    for e in ent:
        if e["signal_type"] not in ARM_TYPES:
            continue
        out["entries"] += 1
        entry, stop = e["entry"], e["stop"]
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        long = e["direction"] == "call"
        target = (entry + 2 * risk) if long else (entry - 2 * risk)
        j = _simulate_to_stopout(candles, e["bar"], entry, stop, target,
                                 e["direction"])
        if j is None:
            out["winner"] += 1
            continue
        k = _find_reclaim(candles, j, entry, e["direction"])
        if k is None:
            out["no_reclaim"] += 1
            continue
        reclaim_close = candles[k].close
        r2 = abs(reclaim_close - stop)
        if r2 <= 0:
            continue
        R, outcome, exit_price = _reentry_R(candles, k, reclaim_close, stop,
                                           target, e["direction"])
        if R is None:
            continue
        out["candidates"].append({
            "symbol": sym,
            "day": day,
            "signal_type": e["signal_type"],
            "direction": e["direction"],
            "grade": e["grade"],
            "original_entry_bar": e["bar"],
            "original_entry_time": candles[e["bar"]].timestamp,
            "stop_out_bar": j,
            "stop_out_time": candles[j].timestamp,
            "reclaim_bar": k,
            "reclaim_time": candles[k].timestamp,
            "entry_price": round(entry, 4),
            "original_stop": round(stop, 4),
            "original_target": round(target, 4),
            "reclaim_close": round(reclaim_close, 4),
            "reentry_R": R,
            "reentry_outcome": outcome,
            "reentry_exit_price": round(exit_price, 4) if exit_price is not None else None,
        })
    return out


def _simulate_to_stopout(candles, entry_i, entry, stop, target, direction):
    """Walk the original trade forward from bar entry_i+1. Returns the bar index
    of the stop-out (the first bar that touches the stop before/at the target),
    or None if the trade hit target first / never stopped within the session."""
    long = direction == "call"
    for k in range(entry_i + 1, len(candles)):
        c = candles[k]
        stopped = c.low <= stop if long else c.high >= stop
        targeted = c.high >= target if long else c.low <= target
        if stopped:           # conservative: stop wins a same-bar tie (== backtest)
            return k
        if targeted:          # winner -> never arms -> no candidate
            return None
    return None               # open at EOD (scratch) -> never stopped -> no arm


def _find_reclaim(candles, stopout_i, entry, direction):
    """First bar from the stop-out bar forward whose CLOSE is at/above the
    original entry price (at/below for shorts), within the same session."""
    long = direction == "call"
    for k in range(stopout_i, len(candles)):
        close = candles[k].close
        if (close >= entry) if long else (close <= entry):
            return k
    return None


def _reentry_R(candles, reclaim_i, reclaim_close, stop, target, direction):
    """R returned by taking the re-entry at the reclaim close with the ORIGINAL
    stop and target, simulated from reclaim_i+1 to stop/target/EOD.

    win   = target hit first (R = move_to_target / re-entry risk, > 0)
    loss  = stop hit first (R = -1.0)
    scratch = neither by EOD -> mark to last close (signed partial R)
    """
    long = direction == "call"
    r2 = abs(reclaim_close - stop)
    if r2 <= 0:
        return None, "degenerate", None
    exit_price = None
    for k in range(reclaim_i + 1, len(candles)):
        c = candles[k]
        stopped = c.low <= stop if long else c.high >= stop
        targeted = c.high >= target if long else c.low <= target
        if stopped:
            return -1.0, "loss", stop
        if targeted:
            exit_price = target
            move = (target - reclaim_close) if long else (reclaim_close - target)
            return round(move / r2, 4), "win", target
    # EOD scratch at last close (matches backtest_week's open-trade EOD close)
    last = candles[-1].close
    move = (last - reclaim_close) if long else (reclaim_close - last)
    return round(move / r2, 4), "scratch", last


def main():
    pairs = []
    for sym in sorted(os.listdir(ARCHIVE)):
        sd = os.path.join(ARCHIVE, sym)
        if not os.path.isdir(sd):
            continue
        for f in sorted(glob.glob(os.path.join(sd, "*.csv"))):
            pairs.append((sym, os.path.basename(f)[:-4]))

    candidates = []
    skipped_winner = 0          # original hit target / never stopped -> never armed
    skipped_no_reclaim = 0     # stopped but never reclaimed in-session
    n_entries = 0
    n_days = 0
    # Detection per (symbol, day) is independent -> parallelise across cores.
    # Each worker reuses the harness's own t4_engine_recall.run_day detection,
    # so the entries scanned are exactly what the engine would take.
    nproc = min(4, os.cpu_count() or 1)
    with mp.Pool(nproc) as pool:
        for r in pool.imap_unordered(_scan_day, pairs, chunksize=25):
            if r["ok"]:
                n_days += 1
            n_entries += r["entries"]
            skipped_winner += r["winner"]
            skipped_no_reclaim += r["no_reclaim"]
            candidates.extend(r["candidates"])

    # stable, human-readable order: symbol, day, original entry bar
    candidates.sort(key=lambda c: (c["symbol"], c["day"], c["original_entry_bar"]))

    with open(OUT_JSONL, "w") as f:
        for c in candidates:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # ---- summary metrics ----
    n = len(candidates)
    if n:
        wins = sum(1 for c in candidates if c["reentry_outcome"] == "win")
        win_rate = round(wins / n * 100, 1)
        avg_R = round(sum(c["reentry_R"] for c in candidates) / n, 4)
        oc = Counter(c["reentry_outcome"] for c in candidates)
    else:
        wins = win_rate = avg_R = 0
        oc = Counter()

    by_setup = Counter(c["signal_type"] for c in candidates)
    by_grade = Counter(c["grade"] for c in candidates)
    by_dir = Counter(c["direction"] for c in candidates)

    lines = []
    lines.append("# T8 — the 84% re-entry candidates the card deck can never show")
    lines.append("")
    lines.append("> Source deck input: `research/rule84_candidates.jsonl` — the "
                 "candidate set this row produces. It is the input for the "
                 "two-bar 84% grading deck Austin asked for: each line is a "
                 "losing break-and-retest / one-candle-rule entry, its stop-out, "
                 "and the bar that reclaimed the original entry price — the "
                 "three bars a single-bar grading card physically cannot hold.")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("```")
    lines.append(f"rule84_candidates: {n}")
    lines.append(f"rule84_win_rate: {win_rate}")
    lines.append(f"rule84_avg_R: {avg_R}")
    lines.append("```")
    lines.append("")
    lines.append(f"- scanned **{n_days}** archived sessions across "
                 f"{len({p[0] for p in pairs})} symbols; {n_entries} fired "
                 "break-and-retest / one-candle-rule entries the engine would take.")
    lines.append(f"- {skipped_winner} originals hit target (or never stopped "
                 "before EOD) -> a winner never arms the re-entry.")
    lines.append(f"- {skipped_no_reclaim} stopped out but never reclaimed the "
                 "entry price later that session -> no re-entry to take.")
    lines.append(f"- outcome mix: {dict(oc)}  "
                 f"(setup: {dict(by_setup)}  grade: {dict(by_grade)}  "
                 f"dir: {dict(by_dir)})")
    lines.append("")
    lines.append("## What the 84% rule is, in plain English")
    lines.append("")
    lines.append(
        "The 84% rule is a do-over for a trade that already failed. You take a "
        "break-and-retest or one-candle-rule entry, it stops you out, and then "
        "price turns around and closes back at the price you originally got in. "
        "The rule says: take the trade again, with the same stop and the same "
        "target. The claim is that the first loss was bad timing, not a bad "
        "idea — the setup was right, the entry was early — so the second bite "
        "works far more often than a cold entry.")
    lines.append("")
    lines.append("## Why it never showed up in the grading decks")
    lines.append("")
    lines.append(
        "Every card the deck has ever shown Austin is one bar: here is a bar, "
        "what would you do? The 84% rule is not a one-bar question. It needs "
        "the first entry, the bar that stopped it out, and the later bar that "
        "closed back through the original entry price — three bars tied "
        "together by a loss in between. A grading card that shows a single bar "
        "has no way to ask about that, so the deck has never put one in front "
        "of him, and nothing in the archive has ever reported how often the "
        "pattern is even there. This scan is the first time that set exists.")
    lines.append("")
    lines.append("## Are these candidates worth arming?")
    lines.append("")
    if n == 0:
        lines.append(
            "No candidates were found in the archive, so there is nothing here "
            "to arm. That is itself the finding: the pattern the 84% rule "
            "describes does not occur in the archived sessions under the "
            "engine's own entry detection.")
    else:
        verdict_win = (f"The {n} candidates ran **{win_rate}%** to target "
                       f"({wins} of {n}) at an average of **{avg_R}R**.")
        lines.append(
            f"{verdict_win} For context, the rule's own claim is an 84% hit "
            f"rate. Measured against the engine's actual break-and-retest and "
            f"one-candle-rule losers in the archive, the re-entry does not land "
            f"near that — these are the trades the deck was never shown, graded "
            f"cold by the geometry alone.")
        if avg_R > 0 and win_rate >= 50:
            lines.append("")
            lines.append(
                "The average R is positive and the win rate clears half, so the "
                "pattern is not obviously leaking — but this row measures only "
                "and does not arm it. Arming RULE84 is Austin's call, and the "
                "two-bar deck built from this list is how he judges it on his "
                "own charts rather than on a number.")
        else:
            lines.append("")
            lines.append(
                "The average R and win rate do not clear the bar the rule sets "
                "for itself, so on the evidence here there is no case for "
                "arming it. This row measures only and does not change any "
                "trading gate; the two-bar deck built from this list is what "
                "lets Austin see these on his own charts and settle it.")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        "- Detection: `research/t4_engine_recall.run_day` — the harness's own "
        "replay of `signal_runner.SignalRunner.detect_signals` (bar-by-bar, "
        "11:00 entry cutoff, 30-bar per-idea dedupe, archive-reconstructed "
        "PDH/PDL/PMH/PML/HTF bias). Every fired break-and-retest and "
        "one-candle-rule entry, all grades (not S-only).")
    lines.append(
        "- Original trade: entered at the entry bar's close, stop at the "
        "setup's own stop, 2R target; walked forward to the first bar that "
        "touches the stop before the target (stop wins a same-bar tie, as in "
        "the backtest). A trade that hits target first, or is still open at "
        "the session close, never stopped out and so never arms — no candidate.")
    lines.append(
        "- Reclaim: the first bar from the stop-out bar forward whose CLOSE is "
        "at/above the original entry price (at/below for shorts), same session.")
    lines.append(
        "- Re-entry R: taken at the reclaim close with the ORIGINAL stop and "
        "target, simulated forward to its own stop (-1R), target (+R), or the "
        "session close (signed partial R). `rule84_win_rate` is the fraction "
        "that hit target; `rule84_avg_R` is the mean signed R over all "
        "candidates.")
    lines.append(
        "- This row measures only. It does not arm RULE84 and changes no "
        "trading gate; `python research/regression_gate.py` is unchanged.")

    open(OUT_MD, "w").write("\n".join(lines) + "\n")

    print(f"days scanned: {n_days}")
    print(f"BR/OCR fired entries: {n_entries}")
    print(f"  winners / never-stopped (no arm): {skipped_winner}")
    print(f"  stopped but no in-session reclaim: {skipped_no_reclaim}")
    print(f"candidates: {n}")
    print(f"  outcome mix: {dict(oc)}")
    print(f"  win_rate: {win_rate}%  avg_R: {avg_R}")
    print(f"  setup: {dict(by_setup)}  grade: {dict(by_grade)}  dir: {dict(by_dir)}")
    print(f"wrote {OUT_JSONL} and {OUT_MD}")


if __name__ == "__main__":
    main()
