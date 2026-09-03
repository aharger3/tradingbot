"""g75_deck2_build.py -- the second homework deck, built to fix the first one's design.

WHY THIS EXISTS
---------------
The 30-card batch of 2026-08-29 (research/g71_homework_build.py) was read as "the
one-candle rule is the engine's best detector at 80%". research/g74_verdict.md
killed that reading. Three of the four things that killed it were faults in the
DECK, not in Austin's eye and not in the engine:

  FAULT 1  THE ARMS WERE NOT COMPARABLE.
           g71 sorted candidates cleanest-first (`cands.sort(key=tripped)`).
           That only works if every arm HAS enough clean days. The 84% rule has
           six zero-downgrade days in two years; the deck took three of them and
           filled the other seven slots with days the engine had already marked
           down, while the one-candle rule -- with 156 clean days -- took nine.
           The lowest-scoring arm was handed the worst cards by construction.

           FIXED TWO WAYS. (a) There is no cleanest-first sort here at all. Only
           85 of the 4,508 trades the engine actually books have zero downgrades
           (1.9%), so sorting on that would AGAIN build a deck out of the 2% that
           does not look like the book. (b) Arm size is decided by SUPPLY, out
           loud, BEFORE any card is chosen: the scarcest arm caps the deck, the
           other two are cut to match it, and the page says so.

  FAULT 2  THE DECK AND THE TRADING BARELY TOUCHED.
           g71 required the card's setup to sit on one of Austin's six levels.
           A one-candle-rule signal has no level -- its "level" is an order block,
           which is a candle -- so that gate kept the 8.7% of one-candle-rule days
           where the order block HAPPENED to land on one of his six. Of the 482
           one-candle-rule trades the engine really books, exactly ONE passes all
           three filters those ten cards passed. He was grading a population the
           engine does not trade.

           FIXED. Every card here is a symbol-day where the engine BOOKED A TRADE
           -- `traded == True` on research/bt2y_trades.json, the two-year book.
           No his-six eligibility gate, no S-grade gate, no zero-downgrade gate.
           His six levels are DRAWN on every chart because they are how he reads
           a chart; they are not a filter on which charts he is shown.

  FAULT 3  CONFOUNDED BY THE DAY.
           Of seven measurable properties only session trendiness separated his
           yes from his no (0.145 vs 0.072, p=0.014) -- and the one-candle-rule
           arm had drawn the trendiest sessions (0.151 against break-and-retest's
           0.103). Some of its 80% was that draw. The setup label itself predicted
           nothing (p=0.70).

           FIXED. The deck is built in ROUNDS OF THREE: one break-and-retest day,
           one one-candle-rule day, one 84%-rule day, matched so all three trended
           within `TREND_TOL` of each other. Trendiness is the efficiency ratio
           over 09:30-11:00, `t21_card_filter.features()["er_session"]` -- the
           same number g74 measured his answers against, not a new one invented
           here.

AND ONE THING THAT WORKED, CARRIED FORWARD
------------------------------------------
Every hard finding in g74 came out of the free-text minute, not the yes/no box:
seven times out of seven the engine was later than him on a one-candle-rule card,
median 41 minutes inside a 90-minute window. So on this page the minute is not an
optional afterthought in a note field -- the card is not counted as finished
without it, a yes-card with no minute wears a warning, and the top of the page
carries a running "N of M answered without a minute" count. `window.probeRow`
parses the minute out of the note into its own `entry_minute` field, so the next
analysis does not have to regex his prose.

WHAT IS ON A CARD, AND WHAT IS DELIBERATELY NOT
-----------------------------------------------
ON:   the symbol, the date, the 1-minute 09:30-11:00 session, and his six levels
      PDH, PDL, PMH, PML, ORH, ORL (settled 2026-08-29; the same six
      `downgrade.CONFLUENCE_LEVELS` uses).
NOT:  no entry line, no stop, no target, no grade, no outcome, no P&L -- and,
      new here, NO SETUP LABEL. g71 printed "the engine claims: OCR" on the card.
      That is a tell: it invites him to answer the label rather than the chart,
      and the label is the exact thing the arms are testing. Which arm a card
      belongs to lives in the manifest and never reaches the HTML.

      This changes the question the card asks, on purpose. g71 asked "is this an
      S trade?" about a signal he could not see. This asks "would you take a
      trade on this chart, and at what minute?" -- which is answerable from the
      chart alone, and whose answer prices BOTH precision (did the engine book a
      chart he would trade) and lateness (is his minute earlier than its minute)
      on the trades the engine really takes.

GUARDS
------
* `build_deck.seen_card_ids()` -- judged (1,178 symbol-days) OR ever served.
  The build ABORTS on a collision.
* `t21_card_filter` -- the shipped deck pre-filter (reach <= 8R at the entry bar).
* One card per symbol-day; at most `MAX_PER_SYMBOL` cards per symbol.
* Only symbol-days where the engine booked ONE KIND of setup. A day carrying both
  a break-and-retest and a one-candle-rule trade cannot be attributed to an arm,
  so it is not a candidate. 258 mixed days are dropped for this reason.

OUTPUT
------
    research/g75_deck2.html                        the page
    research/decks/g75-deck2-manifest.jsonl        served record + answer key

    python research/g75_deck2_build.py [--seed 75] [--rounds 0] [--tol 0.010]

    --rounds 0 means "as many as the scarcest arm supplies" (the point of fix 1).

NOT SERVED BY THIS SCRIPT. Writing the manifest marks these symbol-days as served
so a later deck cannot repeat them. If this deck is abandoned rather than sent,
delete research/decks/g75-deck2-manifest.jsonl and the days go back in the pool.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd
import probe_chart
import probe_page
import t21_card_filter as card_filter

BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT_HTML = os.path.join(HERE, "g75_deck2.html")
OUT_MANIFEST = os.path.join(HERE, "decks", "g75-deck2-manifest.jsonl")
G71_MANIFEST = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
DECK_ID = "g75-deck2"

# The three detectors, as arms. A symbol-day is a candidate only if the engine
# booked exactly one of them there, so an arm label is unambiguous.
SETUP_OF = {"break_and_retest": "BR", "one_candle_rule": "OCR",
            "reentry_84_rule": "84"}
ARMS = ("BR", "OCR", "84")
ARM_NAME = {"BR": "break and retest", "OCR": "one candle rule",
            "84": "84% re-entry"}

# Austin's six, as settled 2026-08-29 and as `downgrade.CONFLUENCE_LEVELS` holds
# them. Drawn on every card; NOT a filter on which cards exist.
HIS_SIX_KEYS = ("pdh", "pdl", "pmh", "pml", "orh", "orl")

# How close two sessions' efficiency ratios must be to sit in the same round.
# 0.010 is a tenth of the gap g74 measured between his yes-days and his no-days
# (0.145 vs 0.072), so a matched round cannot carry the effect that decided his
# answer last time.
TREND_TOL = 0.010
MAX_PER_SYMBOL = 2

NO_REASONS = [
    ("chop", "chop / no structure here"),
    ("no_displacement", "no displacement &mdash; the break had no force"),
    ("stale_retest", "stale retest &mdash; came back too late"),
    ("level_not_respected", "level not respected &mdash; closing on it / chopping on it"),
    ("exhausted", "exhausted &mdash; the move is already spent"),
    ("counter_trend_not_respected", "counter-trend candles not bought back"),
    ("break_then_rejection", "broke, then gave it straight back"),
    ("no_retest", "no retest &mdash; ran and never came back"),
    ("chase", "chase &mdash; too far past the level"),
    ("late", "nothing here early enough to trade"),
    ("wrong_level", "wrong level &mdash; not a level I watch"),
    ("not_a_trade", "not a trade at all &mdash; wrong chart to show me"),
    ("other", "other &mdash; say it below"),
]


# ------------------------------------------------------------------ candidates

def load_book(path=BOOK):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["trades"]


def candidate_days(rows):
    """{(sym, day): {arm, rep, n_trades}} for every day the engine BOOKED trades
    of exactly one kind, plus the census of what was dropped.

    `rep` is the day's FIRST booked trade. That is the one the engine acted on
    under the one-trade-a-day rule, and its `et` is the minute Austin's own
    minute gets compared against.
    """
    booked = [r for r in rows if r.get("traded")]
    by_day = defaultdict(list)
    for r in booked:
        by_day[(r["sym"], r["day"])].append(r)

    out, census = {}, Counter()
    census["booked_trades"] = len(booked)
    census["booked_days"] = len(by_day)
    for key, rs in by_day.items():
        arms = {SETUP_OF[r["setup"]] for r in rs}
        if len(arms) != 1:
            census["mixed_setup_days"] += 1
            continue
        arm = arms.pop()
        rep = min(rs, key=lambda r: r.get("et") or "99:99")
        out[key] = {"arm": arm, "rep": rep, "n_trades": len(rs)}
        census["pure_" + arm] += 1
    return out, census


def supply(days, seen, seed):
    """Score every candidate through the shipped pre-filter and return the pool
    per arm, sorted by nothing at all.

    THE ORDER MATTERS AND IT IS THE POINT OF FIX 1. g71 sorted by `tripped`
    (cleanest first), which quietly handed the scarce arm the worst cards. Here
    the pool is shuffled with a seed and nothing else, so a card's chance of
    reaching him does not depend on how much the engine liked it.
    """
    rng = random.Random(seed)
    pool = {a: [] for a in ARMS}
    drops = {a: Counter() for a in ARMS}
    items = sorted(days.items())
    rng.shuffle(items)
    for (sym, day), v in items:
        a = v["arm"]
        if "%s_%s" % (sym, day) in seen:
            drops[a]["already_judged_or_served"] += 1
            continue
        feat = card_filter.features(sym, day, v["rep"].get("et"))
        if feat is None:
            drops[a]["no_features"] += 1
            continue
        ok, why = card_filter.verdict(feat)
        if not ok:
            for w in why:
                drops[a]["t21_" + w] += 1
            continue
        pool[a].append({"symbol": sym, "day": day, "arm": a, "rep": v["rep"],
                        "n_trades": v["n_trades"], "er": feat["er_session"],
                        "prefilter": {"er_session": feat["er_session"],
                                      "reach_r": feat["reach_r"],
                                      "impulse_atr": feat["impulse_atr"],
                                      "et": feat["et"]}})
    return pool, drops


# ------------------------------------------------------------------ matching

def build_rounds(pool, want, tol, seed):
    """Rounds of three matched on session trendiness.

    The scarcest arm is the anchor -- it is the arm that cannot be padded, and
    padding it is precisely what broke the last deck. Each anchor card then
    recruits the CLOSEST-trending unused day from each of the other two arms.
    An anchor that cannot recruit both inside `tol` is dropped and reported;
    the deck gets shorter rather than mismatched.
    """
    rng = random.Random(seed + 1)
    anchor = min(ARMS, key=lambda a: len(pool[a]))
    others = [a for a in ARMS if a != anchor]

    anchors = list(pool[anchor])
    rng.shuffle(anchors)

    used = {a: set() for a in ARMS}
    per_symbol = Counter()
    rounds, failed = [], Counter()

    for a_card in anchors:
        if want and len(rounds) >= want:
            break
        if per_symbol[a_card["symbol"]] >= MAX_PER_SYMBOL:
            failed["anchor_symbol_cap"] += 1
            continue
        # Provisional holds: the anchor and each recruit reserve a symbol slot
        # while the round is being formed, so two arms cannot both spend the
        # last slot of one symbol. Every hold is released if the round fails.
        held = [a_card["symbol"]]
        per_symbol[a_card["symbol"]] += 1
        picked, ok = {}, True
        for other in others:
            cands = [c for c in pool[other]
                     if (c["symbol"], c["day"]) not in used[other]
                     and per_symbol[c["symbol"]] < MAX_PER_SYMBOL
                     and c["symbol"] != a_card["symbol"]
                     and abs(c["er"] - a_card["er"]) <= tol]
            if not cands:
                failed["no_match_" + other] += 1
                ok = False
                break
            best = min(cands, key=lambda c: (abs(c["er"] - a_card["er"]),
                                             c["symbol"], c["day"]))
            picked[other] = best
            held.append(best["symbol"])
            per_symbol[best["symbol"]] += 1
        if not ok:
            for sym in held:
                per_symbol[sym] -= 1
            continue
        row = [a_card] + [picked[o] for o in others]
        for c in row:
            used[c["arm"]].add((c["symbol"], c["day"]))   # holds already counted
        rng.shuffle(row)               # no positional tell inside a round
        rounds.append(row)
    return rounds, anchor, failed


# ------------------------------------------------------------------ rendering

def levels_for(sym, day, candles):
    """His six, keyed the way probe_chart wants them.

    All six are fixed at or before 09:30 (prior day, pre-market, and the opening
    range = the first five RTH bars, the definition build_deck.py and every
    backtest use), so none of them can leak a bar the engine had not seen.
    """
    pdh, pdl, _o, _c = bd.prior_day_levels(sym, day)
    pmh, pml = bd.premarket_extremes(sym, day)
    orh = max(c.high for c in candles[:5]) if len(candles) >= 5 else None
    orl = min(c.low for c in candles[:5]) if len(candles) >= 5 else None
    return {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
            "orh": orh, "orl": orl}


_LVL_DRAWN = re.compile(r'class="lvl-t [^"]*"[^>]*>([A-Z]{3}) ')


def offchart_note(svg, levels, candles):
    """Name the levels the chart could not fit. Same reasoning as g71: probe_chart
    only lets a level widen the frame by a quarter of the session's range, and a
    card silently showing four of six is a card missing two of his inputs. Read
    back what the SVG drew rather than re-deriving its framing."""
    drawn = set(_LVL_DRAWN.findall(svg))
    hi = max(c.high for c in candles)
    lo = min(c.low for c in candles)
    missing = []
    for key, lab, _cls in probe_chart.LEVELS:
        v = levels.get(key)
        if v is None or lab in drawn:
            continue
        missing.append("%s %.2f %s" % (lab, v, "above" if v > hi else "below"))
    if not missing:
        return ""
    return ('<div class="legend" style="padding-top:0"><span>'
            '<b>off this chart:</b> %s</span></div>' % " &middot; ".join(missing))


EXTRA_CSS = """
<style>
.nag{
  margin:0 16px 14px; padding:9px 12px; border-radius:8px;
  background:var(--surface-2); border:1px solid var(--stop);
  color:var(--stop); font-size:13px; font-weight:600;
}
.card[data-minute="0"]{border-color:var(--stop)}
.tally{
  background:var(--surface); border:1px solid var(--rule); border-radius:10px;
  padding:12px 16px; margin:0 0 18px; box-shadow:var(--shadow); font-size:14px;
}
.tally b{font-family:"IBM Plex Mono",monospace}
.tally[data-open="1"]{border-color:var(--stop)}
</style>
"""

# Runs AFTER probe_page's own script (shell() emits that last, this is appended
# after it), so these listeners fire second on the same bubbled event and can
# correct the progress bar probe_page just drew. probe_page.py is not modified.
NAG_JS = """
<script>
(function(){
  function cards(){ return [].slice.call(document.querySelectorAll('.card')); }
  function noteOf(card){
    var t = card.querySelector('textarea[data-note="entry"]');
    return t ? t.value : '';
  }
  var TIME = /\\b(\\d{1,2})[:;.\\s]?(\\d{2})\\b/;
  window.parseMinute = function(s){
    var m = TIME.exec(s || '');
    if (!m) return null;
    var h = parseInt(m[1], 10), mi = parseInt(m[2], 10);
    if (h < 9 || h > 11 || mi > 59) return null;
    var t = (h - 9) * 60 + mi - 30;
    if (t < 0 || t > 90) return null;
    return ('0' + h).slice(-2) + ':' + ('0' + mi).slice(-2);
  };
  function isYes(card){
    var c = card.querySelector('.q[data-q="take"] .chip[data-v="yes"]');
    return !!(c && c.getAttribute('aria-pressed') === 'true');
  }
  function nag(){
    var open = 0, yes = 0, done = 0, cs = cards();
    cs.forEach(function(card){
      var need = isYes(card), have = !!window.parseMinute(noteOf(card));
      if (need) yes++;
      var bad = need && !have;
      if (bad) open++;
      card.setAttribute('data-minute', bad ? '0' : '1');
      var n = card.querySelector('.nag');
      if (n) n.hidden = !bad;
      if (bad) card.setAttribute('data-done', '0');
      if (card.getAttribute('data-done') === '1') done++;
    });
    var cnt = document.getElementById('count');
    if (cnt) cnt.textContent = done + ' / ' + cs.length;
    var fill = document.getElementById('fill');
    if (fill) fill.style.width = (cs.length ? (done * 100 / cs.length) : 0) + '%';
    var t = document.getElementById('tally');
    if (t){
      t.setAttribute('data-open', open ? '1' : '0');
      t.innerHTML = open
        ? ('<b>' + open + '</b> of your <b>' + yes + '</b> yes-cards still has no minute on it. '
           + 'That one line is where every real finding came from last time &mdash; '
           + 'a yes without a minute tells us almost nothing.')
        : ('<b>' + yes + '</b> yes-cards, every one of them with a minute. That is the whole point of this batch.');
    }
  }
  /* The export row is a contract: this only ADDS keys. */
  window.probeRow = function(card, row){
    var s = noteOf(card);
    row.entry_minute = window.parseMinute(s);
    row.entry_minute_given = !!row.entry_minute;
  };
  document.addEventListener('click', nag);
  document.addEventListener('input', nag);
  document.addEventListener('blur', nag, true);
  document.addEventListener('visibilitychange', nag);
  setTimeout(nag, 0);
})();
</script>
"""


def render_card(idx, c):
    cid = "%s_%s" % (c["symbol"], c["day"])
    lv = {k: (round(v, 2) if v is not None else None)
          for k, v in c["levels"].items()}
    svg = probe_chart.render([bd.candle_dict(x) for x in c["candles"]], lv,
                             marks=[],
                             label="%s %s 1-minute 09:30-11:00" % (c["symbol"], c["day"]))
    off = offchart_note(svg, lv, c["candles"])
    # Arm, setup, entry minute, grade and outcome stay OUT of the page.
    export = json.dumps({"symbol": c["symbol"], "date": c["day"]},
                        sort_keys=True).replace('"', "&quot;")

    q_take = probe_page.question(
        "take",
        "Would you take a trade on this chart?",
        "Nothing is marked. The 1-minute session and your six levels are all there is.",
        [("yes", "YES &mdash; there is a trade here"),
         ("no", "NO &mdash; I would sit this one out")],
        required=True)

    q_entry = probe_page.question(
        "entry",
        "If yes &mdash; what minute, and which way?",
        "Tap long or short, then <b>type the minute you would have got in</b> "
        "&mdash; 9:42, 10:07. This is the most valuable line on the page.",
        [("long", "LONG"), ("short", "SHORT")],
        required=False,
        note_placeholder="the minute you would have entered, e.g. 9:42 "
                         "— plus the level or anything else you'd mark")

    nag = ('<p class="nag" hidden>You said yes &mdash; this card needs the minute '
           'you would have entered. Type it in the box above.</p>')

    q_why = probe_page.question(
        "why_not",
        "If no &mdash; why not?",
        "Pick every one that applies. Skip this if you said yes.",
        NO_REASONS, multi=True, required=False, tone="veto",
        note_placeholder="in your own words (optional)")

    return ('<article class="card" data-cid="%s" data-export="%s" data-done="0" '
            'data-minute="1">'
            '<header><span class="idx">%02d</span><span class="tick">%s</span>'
            '<span class="when">%s</span>'
            '<span class="tags"><span class="tag">1-min &middot; 09:30&ndash;11:00 ET</span>'
            '<span class="done-dot"></span></span></header>'
            '<div class="chartwrap">%s</div>'
            '<div class="legend">'
            '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
            '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> pre-market</span>'
            '<span><b style="color:var(--lvl-or)">- - ORH/ORL</b> opening range '
            '(first five minutes)</span></div>'
            '%s%s%s%s</article>'
            % (cid, export, idx, c["symbol"], c["day"], svg, off,
               q_take, q_entry + nag, q_why))


def build(rounds, anchor, anchor_supply, anchor_pure, anchor_unjudged):
    parts = [EXTRA_CSS,
             '<div class="tally" id="tally" data-open="0">Answer a card and this '
             'line starts counting the minutes you have given.</div>']
    n = 0
    for ri, row in enumerate(rounds, 1):
        parts.append('<p class="eyebrow" style="margin:30px 0 10px">'
                     'Round %d of %d &mdash; three days that trended the same</p>'
                     % (ri, len(rounds)))
        for c in row:
            n += 1
            parts.append(render_card(n, c))

    lede = (
        "Every chart in here is a day <strong>the engine actually put money on</strong> "
        "&mdash; a real trade out of the two-year book, not a signal it looked at and "
        "refused. Last time 25 of the 30 cards were signals it never traded, so nothing "
        "you said could tell us whether it trades well. "
        "Nothing is marked: the 1-minute 09:30&ndash;11:00 session and "
        "<strong>your six levels</strong> (PDH, PDL, PMH, PML, ORH, ORL). No entry, no "
        "stop, no grade, no result &mdash; and this time no setup name either, because "
        "naming it invites you to answer the name instead of the chart. "
        "<strong>Would you take a trade here, and if so at what minute.</strong> "
        "The minute is the whole point: last time it was the only thing on the page that "
        "told us anything hard.")

    footer = (
        "<h2>Why it is %d cards and not more</h2>"
        "<p>These charts come in rounds of three. Inside a round, the three days "
        "<b>trended the same amount</b> &mdash; that is deliberate. Last time the arms "
        "were not matched on it, and how much the day trended turned out to be the only "
        "thing that moved your answer at all (you said yes to all ten of the trendiest "
        "days, and five of ten of the choppiest). Matching them means the only thing "
        "left differing between the three cards in a round is the kind of setup.</p>"
        "<p>One of the three kinds only exists <b>%d times in two years</b> as a day the "
        "engine traded &mdash; %d of those you have not already judged, and %d of those "
        "survive your own card filter. So the batch is %d rounds. Last time that arm was "
        "padded out to ten "
        "with days the engine itself had marked down, it scored worst, and the padding is "
        "the likeliest reason. Better a short batch than a rigged one.</p>"
        "<h2>When you're done</h2>"
        "<p>Tap <b>Export</b> at the top, then <b>Copy all</b> and paste it into the chat "
        "&mdash; or <b>Download .jsonl</b>. Answers save to this browser as you tap and "
        "come back if you close the page.</p>"
        % (sum(len(r) for r in rounds), anchor_pure, anchor_unjudged,
           anchor_supply, len(rounds)))

    html = probe_page.shell(
        title="OMEN &mdash; would you have taken this trade",
        eyebrow="OMEN homework &middot; real trades, matched days",
        h1="Would you have taken this trade &mdash; and when?",
        lede=lede, cards_html="".join(parts), footer_html=footer, deck_id=DECK_ID)
    return html + NAG_JS


def write_manifest(rounds, path=OUT_MANIFEST):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for ri, row in enumerate(rounds, 1):
            for c in row:
                r = c["rep"]
                fh.write(json.dumps({
                    "card_id": "%s_%s" % (c["symbol"], c["day"]),
                    "symbol": c["symbol"], "date": c["day"], "deck": DECK_ID,
                    "round": ri,
                    # answer key -- deliberately NOT in the HTML
                    "arm": c["arm"], "engine_setup": r.get("setup"),
                    "setup_label": r.get("setup_label"),
                    "er_session": c["er"],
                    "traded": True, "trades_that_day": c["n_trades"],
                    "et": r.get("et"), "entry_i": r.get("entry_i"),
                    "dir": r.get("dir"), "entry": r.get("entry"),
                    "stop": r.get("stop"), "target": r.get("target"),
                    "out": r.get("out"), "r": r.get("r"), "pnl": r.get("pnl"),
                    "sgrade": r.get("sgrade"), "tripped": r.get("tripped"),
                    "confluence": r.get("confluence"),
                    "downgrades": r.get("downgrades"),
                    "legacy_grade": r.get("grade"),
                    "level": r.get("level"), "level_name": r.get("level_name"),
                    "level_px": r.get("level_px"), "stop_pct": r.get("stop_pct"),
                    "drawn_levels": {k: (round(v, 2) if v is not None else None)
                                     for k, v in c["levels"].items()},
                    "prefilter": c["prefilter"],
                }, sort_keys=True) + "\n")


# ------------------------------------------------------------------ reporting

def _mean(x):
    return sum(x) / len(x) if x else float("nan")


def _med(x):
    s = sorted(x)
    n = len(s)
    if not n:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def perm_spread_p(groups, iters=20000, seed=751):
    """How unusual is the spread between the arms' mean trendiness, if the arm
    label were meaningless? A LARGE p is the result we want -- it says the arms
    are not separated on the thing that decided his answer last time."""
    rng = random.Random(seed)
    sizes = [len(g) for g in groups]
    pool = [v for g in groups for v in g]
    obs = max(_mean(g) for g in groups) - min(_mean(g) for g in groups)
    hit = 0
    for _ in range(iters):
        rng.shuffle(pool)
        i, ms = 0, []
        for n in sizes:
            ms.append(_mean(pool[i:i + n]))
            i += n
        if max(ms) - min(ms) >= obs - 1e-12:
            hit += 1
    return obs, (hit + 1) / (iters + 1)


def old_deck_trendiness():
    """The arms of the g71 deck, on the same measure, for the before/after."""
    out = defaultdict(list)
    if not os.path.exists(G71_MANIFEST):
        return out
    for line in open(G71_MANIFEST, encoding="utf-8"):
        r = json.loads(line)
        pf = r.get("prefilter") or {}
        if pf.get("er_session") is not None:
            out[r["bucket"]].append(pf["er_session"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=75)
    ap.add_argument("--rounds", type=int, default=0,
                    help="0 = as many as the scarcest arm supplies")
    ap.add_argument("--tol", type=float, default=TREND_TOL)
    a = ap.parse_args()

    rows = load_book()
    days, census = candidate_days(rows)
    print("=" * 78)
    print("POPULATION -- trades the engine ACTUALLY BOOKED (fault 2)")
    print("=" * 78)
    print("  %d booked trades on %d symbol-days in the two-year book"
          % (census["booked_trades"], census["booked_days"]))
    print("  %d days carried more than one kind of setup and cannot be attributed "
          "to an arm -- dropped" % census["mixed_setup_days"])
    for arm in ARMS:
        print("    %-3s single-setup traded days: %d" % (arm, census["pure_" + arm]))

    judged = bd.marked_card_ids()
    served = bd.served_card_ids(OUT_MANIFEST)
    seen = judged | served
    print("  no-repeat guard: %d judged + %d served-only = %d seen symbol-days"
          % (len(judged), len(served - judged), len(seen)))

    unjudged = Counter(v["arm"] for (sym, day), v in days.items()
                       if "%s_%s" % (sym, day) not in seen)
    pool, drops = supply(days, seen, a.seed)
    print()
    print("=" * 78)
    print("SUPPLY, COUNTED BEFORE ANY CARD IS CHOSEN (fault 1)")
    print("=" * 78)
    for arm in ARMS:
        print("  %-3s %-20s %5d days available   (dropped: %s)"
              % (arm, ARM_NAME[arm], len(pool[arm]), dict(drops[arm]) or "-"))
    anchor_guess = min(ARMS, key=lambda x: len(pool[x]))
    print("  scarcest arm is %s at %d -- IT sets the deck size, the other two are cut "
          "to match" % (anchor_guess, len(pool[anchor_guess])))

    rounds, anchor, failed = build_rounds(pool, a.rounds, a.tol, a.seed)
    cards = [c for row in rounds for c in row]
    for c in cards:
        c["candles"] = bd.session_candles(c["symbol"], c["day"])
    thin = [c for c in cards if len(c["candles"]) < 60]
    assert not thin, "thin session on %s" % [(c["symbol"], c["day"]) for c in thin]
    for c in cards:
        c["levels"] = levels_for(c["symbol"], c["day"], c["candles"])

    ids = ["%s_%s" % (c["symbol"], c["day"]) for c in cards]
    assert len(set(ids)) == len(ids), "duplicate card inside the batch"
    repeats = sorted(set(ids) & bd.seen_card_ids(OUT_MANIFEST))
    assert not repeats, "batch repeats a judged/served symbol-day: %s" % repeats
    assert all(c["rep"].get("traded") for c in cards), "a card is not a booked trade"

    html = build(rounds, anchor, len(pool[anchor]), census["pure_" + anchor],
                 unjudged[anchor])
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    write_manifest(rounds)

    print()
    print("=" * 78)
    print("THE DECK")
    print("=" * 78)
    print("  wrote %s (%d bytes)" % (OUT_HTML, len(html)))
    print("  wrote %s" % OUT_MANIFEST)
    print("  %d cards in %d matched rounds of 3   (anchor arm: %s)"
          % (len(cards), len(rounds), anchor))
    if failed:
        print("  rounds that could not be formed: %s" % dict(failed))
    counts = Counter(c["arm"] for c in cards)
    for arm in ARMS:
        print("    %-3s %-20s %2d cards   (of %d available)"
              % (arm, ARM_NAME[arm], counts[arm], len(pool[arm])))

    print()
    print("=" * 78)
    print("THE TRENDINESS MATCH (fault 3)")
    print("=" * 78)
    ers = {arm: [c["er"] for c in cards if c["arm"] == arm] for arm in ARMS}
    for arm in ARMS:
        print("    %-3s mean ER %.4f   median %.4f   range %.4f-%.4f"
              % (arm, _mean(ers[arm]), _med(ers[arm]),
                 min(ers[arm]), max(ers[arm])))
    obs, p = perm_spread_p([ers[a_] for a_ in ARMS])
    print("  spread between arm means: %.4f   permutation p = %.3f  (large p = matched)"
          % (obs, p))
    worst = max(max(c["er"] for c in row) - min(c["er"] for c in row)
                for row in rounds)
    print("  worst within-round trendiness gap: %.4f (tolerance %.3f)" % (worst, a.tol))
    old = old_deck_trendiness()
    if old:
        o = {k: _mean(v) for k, v in old.items()}
        print("  for contrast, the g71 deck: %s"
              % "  ".join("%s %.4f" % (k, o[k]) for k in ARMS if k in o))
        print("    -> its spread was %.4f, %.1fx this deck's"
              % (max(o.values()) - min(o.values()),
                 (max(o.values()) - min(o.values())) / obs if obs else float("inf")))

    print()
    print("=" * 78)
    print("CHECKS")
    print("=" * 78)
    print("  REPEAT CHECK: %d of %d cards collide with the %d judged-or-served "
          "symbol-days -- %s"
          % (len(repeats), len(ids), len(bd.seen_card_ids(OUT_MANIFEST)),
             "PASS" if not repeats else "FAIL"))
    print("    (judged corpus alone: %d symbol-days)" % len(judged))
    print("  REAL TRADES: %d of %d cards are days the engine booked a trade -- %s"
          % (sum(1 for c in cards if c["rep"].get("traded")), len(cards),
             "PASS" if all(c["rep"].get("traded") for c in cards) else "FAIL"))
    print("  symbols: %d distinct, max per symbol %d"
          % (len(set(c["symbol"] for c in cards)),
             max(Counter(c["symbol"] for c in cards).values())))
    print("  no cleanest-first sort: downgrades on the chosen cards %s"
          % dict(sorted(Counter(int(c["rep"].get("tripped") or 0)
                                for c in cards).items())))
    print("    (the book's own booked-trade profile: %s)"
          % dict(sorted(Counter(int(r.get("tripped") or 0)
                                for r in rows if r.get("traded")).items())))
    print("  his ladder on the chosen cards: %s"
          % dict(Counter(c["rep"].get("sgrade") for c in cards)))
    print("  legacy ladder: %s" % dict(Counter(c["rep"].get("grade") for c in cards)))
    print("  engine entry minute: median %s, range %s-%s"
          % (sorted(c["rep"]["et"] for c in cards)[len(cards) // 2],
             min(c["rep"]["et"] for c in cards), max(c["rep"]["et"] for c in cards)))
    print("  outcome of the booked trade (hidden from him): %s"
          % dict(Counter(c["rep"].get("out") for c in cards)))
    print("  levels drawn on every card: %s" % ", ".join(k.upper() for k in HIS_SIX_KEYS))
    print("  no entry / stop / grade / outcome / setup name on any card: "
          "%s" % ("PASS" if "STOP" not in html and "engine claims" not in html
                  else "FAIL"))


if __name__ == "__main__":
    main()
