"""g160 -- the 2x2x2x2 day/tier-policy grid, S_CLASSIFIER ON and OFF, over the
honest one-trade(ish)-a-day unit.

    python research/g160_tweak_grid.py

OMEN 9.0 row O1. This is a SELECTION arm: it re-picks trades out of the
already-generated candidate stream in `research/bt2y_trades_retest_on.json`
(RETEST_REQUIRED=1, the shipped default). It does not re-run the engine, so
it cannot model any interaction that only shows up when the engine itself
sees a different candidate set -- see "Known limitation" below, which is the
same shortcut F7's own refuters flagged in the S_CLASSIFIER arm.

Four binary levers, swept as a full 2x2x2x2 = 16-arm grid, plus one baseline:

  DAY_POLICY     one_and_done      -- first takeable candidate of the day, done.
                 first3_loss_halt  -- up to 3 takeable candidates/day, stop
                                      early after 2 consecutive losses (same
                                      HALT_AFTER_CONSECUTIVE_LOSSES=2 the book
                                      itself uses for its own halted rows).
  ENTRY_WINDOW   09:45   -- only candidates with et <= 09:45 are takeable.
                 11:00   -- the book's native full window (SESSION_END).
  TIER_POLICY    s_only          -- only austin_tier ('sgrade' in the book,
                                     computed by signal_runner.compute_austin_tier)
                                     == 'S' is takeable.
                 fire_a_no_s     -- 'S' is always takeable; 'A' becomes
                                     takeable too, but only at or after 10:00
                                     ET on a day where no 'S' has fired yet
                                     (causal -- no lookahead: it only looks at
                                     candidates already scanned this day).
  VETO_1D        off / on  -- see "1D veto" below.

  CLASSIFIER (S_CLASSIFIER v0, F7, REFUTED)  -- ON drops any candidate whose
  stop level is 'OR high'/'OR low' AND carries the 'no_retest' downgrade
  (research/g154_rule_or-break-without-retest.py), same predicate
  research/test_s_classifier.py exercises. F7's own adversarial passes
  refuted it (12 of 498 sessions move, half the gain is one day, a random
  drop clears the same gate 21.7% of the time) -- it is reported here for
  completeness, per the row's own instruction, and is NOT leaned on for
  which arm wins.

Baseline (not part of the 16): `research/omen_metrics.first_of_day_arm` run
unmodified -- the CURRENT shipped one-trade-a-day unit. It applies no
austin_tier restriction at all (the legacy A+/A/B/C/X ladder is what gates
today's book, not the S/A/C ladder -- CLAUDE.md "Two grade ladders"), no
window cut, no 1D veto, classifier off.

"1D veto" (VETO_1D): the book carries no genuine per-symbol daily-timeframe
bias field (its only HTF field, 'bias'/'bias_tf', is a 1-hour bias, and it
already gates 'aligned' upstream of this book). The closest available proxy
for a *daily* directional filter is 'spy_trend' (bull/bear, market-wide,
computed off daily bars) crossed with the candidate's own direction ('dir':
call/put). VETO_1D=on skips a candidate whose direction opposes spy_trend
(call while spy_trend=bear, put while spy_trend=bull). This is a documented
substitution, not the "real" 1D veto O2 will eventually wire -- flagged here
so nobody downstream mistakes it for more than a proxy.

Known limitation (shared with F7): dropping a candidate here does not
release `backtest_week.DEDUPE_FIRES_ONLY`'s suppression window the way the
live engine would if that candidate had never fired in the first place. Every
arm below undercounts what a live rerun of the engine under the same flags
would actually produce. Treat differences between arms as directional, not
exact.

S recall: per arm, of the days that have >=1 'S'-tier candidate surviving
that arm's classifier/window/1D-veto filters, the fraction where the arm's
actual pick(s) for that day include an 'S'-tier trade. Denominator and
numerator are both defined by this script; do not compare to a differently-
defined "recall" number from another script without checking the definition.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research.omen_metrics import ev_r_scoreboard, first_of_day_arm  # noqa: E402

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
H_SPLIT = "2025-09-01"          # H1 < split <= H2, per the row's instruction
RISK_DOLLARS = 1000.0


def _eligible(rows):
    """Same predicate `first_of_day_arm` uses: fired-and-traded, or halted
    (the loss-halt blocked a day that a strict one-a-day policy would still
    be live for)."""
    return [r for r in rows
            if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted"]


def _classifier_drop(r):
    return r.get("level") in ("OR high", "OR low") and "no_retest" in (r.get("downgrades") or ())


def _veto_1d(r):
    d, trend = r.get("dir"), r.get("spy_trend")
    return (d == "call" and trend == "bear") or (d == "put" and trend == "bull")


def build_arm(rows_by_day, *, classifier_on, day_policy, window_end, fire_a_no_s, veto1d_on):
    """Returns (trades, s_available_days, s_captured_days) -- `trades` is a
    flat, chronologically-ordered list of book rows this arm actually takes.
    """
    trades = []
    s_available_days = 0
    s_captured_days = 0

    for day in sorted(rows_by_day):
        cands = sorted(rows_by_day[day], key=lambda r: (r["et"], r["sym"]))
        filtered = []
        for r in cands:
            if classifier_on and _classifier_drop(r):
                continue
            if r["et"] > window_end:
                continue
            if veto1d_on and _veto_1d(r):
                continue
            filtered.append(r)

        if any(r["sgrade"] == "S" for r in filtered):
            s_available_days += 1

        picks = []
        consec_losses = 0
        for r in filtered:
            tier = r["sgrade"]
            already_s = any(p["sgrade"] == "S" for p in picks)
            takeable = (tier == "S") or (
                fire_a_no_s and tier == "A" and r["et"] >= "10:00" and not already_s
            )
            if not takeable:
                continue
            picks.append(r)
            if day_policy == "one_and_done":
                break
            consec_losses = consec_losses + 1 if r["r"] < 0 else 0
            if len(picks) >= 3 or consec_losses >= 2:
                break

        if picks:
            trades.extend(picks)
            if any(p["sgrade"] == "S" for p in picks):
                s_captured_days += 1

    return trades, s_available_days, s_captured_days


def _half(rows, lo=None, hi=None):
    if lo is None:
        return [r for r in rows if r["day"] < hi]
    return [r for r in rows if r["day"] >= lo]


def _sessions(rows, lo=None, hi=None):
    if lo is None:
        days = {r["day"] for r in rows if r["day"] < hi}
    else:
        days = {r["day"] for r in rows if r["day"] >= lo}
    return len(days)


def _scoreboard_row(trades, sessions):
    sb = ev_r_scoreboard(trades, risk_dollars=RISK_DOLLARS, sessions=sessions)
    return sb


def main():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, all_rows = blob["meta"], blob["trades"]
    total_sessions = meta.get("sessions") or len({r["day"] for r in all_rows})
    sessions_h1 = _sessions(all_rows, hi=H_SPLIT)
    sessions_h2 = _sessions(all_rows, lo=H_SPLIT)

    elig = _eligible(all_rows)
    rows_by_day = defaultdict(list)
    for r in elig:
        rows_by_day[r["day"]].append(r)

    print("book: %s -- %d sessions total (H1=%d, H2=%d), %d eligible candidate rows"
          % (os.path.basename(BOOK_PATH), total_sessions, sessions_h1, sessions_h2, len(elig)))

    # -- baseline: today's shipped one-trade-a-day unit, unmodified --------
    baseline_trades = first_of_day_arm(all_rows)
    results = []
    for label, trades in (
        ("BASELINE (shipped first_of_day_arm)", baseline_trades),
    ):
        h1 = _half(trades, hi=H_SPLIT)
        h2 = _half(trades, lo=H_SPLIT)
        sb_all = _scoreboard_row(trades, total_sessions)
        sb_h1 = _scoreboard_row(h1, sessions_h1)
        sb_h2 = _scoreboard_row(h2, sessions_h2)
        results.append({
            "label": label, "classifier": "n/a", "day_policy": "one_and_done (shipped)",
            "window_end": "11:00 (shipped)", "tier_policy": "unrestricted (legacy ladder gates today)",
            "veto1d": "off",
            "n_all": sb_all["n"], "fires_per_day": sb_all["n"] / total_sessions,
            "ev_r_all": sb_all["ev_r"], "ev_r_h1": sb_h1["ev_r"], "ev_r_h2": sb_h2["ev_r"],
            "dollars_day_all": sb_all["expectancy_per_day"],
            "dollars_day_h1": sb_h1["expectancy_per_day"], "dollars_day_h2": sb_h2["expectancy_per_day"],
            "months_green": sb_all["months_green"], "max_dd_R": sb_all["max_drawdown_R"],
            "win_rate": sb_all["win_rate"], "s_recall": None,
        })

    axes = [
        ("classifier_on", [False, True]),
        ("day_policy", ["one_and_done", "first3_loss_halt"]),
        ("window_end", ["09:45", "11:00"]),
        ("fire_a_no_s", [False, True]),
        ("veto1d_on", [False, True]),
    ]
    # 16 arms = day_policy x window_end x fire_a_no_s x veto1d, run TWICE
    # (classifier off, classifier on) so both are on record per the row's
    # "with the classifier ON and OFF" instruction -- 32 rows total below the
    # baseline, but the 16-arm grid itself is the four non-classifier axes.
    for classifier_on in (False, True):
        for day_policy in ("one_and_done", "first3_loss_halt"):
            for window_end in ("09:45", "11:00"):
                for fire_a_no_s in (False, True):
                    for veto1d_on in (False, True):
                        trades, s_avail, s_cap = build_arm(
                            rows_by_day, classifier_on=classifier_on, day_policy=day_policy,
                            window_end=window_end, fire_a_no_s=fire_a_no_s, veto1d_on=veto1d_on)
                        h1 = _half(trades, hi=H_SPLIT)
                        h2 = _half(trades, lo=H_SPLIT)
                        sb_all = _scoreboard_row(trades, total_sessions)
                        sb_h1 = _scoreboard_row(h1, sessions_h1)
                        sb_h2 = _scoreboard_row(h2, sessions_h2)
                        label = "clf=%s day=%s win=%s fireA=%s veto1d=%s" % (
                            "ON" if classifier_on else "off", day_policy, window_end,
                            "on" if fire_a_no_s else "off", "on" if veto1d_on else "off")
                        results.append({
                            "label": label, "classifier": "ON" if classifier_on else "off",
                            "day_policy": day_policy, "window_end": window_end,
                            "tier_policy": "fire_A_when_no_S_by_10" if fire_a_no_s else "s_only",
                            "veto1d": "on" if veto1d_on else "off",
                            "n_all": sb_all["n"], "fires_per_day": sb_all["n"] / total_sessions,
                            "ev_r_all": sb_all["ev_r"], "ev_r_h1": sb_h1["ev_r"], "ev_r_h2": sb_h2["ev_r"],
                            "dollars_day_all": sb_all["expectancy_per_day"],
                            "dollars_day_h1": sb_h1["expectancy_per_day"],
                            "dollars_day_h2": sb_h2["expectancy_per_day"],
                            "months_green": sb_all["months_green"], "max_dd_R": sb_all["max_drawdown_R"],
                            "win_rate": sb_all["win_rate"],
                            "s_recall": (s_cap / s_avail) if s_avail else None,
                            "s_available_days": s_avail,
                        })

    out_json = os.path.join(HERE, "g160_tweak_grid.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {"book": os.path.basename(BOOK_PATH), "total_sessions": total_sessions,
                      "sessions_h1": sessions_h1, "sessions_h2": sessions_h2, "h_split": H_SPLIT,
                      "risk_dollars": RISK_DOLLARS},
            "arms": results,
        }, f, indent=2)
    print("wrote %s (%d arms incl. baseline)" % (out_json, len(results)))

    # -- console table -----------------------------------------------------
    hdr = ("label", "n", "fires/day", "ev_r_all", "ev_r_H1", "ev_r_H2",
           "$/day", "green_mo", "max_DD_R", "win%", "S_recall")
    print("\n" + " | ".join(hdr))
    for row in results:
        print(" | ".join(str(x) for x in (
            row["label"],
            row["n_all"],
            round(row["fires_per_day"], 2),
            row["ev_r_all"] if row["ev_r_all"] is None else round(row["ev_r_all"], 3),
            row["ev_r_h1"] if row["ev_r_h1"] is None else round(row["ev_r_h1"], 3),
            row["ev_r_h2"] if row["ev_r_h2"] is None else round(row["ev_r_h2"], 3),
            row["dollars_day_all"] if row["dollars_day_all"] is None else round(row["dollars_day_all"], 1),
            row["months_green"],
            round(row["max_dd_R"], 2),
            row["win_rate"] if row["win_rate"] is None else round(100 * row["win_rate"], 1),
            row["s_recall"] if row["s_recall"] is None else round(100 * row["s_recall"], 1),
        )))


if __name__ == "__main__":
    main()
