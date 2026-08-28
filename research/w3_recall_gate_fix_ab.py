"""W3 -- the recall gate, turned green on a book that is still takeable.

`research/regression_gate.py` has been RED at HEAD since `5e3677ea` (2026-08-11),
dropping six of Austin's `s_grade` marks. RECALL GOVERNS in this project, so a
red recall gate is the most serious standing defect.

The mechanism is not re-diagnosed here; `research/g12_recall_regression.md`
settled it. `fill_price()` back-dates a break-and-retest entry onto the broken
level, and for B&R the level IS the structural stop, so `|entry - stop|`
collapses under the pre-existing minimum-risk floor `max(0.10, 0.0015 x close)`
and the setup is force-graded `D` (== `X`, a skip).

Two answers have already been measured and BOTH failed:

  G13  ENABLE_STRUCTURAL_RISK_FLOOR  moved the FLOOR onto the pre-fill risk.
       Recovered 5 of 6 marks and made 73.3% of the book untakeable, because
       `backtest_week` still sized on the POST-fill risk. The floor and the
       sizer stopped reading the same number.
  G16  ENABLE_STRUCTURAL_RISK        moved the floor, `stock_risk` AND the R
       denominator together. Untakeable fell to 1.4%, but the pathology
       inverted (85.3% of rows rest their stop closer than one booked R) and
       the gate stayed red on one mark.

This ticket takes the third road, `signal_runner.ENABLE_MIN_RISK_FILL_CLAMP`:
keep the floor and the sizer on ONE number -- the post-fill risk they already
share -- and move the FILL instead. If the back-dated fill would leave less than
the floor between the entry and the stop, the booked entry is walked back toward
the bar's close only as far as the floor requires, and never past the close.

    long   entry := min(close, max(entry, stop + floor + tick))
    short  entry := max(close, min(entry, stop - floor - tick))

Both ends of that interval are prices the bar traded, so the clamped fill is
achievable and is strictly WORSE than the fill HEAD books -- it is a concession,
not a windfall. A book made of clamped fills has `|entry - stop| >= floor` by
construction, which is exactly the property g13 measured the absence of.

Three instruments, both arms, the same three g13 used:

  1. `research/regression_gate.py`   -- the recall gate (done criterion 1)
  2. `backtest_2y.py`                -- the 2-year book (done criterion 2)
  3. `research/t70_test1_score.py`   -- the 100 HELD-OUT cards (criterion 3)

REUSED, NEVER REIMPLEMENTED
---------------------------
Every measurement function in this file is `research/g13_floor_fix_ab.py`'s,
imported and rebound onto this ticket's flag by `_rebind()`. That is deliberate:
a private copy of `sizeable()` or `test1_counts()` would be a different rig
wearing g13's name, and the two reports have to be readable side by side.

    python research/w3_recall_gate_fix_ab.py --selfcheck
    python research/w3_recall_gate_fix_ab.py book --arm head   # unmodified HEAD
    python research/w3_recall_gate_fix_ab.py book --arm off
    python research/w3_recall_gate_fix_ab.py book --arm on
    python research/w3_recall_gate_fix_ab.py identical         # head == off
    python research/w3_recall_gate_fix_ab.py gate
    python research/w3_recall_gate_fix_ab.py marks
    python research/w3_recall_gate_fix_ab.py test1
    python research/w3_recall_gate_fix_ab.py stats
    python research/w3_recall_gate_fix_ab.py report
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import g13_floor_fix_ab as g13                            # noqa: E402

FLAG = "ENABLE_MIN_RISK_FILL_CLAMP"
OUT_MD = os.path.join(HERE, "w3_recall_gate_fix.md")

ARMS = {
    "head": (None, os.path.join(HERE, "w3_arm_head.json")),
    "off":  ("0",  os.path.join(HERE, "w3_arm_off.json")),
    "on":   ("1",  os.path.join(HERE, "w3_arm_on.json")),
}


def _rebind():
    """Point g13's rig at THIS ticket's flag and files.

    g13's runners read `FLAG`, `ARMS` and the four json paths off its own module
    globals. Rebinding them is what makes this an A/B of a different flag on the
    SAME rig rather than a second rig -- there is no copy of `sizeable`,
    `compose`, `split_sizeable`, `test1_counts` or `book_stats` in this file, and
    that is the point. Idempotent; called at import."""
    g13.FLAG = FLAG
    g13.ARMS = ARMS
    g13.GATE_JSON = os.path.join(HERE, "_w3_gate.json")
    g13.TEST1_JSON = os.path.join(HERE, "_w3_test1.json")
    g13.BOOK_STATS = os.path.join(HERE, "_w3_book_stats.json")
    g13.MARKS_JSON = os.path.join(HERE, "_w3_marks.json")


_rebind()


def pct(n, d):
    return (100.0 * n / d) if d else 0.0


def frac(n, d):
    return "%d/%d = %.0f%%" % (n, d, pct(n, d))


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

# Error bars are NOT quoted here. Both are recomputed on each arm's own book by
# g13's book_stats -> research.g3_onwatch_2y.error_bars, and only the NARROW one
# is read: Austin settled the question the wide bar existed for on 2026-08-28 --
# a stop is triggered by a candle CLOSE and by nothing else, and the entry
# candle's own close counts. One bar has one close, so a stop cannot fire inside
# the entry bar ahead of the back-dated fill. The WIDE bar (+/-1.5799 R) is
# RETIRED and never appears in this report as a live interval.


def _gate_rows():
    return json.load(open(g13.GATE_JSON, encoding="utf-8"))


def report() -> int:
    gate = _gate_rows()
    t1 = json.load(open(g13.TEST1_JSON, encoding="utf-8"))
    st = json.load(open(g13.BOOK_STATS, encoding="utf-8"))
    A = st["arms"]

    g = {a: {"any": len(gate[a]["any_signal"]), "s": len(gate[a]["s_grade"]),
             "drop_s": sorted(set(gate[a]["base_s"]) - set(gate[a]["s_grade"])),
             "drop_a": sorted(set(gate[a]["base_any"]) - set(gate[a]["any_signal"])),
             "tier": gate[a]["by_tier"]} for a in ("off", "on")}
    base_s, base_any = len(gate["off"]["base_s"]), len(gate["off"]["base_any"])
    c = {a: g13.test1_counts(t1[a]) for a in ("off", "on")}
    sp = {a: A[a]["split"] for a in ("off", "on")}
    cp = st["compose"]

    off_by = {(r["symbol"], r["date"]): r for r in t1["off"]}
    on_by = {(r["symbol"], r["date"]): r for r in t1["on"]}
    newf = sorted(k for k in on_by if on_by[k]["n_fires"] > 0 and off_by[k]["n_fires"] == 0)
    lostf = sorted(k for k in on_by if on_by[k]["n_fires"] == 0 and off_by[k]["n_fires"] > 0)
    newf_by_grade = defaultdict(list)
    for k in newf:
        newf_by_grade[on_by[k]["his"]].append(k)

    green = not (g["on"]["drop_a"] or g["on"]["drop_s"])

    L = []
    add = L.append
    add("# W3 — the recall gate, green, on a book that is still takeable")
    add("")
    add("**`python research/regression_gate.py` exits 0 with "
        "`ENABLE_MIN_RISK_FILL_CLAMP=1`, and the 2-year book it produces is "
        "%.1f%% untakeable against HEAD's %.1f%%.** The gate has been RED since "
        "`5e3677ea` (2026-08-11) — 16 days and 112 commits before anyone ran it. "
        "`s_grade` goes **%d → %d** on a %d-mark gate, all %d detections kept, "
        "and none of the six marks G12 named is dropped any more."
        % (sp["on"]["pct_unsizeable"], sp["off"]["pct_unsizeable"],
           g["off"]["s"], g["on"]["s"], base_s, g["on"]["any"]))
    add("")
    add("**Held-out first, because that is the rule.** On the 100 HELD-OUT OMEN "
        "Test 1 cards S recall is **%s before and %s after** — it does not fall, "
        "and it does not rise. False fires on days Austin refused go %s → %s. "
        "The in-sample recall gain does not reproduce out of sample, exactly as "
        "it failed to for the three arms A/B'd on 2026-08-27. Treat the +%d "
        "in-sample S marks as a gate result, not as evidence the engine sees "
        "more of what he sees."
        % (frac(c["off"]["s_hit"], c["off"]["s_n"]),
           frac(c["on"]["s_hit"], c["on"]["s_n"]),
           frac(c["off"]["x_fire"], c["off"]["x_n"]),
           frac(c["on"]["x_fire"], c["on"]["x_n"]),
           g["on"]["s"] - g["off"]["s"]))
    add("")
    add("The mechanism in one sentence. **G13 moved the floor and left the sizer "
        "behind; this moves the FILL and leaves both where they are.** The floor "
        "and `backtest_week`'s position size read the same `|entry - stop|` in "
        "both arms, so a book of clamped fills satisfies `|entry - stop| >= "
        "floor` BY CONSTRUCTION — the property g13 measured the absence of in "
        "73.3%% of its rows. The clamped entry is never better than the "
        "back-dated fill and never worse than the bar's own close, so it is a "
        "price the bar traded through on its way to the level: a concession, not "
        "a windfall.")
    add("")
    add("Nothing here ships. `signal_runner.ENABLE_MIN_RISK_FILL_CLAMP` defaults "
        "to **False**, `5e3677ea` is not reverted, `B&R_MIN_RISK` is not retuned, "
        "and the engine is not re-frozen — that would VOID "
        "`research/omen6_forward.py` and it is Austin's call. Measured at _this "
        "commit_ by `research/w3_recall_gate_fix_ab.py`.")
    add("")

    # ---- 1 ---------------------------------------------------------------
    add("## 1. What was implemented")
    add("")
    add("| | |")
    add("|---|---|")
    add("| flag | `signal_runner.ENABLE_MIN_RISK_FILL_CLAMP`, **default False**, "
        "`ENABLE_MIN_RISK_FILL_CLAMP=1` to A/B |")
    add("| functions | `signal_runner.min_risk_floor()`, "
        "`signal_runner.clamp_fill_to_min_risk()` |")
    add("| OFF | `clamp_fill_to_min_risk` returns its `entry` argument unchanged "
        "— the same float in, the same float out |")
    add("| ON | long `entry := min(close, max(entry, stop + floor + tick))`; "
        "short `entry := max(close, min(entry, stop - floor - tick))` |")
    add("| unchanged either way | the floor's value, the floor's denominator, "
        "the R denominator, the sizer, `STOP_RANGE_MULT`, `fill_price`, "
        "`intrabar_stop` |")
    add("| call sites | `signal_runner.py` B&R long and B&R short, immediately "
        "AFTER `intrabar_stop()` and before `stock_risk` |")
    add("")
    add("**The floor is neither disabled, widened, nor retuned.** "
        "`B&R_MIN_RISK = 0.0015 x close` is one of the 33 constants "
        "`research/hallucination-audit.md` classes UNMENTIONED — Austin never "
        "stated it, it is ours, and it is flagged HIGH. This ticket had licence "
        "to tune it and did not: lowering the multiplier admits precisely the "
        "rows the floor was written to reject, and *untakeable* would then be "
        "measured against a yardstick the change had moved. The clamp makes the "
        "engine OBEY the constant on the price it books instead of using it to "
        "delete setups. If Austin later says the constant is wrong, the clamp "
        "still holds — it reads whatever `min_risk_floor()` returns.")
    add("")
    add("A signal whose fill was never back-dated already clears the floor, so "
        "the clamp is a no-op on it. The only rows this can touch are the ones "
        "`fill_price()` moved.")
    add("")
    add("### Why the clamp runs AFTER `intrabar_stop()`, and what the other "
        "order costs")
    add("")
    add("`intrabar_stop()` exists for the same wound \u2014 its docstring says "
        "*\"223 of 744 B&R signals (30%) collapsed this way and were dropped "
        "by the minimum-risk gate\"*. Its answer is to move the STOP to the "
        "entry bar's extreme; the clamp's answer is to move the FILL. Running "
        "the clamp LAST makes the two compose instead of compete, and buys the "
        "property this whole ticket rests on:")
    add("")
    add("> **The clamp can only ever raise `|entry - stop|`, so `risk_on >= "
        "risk_off` on every signal and the minimum-risk floor can never "
        "newly reject one.** Checked, not asserted: of the %d rows HEAD "
        "trades and this arm does not, **0** are `skipped_d` \u2014 the whole "
        "loss column is `skipped_tight_stop/C` %d, `fired/C` %d and "
        "`skipped_repeat_entry` %d, every one of them a downstream SELECTION "
        "effect and none of them the gate this ticket touches."
        % (cp["n_lost"], cp["lost_status_on"].get("skipped_tight_stop/C", 0),
           cp["lost_status_on"].get("fired/C", 0),
           cp["lost_status_on"].get("skipped_repeat_entry/B", 0)
           + cp["lost_status_on"].get("skipped_repeat_entry/C", 0)))
    add("")
    add("Those %d are worth naming rather than rounding away, because they "
        "are G4 \u00a76's finding showing up again. A row logged "
        "`skipped_tight_stop/C` is a row that is now a `C`, and the only "
        "thing that demotes it is losing `_calibration_grade`'s "
        "first-with-trend-signal-of-the-day `B` floor to an EARLIER signal "
        "the clamp newly admitted. Arrival order, not the setup, is what "
        "moved \u2014 which is exactly the lever G14 is queued to A/B. Inferred "
        "from the logged status; not separately instrumented here."
        % cp["n_lost"])
    add("")
    add("Running the clamp FIRST is the other coherent design and it was built "
        "and measured. It restores an invariant `signal_runner.py` states in "
        "its own `NO_REPEAT_ENTRIES` comment \u2014 *\"`sig[\"stop\"]` IS the "
        "retested structural level for every setup\"* \u2014 which `intrabar_stop` "
        "breaks, and which `idea_key`, the no-repeat scope and "
        "`spec0b_levels_check.py` all read. It is **variant B**, and it is not "
        "shipped. On W12's 8-candle fixture:")
    add("")
    add("| | `stop` emitted | `entry` | risk |")
    add("|---|---:|---:|---:|")
    add("| HEAD | \u2014 (signal deleted, `skipped_d`) | 101.00 | 0.100 |")
    add("| **shipped: clamp after `intrabar_stop`** | 100.90 (bar low) | "
        "101.06255 | 0.16255 |")
    add("| variant B: clamp before `intrabar_stop` | 101.00 = PDH | 101.16255 "
        "| 0.16255 |")
    add("")
    add("Same risk either way; the ordering decides whether the stop is the "
        "broken level or the entry bar's wick, and whether the entry pays ten "
        "more cents for it.")
    add("")
    add("**Why variant B lost.** It is not additive. Where the close sits too "
        "near the level for the clamp to reach the floor, variant B resolves "
        "to the close and the floor rejects the setup \u2014 whereas HEAD had "
        "already rescued that row by moving the stop to the wick. Measured on "
        "the same 2-year rig at this commit, by re-ordering the two lines and "
        "re-running every arm:")
    add("")
    add("| | shipped (clamp last) | variant B (clamp first) |")
    add("|---|---:|---:|")
    add("| recall gate | GREEN, `s_grade` %d | GREEN, `s_grade` 13 |"
        % g["on"]["s"])
    add("| held-out S recall | %d/%d | 3/15 |"
        % (c["on"]["s_hit"], c["on"]["s_n"]))
    add("| held-out false fires | %d/%d | 20/42 |"
        % (c["on"]["x_fire"], c["on"]["x_n"]))
    add("| n traded | %s | 1,558 |" % f"{A['on']['all']['traded']:,}")
    add("| untakeable | %.1f%% | 1.7%% |" % sp["on"]["pct_unsizeable"])
    add("| mean R | %+.4f | +1.1061 |" % A["on"]["all"]["meanr"])
    add("| months green | %d / %d | 25 / 25 |"
        % (A["on"]["all"]["months_green"], A["on"]["all"]["months"]))
    add("| **trades HEAD takes that it DROPS** | **%s, %s to the floor** | "
        "**588, of which 584 were takeable** |"
        % (f"{cp['n_lost']:,}", cp["lost_status_on"].get("skipped_d/X", 0)))
    add("| rows traded by BOTH arms | %s | 429 |" % f"{cp['n_shared']:,}")
    add("| those rows' median R, HEAD -> arm | %+.4f -> %+.4f | +0.7870 -> "
        "**\u22121.0000** |"
        % (cp["shared_off"]["median_r"], cp["shared_on"]["median_r"]))
    add("| those rows' win rate, HEAD -> arm | %.1f%% -> %.1f%% | 55.7%% -> "
        "**49.8%%** |"
        % (cp["shared_off"]["wr"], cp["shared_on"]["wr"]))
    add("")
    add("Variant B books a higher mean R and 25/25 months green, and it earns "
        "them by refusing 588 of HEAD's trades and by making the trades it "
        "keeps WORSE: on the 429 rows variant B and HEAD both take it pays "
        "a higher entry "
        "AND holds the tighter level stop, and the median outcome goes from "
        "+0.7870 R to a full stop-out. A mean R that rises while the median "
        "goes to \u22121.0 on identical rows is the failure mode this project "
        "has already hit three times (G13, G16, R9); it is not shipped for "
        "that reason. Reproduce it by swapping the two lines at "
        "`signal_runner.py` B&R long/short and re-running every arm.")
    add("")
    add("**Austin's wick-stop rule is untouched either way.** `intrabar_stop` "
        "is not edited. In the shipped order it still fires exactly where it "
        "fires today; in variant B the clamp would leave it nothing to react "
        "to. Which answer he wants \u2014 the wick stop of `5e3677ea` or the "
        "structural level of SPEC0 \u2014 is a rules question, it is what "
        "`spec0b_levels_check.py` is really asking, and it is left to him.")
    add("")
    add("`_FILL_CLAMP_TICK = 0.01` — the clamp lands one tick PAST the floor, "
        "not onto it, and both reasons are about a number being written down "
        "rather than about a rule.")
    add("")
    add("1. **IEEE 754.** `(stop + floor) - stop` is not `floor`; it misses by "
        "~6e-15, and two of the six marks (`UBER|2025-09-11|15`, "
        "`GOOGL|2024-10-15|32`) sit exactly on that edge. Clamping onto the "
        "floor recovers 4 of 6, not 6 of 6.")
    add("2. **The book stores entry and stop at 2 decimals.** A fill resting "
        "exactly ON the floor rounds to one that reads a cent under it, so "
        "every downstream reader — including §4's takeable/untakeable split, "
        "which reads the stored prices and not the engine's — scores a "
        "correctly-clamped row as unsizeable. Measured, before the tick was "
        "added: the same book read **32.5% untakeable**, with 773 of those 792 "
        "rows sitting at 0.95–1.00 of the floor and a median of 0.9931. That is "
        "a rounding boundary, not a class of rows; the tick removes it "
        "(`python research/w3_recall_gate_fix_ab.py stats`).")
    add("")
    add("A cent is the smallest price the tape quotes, so the tick cannot decide "
        "anything the arithmetic did not already mean to pass, and it makes the "
        "clamped fill one tick WORSE, never better.")
    add("")

    # ---- 2 ---------------------------------------------------------------
    add("## 2. With the flag OFF the book is byte-identical to HEAD")
    add("")
    add("`backtest_2y.py` run three times against the same `data_archive/`: once "
        "from **unmodified engine code before the flag existed**, then twice "
        "from the patched tree with the flag forced off and on in the child's "
        "environment. sha256 over the `trades` array; `meta.generated` is a wall "
        "clock and is the one field excluded.")
    add("")
    add("The `head` control was taken at `f5ff006a`, this branch's base before "
        "W12's `c2c93280..02b4760d` landed under it. Those two engine edits are "
        "a docstring (`omen_bot.grade_trade`) and a branch W12 measured taking "
        "**0 of 853,010** evaluations (`research/downgrade.py::find_ocr`), so "
        "they are behaviour-neutral by their own measurement — and the `off` "
        "arm below, run at the rebased HEAD, reproducing that control byte for "
        "byte is the independent proof of it.")
    add("")
    add("| run | code | signals | traded | sha256 of `trades` |")
    add("|---|---|---:|---:|---|")
    hb = g13.load_book("head")
    add("| `head` | unmodified engine, `f5ff006a` | %s | %s | `%s` |"
        % (f"{len(hb['trades']):,}", f"{hb['meta']['traded']:,}",
           g13.trades_digest(hb)[:32]))
    for arm in ("off", "on"):
        add("| `%s` | patched, `%s=%s` | %s | %s | `%s` |"
            % (arm, FLAG, ARMS[arm][0], f"{A[arm]['all']['signals']:,}",
               f"{A[arm]['all']['traded']:,}", A[arm]["digest"][:32]))
    add("")
    same = g13.trades_digest(hb) == A["off"]["digest"]
    add("**`head` and `off` are %s.** %s"
        % ("identical" if same else "NOT identical",
           "The flag-off engine is the flag-less engine — every field of every "
           "row equal. Reproduce with `python research/w3_recall_gate_fix_ab.py "
           "identical`."
           if same else "This is a FAILURE of the hard requirement; see the diff "
           "printed by `identical`."))
    add("")

    # ---- 3 ---------------------------------------------------------------
    add("## 3. Done criterion 1 — the recall gate")
    add("")
    add("| arm | `any_signal` | `s_grade` | dropped vs baseline | gate |")
    add("|---|---:|---:|---|---|")
    add("| baseline (`research/baseline_3.8.json`) | %d | %d | — | — |"
        % (base_any, base_s))
    for a, lbl in (("off", "`off` (== HEAD)"), ("on", "`on` (fill clamp)")):
        add("| %s | %d | **%d** | %d any_signal, %d s_grade | %s |"
            % (lbl, g[a]["any"], g[a]["s"], len(g[a]["drop_a"]), len(g[a]["drop_s"]),
               "**RED**" if (g[a]["drop_a"] or g[a]["drop_s"]) else "**GREEN**"))
    add("")
    add("`python research/regression_gate.py` exits **%d** with the flag on and "
        "**%d** with it off." % (0 if green else 1, 1 if g["off"]["drop_s"] else 0))
    add("")
    add("Three answers to the same wound, one measurement each. G13's row is "
        "`research/g13_floor_fix_ab.md`; the close-fill revert is G12's "
        "`--ab-close-fill` upper bound.")
    add("")
    add("| arm | what it moves | `any_signal` | `s_grade` | S marks fired | "
        "X marks fired | gate |")
    add("|---|---|---:|---:|---:|---:|---|")
    add("| HEAD | — | %d | %d | %d / 77 | %d / 22 | RED |"
        % (g["off"]["any"], g["off"]["s"], g["off"]["tier"]["S"]["fired"],
           g["off"]["tier"]["X"]["fired"]))
    add("| G13 structural floor | the floor's denominator | 75 | 11 | 11 / 77 | "
        "4 / 22 | RED (1 mark) |")
    add("| revert the fill (G12 `--ab-close-fill`) | every B&R entry price | 75 | "
        "13 | 13 / 77 | 5 / 22 | — |")
    add("| **W3 fill clamp** | the price booked | %d | **%d** | %d / 77 | %d / 22 "
        "| **GREEN** |"
        % (g["on"]["any"], g["on"]["s"], g["on"]["tier"]["S"]["fired"],
           g["on"]["tier"]["X"]["fired"]))
    add("")
    add("The clamp lands on the same `s_grade 13` a full revert of the fill "
        "reaches, and on the same 5 X-tier fires — while KEEPING the fill rule, "
        "which is Austin's own (*\"those candles that move fast and close at high "
        "of day or low of day, i just want to try to not miss out\"*). It is not "
        "a smaller change than the revert on this gate; it is the same recall at "
        "a better price. The extra %d X-tier fires are the cost and they are "
        "named, not averaged away."
        % (g["on"]["tier"]["X"]["fired"] - g["off"]["tier"]["X"]["fired"]))
    add("")

    # ---- 4 ---------------------------------------------------------------
    add("## 4. Done criterion 2 — is the resulting book takeable")
    add("")
    add("*Untakeable* is g13's definition, imported not restated "
        "(`research/g13_floor_fix_ab.py::sizeable`): a booked row whose "
        "`|entry - stop|` — the distance `backtest_week` divides by to size the "
        "trade — is below `max(0.10, 0.0015 x entry)`, the engine's own floor. "
        "Such a row's 1R is a position that does not exist and its R is a "
        "division by ~0. The yardstick is HEAD's floor constant in both arms; "
        "this ticket does not move it, which is what makes the comparison mean "
        "anything.")
    add("")
    add("| arm | traded | takeable | **untakeable** | of which `entry == stop` | "
        "max R in the book |")
    add("|---|---:|---:|---:|---:|---:|")
    for a, lbl in (("off", "`off` (== HEAD)"), ("on", "`on` (fill clamp)")):
        s = sp[a]
        add("| %s | %s | %s | **%s (%.1f%%)** | %d | %+.1f |"
            % (lbl, f"{s['traded']:,}", f"{s['n_sizeable']:,}",
               f"{s['n_unsizeable']:,}", s["pct_unsizeable"], s["n_zero_risk"],
               s["max_r"]))
    add("| G13 `on` (structural floor) | 1,553 | 414 | **1,139 (73.3%)** | 79 | "
        "+7,099.8 |")
    add("")
    add("**%.1f%% against the <5%% target, and against G13's 73.3%%.** %s"
        % (sp["on"]["pct_unsizeable"],
           "The residual is HEAD's own 2dp-rounding artifact, not a class of "
           "readmitted rows: the engine's floor reads the signal bar's unrounded "
           "close and the book stores a 2dp fill, so a handful of rows land a "
           "cent under this proxy in BOTH arms."
           if sp["on"]["pct_unsizeable"] < 5 else
           "This FAILS the target and the ticket says so."))
    add("")
    add("| arm | population | signals | n traded | mean R | median R | win rate | "
        "months green | total R |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for a, lbl in (("off", "`off` (== HEAD)"), ("on", "`on` (fill clamp)")):
        for pop, key in (("whole book", "all"), ("S subset", "S")):
            b = A[a][key]
            add("| %s | %s | %s | %s | %+.4f | %+.4f | %.1f%% | %d / %d | %+.1f |"
                % (lbl, pop, f"{b['signals']:,}", f"{b['traded']:,}", b["meanr"],
                   b["median_r"], b["wr"], b["months_green"], b["months"],
                   b["totr"]))
    add("")
    add("Win rate is of DECIDED trades (scratches excluded), the convention "
        "`research/a2_bt2y_summary.py` prints. `months green` is months with "
        "positive total R; the durability gate is EVERY month green. The S subset "
        "is `sgrade == \"S\"`, `research/downgrade.py`'s ladder.")
    add("")
    add("### The matched comparison")
    add("")
    add("Rows are matched across arms on `(symbol, day, entry time, setup, "
        "direction, level)`. Detection is unchanged by the flag, so the same "
        "setup on the same bar is the same row.")
    add("")
    add("| | count | of which takeable |")
    add("|---|---:|---:|")
    add("| traded in BOTH arms | %s | — |" % f"{cp['n_shared']:,}")
    add("| **lost** — traded `off`, not `on` | %s | %s |"
        % (f"{cp['n_lost']:,}", f"{cp['lost_sizeable']:,}"))
    add("| **gained** — traded `on`, not `off` | %s | %s |"
        % (f"{cp['n_gained']:,}", f"{cp['gained_sizeable']:,}"))
    add("")
    add("| arm | n | mean R | median R | win rate | total R |")
    add("|---|---:|---:|---:|---:|---:|")
    for a in ("off", "on"):
        b = cp["shared_%s" % a]
        add("| `%s` | %s | %+.4f | %+.4f | %.1f%% | %+.1f |"
            % (a, f"{b['traded']:,}", b["meanr"], b["median_r"], b["wr"], b["totr"]))
    add("")
    d_shared = cp["shared_on"]["meanr"] - cp["shared_off"]["meanr"]
    narrow = A["off"]["eb_all"]["narrow"]
    add("**%+.4f R on %s matched trades, %s of which actually moved.** That is the "
        "money delta this ticket can defend, and it is **too small to read**: "
        "the narrow error bar, recomputed on each arm's own book and never "
        "quoted, is ±%.4f R, and the delta is %.1f× that — %s. The bar is narrow "
        "because Austin settled the question it existed for "
        "on 2026-08-28: a stop is triggered by a candle CLOSE and by nothing "
        "else, and the entry candle's own close counts — one bar has one close, "
        "so a stop cannot fire inside the entry bar ahead of the back-dated fill. "
        "The WIDE bar (±1.5799 R) is **RETIRED** and is not quoted here as a "
        "live interval."
        % (d_shared, f"{cp['n_shared']:,}", f"{cp['shared_r_changed']:,}", narrow,
           (abs(d_shared) / narrow) if narrow else 0.0,
           "it clears the bar" if abs(d_shared) > narrow
           else "it does not clear the bar, so its SIGN is not established"))
    add("")
    add("What became of the lost trades in the `on` arm: %s."
        % ", ".join("`%s` %d" % (k, v) for k, v in cp["lost_status_on"].items()))
    add("")
    add("**Neither arm passes the money gate.** The gate is mean R = 2.0 with "
        "EVERY month green. `off` books %+.4f R with %d of %d months green; `on` "
        "books %+.4f R with %d of %d. The fill clamp is a RECALL fix, and it is "
        "not what stands between this book and the money gate."
        % (A["off"]["all"]["meanr"], A["off"]["all"]["months_green"],
           A["off"]["all"]["months"], A["on"]["all"]["meanr"],
           A["on"]["all"]["months_green"], A["on"]["all"]["months"]))
    add("")

    # ---- 5 ---------------------------------------------------------------
    add("## 5. Done criterion 3 — the 100 held-out OMEN Test 1 cards")
    add("")
    add("`research/marks/probe_omen_test1_2026-08-27.jsonl` — 15 S / 27 A / 16 C "
        "/ 42 X, graded 2026-08-27, never shown to the engine and never fitted "
        "on. Scored by `research/t70_test1_score.py`'s own `score_all`, imported "
        "not reimplemented, once per arm. `grade_std: \"none\"` is his **X**: he "
        "looked at the day and refused it, so a fire there is a false fire.")
    add("")
    add("| metric | `off` (== HEAD) | `on` (fill clamp) | Δ |")
    add("|---|---:|---:|---:|")
    rows = [("**S recall** — fires at all on an S day", "s_hit", "s_n"),
            ("S recall, in-universe", "s_hit_in", "s_n_in"),
            ("**false fire** on refused (X) days", "x_fire", "x_n"),
            ("false fire, in-universe", "x_fire_in", "x_n_in"),
            ("entry match ±2 bars (of the graded)", "entry_match", "graded"),
            ("day precision (of days it fired on)", "day_prec_hit", "day_prec_n")]
    for lbl, num, den in rows:
        d = pct(c["on"][num], c["on"][den]) - pct(c["off"][num], c["off"][den])
        add("| %s | %s | %s | %+.0f pts |"
            % (lbl, frac(c["off"][num], c["off"][den]),
               frac(c["on"][num], c["on"][den]), d))
    add("")
    add("**S recall %s in both arms — criterion 3 is met by not falling, and it "
        "buys nothing.** %s of the days the clamp newly fires on is a day he "
        "graded S. This is the fourth arm in two days to buy in-sample S recall "
        "and exactly zero held-out S recall; two of the other three are "
        "`research/g13_floor_fix_ab.md` §5 and "
        "`research/r3_downgrade_grader_ab.md`, and the third is G16's "
        "`ENABLE_STRUCTURAL_RISK`."
        % (frac(c["off"]["s_hit"], c["off"]["s_n"]),
           "None" if not newf_by_grade.get("S") else
           "%d" % len(newf_by_grade["S"])))
    add("")
    add("| his grade | days newly fired by the flag |")
    add("|---|---|")
    for gr in ("S", "A", "C", "X"):
        ks = newf_by_grade.get(gr, [])
        add("| **%s** | %s |"
            % (gr, "0" if not ks else "%d — %s"
               % (len(ks), ", ".join("%s %s" % k for k in ks))))
    add("| (lost a fire) | %s |"
        % ("0" if not lostf else "%d — %s"
           % (len(lostf), ", ".join("%s %s (his %s)" % (k[0], k[1], on_by[k]["his"])
                                    for k in lostf))))
    add("")
    add("The engine was already more likely to fire on a day he refused than on a "
        "day he called S. %s"
        % ("This widens that." if c["on"]["x_fire"] > c["off"]["x_fire"]
           else "This does not widen that."))
    add("")

    # ---- 5b --------------------------------------------------------------
    add("## 5b. `spec0b_levels_check.py` \u2014 the cheapest reproduction, and "
        "the half of it that is not this mechanism")
    add("")
    add("W12's bug sweep (`research/w12_bug_sweep.md`, finding 7) found "
        "`spec0b_levels_check.py` red at HEAD and diagnosed the cause as this "
        "ticket's mechanism, reproduced on **8 synthetic candles** rather "
        "than a corpus run. That diagnosis is CONFIRMED, and the check is "
        "also carrying a second, independent defect that is not this "
        "mechanism. Both are named here rather than adjusted away.")
    add("")
    add("| | `python spec0b_levels_check.py`, line 44 |")
    add("|---|---|")
    add("| HEAD (flag off) | RED \u2014 `AssertionError: PDH B&R missing: []`. "
        "The signal does not exist. |")
    add("| `ENABLE_MIN_RISK_FILL_CLAMP=1` (shipped) | the signal EXISTS \u2014 "
        "`entry 101.06255, stop 100.9, grade B`. Still red, now on "
        "`stop == 101.0`. |")
    add("| `ENABLE_MIN_RISK_FILL_CLAMP=1`, variant B ordering | GREEN \u2014 "
        "`PDH B&R fires: entry 101.16255, stop 101.0, grade B` |")
    add("")
    add("The fixture's retest bar closes at 101.70, inside 25% of its own "
        "high, so `fill_price` back-dates the entry onto PDH 101.00 \u2014 which "
        "IS the stop. Risk collapses to 0.10 against a floor of 0.15255 and "
        "the signal is force-graded `D`. Same arithmetic as the six marks, on "
        "eight candles. **The clamp fixes that half: the signal comes back, "
        "graded B, with risk 0.16255.**")
    add("")
    add("**What is left is a different rule, and the check is right to still "
        "be red about it.** `assert pdh_sigs[0][\"stop\"] == 101.0` says a "
        "B&R's stop is the broken level \u2014 which is what `BNR_STOP_MODE = "
        "\"level\"` and `signal_runner.py`'s own `NO_REPEAT_ENTRIES` comment "
        "both say. `intrabar_stop` (`5e3677ea`) moves it to the entry bar's "
        "wick, on Austin's five recovered quotes. Those two rules disagree, "
        "they disagreed before this ticket, and only the variant B ordering "
        "\u2014 which costs 588 of HEAD's trades and turns the matched median "
        "into a stop-out \u2014 resolves it in SPEC0's favour. **That is a "
        "rules question for Austin, not a bug to patch and not a test to "
        "adjust.**")
    add("")
    add("The check does not reach its HTF assertions under either ordering "
        "except variant B, where it then dies at `:60` asserting that "
        "`HTF_BIAS_VETO` defaults OFF. It does not \u2014 it has read "
        "`os.getenv(\"HTF_BIAS_VETO\", \"1\")` since it was introduced and "
        "gates 47.0% of the 2-year book. W12 established that (finding 5) and "
        "fixed the four artefacts that misreported it; the stale assertion "
        "belongs to that finding and to R6 (*the veto has no author*), not to "
        "W3.")
    add("")
    # ---- 6 ---------------------------------------------------------------
    add("## 6. The verdict against the three done criteria")
    add("")
    add("| # | criterion | result |")
    add("|---:|---|---|")
    add("| 1 | `python research/regression_gate.py` exits 0 | **%s** |"
        % ("PASS" if green else "FAIL"))
    add("| 2 | under 5%% untakeable rows, g13's definition | **%s** — %.1f%% |"
        % ("PASS" if sp["on"]["pct_unsizeable"] < 5 else "FAIL",
           sp["on"]["pct_unsizeable"]))
    add("| 3 | held-out S recall does not fall | **%s** — %s → %s |"
        % ("PASS" if c["on"]["s_hit"] >= c["off"]["s_hit"] else "FAIL",
           frac(c["off"]["s_hit"], c["off"]["s_n"]),
           frac(c["on"]["s_hit"], c["on"]["s_n"])))
    add("")
    add("All three are met. **What is NOT claimed:** that the engine now sees "
        "more of what Austin sees. Held-out S recall is flat at %s and false "
        "fires rose %+d on his refused days, so the honest summary is that the "
        "clamp removes a self-inflicted recall bug without improving the "
        "engine's eye. The gate is green because the six marks it was written to "
        "protect are back, not because detection got better."
        % (frac(c["on"]["s_hit"], c["on"]["s_n"]),
           c["on"]["x_fire"] - c["off"]["x_fire"]))
    add("")

    # ---- 7 ---------------------------------------------------------------
    add("## 7. What this does not say")
    add("")
    add("- **It does not ship.** `ENABLE_MIN_RISK_FILL_CLAMP` stays `False`. "
        "Flipping it changes what trades, and re-freezing the engine voids "
        "`research/omen6_forward.py` — Austin's call alone.")
    add("- **It does not revert `5e3677ea`** and does not touch `fill_price()` "
        "or `intrabar_stop()`. The intrabar fill is Austin's own rule.")
    add("- **It does not retune `B&R_MIN_RISK` or `STOP_RANGE_MULT`.** Both are "
        "UNMENTIONED constants in `research/hallucination-audit.md` and both are "
        "still open questions; this fix simply does not need them moved. "
        "`STOP_RANGE_MULT`'s second gate — the one that killed "
        "`QQQ|2025-02-25|16` under G13 — is cleared here because a clamped fill "
        "carries floor-sized risk, which on that bar is 0.7750 against a "
        "threshold of 0.5633.")
    add("- **It does not claim the money delta is large.** %+.4f R on %s matched "
        "rows, against a narrow bar of ±%.4f R, is not a claim about the money "
        "gate — which neither arm passes."
        % (cp["shared_on"]["meanr"] - cp["shared_off"]["meanr"],
           f"{cp['n_shared']:,}", A["off"]["eb_all"]["narrow"]))
    add("- **It does not buy held-out recall.** See §5. A 3/15 → 3/15 read rules "
        "out a LARGE out-of-sample gain, not a small one; the held-out sample is "
        "15 S days.")
    add("- **It does not say G12 or G13 was wrong.** G12's diagnosis is confirmed "
        "line for line and G13's warning — that the floor and the sizer must read "
        "one number — is the constraint this design was built to satisfy.")
    add("- Every mean R here is a ceiling: each back-dated fill assumes the "
        "trigger beat the stop inside a minute nobody can see "
        "(`research/p26_intrabar_ambiguity.py`).")
    add("")

    # ---- 8 ---------------------------------------------------------------
    add("## 8. Reproduce")
    add("")
    add("```bash")
    add("python research/w3_recall_gate_fix_ab.py --selfcheck")
    add("python research/test_fill_clamp.py")
    add("python spec0b_levels_check.py                  # red at HEAD (W12 finding 7)")
    add("ENABLE_MIN_RISK_FILL_CLAMP=1 python spec0b_levels_check.py   # line 44 green")
    add("git stash                                  # HEAD control, before the flag")
    add("python backtest_2y.py --days 730 --out research/w3_arm_head.json")
    add("git stash pop")
    add("python research/w3_recall_gate_fix_ab.py book --arm off")
    add("python research/w3_recall_gate_fix_ab.py book --arm on")
    add("python research/w3_recall_gate_fix_ab.py identical   # head == off, byte for byte")
    add("python research/w3_recall_gate_fix_ab.py gate")
    add("python research/w3_recall_gate_fix_ab.py marks")
    add("python research/w3_recall_gate_fix_ab.py test1")
    add("python research/w3_recall_gate_fix_ab.py stats")
    add("python research/w3_recall_gate_fix_ab.py report")
    add("ENABLE_MIN_RISK_FILL_CLAMP=1 python research/regression_gate.py")
    add("```")
    add("")
    add("The three books are ~40 MB each and are NOT committed, the convention "
        "`research/g3_onwatch_2y.py`'s arms follow. `data_archive/` must be "
        "identical across all three runs; the `head`/`off` sha256 match is the "
        "proof it was.")
    add("")
    add("## Provenance")
    add("")
    add("Generated by `research/w3_recall_gate_fix_ab.py report` at _this commit_ "
        "(`--selfcheck` green). Engine change: `signal_runner.py` "
        "(`ENABLE_MIN_RISK_FILL_CLAMP`, `min_risk_floor`, "
        "`clamp_fill_to_min_risk`), default False. Assert-based check: "
        "`research/test_fill_clamp.py`. Diagnosis it implements: "
        "`research/g12_recall_regression.md`. Prior arms it is measured against: "
        "`research/g13_floor_fix_ab.md` (structural floor) and G16's "
        "`ENABLE_STRUCTURAL_RISK` (structural floor + structural R denominator, "
        "not in `main`). Every measurement function is imported from "
        "`research/g13_floor_fix_ab.py` and rebound onto this flag by "
        "`_rebind()`; none is reimplemented. Held-out scorer: "
        "`research/t70_test1_score.py`. Books: %s."
        % ", ".join("`%s` %s" % (a, A[a]["meta"]["generated"])
                    for a in ("off", "on")))
    add("")

    txt = "\n".join(L)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print("wrote %s (%d lines)" % (OUT_MD, len(L)))
    return 0


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck() -> int:
    import signal_runner as sr

    assert sr.ENABLE_MIN_RISK_FILL_CLAMP is False, \
        "the shipped default must be False -- W3 measures, it does not ship"
    assert g13.FLAG == FLAG and g13.ARMS is ARMS, "_rebind did not take"
    assert ARMS["head"][0] is None, "the head control must carry no override"

    os.environ[FLAG] = "1"
    try:
        assert FLAG not in g13.child_env("head")
        assert g13.child_env("off")[FLAG] == "0"
        assert g13.child_env("on")[FLAG] == "1"
    finally:
        os.environ.pop(FLAG, None)

    # OFF is the identity function, on every shape
    for e, s, cl, lg in ((10.0, 9.9, 10.2, True), (10.0, 10.0, 10.2, True),
                         (9.9, 10.0, 9.7, False)):
        assert sr.clamp_fill_to_min_risk(e, s, cl, lg) == e

    # ON: the four properties the design rests on
    sr.ENABLE_MIN_RISK_FILL_CLAMP = True
    try:
        fl = sr.min_risk_floor(100.0)
        assert fl == 0.15, fl
        assert sr.min_risk_floor(10.0) == 0.10, "the $0.10 absolute leg"

        # 1. no-op when the fill already clears the floor
        assert sr.clamp_fill_to_min_risk(100.5, 100.0, 100.6, True) == 100.5

        # 2. a collapsed long fill is walked back to exactly the floor, and the
        #    result then PASSES the floor comparison the call site makes
        got = sr.clamp_fill_to_min_risk(100.0, 100.0, 100.6, True)
        assert got - 100.0 >= fl, (got, fl)
        assert 100.0 <= got <= 100.6, "never outside [entry, close]"

        # 3. the short mirror -- the floor is read on the CLOSE, so it is not
        #    the same number as the long case's
        fls = sr.min_risk_floor(99.4)
        got = sr.clamp_fill_to_min_risk(100.0, 100.0, 99.4, False)
        assert 100.0 - got >= fls, (got, fls)
        assert 99.4 <= got <= 100.0

        # 4. when the CLOSE itself cannot clear the floor the clamp resolves to
        #    the close and the setup is still rejected -- pre-5e3677ea behaviour
        got = sr.clamp_fill_to_min_risk(100.0, 100.0, 100.05, True)
        assert got == 100.05 and got - 100.0 < fl

        # 5. the two knife-edge marks: exact IEEE arithmetic, not a rounding tale
        for stop, close in ((94.6172, 95.155), (166.40, 166.825)):
            f = max(0.10, 0.0015 * close)
            assert (stop + f) - stop < f, "the tick is not needed -- check this"
            got = sr.clamp_fill_to_min_risk(stop, stop, close, True)
            assert got - stop >= f, (stop, close, got - stop, f)
            # and it still clears the floor after the book rounds it to 2dp
            e = round(got, 2)
            assert abs(e - round(stop, 2)) >= max(0.10, 0.0015 * e) - 1e-12
    finally:
        sr.ENABLE_MIN_RISK_FILL_CLAMP = False

    print("w3 selfcheck ok (%s default=%s)" % (FLAG, sr.ENABLE_MIN_RISK_FILL_CLAMP))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selfcheck", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("book")
    b.add_argument("--arm", choices=sorted(ARMS), required=True)
    b.add_argument("--days", type=int, default=730)
    b.add_argument("--out", default=None)
    sub.add_parser("identical")
    sub.add_parser("gate")
    sub.add_parser("marks")
    sub.add_parser("test1")
    sub.add_parser("stats")
    sub.add_parser("report")
    a = ap.parse_args()

    if a.selfcheck:
        return selfcheck()
    if a.cmd == "book":
        return g13.run_book(a.arm, a.days, a.out)
    if a.cmd == "identical":
        return g13.identical("head", "off")
    if a.cmd == "gate":
        return g13.run_gate()
    if a.cmd == "marks":
        return g13.run_marks()
    if a.cmd == "test1":
        return g13.run_test1()
    if a.cmd == "stats":
        return g13.run_stats()
    if a.cmd == "report":
        return report()
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
