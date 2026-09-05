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
`--mode s-blind` is AUGUR's 11:05 deck -- **deck kind 3**, settled by grilling
2026-09-03 and specified in `Projects/omen-decks.md`. It is not a smaller reveal;
it is the opposite instrument:

  * every card is cut at the bar the ENGINE ACTED ON, not at a fixed clock, so
    the tape stops where the decision was;
  * for every fire card, one SILENT symbol-day from the same session cut to the
    same bar index, shuffled in, so length is not a tell;
  * the engine's grade, direction, entry, stop, target, reasons and even whether
    the card is a fire or a silent day are HELD OUT. They go to the sidecar
    `research/daily_<day>_s.json`, which is the evening reveal's answer key;
  * the marks are Test 2's, and the comment box is the primary field.

It writes omen-daily-<day>-s.html; the two modes never collide.

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
import collections
import json
import random
import re
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
#   blind      the session stops at 11:00 and each CARD stops at the bar the
#              engine acted on, so he is marking the chart a trader actually had
#              in front of him, not one whose next hour answered the question
#   held out   nothing about the engine's call is on the card, not even whether
#              there was one -- that is the sidecar's job
#   selective  cards are the symbol-days worth his attention, plus a matched
#              silent day for each, so "something is here" is not the default
#   comment    the comment box is the point. Austin, 2026-09-02: "you need to
#              take my homework more seriously and not just worry about the
#              filters i click its about the comments."
#
# WHY THE SESSION CUT IS 10:59 AND NOT 11:00. This is the OUTER bound; each card
# is cut earlier, at its own fire bar. The T8 entry capture (reused verbatim from
# `build_omen_test1`) is a quarter-hour block plus a minute inside it: six blocks
# of fifteen bars, 09:30-10:59, exactly 90. A 91st bar at 11:00 would be on the
# chart and unreachable by every chip on the card. The engine agrees -- it takes
# no new entry at or after 11:00 (`backtest_week.ENTRY_CUTOFF`) -- so nothing is
# lost, and the grid and the tape end on the same candle. Per card the grid is
# trimmed further, to the blocks that fit that card's own tape.
BLIND_END = "10:59:00"
BLIND_BARS = 90
SBLIND_CAP = 60          # Projects/omen-decks.md; his number, not a saving
# A card cut before 09:45 is not a chart, it is an opening range. The shallowest
# fire seen so far is bar 14 (09:44), which is exactly this floor.
SBLIND_MIN_BARS = 15

# Austin, 2026-09-03: "OCR and 84 percent rule need closer look at or emphasis in
# the cards, not sure why firing less should always be working." So a one-candle
# rule or an 84% re-entry puts a symbol-day on the deck at ANY grade, even when
# every gate killed it.
#
# BR_OCR_CONFLUENCE IS DELIBERATELY NOT HERE, and this is a selection decision,
# not a claim that a confluence signal is not an OCR -- it is one, and it still
# counts as an OCR everywhere else in this file. It sits on 183 of the 226
# candidates of 2026-09-02, i.e. on 28 of 29 symbols. Using it as a SELECTION
# trigger therefore makes every symbol-day a fire card, which leaves no silent
# partner for any of them and collapses deck kind 3's whole no-tell design
# (29 symbols cannot supply 28 silent days). Measured both ways on 09-02 and
# 09-03: under the strict reading every pure OCR/84 symbol-day already carries
# an S, so his emphasis costs zero extra cards and loses nothing.
OCR84_SETUPS = {"one_candle_rule", "reentry_84_rule"}

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
# s-blind: selection (deck kind 3, Projects/omen-decks.md, 2026-09-03)
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


def first_bar(sigs, pred) -> int | None:
    """Index of the earliest candidate matching `pred`, or None."""
    hits = [s["i"] for s in sigs if s["i"] is not None and pred(s)]
    return min(hits) if hits else None


def classify(sigs) -> tuple:
    """(kind, cut index) for one symbol-day, or (None, first candidate index).

    A FIRE card is a symbol-day the engine had an opinion about, and the cut is
    the bar that opinion landed on -- the first S fire, else the first S at all,
    else the first one-candle-rule or 84% candidate. A symbol-day with none of
    those is a SILENT candidate, and what comes back instead is the bar its
    first candidate of ANY kind appeared on, which is how deep a silent tape can
    be cut before it stops being silent.
    """
    i = first_bar(sigs, lambda s: s["tier"] == "S" and s["fired"])
    if i is not None:
        return "S fired", i
    i = first_bar(sigs, lambda s: s["tier"] == "S")
    if i is not None:
        return "S gated", i
    i = first_bar(sigs, lambda s: s["ocr84"])
    if i is not None:
        return "OCR / 84%", i
    return None, first_bar(sigs, lambda s: True)


def match_silent(fires, pool):
    """Pair each fire card with a silent symbol-day cut to the SAME bar index.

    `fires` is [(sym, kind, cut)], `pool` is [(sym, first_candidate_index)] where
    a symbol that never produced a candidate carries None. A silent card cut at
    bar k is only honestly silent if that symbol's first candidate is after k, so
    this is an interval matching, and it is solved the classic way: hand out the
    DEEPEST cuts first and give each the SHALLOWEST silent tape that still covers
    it, so the deep-silent symbols stay available for the deep fires.

    THE UNIVERSE IS THE BINDING CONSTRAINT, NOT THIS FUNCTION. 29 symbols cannot
    supply one silent partner for every fire card once most of them fire, and a
    card cut at 10:57 needs a symbol that produced nothing for 87 minutes --
    usually there is none. It returns what actually exists; the caller reports
    the shortfall rather than papering over it by repeating a symbol.
    """
    INF = 10 ** 9
    avail = sorted(((f if f is not None else INF), s) for s, f in pool)
    out = []
    for sym, _kind, cut in sorted(fires, key=lambda x: -x[2]):
        for j, (f, s2) in enumerate(avail):
            if f > cut:
                out.append((s2, cut))
                avail.pop(j)
                break
    return out


def s_bars(sigs) -> list:
    """Every distinct bar an S candidate landed on, with whether that bar fired.

    Austin, 2026-09-04: "all s cards ... only care about the main 10 stocks".
    One card per symbol shows him the FIRST S and cuts the tape there, so a
    second S at 10:33 on the same symbol is never on any chart. Per-signal decks
    make each S bar its own card. Same-minute duplicates (two candidates on one
    bar, different levels) collapse to one card -- the chart would be identical.
    """
    out = {}
    for s in sigs:
        if s["tier"] == "S" and s["i"] is not None:
            out[s["i"]] = out.get(s["i"], False) or s["fired"]
    return sorted(out.items())


def sblind_collect(day: str, symbols, per_signal: bool = False) -> tuple:
    """(cards, stats). Kind 3: fire-bar cut, matched silent cards, engine held out.

    ``per_signal`` = one card per S bar instead of one per symbol (see `s_bars`).
    Default (``per_signal=False``): one card per symbol-day, CLAUDE.md's rule.
    On 2026-09-03 the per-signal path dealt AMD five times, AMZN four, META
    three -- Austin: "so many repeats", four of his answers literally say
    "same trade" (H1, OMEN 10.0). A symbol with several S bars in one session
    still gets exactly one card; its tape runs through the LAST S bar so every
    one of them is on screen, and each gets a plain cut line (see
    ``sblind_card_html``).
    """
    seen = deck.marked_card_ids() | deck.served_card_ids()
    scan, repeats, nobars = {}, [], []
    for sym in symbols:
        if "%s_%s" % (sym, day) in seen:
            # THE NO-REPEAT GUARANTEE (CLAUDE.md). A symbol-day he has already
            # judged OR ever been SERVED -- shown on any deck, graded or not,
            # per `build_deck.served_card_ids()` -- never comes back. His felt
            # sense of a repeat has beaten this code three times; a card he
            # only looked at and never graded was the fourth way it slipped
            # through (H1, OMEN 10.0).
            repeats.append("%s_%s" % (sym, day))
            continue
        bars, levels, trades = day_signals(sym, day, cut=BLIND_END)
        if not bars or len(bars) < SBLIND_MIN_BARS:
            nobars.append(sym)
            continue
        at = {c.timestamp[:5]: i for i, c in enumerate(bars)}
        scan[sym] = {
            "bars": [{"t": c.timestamp, "o": c.open, "h": c.high,
                      "l": c.low, "c": c.close} for c in bars],
            "levels": levels,
            "sigs": [dict(_sig_row(t), i=at.get(t.entry_time[:5]))
                     for t in trades],
        }

    fires, pool = [], []
    for sym, d in scan.items():
        if per_signal:
            hits = [(sym, "S fired" if f else "S gated", i)
                    for i, f in s_bars(d["sigs"]) if i + 1 >= SBLIND_MIN_BARS]
            if hits:
                fires.extend(hits)
                continue
        kind, i = classify(d["sigs"])
        if kind is None:
            pool.append((sym, i))
        elif i is not None and i + 1 >= SBLIND_MIN_BARS:
            fires.append((sym, kind, i))

    picked = [(sym, kind, cut, False) for sym, kind, cut in fires]
    for sym, cut in match_silent(fires, pool):
        picked.append((sym, "silent", cut, True))

    # The cap, in the order the standard names: OCR/84 rows that are not S go
    # first, then silent cards, and an S fire is never dropped.
    if len(picked) > SBLIND_CAP:
        order = {"S fired": 0, "S gated": 1, "silent": 2, "OCR / 84%": 3}
        picked.sort(key=lambda p: order.get(p[1], 4))
        picked = picked[:SBLIND_CAP]

    cards = []
    for sym, kind, cut, silent in picked:
        d = scan[sym]
        cards.append({
            "symbol": sym, "day": day, "kind": kind, "silent": silent,
            # Per-signal decks hold several cards for one symbol-day, and the
            # page keys its saves on data-cid, so the cut bar joins the id.
            # `build_deck._judgement_key` already strips a `_bNN` suffix.
            "cid": "%s_%s_b%d" % (sym, day, cut) if per_signal
                   else "%s_%s" % (sym, day),
            "cut_i": cut, "cut_t": d["bars"][cut]["t"][:5],
            # WHAT HE SEES.
            "bars": d["bars"][:cut + 1],
            "levels": d["levels"],
            # HELD OUT (deck kind 3). The engine's grade, direction, entry,
            # stop, target, reasons AND whether this card is a fire or a silent
            # day. None of it reaches the HTML; it is here for the evening
            # reveal card and for scoring his marks against the engine.
            "signals": d["sigs"],
        })

    # Order random. A deck sorted by anything is a deck whose order is a hint,
    # and the whole point of kind 3 is that a card carries no tell. Seeded on the
    # session, so rebuilding the same day gives the same deck.
    random.Random("augur-%s" % day).shuffle(cards)
    if per_signal:
        # A longer tape of the same symbol shows how the shorter one resolved,
        # so within a symbol the cuts must run short to long. Symbol order stays
        # the shuffle; only the tapes inside a symbol are sorted.
        pos = {}
        for c in cards:
            pos.setdefault(c["symbol"], len(pos))
        cards.sort(key=lambda c: (pos[c["symbol"]], c["cut_i"]))

    n_silent = sum(1 for c in cards if c["silent"])
    stats = {"repeats": repeats, "nobars": nobars, "fires": len(fires),
             "silent": n_silent, "pool": len(pool),
             "unmatched": len(fires) - n_silent,
             "by_kind": collections.Counter(c["kind"] for c in cards)}
    return cards, stats


# ---------------------------------------------------------------------------
# s-blind: the card
# ---------------------------------------------------------------------------

SBLIND_CSS = """
<style>
/* 60 charts is a lot of SVG for a phone; let the browser skip the offscreen ones */
.card{content-visibility:auto; contain-intrinsic-size:auto 900px}
.chip[hidden]{display:none!important}

/* PROGRESSIVE DISCLOSURE, and it is also the card's economics: an ungraded card
   shows one question, a `none` card costs one tap plus a comment, and only a
   card he would actually trade asks for an entry and a stop. */
.card[data-g=""] .q[data-q="setup"],
.card[data-g=""] .q[data-q="eblock"],
.card[data-g=""] .q[data-q="emin"],
.card[data-g=""] .q[data-q="stop"],
.card[data-g=""] .readout,
.card[data-g="X"] .q[data-q="setup"],
.card[data-g="X"] .q[data-q="eblock"],
.card[data-g="X"] .q[data-q="emin"],
.card[data-g="X"] .q[data-q="stop"],
.card[data-g="X"] .readout,
.card[data-g="C"] .q[data-q="eblock"],
.card[data-g="C"] .q[data-q="emin"],
.card[data-g="C"] .q[data-q="stop"],
.card[data-g="C"] .readout{display:none}
/* "why not" is a question about a refusal, so it exists only on a refusal */
.card:not([data-g="X"]) .q[data-q="why"]{display:none}

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

/* THE PRIMARY FIELD, and it sits directly under the grade because that is the
   order he answers in. Austin: "its about the comments." */
.q[data-q="comment"]{background:var(--accent-soft);border-top:1px solid var(--accent)}
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

# Deck kind 3 names six: BR / OCR / BR+OCR / 84 / OB / other. `build_omen_test1`
# has five -- it predates the order block being asked about on its own -- so the
# list lives here rather than being imported, and OB is the one addition.
SBLIND_SETUP_OPTS = [
    ("BR", "BR &mdash; break &amp; retest"),
    ("OCR", "OCR &mdash; one candle rule"),
    ("BR+OCR", "BR + OCR"),
    ("84", "84% re-entry"),
    ("OB", "OB &mdash; order block"),
    ("other", "Something else"),
]

# No engine entry/stop/target keys: the call is held out on kind 3, so the only
# entry and stop this chart will ever carry are his own.
SBLIND_LEGEND = ('<div class="legend">'
                 '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
                 '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> premarket</span>'
                 '<span><b style="color:var(--lvl-or)">- - ORH/ORL</b> first 5 min</span>'
                 '<span><b style="color:var(--entry)">&#9650; your entry</b></span>'
                 '<span><b style="color:var(--stop)">your stop</b></span></div>')


def sblind_questions(card) -> str:
    """**THE ONE SWAPPABLE PIECE.** Every question on a blind card, in order.

    Deck kind 3's mark set, which is Test 2's ("anything that is a continuation
    of previous cards stuff I liked"): grade, then the COMMENT, then why-not on a
    refusal, then setup, then the entry capture and the stop rail on a card he
    would actually trade. The comment sits directly under the grade because that
    is the order he answers in, and because it is the field this whole instrument
    exists to collect.

    Two contracts it must keep, because the rest of the machinery reads them:

    * **Exactly one question carries `required=1`.** `probe_page.js::answered()`
      returns False when a card has no required question at all, so a card with
      none can never read as done and the progress bar sits at zero forever.
    * **The keys are the export schema.** `grade` / `eblock` / `emin` / `stop` /
      `setup` are read by `build_omen_test1.EXTRA_JS`, which promotes them to
      top-level `entry_i` / `entry_t` / `entry_p` / `entered_before_close` /
      `stop_p` / `stop_src` / `side` / `setup` on every exported row. Rename one
      here and the returned marks lose that field silently.
    """
    stop_chips = "".join(
        '<button class="chip stopchip" type="button" data-v="%.2f" data-src="%s" '
        'aria-pressed="false">%.2f<small>%s</small><span class="risk"></span></button>'
        % (p, lab, p, lab) for p, lab in t1.stop_candidates(card["bars"],
                                                            card["levels"]))
    n_blocks = -(-len(card["bars"]) // 15)          # ceil; the JS hides the rest
    return "".join([
        pp.question(
            "grade", "Your grade.",
            "S clean &middot; A one downgrade &middot; C two &middot; "
            "<b>none = you would not take this</b>.",
            SBLIND_GRADE_OPTS),
        pp.question(
            "comment", "What did you see?",
            "This is the part that becomes a rule &mdash; write something on "
            "every card, including the ones you would not touch.",
            [], required=False,
            note_placeholder="What you saw. Where you would enter and stop. "
                             "What the engine missed."),
        pp.question(
            "why", "Why not?", "One tap. Optional.", t1.WHY_OPTS,
            required=False, tone="veto"),
        pp.question(
            "setup", "What kind of trade is it?",
            "If it is none of these, say <b>Something else</b> and one line "
            "about what it is.", SBLIND_SETUP_OPTS, required=False,
            note_placeholder="(optional) what the setup actually was"),
        pp.question(
            "eblock", "Entry &mdash; which quarter hour?",
            "Tap the block, then the minute inside it. The chart shades the "
            "block and drops your line on the bar.",
            t1.block_opts()[:n_blocks], required=False),
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
    ])


def sblind_card_html(card, n, total) -> str:
    """One card. THE ENGINE IS NOT ON IT.

    No grade, no direction, no entry, no stop, no target, no reasons, and
    nothing that says whether this is a day the engine fired on. The chart is
    candles from 09:30 to the cut, six level lines with their prices, and the
    placeholders his own taps move. `data-export` carries the symbol, the date
    and the length of the tape; everything else the returned row needs is joined
    back from the sidecar, which he never sees.
    """
    sym, day = card["symbol"], card["day"]
    chart = pc.render(card["bars"], card["levels"], interactive=True,
                      label="%s %s" % (sym, day))
    closes = json.dumps([round(b["c"], 2) for b in card["bars"]],
                        separators=(",", ":"))
    export = json.dumps({"symbol": sym, "date": day, "mode": "s-blind",
                         "n_bars": len(card["bars"])},
                        separators=(",", ":"), sort_keys=True)
    head = ('<header><span class="idx">%03d/%03d</span>'
            '<span class="tick">%s</span><span class="when">%s</span>'
            '<span class="tags"><span class="tag">from 09:30</span>'
            '<span class="done-dot"></span></span></header>'
            % (n, total, sym, day))
    return "".join([
        '<article class="card" data-cid="%s" data-n="%d" data-grade="" '
        'data-done="0" data-g="" data-nbars="%d" data-closes=\'%s\' '
        'data-export=\'%s\'>' % (card.get("cid") or "%s_%s" % (sym, day), n,
                                 len(card["bars"]), closes, export),
        head,
        '<div class="chartwrap">%s</div>' % chart, SBLIND_LEGEND,
        sblind_questions(card),
        "</article>",
    ])


# `build_omen_test1.EXTRA_JS` bounds the entry index with a MODULE-WIDE `BARS`,
# because Test 1's hundred charts are all exactly 90 bars. Kind 3's are not --
# every card is cut at its own bar -- so the bound is rewritten, once, to read
# the card's own `data-nbars`. The assertion in `sblind_build` fails the build if
# that line ever moves: without it he could tap a minute that is not on his chart
# and the export would carry an entry the tape never had.
_BARS_SRC = "if (i >= 0 && i < BARS){"
_BARS_DST = "if (i >= 0 && i < (+card.getAttribute('data-nbars') || BARS)){"

# The minute chips for bars that are not on THIS card. The block list is already
# trimmed at build time; the minute chips cannot be, because they are shared
# `+0..+14` offsets that only mean a clock once a block has been picked.
SBLIND_JS = r"""
<script>
(function(){
  function each(l, f){ Array.prototype.forEach.call(l, f); }
  function clamp(card){
    var n = +card.getAttribute('data-nbars') || 0;
    if (!n) return;
    var b = card.querySelector('.q[data-q="eblock"] .chip[aria-pressed="true"]');
    var base = b ? parseInt(b.getAttribute('data-v'), 10) * 15 : null;
    each(card.querySelectorAll('.q[data-q="emin"] .chip'), function(c){
      var off = parseInt(c.getAttribute('data-v'), 10);
      c.hidden = (base !== null) && (base + off >= n);
    });
  }
  document.addEventListener('click', function(e){
    var card = e.target.closest && e.target.closest('.card');
    if (card) clamp(card);
  });
  each(document.querySelectorAll('.card'), clamp);
})();
</script>
"""


def sblind_build(day: str, symbols, per_signal: bool = False) -> tuple:
    cards, stats = sblind_collect(day, symbols, per_signal)
    if not cards:
        raise SystemExit("no cards for %s -- nothing to send" % day)
    total = len(cards)
    js = t1.EXTRA_JS.replace("__BARS__", str(BLIND_BARS))
    assert _BARS_SRC in js, (
        "build_omen_test1.EXTRA_JS no longer bounds the entry index with %r -- "
        "kind 3 cards are cut at different bars and MUST clamp per card"
        % _BARS_SRC)
    js = js.replace(_BARS_SRC, _BARS_DST)

    html = pp.shell(
        title="OMEN blind - %s" % day,
        eyebrow="blind homework - %s" % day,
        h1="What was on the tape this morning",
        lede="%d charts from this session. Each one stops where it stops and "
             "you are told nothing else &mdash; not what the engine thought, "
             "not whether it thought anything at all. Grade it, say what kind "
             "of trade it is, mark your entry and stop if you would take it, "
             "and <b>write a comment on every card</b>. Everything saves as you "
             "go; Export when you are done." % total,
        cards_html=(SBLIND_CSS
                    + "".join(sblind_card_html(c, i, total)
                              for i, c in enumerate(cards, 1))),
        footer_html="1-minute candles from 09:30, cut where they are cut. "
                    "Levels: prior day high/low, premarket high/low, and the "
                    "opening range. Nothing after the last candle is on this "
                    "page, and neither is anything the engine did.",
        deck_id="daily-%s" % day,
    ) + js + SBLIND_JS
    stats["total"] = total
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


# Prices the card legitimately shows: every bar close (`data-closes`, which the
# mid-candle fill capture needs), every structural stop-rail chip, and the six
# level labels inside the chart. An engine entry is a candle close BY
# CONSTRUCTION and an engine stop is usually one of those very levels -- on QQQ
# 2026-09-03 the stop IS the premarket high the card is required to draw -- so a
# naive "is this number in the HTML" test fires on every card and proves nothing.
# The leak test therefore strips all three, and separately asserts that none of
# the SVG classes that
# DRAW a call -- entry rail, stop rail, target rail, arrow, candidate dot -- is
# in the markup at all. Those exist only when `marks`/`hlines`/`dots` are passed
# to probe_chart.render, and kind 3 passes none.
_CHART_PRICE_BLOCKS = (re.compile(r"data-closes='[^']*'"),
                       re.compile(r'<div class="chips stoprail">.*?</div>', re.S),
                       re.compile(r'<svg class="chart".*?</svg>', re.S))
_ENGINE_SVG = ('class="entry"', 'class="stopl"', 'class="arrow"',
               'class="dot ', 'class="hrail ', 'class="entry-t"',
               'class="stop-t"', 'class="dot-t')
# Checked against the card's HEAD ONLY -- header, chart, legend -- because that
# is the whole of the card built from engine data. The question copy below it is
# fixed prose reviewed here, and it legitimately says "engine" ("What the engine
# missed"), which is a prompt, not a leak.
_ENGINE_WORDS = ("fired", "gated", "silent", "candidate", "austin_tier",
                 "verdict", "tier", "engine")


def leak_check(card, html: str) -> None:
    """Fail if anything the card is supposed to hold back reached the markup.

    Deck kind 3 holds out the engine's grade, direction, entry, stop, target,
    reasons AND whether the day was a fire or a silent one. A leak here breaks
    nothing visibly; it quietly turns a blind test into a leading question, and
    the marks it produces cannot be told apart from honest ones afterwards.
    """
    sym = card["symbol"]
    for cls in _ENGINE_SVG:
        assert cls not in html, "%s: the chart draws the engine (%s)" % (sym, cls)
    head = html[:html.index('<section class="q"')]
    for w in _ENGINE_WORDS:
        assert w not in head, "%s: the word %r is on the card" % (sym, w)
    export = json.loads(re.search(r"data-export='([^']*)'", html).group(1))
    assert set(export) == {"symbol", "date", "mode", "n_bars"},         "%s: data-export carries %r" % (sym, sorted(export))
    prose = html
    for rx in _CHART_PRICE_BLOCKS:
        prose = rx.sub("", prose)
    for sig in card["signals"]:
        for field in ("entry", "stop", "target"):
            assert ("%.2f" % sig[field]) not in prose, (
                "%s: engine %s %.2f is on the card outside the chart's own data"
                % (sym, field, sig[field]))
        assert sig["verdict"] not in prose, "%s: a gate verdict is on the card" % sym
        if sig["reason"]:
            assert sig["reason"] not in prose, "%s: an engine reason is on the card" % sym
        if sig["tier"]:
            assert ">%s<" % sig["tier"] not in prose,                 "%s: an engine tier is on the card" % sym


def demo_sblind(day: str | None = None):
    """Self-check for --mode s-blind. Three things silently ruin a kind 3 deck.

    **The blindness.** A card carrying one bar past 11:00 is not blind, and
    nothing on the page would say so -- he would be marking a chart that already
    told him the answer, and the mark would be worthless without anyone knowing.
    Asserted on the bars themselves, never on the flag that produced them.

    **The leak.** Kind 3 holds the engine's whole call back. A grade, an entry
    price or a fire/silent marker reaching the markup does not break anything
    visibly; it just quietly turns a blind test into a leading question. So the
    built HTML is searched for the sidecar's own numbers.

    **The unreachable minute.** Every card is cut at its own bar, so the entry
    grid has to be clamped per card. A chip he can tap that names a minute not on
    his chart writes an entry the tape never had -- the same bug class as a rule
    that becomes a branch which can never be true.
    """
    day = day or latest_archived_day()
    assert BLIND_BARS == len(t1.BLOCKS) * 15, (
        "the entry grid covers %d bars but the window is %d"
        % (len(t1.BLOCKS) * 15, BLIND_BARS))
    bars, levels, trades = day_signals("TSLA", day, cut=BLIND_END)
    assert bars, "TSLA %s produced no blind bars" % day
    assert bars[0].timestamp.startswith("09:30"), bars[0].timestamp
    assert bars[-1].timestamp <= BLIND_END, (
        "blind tape reaches %s -- the deck is not blind" % bars[-1].timestamp)
    assert len(bars) == BLIND_BARS, "%d bars, expected %d" % (len(bars), BLIND_BARS)
    for t in trades:
        assert t.entry_time <= BLIND_END, (
            "candidate at %s is past the blind cut" % t.entry_time)

    cards, st = sblind_collect(day, ["TSLA", "AMZN", "QQQ", "SPY", "NVDA", "MU"])
    assert cards, "no cards from the six-symbol sample"
    for c in cards:
        n = len(c["bars"])
        assert n == c["cut_i"] + 1, "card %s: %d bars but cut_i %d" % (
            c["symbol"], n, c["cut_i"])
        assert n >= SBLIND_MIN_BARS, "card %s cut at %d bars" % (c["symbol"], n)
        assert c["bars"][0]["t"].startswith("09:30"), c["bars"][0]["t"]
        assert c["bars"][-1]["t"] <= BLIND_END, c["bars"][-1]["t"]
        if c["silent"]:
            # A silent card must be silent on the tape SHOWN, not merely
            # unremarkable somewhere later in the morning.
            early = [s for s in c["signals"]
                     if s["i"] is not None and s["i"] <= c["cut_i"]]
            assert not early, "silent card %s has %d candidates on screen" % (
                c["symbol"], len(early))
        html = sblind_card_html(c, 1, 1)
        leak_check(c, html)

    # Per-signal: one card per S bar, ids unique, short tape before long.
    ps, _ = sblind_collect(day, universe.CORE_SYMBOLS, per_signal=True)
    cids = [c["cid"] for c in ps]
    assert len(cids) == len(set(cids)), "per-signal deck repeats a card id"
    by_sym = collections.defaultdict(list)
    for c in ps:
        by_sym[c["symbol"]].append(c["cut_i"])
    for sym, cuts in by_sym.items():
        assert cuts == sorted(cuts), "%s: longer tape before shorter" % sym
    for c in ps:
        assert any(s["tier"] == "S" and s["i"] == c["cut_i"] for s in c["signals"]) \
            or c["silent"] or c["kind"] == "OCR / 84%", \
            "%s cut at %d is not an S bar" % (c["cid"], c["cut_i"])
        assert "_b%d" % c["cut_i"] in sblind_card_html(c, 1, 1), c["cid"]
    print("demo OK -- s-blind %s: %d cards, %d silent, every card cut at its own "
          "bar, no engine field on any card; per-signal core deck %d cards"
          % (day, len(cards), sum(1 for c in cards if c["silent"]), len(ps)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", help="session to build (default: latest archived)")
    ap.add_argument("--sym", help="one symbol only")
    ap.add_argument("--mode", choices=("full", "s-blind"), default="full",
                    help="full (default, the 16:15 reveal, one card per symbol) "
                         "or s-blind (AUGUR's 11:05 deck)")
    ap.add_argument("--pool", choices=("all", "core"), default="all",
                    help="all = the 29-symbol universe; core = the main 10 "
                         "plus SPY (universe.CORE_SYMBOLS)")
    ap.add_argument("--per-signal", action="store_true",
                    help="s-blind only: one card per S bar, not one per symbol "
                         "(Projects/AUGUR.md: 'every S signal from the top-10')")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.demo:
        demo()
        return

    day = a.day or latest_archived_day()
    syms = ([a.sym] if a.sym
            else universe.CORE_SYMBOLS if a.pool == "core"
            else universe.ALL_SYMS)

    if a.mode == "s-blind":
        print("building the 11:05 blind deck for %s over %d symbols%s"
              % (day, len(syms), ", one card per S signal" if a.per_signal else ""))
        cards, html, st = sblind_build(day, syms, a.per_signal)
        DECKS.mkdir(parents=True, exist_ok=True)
        tag = "-s10" if (a.pool == "core" and a.per_signal) else "-s"
        out = DECKS / ("omen-daily-%s%s.html" % (day, tag))
        out.write_text(html, encoding="utf-8")
        # THE SIDECAR IS THE ANSWER KEY. It carries everything the card holds
        # back -- kind, cut bar, and every candidate with its tier, gate verdict,
        # entry, stop, target and reason -- for the evening reveal and for
        # scoring his marks. It is never served to him.
        js = ROOT / "research" / ("daily_%s%s.json" % (day, tag.replace("-", "_")))
        js.write_text(json.dumps({"day": day, "mode": "s-blind",
                                  "cards": cards}, indent=1), encoding="utf-8")
        print()
        print("%s blind deck: %d cards" % (day, st["total"]))
        for k in ("S fired", "S gated", "OCR / 84%", "silent"):
            if st["by_kind"].get(k):
                print("  %-11s %d" % (k, st["by_kind"][k]))
        print("  %d fire cards, %d matched with a silent day; %d could not be "
              "matched (only %d symbol-days were silent at all)"
              % (st["fires"], st["silent"], st["unmatched"], st["pool"]))
        print("  no-repeat guard held back %d symbol-days; %d symbols had too "
              "few bars" % (len(st["repeats"]), len(st["nobars"])))
        print("  deck -> %s" % out)
        print("  key  -> %s" % js)
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
