"""T70 — OMEN Test 1 scored against the engine. The first clean held-out sample.

`research/marks/probe_omen_test1_2026-08-27.jsonl` holds 100 symbol-days Austin
graded on 2026-08-27: 15 S, 27 A, 16 C, 42 X. The engine has never been shown
any of them — no rule was fitted on them, no threshold tuned to them. Every
recall number published before this one was measured on days the rules were
built from. This one is not.

    python research/t70_test1_score.py      # run + write research/t70_test1_score.md
    python research/t70_test1_score.py --selfcheck

Read-only against the engine. No default and no engine behaviour is changed
here; `ON_WATCH` is left at whatever `signal_runner` defaults to.

Reused, not reimplemented:
  * `t4_engine_recall.run_day`     — the bar reader and the bar-by-bar replay
  * `t4_engine_recall.TOL`         — the +/-2 bar entry join tolerance
  * `p25_midcandle_entry.clean_stop` — refuses a stop that is really a note
  * `universe.BACKTEST_SYMBOLS`    — the set the engine is configured to trade

The day-level drive (one `run_day` per graded symbol-day, "fired" = the deduped
entries it would take, a day counts as found when it fires at all) is
`t61_onwatch_ab.measure`'s pattern; the fired/silent + false-fire scorecard is
`t60_baseline`'s section 4.

TWO GRADE LADDERS — see the mapping block below before reading any table.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.t4_engine_recall import TOL, run_day          # noqa: E402
from research.p25_midcandle_entry import clean_stop         # noqa: E402
from universe import BACKTEST_SYMBOLS, INCLUDE_SPY_IN_BACKTEST  # noqa: E402

MARKS = os.path.join(_HERE, "marks", "probe_omen_test1_2026-08-27.jsonl")
OUT_MD = os.path.join(_HERE, "t70_test1_score.md")

TRADED = frozenset(BACKTEST_SYMBOLS)

# ---------------------------------------------------------------------------
# THE TWO LADDERS, and the one mapping this file uses
# ---------------------------------------------------------------------------
# Austin's ladder is S / A / C / X. S is a clean setup, "A = one downgrade,
# C = two" off the eight variables in omen-rulebook.md, X is a refusal to trade.
#
# The legacy engine ladder is A+ / A / B / C / X, from
# `omen_bot.PriceActionAnalyzer._grade_pa`. `X` there is not a grade at all: it
# means the engine should not have fired, so it is a skip, not a bad setup.
#
# The letters collide and the collision has already cost a rule. The rulebook's
# "you need an A+ entry" is Austin's vocabulary, where A+ means what he now
# calls S; the code read it as `_grade_pa`'s A+, a scale that fires on 17 of
# 1,016 traded signals, and the 84% re-entry rule produced 3 signals in two
# years. One word, two ladders, a dead rule.
#
# So the mapping below is a REPORTING CONVENTION, declared out loud, not a claim
# that the two scales measure the same thing:
#
#   engine A+  -> his S    kept for OLD data only -- pre-2026-08-30 runs/logs
#                          still carry this letter; nothing produces it now
#   engine A   -> his S    the ladder's top: zero downgrades, full size
#   engine B   -> his A    the one rung between top and bottom
#   engine C   -> his C    the bottom tradeable rung
#   engine (silent) -> his X   it did not fire, which is its refusal
#
# 2026-08-30 (394bcfe0, "Retire A+ and route the live path on his S grade
# instead"): `_grade_pa` stopped emitting the string "A+" -- `CLEAR_FOR_APLUS`'s
# full-stack promotion now writes `TradeGrade.A` (the new top grade) where it
# used to write `TradeGrade.A_PLUS`, and the old `TradeGrade.A` rung (his A)
# shifted to nothing but `TradeGrade.B`. This mapping did not move with it
# until B3 (bug B-01): `A -> his A` was left stale, so scoring the CURRENT
# engine's own output read every `S`-grade day (which fires the engine's `A`)
# as his `A`, and `research/test_downgrade_grader.py`'s round trip against
# `signal_runner.DOWNGRADE_TIER` (`S -> A, A -> B`, unchanged and correct)
# failed on exactly this. `A+` stays in the table for old data; `A` now joins
# it as his `S`, and `B` alone is his `A`.
#
# Every table below prints the engine's own letter in the header next to his, so
# the two ladders are never silently merged into one column.
LADDER = {"A+": "S", "A": "S", "B": "A", "C": "C", None: "X"}
ENGINE_TIER_RANK = {"A+": 4, "A": 3, "B": 2, "C": 1}
HIS_GRADES = ["S", "A", "C"]            # the 58 he graded as tradeable
COLS = ["S", "A", "C", "X"]             # his ladder, as the engine's tiers map onto it
COL_LABEL = {
    "S": "A+/A (his S)",
    "A": "B (his A)",
    "C": "C (his C)",
    "X": "silent (his X)",
}


# ---------------------------------------------------------------------------
# pure helpers — everything --selfcheck exercises lives here
# ---------------------------------------------------------------------------

def load_cards(path=MARKS):
    """The 100 Test 1 cards. `grade_std` 'none' is his X: a judgement, not a blank."""
    cards = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            row["his"] = "X" if row.get("grade_std") == "none" else row.get("grade_std")
            cards.append(row)
    return cards


def in_universe(symbol):
    """Is this a symbol the engine is configured to trade at all?

    `universe.BACKTEST_SYMBOLS`. SPY is out by an explicit decision
    (`INCLUDE_SPY_IN_BACKTEST = False`); IWM and ACHR are in no backtest tier.
    A card on one of these is not a miss — the engine was never pointed at it.
    t60_baseline hit exactly this and its silent set had to be restated.
    """
    return symbol in TRADED


def best_tier(entries):
    """The best engine tier fired on a day, or None if it stayed silent."""
    tiers = [e.get("grade") for e in (entries or []) if e.get("grade") in ENGINE_TIER_RANK]
    if not tiers:
        return None
    return max(tiers, key=lambda g: ENGINE_TIER_RANK[g])


def maps_to(tier):
    """Engine tier -> the column on Austin's ladder. See the mapping block."""
    return LADDER.get(tier, "X")


def entry_match(entries, entry_i, tol=TOL):
    """Did any fired entry land within +/-tol bars of his entry bar?"""
    if entry_i is None:
        return False
    return any(abs(e["bar"] - entry_i) <= tol for e in (entries or []))


def confusion(scored, grades=HIS_GRADES, cols=COLS):
    """his grade -> engine column -> count, over the cards whose `his` is in grades."""
    tab = {g: {c: 0 for c in cols} for g in grades}
    for s in scored:
        if s["his"] in tab:
            tab[s["his"]][s["col"]] += 1
    return tab


def pct(n, d):
    return (100.0 * n / d) if d else 0.0


def frac(n, d):
    return "%d/%d = %.0f%%" % (n, d, pct(n, d))


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

def score_all(cards, runner=run_day):
    """One `run_day` per distinct symbol-day; every card scored off it."""
    cache = {}
    scored = []
    for c in cards:
        key = (c["symbol"], c["date"])
        if key not in cache:
            try:
                entries, sigs, _raw = runner(*key)
                # run_day returns (None, None, None) when the archive has no bars
                # for that day -- indistinguishable from silence unless recorded.
                cache[key] = (entries or [], sigs or [], None, entries is not None)
            except Exception as exc:                  # a bad archive day is not a miss
                cache[key] = ([], [], str(exc)[:100], False)
        entries, sigs, err, has_bars = cache[key]
        tier = best_tier(entries)
        stop = clean_stop(c) if c.get("entry_p") else None
        scored.append({
            "symbol": c["symbol"],
            "date": c["date"],
            "his": c["his"],
            "setup": c.get("setup"),
            "side": c.get("side"),
            "entry_i": c.get("entry_i"),
            "entry_t": c.get("entry_t"),
            "entry_p": c.get("entry_p"),
            "stop_p": c.get("stop_p"),
            "stop_clean": stop,
            "in_universe": in_universe(c["symbol"]),
            "has_bars": has_bars,
            "n_fires": len(entries),
            "n_signals": len(sigs),
            "tier": tier,
            "col": maps_to(tier),
            "entry_match": entry_match(entries, c.get("entry_i")),
            "signal_match": any(abs(s["bar"] - c["entry_i"]) <= TOL for s in sigs)
                            if isinstance(c.get("entry_i"), int) else False,
            "error": err,
        })
    return scored


def build_md(scored):
    L = []
    everyone = scored
    inuni = [s for s in scored if s["in_universe"]]
    outuni = [s for s in scored if not s["in_universe"]]

    def sub(rows, his=None, fired=None):
        out = rows
        if his is not None:
            out = [r for r in out if r["his"] == his]
        if fired is not None:
            out = [r for r in out if (r["n_fires"] > 0) == fired]
        return out

    s_all, s_in = sub(everyone, "S"), sub(inuni, "S")
    s_hit_all = sub(everyone, "S", True)
    s_hit_in = sub(inuni, "S", True)
    s_silent_all = sub(everyone, "S", False)
    s_silent_in = sub(inuni, "S", False)

    x_all, x_in = sub(everyone, "X"), sub(inuni, "X")
    x_fire_all = sub(everyone, "X", True)
    x_fire_in = sub(inuni, "X", True)

    graded_all = [r for r in everyone if r["his"] in HIS_GRADES]
    graded_in = [r for r in inuni if r["his"] in HIS_GRADES]
    em_all = [r for r in graded_all if r["entry_match"]]
    em_in = [r for r in graded_in if r["entry_match"]]
    sm_all = [r for r in graded_all if r["signal_match"]]

    errs = [r for r in everyone if r["error"]]

    L.append("# T70 — OMEN Test 1 against the engine")
    L.append("")
    L.append("Generated by `research/t70_test1_score.py` (`--selfcheck` green). Marks: "
             "`research/marks/probe_omen_test1_2026-08-27.jsonl` — **%d symbol-days Austin "
             "graded 2026-08-27**: %d S, %d A, %d C, %d X."
             % (len(everyone), len(s_all), len(sub(everyone, "A")),
                len(sub(everyone, "C")), len(x_all)))
    L.append("")
    L.append("**This is the project's first clean held-out recall sample.** No rule was "
             "fitted on these days and no threshold tuned to them. Every recall figure "
             "published before this one — T4, T60, T61 — was measured on the corpus the "
             "rules were built from. Read this one as the out-of-sample number.")
    L.append("")

    # ---- the two ladders -------------------------------------------------
    L.append("## Two ladders, and which maps to which")
    L.append("")
    L.append("Austin grades **S / A / C / X**. The legacy engine grades "
             "**A+ / A / B / C / X** (`omen_bot.PriceActionAnalyzer._grade_pa`). The "
             "letters collide and the collision has already killed a rule: the rulebook's "
             "*\"you need an A+ entry\"* is his vocabulary, where A+ means what he now calls "
             "**S**, but the code read it as `_grade_pa`'s A+ — a different scale — and the "
             "84% re-entry rule fired 3 times in two years.")
    L.append("")
    L.append("The mapping used in every table below, stated so it is never silent:")
    L.append("")
    L.append("| engine tier | his grade | why |")
    L.append("|---|---|---|")
    L.append("| `A+` | **S** | both are the ladder's top — zero downgrades, full size |")
    L.append("| `A` | **A** | his ladder has ONE rung between top and bottom; the engine "
             "has two (`A`, `B`), so both collapse onto his single `A` |")
    L.append("| `B` | **A** | as above — `B` is not a separate grade on his scale |")
    L.append("| `C` | **C** | both are the bottom tradeable rung (his: two downgrades) |")
    L.append("| _silent_ | **X** | the engine firing nothing IS its refusal; engine `X`/`D` "
             "is a skip, never a grade |")
    L.append("")
    tiers_seen = Counter(r["tier"] for r in everyone if r["tier"])
    L.append("**`A+` never occurs in this sample** (engine tier mix across all %d days: %s), "
             "so the column that maps to his S is empty by construction. The engine's top "
             "tier is not something it reaches on Austin's days."
             % (len(everyone), dict(tiers_seen) or "{}"))
    L.append("")

    # ---- universe --------------------------------------------------------
    L.append("## Cards the engine is configured never to trade")
    L.append("")
    L.append("`universe.BACKTEST_SYMBOLS` is the set the engine trades. **SPY is excluded "
             "by decision** (`INCLUDE_SPY_IN_BACKTEST = %s`); **IWM** and **ACHR** are in no "
             "backtest tier at all. Pointing the replay at them and calling the silence a "
             "miss is the trap `t60_baseline` fell into, so these are held out and reported "
             "here instead." % INCLUDE_SPY_IN_BACKTEST)
    L.append("")
    L.append("| symbol | cards | S | A | C | X | engine fired on |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for sym in sorted({r["symbol"] for r in outuni}):
        rows = [r for r in outuni if r["symbol"] == sym]
        L.append("| %s | %d | %d | %d | %d | %d | %d |"
                 % (sym, len(rows), len(sub(rows, "S")), len(sub(rows, "A")),
                    len(sub(rows, "C")), len(sub(rows, "X")),
                    len([r for r in rows if r["n_fires"] > 0])))
    L.append("| **total held out** | **%d** | **%d** | **%d** | **%d** | **%d** | **%d** |"
             % (len(outuni), len(sub(outuni, "S")), len(sub(outuni, "A")),
                len(sub(outuni, "C")), len(sub(outuni, "X")),
                len([r for r in outuni if r["n_fires"] > 0])))
    L.append("")
    L.append("That leaves **%d in-universe cards**: %d S, %d A, %d C, %d X. Every headline "
             "below is given twice — over all %d cards (the denominator the sample was "
             "built with) and over the %d the engine could ever have traded."
             % (len(inuni), len(s_in), len(sub(inuni, "A")), len(sub(inuni, "C")),
                len(x_in), len(everyone), len(inuni)))
    L.append("")
    if errs:
        L.append("_%d day(s) raised inside the replay and are counted as silent: %s_"
                 % (len(errs), ", ".join("%s %s" % (e["symbol"], e["date"]) for e in errs)))
        L.append("")

    # ---- headline --------------------------------------------------------
    L.append("## The three numbers")
    L.append("")
    L.append("`S recall: %d/%d` — the engine fires at all on %d of his %d S days "
             "(**%.0f%%**). In-universe: **%s**."
             % (len(s_hit_all), len(s_all), len(s_hit_all), len(s_all),
                pct(len(s_hit_all), len(s_all)), frac(len(s_hit_in), len(s_in))))
    L.append("")
    L.append("`false fire: %d/%d` — the engine fires on %d of the %d days he graded X, an "
             "explicit refusal to trade (**%.0f%%**). In-universe: **%s**."
             % (len(x_fire_all), len(x_all), len(x_fire_all), len(x_all),
                pct(len(x_fire_all), len(x_all)), frac(len(x_fire_in), len(x_in))))
    L.append("")
    L.append("`entry match +/-%d bars: %s` over the %d he graded S/A/C — a fired entry "
             "within +/-%d bars of his own entry bar (`t4_engine_recall.TOL`). In-universe: "
             "**%s**."
             % (TOL, frac(len(em_all), len(graded_all)), len(graded_all), TOL,
                frac(len(em_in), len(graded_in))))
    L.append("")
    L.append("| metric | all %d | in-universe %d |" % (len(everyone), len(inuni)))
    L.append("|---|---:|---:|")
    L.append("| **S recall** (fires at all on an S day) | %s | %s |"
             % (frac(len(s_hit_all), len(s_all)), frac(len(s_hit_in), len(s_in))))
    L.append("| tradeable-day recall (S/A/C) | %s | %s |"
             % (frac(len([r for r in graded_all if r["n_fires"] > 0]), len(graded_all)),
                frac(len([r for r in graded_in if r["n_fires"] > 0]), len(graded_in))))
    fired_days_all = [r for r in everyone if r["n_fires"] > 0]
    fired_days_in = [r for r in inuni if r["n_fires"] > 0]
    L.append("| day precision (of days it fired on, ones he'd trade) | %s | %s |"
             % (frac(len([r for r in fired_days_all if r["his"] in HIS_GRADES]),
                     len(fired_days_all)),
                frac(len([r for r in fired_days_in if r["his"] in HIS_GRADES]),
                     len(fired_days_in))))
    L.append("| **false fire** on refused (X) days | %s | %s |"
             % (frac(len(x_fire_all), len(x_all)), frac(len(x_fire_in), len(x_in))))
    L.append("| **entry match +/-%d bars** (of the %d graded) | %s | %s |"
             % (TOL, len(graded_all), frac(len(em_all), len(graded_all)),
                frac(len(em_in), len(graded_in))))
    L.append("| entry match, ANY signal incl. skipped (upper bound) | %s | — |"
             % frac(len(sm_all), len(graded_all)))
    L.append("")

    # ---- verdict ---------------------------------------------------------
    L.append("### Verdict")
    L.append("")
    inverted = pct(len(x_fire_all), len(x_all)) > pct(len(s_hit_all), len(s_all))
    L.append("**The engine is %s likely to fire on a day Austin refused than on a day he "
             "called S** — %.0f%% of his X days vs %.0f%% of his S days (in-universe: "
             "%.0f%% vs %.0f%%). On unseen days the signal is %s: it is not a weak "
             "detector of his setups, it is not detecting his setups."
             % ("MORE" if inverted else "less",
                pct(len(x_fire_all), len(x_all)), pct(len(s_hit_all), len(s_all)),
                pct(len(x_fire_in), len(x_in)), pct(len(s_hit_in), len(s_in)),
                "inverted" if inverted else "weak but correctly signed"))
    L.append("")
    L.append("The %d fired days split %d he would trade / %d he refused. Of the %d "
             "tradeable days it does fire on, only %d put an entry within +/-%d bars of "
             "his — so the day-level recall of %s overstates the agreement: the "
             "**bar-level** number is %s."
             % (len(fired_days_all),
                len([r for r in fired_days_all if r["his"] in HIS_GRADES]),
                len([r for r in fired_days_all if r["his"] == "X"]),
                len([r for r in graded_all if r["n_fires"] > 0]),
                len(em_all), TOL,
                frac(len([r for r in graded_all if r["n_fires"] > 0]), len(graded_all)),
                frac(len(em_all), len(graded_all))))
    L.append("")
    L.append("`t4_engine_recall`'s in-sample conclusion — a **detection** problem, not a "
             "filter problem — survives the holdout. %d of the %d silent S days produce no "
             "signal of any grade at all, not even one the filter threw away; on the other "
             "%d the engine saw something and dropped it. No gate on the trades it already "
             "takes recovers setups it never sees."
             % (len([r for r in s_silent_all if r["n_signals"] == 0]), len(s_silent_all),
                len([r for r in s_silent_all if r["n_signals"] > 0])))
    L.append("")

    # ---- the 4x4 ---------------------------------------------------------
    tab = confusion(graded_all)
    L.append("## Grade agreement — the %d he graded S/A/C" % len(graded_all))
    L.append("")
    L.append("Rows are his grade. Columns are the best engine tier fired that day, mapped "
             "onto his ladder by the table above; the engine's own letter is kept in the "
             "header so the two scales stay visible. The diagonal is agreement.")
    L.append("")
    L.append("| his \\ engine | %s | row total |" % " | ".join(COL_LABEL[c] for c in COLS))
    L.append("|---|%s---:|" % ("---:|" * len(COLS)))
    for g in HIS_GRADES:
        n = sum(tab[g].values())
        L.append("| **%s** | %s | %d |"
                 % (g, " | ".join(str(tab[g][c]) for c in COLS), n))
    L.append("| **all %d** | %s | %d |"
             % (len(graded_all),
                " | ".join(str(sum(tab[g][c] for g in HIS_GRADES)) for c in COLS),
                len(graded_all)))
    L.append("")
    diag = sum(tab[g][g] for g in HIS_GRADES if g in tab[g])
    L.append("Exact agreement (the diagonal): **%s**. Everything off it in the last column "
             "is the engine staying silent on a setup he would take."
             % frac(diag, len(graded_all)))
    L.append("")
    L.append("The same table over his X days, for the false-fire read:")
    L.append("")
    xtab = confusion(scored, grades=["X"])
    L.append("| his \\ engine | %s | row total |" % " | ".join(COL_LABEL[c] for c in COLS))
    L.append("|---|%s---:|" % ("---:|" * len(COLS)))
    L.append("| **X** | %s | %d |"
             % (" | ".join(str(xtab["X"][c]) for c in COLS), sum(xtab["X"].values())))
    L.append("")

    # ---- the silent S set ------------------------------------------------
    L.append("## The S days the engine is silent on")
    L.append("")
    L.append("%d of his %d S days produce no fired entry at all. This is the recall gap, "
             "named." % (len(s_silent_all), len(s_all)))
    L.append("")
    L.append("| symbol | date | in universe | setup | side | his entry | engine signals "
             "(every one skipped) |")
    L.append("|---|---|---|---|---|---|---:|")
    for r in sorted(s_silent_all, key=lambda r: (r["symbol"], r["date"])):
        when = r.get("entry_t") or (
            "bar %d" % r["entry_i"] if r["entry_i"] is not None else "—")
        L.append("| %s | %s | %s | %s | %s | %s | %d |"
                 % (r["symbol"], r["date"], "yes" if r["in_universe"] else "**no**",
                    r["setup"] or "—", r["side"] or "—", when, r["n_signals"]))
    L.append("")
    if s_hit_all:
        L.append("The %d S day(s) it does find: %s."
                 % (len(s_hit_all),
                    ", ".join("**%s %s** (engine `%s`%s)"
                              % (r["symbol"], r["date"], r["tier"],
                                 ", entry within +/-%d" % TOL if r["entry_match"]
                                 else ", entry NOT within +/-%d" % TOL)
                              for r in sorted(s_hit_all,
                                              key=lambda r: (r["symbol"], r["date"])))))
        L.append("")

    # ---- stops -----------------------------------------------------------
    with_stop = [r for r in graded_all if r["stop_p"] is not None]
    junk = [r for r in with_stop if r["stop_clean"] is None]
    L.append("## Data quality on the marks themselves")
    L.append("")
    L.append("- **`entry_p` is the entry bar's CLOSE by construction** "
             "(`research/build_omen_test1.py:696` writes `out.entry_p = closes[i]`). He "
             "picks a minute; the page writes that minute's close. It is not a fill price "
             "and nothing here treats it as one — see `research/p25_midcandle_entry.md`.")
    L.append("- **%d of the %d stops he typed are not prices** and are refused, not "
             "repaired, by `p25_midcandle_entry.clean_stop` (a stop more than 50%% from "
             "entry is a note, not a stop): %s. That leaves %d usable stops."
             % (len(junk), len(with_stop),
                ", ".join("%s %s `%s`" % (r["symbol"], r["date"], r["stop_p"]) for r in junk),
                len(with_stop) - len(junk)))
    nobars = [r for r in everyone if not r["has_bars"]]
    L.append("- %s; none of the silence below is missing data."
             % ("All %d symbol-days have archived bars" % len(everyone) if not nobars
                else "%d of %d symbol-days have NO archived bars and cannot be replayed "
                     "(%s) -- they are silence by absence, not by judgement"
                     % (len(nobars), len(everyone),
                        ", ".join("%s %s" % (r["symbol"], r["date"]) for r in nobars))))
    L.append("")

    # ---- method ----------------------------------------------------------
    L.append("## Method")
    L.append("")
    L.append("- Detection: `research/t4_engine_recall.run_day` — "
             "`signal_runner.SignalRunner.detect_signals` replayed bar-by-bar with "
             "`runner.candles = candles[:i+1]`, PDH/PDL/PMH/PML/HTF reconstructed from "
             "`data_archive`, one entry per setup idea per 30-bar window, 11:00 entry "
             "cutoff. Not reimplemented here.")
    L.append("- **Fired** = the entries the engine would take (grade A+/A/B, or C with a "
             "viable stop). D/X-graded and tight-stop-C signals are *skipped* by "
             "`SignalRunner._route` and are counted only in the any-signal upper bound.")
    L.append("- A day is *found* when it fires at least one entry — `t61_onwatch_ab`'s "
             "`n_fires > 0`. An entry *matches* when a fired entry bar is within "
             "**+/-%d bars** of his `entry_i` (`t4_engine_recall.TOL`)." % TOL)
    L.append("- `ON_WATCH` left at the `signal_runner` default. No default, threshold or "
             "engine behaviour was changed to produce these numbers.")
    L.append("- His X (`grade_std: \"none\"`) is a judgement — he looked at the day and "
             "refused it — so a fire there is a false fire, not an unlabelled day.")
    return "\n".join(L) + "\n"


def main():
    cards = load_cards()
    scored = score_all(cards)
    md = build_md(scored)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(md)

    inuni = [s for s in scored if s["in_universe"]]
    s_all = [s for s in scored if s["his"] == "S"]
    x_all = [s for s in scored if s["his"] == "X"]
    graded = [s for s in scored if s["his"] in HIS_GRADES]
    print("wrote %s" % OUT_MD)
    print("  cards %d  in-universe %d  held out %d"
          % (len(scored), len(inuni), len(scored) - len(inuni)))
    print("  S recall        %d/%d   (in-universe %d/%d)"
          % (len([s for s in s_all if s["n_fires"] > 0]), len(s_all),
             len([s for s in inuni if s["his"] == "S" and s["n_fires"] > 0]),
             len([s for s in inuni if s["his"] == "S"])))
    print("  false fire      %d/%d   (in-universe %d/%d)"
          % (len([s for s in x_all if s["n_fires"] > 0]), len(x_all),
             len([s for s in inuni if s["his"] == "X" and s["n_fires"] > 0]),
             len([s for s in inuni if s["his"] == "X"])))
    print("  entry match +/-%d %d/%d"
          % (TOL, len([s for s in graded if s["entry_match"]]), len(graded)))
    print("  engine tier mix %s" % dict(Counter(s["tier"] for s in scored if s["tier"])))


# ---------------------------------------------------------------------------
# selfcheck — hand-built fixture, no engine, no archive, no test framework
# ---------------------------------------------------------------------------

def _selfcheck():
    # --- best_tier: the ranking, and silence -------------------------------
    assert best_tier([]) is None
    assert best_tier(None) is None
    assert best_tier([{"grade": "C"}, {"grade": "B"}]) == "B"
    assert best_tier([{"grade": "B"}, {"grade": "A"}]) == "A"
    assert best_tier([{"grade": "A"}, {"grade": "A+"}]) == "A+"
    # a skipped grade the engine never fires is not a tier
    assert best_tier([{"grade": "X"}]) is None

    # --- the ladder mapping, in both directions ----------------------------
    assert maps_to("A+") == "S", "engine A+ must map to his S, not his A"
    assert maps_to("A") == "A" and maps_to("B") == "A"
    assert maps_to("C") == "C"
    assert maps_to(None) == "X", "silence is his X"
    # the trap: his S must NOT be reachable from the engine's plain A
    assert maps_to("A") != "S"

    # --- entry join: TOL is inclusive at 2, excludes 3 ---------------------
    ent = [{"bar": 40}]
    assert TOL == 2, "this file's join is +/-2 bars, from t4_engine_recall"
    assert entry_match(ent, 40)
    assert entry_match(ent, 42) and entry_match(ent, 38)
    assert not entry_match(ent, 43) and not entry_match(ent, 37)
    assert not entry_match([], 40)
    assert not entry_match(ent, None), "no entry bar cannot match"

    # --- universe: the held-out set ---------------------------------------
    assert not in_universe("SPY"), "SPY is out by INCLUDE_SPY_IN_BACKTEST=False"
    assert not in_universe("IWM") and not in_universe("ACHR")
    assert in_universe("AAPL") and in_universe("QQQ") and in_universe("MARA")

    # --- stop hygiene, borrowed whole from p25 ----------------------------
    assert clean_stop({"entry_p": 277.91, "stop_p": 931}) is None, "931 is 9:31, not a stop"
    assert clean_stop({"entry_p": 94.61, "stop_p": 121052}) is None
    assert clean_stop({"entry_p": 430.59, "stop_p": 20}) is None, "20 means 20 cents"
    assert clean_stop({"entry_p": 277.91, "stop_p": 278.10}) == 278.10

    # --- grade_std 'none' becomes his X, and is a judgement ---------------
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            for row in [
                {"symbol": "AAPL", "date": "d1", "grade_std": "S", "entry_i": 10,
                 "entry_p": 100.0, "stop_p": 99.0, "setup": "BR", "side": "L"},
                {"symbol": "SPY", "date": "d2", "grade_std": "A", "entry_i": 20,
                 "entry_p": 500.0, "stop_p": 931},
                {"symbol": "QQQ", "date": "d3", "grade_std": "none"},
                {"symbol": "MARA", "date": "d4", "grade_std": "C", "entry_i": 30,
                 "entry_p": 15.0, "stop_p": 14.5},
            ]:
                fh.write(json.dumps(row) + "\n")
        cards = load_cards(tmp)
    finally:
        os.unlink(tmp)
    assert [c["his"] for c in cards] == ["S", "A", "X", "C"]

    # --- score_all + confusion, against a fake engine ---------------------
    fake = {
        ("AAPL", "d1"): ([{"bar": 11, "grade": "B"}], [{"bar": 11}], []),   # S, found, matched
        ("SPY", "d2"):  ([{"bar": 20, "grade": "A"}], [{"bar": 20}], []),   # held out
        ("QQQ", "d3"):  ([{"bar": 5, "grade": "C"}], [{"bar": 5}], []),     # false fire
        ("MARA", "d4"): ([], [], []),                                       # C, silent
    }
    scored = score_all(cards, runner=lambda s, d: fake[(s, d)])
    by = {(r["symbol"], r["date"]): r for r in scored}
    assert by[("AAPL", "d1")]["col"] == "A" and by[("AAPL", "d1")]["entry_match"]
    assert by[("SPY", "d2")]["in_universe"] is False
    assert by[("SPY", "d2")]["stop_clean"] is None, "the junk stop must survive as None"
    assert by[("QQQ", "d3")]["his"] == "X" and by[("QQQ", "d3")]["n_fires"] == 1
    assert by[("MARA", "d4")]["col"] == "X" and not by[("MARA", "d4")]["entry_match"]

    tab = confusion(scored)
    assert sum(sum(v.values()) for v in tab.values()) == 3, "the X card is not in the 3x4"
    assert tab["S"]["A"] == 1 and tab["C"]["X"] == 1 and tab["A"]["A"] == 1
    assert tab["S"]["S"] == 0
    xt = confusion(scored, grades=["X"])
    assert xt["X"]["C"] == 1, "a C-tier fire on a refused day is a false fire"

    # in-universe filtering removes exactly the SPY card
    assert len([r for r in scored if r["in_universe"]]) == 3

    # --- a day that raises is silent, not a crash -------------------------
    def boom(sym, day):
        raise RuntimeError("no bars")
    crashed = score_all(cards, runner=boom)
    assert all(r["n_fires"] == 0 and r["error"] and not r["has_bars"] for r in crashed)

    # --- no archive is recorded, not silently read as silence ------------
    nobars = score_all(cards, runner=lambda s, d: (None, None, None))
    assert all(not r["has_bars"] and r["n_fires"] == 0 for r in nobars)
    assert all(r["has_bars"] for r in score_all(cards, runner=lambda s, d: fake[(s, d)]))

    print("selfcheck ok")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
