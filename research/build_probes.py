"""build_probes.py -- OMEN 6 tickets 09 and 10, the two non-deck elicitation probes.

    python research/build_probes.py autopsy      # 09: days Austin traded, engine silent
    python research/build_probes.py head2head    # 10: days the engine fired, Austin refused

Both are read-the-chart / tap-the-answer. No pointer marking, no free-form charting,
so they work on a phone -- the homework delivery contract from the OMEN 6 map.

Where the inputs come from:
  09  research/t60_silent_days.jsonl (written by t60_baseline.py) minus SPY, which the
      engine is configured never to trade -- 37 honest misses. Austin's own entry, stop
      and setup come from his trade sub-rows, so the card does not ask him WHERE he
      entered. It asks WHY it qualified, which is the thing the engine is missing.
  10  the 9 days the engine fired on and Austin graded `none`. Recomputed here rather
      than read from a file, because t60_baseline only counts them.

Output: research/probes/<name>.html -- a single self-contained page, published as a
claude.ai Artifact with the `artifact` capability so taps save and Claude reads them back.
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import probe_chart
import probe_page
from research.t4_engine_recall import rth_candles, prior_day_levels, premarket_extremes
from research.t60_baseline import load_day_cards
from v52_scaleout_run import corpus_b_trades

OUT_DIR = os.path.join(HERE, "probes")
SILENT = os.path.join(HERE, "t60_silent_days.jsonl")
SESSION_START, SESSION_END = "09:30", "11:00"

N_AUTOPSY = 15
SEED = 6


def session(symbol, day):
    out = []
    for c in rth_candles(symbol, day) or []:
        t = c.timestamp[11:16] if "T" in c.timestamp else c.timestamp[:5]
        if SESSION_START <= t < SESSION_END:
            out.append({"t": c.timestamp, "o": c.open, "h": c.high, "l": c.low,
                        "c": c.close, "v": c.volume})
    return out


def levels_for(symbol, day, candles):
    pdh, pdl, _o, _c = prior_day_levels(symbol, day)
    pmh, pml = premarket_extremes(symbol, day)
    orh = max(x["h"] for x in candles[:5]) if len(candles) >= 5 else None
    orl = min(x["l"] for x in candles[:5]) if len(candles) >= 5 else None
    return {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml, "orh": orh, "orl": orl}


LEGEND = ('<div class="legend">'
          '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
          '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> premarket 04:00-09:29</span>'
          '<span><b style="color:var(--lvl-or)">- - ORH/ORL</b> first 5 RTH bars</span>'
          '<span><b style="color:var(--entry)">&#9650; ENTRY</b></span>'
          '<span><b style="color:var(--stop)">STOP</b></span></div>')


def header(idx, total, symbol, day, tags):
    tag_html = "".join('<span class="tag%s">%s</span>' % (" warn" if w else "", t)
                       for t, w in tags)
    return ('<header><span class="idx">%02d/%02d</span>'
            '<span class="tick">%s</span><span class="when">%s</span>'
            '<span class="tags">%s<span class="done-dot"></span></span></header>'
            % (idx, total, symbol, day, tag_html))


# ---------------------------------------------------------------------------
# 09 -- silent-day autopsy
# ---------------------------------------------------------------------------

LEVEL_OPTS = [
    ("pdh", "PDH"), ("pdl", "PDL"), ("pmh", "PMH"), ("pml", "PML"),
    ("orh", "ORH"), ("orl", "ORL"),
    ("prior_close", "Prior close"), ("round", "Round number"),
    ("intraday_hod", "Intraday HOD/LOD"), ("gap_fill", "Gap fill"),
    ("none", "No level — momentum only"),
]

CONFIRM_OPTS = [
    ("displacement", "Displacement candle"),
    ("ocr", "OCR"),
    ("retest_held", "Retest held"),
    ("volume", "Volume surge"),
    ("qqq_trend", "QQQ trending my way"),
    ("flag", "Bull / bear flag"),
    ("htf", "Higher-timeframe thesis"),
    ("84", "84% re-entry"),
    ("none", "None of these"),
]

VERDICT_OPTS = [
    ("scanner_should", "It should have — level + displacement close was right there"),
    ("needs_context", "No — needed context that isn't on this chart"),
    ("discretionary", "No — my entry was discretionary timing"),
    ("bad_trade", "Honestly, I shouldn't have taken it"),
]


def build_autopsy():
    rows = [json.loads(l) for l in open(SILENT, encoding="utf-8") if l.strip()]
    rows = [r for r in rows if r["symbol"] != "SPY"]
    _days, marks = load_day_cards()
    by_day = defaultdict(list)
    for m in marks:
        by_day[(m["symbol"], m["date"])].append(m)

    # S first -- they are what the 90% gate is measured on -- then A, then fill.
    rng = random.Random(SEED)
    rng.shuffle(rows)
    rows.sort(key=lambda r: {"S": 0, "A": 1}.get(r["grade"], 2))
    picked, cards = [], []
    for r in rows:
        if len(picked) >= N_AUTOPSY:
            break
        candles = session(r["symbol"], r["date"])
        if len(candles) < 60:
            continue
        picked.append((r, candles))

    total = len(picked)
    for i, (r, candles) in enumerate(picked, 1):
        key = (r["symbol"], r["date"])
        lv = levels_for(r["symbol"], r["date"], candles)
        ms = sorted(by_day.get(key, []), key=lambda m: m.get("entry_i") or 0)
        marks_svg = [{"i": m["entry_i"], "price": m["entry_p"], "stop": m.get("stop_p"),
                      "side": m.get("side", "L"), "tag": "YOU"}
                     for m in ms if m.get("entry_i") is not None]
        setups = " / ".join(sorted({m.get("setup") or "?" for m in ms})) or "?"
        times = ", ".join(m.get("entry_t", "")[:5] for m in ms if m.get("entry_t"))
        tags = [(r["grade"], False), ("engine silent", True)]
        chart = probe_chart.render(candles, lv, marks_svg,
                                   "%s %s" % (r["symbol"], r["date"]))
        body = [
            '<article class="card" data-cid="%s_%s" data-grade="%s" data-done="0">'
            % (r["symbol"], r["date"], r["grade"]),
            header(i, total, r["symbol"], r["date"], tags),
            '<div class="chartwrap">%s</div>' % chart, LEGEND,
            probe_page.question(
                "level",
                "Which level were you trading off?",
                "Tap every one that was in play. Your entry is the amber line at "
                "%s (setup on file: %s). Tap all that apply."
                % (times or "the marked bar", setups),
                LEVEL_OPTS, multi=True),
            probe_page.question(
                "confirm",
                "What confirmed it?",
                "The thing that turned a level into a trade.",
                CONFIRM_OPTS, multi=True),
            probe_page.question(
                "verdict",
                "Should a scanner watching level + displacement close have caught this?",
                "This is the question the whole probe exists for — it splits 37 misses "
                "into engine bugs, missing features, and days to stop counting against it.",
                VERDICT_OPTS),
            probe_page.question(
                "missing", "One thing the engine had to know.",
                "Only if the answer above was &ldquo;needed context&rdquo;. One line.",
                [], required=False,
                note_placeholder="e.g. QQQ had already broken its own PDH two bars earlier"),
            "</article>",
        ]
        cards.append("".join(body))

    foot = ("<h2>What happens to these answers</h2>"
            "<p>Every tap saves to this page as you make it — close the tab, come back, "
            "it is still here. Nothing to export and nothing to download; Claude reads "
            "the answers straight off the page.</p>"
            "<p>These are the <b>%d</b> days you traded and the engine saw nothing "
            "(SPY excluded — the engine is configured never to trade it, so those 14 are "
            "not misses). S-days are first, because the OMEN 6 gate is measured on them: "
            "the engine currently finds <code>3 of your 28</code>.</p>" % len(rows))

    html = probe_page.shell(
        "Silent-Day Autopsy",
        "OMEN 6 &middot; ticket 09",
        "The engine saw nothing here.",
        "Fifteen days you traded and OMEN stayed silent. Your entry is already marked — "
        "the question is never <em>where</em>, it is <strong>what made it a trade</strong>. "
        "Roughly six minutes, all taps.",
        "".join(cards), foot)
    return html, "silent-day-autopsy", total


# ---------------------------------------------------------------------------
# 10 -- head-to-head
# ---------------------------------------------------------------------------

TAKE_OPTS = [
    ("yes", "Yes — engine's right, I missed it"),
    ("smaller", "Yes, but smaller size"),
    ("no", "No"),
]

VETO_OPTS = [
    ("no_level", "No level at the entry"),
    ("stale", "Level was stale"),
    ("no_displacement", "No displacement"),
    ("chop", "Chop — no clean structure"),
    ("wrong_trend", "Wrong side of the trend"),
    ("late", "Too late in the session"),
    ("thin_rr", "R:R too thin"),
    ("already_extended", "Already extended off the level"),
    ("na", "N/A — I'd have taken it"),
]


def build_head2head():
    days, _marks = load_day_cards()
    fired = defaultdict(list)
    for t in corpus_b_trades():
        fired[(t["symbol"], t["date"])].append(t)
    none_days = {k for k, d in days.items() if (d.get("grade") or "").strip() == "none"}
    keys = sorted(k for k in none_days if k in fired)

    cards = []
    total = len(keys)
    for i, (sym, day) in enumerate(keys, 1):
        candles = session(sym, day)
        if not candles:
            continue
        lv = levels_for(sym, day, candles)
        ts = sorted(fired[(sym, day)], key=lambda t: t["entry_i"])
        marks_svg = [{"i": t["entry_i"], "price": t["entry"], "stop": t["stop"],
                      "side": t.get("side", "L"), "tag": "OMEN"} for t in ts]
        reason = (days[(sym, day)].get("reason_none") or "").strip()
        tags = [("graded none", False), ("%d engine fire%s" % (len(ts), "" if len(ts) == 1 else "s"), True)]
        if reason:
            tags.insert(0, ("you wrote: %s" % reason, False))
        chart = probe_chart.render(candles, lv, marks_svg, "%s %s" % (sym, day))
        entry_t = ", ".join(t.get("entry_t", "")[:5] for t in ts if t.get("entry_t"))
        body = [
            '<article class="card" data-cid="%s_%s" data-grade="none" data-done="0">' % (sym, day),
            header(i, total, sym, day, tags),
            '<div class="chartwrap">%s</div>' % chart, LEGEND,
            probe_page.question(
                "take", "Would you have taken this?",
                "The amber line is where OMEN entered%s. You graded this day "
                "<code>none</code>." % (" at %s" % entry_t if entry_t else ""),
                TAKE_OPTS),
            probe_page.question(
                "veto", "If no — which single thing killed it?",
                "One tag only. Your own rule: an X gets one reason, not a list.",
                VETO_OPTS, tone="veto",
                note_placeholder="Optional: your reason in your own words"),
            "</article>",
        ]
        cards.append("".join(body))

    foot = ("<h2>Why this one is short</h2>"
            "<p>There are only <b>%d</b> days in the whole corpus where OMEN fired and you "
            "refused. That is the entire false-fire set. The answers here become the "
            "engine's veto list — the checks it runs <i>after</i> it finds a setup.</p>"
            "<p>Every tap saves as you make it. Nothing to export.</p>" % total)

    html = probe_page.shell(
        "Head-to-Head",
        "OMEN 6 &middot; ticket 10",
        "OMEN pulled the trigger. You didn't.",
        "Nine days the engine fired and you graded the day <code>none</code>. "
        "The engine's entry is marked. Two taps each, about two minutes.",
        "".join(cards), foot)
    return html, "head-to-head", total


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "autopsy"
    os.makedirs(OUT_DIR, exist_ok=True)
    html, name, n = {"autopsy": build_autopsy, "head2head": build_head2head}[which]()
    path = os.path.join(OUT_DIR, name + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s  (%d cards, %d bytes)" % (path, n, len(html)))


if __name__ == "__main__":
    main()
