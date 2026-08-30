"""g89 page -- the anatomy sample, as a page Austin can mark on a phone.

Reads `research/g89_trade_anatomy.json` (written by g89_trade_anatomy.py) and
renders one card per trade: the chart with every component drawn on it, the
component table with times and R, and one question that lets him point at the
component that is wrong.

WHY A CHIP QUESTION AND NOT JUST A TEXT BOX. `build_deck.marked_card_ids()` --
the no-repeat guarantee -- reads the `answers` dict on an exported row. A
free-text-only card exports `notes` and no `answers`, so it is invisible to the
guarantee and the same symbol-day can be served to him again later. Every card
here therefore carries a real multi-select alongside the prose.

    python research/g89_anatomy_page.py

Writes research/decks/omen-trade-anatomy.html.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import probe_chart as pc            # noqa: E402
from research import probe_page as pp             # noqa: E402

SRC = ROOT / "research" / "g89_trade_anatomy.json"
OUT = ROOT / "research" / "decks" / "omen-trade-anatomy.html"
DECK_ID = "omen-trade-anatomy"

EXTRA_CSS = """
<style>
.anat{width:100%;border-collapse:collapse;margin:14px 0 4px;font-size:13px}
.anat th{text-align:left;font-weight:600;opacity:.62;padding:5px 8px;
  border-bottom:1px solid var(--line);font-size:11px;letter-spacing:.06em;
  text-transform:uppercase}
.anat td{padding:6px 8px;border-bottom:1px solid var(--line);
  font-variant-numeric:tabular-nums}
.anat td.k{white-space:nowrap;font-weight:600}
.anat td.n{text-align:right;white-space:nowrap}
.anat tr.plan td{opacity:.72}
.anat tr.hit td.k{color:var(--ok)}
.anat tr.out td.k{color:var(--warn)}
.tape{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 2px}
.tape b{font-weight:600}
.tape span{background:var(--chipbg);border:1px solid var(--line);border-radius:6px;
  padding:4px 9px;font-size:12px;font-variant-numeric:tabular-nums}
.tape span.bad{border-color:var(--warn)}
.verdict{margin:12px 0 2px;padding:10px 12px;border-left:3px solid var(--warn);
  background:var(--chipbg);border-radius:0 6px 6px 0;font-size:13.5px;line-height:1.5}
.chart .pt1{stroke:#c9832b}       .chart text.pt1{fill:#c9832b}
.chart .rtgt{stroke:#5b8db8}      .chart text.rtgt{fill:#5b8db8}
.chart .tgt{stroke:#7a7a7a;stroke-dasharray:2 4}  .chart text.tgt{fill:#7a7a7a}
.chart .dot.sc{fill:#c9832b}      .chart text.dot-t.sc{fill:#c9832b}
.chart .dot.be{fill:#5b8db8}      .chart text.dot-t.be{fill:#5b8db8}
.chart .dot.ex{fill:var(--warn)}  .chart text.dot-t.ex{fill:var(--warn)}
.chart .dot.pk{fill:var(--ok)}    .chart text.dot-t.pk{fill:var(--ok)}
</style>
"""

KIND = {
    "entry": ("ENTRY", "hit"),
    "stop_set": ("STOP", "plan"),
    "target_set": ("2R TARGET", "plan"),
    "scale_planned": ("PT1 PLAN", "plan"),
    "runner_planned": ("RUNNER PLAN", "plan"),
    "scale_hit": ("PT1 HIT - 50% OFF", "hit"),
    "stop_to_be": ("STOP -> BREAK-EVEN", "hit"),
    "exit": ("EXIT", "out"),
}

WRONG = [
    ("entry", "The entry"),
    ("stop", "The stop"),
    ("pt1", "Where PT1 sits"),
    ("scale_size", "Taking 50% off"),
    ("be", "Moving the stop to BE"),
    ("runner", "The runner target"),
    ("exit", "The exit"),
    ("nothing", "Nothing - this is right"),
    ("no_trade", "I would not have taken this at all"),
]


def card(t, n, total):
    bars = t["bars"]
    # Run the window to 11:00 (bar 90) even when the trade closed at 09:50. The
    # question on this card is partly "should it have exited there", and that is
    # unanswerable if the chart stops eight bars after the exit -- he has to see
    # what the tape went on to do. Never past 11:30, or the candles turn into a
    # ribbon on a phone.
    last = min(len(bars) - 1, max(t["exit_i"] + 8, t["mfe_i"] + 8, 90), 120)
    cd = [{"t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"]}
          for b in bars[:last + 1]]
    long = t["dir"] == "call"

    hl = [{"price": t["target"], "label": "2R", "cls": "tgt"}]
    if t["scale_level"]:
        hl.append({"price": t["scale_level"], "label": "PT1", "cls": "pt1"})
    if t["runner_target"]:
        hl.append({"price": t["runner_target"], "label": "RUN", "cls": "rtgt"})

    dots = []
    for e in t["events"]:
        if e["i"] > last:
            continue
        if e["kind"] == "scale_hit":
            dots.append({"i": e["i"], "price": e["price"], "cls": "sc",
                         "label": "PT1 %+.2fR" % e["r"]})
        elif e["kind"] == "stop_to_be":
            dots.append({"i": e["i"], "price": e["price"], "cls": "be",
                         "label": "BE"})
        elif e["kind"] == "exit":
            dots.append({"i": e["i"], "price": e["price"], "cls": "ex",
                         "label": "OUT %+.2fR" % e["r"]})
    if t["mfe_i"] <= last and t["mfe_r"] > 0.02:
        pk = bars[t["mfe_i"]]
        dots.append({"i": t["mfe_i"], "price": pk["h"] if long else pk["l"],
                     "cls": "pk", "label": "best %+.2fR" % t["mfe_r"]})

    levels = {k: v for k, v in (("pdh", t["pdh"]), ("pdl", t["pdl"]),
                                ("pmh", t["pmh"]), ("pml", t["pml"]))
              if v is not None}
    svg = pc.render(cd, levels,
                    marks=[{"i": t["entry_i"], "price": t["entry"],
                            "stop": t["stop"], "side": "L" if long else "S",
                            "tag": "ENT"}],
                    label="%s %s" % (t["sym"], t["day"]),
                    hlines=hl, dots=dots,
                    vlines=[{"i": t["entry_i"], "label": t["et"], "cls": "clk"}])

    rows = []
    for e in t["events"]:
        lab, cls = KIND.get(e["kind"], (e["kind"].upper(), "plan"))
        rows.append('<tr class="%s"><td class="k">%s</td><td>%s</td>'
                    '<td class="n">%.2f</td><td class="n">%+.2fR</td>'
                    '<td>%s</td></tr>'
                    % (cls, lab, e["et"], e["price"], e["r"], e["note"]))
    table = ('<table class="anat"><tr><th>component</th><th>time</th>'
             '<th>price</th><th>R</th><th>what it is</th></tr>%s</table>'
             % "".join(rows))

    tape = ['<span><b>his grade</b> S</span>',
            '<span><b>engine</b> %s</span>' % t["grade"],
            '<span><b>setup</b> %s</span>' % (t["setup_label"] or t["setup"]),
            '<span><b>risk</b> $%.2f = 1R</span>' % t["risk"],
            '<span%s><b>booked</b> %+.2fR ($%s)</span>'
            % (' class="bad"' if t["r"] < 0 else "", t["r"], "{:,.0f}".format(t["pnl"])),
            '<span><b>offered</b> %+.2fR</span>' % t["mfe_r"],
            '<span class="bad"><b>left behind</b> %+.2fR</span>' % t["left_on_table_r"]]

    if t["scaled"]:
        v = ("Half the position came off at <b>%+.2fR</b> and the stop went to "
             "break-even there. The trade went on to offer <b>%+.2fR</b>. "
             "PT1 sits at the %s of the day as of the entry bar, which on a "
             "retest entry is only <b>%.2f</b> away — %.0f%% of the risk."
             % (t["scale_r"], t["mfe_r"], "high" if long else "low",
                abs(t["scale_level"] - t["entry"]),
                abs(t["scale_level"] - t["entry"]) / t["risk"] * 100))
    else:
        v = ("PT1 was never reached, so the whole position rode the original "
             "stop. It offered <b>%+.2fR</b> at %s before it went to "
             "<b>%+.2fR</b>." % (t["mfe_r"], t["mfe_et"], t["r"]))

    q = pp.question(
        "wrong", "Which component is wrong here?",
        "Tick everything that is off. Then say in the box what should have "
        "happened instead — the price, the time, or the rule.",
        WRONG, multi=True, required=True,
        note_placeholder="e.g. \"PT1 should be the 2R target, not the HOD\" or "
                         "\"entry is 3 candles late, should be 09:47\"")

    # `data-cid` is the attribute probe_page's exporter reads for `card_id`
    # (probe_page.py:349) -- `data-card` exports null and the row becomes
    # invisible to build_deck.marked_card_ids(), i.e. a lost mark. `data-export`
    # then merges these keys into every exported row so the row identifies its
    # own symbol-day even if card_id parsing ever changes. No `data-grade`: this
    # page never asks him for a grade and must not write one into the pool.
    export = json.dumps({"symbol": t["sym"], "day": t["day"], "et": t["et"],
                         "dir": t["dir"], "setup": t["setup"],
                         "section": "trade_anatomy",
                         "source_deck": DECK_ID}).replace('"', "&quot;")
    return ('<article class="card" data-cid="%s_%s" data-export="%s" data-n="%d">'
            '<header><p class="eyebrow">%d / %d &middot; he graded this day S</p>'
            '<h2>%s &middot; %s &middot; %s %s</h2></header>'
            '<div class="chart">%s</div>'
            '<div class="tape">%s</div>'
            '%s<div class="verdict">%s</div>%s</article>'
            % (t["sym"], t["day"], export, n, n, total, t["sym"], t["day"],
               t["et"], "long" if long else "short", svg, "".join(tape), table,
               v, q))


def main():
    blob = json.load(open(SRC, encoding="utf-8"))
    trades = blob["trades"]
    cards = "".join(card(t, i + 1, len(trades)) for i, t in enumerate(trades))
    html = pp.shell(
        "OMEN — trade anatomy",
        "sample, not a deck",
        "Every component of %d trades" % len(trades),
        "These are days you graded <b>S</b>. For each one: exactly where it "
        "entered, exactly where the stop sat, where PT1 was and when half came "
        "off, when the stop moved to break-even, and where it finally exited — "
        "next to what the trade actually went on to offer. Tick the components "
        "that are wrong and say what should have happened. Everything saves as "
        "you go; hit Export when you are done.",
        EXTRA_CSS + cards,
        "1R = $1,000. Times are ET. R is measured against the original stop. "
        "Built by research/g89_trade_anatomy.py + research/g89_anatomy_page.py "
        "from research/bt2y_trades.json (honest close fill).",
        DECK_ID)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print("wrote %s (%d cards, %.0f KB)"
          % (OUT, len(trades), OUT.stat().st_size / 1024))


if __name__ == "__main__":
    main()
