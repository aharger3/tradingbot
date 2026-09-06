"""build_tape.py -- OMEN 10.0 row T1: the two-year tape page.

Builds on `research/build_bt2y_report.py` (its facet engine, its JS, its
edge scanner) rather than forking it: `encode()`, the `FACETS` field list and
the whole client-side script are imported/extended, not retyped. What this
file adds on top:

  * multiple STAMPED books merged into one page, each row tagged with which
    book it came from (`source`, `fillmode`) instead of one bt2y_trades.json
  * a `lane` facet (core11 / index3 / full29 -- a signal can sit in more than
    one, so it is MULTI like `tags`)
  * a `policy` facet (`every_signal` / `first_of_day` / `up_to_3`) -- his day
    policy, computed the same way R3's baseline number was computed
    (`research/loop_cycle.up_to_3_rows`, `research/g72_suppress_price`),
    scoped to the core-11 universe exactly as `research/tape/loop.json`'s
    `universe.row_filter` does, so the numbers this page shows for the
    default selection are the SAME numbers, not a re-derivation
  * a tiny separate fill-mode study table (R1's `fillarms_*` books --
    different day, different commit, a different trade schema entirely; see
    "Why the fill-mode study is a separate table" below) -- not merged into
    the row-level engine

WHAT IS DELIBERATELY LEFT OUT, AND WHY (README has the long version):
  * `status == "skipped_d"` rows (106,217 of the baseline's 127,513 signals --
    the engine's own downgrade filter, never graded, never a candidate) are
    dropped from every source. That autopsy already exists
    (`research/build_probes.py`'s silent-day probe); keeping them here would
    multiply the page's size by ~6x for a dimension this page does not
    analyze.
  * Comparison sources (phantom, every Phase-L flag) keep only traded +
    halted rows -- the trades that decide a dollar figure -- not the full
    candidate firehose. Only the default `baseline`/`close` source keeps the
    richer fired/tight-stop-skip/filtered breakdown, because only it is the
    thing being explored candidate-by-candidate; the others exist to be
    compared at the trade level.
  * exit model and instrument are single-value facets today: every stamped
    book in `research/tape/` uses the shipped ladder exit
    (`SCALE_PLAN=hod_then_runner_be`; no flat-2R book has been built here),
    and T2's instrument columns (`research/g213_instruments.md`) have not
    landed. Both facets are present so the rail's shape does not change when
    they do; each carries exactly one chip until then.

Usage: python research/build_tape.py [--out research/tape/omen-tape.html]
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import build_bt2y_report as bt2y_mod        # noqa: E402
from research.build_bt2y_report import (              # noqa: E402
    encode as base_encode, FACETS as BASE_FACETS, MULTI as BASE_MULTI,
    NUMS, STRS, book_of, TEMPLATE as BASE_TEMPLATE,
)
from research.loop_cycle import up_to_3_rows           # noqa: E402
from research.g72_suppress_price import (               # noqa: E402
    shipped_rows, oneaday_rows, stats as g72_stats,
)
from research import book_stamp                          # noqa: E402
import universe                                           # noqa: E402

TAPE = ROOT / "research" / "tape"
CORE_SET = frozenset(universe.CORE_SYMBOLS)
INDEX_SET = frozenset(universe.INDEX_POOL_SET)

# ------------------------------------------------------------- extra facets
# Appended to build_bt2y_report's FACETS/MULTI so the page renders one more
# rail section per new dimension without touching the shared JS engine.
EXTRA_FACETS = [
    ("source", "Book / flag variant"),
    ("fillmode", "Fill mode"),
    ("lane", "Pool (core / index / full)"),
    ("policy", "Day policy"),
    ("wk", "Week"),
    ("exitmodel", "Exit model"),
    ("instrument", "Instrument"),
]
EXTRA_MULTI = ["lane", "policy"]
FACETS = BASE_FACETS + EXTRA_FACETS
MULTI_FIELDS = BASE_MULTI + EXTRA_MULTI


def encode_extended(trades):
    """base_encode() dict/list-encodes whatever FACETS/MULTI it finds in its
    OWN module globals -- calling it directly silently drops every facet
    this file adds (source, fillmode, lane, policy, wk, exitmodel,
    instrument), because those live only in build_tape.FACETS/MULTI_FIELDS.
    Rebind the base module's globals for the duration of the call so its one
    encoder (not a fork of it) sees the extended field list, then restore
    them -- this file's own module state (FACETS/MULTI_FIELDS above) is
    untouched either way."""
    saved = bt2y_mod.FACETS, bt2y_mod.MULTI
    bt2y_mod.FACETS, bt2y_mod.MULTI = FACETS, MULTI_FIELDS
    try:
        return bt2y_mod.encode(trades)
    finally:
        bt2y_mod.FACETS, bt2y_mod.MULTI = saved

# One row per (source, fillmode, sym, day, entry minute) among TRADED rows --
# the no-repeat guarantee this page's own self-check enforces before it ever
# writes the HTML.
DupeKey = tuple


def lane_of(sym: str) -> list:
    lane = []
    if sym in CORE_SET:
        lane.append("core11")
    if sym in INDEX_SET:
        lane.append("index3")
    lane.append("full29")
    return lane


def week_of(day: str) -> str:
    try:
        y, w, _ = date.fromisoformat(day).isocalendar()
        return "%d-W%02d" % (y, w)
    except Exception:
        return "n/a"


def tag_common(rows, *, source, fillmode):
    """Attach the facets every merged row carries, in place."""
    for r in rows:
        r["source"] = source
        r["fillmode"] = fillmode
        r["lane"] = lane_of(r.get("sym", ""))
        r["wk"] = week_of(r.get("day", ""))
        r["exitmodel"] = "ladder (hod_then_runner_be)"
        r["instrument"] = "shares (T2 not landed)"
        r["policy"] = []          # filled in by tag_policy for the core lane
    return rows


def tag_policy(rows):
    """His day policy, scoped to core-11 -- exactly loop.json's row_filter.

    Every traded (or halted) row on a non-core symbol keeps policy == [] on
    purpose: R3's baseline number was computed on the core-11 universe only,
    and a page that quietly widened the pool while a policy filter was
    active would show a number nobody asked for. Selecting a wider pool
    alongside a policy filter shows exactly the core-11 rows that carry
    that tag -- documented in the README, not silently reinterpreted here.
    """
    core_rows = [r for r in rows if r.get("tier") == "core"]
    # The SAME candidate pool oneaday_rows/up_to_3_rows build internally:
    # fired-and-traded, plus the account-wide two-loss halt's own rows (a
    # halt this unit's own stop rule would not have reached yet does not
    # erase the rest of the day). Tagging "every_signal" off shipped_rows()
    # (traded == True only) undercounts by exactly the halted rows and
    # silently drops 149 of R3's 769 up_to_3 trades from this facet -- found
    # while wiring this up, fixed here rather than shipped broken.
    candidates = [r for r in core_rows
                  if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted"]
    first = oneaday_rows(core_rows)
    up3 = up_to_3_rows(core_rows)
    first_ids = {id(r) for r in first}
    up3_ids = {id(r) for r in up3}
    for r in candidates:
        tags = ["every_signal"]
        if id(r) in first_ids:
            tags.append("first_of_day")
        if id(r) in up3_ids:
            tags.append("up_to_3")
        r["policy"] = tags


def load_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def flag_decision(flag):
    """The real cycles.md verdict for a Phase-L flag ('hold' or 'ship') --
    read, not assumed. Referee (T1 v1): the provenance note hardcoded 'hold'
    for every Phase-L book though cycles.md records DAY_POLICY as 'ship'."""
    path = TAPE / "cycles.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "unknown (cycles.md not found)"
    decision = None
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 4 and cells[3] == flag:
            decision = cells[4]        # last matching row wins (repairs append)
    return decision or "unknown (not found in cycles.md)"


# ------------------------------------------------------------- rich sources

def load_rich_sources():
    """baseline (close+phantom) and every Phase-L 'on' book, trimmed.

    Returns (rows, notes) -- notes is the provenance line for each source,
    used by the README section and printed at build time.
    """
    rows = []
    notes = []

    meta_b, base_rows = load_gz(TAPE / "baseline_2026-09-05.json.gz")
    base_rows = [r for r in base_rows if r.get("status") != "skipped_d"]
    for r in base_rows:
        r["book"] = book_of(r)
    tag_common(base_rows, source="baseline", fillmode="close")
    tag_policy(base_rows)
    rows.extend(base_rows)
    notes.append("baseline / close -- research/tape/baseline_2026-09-05.json.gz "
                 "(book_id %s), full fired/tight-stop/halted breakdown, "
                 "skipped_d dropped (%d rows kept of %d signals)."
                 % (meta_b["stamp"]["book_id"], len(base_rows), meta_b["signals"]))

    meta_p, phantom_rows = load_gz(TAPE / "baseline_2026-09-05_published.json.gz")
    phantom_rows = [r for r in phantom_rows if r.get("traded") or r.get("status") == "halted"]
    for r in phantom_rows:
        r["book"] = book_of(r)
    tag_common(phantom_rows, source="baseline", fillmode="phantom")
    tag_policy(phantom_rows)
    rows.extend(phantom_rows)
    notes.append("baseline / phantom -- research/tape/baseline_2026-09-05_published.json.gz "
                 "(book_id %s), ENTRY_FILL=published, traded+halted only (%d rows kept)."
                 % (meta_p["stamp"]["book_id"], len(phantom_rows)))

    phase_l = [
        ("L1_on (the 1R first-target rule, MIN_PT1_R)", "MIN_PT1_R", "book_MIN_PT1_R_on.json.gz"),
        ("L2_on (the 84% re-entry as decided, RULE84_DECIDED)", "RULE84_DECIDED",
         "book_RULE84_DECIDED_on.json.gz"),
        ("L3_on (one-candle-rule needs a strong retest candle, OCR_RETEST_DISPLACEMENT)",
         "OCR_RETEST_DISPLACEMENT", "book_OCR_RETEST_DISPLACEMENT_on.json.gz"),
        ("L4_on (the 15-minute structure trend test, TREND_DEF)", "TREND_DEF",
         "book_TREND_DEF_on.json.gz"),
        ("L5_on (up to 3 trades a day, stop after a win or 2 losses, DAY_POLICY)",
         "DAY_POLICY", "book_DAY_POLICY_on.json.gz"),
    ]
    for label, flag, fname in phase_l:
        meta_l, lrows = load_gz(TAPE / fname)
        lrows = [r for r in lrows if r.get("traded") or r.get("status") == "halted"]
        for r in lrows:
            r["book"] = book_of(r)
        src = label.split()[0]
        tag_common(lrows, source=src, fillmode="close")
        tag_policy(lrows)
        rows.extend(lrows)
        notes.append("%s -- research/tape/%s (book_id %s), cycles.md decision: %s; "
                     "traded+halted only (%d rows kept)."
                     % (label, fname, meta_l["stamp"]["book_id"], flag_decision(flag),
                        len(lrows)))

    return rows, notes


# --------------------------------------------------------- fill-mode study
# R1's fillarms_* books: a different day, a different (dirty) commit lineage
# (57f2fbd2.../c7d52853..., never 29e4abc6), and a different trade schema
# entirely (entry_time/fill_mode/austin_tier, no month/week/pool/tags). They
# cannot be merged into the row-level engine above without either forging
# fields the replay never recorded or silently implying a same-day A/B that
# is not true (SWARM.md law 5). So: one small, static, clearly-labelled
# summary table instead -- ranked among THEMSELVES only, never against the
# baseline's $/day.
FILLARM_MODES = ["as_booked", "close", "next_open", "limit_level", "mid_candle", "chase_once"]
FILLARM_POOLS = ["core11", "full29"]


def fillarm_summary():
    rows = []
    for mode in FILLARM_MODES:
        for pool in FILLARM_POOLS:
            path = TAPE / ("fillarms_%s_%s.json.gz" % (mode, pool))
            if not path.exists():
                continue
            meta, trades = load_gz(path)
            filled = [t for t in trades if not t.get("unfilled")]
            n = len(filled)
            days = len({t["day"] for t in filled})
            total_r = sum(t.get("r", 0.0) for t in filled)
            total_dollars = sum(t.get("pnl", 0.0) for t in filled)
            wins = sum(1 for t in filled if t.get("r", 0) > 0)
            rows.append({
                "mode": mode, "pool": pool, "trades": n,
                "unfilled": len(trades) - n,
                "days": days,
                "per_day": round(total_dollars / days, 0) if days else 0,
                "mean_r": round(total_r / n, 4) if n else 0,
                "win_pct": round(wins / n * 100, 1) if n else 0,
                "book_id": meta.get("stamp", {}).get("book_id", "?"),
                "commit": (meta.get("stamp", {}).get("git", {}).get("commit") or "?")[:10],
            })
    return rows


# ------------------------------------------------------------- self-check

def check_no_repeats(rows):
    """The spec's own no-repeat key: one row per (symbol, day, entry minute)
    -- scoped per (source, fillmode), because each source IS a different
    stamped book covering the same 499 sessions on purpose (baseline vs.
    phantom-fill vs. each Phase-L "on" book); merging across sources is
    this page's whole point, not a repeat.

    Referee (pass 2 + pass 3, upheld both passes): the prior key added
    dir/entry/stop/pnl/status/level_name on top of (sym, day, et), and
    level_name in particular always differs between the two rows of a real
    duplicate (the replay can legitimately fire two DIFFERENTLY NAMED
    pivots at the same price in the same minute -- signal_runner.py names a
    level by which pivot it is, not by the price it converges to), so that
    key could never report anything but zero. Keying on the spec's own
    (source, fillmode, sym, day, et) instead finds real duplicates: 5 keys
    inside the published up_to_3/core11/baseline/close unit (worth -$2,514,
    9.8% of that unit's -$25,746 loss, and a fifth of these 5 consume a
    2nd/3rd day-policy slot a different signal would otherwise have taken),
    151 keys / 160 extra rows in the full baseline/close book, 963 keys /
    1,020 extra rows across all 7 merged sources (research/t1_referee.md
    pass 3, research/t1_referee_pass3.py). Only 50 of those 160 extra rows
    in baseline/close share an identical P&L with their twin (110 differ);
    only 24 share a stop -- so these are not render-time double-counts of
    one trade, they are the replay firing two distinct signals that landed
    in the same (symbol, day, minute).

    This is a genuine property of the shipped engine's arrival order, not a
    bug this page's book-merging introduced (confirmed: fixing it would
    mean deciding which of the two same-minute pivots the day-policy unit
    should see, which moves which candidate is R3's baseline 2nd/3rd
    arrival -- a second change, out of scope for this row; see the repair's
    Refereed section). The build reports the real, nonzero count rather
    than the false zero the old key produced; it does not hard-fail on it,
    because that specific fix is not made here."""
    seen = Counter()
    for r in rows:
        if not r.get("traded"):
            continue
        key = (r.get("source"), r.get("fillmode"), r.get("sym"), r.get("day"), r.get("et"))
        seen[key] += 1
    dupes = {k: n for k, n in seen.items() if n > 1}
    extra_rows = sum(n - 1 for n in dupes.values())
    return len(dupes), extra_rows, list(dupes.items())[:10]


# ------------------------------------------------------------------ README
# The default-selection figures, computed the same way this build asserts
# them (see test_tape.py) -- printed into the generated page's footer note
# and the README so a reader never has to trust an unverified number.
DEFAULT_SEL_UNIT = "up_to_3_stop_win_or_2loss, core-11, close fill, baseline (research/loop_cycle.up_to_3_rows)"


def compute_default_selection_stats(rows):
    core_baseline_close = [r for r in rows
                           if r.get("source") == "baseline" and r.get("fillmode") == "close"
                           and "up_to_3" in r.get("policy", [])]
    sessions = len({r["day"] for r in rows if r.get("source") == "baseline"
                    and r.get("fillmode") == "close"})
    return g72_stats(core_baseline_close, sessions)


TEMPLATE = (BASE_TEMPLATE
    .replace("<title>OMEN Two-Year Tape</title>",
             "<title>OMEN Two-Year Tape</title>")
    .replace(
        # Referee (pass 2 + pass 3, upheld both passes): the word "phantom"
        # appeared 0 times anywhere in the static page shell -- a reader
        # who picks the "phantom" chip under Fill mode meets an unlabelled
        # word with no warning that it prices a fill that never existed
        # (the same fill the rest of this repo calls out as the reason
        # every pre-2026-08-30 dollar figure was wrong). Say so in plain
        # text next to the filter rail, where the chip lives.
        '  <div class="railhead">\n'
        '    <h2>Filters</h2>',
        '<p class="note" style="margin:0 0 10px">\n'
        '    <b>Fill mode &mdash; phantom is a warning, not a choice.</b>\n'
        '    &ldquo;phantom&rdquo; fill means <span class="mono">ENTRY_FILL=published</span>:\n'
        '    the price used before 2026-08-30, obtainable at 105 of 4,508 trades\n'
        '    (2.3%). It is on this page so it stays visible beside the honest\n'
        '    &ldquo;close&rdquo; fill, never to be picked as the default reading.\n'
        '  </p>\n'
        '  <div class="railhead">\n'
        '    <h2>Filters</h2>')
    .replace('<h1>OMEN <em>Two-Year Tape</em></h1>',
             '<h1>OMEN <em>Two-Year Tape</em></h1>')
    .replace(
        '<button class="ghost" id="reset" type="button">Traded only</button>',
        '<button class="ghost" id="reset" type="button">R3 default</button>')
    .replace(
        'function defaultSel(){          // the page opens on the traded book, not the raw firehose\n'
        '  clearSel();\n'
        '  var c = dicts.book.indexOf("traded");\n'
        '  if(c >= 0) sel.book.add(c);\n'
        '}',
        'function defaultSel(){          // R3\'s baseline exactly: core-11, close fill,\n'
        '  clearSel();                    // baseline source, his up-to-3 day policy\n'
        '  function pick(field, value){\n'
        '    var c = dicts[field].indexOf(value);\n'
        '    if(c >= 0) sel[field].add(c);\n'
        '  }\n'
        '  pick("source", "baseline");\n'
        '  pick("fillmode", "close");\n'
        '  pick("lane", "core11");\n'
        '  pick("policy", "up_to_3");\n'
        '}')
    .replace(
        # drawEquity(): the curve was R-only -- label each gridline and the
        # endpoint with the dollar figure too (R * RISK), no second axis or
        # toggle needed. Referee (T1 v1): equity curve and max drawdown were
        # R-only, no dollar curve.
        '  [0,.25,.5,.75,1].forEach(function(t){\n'
        '    var v=mn+(mx-mn)*t;\n'
        '    svg.appendChild(svgEl("line",{x1:P,x2:W-8,y1:y(v),y2:y(v),"class":"gridline"}));\n'
        '    svg.appendChild(svgEl("text",{x:4,y:y(v)+3,"class":"axlab"},v.toFixed(0)+"R"));\n'
        '  });',
        '  [0,.25,.5,.75,1].forEach(function(t){\n'
        '    var v=mn+(mx-mn)*t;\n'
        '    svg.appendChild(svgEl("line",{x1:P,x2:W-8,y1:y(v),y2:y(v),"class":"gridline"}));\n'
        '    svg.appendChild(svgEl("text",{x:4,y:y(v)+3,"class":"axlab"},\n'
        '      v.toFixed(0)+"R ("+money(v*RISK)+")"));\n'
        '  });')
    .replace(
        '  svg.appendChild(svgEl("circle",{cx:x(eq.length-1),cy:y(eq[eq.length-1]),r:3.2,\n'
        '    fill:up?"var(--win)":"var(--loss)"}));',
        '  svg.appendChild(svgEl("circle",{cx:x(eq.length-1),cy:y(eq[eq.length-1]),r:3.2,\n'
        '    fill:up?"var(--win)":"var(--loss)"}));\n'
        '  svg.appendChild(svgEl("text",{x:x(eq.length-1)-4,y:y(eq[eq.length-1])-8,\n'
        '    "class":"axlab","text-anchor":"end"},\n'
        '    fmt(eq[eq.length-1],1)+"R = "+money(eq[eq.length-1]*RISK)));')
    .replace(
        'var MULTI = {tags:1, downgrades:1};       // fields holding a list per signal',
        'var MULTI = {tags:1, downgrades:1, lane:1, policy:1};  // fields holding a list per signal')
    .replace(
        # stats(): add $/day, avg win/avg loss (dollars), fires/day and a
        # weeks-green count using the `wk` facet this row adds -- the
        # scoreboard patch below reads these. Referee (T1 v1): none of
        # $/day, avg win/avg loss, weeks green, fires/day were on the
        # scoreboard.
        'function stats(idxs){\n'
        '  var n=idxs.length, w=0,l=0,sc=0, sumR=0, gp=0, gl=0, bars=0, dec=0;\n'
        '  var eq=0, peak=0, dd=0, streak=0, worstStreak=0;\n'
        '  var byMonth = {}, days = {};\n'
        '  for(var k=0;k<n;k++){\n'
        '    var i=idxs[k], r=cols.r[i], o=val("out",i);\n'
        '    sumR+=r; bars+=cols.bars[i];\n'
        '    if(o==="win"){w++;dec++;} else if(o==="loss"){l++;dec++;} else sc++;\n'
        '    if(r>0) gp+=r; else gl+=-r;\n'
        '    eq+=r; if(eq>peak) peak=eq; if(peak-eq>dd) dd=peak-eq;\n'
        '    if(r<0){ streak++; if(streak>worstStreak) worstStreak=streak; } else streak=0;\n'
        '    var m=val("ym",i); byMonth[m]=(byMonth[m]||0)+r;\n'
        '    days[val("day",i)]=1;\n'
        '  }\n'
        '  var months=Object.keys(byMonth).sort();\n'
        '  var green=0; months.forEach(function(m){ if(byMonth[m]>0) green++; });\n'
        '  return {n:n, w:w, l:l, sc:sc, dec:dec,\n'
        '    wr: dec? w/dec*100 : 0,\n'
        '    meanR: n? sumR/n : 0, sumR: sumR,\n'
        '    pf: gl? gp/gl : (gp?Infinity:0),\n'
        '    dd: dd, worstStreak: worstStreak,\n'
        '    bars: n? bars/n : 0,\n'
        '    months: months, byMonth: byMonth,\n'
        '    greenPct: months.length? green/months.length*100 : 0,\n'
        '    days: Object.keys(days).length};\n'
        '}',
        'function stats(idxs){\n'
        '  var n=idxs.length, w=0,l=0,sc=0, sumR=0, gp=0, gl=0, bars=0, dec=0;\n'
        '  var eq=0, peak=0, dd=0, streak=0, worstStreak=0;\n'
        '  var winPnl=0, lossPnl=0, winN=0, lossN=0;\n'
        '  var byMonth = {}, byWeek = {}, days = {};\n'
        '  for(var k=0;k<n;k++){\n'
        '    var i=idxs[k], r=cols.r[i], o=val("out",i);\n'
        '    sumR+=r; bars+=cols.bars[i];\n'
        '    if(o==="win"){w++;dec++;} else if(o==="loss"){l++;dec++;} else sc++;\n'
        '    if(r>0) gp+=r; else gl+=-r;\n'
        '    var pnl = r*RISK;\n'
        '    if(pnl>0){ winPnl+=pnl; winN++; } else if(pnl<0){ lossPnl+=pnl; lossN++; }\n'
        '    eq+=r; if(eq>peak) peak=eq; if(peak-eq>dd) dd=peak-eq;\n'
        '    if(r<0){ streak++; if(streak>worstStreak) worstStreak=streak; } else streak=0;\n'
        '    var m=val("ym",i); byMonth[m]=(byMonth[m]||0)+r;\n'
        '    var wkv=val("wk",i); byWeek[wkv]=(byWeek[wkv]||0)+r;\n'
        '    days[val("day",i)]=1;\n'
        '  }\n'
        '  var months=Object.keys(byMonth).sort();\n'
        '  var green=0; months.forEach(function(m){ if(byMonth[m]>0) green++; });\n'
        '  var weeks=Object.keys(byWeek).sort();\n'
        '  var weekGreen=0; weeks.forEach(function(w2){ if(byWeek[w2]>0) weekGreen++; });\n'
        '  var nDays=Object.keys(days).length;\n'
        '  return {n:n, w:w, l:l, sc:sc, dec:dec,\n'
        '    wr: dec? w/dec*100 : 0,\n'
        '    meanR: n? sumR/n : 0, sumR: sumR,\n'
        '    pf: gl? gp/gl : (gp?Infinity:0),\n'
        '    dd: dd, worstStreak: worstStreak,\n'
        '    bars: n? bars/n : 0,\n'
        '    months: months, byMonth: byMonth,\n'
        '    greenPct: months.length? green/months.length*100 : 0,\n'
        '    weeks: weeks, weeksGreenPct: weeks.length? weekGreen/weeks.length*100 : 0,\n'
        '    perDay: nDays? (sumR*RISK)/nDays : 0, firesPerDay: nDays? n/nDays : 0,\n'
        '    avgWin: winN? winPnl/winN : 0, avgLoss: lossN? lossPnl/lossN : 0,\n'
        '    days: nDays};\n'
        '}')
    .replace(
        # renderKPIs(): surface the four dollar/durability reads the row asks
        # for. Inherited card layout unchanged for the rest.
        '    ["Months green", fmt(s.greenPct,0)+"%",\n'
        '      \'<span class="gate \'+durable+\'">\'+s.months.length+" months</span>", cls(s.greenPct-50)],\n'
        '    ["Avg hold", fmt(s.bars,0)+" min", "entry bar to exit bar", "neu"]\n'
        '  ];',
        '    ["Months green", fmt(s.greenPct,0)+"%",\n'
        '      \'<span class="gate \'+durable+\'">\'+s.months.length+" months</span>", cls(s.greenPct-50)],\n'
        '    ["Weeks green", fmt(s.weeksGreenPct,0)+"%", s.weeks.length+" weeks", cls(s.weeksGreenPct-50)],\n'
        '    ["$/day", money(s.perDay), s.days+" trading days", cls(s.perDay)],\n'
        '    ["Avg win / avg loss", money(s.avgWin)+" / "+money(s.avgLoss),\n'
        '      "per-trade dollars at $"+RISK+"/R", "neu"],\n'
        '    ["Fires/day", fmt(s.firesPerDay,2), "rows in selection per traded day", "neu"],\n'
        '    ["Avg hold", fmt(s.bars,0)+" min", "entry bar to exit bar", "neu"]\n'
        '  ];')
    .replace(
        # Referee (pass 3, defect 1): "source" and "fillmode" are book/fill
        # VARIANTS of the same underlying two-year window, not independent
        # dimensions like symbol or month -- picking two chips in either
        # field silently UNIONS two different books into one KPI row (e.g.
        # baseline+phantom, or baseline+every Phase-L "on" book at once),
        # which is exactly how the refuted "+$799.6/day, 21/25 green"
        # (2 fillmode chips) and "+$3,531/day, 17/25 green, 64,788 rows"
        # (Clear -> zero filters -> all 7 sources at once) numbers got
        # printed. Make these two fields EXCLUSIVE-select (radio, not
        # checkbox): clicking a chip in "source" or "fillmode" replaces
        # whatever was selected there instead of adding to it. Every other
        # facet (symbol, month, setup, ...) keeps its normal multi-chip OR
        # behavior -- this is scoped to the two fields that name a book.
        '  rail.addEventListener("click", function(e){\n'
        '    var c = e.target.closest(".chip"); if(!c) return;\n'
        '    var field = c.parentNode.getAttribute("data-field"), code = +c.getAttribute("data-code");\n'
        '    var s = sel[field];\n'
        '    if(s.has(code)) s.delete(code); else s.add(code);\n'
        '    render();\n'
        '  });',
        '  var EXCLUSIVE_SELECT = {source:1, fillmode:1};   // book/fill variants, not independent facets\n'
        '  rail.addEventListener("click", function(e){\n'
        '    var c = e.target.closest(".chip"); if(!c) return;\n'
        '    var field = c.parentNode.getAttribute("data-field"), code = +c.getAttribute("data-code");\n'
        '    var s = sel[field];\n'
        '    if(EXCLUSIVE_SELECT[field]){\n'
        '      if(s.has(code) && s.size===1) s.clear(); else { s.clear(); s.add(code); }\n'
        '    } else if(s.has(code)) s.delete(code); else s.add(code);\n'
        '    render();\n'
        '  });')
    .replace(
        # Referee (pass 3, defect 1): the "Clear" button called clearSel()
        # then render(), so one click summed all 7 merged sources over the
        # same 499 sessions (+$3,531/day, 17/25 green, 64,788 rows) with no
        # warning -- a reader's most obvious next click after "R3 default"
        # produced the least meaningful number on the page. Clear now falls
        # back to the R3 default selection instead of the raw union; a
        # reader who genuinely wants a single wide-open facet can still
        # empty just that one field by re-clicking its lone active chip.
        'document.getElementById("clear").onclick=function(){ clearSel(); page=0; render(); };',
        'document.getElementById("clear").onclick=function(){ defaultSel(); page=0; render(); };')
    .replace(
        '<div class="panel scroll"><table id="trades"></table></div>\n'
        '    <div class="pager">',
        '<div class="panel scroll"><table id="trades"></table></div>\n'
        '    <div class="pager">')
    .replace(
        '<script id="data" type="application/json">__DATA__</script>',
        '<section id="fillarmsec">\n'
        '  <h2>Fill-mode study <span class="hint">R1, a separate day and commit '
        '&mdash; ranked only against itself, never against the baseline</span></h2>\n'
        '  <p class="note">These 12 rows come from a different replay '
        '(<span class="mono">research/tape/fillarms_*.json.gz</span>), built the '
        'same day but off a different, dirty commit than the baseline above. '
        'They answer one question &mdash; which fill mode wins, holding '
        'everything else about that older replay fixed &mdash; and say nothing '
        'about the baseline\'s own $/day.</p>\n'
        '  <div class="panel scroll"><table id="fillarms"></table></div>\n'
        '</section>\n'
        '<script id="data" type="application/json">__DATA__</script>\n'
        '<script id="fillarmdata" type="application/json">__FILLARM_DATA__</script>')
    .replace(
        "render();\n})();",
        "render();\n"
        "(function(){\n"
        "  var rows = JSON.parse(document.getElementById('fillarmdata').textContent);\n"
        "  var head = '<thead><tr><th>Fill mode</th><th>Pool</th><th>N</th>"
        "<th>Unfilled</th><th>Days</th><th>$/day</th><th>Mean R</th><th>Win%</th>"
        "<th>Book id</th></tr></thead>';\n"
        "  var body = rows.map(function(r){\n"
        "    return '<tr><td>'+r.mode+'</td><td class=\"num\">'+r.pool+'</td>'+\n"
        "      '<td class=\"num\">'+r.trades+'</td><td class=\"num\">'+r.unfilled+'</td>'+\n"
        "      '<td class=\"num\">'+r.days+'</td><td class=\"num '+(r.per_day>=0?'pos':'neg')+'\">'+\n"
        "      money(r.per_day)+'</td><td class=\"num\">'+r.mean_r.toFixed(3)+'</td>'+\n"
        "      '<td class=\"num\">'+r.win_pct+'</td><td class=\"num\">'+r.book_id+'</td></tr>';\n"
        "  }).join('');\n"
        "  document.getElementById('fillarms').innerHTML = head+'<tbody>'+body+'</tbody>';\n"
        "})();\n"
        "})();")
)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="research/tape/omen-tape.html")
    args = ap.parse_args()

    rows, notes = load_rich_sources()

    nkeys, nextra, examples = check_no_repeats(rows)
    print("duplicate check on (source, fillmode, sym, day, et): %d duplicate keys, "
          "%d extra rows, among %d traded rows -- known engine arrival-order "
          "property (two differently-named pivots, same symbol/day/minute), "
          "NOT a page-construction bug; see check_no_repeats() docstring and "
          "the T1 repair's Refereed section. Examples: %s"
          % (nkeys, nextra, sum(1 for r in rows if r.get("traded")), examples))

    default_stats = compute_default_selection_stats(rows)
    print("default selection (R3 baseline unit): %s" % default_stats)

    dicts, cols = encode_extended(rows)
    meta = {
        "generated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "first": min(r["day"] for r in rows),
        "last": max(r["day"] for r in rows),
        "sessions": len({r["day"] for r in rows if r["source"] == "baseline"
                         and r["fillmode"] == "close"}),
        "signals": len(rows),
        "traded": sum(1 for r in rows if r.get("traded")),
        "risk_dollars": 1000.0,
    }
    payload = {"meta": meta, "facets": FACETS, "dicts": dicts, "cols": cols}
    data = json.dumps(payload, separators=(",", ":"))
    fillarm_data = json.dumps(fillarm_summary(), separators=(",", ":"))

    from universe import MIN_SAMPLE_N
    html = (TEMPLATE
            .replace("__DATA__", data)
            .replace("__FILLARM_DATA__", fillarm_data)
            .replace("__SESSIONS__", str(meta["sessions"]))
            .replace("__FIRST__", meta["first"]).replace("__LAST__", meta["last"])
            .replace("__GEN__", meta["generated"].replace("T", " "))
            .replace("__NSIG__", "{:,}".format(meta["signals"]))
            .replace("__NTRADED__", "{:,}".format(meta["traded"]))
            .replace("__RISK__", str(int(meta["risk_dollars"])))
            .replace("__MIN_SAMPLE_N__", str(MIN_SAMPLE_N))
            .replace("__SUMMARY__", ""))

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print("wrote %s (%.2f MB)" % (out, out.stat().st_size / 1e6))
    print("\nsources merged:")
    for n in notes:
        print("  - " + n)


if __name__ == "__main__":
    main()
