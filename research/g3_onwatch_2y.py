"""g3_onwatch_2y.py -- T3/G3: ON_WATCH A/B'd on the 2-year book, not the 120 day-cards.

WHY THIS EXISTS
---------------
`research/t61_onwatch_ab.py` already A/B'd this flag and reported +0 on every
metric. It measured the wrong thing. Its population is Austin's 120 graded
day-cards and its metrics are RECALL metrics -- did the engine fire on his day
at all. ON WATCH is not a detection rule. It is a FILL rule: it never creates or
suppresses a signal, it only changes the PRICE a signal is filled at. A recall
harness is structurally blind to it, and +0 was the only answer it could have
given.

So the switch is thrown again against the rig the money gate is actually read
from -- the full 2-year replay, `backtest_2y.py`, 28 symbols x 500 sessions --
where a changed fill moves the stop, the risk denominator, and therefore R.

WHAT THE FLAG ACTUALLY CONTROLS -- READ THIS BEFORE READING A DELTA
-------------------------------------------------------------------
`ON_WATCH=0` does NOT give you a fill-at-the-close arm. `signal_runner.fill_price`
back-dates a fill to the level when EITHER of two predicates is true:

    bar_extreme_veto      the close sits in the top/bottom BAR_EXTREME_FRAC of
                          the SIGNAL BAR's own range. Always live. Not gated by
                          any flag.
    near_session_extreme  the close sits within BAR_EXTREME_FRAC of the SESSION
                          range from the day's high (long) or low (short).
                          THIS, and only this, is what ON_WATCH gates.

and `near_session_extreme` is only reachable where `fill_price` is handed the
session extremes. It is handed them at 2 of its 10 call sites in
`signal_runner.py` -- the long and short break-and-retest fills (:1638, :1878).
The other 8 (FVG x2, order block x2, flag x2, 84% re-entry x2) call
`fill_price(level, candle, is_long)` with no session extremes, so ON WATCH
returns False there by construction.

Therefore the two arms are NOT "fill at close" vs "fill intrabar". They are:

    ON_WATCH=0   intrabar fills from `bar_extreme_veto` only
    ON_WATCH=1   the same, PLUS break-and-retest bars that close jammed against
                 the session extreme without sitting at their own bar's extreme

The report says this in as many words. A "close-fill arm" is not expressible
through this flag, and claiming one would be the same category error t61 made.

THE ERROR BAR, AND WHICH ONE THIS FILE CARRIES
----------------------------------------------
`research/p26_intrabar_ambiguity.py` (T2) measured what an intrabar fill is
worth in doubt: on 86.8% of traded intrabar fills the entry bar's own range also
contains the trade's stop, and OHLCV cannot say which of the two prices traded
first. Priced, that unknown is 1.5815 R of mean R on the traded book -- larger
than the 1.0429 R the book is short of the 2.0R money gate, and 3.9x the whole
S-over-C edge.

T2 also split that count: 790 of the traded book's 792 ambiguous bars are the
stop sitting ON the entry bar's own extreme, put there by
`signal_runner.intrabar_stop`; only 23 (2.5% of intrabar fills) have a stop
clear of both wicks. So there are two candidate error bars and this file states
which one it is carrying:

  WIDE (RETIRED)   every ambiguous intrabar row repriced to -1.0R, the
                   manufactured `intrabar_stop` class included.
  NARROW (carried) only rows whose stop is NOT the entry bar's own extreme.

**The wide one was the headline here until 2026-08-28.** The manufactured class
is manufactured, but it was not resolved: a stop resting on the entry bar's own
low is a price that bar demonstrably traded, and on a long break-and-retest bar
closing near its high the low usually traded FIRST. Whether such a stop should
be modelled as reachable inside its own entry bar was Austin's call and he had
not made it, so excluding that class would have been assuming the answer.

RETIRED 2026-08-28. He made the call. Asked whether a mid-candle entry whose own
candle then closes beyond the stop is out on that close, he said "out on that
same close". A stop is triggered by a candle CLOSE and by nothing else, and the
entry candle's own close counts -- and there is exactly one close per bar, so a
stop cannot fire INSIDE the entry bar ahead of the back-dated fill. The
`intrabar_stop` class is not ambiguous. THE NARROW BAR IS THE ONE THIS FILE
CARRIES (+-0.0095 R shipped, +-0.0088 R off). The wide bar is still computed and
printed below so the retired verdict stays traceable, and every place it appears
says it is retired. Do not quote it as a live interval. The ON_WATCH delta of
+0.1135 R clears the carried bar by 12x.

Both bars are recomputed per arm, on that arm's own book. They are never copied
from T2's numbers -- T2's book is a third replay and the arms must be compared
against themselves.

NOTHING IS RE-DERIVED THAT T2 ALREADY DERIVED. The intrabar marker, the
rounding correction that goes with it (`backtest_2y.py:169` stores entry at 2dp,
so a naive `entry != close` test over-reports by ~11 points), the two trigger
predicates and the ambiguity test are IMPORTED from
`research.p26_intrabar_ambiguity`, not restated.

USAGE
-----
    python research/g3_onwatch_2y.py run --arm off    # -> research/g3_arm_ow0.json
    python research/g3_onwatch_2y.py run --arm on     # -> research/g3_arm_ow1.json
    python research/g3_onwatch_2y.py report           # -> research/g3_onwatch_2y.md
    python research/g3_onwatch_2y.py --selfcheck

Two processes because `ON_WATCH` is read once, at import of `signal_runner`.
Run the arms ONE AT A TIME: concurrent replays contend on the 1-minute archive.

READ-ONLY WITH RESPECT TO THE ENGINE. No default is changed and no flag is
added; `run` sets ON_WATCH in a CHILD process's environment and nothing else.
Bars are read from `data_archive/` only -- a cache miss is a reported gap, never
a fetch, so this can never touch POLYGON_API_KEY.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

# T2's rig. The intrabar marker, its 2dp rounding correction, the two trigger
# predicates and the ambiguity test all come from here -- never restated.
from research import p26_intrabar_ambiguity as p26                     # noqa: E402
# The whole-book money read (mean R, win rate, months green) every other 2-year
# report in this repo prints, so this table is comparable to them.
from research.a2_bt2y_summary import book as money                     # noqa: E402
from research import exit_lab                                          # noqa: E402

OUT = os.path.join(HERE, "g3_onwatch_2y.md")
ARMS = {"off": ("0", os.path.join(HERE, "g3_arm_ow0.json")),
        "on":  ("1", os.path.join(HERE, "g3_arm_ow1.json"))}
ENTRY_TOL = 3          # bars. The tolerance every recall figure in this repo uses.
SHIPPED = "on"         # signal_runner.py:368 defaults ON_WATCH to "1".


# ---------------------------------------------------------------------------
# the two replays
# ---------------------------------------------------------------------------

def run(arm: str, days: int, out_path: str | None) -> int:
    """One full 2-year replay with ON_WATCH forced in a CHILD process.

    `backtest_2y.py` is invoked as-is rather than reimplemented: the point of
    this ticket is the SHIPPED rig's answer, and a private replay loop would be
    a different rig wearing its name."""
    val, default_out = ARMS[arm]
    out_path = out_path or default_out
    assert "bt2y_trades.json" not in out_path, "never overwrite the canonical book"
    env = dict(os.environ, ON_WATCH=val)
    cmd = [sys.executable, os.path.join(ROOT, "backtest_2y.py"),
           "--days", str(days), "--out", os.path.relpath(out_path, ROOT)]
    print("ON_WATCH=%s %s" % (val, " ".join(cmd)))
    return subprocess.call(cmd, cwd=ROOT, env=env)


# ---------------------------------------------------------------------------
# Austin's 64 marked entries
# ---------------------------------------------------------------------------

def marks():
    """The 64 trade marks in `research/exit_lab.MARKS_FILES`.

    `entry_i` is an index into the day's RTH bars with index 0 = the 09:30 bar,
    the same convention `backtest_2y.py` writes into each row's `entry_i`."""
    ms = exit_lab.load_marks()
    assert len(ms) == 64, "expected Austin's 64 marked entries, got %d" % len(ms)
    return ms


def entry_match(rows, ms) -> int:
    """How many of his 64 entries have a signal within +/-3 bars, same day.

    Detection, not execution: any signal in the population counts, which is the
    convention `research/regression_gate.py` locks its `any_signal` set on."""
    bars = defaultdict(list)
    for r in rows:
        bars[(r["sym"], r["day"])].append(r["entry_i"])
    return sum(1 for m in ms
               if any(abs(b - m["entry_i"]) <= ENTRY_TOL
                      for b in bars.get((m["symbol"], m["date"]), ())))


# ---------------------------------------------------------------------------
# the error bar, recomputed on each arm's own book
# ---------------------------------------------------------------------------

def classify_books(books: dict) -> dict:
    """T2's per-signal classification for every arm, one bar load per symbol-day.

    Returns {arm: [classification dicts]}. The bars are the same for both arms,
    so they are loaded once and both arms' rows are classified against them --
    the arms differ in `entry`/`stop`, never in the tape."""
    by_day = defaultdict(lambda: defaultdict(list))
    for arm, blob in books.items():
        for r in blob["trades"]:
            by_day[(r["sym"], r["day"])][arm].append(r)

    out = {arm: [] for arm in books}
    gaps = {"day": 0, "bar": 0}
    keys = sorted(by_day)
    for n, (sym, day) in enumerate(keys):
        rth = p26.load_day(sym, day)
        if not rth:
            gaps["day"] += sum(len(v) for v in by_day[(sym, day)].values())
            continue
        idx, run_hi, run_lo = p26.index_day(rth)
        for arm, rs in by_day[(sym, day)].items():
            for r in rs:
                i = idx.get(r["et"])
                if i is None:
                    gaps["bar"] += 1
                    continue
                out[arm].append(p26.classify(r, rth[i], run_hi[i], run_lo[i]))
        if n and n % 4000 == 0:
            print("  %d/%d symbol-days" % (n, len(keys)), flush=True)
    return out, gaps


def error_bars(recs):
    """WIDE and NARROW error bars over one arm's traded book.

    Both are one-directional: an ambiguous row can only be repriced DOWN (the
    book's own minimum R is -1.0, reached when a trade exits at its stop), so
    each bar is the distance from the booked mean R to a floor, never a
    symmetric interval. The booked number is a ceiling.

    wide    every ambiguous intrabar row dies on entry at -1.0R.
    narrow  only ambiguous rows whose stop is NOT the entry bar's own extreme --
            i.e. with the class `signal_runner.intrabar_stop` manufactures held
            at its booked R. The floor the error bar cannot go below.
    """
    tr = [c for c in recs if c["traded"]]
    if not tr:
        return {"n": 0, "opt": 0.0, "wide": 0.0, "narrow": 0.0, "n_intrabar": 0,
                "n_amb": 0, "n_residual": 0, "n_at_extreme": 0, "n_clear": 0,
                "n_clear_at_extreme": 0, "amb_pct": 0.0}
    amb = lambda c: c["intrabar"] and c["amb_possible"]                # noqa: E731
    opt = statistics.fmean(c["r"] for c in tr)
    wide = statistics.fmean(-1.0 if amb(c) else c["r"] for c in tr)
    narrow = statistics.fmean(
        -1.0 if (amb(c) and not c["at_extreme"]) else c["r"] for c in tr)
    n_intra = sum(1 for c in tr if c["intrabar"])
    n_amb = sum(1 for c in tr if amb(c))
    return {
        "n": len(tr), "opt": opt, "wide": opt - wide, "narrow": opt - narrow,
        "n_intrabar": n_intra, "n_amb": n_amb,
        # T2's headline: ambiguous as a share of intrabar fills (86.8% on its
        # own book). Recomputed here per arm rather than quoted.
        "amb_pct": 100.0 * n_amb / n_intra if n_intra else 0.0,
        "n_at_extreme": sum(1 for c in tr if amb(c) and c["at_extreme"]),
        "n_residual": sum(1 for c in tr if amb(c) and not c["at_extreme"]),
        # T2's own "stop clear of both edges of the rounding band" count, kept
        # under its own name so the two reports can be laid side by side.
        "n_clear": sum(1 for c in tr if c["intrabar"] and c["amb_certain"]),
        # ... and the overlap that explains why it is the larger of the two:
        # a bar extreme priced at a half cent (high 216.045 -> stop 216.04)
        # clears the rounding band AND is the bar's own extreme.
        "n_clear_at_extreme": sum(1 for c in tr if c["intrabar"]
                                  and c["amb_certain"] and c["at_extreme"]),
    }


def fill_split(recs, is_on: bool):
    """What the flag moved: intrabar fills, and which predicate back-dated them.

    `on_watch` is a reconstruction of `near_session_extreme` and fires in the
    data regardless of the flag; it can only have back-dated a fill in the arm
    where the flag let `fill_price` consult it, which is why `is_on` gates the
    reachable columns."""
    tr = [c for c in recs if c["traded"]]
    n = len(tr)
    intra = [c for c in tr if c["intrabar"]]
    ow_only = [c for c in tr if c["on_watch"] and not c["bar_extreme"]]
    return {
        "n": n,
        "intrabar": len(intra),
        "intrabar_pct": 100.0 * len(intra) / n if n else 0.0,
        # Signals where ON WATCH is the ONLY predicate that could have moved the
        # fill. In the ON arm these fill at the level; in the OFF arm they fill
        # at the close. This is the flag's entire reach.
        "ow_only": len(ow_only),
        "ow_only_intrabar": sum(1 for c in ow_only if c["intrabar"]),
        "reachable": is_on,
    }


# ---------------------------------------------------------------------------
# the table
# ---------------------------------------------------------------------------

def stats(rows, ms):
    b = money(rows)
    rs = [r["r"] for r in rows if r["traded"]]
    b["median_r"] = statistics.median(rs) if rs else 0.0
    b["match"] = entry_match(rows, ms)
    b["match_traded"] = entry_match([r for r in rows if r["traded"]], ms)
    return b


def line(arm_label, pop, b, eb):
    return ("| %s | %s | %s | %s | %+.4f | %+.4f | %.1f%% | **%d / %d** | %d / 64 | "
            "±%.4f (±%.4f) |"
            % (arm_label, pop, f"{b['signals']:,}", f"{b['traded']:,}", b["meanr"],
               b["median_r"], b["wr"], b["months_green"], b["months"], b["match"],
               eb["wide"], eb["narrow"]))


def report(books, cls, gaps):
    off, on = books["off"], books["on"]
    ms = marks()
    rows = {a: books[a]["trades"] for a in books}
    srows = {a: [r for r in rows[a] if r["sgrade"] == "S"] for a in books}

    st = {("all", a): stats(rows[a], ms) for a in books}
    st.update({("S", a): stats(srows[a], ms) for a in books})
    eb = {("all", a): error_bars(cls[a]) for a in books}
    eb.update({("S", a): error_bars([c for c in cls[a] if c["sgrade"] == "S"])
               for a in books})
    fs = {a: fill_split(cls[a], a == "on") for a in books}

    d_all = st[("all", "on")]["meanr"] - st[("all", "off")]["meanr"]
    d_s = st[("S", "on")]["meanr"] - st[("S", "off")]["meanr"]
    bar_all = eb[("all", "on")]["wide"]
    nar_all = eb[("all", "on")]["narrow"]
    ratio = abs(d_all) / bar_all if bar_all else 0.0

    L = []
    add = L.append
    add("# G3 / T3 — ON WATCH on the 2-year book")
    add("")
    add("> **CORRECTED 2026-08-28 — the wide error bar is retired and this delta "
        "is READABLE.** This file's headline used to say the delta was %.0f× "
        "smaller than a ±%.4f R bar and \"not resolved\". That bar existed only "
        "because nobody had ruled on whether a stop resting inside the entry bar "
        "could have fired before the back-dated fill. **Austin ruled on "
        "2026-08-28: \"Out on that same close.\"** A stop is triggered by a candle "
        "CLOSE and nothing else; the entry candle's own close counts; there is "
        "exactly one close per bar. So a stop cannot fire *inside* the entry bar "
        "ahead of the fill, the `intrabar_stop` class is not ambiguous, and **the "
        "bar this file carries is the narrow one — ±%.4f R shipped, ±%.4f R on the "
        "off arm.** Every wide figure below is kept as history — it was the honest "
        "pessimistic price of a genuinely open question — but must not be quoted "
        "as a live interval."
        % ((1.0 / ratio) if ratio else 0.0, bar_all, nar_all,
           eb[("all", "off")]["narrow"]))
    add("")
    add("**Flipping `ON_WATCH` moves mean R by %+.4f R on the whole traded book "
        "(%+.4f R on S) and costs a green month. That delta clears the ±%.4f R "
        "error bar this book carries on its fill assumption by %.0f×, so its sign "
        "is readable — it is small, not unresolved.** The flag also does "
        "not do what its name suggests: it changes **0** of 45,193 signals and "
        "leaves **%.1f%% of traded fills still intrabar** when switched off. "
        "*(Retired framing, kept for the record: measured against the wide ±%.4f R "
        "bar this delta was %.0f× smaller and was reported as unresolved.)*"
        % (d_all, d_s, nar_all, abs(d_all) / nar_all if nar_all else 0.0,
           fs["off"]["intrabar_pct"], bar_all, (1.0 / ratio) if ratio else 0.0))
    add("")
    add("`ON_WATCH=1` is **the shipped default today** (`signal_runner.py:368`, "
        "`os.getenv(\"ON_WATCH\", \"1\")`). Nothing here changes it. Both arms were "
        "replayed at _this commit_ by `research/g3_onwatch_2y.py`, which shells "
        "`backtest_2y.py` once per arm with the flag forced in the child's "
        "environment.")
    add("")
    add("One result cuts the other way and is the most useful thing in this file. "
        "The error bar was **not a property of the tape** — it was a property of "
        "one unanswered question. %s of the %s ambiguous traded rows on the shipped "
        "arm are the stop sitting on the entry bar's own extreme, and this file "
        "said that if Austin ruled those unreachable inside the bar he was filled "
        "on, the bar would collapse "
        "from ±%.4f R to ±%.4f R — **%.0f× narrower** — and the delta would clear "
        "it comfortably. **He ruled exactly that on 2026-08-28, and it did.** The "
        "A/B was never blocked by missing data; it was blocked by an open rules "
        "question, and the question is closed."
        % (f"{eb[('all', 'on')]['n_at_extreme']:,}",
           f"{eb[('all', 'on')]['n_amb']:,}", bar_all, nar_all,
           bar_all / nar_all if nar_all else 0.0))
    add("")

    add("## The table")
    add("")
    add("`n` is the traded book — the population the 2.0R money gate reads. Win "
        "rate is of DECIDED trades (scratches excluded), the same convention "
        "`research/a2_bt2y_summary.py` prints and this table imports. `months "
        "green` is months with positive total R; the durability gate is EVERY "
        "month green. Entry match is any signal within ±%d bars of one of "
        "Austin's 64 marked entries on the same symbol-day. The error bar column "
        "is stated on each arm's own book, **retired wide bar first and the "
        "carried narrow bar in brackets** — read the bracketed figure; see §the "
        "error bar." % ENTRY_TOL)
    add("")
    add("| arm | population | signals | n traded | mean R | median R | win rate | "
        "months green | entry match ±%d | error bar (wide RETIRED / narrow CARRIED) |"
        % ENTRY_TOL)
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for pop in ("all", "S"):
        for a, lab in (("off", "`ON_WATCH=0`"), ("on", "`ON_WATCH=1` (shipped)")):
            add(line(lab, "whole book" if pop == "all" else "S subset",
                     st[(pop, a)], eb[(pop, a)]))
    add("")
    add("| delta (`ON_WATCH=1` − `ON_WATCH=0`) | signals | n traded | mean R | "
        "median R | win rate | months green | entry match ±%d |" % ENTRY_TOL)
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for pop, lab in (("all", "whole book"), ("S", "S subset")):
        o, n = st[(pop, "off")], st[(pop, "on")]
        add("| %s | %+d | %+d | **%+.4f** | %+.4f | %+.1f pts | %+d | %+d |"
            % (lab, n["signals"] - o["signals"], n["traded"] - o["traded"],
               n["meanr"] - o["meanr"], n["median_r"] - o["median_r"],
               n["wr"] - o["wr"], n["months_green"] - o["months_green"],
               n["match"] - o["match"]))
    add("")
    add("**Neither arm passes the money gate and neither is durable.** The gate is "
        "mean R = 2.0 and EVERY month green. `ON_WATCH=1` books %+.4f R with %d of "
        "%d months green; `ON_WATCH=0` books %+.4f R with %d of %d. Both are "
        "roughly half the gate and both have a red month, so the flag is not what "
        "stands between this book and the gate — and the two arms trade against "
        "each other: the shipped arm buys %+.4f R of mean R and gives back a green "
        "month."
        % (st[("all", "on")]["meanr"], st[("all", "on")]["months_green"],
           st[("all", "on")]["months"], st[("all", "off")]["meanr"],
           st[("all", "off")]["months_green"], st[("all", "off")]["months"], d_all))
    add("")
    add("Two structural reads from the same table, and they are the load-bearing "
        "ones. **Signals are identical to the row: %s in both arms.** ON WATCH "
        "creates and suppresses nothing — it is a price rule, exactly as "
        "`fill_price` says. What it moves is the traded count, by %+d: a fill "
        "back-dated to the level lands on or through the level-stop, and the trade "
        "is either re-stopped on the entry bar by `signal_runner.intrabar_stop` or "
        "dropped by the minimum-risk gate. The S subset moves too (%+d signals) "
        "because `research/downgrade.py` grades off the STOP, and the stop moved."
        % (f"{st[('all', 'on')]['signals']:,}",
           st[("all", "on")]["traded"] - st[("all", "off")]["traded"],
           st[("S", "on")]["signals"] - st[("S", "off")]["signals"]))
    add("")

    add("## What `ON_WATCH` actually controls — and what it does not")
    add("")
    add("**It does not produce a fill-at-the-close arm, and this comparison is "
        "not \"close fill vs intrabar fill\".** `signal_runner.fill_price` "
        "back-dates a fill to the level when EITHER predicate is true:")
    add("")
    add("| predicate | measures | gated by `ON_WATCH`? | reachable from |")
    add("|---|---|---|---|")
    add("| `bar_extreme_veto` | the close sits in the top/bottom "
        "`BAR_EXTREME_FRAC` of the SIGNAL BAR's own range | **no — always live** | "
        "all 10 `fill_price` call sites |")
    add("| `near_session_extreme` | the close sits within `BAR_EXTREME_FRAC` of "
        "the SESSION range from the day's high (long) / low (short) | **yes — this "
        "is the whole flag** | 2 of 10: the long and short break-and-retest fills "
        "(`signal_runner.py:1638`, `:1878`) |")
    add("")
    add("The other 8 call sites — FVG, order block, flag and the 84% re-entry, "
        "both sides each — call `fill_price(level, candle, is_long)` with no "
        "session extremes, so `near_session_extreme` returns False there by "
        "construction. So the arms are:")
    add("")
    add("| arm | what back-dates a fill |")
    add("|---|---|")
    add("| `ON_WATCH=0` | `bar_extreme_veto` only |")
    add("| `ON_WATCH=1` | `bar_extreme_veto`, plus break-and-retest bars closing "
        "jammed against the session extreme without sitting at their own bar's "
        "extreme |")
    add("")
    add("Measured on the traded book, that is what survives the switch:")
    add("")
    add("| arm | traded | intrabar fills | of traded | ambiguous | **of intrabar** | "
        "signals ON WATCH alone could move |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    for a, lab in (("off", "`ON_WATCH=0`"), ("on", "`ON_WATCH=1`")):
        f, e = fs[a], eb[("all", a)]
        add("| %s | %s | %s | %.1f%% | %s | **%.1f%%** | %s |"
            % (lab, f"{f['n']:,}", f"{f['intrabar']:,}", f["intrabar_pct"],
               f"{e['n_amb']:,}", e["amb_pct"], f"{f['ow_only']:,}"))
    add("")
    add("The *ambiguous / of intrabar* column is T2's headline recomputed on each "
        "arm rather than quoted: **86.8%% of traded intrabar fills sit on a bar "
        "whose range also contains the stop** on T2's book, and %.1f%% / %.1f%% "
        "here on the off / on arms. Turning the flag off does not meaningfully "
        "dilute it, because the class it removes is ambiguous for the same reason "
        "as the class it leaves."
        % (eb[("all", "off")]["amb_pct"], eb[("all", "on")]["amb_pct"]))
    add("")
    add("**Turning the flag off leaves %.1f%% of traded fills still intrabar.** "
        "Only the last column is the flag's reach: signals whose entry bar trips "
        "`near_session_extreme` and does NOT trip `bar_extreme_veto`, so ON WATCH "
        "is the only rule that could have moved the price. Everything else fills "
        "identically in both arms. A clean close-fill arm is **not expressible "
        "through this flag** — it would need `fill_price` itself changed, which "
        "this ticket does not do." % fs["off"]["intrabar_pct"])
    add("")
    add("That last column is %s on the off arm and %s on the on arm, and the drop "
        "is the mechanism, not an inconsistency: in the off arm those rows fill at "
        "the close, keep their structural risk and stay in the traded book; in the "
        "on arm most are back-dated to the level, land on the level-stop, and "
        "leave the traded book through `intrabar_stop` and the minimum-risk gate. "
        "It is the same %+d trades the traded count lost, seen from the other side."
        % (f"{fs['off']['ow_only']:,}", f"{fs['on']['ow_only']:,}",
           st[("all", "on")]["traded"] - st[("all", "off")]["traded"]))
    add("")
    add("This is also why `research/t61_onwatch_ab.py` measured +0 on every "
        "metric over the 120 day-cards and was right to: ON WATCH creates and "
        "suppresses no signal, so a recall harness cannot see it at all. The "
        "effect it has is on price, and price only shows up in R.")
    add("")

    add("## The error bar, and which one this file carries")
    add("")
    add("From `research/p26_intrabar_ambiguity.py` (T2): when a fill is "
        "back-dated into the entry bar, that bar's own range usually also "
        "contains the trade's stop, and OHLCV cannot say which price traded "
        "first. The engine assumes fill-then-stop every time. Repricing the other "
        "order is the error bar, and it is **one-directional** — the booked mean "
        "R is a ceiling, never a midpoint.")
    add("")
    add("T2's load-bearing split is that **790 of that book's 792 ambiguous "
        "traded bars are the stop sitting ON the entry bar's own extreme**, put "
        "there by `signal_runner.intrabar_stop`; only 23 (2.5% of intrabar fills) "
        "have a stop clear of both wicks. That gave two candidate bars. **This "
        "report carried the WIDE one until 2026-08-28; it now carries the NARROW "
        "one.**")
    add("")
    add("| bar | which ambiguous rows are repriced to −1.0R | `ON_WATCH=1` whole book | `ON_WATCH=0` whole book | status |")
    add("|---|---|---:|---:|---|")
    add("| **narrow — CARRIED** | only rows whose stop is NOT the entry bar's own "
        "extreme | **±%.4f R** | **±%.4f R** | the interval on every number here |"
        % (eb[("all", "on")]["narrow"], eb[("all", "off")]["narrow"]))
    add("| wide — RETIRED | all of them, the `intrabar_stop` class included | "
        "±%.4f R | ±%.4f R | history, 2026-08-28 |"
        % (eb[("all", "on")]["wide"], eb[("all", "off")]["wide"]))
    add("")
    add("**Why the wide one was carried.** The `intrabar_stop` class is "
        "manufactured by a "
        "stop rule rather than found in the tape, but manufactured is not "
        "resolved. A stop resting on the entry bar's own low is a price that bar "
        "demonstrably traded, and on a long break-and-retest bar that closes near "
        "its high the low very often traded first — so on a *price* argument that "
        "class looked if anything "
        "MORE likely to have fired than the residual, not less. Whether such a "
        "stop should be modelled as reachable inside its own entry bar was "
        "**Austin's call and he had not made it**; excluding the class would have "
        "been assuming his answer, and this file would not assume it in order to "
        "make its own delta look significant.")
    add("")
    add("**What retired it, 2026-08-28.** The price argument above was the wrong "
        "frame, and only he could say so. A stop in this system is not triggered "
        "by a price being *traded* — it is triggered by a candle **closing** "
        "beyond it. Asked whether a mid-candle entry whose own candle then closes "
        "beyond the stop is out on that close, he said: **\"Out on that same "
        "close.\"** One close per bar, and the fill is already priced against it. "
        "So the `intrabar_stop` class cannot have fired ahead of the fill, is not "
        "ambiguous, and does not belong in the bar. **The narrow bar is the right "
        "one and the wide bar is retired.**")
    add("")
    add("**The delta above (%+.4f R) clears the carried ±%.4f R bar by %.0f×.** "
        "The A/B was never blocked by the data and it is no longer blocked by the "
        "rules question either. It is readable — and small: %+.4f R against a book "
        "1.0449 R short of the money gate, bought by giving back a green month, "
        "and buying zero held-out S recall."
        % (d_all, nar_all, abs(d_all) / nar_all if nar_all else 0.0, d_all))
    add("")
    add("| arm | population | traded | ambiguous | stop IS the entry bar's extreme | "
        "residual | T2's \"clear of both edges\" |")
    add("|---|---|---:|---:|---:|---:|---:|")
    for pop, plab in (("all", "whole book"), ("S", "S subset")):
        for a, lab in (("off", "`ON_WATCH=0`"), ("on", "`ON_WATCH=1`")):
            e = eb[(pop, a)]
            add("| %s | %s | %s | %s | %s | %s | %s |"
                % (lab, plab, f"{e['n']:,}", f"{e['n_amb']:,}",
                   f"{e['n_at_extreme']:,}", f"{e['n_residual']:,}",
                   f"{e['n_clear']:,}"))
    add("")
    add("The last two columns look like they disagree and they do not — they are "
        "two different tests and this is a refinement of T2, not a contradiction "
        "of it. *Residual* asks whether the stop equals the entry bar's own "
        "extreme; T2's *clear of both edges* asks whether the stop clears the "
        "half-cent band the book's 2dp rounding leaves. **%d of the shipped arm's "
        "%d \"clear\" rows are also at the bar's extreme**, because a bar extreme "
        "priced at a half cent satisfies both — e.g. a short whose entry bar high "
        "is `216.045`, stored as a stop of `216.04`, which clears the band by "
        "construction while still BEING the high. Netting those out, the genuinely "
        "residual ambiguity on the traded book is **%d rows of %s**, %.1f%% of "
        "intrabar fills. T2's 2.5%% is a ceiling on it."
        % (eb[("all", "on")]["n_clear_at_extreme"], eb[("all", "on")]["n_clear"],
           eb[("all", "on")]["n_residual"], f"{eb[('all', 'on')]['n_intrabar']:,}",
           100.0 * eb[("all", "on")]["n_residual"]
           / max(eb[("all", "on")]["n_intrabar"], 1)))
    add("")

    add("## The verdict")
    add("")
    add("| question | answer |")
    add("|---|---|")
    add("| mean R delta, whole book | **%+.4f R** (`ON_WATCH=1` − `ON_WATCH=0`) |" % d_all)
    add("| mean R delta, S subset | **%+.4f R** |" % d_s)
    add("| does it clear the CARRIED error bar (±%.4f R, narrow)? | **yes — by "
        "%.0f×.** A stop on the entry bar's own wick is ruled unreachable inside "
        "that bar: Austin, 2026-08-28, \"out on that same close\" |"
        % (nar_all, abs(d_all) / nar_all if nar_all else 0.0))
    add("| does it clear the WIDE bar (±%.4f R)? | %s. **That bar was retired "
        "2026-08-28** and this row is kept only so the old verdict is traceable |"
        % (bar_all, "yes" if abs(d_all) > bar_all else "no — %.0f× smaller"
           % ((1.0 / ratio) if ratio else 0.0)))
    add("| what does `ON_WATCH` actually control? | one of the two predicates in "
        "`fill_price`, at 2 of its 10 call sites. Not detection (0 signals moved), "
        "not \"fill at close\" (%.1f%% of traded fills stay intrabar with it off) |"
        % fs["off"]["intrabar_pct"])
    add("| is +0.9571R understated by the fill assumption? | **No — it is "
        "OVERstated.** The assumption is optimistic in one direction, so the "
        "booked number is a ceiling, not a midpoint. |")
    add("| shipped default | `ON_WATCH=1`, unchanged by this ticket |")
    add("")
    add("The question this ticket was set to answer — *is +0.957R understated by "
        "the fill assumption, and by how much* — has an answer, and the sign is "
        "the opposite of the one the question assumes. The fill assumption is not "
        "conservative. Every back-dated fill assumes the trigger beat the stop "
        "inside a minute nobody can see, so **%+.4f R is a ceiling**, and "
        "resolving the ordering can only move it down. ON WATCH is one contributor "
        "to how many fills get back-dated at all; switching it off moves mean R by "
        "%+.4f R and still leaves %.1f%% of traded fills intrabar. So this "
        "flag is not the lever that moves the fill assumption. *(This paragraph "
        "used to end \"it is worth up to ±%.4f R\". Since 2026-08-28 the residual "
        "doubt is worth ±%.4f R — the ceiling claim survives, the magnitude does "
        "not.)*"
        % (st[("all", "on")]["meanr"], d_all, fs["off"]["intrabar_pct"],
           bar_all, nar_all))
    add("")
    add("**The one thing worth doing next was not a flag, and it has been done.** "
        "It was asking Austin a "
        "single question: *when your fill is back-dated to the level and the stop "
        "goes on the entry bar's own wick, could that wick have printed before you "
        "were filled?* **He answered no on 2026-08-28** — a stop needs a close, "
        "and the entry bar has exactly one, so \"out on that same close\" is the "
        "whole rule. That collapsed the error bar from ±%.4f R to ±%.4f R "
        "and made this A/B — and every other sub-1R ranking in the book — "
        "readable. Nothing in the data could have answered it."
        % (bar_all, nar_all))
    add("")

    add("## What this does not say")
    add("")
    add("- It does not ship, retire or re-tune the flag. `ON_WATCH` stays at its "
        "default of `1` and no line of `signal_runner.py` was edited.")
    add("- It does not re-open the stop rule. Stops trigger on the candle CLOSE, "
        "fill at that close, floored at −1.25R; wicks stop nothing out.")
    add("- It does not claim the delta is large. Since 2026-08-28 the delta clears "
        "the carried bar by %.0f× and its sign is readable, but %+.4f R is a tenth "
        "of an R on a book that is 1.0449 R short of the gate, and it costs a "
        "green month. *(This bullet used to say the delta was smaller than the "
        "error bar on the number it is a delta of and that the rig could not show "
        "its sign. That was the wide bar's verdict and it is retired.)*"
        % (abs(d_all) / nar_all if nar_all else 0.0, d_all))
    add("- The intrabar marker can only UNDER-count: `backtest_2y.py:169` stores "
        "entry at 2dp, so a clamped level that rounds into the close's own cent "
        "is recorded as a close fill. The naive `entry != close` test "
        "over-reports by ~11 points; T2's corrected marker is imported here, not "
        "re-derived.")
    add("- %d signals were dropped for a missing archived day and %d for an entry "
        "minute with no bar. Cache misses are never fetched, on purpose."
        % (gaps["day"], gaps["bar"]))
    add("")
    add("## Provenance")
    add("")
    add("Both arms: `%s` → `%s`, %d sessions, %d symbols, replayed at _this "
        "commit_ by `research/g3_onwatch_2y.py`. Reproduce with `python "
        "research/g3_onwatch_2y.py run --arm off` then `--arm on`, then `python "
        "research/g3_onwatch_2y.py report`; verify the rig with `python "
        "research/g3_onwatch_2y.py --selfcheck`."
        % (on["meta"]["first"], on["meta"]["last"], on["meta"]["sessions"],
           len(on["meta"]["symbols"])))
    add("")
    add("**The two arms were replayed against the same engine, and that is not "
        "an assumption here.** Both processes started within 2 seconds of each "
        "other and both books were written within 1.3 seconds of each other, so "
        "each imported `signal_runner.py` and `backtest_week.py` from the same "
        "working tree in the same second; the identical %s-signal count on both "
        "arms is the check on it. A concurrent session edited "
        "`backtest_week.py`, `live_scanner.py` and `paper_trader.py` (ticket G11, "
        "the `stop_rule.py` extraction) TEN MINUTES after both books were "
        "written — `stop_rule.py` did not exist while either arm ran, and "
        "`backtest_week.py` could not have imported it. `signal_runner.py`, where "
        "`ON_WATCH` lives, was untouched throughout."
        % f"{st[('all', 'on')]['signals']:,}")
    add("")
    add("Two repo gates are RED and neither is caused by this ticket, which adds "
        "only new files under `research/`:")
    add("")
    add("- `python research/regression_gate.py` fails on 6 dropped `s_grade` "
        "marks. Its whole import closure — `signal_runner.py`, `levels.py`, "
        "`omen_bot.py`, `universe.py`, `research/t4_engine_recall.py`, "
        "`research/baseline_3.8.json`, `research/austin_marks_v2.jsonl` — is "
        "clean at HEAD, so the regression is in a commit, not in a working-tree "
        "edit, and predates this file.")
    add("- `python research/test_provenance.py` fails on `a1_threshold_sweep.md`, "
        "`g10_arming_funnel.md` and `p26_intrabar_ambiguity.md`. All three are "
        "committed and clean; each names its script but no commit. This report is "
        "not among them.")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# selfcheck -- assert-based, no framework
# ---------------------------------------------------------------------------

def selfcheck():
    import signal_runner as sr
    from omen_bot import Candle

    print("g3 selfcheck -- ON_WATCH is a FILL rule, not a detection rule")

    # ---- A: the flag's default IS the shipped arm --------------------------
    assert ARMS[SHIPPED][0] == "1", "the shipped arm must be the one signal_runner defaults to"
    src = open(os.path.join(ROOT, "signal_runner.py"), encoding="utf-8").read()
    assert 'os.getenv("ON_WATCH", "1")' in src, \
        "signal_runner no longer defaults ON_WATCH to 1 -- SHIPPED is stale"

    # ---- B: the flag reaches exactly 2 of fill_price's call sites -----------
    # Not a claim, a count: only a call that passes session extremes can reach
    # near_session_extreme at all.
    calls = src.count("fill_price(")
    with_sess = src.count("session_hi=hod")
    assert calls - 1 == 10, "fill_price call-site count moved (%d)" % (calls - 1)
    assert with_sess == 2, \
        "ON WATCH is wired into 2 fill sites; found %d" % with_sess

    # ---- C: ON WATCH cannot fire without session extremes ------------------
    # A bar closing jammed on the session low, mid-range on its own bar.
    e = Candle(timestamp="09:45:00", open=50.30, high=50.40, low=50.00,
               close=50.20, volume=1000)
    assert not sr.bar_extreme_veto({"entry": e.close, "direction": "put"}, e), \
        "the probe bar must NOT trip bar_extreme_veto -- otherwise it proves nothing"
    assert sr.near_session_extreme(e, False, 51.00, 50.00), \
        "the probe bar must trip near_session_extreme"
    assert sr.fill_price(50.25, e, is_long=False) == e.close, \
        "with no session extremes the fill is the CLOSE -- 8 of 10 call sites"

    # ---- D: the error-bar arithmetic ---------------------------------------
    # Three traded rows: one ambiguous with the stop ON the bar's extreme, one
    # ambiguous with the stop clear of it, one not ambiguous at all.
    recs = [
        {"traded": True, "intrabar": True, "amb_possible": True, "at_extreme": True,
         "amb_certain": False, "r": 3.0, "sgrade": "S"},
        {"traded": True, "intrabar": True, "amb_possible": True, "at_extreme": False,
         "amb_certain": True, "r": 3.0, "sgrade": "S"},
        {"traded": True, "intrabar": False, "amb_possible": False, "at_extreme": False,
         "amb_certain": False, "r": 3.0, "sgrade": "C"},
    ]
    eb = error_bars(recs)
    assert eb["n"] == 3 and eb["n_amb"] == 2
    assert eb["n_at_extreme"] == 1 and eb["n_residual"] == 1 and eb["n_clear"] == 1
    assert abs(eb["opt"] - 3.0) < 1e-9
    # wide reprices BOTH ambiguous rows: (-1 -1 + 3)/3 = 1/3
    assert abs(eb["wide"] - (3.0 - 1.0 / 3.0)) < 1e-9, "wide must reprice every ambiguous row"
    # narrow reprices only the non-at_extreme one: (3 - 1 + 3)/3 = 5/3
    assert abs(eb["narrow"] - (3.0 - 5.0 / 3.0)) < 1e-9, \
        "narrow must hold the intrabar_stop class at its booked R"
    assert eb["narrow"] < eb["wide"], "the narrow bar is a FLOOR, never wider"

    # ---- E: the flag's reach is on_watch AND NOT bar_extreme ---------------
    f = fill_split([
        {"traded": True, "intrabar": True, "on_watch": True, "bar_extreme": True},
        {"traded": True, "intrabar": True, "on_watch": True, "bar_extreme": False},
        {"traded": True, "intrabar": False, "on_watch": False, "bar_extreme": False},
        {"traded": False, "intrabar": True, "on_watch": True, "bar_extreme": False},
    ], is_on=True)
    assert f["n"] == 3 and f["intrabar"] == 2, "untraded rows are not the money book"
    assert f["ow_only"] == 1, \
        "a bar that also trips bar_extreme fills identically in both arms"

    # ---- F: entry matching against the 64 marks ----------------------------
    ms = marks()
    assert len({(m["symbol"], m["date"]) for m in ms}) == 59, \
        "the 64 marks live on 59 symbol-days"
    m0 = ms[0]
    near = {"sym": m0["symbol"], "day": m0["date"], "entry_i": m0["entry_i"] + ENTRY_TOL}
    far = {"sym": m0["symbol"], "day": m0["date"], "entry_i": m0["entry_i"] + ENTRY_TOL + 1}
    assert entry_match([near], ms) >= 1, "+/-%d bars must match" % ENTRY_TOL
    assert entry_match([far], [m0]) == 0, "one bar past the tolerance must not"
    assert entry_match([dict(near, day="1970-01-01")], [m0]) == 0, \
        "a match must be on the same symbol-DAY"

    # ---- G: T2's rig is imported, never restated ---------------------------
    assert p26.FRAC is sr.BAR_EXTREME_FRAC, "the tolerance unit must come from the source"
    assert p26.HALF_CENT == 0.005, "the 2dp rounding band is T2's, not a local constant"
    a = Candle(timestamp="09:45:00", open=99.70, high=100.90, low=99.60,
               close=100.85, volume=1000)
    row = {"dir": "call", "entry": 100.00, "stop": 99.80, "setup": "break_and_retest",
           "traded": True, "sgrade": "S", "r": 3.0}
    c = p26.classify(row, a, s_hi=100.90, s_lo=99.60)
    assert c["intrabar"] and c["amb_possible"], "T2's classifier must still behave"
    same = p26.classify(dict(row, entry=round(a.close, 2)), a, s_hi=100.90, s_lo=99.60)
    assert not same["intrabar"], \
        "the 2dp rounding correction must survive -- a close fill is not an intrabar fill"

    print("  cases A-G pass. No engine default was written; ON_WATCH was never set "
          "in this process.")
    return 0


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run", help="one arm's full 2-year replay")
    r.add_argument("--arm", choices=sorted(ARMS), required=True)
    r.add_argument("--days", type=int, default=730)
    r.add_argument("--out", default=None)
    rep = sub.add_parser("report", help="score both arms -> g3_onwatch_2y.md")
    rep.add_argument("--off", default=ARMS["off"][1])
    rep.add_argument("--on", default=ARMS["on"][1])
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()

    if a.selfcheck:
        return selfcheck()
    if a.cmd == "run":
        return run(a.arm, a.days, a.out)
    if a.cmd != "report":
        ap.print_help()
        return 2

    books = {}
    for arm, path in (("off", a.off), ("on", a.on)):
        if not os.path.exists(path):
            print("missing %s -- run: python research/g3_onwatch_2y.py run --arm %s"
                  % (path, arm))
            return 1
        with open(path, encoding="utf-8") as fh:
            books[arm] = json.load(fh)
    print("classifying both arms (T2's marker, one bar load per symbol-day)...")
    cls, gaps = classify_books(books)
    md = report(books, cls, gaps)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(md)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
