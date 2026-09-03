"""g72_qqq_tiebreak_build.py -- one card: QQQ, 2026-07-31. Settle a conflict.

Austin graded this symbol-day twice, seven days apart, and gave opposite
answers:

    research/marks/deck_marks_index_2026-08-19.jsonl:41
        {"type":"day","card_id":"QQQ_2026-07-31", ... "grade":"none",
         "reason_none":"missed it", ...}

    research/marks/probe_master_homework_2026-08-26.jsonl:12
        {"type":"probe","card_id":"cal_QQQ_2026-07-31_b23", ...
         "answers":{"your_grade":["S"]}, ...}

Asked which stands, he said: "Show me the chart again before I decide." This
builds that single re-look card -- same shell as g71_homework.html
(g71_homework_build.py), pared to one card and one question.

DELIBERATE REPEAT -- the one exception to the no-repeat guarantee
-------------------------------------------------------------------
build_deck.py::marked_card_ids() will (correctly) report QQQ_2026-07-31 as
already judged -- twice, which is the whole problem this card exists to fix.
This script calls it below ONLY to confirm and print that fact; it does not
filter the card out on it, and it does not touch build_deck.py or either mark
file above. When his answer comes back here it SUPERSEDES the conflicting
pair -- both stay in their files untouched, per marks/LEDGER.md ("never
delete or rewrite a mark file"). Record the supersession wherever this answer
gets logged, not by editing marks/*.jsonl.

CARD CONTENT
------------
1-minute chart, 09:30-11:00 ET, static SVG (probe_chart.render, unedited).
Only his six levels per the codebase's own definition (downgrade.py
CONFLUENCE_LEVELS, the same six build_deck.py and g71_homework_build.py both
draw): PDH, PDL, PMH, PML, ORH, ORL -- ORH/ORL is the first-5-RTH-bar opening
range, the "HOD/LOD" of the request in spirit (probe_chart.LEVELS only knows
these six keys/labels and is not touched by this script). No entry, no stop,
no grade, no outcome, no engine mark, and no hint anywhere on the page of
either of the two answers above.

One question: is this an S? YES / NO, plus an optional free-text note.

    python research/g72_qqq_tiebreak_build.py
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd
import probe_chart
import probe_page

SYMBOL = "QQQ"
DAY = "2026-07-31"
CARD_ID = "%s_%s" % (SYMBOL, DAY)
OUT_HTML = os.path.join(HERE, "g72_qqq_tiebreak.html")
DECK_ID = "g72-qqq-tiebreak"

_LVL_DRAWN = re.compile(r'class="lvl-t [^"]*"[^>]*>([A-Z]{3}) ')


def offchart_note(svg, levels, candles):
    """Name the levels the chart could not fit, with their price and side.

    Lifted from g71_homework_build.py's own helper (same docstring reasoning):
    probe_chart only lets a level widen the frame by a quarter of the
    session's own range, so a far level (PDL here -- 16+ points off a ~4-point
    tolerance) is silently dropped rather than flattening 90 candles into a
    ribbon. This names what's missing instead of quietly showing him five of
    his six levels."""
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


def levels_for(symbol, day, candles):
    """The six levels, same definitions as g71_homework_build.py levels_for()
    and build_deck.py's own inline version: ORH/ORL = first 5 RTH bars."""
    pdh, pdl, _o, _c = bd.prior_day_levels(symbol, day)
    pmh, pml = bd.premarket_extremes(symbol, day)
    orh = max(c.high for c in candles[:5]) if len(candles) >= 5 else None
    orl = min(c.low for c in candles[:5]) if len(candles) >= 5 else None
    return {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml, "orh": orh, "orl": orl}


def build():
    # --- deliberate-repeat check: confirm and log, never filter -------------
    judged = bd.marked_card_ids()
    if CARD_ID in judged:
        print("no-repeat guard: %s IS in marked_card_ids() (expected -- this is "
              "the deliberate repeat that settles the S/not-S conflict, not a "
              "guarantee failure). Proceeding anyway." % CARD_ID)
    else:
        print("no-repeat guard: %s not found in marked_card_ids() -- unexpected, "
              "the whole point of this card is that it WAS already judged twice. "
              "Proceeding anyway, since this card is hardcoded, not picked from "
              "a pool." % CARD_ID)

    candles = bd.session_candles(SYMBOL, DAY)
    if len(candles) < 60:
        raise SystemExit("only %d RTH candles for %s -- expected a full 09:30-"
                          "11:00 session" % (len(candles), CARD_ID))
    levels = levels_for(SYMBOL, DAY, candles)
    lv_rounded = {k: (round(v, 2) if v is not None else None)
                 for k, v in levels.items()}

    svg = probe_chart.render(
        [bd.candle_dict(c) for c in candles], lv_rounded, marks=[],
        label="%s %s 1-minute 09:30-11:00" % (SYMBOL, DAY))
    off = offchart_note(svg, lv_rounded, candles)

    export = json.dumps({"symbol": SYMBOL, "date": DAY, "tiebreak": True},
                        sort_keys=True).replace('"', "&quot;")

    q_is_s = probe_page.question(
        "is_s",
        "Is this an S trade?",
        "Yes or no. Nothing on this chart is marked &mdash; the 1-minute "
        "09:30&ndash;11:00 session and your six levels are all there is.",
        [("yes", "YES &mdash; this is an S"), ("no", "NO &mdash; not an S")],
        required=True,
        note_placeholder="anything you want to add &mdash; optional")

    card = ('<article class="card" data-cid="%s" data-export="%s" data-done="0">'
            '<header><span class="idx">01</span><span class="tick">%s</span>'
            '<span class="when">%s</span>'
            '<span class="tags"><span class="tag">1-min &middot; 09:30&ndash;11:00 ET</span>'
            '<span class="done-dot"></span></span></header>'
            '<div class="chartwrap">%s</div>'
            '<div class="legend"><span><b>PDH/PDL</b> prior day</span>'
            '<span><b>PMH/PML</b> pre-market</span>'
            '<span><b>ORH/ORL</b> opening range</span></div>'
            '%s%s</article>'
            % (CARD_ID, export, SYMBOL, DAY, svg, off, q_is_s))

    lede = ("One chart, one question. The 1-minute 09:30&ndash;11:00 session and "
            "your six levels &mdash; nothing else is marked: no entry, no stop, "
            "no grade, no outcome. <strong>You say yes or no.</strong>")
    footer = ("<h2>When you're done</h2><p>Tap <b>Export</b> at the top, then "
              "<b>Copy all</b> and paste it into the chat &mdash; or "
              "<b>Download .jsonl</b>. Your answer saves to this browser as you "
              "tap, and comes back if you close the page.</p>")

    html = probe_page.shell(
        title="OMEN &mdash; QQQ 7/31 re-look",
        eyebrow="OMEN homework &middot; one card, one re-look",
        h1="QQQ, July 31 &mdash; is this an S?",
        lede=lede, cards_html=card, footer_html=footer, deck_id=DECK_ID)

    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("Wrote %s (%d bytes)" % (OUT_HTML, len(html)))
    return html


if __name__ == "__main__":
    build()
