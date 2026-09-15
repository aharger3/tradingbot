"""build_perfect_deck_2026-09-15.py -- 3 "no questions" break-and-retest cards.

Austin, 2026-09-15: "with all the data and marks you have, propose 3 S trades
-- the really top trades where you say 'look at this, I have no questions,
it's a perfect break-retest' -- and I can say yes on all of them."

WHERE THE CANDIDATES COME FROM. Never a backtest run here -- reads the
honest active baseline book only (``research/tape/baseline_2026-09-13.json.gz``,
fill=close, his day policy) and the archive's own bars
(``g80_ordertype_grid.day_pack``, "data preparation only; no fill and no
grade is computed here"). Nothing is re-simulated and no mark file is
touched.

THE FUNNEL (every step's count is printed and written to the README, so
the selection is auditable, not asserted):

  1. setup == break_and_retest (BR or BR+OCR)
  2. sgrade == S (Austin's classifier ladder -- the engine's automatic S,
     not a human mark)
  3. entry (``et``) between 09:35 and 10:30 ET
  4. core-11 symbol (``tier == "core"``)
  5. status == fired, traded == True
  6. out == win and realized R >= +2
  7. first scale point (the row's own PT1 = ``target``) >= 1R from entry
  8. bar-level, read straight off the archive (no simulation): the trade's
     OWN level was broken for the first time that day (first close beyond
     it since the level existed) and the retest afterward never closed back
     through the level a second time (a genuine single break-and-retest,
     not a multi-leg whipsaw) -- computed by ``_break_retest`` below.

Two of the nine rows that pass steps 1-7 fail step 8 on inspection (AAPL
2026-02-23, AMD 2024-09-25): both round-tripped back through their level
for 5-13 bars before reclaiming it, which is a real second leg, not one
clean retest -- kept out, not silently dropped; the README says why.

Of the 7 survivors the 3 shipped here are the only ones where the break
bar, the retest bar and the entry bar are three DISTINCT bars (so the chart
tells a break -> retest -> entry story instead of collapsing two labels
onto one candle) and they are three different symbols in three different
months -- the other 4 survivors either repeat NVDA/TSLA/AMD or fold retest
and entry onto the same bar.

Chart renderer: ``research/probe_chart.py`` (the same renderer
``research/sm_deck.py`` calls), rendered to PNG via Playwright exactly as
``sm_deck._render_pngs`` does.

    python research/build_perfect_deck_2026-09-15.py

Writes research/decks/perfect_2026-09-15/<n>_<symbol>_<day>.png,
manifest.json and README.md.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research import g80_ordertype_grid as G       # noqa: E402
from research import probe_chart as pc             # noqa: E402
from research import probe_page as pp              # noqa: E402

BASELINE = os.path.join(HERE, "tape", "baseline_2026-09-13.json.gz")
OUT_DIR = os.path.join(HERE, "decks", "perfect_2026-09-15")
WIN_START, WIN_END = "09:30:00", "11:00:00"
PNG_W, PNG_H = 1200, 800

# The 3 shipped picks, identified by (sym, day, et, side) -- enough to pick
# one row out of the baseline's occasional same-minute duplicate pivots
# (research/tape/README.md, "a genuine near-duplicate in the source data").
PICKS = [
    ("NVDA", "2024-10-17", "09:47", "L"),
    ("AMD", "2025-05-07", "09:58", "S"),
    ("GOOGL", "2026-03-11", "10:03", "L"),
]


def _load_trades():
    with gzip.open(BASELINE, "rt", encoding="utf-8") as f:
        return json.load(f)["trades"]


def _orh_orl(bars):
    orb = [c for c in bars if c.timestamp < "09:35:00"]
    if not orb:
        return None, None
    return max(c.high for c in orb), min(c.low for c in orb)


def _established_idx(level, level_name, bars):
    """First bar index the trade's own level could have been in play."""
    m = re.search(r"@(\d\d:\d\d)", level_name or "")
    if m:
        tgt = m.group(1)
        for i, c in enumerate(bars):
            if c.timestamp[:5] >= tgt:
                return i
        return len(bars)
    if level in ("OR high", "OR low"):
        for i, c in enumerate(bars):
            if c.timestamp[:5] >= "09:35":
                return i
        return 0
    return 0  # PDH/PDL/PMH/PML -- known before the open


def _break_retest(t, bars):
    """(break_i, retest_i, entry_i, clean) -- bar-level, straight off the archive.

    break_i: first bar at/after the level's own establishment whose CLOSE is
    beyond the level in the trade direction (the first break, by
    construction -- there is no earlier close-through to check because this
    IS the first one found).
    retest_i: the bar between break_i and entry_i whose low (long) / high
    (short) comes closest to the level, i.e. the deepest point of the
    pullback.
    clean: True iff no bar between break_i and entry_i closes back on the
    WRONG side of the level (a second leg / whipsaw, not one retest).
    """
    level_px = t["level_px"]
    side = t["side"]
    et = t["et"]
    est_i = _established_idx(t["level"], t["level_name"], bars)
    entry_i = next((i for i, c in enumerate(bars) if c.timestamp[:5] == et), None)
    break_i = None
    for i in range(est_i, len(bars)):
        c = bars[i]
        thru = (c.close > level_px) if side == "L" else (c.close < level_px)
        if thru:
            break_i = i
            break
    if break_i is None or entry_i is None:
        return None, None, entry_i, False
    best_i, best_abs = None, None
    for i in range(break_i + 1, entry_i + 1):
        c = bars[i]
        d = (c.low - level_px) if side == "L" else (level_px - c.high)
        if best_abs is None or abs(d) < best_abs:
            best_abs, best_i = abs(d), i
    clean = True
    for i in range(break_i + 1, entry_i):
        c = bars[i]
        ok = (c.close > level_px) if side == "L" else (c.close < level_px)
        if not ok:
            clean = False
    return break_i, best_i, entry_i, clean


def run_funnel(trades):
    """Reproduces the selection funnel; returns (steps, survivors, clean_rows)."""
    steps = []
    s = trades
    steps.append(("all baseline signals", len(s)))
    s = [t for t in s if t.get("setup") == "break_and_retest"]
    steps.append(("setup = break-and-retest (BR/BR+OCR)", len(s)))
    s = [t for t in s if t.get("sgrade") == "S"]
    steps.append(("engine grade S", len(s)))
    s = [t for t in s if "09:35" <= t.get("et", "") <= "10:30"]
    steps.append(("entry 09:35-10:30 ET", len(s)))
    s = [t for t in s if t.get("tier") == "core"]
    steps.append(("core-11 symbol", len(s)))
    s = [t for t in s if t.get("status") == "fired" and t.get("traded")]
    steps.append(("fired and traded", len(s)))
    s = [t for t in s if t.get("out") == "win" and t.get("r", 0) >= 2]
    steps.append(("win, realized R >= +2", len(s)))

    def tgt_r(t):
        risk = abs(t["entry"] - t["stop"])
        return abs(t["target"] - t["entry"]) / risk if risk else 0.0

    s = [t for t in s if tgt_r(t) >= 1]
    steps.append(("PT1 (first scale) >= 1R from entry", len(s)))

    clean_rows, dirty_rows = [], []
    for t in s:
        bars, pdh, pdl, pmh, pml = G.day_pack(t["sym"], t["day"])
        b, r_, e, clean = _break_retest(t, bars)
        row = dict(t, _break_i=b, _retest_i=r_, _entry_i=e)
        (clean_rows if clean else dirty_rows).append(row)
    steps.append(("clean single retest (no whipsaw close back through the level)",
                  len(clean_rows)))
    return steps, clean_rows, dirty_rows


def clean_level_name(t):
    return t["level_name"].replace("not-his: ", "").replace("his: ", "")


def build_card(t, idx):
    sym, day = t["sym"], t["day"]
    bars_full, pdh, pdl, pmh, pml = G.day_pack(sym, day)
    bars = [c for c in bars_full if WIN_START <= c.timestamp <= WIN_END]
    candles = [{"t": c.timestamp, "o": c.open, "h": c.high, "l": c.low, "c": c.close}
               for c in bars]

    break_i, retest_i, entry_i = t["_break_i"], t["_retest_i"], t["_entry_i"]
    side = t["side"]
    level_px = t["level_px"]

    # No PDH/PDL/PMH/PML/ORH/ORL context lines -- not asked for, and on all 3
    # of these trades one or more sits within cents of entry/stop/level,
    # which collides label text on a 1200x800 phone card. Only what was
    # asked for: the level, PT1, entry, stop, break, retest.
    marks = [{"i": entry_i, "price": t["entry"], "side": side, "tag": "ENTRY"}]
    hlines = [{"price": t["target"], "label": "PT1", "cls": "tgt"}]

    # This engine's stop always rests exactly on the broken level
    # (`stop_rule.py`, CLAUDE.md "the level stop ... fills at that close") --
    # true on all 3 of these rows (stop == level_px to the cent) -- so one
    # combined, named line instead of two identical overlapping ones.
    assert abs(t["stop"] - level_px) < 0.005, "stop != level_px for %s %s" % (sym, day)
    hlines.append({"price": level_px, "label": clean_level_name(t), "cls": "lvlnamed"})

    dots = [
        {"i": break_i, "price": bars[break_i].close, "label": "BREAK", "cls": "brk"},
        {"i": retest_i,
         "price": bars[retest_i].low if side == "L" else bars[retest_i].high,
         "label": "RETEST", "cls": "rt"},
    ]

    svg = pc.render(candles, {}, marks=marks, hlines=hlines, dots=dots,
                    label="%s %s  09:30-11:00" % (sym, day))
    return svg


_CARD_CSS = """
<style>
:root{--tgt:#0d6961;--lvln:#8a5ea3;--brk:#a86a06;--rt:#3f7f76}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --tgt:#54cfbe;--lvln:#bb92d1;--brk:#e0a340;--rt:#6dbcb0}}
:root[data-theme="dark"]{--tgt:#54cfbe;--lvln:#bb92d1;--brk:#e0a340;--rt:#6dbcb0}
html,body{margin:0}
.pfpage{width:%dpx;height:%dpx;box-sizing:border-box;padding:22px 26px;
  background:var(--bg);display:flex;flex-direction:column}
.pfhead{font-family:"IBM Plex Serif",Georgia,serif;font-weight:600;
  font-size:32px;color:var(--ink);margin:0 0 4px}
.pfsub{font-family:"IBM Plex Mono",monospace;font-size:15px;color:var(--ink-2);
  margin:0 0 14px}
.pfchart{background:var(--surface);border:1px solid var(--rule);
  border-radius:10px;padding:14px 130px 14px 14px}
.chart{overflow:visible}
.chart .hrail.tgt{stroke:var(--tgt);stroke-width:1.1;stroke-dasharray:7 4}
.chart .hrail-t.tgt{font-family:"IBM Plex Mono",monospace;font-size:9px;
  font-weight:600;fill:var(--tgt)}
.chart .hrail.lvlnamed{stroke:var(--lvln);stroke-width:1.3;stroke-dasharray:3 3}
.chart .hrail-t.lvlnamed{font-family:"IBM Plex Mono",monospace;font-size:10px;
  font-weight:600;fill:var(--lvln)}
.chart .dot.brk{stroke:var(--brk);fill:var(--surface);stroke-width:2.2}
.chart .dot-t.brk{font-family:"IBM Plex Mono",monospace;font-size:11px;
  font-weight:700;fill:var(--brk);paint-order:stroke;stroke:var(--surface);
  stroke-width:3px}
.chart .dot.rt{stroke:var(--rt);fill:var(--surface);stroke-width:2.2}
.chart .dot-t.rt{font-family:"IBM Plex Mono",monospace;font-size:11px;
  font-weight:700;fill:var(--rt);paint-order:stroke;stroke:var(--surface);
  stroke-width:3px}
.pflegend{font-family:"IBM Plex Mono",monospace;font-size:13px;color:var(--ink-3);
  margin-top:14px;display:flex;gap:16px;flex-wrap:wrap}
</style>
""" % (PNG_W, PNG_H)

_LEGEND = (
    '<div class="pflegend"><span style="color:var(--lvln)">&#9644; level = stop '
    '(this engine\'s stop always sits on the broken level)</span>'
    '<span style="color:var(--brk)">&#9679; break bar</span>'
    '<span style="color:var(--rt)">&#9679; retest bar</span>'
    '<span>amber line = entry</span>'
    '<span style="color:var(--tgt)">&#9644; PT1</span></div>')


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _page_html(t, svg):
    title = "%s %s &middot; %+.2fR" % (t["sym"], t["day"], t["r"])
    sub = ("%s &middot; %s side &middot; entry %s ET &middot; level %s"
          % (t["setup_label"], "long" if t["side"] == "L" else "short",
             t["et"], clean_level_name(t)))
    return (
        "<!doctype html><html><head><meta charset='utf-8'>" + pp.FONTS
        + pp.CSS + _CARD_CSS + "</head><body><div class='pfpage'>"
        + "<h1 class='pfhead'>%s</h1>" % title
        + "<p class='pfsub'>%s</p>" % _esc(sub)
        + "<div class='pfchart'>%s</div>" % svg
        + _LEGEND + "</div></body></html>")


def render_pngs(cards):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": PNG_W, "height": PNG_H})
        try:
            for t, svg, out_path in cards:
                page.set_content(_page_html(t, svg), wait_until="load")
                page.screenshot(path=out_path)
        finally:
            browser.close()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    trades = _load_trades()
    steps, clean_rows, dirty_rows = run_funnel(trades)

    by_key = {}
    for t in clean_rows + dirty_rows:
        by_key[(t["sym"], t["day"], t["et"], t["side"])] = t

    entries, to_render = [], []
    why = {
        ("NVDA", "2024-10-17"): "gap-fade pivot high @09:40 breaks, one clean "
            "hammer retest bar at 09:46 within 11% of 1R of the level, entry "
            "09:47, straight to +2.76R with no whipsaw.",
        ("AMD", "2025-05-07"): "OR low breaks at 09:49, an 8-bar orderly pullback "
            "closes within 6% of 1R of the level at 09:57 and never re-crosses "
            "it, entry 09:58 for +4.99R -- the cleanest R of the nine candidates.",
        ("GOOGL", "2026-03-11"): "pivot high @09:53 breaks at 09:58, an "
            "immediate one-bar retest at 09:59 holds 13% of 1R above the level, "
            "a 3-bar base, entry 10:03 for +3.03R.",
    }

    for i, (sym, day, et, side) in enumerate(PICKS, start=1):
        t = by_key.get((sym, day, et, side))
        if t is None:
            raise SystemExit("pick not found in clean survivors: %s" % ((sym, day, et, side),))
        svg = build_card(t, i)
        png_name = "%d_%s_%s.png" % (i, sym, day)
        png_path = os.path.join(OUT_DIR, png_name)
        to_render.append((t, svg, png_path))
        entries.append({
            "id": "%s_%s" % (sym, day),
            "symbol": sym,
            "day": day,
            "level": clean_level_name(t),
            "entry_time": et + " ET",
            "r": round(t["r"], 3),
            "why_perfect": why[(sym, day)],
            "png": "research/decks/perfect_2026-09-15/%s" % png_name,
        })

    render_pngs(to_render)

    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=1)

    write_readme(steps, clean_rows, dirty_rows, entries)

    print("perfect deck 2026-09-15: %d cards" % len(entries))
    for e in entries:
        print("  %-14s entry %s  R=%+.2f  %s" % (e["id"], e["entry_time"], e["r"], e["png"]))
    return 0


def write_readme(steps, clean_rows, dirty_rows, entries):
    lines = []
    lines.append("# perfect_2026-09-15 -- 3 no-questions break-and-retest cards\n")
    lines.append("Austin, 2026-09-15: \"propose 3 S trades -- the really top trades "
                 "where you say 'look at this, I have no questions, it's a perfect "
                 "break-retest' -- and I can say yes on all of them.\"\n")
    lines.append("Never a backtest run for this: reads the honest active baseline "
                 "book only (`research/tape/baseline_2026-09-13.json.gz`, fill=close, "
                 "his day policy) and the archive's own bars "
                 "(`g80_ordertype_grid.day_pack`). No mark file touched.\n")
    lines.append("## Selection filter\n")
    lines.append("1. `setup == break_and_retest` (BR or BR+OCR)")
    lines.append("2. `sgrade == S` (engine grade, Austin's S/A/C classifier ladder)")
    lines.append("3. entry (`et`) between 09:35 and 10:30 ET")
    lines.append("4. core-11 symbol (`tier == core`)")
    lines.append("5. `status == fired` and `traded == true`")
    lines.append("6. `out == win` and realized R >= +2")
    lines.append("7. first scale point (the row's own PT1, `target`) >= 1R from entry")
    lines.append("8. bar-level, read off the archive: the level's first close-through "
                 "that day (the FIRST break) followed by a single retest that never "
                 "closes back through the level a second time (no whipsaw)\n")
    lines.append("## Candidates that passed every step\n")
    lines.append("| step | passed |")
    lines.append("|---|---|")
    for name, n in steps:
        lines.append("| %s | %d |" % (name, n))
    lines.append("")
    lines.append("9 rows pass steps 1-7. Bar-level inspection (step 8) drops 2 of "
                 "them for a genuine second leg, not a defect in the count:\n")
    for t in dirty_rows:
        lines.append("- **%s %s** (%s, level %s) -- closes back through the level "
                     "multiple times between the break and the entry (a real "
                     "round-trip, not one retest); kept out, not silently dropped."
                     % (t["sym"], t["day"], t["level"], t["level_name"]))
    lines.append("")
    lines.append("The remaining %d clean rows: %s. The 3 shipped are the ones where "
                 "the break bar, the retest bar and the entry bar are three distinct "
                 "candles (so the chart tells break -> retest -> entry, not two "
                 "labels stacked on one candle), preferring different symbols and "
                 "different months over the other 4 (which repeat a symbol or fold "
                 "the retest onto the entry bar).\n" % (
                     len(clean_rows),
                     ", ".join("%s %s" % (t["sym"], t["day"]) for t in clean_rows)))
    lines.append("## The 3 shipped\n")
    lines.append("| id | entry | R | level | why |")
    lines.append("|---|---|---|---|---|")
    for e in entries:
        lines.append("| %s | %s | %+.2f | %s | %s |" % (
            e["id"], e["entry_time"], e["r"], e["level"], e["why_perfect"]))
    lines.append("")
    lines.append("PNGs: `research/decks/perfect_2026-09-15/1_NVDA_2024-10-17.png`, "
                 "`2_AMD_2025-05-07.png`, `3_GOOGL_2026-03-11.png`. Manifest: "
                 "`research/decks/perfect_2026-09-15/manifest.json`. Builder: "
                 "`research/build_perfect_deck_2026-09-15.py`.\n")
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
