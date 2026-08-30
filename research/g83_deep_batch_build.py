"""g83_deep_batch_build.py -- the deep batch: 60 charts, one question, one minute box.

WHAT THIS IS
------------
A second, longer homework page for Austin, built the same night as the master
homework (research/build_master_homework.py) and deliberately NOT the same shape.
The master page is seven angles in one sitting. This one is a single angle, sixty
times: **is this an S, and what minute do you get in.**

WHY THE QUOTA IS 20 / 20 / 20
-----------------------------
research/g77_wrongchart.md proved the old deck builder chose which signal a card
was about by how much the engine BELIEVED it -- Austin-ladder S, fewest
downgrades, earliest minute -- and never once read `traded`. So every precision
number it produced was measured against an object the engine had refused. 25 of
its 30 cards were signals the engine never took.

The fix there was "only build cards from booked trades". That is right for a
precision deck and wrong for this one, because it can only ever score the engine
on days it already likes. This page instead serves all three roles in equal,
stated proportion:

    20  the engine TRADED           (>=1 booked trade that morning)
    20  the engine FIRED, NO TRADE  (>=1 detection, none booked)
    20  the engine was SILENT       (no detection at all, 09:30-11:00)

so one page prices three different things at once:
  * traded    -- does he agree with the days it puts money on   (precision)
  * refused   -- is the refusal right, or is it throwing away his setups
  * silent    -- the recall hole: days it never even looked at

WHAT IS ON A CARD, AND WHAT IS DELIBERATELY NOT
-----------------------------------------------
ON:   symbol, date, the 1-minute 09:30-11:00 session, and his six levels
      PDH / PDL / PMH / PML / ORH / ORL.
NOT:  no entry, no stop, no target, no setup name, no grade, no outcome -- and
      above all NO ROLE. The three buckets must be indistinguishable on the page
      or the answer key leaks into the answer. The role lives only in
      research/decks/g83-deep-batch-manifest.jsonl.

That is also why NO PRE-FILTER runs here. research/t21_card_filter is the shipped
deck pre-filter and build_deck.pick applies it to fire-day candidates while letting
silent-day candidates through untouched. Applied on this page it would filter two
of the three buckets and not the third, which is exactly the confound the batch
exists to avoid: the engine buckets would be made to look better than the silent
bucket by construction. Every card here is drawn at random from its own pool and
nothing else.

THE MINUTE
----------
Twenty of the last thirty cards carried a stated entry minute unprompted, and
research/g74_verdict.md found every hard result in that batch came out of the
minute rather than the yes/no. So it is asked for deliberately: a box on every
card, a warning on any S card without one, and a running count at the top.
window.probeRow parses it into its own `entry_minute` field so the next analysis
does not have to regex prose.

NO REPEATS
----------
build_deck.seen_card_ids() -- judged in ANY mark corpus OR ever served in ANY
manifest -- plus research/decks/g75-deck2-manifest.jsonl named explicitly (it is
unserved homework already waiting for him; it is inside seen_card_ids too, and
being named here means a rename of that file cannot silently un-protect it).

DARK
----
Austin asked for dark artifacts. The palette is not invented here: it is
probe_page.py's own dark block, pinned on so the page is dark whatever the
viewer's OS says. Nothing in probe_page.py is modified.

    python research/g83_deep_batch_build.py [--seed 83] [--per-bucket 20]

Output: research/probes/omen-deep-batch.html
        research/decks/g83-deep-batch-manifest.jsonl   (answer key, NOT in the HTML)

NOT SERVED BY THIS SCRIPT. Writing the manifest marks these symbol-days as served
so a later deck cannot repeat them. If the batch is abandoned rather than sent,
delete the manifest and the days go back in the pool.
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

BOOK = os.path.join(HERE, "bt2y_trades.json")
ARCHIVE = os.path.join(ROOT, "data_archive")
OUT_HTML = os.path.join(HERE, "probes", "omen-deep-batch.html")
OUT_MANIFEST = os.path.join(HERE, "decks", "g83-deep-batch-manifest.jsonl")
G75_MANIFEST = os.path.join(HERE, "decks", "g75-deck2-manifest.jsonl")
DECK_ID = "g83-deep-batch"

HIS_SIX_KEYS = ("pdh", "pdl", "pmh", "pml", "orh", "orl")

# 90 bars is a full 09:30-11:00 session. Anything much short of that is a
# half-drawn chart and is not worth one of his sixty slots.
MIN_BARS = 85

# No one symbol may own more than this many of the sixty. 342 of the 604 silent
# symbol-days in the book are SPCX alone; uncapped, the silent bucket would be
# a SPCX deck wearing a quota.
MAX_PER_SYMBOL = 3

ROLES = ("traded", "fired_not_traded", "silent")
ROLE_BLURB = {
    "traded": "the engine booked a trade that morning",
    "fired_not_traded": "the engine found setups that morning and refused every one",
    "silent": "the engine found nothing at all that morning",
}


# ------------------------------------------------------------------ the pools

def load_book(path=BOOK):
    """Per-day counts and booked rows out of the two-year book.

    The full book is 134,012 signal rows and ~138MB on disk; only what a card
    needs is kept.
    """
    with open(path, encoding="utf-8") as fh:
        blob = json.load(fh)
    meta, rows = blob["meta"], blob["trades"]
    n_sig = Counter()
    booked = defaultdict(list)
    setups = defaultdict(set)
    session_days = set()
    for r in rows:
        key = (r["sym"], r["day"])
        n_sig[key] += 1
        session_days.add(r["day"])
        setups[key].add(r.get("setup"))
        if r.get("traded"):
            booked[key].append(r)
    return n_sig, booked, setups, session_days, list(meta["symbols"]), meta


def archive_grid(symbols, session_days):
    """Every (symbol, day) the archive holds for a book symbol on a book session."""
    out = set()
    for sym in symbols:
        d = os.path.join(ARCHIVE, sym)
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if name.endswith(".csv") and name[:-4] in session_days:
                out.add((sym, name[:-4]))
    return out


def classify(n_sig, booked, grid):
    """{role: [(sym, day)]} over the whole two-year grid."""
    pools = {r: [] for r in ROLES}
    for key in sorted(grid):
        n = n_sig.get(key, 0)
        if n == 0:
            pools["silent"].append(key)
        elif booked.get(key):
            pools["traded"].append(key)
        else:
            pools["fired_not_traded"].append(key)
    return pools


def levels_for(sym, day, candles):
    """His six, keyed the way probe_chart wants them.

    All six are fixed at or before 09:30 -- prior day, pre-market, and the
    opening range (the first five RTH bars, the definition build_deck.py and
    every backtest use) -- so no level can leak a bar the engine had not seen.
    """
    pdh, pdl, _o, _c = bd.prior_day_levels(sym, day)
    pmh, pml = bd.premarket_extremes(sym, day)
    orh = max(c.high for c in candles[:5]) if len(candles) >= 5 else None
    orl = min(c.low for c in candles[:5]) if len(candles) >= 5 else None
    return {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
            "orh": orh, "orl": orl}


def draw(pools, seen, want, seed):
    """`want` cards per role, at random, no repeats, no symbol over the cap.

    Rejections are counted per role and reported -- "how many candidates did you
    throw away" is a question with a number for an answer, not a shrug.
    """
    rng = random.Random(seed)
    per_symbol = Counter()
    picked = {r: [] for r in ROLES}
    census = {r: Counter() for r in ROLES}
    for role in ROLES:
        cands = list(pools[role])
        census[role]["pool"] = len(cands)
        rng.shuffle(cands)
        for sym, day in cands:
            if len(picked[role]) >= want:
                break
            cid = "%s_%s" % (sym, day)
            if cid in seen:
                census[role]["rejected_judged_or_served"] += 1
                continue
            if per_symbol[sym] >= MAX_PER_SYMBOL:
                census[role]["rejected_symbol_cap"] += 1
                continue
            candles = bd.session_candles(sym, day)
            if len(candles) < MIN_BARS:
                census[role]["rejected_short_session"] += 1
                continue
            levels = levels_for(sym, day, candles)
            if sum(1 for k in HIS_SIX_KEYS if levels.get(k) is not None) < 4:
                # A chart missing half his levels asks him to read a chart he
                # would never read. Rare (a missing prior session), but real.
                census[role]["rejected_missing_levels"] += 1
                continue
            per_symbol[sym] += 1
            picked[role].append({"symbol": sym, "day": day, "role": role,
                                 "candles": candles, "levels": levels})
            census[role]["kept"] += 1
    return picked, census


# ------------------------------------------------------------------ rendering

_LVL_DRAWN = re.compile(r'class="lvl-t [^"]*"[^>]*>([A-Z]{3}) ')


def offchart_note(svg, levels, candles):
    """Name the levels the chart could not fit.

    probe_chart only lets a level widen the frame by a quarter of the session's
    range, so a card can silently show four of six. Read back what the SVG drew
    rather than re-deriving its framing.
    """
    drawn = set(_LVL_DRAWN.findall(svg))
    hi = max(c.high for c in candles)
    missing = []
    for key, lab, _cls in probe_chart.LEVELS:
        v = levels.get(key)
        if v is None or lab in drawn or key not in HIS_SIX_KEYS:
            continue
        missing.append("%s %.2f %s" % (lab, v, "above" if v > hi else "below"))
    if not missing:
        return ""
    return ('<div class="legend" style="padding-top:0"><span>'
            '<b>off this chart:</b> %s</span></div>' % " &middot; ".join(missing))


# probe_page.py already ships this exact dark palette behind
# `@media (prefers-color-scheme:dark)` and `:root[data-theme="dark"]`. Austin
# asked for dark artifacts, so it is pinned on here instead of left to the
# viewer's OS. `:root:root` is (0,2,0) specificity and lands after both of
# probe_page's blocks, so it wins in all three theme states. Nothing in
# probe_page.py is modified and no colour is invented.
DARK_CSS = """
<style>
:root:root{
  color-scheme:dark;
  --bg:#0d1211; --surface:#151d1c; --surface-2:#1d2726;
  --ink:#e7edeb; --ink-2:#a3b3af; --ink-3:#7d8d89;
  --rule:#25322f; --rule-2:#33433f;
  --accent:#54cfbe; --accent-ink:#07201d; --accent-soft:#16332f;
  --up:#48b57c; --dn:#e07068; --entry:#e0a340; --stop:#d47a70;
  --lvl-pd:#8fa2dc; --lvl-pm:#bb92d1; --lvl-or:#6dbcb0; --lvl-hl:#e09a5c;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -16px rgba(0,0,0,.7);
}
html{background:#0d1211}
</style>
"""

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
.quota{
  background:var(--surface); border:1px solid var(--rule); border-radius:10px;
  padding:14px 16px; margin:0 0 18px; box-shadow:var(--shadow); font-size:14px;
  color:var(--ink-2);
}
.quota h2{
  font-family:"IBM Plex Serif",Georgia,serif; font-size:16px; font-weight:600;
  margin:0 0 8px; color:var(--ink);
}
.quota ul{margin:0; padding-left:18px}
.quota li{margin:3px 0}
.quota b{color:var(--ink)}
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
  function isS(card){
    var c = card.querySelector('.q[data-q="s"] .chip[data-v="s"]');
    return !!(c && c.getAttribute('aria-pressed') === 'true');
  }
  function nag(){
    var open = 0, yes = 0, done = 0, cs = cards();
    cs.forEach(function(card){
      var need = isS(card), have = !!window.parseMinute(noteOf(card));
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
        ? ('<b>' + open + '</b> of your <b>' + yes + '</b> S cards still has no minute on it. '
           + 'That one line is where every hard finding came from last time &mdash; '
           + 'an S with no minute tells us almost nothing.')
        : ('<b>' + yes + '</b> S cards, every one of them with a minute. That is the whole point of this batch.');
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


def render_card(idx, c, total):
    cid = "%s_%s" % (c["symbol"], c["day"])
    lv = {k: (round(v, 2) if v is not None else None)
          for k, v in c["levels"].items()}
    svg = probe_chart.render([bd.candle_dict(x) for x in c["candles"]], lv,
                             marks=[],
                             label="%s %s 1-minute 09:30-11:00"
                                   % (c["symbol"], c["day"]))
    off = offchart_note(svg, lv, c["candles"])
    # ROLE stays out of the page. So does everything the engine thought.
    export = json.dumps({"symbol": c["symbol"], "date": c["day"]},
                        sort_keys=True).replace('"', "&quot;")

    q_s = probe_page.question(
        "s",
        "Is this an S?",
        "Nothing is marked. The 1-minute session and your six levels are all "
        "there is.",
        [("s", "S &mdash; I take this"), ("no", "Not an S")],
        required=True)

    q_entry = probe_page.question(
        "entry",
        "What minute do you get in?",
        "<b>Type the minute</b> &mdash; 9:42, 10:07. Twenty of the last thirty "
        "cards carried one and it was the most useful thing on the page, so it "
        "is being asked for out loud this time. Anything else you want to say "
        "about the chart can go in the same box.",
        [],
        required=False,
        note_placeholder="9:42 — and the level, the direction, anything else")

    nag = ('<p class="nag" hidden>You called this an S &mdash; it needs the '
           'minute you would have got in. Type it in the box above.</p>')

    return ('<article class="card" data-cid="%s" data-export="%s" data-done="0" '
            'data-minute="1">'
            '<header><span class="idx">%02d/%d</span>'
            '<span class="tick">%s</span>'
            '<span class="when">%s</span>'
            '<span class="tags"><span class="tag">1-min &middot; 09:30&ndash;11:00 ET</span>'
            '<span class="done-dot"></span></span></header>'
            '<div class="chartwrap">%s</div>'
            '<div class="legend">'
            '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
            '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> pre-market</span>'
            '<span><b style="color:var(--lvl-or)">- - ORH/ORL</b> opening range '
            '(first five minutes)</span></div>'
            '%s%s%s</article>'
            % (cid, export, idx, total, c["symbol"], c["day"], svg, off,
               q_s, q_entry + nag))


def quota_block(counts):
    return (
        '<div class="quota"><h2>What is in this batch, and in what proportion</h2>'
        '<p>Sixty charts, shuffled. They are drawn to a stated quota, and '
        '<b>which card is which is not on this page</b> &mdash; the key is in the '
        'build record, not in front of you:</p>'
        '<ul>'
        '<li><b>%d</b> mornings the engine <b>booked a trade</b></li>'
        '<li><b>%d</b> mornings the engine <b>found setups and refused every one</b></li>'
        '<li><b>%d</b> mornings the engine <b>found nothing at all</b></li>'
        '</ul>'
        '<p style="margin-top:9px">That mix exists because the old builder never '
        'asked whether the engine took the signal it was showing you &mdash; 25 of '
        'the last 30 cards were signals it had refused, so every precision number '
        'off them measured the wrong thing. This one prices all three at once: do '
        'you agree with what it trades, is it right to refuse what it refuses, and '
        'what is it missing entirely.</p></div>'
        % (counts["traded"], counts["fired_not_traded"], counts["silent"]))


def build(cards, counts):
    parts = [DARK_CSS, EXTRA_CSS, quota_block(counts),
             '<div class="tally" id="tally" data-open="0">Answer a card and this '
             'line starts counting the minutes you have given.</div>']
    total = len(cards)
    for i, c in enumerate(cards, 1):
        parts.append(render_card(i, c, total))

    lede = (
        "One question, sixty times: <strong>is this an S</strong>, and "
        "<strong>what minute do you get in</strong>. Nothing is marked &mdash; the "
        "1-minute 09:30&ndash;11:00 session and your six levels (PDH, PDL, PMH, "
        "PML, ORH, ORL), no entry, no stop, no setup name, no grade, no result. "
        "This is the long sitting: the master page is the variety, this one is "
        "depth on the single thing that decides everything else.")

    footer = (
        "<h2>Why the minute matters more than the S</h2>"
        "<p>Twenty of the thirty cards you did last night carried a minute you "
        "wrote without being asked &mdash; <i>9:47</i>, <i>9:38 is the entry</i>, "
        "<i>10:09 would never trade</i>. Every hard finding out of that batch came "
        "from those lines and not from the yes/no: seven times out of seven the "
        "engine was later than you, median 41 minutes inside a 90-minute window. "
        "The yes/no says whether it is looking at the right days. The minute says "
        "whether it is trading them at the right time, and that is the one that "
        "moves money.</p>"
        "<h2>How the sixty were chosen</h2>"
        "<p>At random inside each of the three buckets, and nothing else. No "
        "cleanest-first sort, no grade filter, no card pre-filter &mdash; filtering "
        "two of the three buckets and not the third would make the engine's own "
        "days look better than the days it never saw, which is precisely what this "
        "batch is trying to measure. At most three cards per symbol. Nothing here "
        "has ever been put in front of you before, in any deck, probe or page.</p>"
        "<h2>When you're done</h2>"
        "<p>Tap <b>Export</b> at the top, then <b>Copy all</b> and paste it into "
        "the chat &mdash; or <b>Download .jsonl</b>. Answers save to this browser "
        "as you tap and come back if you close the page.</p>")

    html = probe_page.shell(
        title="OMEN &mdash; deep batch: is this an S, and when",
        eyebrow="OMEN homework &middot; the long sitting",
        h1="Is this an S &mdash; and what minute do you get in?",
        lede=lede, cards_html="".join(parts), footer_html=footer,
        deck_id=DECK_ID)
    return html + NAG_JS


def write_manifest(cards, n_sig, booked, setups, path=OUT_MANIFEST):
    """The served record AND the answer key. Deliberately not in the HTML."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for i, c in enumerate(cards, 1):
            key = (c["symbol"], c["day"])
            rows = booked.get(key, [])
            first = min(rows, key=lambda r: r.get("et") or "99:99") if rows else None
            row = {
                "card_id": "%s_%s" % (c["symbol"], c["day"]),
                "symbol": c["symbol"], "date": c["day"], "deck": DECK_ID,
                "position": i,
                # ---- answer key, deliberately NOT in the HTML ----
                "role": c["role"],
                "role_meaning": ROLE_BLURB[c["role"]],
                "engine_signals": n_sig.get(key, 0),
                "engine_trades": len(rows),
                "engine_setups": sorted(x for x in setups.get(key, set()) if x),
                "drawn_levels": {k: (round(v, 2) if v is not None else None)
                                 for k, v in c["levels"].items()},
                "bars": len(c["candles"]),
            }
            if first is not None:
                row.update({
                    "first_trade_et": first.get("et"),
                    "first_trade_setup": first.get("setup"),
                    "first_trade_dir": first.get("dir"),
                    "first_trade_entry": first.get("entry"),
                    "first_trade_stop": first.get("stop"),
                    "first_trade_target": first.get("target"),
                    "first_trade_out": first.get("out"),
                    "first_trade_r": first.get("r"),
                    "first_trade_pnl": first.get("pnl"),
                    "first_trade_level": first.get("level_name"),
                    "legacy_grade": first.get("grade"),
                    "sgrade": first.get("sgrade"),
                    "tripped": first.get("tripped"),
                    "confluence": first.get("confluence"),
                    "downgrades": first.get("downgrades"),
                })
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def g75_ids(path=G75_MANIFEST):
    """The 39 cards already waiting for him. Inside seen_card_ids() too; named
    here so a rename of that file cannot silently un-protect them."""
    out = set()
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            out.add(json.loads(line)["card_id"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=83)
    ap.add_argument("--per-bucket", type=int, default=20)
    a = ap.parse_args()

    n_sig, booked, setups, session_days, symbols, _meta = load_book()
    grid = archive_grid(symbols, session_days)
    pools = classify(n_sig, booked, grid)

    seen = bd.seen_card_ids(OUT_MANIFEST)
    g75 = g75_ids()
    new_from_g75 = len(g75 - seen)
    seen |= g75

    picked, census = draw(pools, seen, a.per_bucket, a.seed)
    counts = {r: len(picked[r]) for r in ROLES}

    cards = [c for r in ROLES for c in picked[r]]
    random.Random(a.seed + 1).shuffle(cards)   # no positional tell

    # Guard: the role a card claims is re-derived from the book rather than
    # trusted from the label, the way g77_realtrade_pick.role_guard does it.
    for c in cards:
        key = (c["symbol"], c["day"])
        n, b = n_sig.get(key, 0), len(booked.get(key, []))
        want = ("silent" if n == 0 else "traded" if b else "fired_not_traded")
        assert c["role"] == want, "%s %s labelled %s, book says %s" % (
            c["symbol"], c["day"], c["role"], want)
        assert "%s_%s" % (c["symbol"], c["day"]) not in seen, "a repeat leaked through"
    assert len({(c["symbol"], c["day"]) for c in cards}) == len(cards)

    html = build(cards, counts)
    for leak in ('"role"', "fired_not_traded", "engine_signals", "sgrade"):
        assert leak not in html, "the answer key leaked into the HTML: %s" % leak

    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    write_manifest(cards, n_sig, booked, setups)

    print("wrote %s (%d bytes, %d cards)" % (OUT_HTML, len(html), len(cards)))
    print("wrote %s" % OUT_MANIFEST)
    print("\nexclusion set: %d symbol-days already judged or served" % len(seen))
    print("  of which the unserved g75 deck-two batch contributes %d cards "
          "(%d not already inside seen_card_ids)" % (len(g75), new_from_g75))
    print("two-year grid: %d symbol-days over %d sessions, %d symbols"
          % (len(grid), len(session_days), len(symbols)))
    print("\n%-18s %8s %9s %8s %9s %9s %6s"
          % ("bucket", "pool", "rej_seen", "rej_cap", "rej_bars", "rej_lvls", "kept"))
    tot = Counter()
    for r in ROLES:
        c = census[r]
        tot.update(c)
        print("%-18s %8d %9d %8d %9d %9d %6d"
              % (r, c["pool"], c["rejected_judged_or_served"],
                 c["rejected_symbol_cap"], c["rejected_short_session"],
                 c["rejected_missing_levels"], c["kept"]))
    print("%-18s %8d %9d %8d %9d %9d %6d"
          % ("TOTAL", tot["pool"], tot["rejected_judged_or_served"],
             tot["rejected_symbol_cap"], tot["rejected_short_session"],
             tot["rejected_missing_levels"], tot["kept"]))
    rejected = (tot["rejected_judged_or_served"] + tot["rejected_symbol_cap"]
                + tot["rejected_short_session"] + tot["rejected_missing_levels"])
    print("\ncandidates inspected and rejected before the sixty were filled: %d"
          % rejected)
    print("symbols on the page: %s"
          % ", ".join("%s x%d" % (s, n) for s, n in
                      Counter(c["symbol"] for c in cards).most_common()))
    print("date range on the page: %s .. %s"
          % (min(c["day"] for c in cards), max(c["day"] for c in cards)))


if __name__ == "__main__":
    main()
