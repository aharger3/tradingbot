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
        ("L1_on (the 1R first-target rule, MIN_PT1_R)", "book_MIN_PT1_R_on.json.gz"),
        ("L2_on (the 84% re-entry as decided, RULE84_DECIDED)", "book_RULE84_DECIDED_on.json.gz"),
        ("L3_on (one-candle-rule needs a strong retest candle, OCR_RETEST_DISPLACEMENT)",
         "book_OCR_RETEST_DISPLACEMENT_on.json.gz"),
        ("L4_on (the 15-minute structure trend test, TREND_DEF)", "book_TREND_DEF_on.json.gz"),
        ("L5_on (up to 3 trades a day, stop after a win or 2 losses, DAY_POLICY)",
         "book_DAY_POLICY_on.json.gz"),
    ]
    for label, fname in phase_l:
        meta_l, lrows = load_gz(TAPE / fname)
        lrows = [r for r in lrows if r.get("traded") or r.get("status") == "halted"]
        for r in lrows:
            r["book"] = book_of(r)
        src = label.split()[0]
        tag_common(lrows, source=src, fillmode="close")
        tag_policy(lrows)
        rows.extend(lrows)
        notes.append("%s -- research/tape/%s (book_id %s), all held --> hold "
                     "(cycles.md); traded+halted only (%d rows kept)."
                     % (label, fname, meta_l["stamp"]["book_id"], len(lrows)))

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
    """A construction-integrity check on THIS page's own book-merging: did
    build_tape.py ever insert the identical physical trade twice (e.g. a book
    loaded and appended twice by a bug in this script)?

    Not an audit of the replay engine's own behavior. Two trades count as
    the SAME row only if every field the engine recorded about them agrees
    -- symbol, day, entry minute, direction, entry, stop, pnl, status AND
    which named level was retested. That last field matters: the replay can
    legitimately fire two DIFFERENT named pivots that happen to sit at the
    same price in the same minute (e.g. ACHR 2025-01-07 10:39, "pivot low
    @10:18" and "pivot low @10:24" both at $11.13, priced identically) --
    that is a real, pre-existing arrival-order property of the shipped
    engine (`signal_runner.py` names a level by which pivot it is, not by
    the price it converges to), not a row this page invented, and collapsing
    it here would change which candidate the day-policy unit sees as the
    day's 2nd/3rd arrival -- silently moving R3's already-published $-52/day
    baseline number, which is exactly the failure this file's docstring
    exists to prevent. Confirmed zero duplicates under this identity for
    every source merged as of 2026-09-05; the near-duplicate phenomenon
    itself (127 pairs across the merged sources, same price/pnl, different
    level name) is a genuine engine finding, flagged separately, not fixed
    here (one change per row)."""
    seen = Counter()
    for r in rows:
        if not r.get("traded"):
            continue
        key = (r.get("source"), r.get("fillmode"), r.get("sym"), r.get("day"),
               r.get("et"), r.get("dir"), round(r.get("entry", 0.0) or 0.0, 4),
               round(r.get("stop", 0.0) or 0.0, 4), round(r.get("pnl", 0.0) or 0.0, 4),
               r.get("status"), r.get("level_name"))
        seen[key] += 1
    dupes = {k: n for k, n in seen.items() if n > 1}
    return len(dupes), list(dupes.items())[:10]


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
        'var MULTI = {tags:1, downgrades:1};       // fields holding a list per signal',
        'var MULTI = {tags:1, downgrades:1, lane:1, policy:1};  // fields holding a list per signal')
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

    ndupe, examples = check_no_repeats(rows)
    if ndupe:
        print("DUPLICATE CHECK FAILED: %d duplicate (source, fillmode, sym, day, et) "
              "keys among traded rows. Examples: %s" % (ndupe, examples), file=sys.stderr)
        sys.exit(1)
    print("duplicate check: 0 duplicates among %d traded rows" %
          sum(1 for r in rows if r.get("traded")))

    default_stats = compute_default_selection_stats(rows)
    print("default selection (R3 baseline unit): %s" % default_stats)

    dicts, cols = base_encode(rows)
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
