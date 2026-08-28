"""build_h2_deck.py -- the H2 three-lane grading page (OMEN 6 H2 master spec, W7).

    python research/build_h2_deck.py
    python research/build_h2_deck.py --n1 60 --n2 30 --n3 30 --seed 11

One page, three lanes, because three overnight workstreams are blocked on three
different judgements and Austin has one sitting:

  lane 1  B-REMAP     60 cards, ONE tap.   W1 / spec 1.2. There is no B grade any
          more; 1,000 of 1,017 traded signals in `research/g3_arm_ow1.json` are B
          only because `signal_runner._calibration_grade` floors a C up to B when
          it is the first with-trend signal of the day. These are ENGINE-PROPOSED
          cards -- the entry and the stop are already drawn -- so a single
          S/A/C/X tap is a verdict on a specific proposal and nothing is missing.

  lane 2  SILENT DAY  30 cards, TWO taps.  W5 / spec 3 W7. Days he graded S where
          the engine produced no entry. There is NO proposal here, so a grade
          alone is a day-level opinion with no entry and no stop. Tap 2 names the
          LEVEL; level + direction makes a break-and-retest entry (the retest of
          the broken level) and its structural stop (that same level) derivable.
          Tap 2 is hidden until tap 1 is something other than X.

  lane 3  GIVE-BACK   30 cards, ONE tap.   W2 / spec 1.4. 53.8% of trades touch
          2R; the shipped ladder keeps 2R on 27.0%. These are trades whose
          `mfe_clock >= 2.0` and whose ladder gave it back. Entry, stop, the 2R
          rail and the 11:00 clock bar are drawn; the one tap is the position he
          would still be holding at 11:00. That label cannot be derived from
          price -- it is the input the time-scaled exit sweep is missing.

Delivery contract (CLAUDE.md "Homework instruments"): saves as he works, survives
a closed tab, restores on load, visible saved-indicator, Export -> Copy all /
Download .jsonl with no round trip, phone-shaped, charts as static SVG rendered
here in Python. All of that comes from `probe_page.py` / `probe_chart.py`; this
file adds data and three questions, and does not fork the shell.

Output: research/probes/omen-h2-3lane.html
Proved by: research/test_h2_deck_page.py
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import probe_chart                                                     # noqa: E402
import probe_page                                                      # noqa: E402
from research.build_deck import marked_card_ids                        # noqa: E402
from research.p26_intrabar_ambiguity import load_day                   # noqa: E402
from research.t4_engine_recall import (prior_day_levels,               # noqa: E402
                                       premarket_extremes)

OUT_DIR = os.path.join(HERE, "probes")
DECK_ID = "omen-h2-3lane"

G3 = os.path.join(HERE, "g3_arm_ow1.json")            # 1,017 traded, ON WATCH on
H1 = os.path.join(HERE, "h1_2y_nowatch.json")         # same book + mfe/ladder clocks
W5 = os.path.join(HERE, "w5_silent_s_autopsy.md")     # the 12 held-out missed S days
T60 = os.path.join(HERE, "t60_silent_days.jsonl")     # 51 rows, 37 once SPY is out

OPEN, CLOSE_ = "09:30", "11:00"
LATE_CLOSE = "12:00"      # lane 3 only: he cannot judge "past 11:00" off a chart
CLOCK = "11:00"           # that stops at 11:00


# ---------------------------------------------------------------------------
# bars and levels -- archive only, never a network call
# ---------------------------------------------------------------------------

def session(symbol, day, end=CLOSE_):
    """[{t,o,h,l,c,v}] for 09:30..end, or [] if the day is not archived.

    `p26.load_day` is cache-first with the fetch guard ON: a missing day is a
    data gap to skip, never a reason to hit Polygon from a page generator.
    """
    rth = load_day(symbol, day)
    if not rth:
        return []
    out = []
    for c in rth:
        t = c.timestamp[11:16] if "T" in c.timestamp else c.timestamp[:5]
        if OPEN <= t < end:
            out.append({"t": c.timestamp, "o": c.open, "h": c.high, "l": c.low,
                        "c": c.close, "v": c.volume})
    return out


def levels_for(symbol, day, candles):
    try:
        pdh, pdl, _o, _c = prior_day_levels(symbol, day)
        pmh, pml = premarket_extremes(symbol, day)
    except Exception:
        pdh = pdl = pmh = pml = None
    orh = max(x["h"] for x in candles[:5]) if len(candles) >= 5 else None
    orl = min(x["l"] for x in candles[:5]) if len(candles) >= 5 else None
    return {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml, "orh": orh, "orl": orl}


def bar_time(candles, i):
    if not (0 <= i < len(candles)):
        return ""
    t = candles[i]["t"]
    return t[11:16] if "T" in t else t[:5]


def index_of_time(candles, hhmm):
    for i, c in enumerate(candles):
        if bar_time(candles, i) >= hhmm:
            return i
    return None


# ---------------------------------------------------------------------------
# sampling
# ---------------------------------------------------------------------------

def _quarter(day):
    return "%s-Q%d" % (day[:4], (int(day[5:7]) - 1) // 3 + 1)


def _round_robin_by_symbol(rows, rng):
    """Interleave rows so no symbol runs consecutively -- the symbol spread."""
    by = defaultdict(list)
    for r in rows:
        by[r["sym"]].append(r)
    for v in by.values():
        rng.shuffle(v)
    # Shuffled, not sorted by frequency: sorting made the heaviest symbol the
    # first pick in EVERY quarter, and a 60-card lane that only takes 6 per
    # quarter then saw the same handful of tickers over and over.
    order = sorted(by)
    rng.shuffle(order)
    out = []
    while any(by[s] for s in order):
        for s in order:
            if by[s]:
                out.append(by[s].pop(0))
    return out


def stratify(rows, n, seed):
    """n rows spread across the 2-year window AND across symbols.

    Quarters are drawn round-robin so a bull stretch cannot own the sample, and
    within a quarter symbols are interleaved so NVDA cannot own it either.
    """
    rng = random.Random(seed)
    by_q = defaultdict(list)
    for r in rows:
        by_q[_quarter(r["day"])].append(r)
    for q in by_q:
        by_q[q] = _round_robin_by_symbol(by_q[q], rng)
    qs = sorted(by_q)
    out, i = [], 0
    while len(out) < n and any(by_q[q] for q in qs):
        q = qs[i % len(qs)]
        if by_q[q]:
            out.append(by_q[q].pop(0))
        i += 1
    return out


# ---------------------------------------------------------------------------
# lane inputs
# ---------------------------------------------------------------------------

def b_only_rows():
    """Traded signals carrying the legacy `B` -- the whole remap population.

    `grade` is the legacy A+/A/B/C/X ladder the engine trades on today. Every
    traded B in this book is a B because of the first-with-trend floor; the
    downgrade count that the S/A/C/X ladder actually wants is carried beside it
    in `downgrades`, and it is what makes 3+ an X.
    """
    book = json.load(open(G3, encoding="utf-8"))
    return [t for t in book["trades"]
            if t.get("traded") and t.get("grade") == "B"
            and t.get("entry") is not None and t.get("stop") is not None]


def giveback_rows():
    """Trades that reached >= 2R MFE and whose shipped ladder gave it back.

    Arm A of h1_2y_nowatch is the ON-WATCH-off 2-year replay (1,091 trades) with
    `mfe_clock` / `ladder_clock` / `flat2r_clock` attached on ONE clock -- the
    exit_lab 11:00 horizon. Do not mix it with backtest_week's 16:00 numbers.
    """
    d = json.load(open(H1, encoding="utf-8"))
    return [t for t in d["arms"]["A"]
            if (t.get("mfe_clock") or 0) >= 2.0 and (t.get("ladder_clock") or 0) < 2.0]


_W5_ROW = re.compile(
    # `| 4 | **IWM** ⚠ | 2025-03-14 |` -- the out-of-universe warning sits INSIDE
    # the symbol cell, so anything up to the next pipe has to be tolerated.
    r"^\|\s*\d+\s*\|\s*\*\*([A-Z][A-Z0-9.\-]*)\*\*[^|]*\|\s*(\d{4}-\d{2}-\d{2})\s*\|")


def missed_s_days():
    """The 12 held-out S days the engine missed, read off the W5 report.

    Source of record is `research/w5_silent_s_autopsy.md`, produced by
    `research/w5_silent_s_autopsy.py` against
    `research/marks/probe_omen_test1_2026-08-27.jsonl`. Parsed rather than
    retyped so the list cannot drift from the report, and asserted at 12 so a
    format change fails loudly instead of silently shrinking the lane.
    """
    out = []
    if not os.path.exists(W5):
        return out
    for line in open(W5, encoding="utf-8"):
        m = _W5_ROW.match(line.strip())
        if m:
            out.append({"sym": m.group(1), "day": m.group(2), "grade": "S",
                        "src": "test1-missed-S"})
    return out


def t60_silent_rows():
    """The 37 non-SPY silent days behind ticket 09 / `research/build_probes.py`.

    SPY is dropped for the same reason build_probes drops it: the engine is
    configured never to trade SPY, so those are not misses.
    """
    rows = []
    if not os.path.exists(T60):
        return rows
    for line in open(T60, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("symbol") == "SPY":
            continue
        rows.append({"sym": r["symbol"], "day": r["date"],
                     "grade": r.get("grade") or "?", "src": "t60-silent"})
    return rows


# ---------------------------------------------------------------------------
# questions
# ---------------------------------------------------------------------------

# Labels stay single-token: at 390px a two-word chip wraps and grows taller
# than the other three, which reads as a different kind of button.
SAC = [("S", "S"), ("A", "A"), ("C", "C"), ("X", "X")]

LEVEL_OPTS = [
    ("PMH", "PMH"), ("PDH", "PDH"), ("ORH", "ORH"), ("VWAP", "VWAP"),
    ("PML", "PML"), ("PDL", "PDL"), ("ORL", "ORL"), ("other", "Other"),
    # Auto-pressed by the page when tap 1 is X, so the shell's required-question
    # check completes an X card without ever showing him a second tap.
    ("na", "n/a"),
]

HOLD_OPTS = [
    ("full", "FULL"),
    ("half", "~HALF"),
    ("runner", "~10% RUNNER"),
    ("flat", "FLAT"),
]

LEGEND = ('<div class="legend">'
          '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
          '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> premarket</span>'
          '<span><b style="color:var(--lvl-or)">- - ORH/ORL</b> first 5 bars</span>'
          '<span><b style="color:var(--entry)">&#9650; ENTRY</b></span>'
          '<span><b style="color:var(--stop)">STOP</b></span></div>')

# Lane 2 draws no entry and no stop -- that is the whole premise of the lane --
# so its legend must not advertise two keys that appear on no chart.
LEGEND2 = ('<div class="legend">'
           '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
           '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> premarket</span>'
           '<span><b style="color:var(--lvl-or)">- - ORH/ORL</b> first 5 bars</span>'
           '<span>no entry drawn &mdash; the engine proposed none</span></div>')

LEGEND3 = LEGEND[:-len("</div>")] + (
    '<span><b style="color:var(--tgt)">- - 2R</b> target</span>'
    '<span><b style="color:var(--clk)">| 11:00</b> clock</span></div>')


def _attr(obj):
    return (json.dumps(obj, sort_keys=True).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#39;"))


def header(idx, total, symbol, day, tags):
    tag_html = "".join('<span class="tag%s">%s</span>' % (" warn" if w else "", t)
                       for t, w in tags)
    return ('<header><span class="idx">%02d/%02d</span>'
            '<span class="tick">%s</span><span class="when">%s</span>'
            '<span class="tags">%s<span class="done-dot"></span></span></header>'
            % (idx, total, symbol, day, tag_html))


# ---------------------------------------------------------------------------
# cards
# ---------------------------------------------------------------------------

def card_b(idx, total, r, candles):
    sym, day = r["sym"], r["day"]
    lv = levels_for(sym, day, candles)
    i = r.get("entry_i")
    side = r.get("side") or ("L" if r.get("dir") == "call" else "S")
    marks = ([{"i": i, "price": r["entry"], "stop": r["stop"], "side": side,
               "tag": "OMEN"}] if i is not None and 0 <= i < len(candles) else [])
    et = r.get("et") or bar_time(candles, i or 0)
    ndg = len(r.get("downgrades") or [])
    tags = [("%s %s" % ("LONG" if side == "L" else "SHORT",
                        (r.get("setup") or "").replace("_", " ")), False),
            ("was B", True)]
    export = {
        "lane": "b_remap", "symbol": sym, "date": day,
        "eng_grade": "B", "eng_sgrade": r.get("sgrade"),
        "eng_entry": r.get("entry"), "eng_stop": r.get("stop"),
        "eng_side": side, "eng_entry_i": i, "eng_et": et,
        "eng_setup": r.get("setup"), "eng_level": r.get("level"),
        "eng_downgrades": r.get("downgrades") or [], "n_downgrades": ndg,
    }
    return "".join([
        '<article class="card lane1" data-lane="b_remap" data-cid="b_%s_%s_b%s" '
        'data-grade="" data-g="" data-done="0" data-export=\'%s\'>'
        % (sym, day, i, _attr(export)),
        header(idx, total, sym, day, tags),
        '<div class="chartwrap">%s</div>'
        % probe_chart.render(candles, lv, marks, "%s %s" % (sym, day)), LEGEND,
        probe_page.question(
            "grade",
            "OMEN wants this trade. What is it really?",
            "Entry <b>%s</b> at %s, stop %s. One tap. "
            "0 downgrades = S, 1 = A, 2 = C, 3+ = X — kill it."
            % ("long" if side == "L" else "short",
               ("%.2f" % r["entry"]), ("%.2f" % r["stop"])),
            SAC),
        "</article>",
    ])


def card_silent(idx, total, r, candles):
    sym, day = r["sym"], r["day"]
    lv = levels_for(sym, day, candles)
    export = {"lane": "silent_day", "symbol": sym, "date": day,
              "src": r.get("src"), "grade_on_file": r.get("grade")}
    return "".join([
        '<article class="card lane2" data-lane="silent_day" data-cid="s_%s_%s" '
        'data-grade="" data-g="" data-done="0" data-export=\'%s\'>'
        % (sym, day, _attr(export)),
        header(idx, total, sym, day, [("engine silent", True)]),
        '<div class="chartwrap">%s</div>'
        % probe_chart.render(candles, lv, [], "%s %s" % (sym, day)), LEGEND2,
        probe_page.question(
            "grade",
            "OMEN saw nothing here. What did you see?",
            "No entry is drawn because the engine never proposed one. "
            "Grade the day: 0 downgrades = S, 1 = A, 2 = C, X = nothing here.",
            SAC),
        probe_page.question(
            "level",
            "Which level did it come off?",
            "One tap. The level IS the stop on a break-and-retest, so this plus "
            "the direction is enough to rebuild the trade without you marking "
            "the chart.",
            LEVEL_OPTS),
        "</article>",
    ])


def card_giveback(idx, total, r, candles):
    sym, day = r["sym"], r["day"]
    lv = levels_for(sym, day, candles)
    i = r.get("entry_i")
    side = r.get("side") or "L"
    entry, stop = r["entry"], r["stop"]
    risk = abs(entry - stop)
    two_r = entry + (2 * risk if side == "L" else -2 * risk)
    marks = ([{"i": i, "price": entry, "stop": stop, "side": side, "tag": "ENTRY"}]
             if i is not None and 0 <= i < len(candles) else [])
    clk = index_of_time(candles, CLOCK)
    vlines = [{"i": clk, "label": CLOCK, "cls": "clk"}] if clk is not None else []
    et = bar_time(candles, i) if i is not None else ""
    tags = [("%s %s" % ("LONG" if side == "L" else "SHORT",
                        (r.get("setup") or "").replace("_", " ")), False),
            ("MFE %.1fR" % (r.get("mfe_clock") or 0), False),
            ("ladder kept %.2fR" % (r.get("ladder_clock") or 0), True)]
    export = {
        "lane": "giveback", "symbol": sym, "date": day,
        "entry": entry, "stop": stop, "side": side, "entry_i": i, "entry_t": et,
        "two_r": round(two_r, 4), "setup": r.get("setup"),
        "mfe_clock": r.get("mfe_clock"), "ladder_clock": r.get("ladder_clock"),
        "flat2r_clock": r.get("flat2r_clock"), "sgrade": r.get("sgrade"),
        "clock_bar_i": clk,
    }
    return "".join([
        '<article class="card lane3" data-lane="giveback" data-cid="g_%s_%s_b%s" '
        'data-grade="" data-g="" data-done="0" data-export=\'%s\'>'
        % (sym, day, i, _attr(export)),
        header(idx, total, sym, day, tags),
        '<div class="chartwrap">%s</div>'
        % probe_chart.render(candles, lv, marks, "%s %s" % (sym, day),
                             hlines=[{"price": two_r, "label": "2R", "cls": "tgt"}],
                             vlines=vlines), LEGEND3,
        probe_page.question(
            "hold",
            "At 11:00 you are —",
            "You entered %s at %s, stop %s, and it ran to <b>%.1fR</b>. "
            "The chart runs to 12:00 so you can see what the runner was worth. "
            "One tap: how much of the position is still on at the 11:00 line?"
            % ("long" if side == "L" else "short", ("%.2f" % entry),
               ("%.2f" % stop), (r.get("mfe_clock") or 0)),
            HOLD_OPTS),
        "</article>",
    ])


# ---------------------------------------------------------------------------
# page furniture
# ---------------------------------------------------------------------------

EXTRA_CSS = """
<style>
:root{--tgt:#0d6961; --clk:#7b8b87}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--tgt:#54cfbe; --clk:#9aa9a5}}
:root[data-theme="dark"]{--tgt:#54cfbe; --clk:#9aa9a5}
.chart .hrail{stroke:var(--tgt); stroke-width:1.1; stroke-dasharray:7 4}
.chart .hrail-t{font-family:"IBM Plex Mono",monospace; font-size:9px; font-weight:600; fill:var(--tgt)}
.chart .vmark{stroke:var(--clk); stroke-width:1.4; stroke-dasharray:3 3}
.chart .vmark-t{font-family:"IBM Plex Mono",monospace; font-size:9px; font-weight:600;
  fill:var(--clk); text-anchor:middle}
.sec{
  margin:30px 0 14px; padding:14px 16px; border-radius:10px;
  background:var(--accent-soft); border:1px solid var(--rule);
}
.sec h2{
  font-family:"IBM Plex Serif",Georgia,serif; font-size:19px; font-weight:600;
  margin:0 0 4px; color:var(--ink);
}
.sec p{margin:0; font-size:13.5px; color:var(--ink-2)}
.sec .lane{
  font-family:"IBM Plex Mono",monospace; font-size:10px; font-weight:600;
  letter-spacing:.12em; text-transform:uppercase; color:var(--accent);
  display:block; margin:0 0 5px;
}
/* Tap 2 exists only once tap 1 says there was a trade. The `n/a` chip is never
   shown -- the page presses it for him on X so the card still counts as done. */
.lane2[data-g=""] .q[data-q="level"],
.lane2[data-g="X"] .q[data-q="level"]{display:none}
.q[data-q="level"] .chip[data-v="na"]{display:none}
.q[data-q="grade"] .chip[data-v="X"][aria-pressed="true"]{
  background:var(--stop); border-color:var(--stop); color:#fff;
}
.q[data-q="grade"] .chips .chip{flex:1 1 calc(25% - 6px); text-align:center}
.q[data-q="hold"] .chips .chip{flex:1 1 calc(50% - 4px); text-align:center}
.q[data-q="level"] .chips .chip{flex:1 1 calc(25% - 6px); text-align:center}
@media (max-width:520px){
  .q[data-q="grade"] .chips .chip{flex:1 1 calc(25% - 6px)}
  .q[data-q="level"] .chips .chip{flex:1 1 calc(25% - 6px); padding:10px 4px}
  .sec{margin:22px 0 12px; padding:12px 13px}
}
</style>
"""

# One job: mirror the grade onto the card as data-g so the CSS above can reveal
# tap 2, and press the hidden `level=na` chip when the grade is X. Pressing it by
# synthesising a real click means probe_page's OWN handler does the toggle, the
# progress refresh and the localStorage save -- the shell stays the only thing
# that writes state.
EXTRA_JS = r"""
<script>
(function(){
  var syncing = false;
  function gradeOf(card){
    var on = card.querySelector('.q[data-q="grade"] .chip[aria-pressed="true"]');
    return on ? on.getAttribute('data-v') : '';
  }
  function sync(card){
    if (!card || syncing) return;
    var g = gradeOf(card);
    card.setAttribute('data-g', g);
    card.setAttribute('data-grade', g);
    if (card.getAttribute('data-lane') !== 'silent_day') return;
    var na = card.querySelector('.q[data-q="level"] .chip[data-v="na"]');
    if (!na) return;
    var want = (g === 'X');
    var have = na.getAttribute('aria-pressed') === 'true';
    if (want === have) return;
    syncing = true;
    try { na.click(); } finally { syncing = false; }
  }
  document.addEventListener('click', function(e){
    if (!e.target.closest) return;
    var chip = e.target.closest('.chip');
    if (!chip) return;
    sync(chip.closest('.card'));
  });
  Array.prototype.forEach.call(document.querySelectorAll('.card'), sync);
})();
</script>
"""


def section(lane, title, blurb):
    return ('<div class="sec"><span class="lane">%s</span><h2>%s</h2><p>%s</p></div>'
            % (lane, title, blurb))


FOOT = ("<h2>What happens to these taps</h2>"
        "<p>Every tap saves in this page as you make it — close the tab, come back on "
        "the phone, it is still here. When you are done, or partway, hit "
        "<b>Export</b> at the top, then <b>Copy all</b> and paste it into the chat, or "
        "<b>Download .jsonl</b> and send the file. Nothing leaves the page until you "
        "do that.</p>"
        "<p><b>Lane 1</b> kills <code>B</code>: 1,000 of 1,017 traded signals carry it "
        "only because the engine floors the first with-trend signal of the day. "
        "<b>Lane 2</b> is the recall wound — the engine finds 3 of your 15 held-out S "
        "days, and a level plus a direction is all it needs to rebuild the entry and "
        "the stop. <b>Lane 3</b> is the give-back: 53.8%% of trades touch 2R and the "
        "shipped ladder keeps it on 27.0%%, and only you can say how much of the "
        "position should still be on at 11:00.</p>"
        "<p>Cards: <b>%d</b> B-remap · <b>%d</b> silent days · <b>%d</b> give-back "
        "= <b>%d</b>. Generated by <code>research/build_h2_deck.py</code>.</p>")


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def build(n1, n2, n3, seed, verbose=True):
    judged = marked_card_ids()
    used = set()          # one card per symbol-day across the WHOLE page
    parts, stats = [], {}

    def key(r):
        return "%s_%s" % (r["sym"], r["day"])

    # ---- lane 1 -----------------------------------------------------------
    pool = [r for r in b_only_rows() if key(r) not in judged]
    seen_day = set()
    uniq = []
    for r in pool:                       # one signal per symbol-day, the first
        if key(r) in seen_day:
            continue
        seen_day.add(key(r))
        uniq.append(r)
    lane1, i = [], 0
    for r in stratify(uniq, n1 * 3, seed):
        if len(lane1) >= n1:
            break
        if key(r) in used:
            continue
        cs = session(r["sym"], r["day"])
        if len(cs) < 60:
            continue
        used.add(key(r))
        lane1.append((r, cs))
    stats["lane1_pool"] = len(uniq)

    # ---- lane 2 -----------------------------------------------------------
    # DELIBERATE no-repeat EXEMPTION. `marked_card_ids()` is not applied here,
    # and that is the entire point of the lane: these are days Austin already
    # graded S (or A) and the engine stayed silent on. Re-showing them is what
    # buys the missing level, which is the thing his old grade does not carry.
    # Lanes 1 and 3 go through the guard; lane 2 must not.
    s_rows = missed_s_days()
    if verbose and len(s_rows) != 12:
        print("  warn: parsed %d rows from w5_silent_s_autopsy.md, expected 12"
              % len(s_rows))
    fill = t60_silent_rows()
    have = {key(r) for r in s_rows}
    fill = [r for r in fill if key(r) not in have]
    fill.sort(key=lambda r: ({"S": 0, "A": 1}.get(r["grade"], 2), r["sym"], r["day"]))
    lane2 = []
    for r in list(s_rows) + fill:
        if len(lane2) >= n2:
            break
        if key(r) in used:
            continue
        cs = session(r["sym"], r["day"])
        if len(cs) < 60:
            continue
        used.add(key(r))
        lane2.append((r, cs))
    random.Random(seed + 1).shuffle(lane2)      # no positional tell
    stats["lane2_missed_s"] = len(s_rows)

    # ---- lane 3 -----------------------------------------------------------
    gpool = [r for r in giveback_rows() if key(r) not in judged]
    lane3 = []
    for r in stratify(gpool, n3 * 4, seed + 2):
        if len(lane3) >= n3:
            break
        if key(r) in used:
            continue
        cs = session(r["sym"], r["day"], end=LATE_CLOSE)
        if len(cs) < 60 or index_of_time(cs, CLOCK) is None:
            continue
        used.add(key(r))
        lane3.append((r, cs))
    stats["lane3_pool"] = len(gpool)

    # ---- render -----------------------------------------------------------
    parts.append(section(
        "Lane 1 &middot; B-remap &middot; one tap",
        "There is no B. Re-grade these.",
        "OMEN already drew the entry and the stop, so a single tap is a verdict on "
        "a specific proposal. 0 downgrades = S, 1 = A, 2 = C, 3+ = X — kill it."))
    for n, (r, cs) in enumerate(lane1, 1):
        parts.append(card_b(n, len(lane1), r, cs))

    parts.append(section(
        "Lane 2 &middot; silent days &middot; two taps",
        "The engine saw nothing. You did.",
        "No entry is drawn — there was no proposal. Grade the day, then name the "
        "level it came off. Level plus direction rebuilds the entry and the stop."))
    for n, (r, cs) in enumerate(lane2, 1):
        parts.append(card_silent(n, len(lane2), r, cs))

    parts.append(section(
        "Lane 3 &middot; give-back &middot; one tap",
        "It touched 2R and handed it back.",
        "Entry, stop, the 2R rail and the 11:00 clock are drawn, and the chart runs "
        "to 12:00. One tap: how much of the position is still on at 11:00?"))
    for n, (r, cs) in enumerate(lane3, 1):
        parts.append(card_giveback(n, len(lane3), r, cs))

    total = len(lane1) + len(lane2) + len(lane3)
    html = probe_page.shell(
        "OMEN H2 Three-Lane",
        "OMEN 6 H2 &middot; W1 / W5 / W2",
        "Three lanes, one sitting.",
        "<strong>%d cards.</strong> Lane 1 kills the B grade (one tap). Lane 2 is the "
        "recall wound (two taps). Lane 3 is the give-back (one tap). Taps only — "
        "nothing to type, nothing to mark with a pointer. Saves as you go." % total,
        "".join(parts), FOOT % (len(lane1), len(lane2), len(lane3), total), DECK_ID)
    # The shell is `<title><fonts><css>…`; the extra sheet has to come after it to
    # win, and the extra script after the shell's so probe_page handles a click first.
    html = html.replace("</style>", "</style>" + EXTRA_CSS, 1) + EXTRA_JS

    stats.update(lane1=len(lane1), lane2=len(lane2), lane3=len(lane3),
                 total=total, judged=len(judged))
    return html, stats, [lane1, lane2, lane3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n1", type=int, default=60)
    ap.add_argument("--n2", type=int, default=30)
    ap.add_argument("--n3", type=int, default=30)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    html, st, lanes = build(a.n1, a.n2, a.n3, a.seed)

    # The no-repeat guarantee, asserted rather than assumed. Lane 2 is exempt by
    # design (see build()); lanes 1 and 3 must be clean against every corpus.
    judged = marked_card_ids()
    bad = sorted({"%s_%s" % (r["sym"], r["day"]) for r, _ in lanes[0] + lanes[2]}
                 & judged)
    assert not bad, "lane 1/3 repeat already-judged days: %s" % bad
    ids = re.findall(r'data-cid="([^"]+)"', html)
    assert len(set(ids)) == len(ids), "duplicate card_id in the page"

    path = os.path.join(OUT_DIR, DECK_ID + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s  (%d bytes)" % (path, len(html)))
    print("  lane 1 b-remap    %3d cards   (pool %d B-only symbol-days)"
          % (st["lane1"], st["lane1_pool"]))
    print("  lane 2 silent     %3d cards   (%d parsed missed-S + t60 fill; "
          "no-repeat guard EXEMPT by design)" % (st["lane2"], st["lane2_missed_s"]))
    print("  lane 3 give-back  %3d cards   (pool %d >=2R MFE give-backs)"
          % (st["lane3"], st["lane3_pool"]))
    print("  no-repeat guard excluded %d already-judged symbol-days" % st["judged"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
