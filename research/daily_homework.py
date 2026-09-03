"""The daily pass: what OMEN saw today, one chart per symbol, marked in 5 minutes.

Austin, 2026-09-01: "The next homework should be today's trades, how it would
have traded today. Every 's' that would have fired ... That's something we could
work to do daily ... I can really describe in detail. And you can really take all
that into account."

    python research/daily_homework.py                 # most recent archived session
    python research/daily_homework.py --day 2026-09-01
    python research/daily_homework.py --day 2026-09-02 --mode s-blind

Writes research/decks/omen-daily-<day>.html and research/daily_<day>.json.
Run `research/daily_fetch.py` first -- this reads the archive, it does not fetch.

TWO MODES, TWO INSTRUMENTS. `--mode full` (the default, unchanged) is the 16:15
REVEAL: the whole tape, one card per symbol, everything the engine produced.
`--mode s-blind` is AUGUR's 11:05 deck -- bars cut at 11:00, only the symbol-days
worth his attention, the engine's own call drawn on the chart, and a comment box
as the primary field. See the block above `BLIND_END` for why it exists and why
the cut is where it is. It writes omen-daily-<day>-s.html; the two never collide.

WHY ONE CARD PER SYMBOL AND NOT ONE PER SIGNAL. On 2026-09-01 the engine produced
**269 candidates and fired 50** across 29 symbols. He takes 1-3 a day. A card per
signal is a 269-card deck asking him to adjudicate the engine's noise; a card per
symbol is 29 charts asking the only question that trains a classifier: *was there
an S on this tape, and at what minute*. His answer is then a label on the
symbol-day, which is the unit `marked_card_ids()` and every recall rig already
speak.

WHAT HIS OWN MARKS SAID WAS WRONG WITH THE LAST DECK, and what is fixed here
(research/marks/probe_g84_all_in_one_STANDING154_2026-09-01.jsonl):

* "cant critique entry and stop because cant see" (QQQ_2024-08-26) and "little
  difficult to confirm setup and what the entry candle looks like"
  (ORCL_2025-04-02) -- so every card draws the full 09:30-11:00 tape with all six
  levels, never a crop.
* "i dont see a OCR or the level its referencing because its too far away from the
  PDL" (MU_2024-10-09) -- so each engine dot is labelled with the level it broke
  (`stop_level_name`), not just a time.
* "b candle right but entry is 3 candles earlier" (UBER_2025-10-21), "the entry
  shouldve been 6 candles earlier" (PLTR_2024-09-20) -- so the minute box is the
  primary field on every card, and the engine's own minutes are drawn beside it
  for him to correct rather than described in prose.
* A section answered identically eight times measures the page, not him (the
  displacement section, 8/8 "no"). Every question here is therefore per-symbol
  and per-tape, with "nothing here" as an explicit, cheap first chip.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import universe                                     # noqa: E402
import backtest_week as bw                          # noqa: E402
import polygon_feed as pf                           # noqa: E402
from research import build_deck as deck             # noqa: E402
from research import build_omen_test1 as t1         # noqa: E402
from research import g80_ordertype_grid as G        # noqa: E402
from research import probe_chart as pc              # noqa: E402
from research import probe_page as pp               # noqa: E402

DECKS = ROOT / "research" / "decks"
WIN_START, WIN_END = "09:30:00", "11:00:00"

# ---------------------------------------------------------------------------
# --mode s-blind -- AUGUR's 11:05 deck (omen-8 ticket 02)
# ---------------------------------------------------------------------------
# The 16:15 pass above is the REVEAL: the whole tape, one card per symbol, every
# candidate the engine produced. This mode is the opposite instrument and runs
# four hours earlier, while the day is still live:
#
#   blind      bars stop at 11:00, so he is marking a chart he could actually
#              have traded, not one whose afternoon already answered the question
#   selective  cards are the symbol-days worth his attention, not all 29
#   comment    the comment box is the point. Austin, 2026-09-02: "you need to
#              take my homework more seriously and not just worry about the
#              filters i click its about the comments."
#
# WHY THE CUT IS 10:59 AND NOT 11:00. The T8 entry capture (reused verbatim from
# `build_omen_test1`) is a quarter-hour block plus a minute inside it: six blocks
# of fifteen bars, 09:30-10:59, exactly 90. A 91st bar at 11:00 would be on the
# chart and unreachable by every chip on the card. The engine agrees -- it takes
# no new entry at or after 11:00 (`backtest_week.ENTRY_CUTOFF`) -- so nothing is
# lost, and the grid and the tape end on the same candle.
BLIND_END = "10:59:00"
BLIND_BARS = 90
SBLIND_CAP = 60          # Projects/omen-decks.md; his number, not a saving

# Austin, 2026-09-03: "OCR and 84 percent rule need closer look at or emphasis in
# the cards, not sure why firing less should always be working." So an OCR or an
# 84% re-entry puts a symbol-day on the deck at ANY grade and whatever the gates
# did with it, tagged with the gate that killed it -- he is being asked whether
# the gate was wrong, which is a question the reveal deck cannot pose.
# BR_OCR_CONFLUENCE is in here because it carries an OCR leg: it IS a one-candle
# rule that also happens to be a break-and-retest (omen_bot.SignalType).
OCR84_SETUPS = {"one_candle_rule", "br_ocr_confluence", "reentry_84_rule"}

SETUP_LABEL = {
    "break_and_retest": "break &amp; retest",
    "one_candle_rule": "one candle rule",
    "br_ocr_confluence": "BR + OCR confluence",
    "reentry_84_rule": "84% re-entry",
    "fair_value_gap": "fair value gap",
    "flag": "flag",
}

# The level, and the timeframe it was drawn on. Austin, MU 2024-10-09: "i dont
# see a OCR or the level its referencing" -- a level name with no timeframe is
# half an answer, because PDH and a 1-minute swing high are not the same claim.
LEVEL_TF = {
    "PDH": "prior day", "PDL": "prior day",
    "PDO": "prior day", "PDC": "prior day",
    "PMH": "premarket 04:00-09:29", "PML": "premarket 04:00-09:29",
    "OR high": "opening range, 09:30-09:34",
    "OR low": "opening range, 09:30-09:34",
    "HOD": "session high, 1-min", "LOD": "session low, 1-min",
}

EXTRA_CSS = """
<style>
.tape{display:flex;flex-wrap:wrap;gap:7px;margin:9px 0 3px}
.tape span{background:var(--chipbg);border:1px solid var(--line);border-radius:6px;
  padding:3px 8px;font-size:11.5px;font-variant-numeric:tabular-nums}
.tape span.fired{border-color:var(--warn)}
.tape span.quiet{opacity:.55}
.sigs{width:100%;border-collapse:collapse;margin:10px 0 2px;font-size:12.5px}
.sigs th{text-align:left;font-weight:600;opacity:.6;padding:4px 7px;
  border-bottom:1px solid var(--line);font-size:10.5px;letter-spacing:.05em;
  text-transform:uppercase}
.sigs td{padding:5px 7px;border-bottom:1px solid var(--line);
  font-variant-numeric:tabular-nums}
.sigs td.k{white-space:nowrap;font-weight:600}
.sigs tr.fired td.k{color:var(--warn)}
.sigs tr.skip td{opacity:.5}
.chart .dot.f{fill:var(--warn)}   .chart text.dot-t.f{fill:var(--warn)}
.chart .dot.s{fill:#7a7a7a}       .chart text.dot-t.s{fill:#7a7a7a}
</style>
"""


def window(trades):
    return [t for t in trades if WIN_START <= t.entry_time <= WIN_END]


def day_signals(sym: str, day: str, cut: str | None = None):
    """(bars, levels, trades-in-window) for one symbol-day. Archive only.

    ``cut`` (an "HH:MM:SS", inclusive) truncates the tape BEFORE the engine sees
    it, not after. That distinction is the whole blindness guarantee: the
    candidates on a blind card have to be the ones a runner standing at 10:59
    would have had, and a filter applied to the OUTPUT of a full-day simulation
    is not that -- the 84% re-entry arms off a stop-out, and a stop-out at 11:40
    can arm a re-entry the morning could not know about.
    """
    bars, pdh, pdl, pmh, pml = G.day_pack(sym, day)
    if not bars:
        return None, None, []
    if cut:
        bars = [c for c in bars if c.timestamp <= cut]
        if not bars:
            return None, None, []
    trades = window(bw.simulate_day(sym, day, bars, pdh, pdl, None, pmh, pml))
    orb = [c for c in bars if c.timestamp < "09:35:00"]
    levels = {
        "pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
        "orh": max(c.high for c in orb) if orb else None,
        "orl": min(c.low for c in orb) if orb else None,
    }
    return bars, levels, trades


def collect(day: str, symbols) -> list:
    out = []
    for sym in symbols:
        bars, levels, trades = day_signals(sym, day)
        if not bars:
            print(f"  [{sym}] no bars -- skipped")
            continue
        out.append({
            "symbol": sym, "day": day,
            "bars": [{"t": c.timestamp, "o": c.open, "h": c.high,
                      "l": c.low, "c": c.close} for c in bars
                     if WIN_START <= c.timestamp <= WIN_END],
            "levels": levels,
            "signals": [{
                "et": t.entry_time[:5], "dir": t.direction, "grade": t.grade,
                "status": t.status, "fired": t.status == "fired",
                "setup": t.setup_type or t.signal_type,
                "level": t.stop_level_name, "entry": round(t.entry, 4),
                "stop": round(t.stop, 4), "outcome": t.outcome,
                "idx": t.entry_idx,
            } for t in trades],
        })
        f = sum(1 for t in trades if t.status == "fired")
        print(f"  [{sym}] {len(trades)} candidates, {f} fired")
    return out


def _dots(card):
    """One labelled dot per engine candidate, indexed into the WINDOW bars.

    `entry_idx` indexes the full RTH day; the chart only holds 09:30-11:00, and
    those coincide only because the window starts at the open. Re-derive from
    the timestamp anyway -- a silent off-by-N here would put every dot on the
    wrong candle and quietly invalidate every minute he gives back.
    """
    at = {b["t"][:5]: i for i, b in enumerate(card["bars"])}
    dots = []
    for s in card["signals"]:
        i = at.get(s["et"])
        if i is None:
            continue
        dots.append({"i": i, "price": s["entry"],
                     "label": ("%s %s" % (s["et"], s["grade"])),
                     "cls": "f" if s["fired"] else "s"})
    return dots


def card_html(card, n) -> str:
    sym, day = card["symbol"], card["day"]
    sigs = card["signals"]
    fired = [s for s in sigs if s["fired"]]

    tape = ['<span class="%s"><b>%d</b> candidates</span>'
            % ("quiet" if not sigs else "", len(sigs))]
    if fired:
        tape.append('<span class="fired"><b>%d</b> fired</span>' % len(fired))
        tape.append("<span>first %s</span>" % fired[0]["et"])
    else:
        tape.append('<span class="quiet">engine silent</span>')
    lv = card["levels"]
    tape.append("<span>PDH %s / PDL %s</span>"
                % (_f(lv["pdh"]), _f(lv["pdl"])))
    tape.append("<span>PMH %s / PML %s</span>"
                % (_f(lv["pmh"]), _f(lv["pml"])))

    rows = ""
    for s in sigs:
        rows += ('<tr class="%s"><td class="k">%s</td><td>%s</td><td>%s</td>'
                 '<td>%s</td><td>%s</td><td>%s</td></tr>'
                 % ("fired" if s["fired"] else "skip", s["et"],
                    s["dir"], s["grade"], s["setup"].replace("_", " "),
                    s["level"] or "-", "%.2f" % s["entry"]))
    table = ('<table class="sigs"><tr><th>ET</th><th>Dir</th><th>Grade</th>'
             '<th>Setup</th><th>Level broken</th><th>Entry</th></tr>%s</table>'
             % rows) if rows else ""

    chart = pc.render(card["bars"], card["levels"], dots=_dots(card),
                      label="%s %s  09:30-11:00" % (sym, day))

    q = pp.question(
        "s_today",
        "Was there an S on this tape?",
        "The dots are the engine's candidates - orange fired, grey it skipped. "
        "If the S is not on a dot, that is the answer we most need.",
        [("no", "No S here"), ("s", "Yes - S"), ("a", "Only an A"),
         ("missed", "S the engine never saw")],
        note_placeholder="What minute, and why. Anything you want to say about "
                         "the entry, the stop, the targets, or what the engine "
                         "got wrong.",
    )
    return ('<article class="card" data-card="%s_%s" data-n="%d">'
            '<h2>%s <span class="muted">%s</span></h2>'
            '<div class="tape">%s</div>%s%s%s</article>'
            % (sym, day, n, sym, day, "".join(tape), chart, table, q))


def _f(v):
    return "-" if v is None else ("%.2f" % v)


# ---------------------------------------------------------------------------
# s-blind: selection
# ---------------------------------------------------------------------------

def gate_verdict(t) -> str:
    """"fired", or "gated by <gate>" naming the ONE gate that killed this signal.

    `backtest_week.BacktestRunner._route` labels the outcome after delegating to
    the base, and its `skipped_tight_stop` is a catch-all covering four different
    refusals (X grade, min-stop-pct, the real tight-stop skip, and anything a
    future gate adds). The reason prose carries the tag that says which, so the
    specific statuses are trusted first and the prose disambiguates the bucket.

    Plain English, because Austin reads this: no flag names, no ticket ids.
    """
    if t.status == "fired":
        return "fired"
    # `skipped_d` is named for TradeGrade.D, which since omen-3.7 T5 is an ALIAS
    # of X and means exactly "the engine graded this do-not-trade". Saying "D" on
    # a card would be a letter from a retired ladder.
    by_status = {
        "skipped_d": "engine graded it do-not-trade",
        "skipped_level_retired": "level already used up today",
        "skipped_repeat_entry": "same level already taken today",
        "skipped_repeat_idea": "same idea already taken today",
    }
    if t.status in by_status:
        return by_status[t.status]
    r = t.reason or ""
    if "[skip: repeat idea]" in r:
        return "same idea already taken today"
    if "[skip: repeat entry]" in r:
        return "same level already taken today"
    if "[skip: stop under" in r:
        return "stop too small to be a real stop"
    if "[retired:" in r:
        return "level already used up today"
    if "[veto: at session extreme]" in r:
        return "sitting at the session high or low"
    if t.grade in ("D", "X"):
        return "engine graded it do-not-trade"
    return "stop too tight"


def level_label(name: str) -> str:
    """"PDH (prior day)" -- the level and the timeframe it was drawn on."""
    if not name:
        return "no named level"
    return "%s (%s)" % (name, LEVEL_TF.get(name, "intraday 1-min structure"))


def _sig_row(t) -> dict:
    """One engine candidate, everything a blind card needs and nothing it must
    not see. No `outcome`, no exit -- the tape it would be read off does not
    exist yet at 11:05, and on a replay it is exactly the answer being withheld.
    """
    setup = t.setup_type or t.signal_type
    return {
        "et": t.entry_time[:5], "dir": t.direction,
        "tier": t.austin_tier or "", "grade": t.grade,
        "fired": t.status == "fired", "verdict": gate_verdict(t),
        "setup": setup, "setup_label": SETUP_LABEL.get(setup, setup.replace("_", " ")),
        "ocr84": setup in OCR84_SETUPS,
        "level": t.stop_level_name or "", "level_label": level_label(t.stop_level_name),
        "entry": round(t.entry, 4), "stop": round(t.stop, 4),
        "target": round(t.target, 4), "reason": (t.reason or "").strip(),
    }


def card_rank(sigs) -> int:
    """Deck order. Lower sorts first; 9 means "not on this deck".

    S fires, then S the gates killed, then OCR/84% at any grade, then the
    S-adjacent A rows if there is room under the 60-card cap.
    """
    if any(s["tier"] == "S" and s["fired"] for s in sigs):
        return 0
    if any(s["tier"] == "S" for s in sigs):
        return 1
    if any(s["ocr84"] for s in sigs):
        return 2
    if any(s["tier"] == "A" for s in sigs):
        return 3
    return 9


RANK_LABEL = {0: "S fired", 1: "S, gated", 2: "OCR / 84%", 3: "A, S-adjacent"}


def sblind_collect(day: str, symbols) -> tuple:
    """(cards, stats). Applies the no-repeat guard and the 60-card cap."""
    marked = deck.marked_card_ids()
    cards, repeats, nobars = [], [], []
    for sym in symbols:
        cid = "%s_%s" % (sym, day)
        if cid in marked:
            # THE NO-REPEAT GUARANTEE (CLAUDE.md). A symbol-day he has already
            # judged -- in ANY corpus, `grade: "none"` included -- never comes
            # back. His felt sense of a repeat has beaten this code three times.
            repeats.append(cid)
            continue
        bars, levels, trades = day_signals(sym, day, cut=BLIND_END)
        if not bars:
            nobars.append(sym)
            continue
        sigs = [_sig_row(t) for t in trades]
        rank = card_rank(sigs)
        if rank == 9:
            continue
        cards.append({
            "symbol": sym, "day": day, "rank": rank,
            "bars": [{"t": c.timestamp, "o": c.open, "h": c.high,
                      "l": c.low, "c": c.close} for c in bars
                     if WIN_START <= c.timestamp <= BLIND_END],
            "levels": levels, "signals": sigs,
        })
        print("  [%s] %d candidates, %s" % (sym, len(sigs), RANK_LABEL[rank]))
    cards.sort(key=lambda c: (c["rank"],
                              -sum(1 for s in c["signals"] if s["fired"]),
                              -len(c["signals"]), c["symbol"]))
    stats = {"repeats": repeats, "nobars": nobars, "before_cap": len(cards)}
    if len(cards) > SBLIND_CAP:
        cards = cards[:SBLIND_CAP]
    return cards, stats


# ---------------------------------------------------------------------------
# s-blind: the card
# ---------------------------------------------------------------------------

SBLIND_CSS = """
<style>
/* 60 charts is a lot of SVG for a phone; let the browser skip the offscreen ones */
.card{content-visibility:auto; contain-intrinsic-size:auto 1000px}
.tape{display:flex;flex-wrap:wrap;gap:7px;margin:10px 16px 2px}
.tape span{background:var(--surface-2);border:1px solid var(--rule);border-radius:6px;
  padding:3px 8px;font-size:11.5px;font-family:"IBM Plex Mono",monospace;
  font-variant-numeric:tabular-nums;color:var(--ink-2)}
.tape span.fired{border-color:var(--entry);color:var(--entry)}
.tape span.gated{border-color:var(--stop);color:var(--stop)}
.sigs{width:calc(100% - 32px);border-collapse:collapse;margin:10px 16px 4px;font-size:12.5px}
.sigs th{text-align:left;font-weight:600;color:var(--ink-3);padding:4px 6px;
  border-bottom:1px solid var(--rule);font-size:10px;letter-spacing:.06em;
  text-transform:uppercase;font-family:"IBM Plex Mono",monospace}
.sigs td{padding:5px 6px;border-bottom:1px solid var(--rule);
  font-variant-numeric:tabular-nums;vertical-align:top}
.sigs td.k{white-space:nowrap;font-weight:600;font-family:"IBM Plex Mono",monospace}
.sigs tr.fired td.k{color:var(--entry)}
.sigs tr.gated td{opacity:.72}
.sigs td.v{font-size:11.5px;color:var(--ink-3)}
.sigs tr.fired td.v{color:var(--entry)}
.why{margin:0 16px 12px;font-size:11.5px;color:var(--ink-3);line-height:1.45;
  font-family:"IBM Plex Mono",monospace;word-break:break-word}
.chart .dot.f{fill:var(--entry)} .chart text.dot-t.f{fill:var(--entry)}
.chart .dot.s{fill:var(--ink-3)} .chart text.dot-t.s{fill:var(--ink-3)}
.chart .hrail.tgt{stroke:var(--up);stroke-width:1;stroke-dasharray:6 3;opacity:.85}
.chart .hrail-t.tgt{font-family:"IBM Plex Mono",monospace;font-size:9px;
  font-weight:600;fill:var(--up)}

/* progressive disclosure: the entry capture only once he says it is tradeable.
   The COMMENT never hides -- it is the primary field, and a card he refuses is
   exactly the card whose comment is worth most. */
.card[data-g=""] .q[data-q="eblock"],
.card[data-g=""] .q[data-q="emin"],
.card[data-g=""] .q[data-q="stop"],
.card[data-g=""] .readout,
.card[data-g="X"] .q[data-q="eblock"],
.card[data-g="X"] .q[data-q="emin"],
.card[data-g="X"] .q[data-q="stop"],
.card[data-g="X"] .readout{display:none}

.q[data-q="grade"] .chip{flex:1 1 calc(50% - 4px);font-weight:600}
.q[data-q="grade"] .chip[data-v="X"][aria-pressed="true"]{
  background:var(--stop);border-color:var(--stop);color:#fff}
.q[data-q="emin"] .chips{gap:6px}
.q[data-q="emin"] .chip{flex:0 0 auto;min-width:52px;text-align:center;
  font-family:"IBM Plex Mono",monospace;font-weight:600}
.q[data-q="eblock"] .chip{flex:1 1 calc(33.333% - 5px);text-align:center;
  font-family:"IBM Plex Mono",monospace;font-size:12.5px}
.readout{border-top:1px solid var(--rule);padding:11px 16px}
.readout .hint{margin:0;font-family:"IBM Plex Mono",monospace;font-size:13px;
  color:var(--ink-2)}
.readout .hint b{color:var(--entry)}
.readout .hint i{color:var(--stop);font-style:normal}
.stopchip{flex:1 1 calc(50% - 4px);font-family:"IBM Plex Mono",monospace;
  font-weight:600;display:flex;flex-direction:column;align-items:flex-start;
  gap:1px;line-height:1.25}
.stopchip small{font-family:"IBM Plex Sans",sans-serif;font-weight:400;
  font-size:11px;color:var(--ink-3)}
.stopchip[aria-pressed="true"]{background:var(--stop);border-color:var(--stop);color:#fff}
.stopchip[aria-pressed="true"] small{color:rgba(255,255,255,.8)}
.stopchip .risk{font-size:11px;color:var(--ink-3);font-weight:500}
.stopchip .risk:empty{display:none}
.stopchip[aria-pressed="true"] .risk{color:rgba(255,255,255,.85)}
.chart .usermark .band{fill:var(--accent);opacity:.09}
.chart .usermark .uentry{stroke:var(--entry);stroke-width:1.4}
.chart .usermark .ubar{stroke:var(--entry);stroke-width:1;stroke-dasharray:2 3;opacity:.75}
.chart .usermark .uentry-t{font-family:"IBM Plex Mono",monospace;font-size:9px;
  font-weight:600;fill:var(--entry)}
.chart .usermark .ustop{stroke:var(--stop);stroke-width:1.4;stroke-dasharray:4 3}
.chart .usermark .ustop-t{font-family:"IBM Plex Mono",monospace;font-size:9px;
  font-weight:600;fill:var(--stop)}

/* THE PRIMARY FIELD. Everything above it is one tap; this is the part that
   turns into a rule. It gets the accent border and the tall box. */
.q[data-q="comment"]{background:var(--accent-soft);border-top:1px solid var(--accent)}
.q[data-q="comment"] h3{color:var(--ink)}
.q[data-q="comment"] textarea.note{min-height:104px;background:var(--surface);
  border-color:var(--accent)}
@media (max-width:520px){.q[data-q="emin"] .chip{min-width:46px}}
</style>
"""

SBLIND_GRADE_OPTS = [
    ("S", "S &mdash; clean"),
    ("A", "A &mdash; one downgrade"),
    ("C", "C &mdash; two downgrades"),
    ("X", "none &mdash; I would not trade this"),
]

SBLIND_LEGEND = ('<div class="legend">'
                 '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
                 '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> premarket</span>'
                 '<span><b style="color:var(--lvl-or)">- - ORH/ORL</b> first 5 min</span>'
                 '<span><b style="color:var(--entry)">&#9650; engine entry</b></span>'
                 '<span><b style="color:var(--stop)">engine stop</b></span>'
                 '<span><b style="color:var(--up)">- - target</b></span></div>')


def _bar_index(card) -> dict:
    """HH:MM -> bar index, over the bars actually on this card's chart."""
    return {b["t"][:5]: i for i, b in enumerate(card["bars"])}


def _primary(sigs):
    """The candidate whose call gets DRAWN. Same precedence the deck is ordered
    by, so the line on the chart is the reason the card is on the deck."""
    if not sigs:
        return None
    def key(s):
        return (0 if (s["tier"] == "S" and s["fired"]) else
                1 if s["tier"] == "S" else
                2 if s["ocr84"] else 3, s["et"])
    return sorted(sigs, key=key)[0]


def sblind_questions(card) -> str:
    """**THE ONE SWAPPABLE PIECE.** Every question on a blind card, in order.

    Austin, 2026-09-03: AUGUR must not build decks in any format except the one
    being decided. The card format is still being grilled, so it is fenced off
    HERE and nowhere else -- selection (`sblind_collect`), blindness
    (`day_signals(cut=...)`), the chart, delivery and the return path are all
    format-independent and settled. Replacing this function replaces the format;
    nothing else in the file has to move.

    Two contracts it must keep, because the rest of the machinery reads them:

    * **Exactly one question carries `required=1`.** `probe_page.js::answered()`
      returns False when a card has no required question at all, so a card with
      none can never read as done and the progress bar sits at zero forever.
    * **The keys are the export schema.** `grade` / `eblock` / `emin` / `stop`
      are read by `build_omen_test1.EXTRA_JS`, which promotes them to top-level
      `entry_i` / `entry_t` / `entry_p` / `stop_p` / `side` on every exported
      row. Rename one here and the returned marks lose that field silently.
    """
    stop_chips = "".join(
        '<button class="chip stopchip" type="button" data-v="%.2f" data-src="%s" '
        'aria-pressed="false">%.2f<small>%s</small><span class="risk"></span></button>'
        % (p, lab, p, lab) for p, lab in t1.stop_candidates(card["bars"],
                                                            card["levels"]))
    return "".join([
        pp.question(
            "grade", "Your grade.",
            "S clean &middot; A one downgrade &middot; C two &middot; "
            "<b>none = you would not take this</b>. The entry capture below "
            "only appears once you say it is tradeable.",
            SBLIND_GRADE_OPTS),
        pp.question(
            "eblock", "Entry &mdash; which quarter hour?",
            "Tap the block, then the minute inside it. The chart shades the "
            "block and drops your line on the bar.",
            t1.block_opts(), required=False),
        pp.question(
            "emin", "&hellip; and which minute?",
            "These relabel to the clock as soon as a block is chosen. Entry "
            "price defaults to that candle&rsquo;s close &mdash; if you got in "
            "before it closed, type the price you actually filled at.",
            t1.minute_opts(), required=False,
            note_placeholder="(optional) the price you actually filled at, if "
                             "you entered before the candle closed"),
        '<div class="q readout"><p class="hint" data-role="entryout">'
        'no entry marked yet</p></div>',
        '<section class="q" data-q="stop" data-multi="0" data-required="0">'
        '<h3>Stop.</h3><p class="hint">Structure prices off this chart. Risk '
        'fills in once the entry is set.</p><div class="chips stoprail">%s</div>'
        '<textarea class="note" data-note="stop" placeholder="(optional) exact '
        'stop price if none of these is it"></textarea></section>' % stop_chips,
        pp.question(
            "comment", "What did you see?",
            "This is the part that becomes a rule. Anything: why the engine was "
            "wrong, what the gate should have done, what you would have waited "
            "for. One line is worth more than a tap.",
            [], required=False,
            note_placeholder="What you saw. Where you'd enter and stop. "
                             "What the engine missed."),
    ])


def sblind_card_html(card, n, total) -> str:
    sym, day, sigs = card["symbol"], card["day"], card["signals"]
    at = _bar_index(card)
    lead = _primary(sigs)

    marks, hlines, dots = [], [], []
    if lead is not None and lead["et"] in at:
        i = at[lead["et"]]
        marks.append({"i": i, "price": lead["entry"], "stop": lead["stop"],
                      "side": "L" if lead["dir"] == "call" else "S",
                      "tag": "ENGINE"})
        hlines.append({"price": lead["target"], "label": "TARGET", "cls": "tgt"})
    for s in sigs:
        if s is lead or s["et"] not in at:
            continue
        dots.append({"i": at[s["et"]], "price": s["entry"],
                     "label": "%s %s" % (s["et"], s["tier"] or s["grade"]),
                     "cls": "f" if s["fired"] else "s"})

    chart = pc.render(card["bars"], card["levels"], marks=marks, hlines=hlines,
                      dots=dots, interactive=True,
                      label="%s %s  09:30-11:00" % (sym, day))

    fired = [s for s in sigs if s["fired"]]
    tape = ['<span>%s</span>' % RANK_LABEL[card["rank"]],
            '<span><b>%d</b> candidates</span>' % len(sigs)]
    if fired:
        tape.append('<span class="fired"><b>%d</b> fired, first %s</span>'
                    % (len(fired), fired[0]["et"]))
    else:
        tape.append('<span class="gated">none fired</span>')
    if any(s["ocr84"] for s in sigs):
        tape.append('<span class="fired">OCR / 84%</span>')
    lv = card["levels"]
    tape.append("<span>PDH %s / PDL %s</span>" % (_f(lv["pdh"]), _f(lv["pdl"])))
    tape.append("<span>PMH %s / PML %s</span>" % (_f(lv["pmh"]), _f(lv["pml"])))

    rows = "".join(
        '<tr class="%s"><td class="k">%s</td><td>%s</td><td>%s</td><td>%s</td>'
        '<td>%s</td><td>%s / %s / %s</td><td class="v">%s</td></tr>'
        % ("fired" if s["fired"] else "gated", s["et"],
           "long" if s["dir"] == "call" else "short",
           s["tier"] or s["grade"], s["setup_label"], s["level_label"],
           "%.2f" % s["entry"], "%.2f" % s["stop"], "%.2f" % s["target"],
           s["verdict"])
        for s in sigs)
    table = ('<table class="sigs"><tr><th>ET</th><th>Side</th><th>Tier</th>'
             '<th>Setup</th><th>Level broken</th><th>Entry / stop / target</th>'
             '<th>What happened to it</th></tr>%s</table>' % rows) if rows else ""
    why = ('<p class="why">%s</p>' % lead["reason"]) if (lead and lead["reason"]) else ""

    closes = json.dumps([round(b["c"], 2) for b in card["bars"]],
                        separators=(",", ":"))
    export = json.dumps({
        "symbol": sym, "date": day, "mode": "s-blind", "deck_rank": card["rank"],
        "engine_tiers": sorted({s["tier"] for s in sigs if s["tier"]}),
        "engine_setups": sorted({s["setup"] for s in sigs}),
        "engine_verdicts": sorted({s["verdict"] for s in sigs}),
        "engine_n": len(sigs), "engine_fired": len(fired),
        "engine_entry": lead["entry"] if lead else None,
        "engine_stop": lead["stop"] if lead else None,
        "engine_target": lead["target"] if lead else None,
        "engine_level": lead["level"] if lead else None,
        "engine_et": lead["et"] if lead else None,
    }, separators=(",", ":"), sort_keys=True)

    head = ('<header><span class="idx">%03d/%03d</span>'
            '<span class="tick">%s</span><span class="when">%s</span>'
            '<span class="tags"><span class="tag">09:30&ndash;11:00</span>'
            '<span class="done-dot"></span></span></header>'
            % (n, total, sym, day))

    return "".join([
        '<article class="card" data-cid="%s_%s" data-n="%d" data-grade="" '
        'data-done="0" data-g="" data-closes=\'%s\' data-export=\'%s\'>'
        % (sym, day, n, closes, export),
        head,
        '<div class="chartwrap">%s</div>' % chart, SBLIND_LEGEND,
        '<div class="tape">%s</div>' % "".join(tape), table, why,
        sblind_questions(card),
        "</article>",
    ])


def sblind_build(day: str, symbols) -> tuple:
    cards, stats = sblind_collect(day, symbols)
    if not cards:
        raise SystemExit("no S / OCR / 84%% cards for %s -- nothing to send" % day)
    total = len(cards)
    by_rank = {}
    for c in cards:
        by_rank[RANK_LABEL[c["rank"]]] = by_rank.get(RANK_LABEL[c["rank"]], 0) + 1
    n_ocr = sum(1 for c in cards if any(s["ocr84"] for s in c["signals"]))
    n_fired = sum(1 for c in cards for s in c["signals"] if s["fired"])

    html = pp.shell(
        title="OMEN blind - %s" % day,
        eyebrow="blind homework - %s" % day,
        h1="What the engine saw before 11:00",
        lede="%d charts, cut at 11:00 &mdash; you are seeing exactly what it "
             "saw. The engine&rsquo;s own call is drawn on each one. Grade it, "
             "mark where you would have got in and where the stop goes, and "
             "<b>write a comment</b>. The comment is the part that changes the "
             "engine. Everything saves as you go; Export when you are done."
             % total,
        cards_html=(SBLIND_CSS
                    + "".join(sblind_card_html(c, i, total)
                              for i, c in enumerate(cards, 1))),
        footer_html="Bars: 09:30&ndash;10:59 only, from research/daily_fetch.py. "
                    "Signals: backtest_week.simulate_day on those bars alone. "
                    "Tier is the S/A/C ladder. &ldquo;What happened to it&rdquo; "
                    "names the gate that stopped a candidate becoming a trade "
                    "&mdash; say so if the gate was wrong.",
        deck_id="daily-%s" % day,
    ) + t1.EXTRA_JS.replace("__BARS__", str(BLIND_BARS))
    stats.update({"total": total, "by_rank": by_rank, "ocr84_cards": n_ocr,
                  "fired": n_fired})
    return cards, html, stats


def build(day: str, symbols) -> tuple:
    cards = collect(day, symbols)
    # Loudest tapes first: he is most likely to have an opinion where the engine
    # was most active, and the quiet ones are a fast "No S here" tap at the end.
    cards.sort(key=lambda c: (-sum(1 for s in c["signals"] if s["fired"]),
                              -len(c["signals"]), c["symbol"]))
    n_c = sum(len(c["signals"]) for c in cards)
    n_f = sum(1 for c in cards for s in c["signals"] if s["fired"])

    html = pp.shell(
        title="OMEN daily - %s" % day,
        eyebrow="daily pass - %s" % day,
        h1="What the engine saw today",
        lede="%d symbols, <b>%d candidates</b>, <b>%d fired</b>. You take 1-3. "
             "Mark where the S actually was - and where it wasn't. Every card "
             "saves as you go; Export when you are done."
             % (len(cards), n_c, n_f),
        cards_html=EXTRA_CSS + "".join(card_html(c, i)
                                       for i, c in enumerate(cards, 1)),
        footer_html="Bars: yfinance 1-min via research/daily_fetch.py. "
                    "Signals: backtest_week.simulate_day, shipped fill. "
                    "Grades are the engine's A+/A/B/C/X ladder - X means it "
                    "should not have fired.",
        deck_id="omen-daily-%s" % day,
    )
    return cards, html, n_c, n_f


def latest_archived_day() -> str:
    days = set()
    for sym in universe.ALL_SYMS[:6]:
        d = pf.ARCHIVE / sym
        if d.exists():
            days |= {f.stem for f in d.glob("*.csv")}
    if not days:
        raise SystemExit("no archive -- run research/daily_fetch.py first")
    return max(days)


def demo():
    """Self-check: every dot must land on the bar whose minute it claims.

    This is the one thing that silently destroys the deck's value -- a dot on
    the wrong candle makes every minute he gives back a correction to a lie.
    """
    day = latest_archived_day()
    cards = collect(day, ["TSLA"])
    assert cards, "TSLA produced no card"
    c = cards[0]
    assert c["bars"], "no window bars"
    assert c["bars"][0]["t"].startswith("09:30"), c["bars"][0]["t"]
    assert c["bars"][-1]["t"] <= WIN_END, c["bars"][-1]["t"]
    for d, s in zip(_dots(c), [s for s in c["signals"]
                               if s["et"] in {b["t"][:5] for b in c["bars"]}]):
        assert c["bars"][d["i"]]["t"][:5] == s["et"], \
            "dot %r landed on bar %s" % (d, c["bars"][d["i"]]["t"])
        lo, hi = c["bars"][d["i"]]["l"], c["bars"][d["i"]]["h"]
        assert lo - 0.02 <= s["entry"] <= hi + 0.02, \
            "entry %.4f outside bar %s [%.4f, %.4f]" % (s["entry"], s["et"], lo, hi)
    print("demo OK -- %s TSLA: %d bars, %d signals, every dot on its own bar"
          % (day, len(c["bars"]), len(c["signals"])))
    demo_sblind(day)


def demo_sblind(day: str | None = None):
    """Self-check for --mode s-blind. Two things can silently ruin this deck.

    **The blindness.** A card that carries one bar past 11:00 is not blind, and
    nothing on the page would say so -- he would simply be marking a chart that
    already told him the answer, and the mark would be worthless without anyone
    knowing. Asserted on the bars themselves, not on the flag that produced them.

    **The reachable grid.** The entry capture is six quarter-hour blocks of
    fifteen minutes. If the tape is longer than the grid, the last bars are on
    the chart and unreachable by every chip on the card -- the same bug class as
    a rule that becomes a branch which can never be true.
    """
    day = day or latest_archived_day()
    assert BLIND_BARS == len(t1.BLOCKS) * 15, (
        "the entry grid covers %d bars but the tape is %d -- bars past the last "
        "block are unmarkable" % (len(t1.BLOCKS) * 15, BLIND_BARS))
    bars, levels, trades = day_signals("TSLA", day, cut=BLIND_END)
    assert bars, "TSLA %s produced no blind bars" % day
    assert bars[0].timestamp.startswith("09:30"), bars[0].timestamp
    assert bars[-1].timestamp <= BLIND_END, (
        "blind tape reaches %s -- the deck is not blind" % bars[-1].timestamp)
    assert len(bars) == BLIND_BARS, "%d bars, expected %d" % (len(bars), BLIND_BARS)
    for t in trades:
        assert t.entry_time <= BLIND_END, (
            "candidate at %s is past the blind cut" % t.entry_time)
    sigs = [_sig_row(t) for t in trades]
    assert all(s["verdict"] for s in sigs), "a candidate with no gate verdict"
    assert all("[" not in s["verdict"] for s in sigs), \
        "a gate verdict leaked an engine tag: %r" % [s["verdict"] for s in sigs]
    print("demo OK -- s-blind %s TSLA: %d bars to %s, %d candidates, "
          "grid covers every bar" % (day, len(bars), bars[-1].timestamp[:5],
                                     len(sigs)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", help="session to build (default: latest archived)")
    ap.add_argument("--sym", help="one symbol only")
    ap.add_argument("--mode", choices=("full", "s-blind"), default="full",
                    help="full (default, the 16:15 reveal, one card per symbol) "
                         "or s-blind (AUGUR's 11:05 deck)")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.demo:
        demo()
        return

    day = a.day or latest_archived_day()
    syms = [a.sym] if a.sym else universe.ALL_SYMS

    if a.mode == "s-blind":
        print("building the 11:05 blind deck for %s over %d symbols"
              % (day, len(syms)))
        cards, html, st = sblind_build(day, syms)
        DECKS.mkdir(parents=True, exist_ok=True)
        out = DECKS / ("omen-daily-%s-s.html" % day)
        out.write_text(html, encoding="utf-8")
        js = ROOT / "research" / ("daily_%s_s.json" % day)
        js.write_text(json.dumps({"day": day, "mode": "s-blind",
                                  "cards": cards}, indent=1), encoding="utf-8")
        print("\n%s blind deck: %d cards (%d candidates fired), "
              "%d carry an OCR or 84%% candidate"
              % (day, st["total"], st["fired"], st["ocr84_cards"]))
        for k in ("S fired", "S, gated", "OCR / 84%", "A, S-adjacent"):
            if st["by_rank"].get(k):
                print("  %-14s %d" % (k, st["by_rank"][k]))
        print("  no-repeat guard held back %d symbol-days; %d symbols had no bars"
              % (len(st["repeats"]), len(st["nobars"])))
        if st["before_cap"] > SBLIND_CAP:
            print("  capped at %d (had %d)" % (SBLIND_CAP, st["before_cap"]))
        print("  deck -> %s" % out)
        print("  data -> %s" % js)
        return

    print("building the daily pass for %s over %d symbols" % (day, len(syms)))
    cards, html, n_c, n_f = build(day, syms)

    DECKS.mkdir(parents=True, exist_ok=True)
    out = DECKS / ("omen-daily-%s.html" % day)
    out.write_text(html, encoding="utf-8")
    js = ROOT / "research" / ("daily_%s.json" % day)
    js.write_text(json.dumps({"day": day, "cards": cards}, indent=1),
                  encoding="utf-8")

    print("\n%s: %d symbols, %d candidates, %d fired"
          % (day, len(cards), n_c, n_f))
    print("  deck -> %s" % out)
    print("  data -> %s" % js)


if __name__ == "__main__":
    main()
