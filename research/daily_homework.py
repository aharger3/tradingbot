"""The daily pass: what OMEN saw today, one chart per symbol, marked in 5 minutes.

Austin, 2026-09-01: "The next homework should be today's trades, how it would
have traded today. Every 's' that would have fired ... That's something we could
work to do daily ... I can really describe in detail. And you can really take all
that into account."

    python research/daily_homework.py                 # most recent archived session
    python research/daily_homework.py --day 2026-09-01

Writes research/decks/omen-daily-<day>.html and research/daily_<day>.json.
Run `research/daily_fetch.py` first -- this reads the archive, it does not fetch.

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
from research import g80_ordertype_grid as G        # noqa: E402
from research import probe_chart as pc              # noqa: E402
from research import probe_page as pp               # noqa: E402

DECKS = ROOT / "research" / "decks"
WIN_START, WIN_END = "09:30:00", "11:00:00"

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


def day_signals(sym: str, day: str):
    """(bars, levels, trades-in-window) for one symbol-day. Archive only."""
    bars, pdh, pdl, pmh, pml = G.day_pack(sym, day)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", help="session to build (default: latest archived)")
    ap.add_argument("--sym", help="one symbol only")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.demo:
        demo()
        return

    day = a.day or latest_archived_day()
    syms = [a.sym] if a.sym else universe.ALL_SYMS
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
