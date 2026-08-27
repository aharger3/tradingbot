"""build_omen_test1.py -- OMEN Test 1: 100 charts, graded S/A/C/X, entry and stop marked.

    python research/build_omen_test1.py
    -> research/probes/omen-test-1.html
       research/probes/omen-test-1-manifest.jsonl   (the answer key, OUTSIDE the HTML)

Austin, 2026-08-26:

    "I'm looking for a 100 question multiple choice test of 9:30 to 11 candles with
     the levels I watch, me marking the entry and stop loss, and grading S A C X and
     optional comments. You can mix all types of trades in there including ones that
     the engine doesn't have in its roster. The goal is for me to match with 95
     percent of the S calls, so if you want to change the size of the test for results
     to match that denominator easier, go for it."

WHY 100 AND NOT THE STANDARD'S 60
---------------------------------
`Projects/omen-decks.md` caps a deck at 60 cards and `build_deck.py` enforces it with
a `SystemExit`, because two 120-card decks sat ungraded for a week. That cap is not
overridden here -- `build_deck.py` is untouched on that line. This is a different
instrument with a numeric target attached, and the target sets the size:

    "95% of the S calls" is a fraction whose denominator is the S subset.
    One disagreement costs  1 / N_S.

      N_S = 20  ->  5.0 pts.  95% means 19/20. ONE miss fails. Unreadable.
      N_S = 24  ->  4.2 pts.  (a 60-card test at this S rate)  ONE miss fails.
      N_S = 40  ->  2.5 pts.  TWO misses still pass (38/40 = 95.0%).
      N_S = 50  ->  2.0 pts.  TWO misses pass at 96%, three fail at 94%.

A target that flips on a single card measures noise, not agreement. The build
therefore sizes the *S subset* first and lets the card count follow: 40 cards carry
a grader-S on the engine's own S/A/C ladder, which is the half of the denominator
that is knowable before he marks anything -- and the draw actually lands 50, because
ten of the off-roster days also carry a grader-S. One disagreement therefore costs
2.0 points and the target survives two. 100 cards is what that costs at a mix that
also leaves room for silent days, off-roster structure and easy X calls.

The number on the page is the number the build measured, not this one: `scorebox()`
takes it as an argument and derives the whole paragraph from it.

Finishability -- the real constraint the 60-card cap was protecting -- is bought back
a different way: five numbered parts of 20, each with its own progress bar, each
finishable in about ten minutes, one export for the whole page. And the deck
standard's own economics hold: GRADE is the only required control. Entry, stop and
setup appear only when he grades the chart tradeable, so an X card is one tap.

CARD MIX -- and the off-roster cards are the point of the exercise
-----------------------------------------------------------------
The engine's roster is break-and-retest, one-candle-rule, their confluence, the 84%
re-entry, and the retired FVG/flag detectors. Austin asked for setups it has no
detector for, because those cards are the only way to find a rule that does not exist
yet. Five structural patterns are classified here purely to SELECT days -- never shown
on a card, never named to him:

  gap_fill      opens away from the prior close and walks back to it. PDC is not
                even in the level set the engine draws.
  or_reversal   closes through one side of the opening range, then closes through
                the other. `break_then_rejection` is unreachable in `downgrade.py`
                (p2_threshold_sweep.md), so nothing detects this.
  no_retest     breaks a level with force and never comes back to it. B&R needs the
                retest by construction, so this day is invisible to the roster.
  range_fade    the whole window sits inside the premarket range and both ends get
                worked. Nothing in the roster fades a range.
  double_tap    two touches of the same extreme with a pullback between. Austin
                (rulebook, card 14): a two-candle version "is not an OCR -- that is a
                pivot structure break".

WHERE THE SELECTION BIAS COMES FROM
-----------------------------------
`research/p2_threshold_sweep.md`: the grader agrees with Austin on 21 of 58 cards and
S recall is 12/28. Agreement is the wound, so the draw is biased toward days where
the two are most likely to disagree -- above all the `s_dropped` stratum, the days
`downgrade.py` scores S and `_grade_pa` throws away (`research/g4_dropped_s.md`: the
engine's real entry rule is arrival order, and 96.5% of S setups are dropped by a
candle-shape test). But a test made only of hard cards cannot measure 95% of
anything, so 12 cards come from the engine's own traded S book and 20 from days whose
best signal is a C -- the easy end.

NO REPEATS, IN BOTH DIRECTIONS
------------------------------
Against history: `build_deck.marked_card_ids()`, which reads every mark corpus.
Within this document: a `SYMBOL_DATE` set that every stratum draws behind, plus an
assertion in `verify()` that fails the build if any symbol-day appears twice. The
master homework shipped QQQ 2026-07-20 and QQQ 2026-07-24 on two cards each because
it deduped only against history (G12). Austin's time is the scarce input; a repeat
spends it twice for one answer.

`marked_card_ids()` also had a hole that this build fixed in `build_deck.py`: prefixed
card_ids like `cal_QQQ_2026-06-29_b10` parsed to the key `cal_QQQ`, so all 51 rows of
`marks/probe_master_homework_2026-08-26.jsonl` were invisible to the guard, and the 25
`sr_` rows carried no grade field at all. 633 judged days -> 658.

DELIVERY
--------
`probe_page.py` owns persistence and export -- localStorage per card on every tap,
restore on load, a visible saved indicator, Export -> Copy all / Download .jsonl. It
does NOT use the claude.ai artifact runtime to save answers; that was tried on
2026-08-22 and nothing persisted. Charts are static SVG rendered in Python by
`probe_chart.py`. Entry and stop are captured by TAP, never by pointer -- see
`research/omen_test1.md` for the design and why.
"""
from __future__ import annotations

import collections
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as deck
import probe_chart
import probe_page
from research.t4_engine_recall import (rth_candles, prior_day_levels,
                                       premarket_extremes)

OUT_DIR = os.path.join(HERE, "probes")
# The deck id is a parameter because Test 1 is graded and its HTML is the record
# of what Austin was actually shown. Regenerating over it would destroy that.
# `OMEN_DECK=omen-test-3 python research/build_omen_test1.py` builds the next one.
DECK_ID = os.getenv("OMEN_DECK", "omen-test-2").strip() or "omen-test-2"
OUT_NAME = DECK_ID + ".html"
MANIFEST = DECK_ID + "-manifest.jsonl"
BT2Y = os.path.join(HERE, "bt2y_trades.json")

SESSION_START, SESSION_END = "09:30", "11:00"
BARS = 90                     # 09:30..10:59 inclusive; cards must be exactly this
PART_SIZE = 20
SEED = 1
FROM_DAY = "2025-01-01"       # keep the regime next to the corpus he already graded
MAX_PER_SYMBOL = 8            # so the test is not four symbols wearing a hat

# stratum -> how many cards. The first two are the S denominator (see the header).
QUOTAS = [
    ("s_traded", 12),
    ("s_dropped", 28),
    ("silent", 15),
    ("offroster", 25),
    ("low", 20),
]
N_CARDS = sum(n for _k, n in QUOTAS)

OFFROSTER_PATTERNS = ("gap_fill", "or_reversal", "no_retest", "range_fade", "double_tap")
OFFROSTER_EACH = 5

_ORDER = {"S": 0, "A": 1, "C": 2}


# ---------------------------------------------------------------------------
# bars
# ---------------------------------------------------------------------------

def session(symbol, day):
    cs = rth_candles(symbol, day)
    if not cs:
        return []
    out = []
    for c in cs:
        t = c.timestamp[11:16] if "T" in c.timestamp else c.timestamp[:5]
        if SESSION_START <= t < SESSION_END:
            out.append({"t": t, "o": c.open, "h": c.high, "l": c.low,
                        "c": c.close, "v": c.volume})
    return out


def levels_for(symbol, day, bars):
    pdh, pdl, _pdo, pdc = prior_day_levels(symbol, day)
    pmh, pml = premarket_extremes(symbol, day)
    lv = {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
          "orh": max(b["h"] for b in bars[:5]), "orl": min(b["l"] for b in bars[:5])}
    return lv, pdc


# ---------------------------------------------------------------------------
# off-roster classifiers -- SELECTION ONLY. None of this reaches a card.
# ---------------------------------------------------------------------------

def _touches(bars, price, tol):
    return sum(1 for b in bars if b["l"] - tol <= price <= b["h"] + tol)


def classify(bars, lv, pdc):
    """Which off-roster pattern, if any, this session is. First hit wins."""
    o = bars[0]["o"]
    hi = max(b["h"] for b in bars)
    lo = min(b["l"] for b in bars)
    rng = hi - lo
    if rng <= 0 or o <= 0:
        return None
    tol = rng * 0.05

    # gap_fill -- opens >=0.4% away from the prior close and trades back through it
    if pdc:
        gap = (o - pdc) / pdc
        if abs(gap) >= 0.004 and lo <= pdc <= hi:
            crossed = any(b["l"] <= pdc <= b["h"] for b in bars[3:])
            if crossed:
                return "gap_fill"

    orh, orl = lv["orh"], lv["orl"]
    # or_reversal -- closes through one side of the opening range, then the other
    up = [i for i, b in enumerate(bars) if i >= 5 and b["c"] > orh]
    dn = [i for i, b in enumerate(bars) if i >= 5 and b["c"] < orl]
    if up and dn and (min(dn) > min(up) + 3 or min(up) > min(dn) + 3):
        return "or_reversal"

    # no_retest -- a forceful close through a level that price never revisits
    for name in ("pdh", "pdl", "pmh", "pml", "orh", "orl"):
        p = lv.get(name)
        if p is None or not (lo <= p <= hi):
            continue
        for i in range(5, len(bars) - 20):
            b = bars[i]
            body = abs(b["c"] - b["o"])
            if body < rng * 0.10:
                continue
            broke_up = b["c"] > p and b["o"] <= p
            broke_dn = b["c"] < p and b["o"] >= p
            if not (broke_up or broke_dn):
                continue
            after = bars[i + 1:]
            back = min(abs(x["l"] - p) if broke_up else abs(x["h"] - p) for x in after)
            if broke_up and min(x["l"] for x in after) > p + tol:
                return "no_retest"
            if broke_dn and max(x["h"] for x in after) < p - tol:
                return "no_retest"
            del back

    # range_fade -- contained inside the premarket range, both ends worked twice
    pmh, pml = lv.get("pmh"), lv.get("pml")
    if pmh and pml and pmh > pml:
        if hi <= pmh + tol and lo >= pml - tol and (pmh - pml) > 0:
            if _touches(bars, pmh, tol) >= 2 and _touches(bars, pml, tol) >= 2:
                return "range_fade"

    # double_tap -- two touches of the session extreme >=8 bars apart with a
    # real pullback between. Austin: a two-candle version is a pivot structure
    # break, not an OCR.
    for extreme, key, sign in ((hi, "h", 1), (lo, "l", -1)):
        idx = [i for i, b in enumerate(bars) if abs(b[key] - extreme) <= rng * 0.02]
        if len(idx) >= 2 and idx[-1] - idx[0] >= 8:
            mid = bars[idx[0]:idx[-1] + 1]
            pull = (extreme - min(x["l"] for x in mid)) if sign > 0 else \
                   (max(x["h"] for x in mid) - extreme)
            if pull >= rng * 0.35:
                return "double_tap"
    return None


# ---------------------------------------------------------------------------
# engine index
# ---------------------------------------------------------------------------

def engine_index():
    """(symbol, day) -> {best sgrade, traded?, setups, legacy grades} from the
    committed 2-year replay. Reading the book instead of re-running detection is
    what makes this build cheap; the book is the same one every published number
    in DIRECTION.md comes from."""
    with open(BT2Y, encoding="utf-8") as fh:
        book = json.load(fh)
    by_day = collections.defaultdict(list)
    for row in book["trades"]:
        by_day[(row["sym"], row["day"])].append(row)
    idx = {}
    for key, rows in by_day.items():
        best = min((_ORDER.get(r["sgrade"], 9) for r in rows), default=9)
        idx[key] = {
            "best_sgrade": "SAC"[best] if best < 3 else None,
            "traded": sum(1 for r in rows if r["traded"]),
            "alerts": sum(1 for r in rows if r.get("alert")),
            "signals": len(rows),
            "setups": sorted({r["setup"] for r in rows}),
            "legacy": sorted({r["grade"] for r in rows}),
        }
    return idx, set(book["meta"]["symbols"])


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

def stratum_of(info):
    """The engine-side bucket for a day, from the replay book alone."""
    if info is None:
        return "silent"
    if info["best_sgrade"] == "S":
        return "s_traded" if info["traded"] else "s_dropped"
    if info["best_sgrade"] == "C" or info["best_sgrade"] is None:
        return "low"
    return "mid"          # best is A -- not drawn directly, used only for off-roster


def select():
    idx, bt_symbols = engine_index()
    judged = deck.marked_card_ids()

    pool = [(s, d) for s, d in deck.universe()
            if s in bt_symbols and d >= FROM_DAY and "%s_%s" % (s, d) not in judged]
    rng = random.Random(SEED)
    rng.shuffle(pool)

    want = dict(QUOTAS)
    off_want = {p: OFFROSTER_EACH for p in OFFROSTER_PATTERNS}
    picked = {k: [] for k, _n in QUOTAS}
    used_days: set[str] = set()          # the within-document guarantee
    per_symbol: collections.Counter = collections.Counter()
    probed = 0

    def full():
        return all(len(picked[k]) >= want[k] for k in want)

    for sym, day in pool:
        if full():
            break
        key = "%s_%s" % (sym, day)
        if key in used_days or per_symbol[sym] >= MAX_PER_SYMBOL:
            continue
        info = idx.get((sym, day))
        strat = stratum_of(info)
        # cheap rejection before touching disk: is any bucket this day could land
        # in still open?
        off_open = any(v > 0 for v in off_want.values()) and \
            len(picked["offroster"]) < want["offroster"]
        if not off_open and (strat not in want or len(picked[strat]) >= want[strat]):
            continue

        bars = session(sym, day)
        probed += 1
        if len(bars) != BARS:
            continue
        lv, pdc = levels_for(sym, day, bars)
        if lv["pdh"] is None or lv["pmh"] is None:
            continue                      # a card without its levels cannot be graded

        pattern = classify(bars, lv, pdc)
        # Off-roster first: a day the engine never traded AND that matches a
        # pattern nothing in the roster detects.
        if (pattern and off_want.get(pattern, 0) > 0
                and len(picked["offroster"]) < want["offroster"]
                and (info is None or not info["traded"])):
            off_want[pattern] -= 1
            picked["offroster"].append((sym, day, bars, lv, pdc, info, pattern))
        elif strat in want and len(picked[strat]) < want[strat]:
            picked[strat].append((sym, day, bars, lv, pdc, info, pattern))
        else:
            continue
        used_days.add(key)
        per_symbol[sym] += 1

    for k, n in QUOTAS:
        assert len(picked[k]) == n, (
            "stratum %s short: %d of %d (probed %d days)" % (k, len(picked[k]), n, probed))
    return picked, judged, probed, off_want


# ---------------------------------------------------------------------------
# stop candidates
# ---------------------------------------------------------------------------

def stop_candidates(bars, lv):
    """Structural prices Austin could actually be stopping behind, built at BUILD
    time so every chip is in the served markup and survives a reload untouched.

    Deliberately not a numeric input: a price field on a phone is a keyboard, and
    a keyboard is the thing that stops a card getting finished. The free-text
    escape hatch on the same question covers a stop none of these express.
    """
    n = len(bars)
    hi = max(b["h"] for b in bars)
    lo = min(b["l"] for b in bars)
    rng = (hi - lo) or 1.0
    out = []

    for name in ("pdh", "pdl", "pmh", "pml", "orh", "orl"):
        p = lv.get(name)
        if p is not None and lo - rng * 0.15 <= p <= hi + rng * 0.15:
            out.append((round(p, 2), name.upper()))

    for i in range(2, n - 2):
        w = bars[i - 2:i + 3]
        if bars[i]["h"] >= max(x["h"] for x in w) and bars[i]["h"] > bars[i]["o"]:
            out.append((round(bars[i]["h"], 2), "swing high %s" % bars[i]["t"]))
        if bars[i]["l"] <= min(x["l"] for x in w) and bars[i]["l"] < bars[i]["o"]:
            out.append((round(bars[i]["l"], 2), "swing low %s" % bars[i]["t"]))

    out.append((round(hi, 2), "session high"))
    out.append((round(lo, 2), "session low"))

    # thin: keep the widest spread of distinct prices, nearest-first labels win
    out.sort(key=lambda t: -t[0])
    keep, last = [], None
    for price, label in out:
        if last is not None and abs(last - price) < rng * 0.012:
            continue
        keep.append((price, label))
        last = price
    if len(keep) > 18:
        step = len(keep) / 18.0
        keep = [keep[int(i * step)] for i in range(18)]
    return keep


# ---------------------------------------------------------------------------
# card
# ---------------------------------------------------------------------------

LEGEND = ('<div class="legend">'
          '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
          '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> premarket 04:00-09:29</span>'
          '<span><b style="color:var(--lvl-or)">- - ORH/ORL</b> first 5 RTH bars</span>'
          '<span><b style="color:var(--entry)">&#9650; your entry</b></span>'
          '<span><b style="color:var(--stop)">your stop</b></span></div>')

GRADE_OPTS = [
    ("S", "S &mdash; clean"),
    ("A", "A &mdash; one downgrade"),
    ("C", "C &mdash; two downgrades"),
    ("X", "X &mdash; no trade here"),
]

WHY_OPTS = [
    ("no_level", "No level"), ("chop", "Chop"), ("too_extended", "Too extended"),
    ("gap_too_big", "Gap too big"), ("low_volume", "Low volume"),
    ("news_risk", "News risk"), ("no_setup", "Nothing set up"), ("other", "Other"),
]

SETUP_OPTS = [
    ("BR", "BR &mdash; break &amp; retest"),
    ("OCR", "OCR &mdash; one candle rule"),
    ("BR+OCR", "BR + OCR"),
    ("84", "84% re-entry"),
    ("other", "Something else"),
]

BLOCKS = [("%02d:%02d" % (9 + (30 + b * 15) // 60, (30 + b * 15) % 60),
           "%02d:%02d" % (9 + (44 + b * 15) // 60, (44 + b * 15) % 60))
          for b in range(BARS // 15)]


def block_opts():
    return [(str(i), "%s&ndash;%s" % (a, b)) for i, (a, b) in enumerate(BLOCKS)]


def minute_opts():
    return [(str(i), "+%d" % i) for i in range(15)]


def card_html(idx, total, part, sym, day, bars, lv, pdc):
    chart = probe_chart.render(bars, lv, [], "%s %s" % (sym, day), interactive=True)
    stops = stop_candidates(bars, lv)
    stop_chips = "".join(
        '<button class="chip stopchip" type="button" data-v="%.2f" data-src="%s" '
        'aria-pressed="false">%.2f<small>%s</small><span class="risk"></span></button>'
        % (p, lab, p, lab) for p, lab in stops)

    closes = json.dumps([round(b["c"], 2) for b in bars], separators=(",", ":"))
    export = json.dumps({"symbol": sym, "date": day, "part": part},
                        separators=(",", ":"), sort_keys=True)

    head = ('<header><span class="idx">%03d/%03d</span><span class="tick">%s</span>'
            '<span class="when">%s</span>'
            '<span class="tags"><span class="tag">09:30&ndash;11:00</span>'
            '<span class="done-dot"></span></span></header>' % (idx, total, sym, day))

    return "".join([
        '<article class="card tcard" data-cid="t1_%s_%s" data-grade="" data-done="0" '
        'data-g="" data-closes=\'%s\' data-export=\'%s\'>' % (sym, day, closes, export),
        head,
        '<div class="chartwrap">%s</div>' % chart, LEGEND,
        probe_page.question(
            "grade", "Grade this chart.",
            "S clean &middot; A one downgrade &middot; C two &middot; "
            "<b>X = no trade here at all</b>. Everything else on this card only "
            "appears if you grade it tradeable.",
            GRADE_OPTS),
        probe_page.question(
            "why", "Why not?", "One tap. Optional.", WHY_OPTS,
            required=False, tone="veto"),
        probe_page.question(
            "eblock", "Entry &mdash; which quarter hour?",
            "Tap the block, then the minute inside it. The chart shades the block "
            "and drops the line on the bar, so you can nudge until it sits right.",
            block_opts(), required=False),
        probe_page.question(
            "emin", "&hellip; and which minute?",
            "These are minutes inside the block you picked &mdash; they relabel to "
            "the clock as soon as one is chosen. Entry price defaults to that "
            "candle&rsquo;s close &mdash; if you got in before it closed, type the "
            "price you actually filled at.", minute_opts(),
            required=False,
            note_placeholder="(optional) the price you actually filled at, if "
                             "you entered before the candle closed"),
        '<div class="q readout" data-when="trade"><p class="hint" '
        'data-role="entryout">no entry marked yet</p></div>',
        '<section class="q" data-q="stop" data-multi="0" data-required="0" '
        'data-when="trade"><h3>Stop.</h3><p class="hint">Structure prices off this '
        'chart &mdash; levels, swings, the session extremes. Risk fills in once the '
        'entry is set.</p><div class="chips stoprail">%s</div>'
        '<textarea class="note" data-note="stop" placeholder="(optional) exact stop '
        'price if none of these is it"></textarea></section>' % stop_chips,
        probe_page.question(
            "setup", "What kind of trade is it?",
            "If it is none of the four, say <b>Something else</b> and one line about "
            "what it is &mdash; that line is the whole reason this test mixes in "
            "setups the engine has no detector for.",
            SETUP_OPTS, required=False,
            note_placeholder="(optional) what the setup actually was"),
        probe_page.question(
            "comment", "Anything else?", "Optional, one line.", [],
            required=False, note_placeholder="(optional)"),
        "</article>",
    ])


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------

EXTRA_CSS = """
<style>
.sec{display:block}
/* 100 charts is ~20,000 SVG elements. Let the browser skip the ones nobody is
   looking at -- without this a mid-range phone stutters on every scroll. */
.tcard{content-visibility:auto; contain-intrinsic-size:auto 900px}
.sechead{
  margin:30px 0 16px; padding:15px 17px; border-radius:10px;
  background:var(--surface-2); border:1px solid var(--rule-2); scroll-margin-top:64px;
}
.sechead .kicker{
  font-family:"IBM Plex Mono",monospace; font-size:10.5px; font-weight:600;
  letter-spacing:.14em; text-transform:uppercase; color:var(--accent);
  display:block; margin:0 0 5px;
}
.sechead h2{
  font-family:"IBM Plex Serif",Georgia,serif; font-weight:600; font-size:21px;
  line-height:1.2; margin:0 0 6px; color:var(--ink);
}
.sechead p{margin:0; font-size:13.5px; color:var(--ink-2); max-width:66ch}
.secprog{display:flex; align-items:center; gap:9px; margin:11px 0 0}
.secprog .seccount{
  font-family:"IBM Plex Mono",monospace; font-size:12px; font-weight:600;
  font-variant-numeric:tabular-nums; color:var(--ink-2); white-space:nowrap;
}
.secprog .sectrack{
  flex:1 1 60px; height:4px; background:var(--rule-2); border-radius:2px; overflow:hidden;
}
.secprog .secfill{height:100%; width:0%; background:var(--accent); transition:width .25s ease}
.sec[data-complete="1"] .sechead{border-color:var(--accent)}
.sec[data-complete="1"] .sechead .kicker::after{content:" — done"; color:var(--accent)}

/* the scoring panel -- he has to see the arithmetic before he starts */
.scorebox{
  background:var(--surface); border:1px solid var(--accent); border-radius:10px;
  padding:15px 17px; margin:18px 0 4px; box-shadow:var(--shadow);
}
.scorebox h2{
  font-family:"IBM Plex Serif",Georgia,serif; font-size:17px; font-weight:600;
  margin:0 0 7px; color:var(--ink);
}
.scorebox p{margin:0 0 8px; font-size:13.5px; color:var(--ink-2); max-width:68ch}
.scorebox p:last-child{margin-bottom:0}
.scorebox b{color:var(--ink)}
.scorebox code, .sechead code{
  font-family:"IBM Plex Mono",monospace; font-size:12.5px;
  background:var(--surface-2); padding:1px 5px; border-radius:4px;
}
.gradekey{
  display:flex; flex-wrap:wrap; gap:8px; margin:10px 0 0; padding:0; list-style:none;
  font-size:13px;
}
.gradekey li{
  border:1px solid var(--rule-2); border-radius:8px; padding:7px 10px;
  background:var(--surface-2); flex:1 1 150px;
}
.gradekey b{
  font-family:"IBM Plex Mono",monospace; font-size:14px; color:var(--accent);
  margin-right:5px;
}
.gradekey li.xkey b{color:var(--stop)}

/* progressive disclosure: grade first, everything else only if tradeable */
.tcard[data-g=""] [data-when="trade"],
.tcard[data-g=""] .q[data-q="eblock"],
.tcard[data-g=""] .q[data-q="emin"],
.tcard[data-g=""] .q[data-q="setup"],
.tcard[data-g=""] .q[data-q="comment"],
.tcard[data-g=""] .q[data-q="why"],
.tcard[data-g="X"] [data-when="trade"],
.tcard[data-g="X"] .q[data-q="eblock"],
.tcard[data-g="X"] .q[data-q="emin"],
.tcard[data-g="X"] .q[data-q="setup"]{display:none}
.tcard[data-g="S"] .q[data-q="why"],
.tcard[data-g="A"] .q[data-q="why"],
.tcard[data-g="C"] .q[data-q="why"]{display:none}

.q[data-q="grade"] .chip{flex:1 1 calc(50% - 4px); font-weight:600}
.q[data-q="grade"] .chip[data-v="X"][aria-pressed="true"]{
  background:var(--stop); border-color:var(--stop); color:#fff;
}
.q[data-q="emin"] .chips{gap:6px}
.q[data-q="emin"] .chip{
  flex:0 0 auto; min-width:52px; text-align:center;
  font-family:"IBM Plex Mono",monospace; font-weight:600;
}
.q[data-q="eblock"] .chip{
  flex:1 1 calc(33.333% - 5px); text-align:center;
  font-family:"IBM Plex Mono",monospace; font-size:12.5px;
}
.readout{border-top:1px solid var(--rule); padding:11px 16px}
.readout .hint{
  margin:0; font-family:"IBM Plex Mono",monospace; font-size:13px; color:var(--ink-2);
}
.readout .hint b{color:var(--entry)}
.readout .hint i{color:var(--stop); font-style:normal}
/* No nested scroller. A scroll container inside a scrolling page is the single
   most reliable way to lose a tap on a phone, so the rail is laid out two-up and
   allowed to be tall. */
.stopchip{
  flex:1 1 calc(50% - 4px); font-family:"IBM Plex Mono",monospace; font-weight:600;
  display:flex; flex-direction:column; align-items:flex-start; gap:1px;
  line-height:1.25;
}
.stopchip small{
  font-family:"IBM Plex Sans",sans-serif; font-weight:400; font-size:11px;
  color:var(--ink-3); letter-spacing:.01em;
}
.stopchip[aria-pressed="true"]{background:var(--stop); border-color:var(--stop); color:#fff}
.stopchip[aria-pressed="true"] small{color:rgba(255,255,255,.8)}
.stopchip .risk{font-size:11px; color:var(--ink-3); font-weight:500}
.stopchip .risk:empty{display:none}
.stopchip[aria-pressed="true"] .risk{color:rgba(255,255,255,.85)}

/* the marks the page draws onto the served SVG */
.chart .usermark .band{fill:var(--accent); opacity:.09}
.chart .usermark .uentry{stroke:var(--entry); stroke-width:1.4}
.chart .usermark .ubar{stroke:var(--entry); stroke-width:1; stroke-dasharray:2 3; opacity:.75}
.chart .usermark .uentry-t{
  font-family:"IBM Plex Mono",monospace; font-size:9px; font-weight:600; fill:var(--entry);
}
.chart .usermark .ustop{stroke:var(--stop); stroke-width:1.4; stroke-dasharray:4 3}
.chart .usermark .ustop-t{
  font-family:"IBM Plex Mono",monospace; font-size:9px; font-weight:600; fill:var(--stop);
}
.endbar{
  display:flex; gap:8px; flex-wrap:wrap; align-items:center;
  margin:18px 0 0; padding-top:14px; border-top:1px solid var(--rule);
}
@media (max-width:520px){
  .sechead{padding:13px 13px}
  .sechead h2{font-size:19px}
  .q[data-q="emin"] .chip{min-width:46px}
}
</style>
"""

EXTRA_JS = r"""
<script>
/* OMEN Test 1 -- entry/stop capture, chart feedback, per-part progress.

   Storage and export belong to probe_page.js and nothing here touches them.
   Entry and stop are ordinary .chip buttons inside ordinary .q sections, so
   probe_page saves and restores them with the same code it uses for every other
   answer. This file only READS those chips and moves elements that are already
   in the served SVG. That is the whole reason entry/stop survive a reload here
   when canvas marking never has.  */
(function(){
  var BARS = __BARS__;

  function each(list, fn){ Array.prototype.forEach.call(list, fn); }
  function pressed(card, q){
    var el = card.querySelector('.q[data-q="' + q + '"] .chip[aria-pressed="true"]');
    return el;
  }
  function times(i){
    var m = 570 + i;                        /* 09:30 == minute 570 */
    var h = Math.floor(m / 60), mm = m % 60;
    return (h < 10 ? '0' : '') + h + ':' + (mm < 10 ? '0' : '') + mm;
  }

  /* ---- the one place a card's marks are read out of the DOM ---- */
  function mark(card){
    var out = {};
    var g = pressed(card, 'grade');
    if (g) out.grade = g.getAttribute('data-v');
    var closes;
    try { closes = JSON.parse(card.getAttribute('data-closes') || '[]'); }
    catch (e) { closes = []; }

    var b = pressed(card, 'eblock'), m = pressed(card, 'emin');
    if (b) out.block = parseInt(b.getAttribute('data-v'), 10);
    if (b && m){
      var i = out.block * 15 + parseInt(m.getAttribute('data-v'), 10);
      if (i >= 0 && i < BARS){
        out.entry_i = i;
        out.entry_t = times(i);
        /* The picked bar's close is the DEFAULT fill, not the only one. Austin
           enters before the close -- "as candle forming not HOD/LOD" -- and the
           old code wrote closes[i] unconditionally, so every entry in the corpus
           read as an at-close fill by construction and the question could not be
           answered from the data (research/p25_midcandle_entry.md). The close is
           kept as bar_close_p so nothing that compared against it breaks.
           Same typed-price escape hatch the stop has had all along. */
        out.bar_close_p = closes[i];
        out.entry_p = closes[i];
        out.entered_before_close = false;
        var en = card.querySelector('.q[data-q="emin"] textarea.note');
        if (en){
          var etyped = parseFloat(String(en.value).replace(/[^0-9.\-]/g, ''));
          if (isFinite(etyped) && etyped > 0){
            out.entry_p = etyped;
            out.entered_before_close = etyped !== closes[i];
          }
        }
      }
    }

    var s = pressed(card, 'stop');
    if (s){
      out.stop_p = parseFloat(s.getAttribute('data-v'));
      out.stop_src = s.getAttribute('data-src');
    }
    /* typed price wins over the rail -- it is the escape hatch, so it must */
    var t = card.querySelector('.q[data-q="stop"] textarea.note');
    if (t){
      var typed = parseFloat(String(t.value).replace(/[^0-9.\-]/g, ''));
      if (isFinite(typed) && typed > 0){ out.stop_p = typed; out.stop_src = 'typed'; }
    }
    var st = pressed(card, 'setup');
    if (st) out.setup = st.getAttribute('data-v');
    if (out.entry_p != null && out.stop_p != null){
      out.side = out.stop_p < out.entry_p ? 'L' : 'S';
      out.risk = Math.round(Math.abs(out.entry_p - out.stop_p) * 100) / 100;
    }
    return out;
  }

  /* ---- paint the served SVG placeholders ---- */
  function paint(card){
    var mk = mark(card);
    card.setAttribute('data-g', mk.grade || '');

    var svg = card.querySelector('svg.chart');
    if (!svg) return;
    var n = +svg.getAttribute('data-n'), padl = +svg.getAttribute('data-padl'),
        padt = +svg.getAttribute('data-padt'), pw = +svg.getAttribute('data-plotw'),
        ph = +svg.getAttribute('data-ploth'), lo = +svg.getAttribute('data-lo'),
        hi = +svg.getAttribute('data-hi');
    var span = (hi - lo) || 1;
    function X(i){ return padl + (i + 0.5) * pw / n; }
    function Y(p){                              /* clamp, never rescale */
      var y = padt + (hi - p) * ph / span;
      return Math.max(padt, Math.min(padt + ph, y));
    }
    function set(el, on, attrs){
      if (!el) return;
      if (!on){ el.setAttribute('hidden', ''); return; }
      el.removeAttribute('hidden');
      for (var k in attrs) el.setAttribute(k, attrs[k]);
    }

    var tradeable = mk.grade && mk.grade !== 'X';
    var band = svg.querySelector('.band');
    set(band, tradeable && mk.block != null,
        {x: X(mk.block * 15) - pw / n / 2, width: pw * 15 / n});

    var showE = tradeable && mk.entry_p != null;
    set(svg.querySelector('.uentry'), showE, {y1: Y(mk.entry_p), y2: Y(mk.entry_p)});
    set(svg.querySelector('.ubar'), showE, {x1: X(mk.entry_i), x2: X(mk.entry_i)});
    var et = svg.querySelector('.uentry-t');
    set(et, showE, {y: Y(mk.entry_p) + 3.4});
    if (showE && et) et.textContent = 'ENTRY ' + mk.entry_p.toFixed(2);

    var showS = tradeable && mk.stop_p != null && isFinite(mk.stop_p);
    set(svg.querySelector('.ustop'), showS, {y1: Y(mk.stop_p), y2: Y(mk.stop_p)});
    var stt = svg.querySelector('.ustop-t');
    set(stt, showS, {y: Y(mk.stop_p) + 3.4});
    if (showS && stt) stt.textContent = 'STOP ' + mk.stop_p.toFixed(2);

    /* readout */
    var ro = card.querySelector('[data-role="entryout"]');
    if (ro){
      if (!showE){
        ro.innerHTML = 'no entry marked yet &mdash; tap a quarter hour, then a minute';
      } else {
        var s = '<b>entry ' + mk.entry_t + ' @ ' + mk.entry_p.toFixed(2) + '</b>';
        if (showS){
          s += ' &nbsp;·&nbsp; <i>stop ' + mk.stop_p.toFixed(2) + '</i>' +
               ' &nbsp;·&nbsp; risk ' + mk.risk.toFixed(2) +
               ' &nbsp;·&nbsp; ' + (mk.side === 'L' ? 'long' : 'short');
        } else {
          s += ' &nbsp;·&nbsp; no stop yet';
        }
        ro.innerHTML = s;
      }
    }

    /* the minute chips are static `+n` offsets in the markup so they persist and
       restore untouched; relabel them to the real clock once the block is known */
    each(card.querySelectorAll('.q[data-q="emin"] .chip'), function(chip){
      var off = parseInt(chip.getAttribute('data-v'), 10);
      chip.textContent = (mk.block == null) ? ('+' + off) : times(mk.block * 15 + off);
    });

    /* risk annotation on every stop chip, once the entry is known */
    each(card.querySelectorAll('.stopchip'), function(chip){
      var r = chip.querySelector('.risk');
      if (!r) return;
      if (!showE){ r.textContent = ''; return; }
      var p = parseFloat(chip.getAttribute('data-v'));
      var d = p - mk.entry_p;
      if (Math.abs(d) < 0.005){ r.textContent = 'at entry'; return; }
      r.textContent = (d < 0 ? 'long ' : 'short ') + Math.abs(d).toFixed(2);
    });
  }

  /* ---- per-part progress ---- */
  function tally(){
    each(document.querySelectorAll('.sec'), function(sec){
      var cs = sec.querySelectorAll('.card'), done = 0;
      each(cs, function(c){ if (c.getAttribute('data-done') === '1') done++; });
      var cnt = sec.querySelector('.seccount');
      if (cnt) cnt.textContent = done + ' / ' + cs.length;
      var fill = sec.querySelector('.secfill');
      if (fill) fill.style.width = (cs.length ? done * 100 / cs.length : 0) + '%';
      sec.setAttribute('data-complete', (cs.length && done === cs.length) ? '1' : '0');
    });
  }

  /* probe_page.js registered its listeners first, so by the time these run the
     chip it just toggled already carries its new aria-pressed and the card its
     refreshed data-done. */
  document.addEventListener('click', function(e){
    if (!e.target.closest) return;
    if (e.target.closest('.exportjump')){
      var b = document.getElementById('exportbtn');
      if (b) b.click();
      return;
    }
    var card = e.target.closest('.card');
    if (card) paint(card);
    tally();
  });
  document.addEventListener('input', function(e){
    var card = e.target.closest && e.target.closest('.card');
    if (card) paint(card);
    tally();
  });

  /* export: promote the taps to top-level fields so a row joins back to bars
     without anyone having to re-derive it from `answers`. */
  window.probeRow = function(card, row){
    var mk = mark(card);
    if (mk.grade){
      row.grade = mk.grade;
      /* the historical corpus spells "no trade" as `none`; keep one word for
         one meaning so a single parser reads this file and every older one */
      row.grade_std = mk.grade === 'X' ? 'none' : mk.grade;
    }
    ['entry_i', 'entry_t', 'entry_p', 'bar_close_p', 'entered_before_close',
     'stop_p', 'stop_src', 'side', 'setup']
      .forEach(function(k){ if (mk[k] != null) row[k] = mk[k]; });
  };

  each(document.querySelectorAll('.card'), paint);   /* repaint restored answers */
  tally();
})();
</script>
"""


def part_section(num, cards, first, last):
    return ('<section class="sec" data-complete="0" id="part%d">'
            '<div class="sechead"><span class="kicker">Part %d of %d '
            '&middot; cards %d&ndash;%d &middot; ~10 min</span>'
            '<h2>Part %d</h2>'
            '<p>Stop anywhere. Everything you have tapped is already saved, and '
            '<b>Export</b> works on a half-finished page exactly as well as on a '
            'finished one.</p>'
            '<div class="secprog"><span class="seccount">0 / %d</span>'
            '<span class="sectrack"><span class="secfill"></span></span></div>'
            '</div>%s</section>'
            % (num, num, N_CARDS // PART_SIZE, first, last, num,
               len(cards), "".join(cards)))


def scorebox(grader_s):
    """The denominator arithmetic, above the first card, because a target he
    cannot read is a target he cannot hit. ``grader_s`` is measured from the draw,
    never assumed -- a number on this page that the build did not produce is the
    exact failure mode CLAUDE.md's "if you publish a number, commit the script"
    rule exists to stop."""
    def tolerance(n):
        """How many disagreements a denominator of n still clears 95% with."""
        k = 0
        while n and (n - (k + 1)) * 100.0 / n >= 95.0:
            k += 1
        return k

    pt = 100.0 / grader_s
    tol = tolerance(grader_s)
    small = max(1, int(round(grader_s * 60.0 / N_CARDS)))   # same mix at deck size
    small_tol = tolerance(small)
    return (
        '<div class="scorebox">'
        '<h2>How this is scored, before you start</h2>'
        '<p>You asked to match on <b>95%% of the S calls</b>. That fraction is only '
        'as readable as its denominator, so this test is sized around the '
        'denominator rather than the other way round.</p>'
        '<p><b>%d cards.</b> <b>%d</b> of them are days the engine&rsquo;s own S/A/C '
        'grader already calls <code>S</code> &mdash; that is the half of the '
        'denominator I know before you touch it. Every S you add from the other %d '
        'cards grows it further, which only makes the target easier to read.</p>'
        '<p>At a denominator of <b>%d</b>, one disagreement costs <b>%.1f points</b>, '
        'so the target survives <b>%d</b> of them: <code>%d/%d = %.1f%%</code> passes, '
        '<code>%d/%d = %.1f%%</code> fails. Cut this to the 60-card deck standard and '
        'the same mix carries about <b>%d</b> S cards &mdash; one disagreement costs '
        '%.1f points and the target survives only <b>%d</b>, so a single chart decides '
        'the result. That is why this is longer than the standard allows, and it is '
        'the only reason.</p>'
        '<ul class="gradekey">'
        '<li><b>S</b>clean &mdash; nothing tripped</li>'
        '<li><b>A</b>one downgrade</li>'
        '<li><b>C</b>two downgrades (the floor)</li>'
        '<li class="xkey"><b>X</b><b style="color:var(--stop)">no trade here at '
        'all.</b> On the engine&rsquo;s old ladder X meant &ldquo;it should not have '
        'fired&rdquo;. Here you are grading a <i>chart</i>, not an engine output, so X '
        'is simply your <code>none</code>: you would not have taken anything in this '
        'window.</li>'
        '</ul>'
        '<p style="margin-top:10px">Only the grade is required. Tap <b>X</b> and the '
        'card is finished in one tap. Entry, stop and setup appear only once you grade '
        'a chart tradeable.</p>'
        '</div>'
        % (N_CARDS, grader_s, N_CARDS - grader_s, grader_s, pt, tol,
           grader_s - tol, grader_s, (grader_s - tol) * 100.0 / grader_s,
           grader_s - tol - 1, grader_s, (grader_s - tol - 1) * 100.0 / grader_s,
           small, 100.0 / small, small_tol))


def build():
    picked, judged, probed, off_left = select()

    rows = []
    for strat, _n in QUOTAS:
        for sym, day, bars, lv, pdc, info, pattern in picked[strat]:
            rows.append({"symbol": sym, "day": day, "bars": bars, "lv": lv,
                         "pdc": pdc, "info": info, "pattern": pattern,
                         "stratum": strat})
    rng = random.Random(SEED + 1)
    rng.shuffle(rows)                       # no positional tell by stratum

    cards, manifest = [], []
    for i, r in enumerate(rows, 1):
        part = (i - 1) // PART_SIZE + 1
        cards.append(card_html(i, len(rows), part, r["symbol"], r["day"],
                               r["bars"], r["lv"], r["pdc"]))
        info = r["info"] or {}
        manifest.append({
            "card_id": "t1_%s_%s" % (r["symbol"], r["day"]),
            "symbol": r["symbol"], "date": r["day"], "test": DECK_ID,
            "part": part, "n": i,
            "stratum": r["stratum"], "offroster_pattern": r["pattern"],
            "engine_best_sgrade": info.get("best_sgrade"),
            "engine_traded": info.get("traded", 0),
            "engine_signals": info.get("signals", 0),
            "engine_setups": info.get("setups", []),
            "engine_legacy_grades": info.get("legacy", []),
        })

    parts = []
    for p in range(N_CARDS // PART_SIZE):
        chunk = cards[p * PART_SIZE:(p + 1) * PART_SIZE]
        parts.append(part_section(p + 1, chunk, p * PART_SIZE + 1,
                                  p * PART_SIZE + len(chunk)))

    foot = ("<h2>Your answers cannot go anywhere</h2>"
            "<p>Every tap writes to this browser the moment you make it. Close the tab, "
            "lose the battery, come back next week &mdash; it is all still here, "
            "including the entry and the stop. The indicator at the top says "
            "<code>saved</code> each time it lands, and if your browser ever refuses to "
            "store it, that indicator turns red and says so. It does not fail "
            "quietly.</p>"
            "<p>When you are done &mdash; or partway, it does not matter &mdash; hit "
            "<b>Export</b>, then <b>Copy all</b>, and paste it into the chat. The box is "
            "an ordinary editable text box, so ctrl/cmd+A then ctrl/cmd+C works even "
            "where the button is blocked. <b>Download .jsonl</b> works too where the "
            "browser allows it.</p>"
            "<p>Not one of these %d charts is a day you have judged before, in any file "
            "I hold &mdash; %d already-judged symbol-days were removed from the pool "
            "before the draw, and no symbol-day appears on two cards.</p>"
            '<div class="endbar">'
            '<button class="jump exportjump" type="button">Export &amp; copy</button>'
            '<span class="hint">or scroll back up &mdash; the bar follows you</span>'
            "</div>" % (N_CARDS, len(judged)))

    grader_s = sum(1 for r in rows if (r["info"] or {}).get("best_sgrade") == "S")

    html = probe_page.shell(
        "OMEN Test 1",
        "OMEN &middot; test 1",
        "One hundred charts. Grade, entry, stop.",
        "09:30&ndash;11:00, one-minute candles, PDH/PDL, PMH/PML and ORH/ORL drawn. "
        "Grade every chart <strong>S / A / C / X</strong>; on the ones you would trade, "
        "mark <strong>where you got in</strong> and <strong>where your stop was</strong>. "
        "Five parts of twenty. It saves as you go, and every control is a tap.",
        EXTRA_CSS + scorebox(grader_s) + "".join(parts), foot, DECK_ID)
    html += EXTRA_JS.replace("__BARS__", str(BARS))

    stats = {
        "cards": len(rows),
        "judged_excluded": len(judged),
        "probed": probed,
        "strata": collections.Counter(r["stratum"] for r in rows),
        "patterns": collections.Counter(r["pattern"] for r in rows
                                        if r["stratum"] == "offroster"),
        "symbols": collections.Counter(r["symbol"] for r in rows),
        "offroster_unfilled": {k: v for k, v in off_left.items() if v},
        "grader_s": grader_s,
    }
    return html, manifest, stats, judged


CID_RE = re.compile(r'<article class="card tcard" data-cid="([^"]+)"')


def verify(html, manifest, judged):
    """Fail loudly. Every assertion here is a failure this project has actually had."""
    cids = CID_RE.findall(html)
    assert len(cids) == N_CARDS, "%d cards in HTML, expected %d" % (len(cids), N_CARDS)

    dupes = sorted({c for c in cids if cids.count(c) > 1})
    assert not dupes, "duplicate data-cid -- two cards share a save slot: %s" % dupes

    # G12: the master homework asked QQQ 2026-07-20 and 2026-07-24 twice each
    # because it deduped only against history. Dedupe WITHIN the document too.
    days = ["%s_%s" % (m["symbol"], m["date"]) for m in manifest]
    twice = sorted({d for d in days if days.count(d) > 1})
    assert not twice, "symbol-day on two cards: %s" % twice

    repeats = sorted(set(days) & judged)
    assert not repeats, "test repeats already-judged days: %s" % repeats

    # delivery contract
    export = re.search(r'<textarea id="out"[^>]*>', html)
    assert export, "no export textarea"
    assert "readonly" not in html.lower(), "a readonly attribute leaked into the page"
    assert "localStorage.setItem" in html, "no localStorage save"
    assert 'id="exportbtn"' in html, "no #exportbtn"
    assert 'id="saved"' in html, "no saved indicator"
    assert "<canvas" not in html.lower(), "charts must be static SVG, not canvas"
    assert "window.claude" not in html or "artifact" not in html.split("window.claude")[1][:400], \
        "page leans on the artifact capability for persistence"

    # every card must be countable, and must carry the four controls
    for block in html.split('<article class="card tcard"')[1:]:
        card = block.split("</article>")[0]
        head = card[:80]
        for need in ('data-q="grade"', 'data-q="eblock"', 'data-q="emin"',
                     'data-q="stop"', 'data-q="setup"'):
            assert need in card, "card missing %s: %s" % (need, head)
        assert card.count('data-required="1"') == 1, (
            "exactly one required question per card (grade): %s" % head)
        assert 'data-q="grade" data-multi="0" data-required="1"' in card, (
            "grade must be the required one: %s" % head)
        assert 'class="usermark"' in card, "no mark layer on the chart: %s" % head
        assert card.count('data-v="X"') == 1, "no X grade option: %s" % head
    return cids


def main():
    html, manifest, stats, judged = build()
    verify(html, manifest, judged)

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, OUT_NAME)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    man_path = os.path.join(OUT_DIR, MANIFEST)
    with open(man_path, "w", encoding="utf-8") as fh:
        for row in manifest:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    print("wrote %s  (%d bytes, %d cards, %d parts of %d)"
          % (path, len(html), stats["cards"], N_CARDS // PART_SIZE, PART_SIZE))
    print("wrote %s  (answer key, OUTSIDE the html)" % man_path)
    print("  strata:   " + "  ".join("%s=%d" % kv for kv in sorted(stats["strata"].items())))
    print("  off-roster:" + "  ".join(" %s=%d" % kv for kv in sorted(stats["patterns"].items())))
    if stats["offroster_unfilled"]:
        print("  UNFILLED off-roster quotas: %s" % stats["offroster_unfilled"])
    print("  grader-S cards: %d  ->  one disagreement = %.1f points of the 95%% target"
          % (stats["grader_s"], 100.0 / stats["grader_s"]))
    print("  no-repeat: %d judged symbol-days excluded; %d days probed; "
          "0 repeats in-document" % (stats["judged_excluded"], stats["probed"]))
    print("  symbols:  %d distinct, max %d on one symbol"
          % (len(stats["symbols"]), max(stats["symbols"].values())))


if __name__ == "__main__":
    main()
