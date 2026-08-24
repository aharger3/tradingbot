"""build_calibration.py -- OMEN 6 ticket 20: tune the grader against Austin, not against a curve.

T66 measured `downgrade.py` over his 120 graded day-cards and the verdict was "the
mechanism works, the thresholds do not":

    grade distribution   S/A/C = 168 / 304 / 778
    his own corpus       S/A/C =  28 /  27 /   3

The tempting fix is to fit the seven thresholds to those 120 rows. That is
overfitting to the only data the gate is measured on, and it would produce a number
nobody should believe.

So this asks him instead, and it asks the ONLY question that tunes anything: on a
chart where the grader and his own mark disagree, **which tripped downgrade does he
reject?** A card is not "do you like this trade" -- it is "the machine says these
three things are wrong with it; which of them is actually wrong?"

Two disagreement classes, deliberately balanced:

  GRADER TOO HARSH  it graded C or A on a bar within +/-3 of one of his 64 marked
                    entries. He took it. Something in the trip list is a false alarm.
  GRADER TOO SOFT   it graded S on a day he graded `none`. He refused it. Either a
                    downgrade failed to fire, or one is missing from the list.

Both are needed. Tuning on one direction alone moves recall and precision the same
way and learns nothing.

    python research/build_calibration.py
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import probe_chart
import probe_page
from research import downgrade as dg
from research.t4_engine_recall import (CaptureRunner, rth_candles, prior_day_levels,
                                       premarket_extremes, htf_bias, ENTRY_CUTOFF)
from research.t60_baseline import load_day_cards

OUT_DIR = os.path.join(HERE, "probes")
SESSION_START, SESSION_END = "09:30", "11:00"
TOL = 3
PER_CLASS = 6

PRETTY = {
    "no_displacement": "No displacement on the break",
    "stale_retest": "Stale retest (>%d bars after the break)" % dg.STALE_BARS,
    "level_not_respected": "Level not respected — closes sitting on it",
    "exhausted": "Stock exhausted — large move already made",
    "counter_trend_not_respected": "Counter-trend candles not bought back",
    "break_then_rejection": "Broke, then gave it straight back",
    "no_retest": "Never retested the level",
    "ocr_not_respected": "Price closed through the OCR",
}


def window(candles):
    out = []
    for c in candles:
        t = c.timestamp[11:16] if "T" in c.timestamp else c.timestamp[:5]
        if SESSION_START <= t < SESSION_END:
            out.append(c)
    return out


def as_dicts(cs):
    return [{"t": c.timestamp, "o": c.open, "h": c.high, "l": c.low,
             "c": c.close, "v": c.volume} for c in cs]


def scan(symbol, day):
    """Every signal on the day, each carrying its downgrade record."""
    candles = rth_candles(symbol, day)
    if not candles:
        return None, None
    pdh, pdl, pdo, pdc = prior_day_levels(symbol, day)
    pmh, pml = premarket_extremes(symbol, day)
    r = CaptureRunner(symbol)
    r.pdh, r.pdl = pdh, pdl
    r.pmh, r.pml = pmh, pml
    r.pd_open, r.pd_close = pdo, pdc
    bias = htf_bias(symbol, day)
    r.htf_bias = bias
    r.qqq_breaks = None
    bars = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
            for c in candles]

    out = []
    for i in range(5, len(candles)):
        if ENTRY_CUTOFF and candles[i].timestamp >= ENTRY_CUTOFF:
            continue
        r.candles = candles[: i + 1]
        before = len(r.captured)
        try:
            r.detect_signals()
        except Exception:
            continue
        for s in r.captured[before:]:
            rec = dg.score(bars, i, s.get("stop"), s.get("direction") == "call",
                           htf_bias=bias)
            if rec is None:
                continue
            out.append({"bar": i, "entry": s.get("entry"), "stop": s.get("stop"),
                        "side": "L" if s.get("direction") == "call" else "S",
                        "level": s.get("stop_level_name"), "rec": rec,
                        "t": candles[i].timestamp})
    return out, candles


LEGEND = ('<div class="legend">'
          '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b></span>'
          '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b></span>'
          '<span><b style="color:var(--lvl-or)">- - ORH/ORL</b></span>'
          '<span><b style="color:var(--entry)">&#9650; ENGINE ENTRY</b></span>'
          '<span><b style="color:var(--stop)">STOP</b></span></div>')


def card(idx, total, sym, day, sig, klass, austin_grade):
    cs = window(rth_candles(sym, day))
    if len(cs) < 60:
        return None
    dicts = as_dicts(cs)
    pdh, pdl, _o, _c = prior_day_levels(sym, day)
    pmh, pml = premarket_extremes(sym, day)
    lv = {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
          "orh": max(x["h"] for x in dicts[:5]), "orl": min(x["l"] for x in dicts[:5])}
    # the scan indexes the full RTH list; the chart shows the 09:30-11:00 window,
    # and they share index 0 because rth_candles starts at 09:30
    marks = [{"i": sig["bar"], "price": sig["entry"], "stop": sig["stop"],
              "side": sig["side"], "tag": "OMEN"}] if sig["bar"] < len(dicts) else []
    chart = probe_chart.render(dicts, lv, marks, "%s %s" % (sym, day))

    rec = sig["rec"]
    tripped = rec["tripped"]
    trip_html = "".join(
        '<li style="margin:2px 0">%s</li>' % PRETTY.get(t, t) for t in tripped) or \
        '<li style="margin:2px 0;color:var(--ink-3)">nothing — the grader found it clean</li>'
    verdict = ('<div class="q" style="border-top:0;padding-bottom:0">'
               '<p class="hint" style="margin:0 0 6px">The grader said '
               '<b style="color:var(--accent)">%s</b>%s. You said '
               '<b>%s</b>.</p>'
               '<ul style="margin:0 0 4px 18px;padding:0;font-size:13.5px">%s</ul></div>'
               % (rec["grade"],
                  " (with confluence +1)" if rec["confluence"] else "",
                  austin_grade, trip_html))

    tags = [(austin_grade, False),
            ("grader: %s" % rec["grade"], True)]
    tag_html = "".join('<span class="tag%s">%s</span>' % (" warn" if w else "", t)
                       for t, w in tags)
    head = ('<header><span class="idx">%02d/%02d</span><span class="tick">%s</span>'
            '<span class="when">%s &middot; %s &middot; %s</span>'
            '<span class="tags">%s<span class="done-dot"></span></span></header>'
            % (idx, total, sym, day, sig["t"][11:16] if "T" in sig["t"] else sig["t"][:5],
               sig["level"] or "?", tag_html))

    reject_opts = [(t, PRETTY.get(t, t)) for t in tripped] or \
                  [("none_tripped", "Nothing was flagged")]

    body = [
        '<article class="card" data-cid="%s_%s_b%d" data-grade="%s" data-done="0">'
        % (sym, day, sig["bar"], austin_grade),
        head,
        '<div class="chartwrap">%s</div>' % chart, LEGEND, verdict,
        probe_page.question(
            "your_grade", "What is this, actually?",
            "Your grade for the engine's entry, not for the day.",
            [("S", "S"), ("A", "A"), ("C", "C"), ("no", "Not a trade at all")]),
        probe_page.question(
            "reject", "Which flags are WRONG?",
            "Tap any the machine got wrong. This is the tuning signal — a flag you "
            "reject is one whose threshold is too tight."
            if tripped else
            "It flagged nothing. If you would not take this, something is missing "
            "from the list — say what in the note.",
            reject_opts, multi=True, required=False,
            note_placeholder="(optional) what it missed, or what it got wrong"),
        "</article>",
    ]
    return "".join(body)


def main():
    days, marks = load_day_cards()
    by_day = defaultdict(list)
    for m in marks:
        if m.get("entry_i") is not None:
            by_day[(m["symbol"], m["date"])].append(m)
    graded = {k: (v.get("grade") or "").strip() for k, v in days.items()}

    harsh, soft = [], []
    for (sym, date) in sorted(days):
        if len(harsh) >= PER_CLASS and len(soft) >= PER_CLASS:
            break
        g = graded[(sym, date)]
        if g == "" or (g != "none" and not by_day.get((sym, date))):
            continue
        sigs, _cs = scan(sym, date)
        if not sigs:
            continue
        mine = by_day.get((sym, date), [])
        for s in sigs:
            near = any(abs(s["bar"] - m["entry_i"]) <= TOL for m in mine)
            if g != "none" and near and s["rec"]["grade"] != "S" and len(harsh) < PER_CLASS:
                harsh.append((sym, date, s, "harsh", g))
                break
            if g == "none" and s["rec"]["grade"] == "S" and len(soft) < PER_CLASS:
                soft.append((sym, date, s, "soft", "none"))
                break

    picked = harsh + soft
    total = len(picked)
    cards = []
    n = 0
    for sym, date, sig, klass, g in picked:
        n += 1
        html = card(n, total, sym, date, sig, klass, g)
        if html:
            cards.append(html)

    foot = ("<h2>Why these cards</h2>"
            "<p>Every one is a chart where the grader and you <b>disagree</b>. The first "
            "half are entries you took and it did not grade S. The second half are days you "
            "refused and it graded S anyway. Tuning on one direction alone moves recall and "
            "precision the same way and teaches nothing.</p>"
            "<p>The thresholds behind those flags are <b>numbers I invented</b>. You gave the "
            "eight variables; nobody set the constants. Every flag you reject is one whose "
            "number is too tight, and that is the entire point of this deck.</p>"
            "<p>Saves as you tap. <b>Export → Copy all</b> when you're done.</p>")

    html = probe_page.shell(
        "Grader Calibration",
        "OMEN 6 &middot; ticket 20",
        "The machine says these are wrong. Are they?",
        "Twelve charts where the grader disagrees with you. It shows its reasons; you "
        "say which reasons are bad. About <strong>six minutes</strong>.",
        "".join(cards), foot, "grader-calibration")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "grader-calibration.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%d cards: %d harsh, %d soft)"
          % (path, len(cards), len(harsh), len(soft)))


if __name__ == "__main__":
    main()
