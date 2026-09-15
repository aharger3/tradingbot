"""sm_deck.py -- phone-gradeable S decks for the 8pm stage-manager call.

Austin, 2026-09-14: "there has to be an easier way to do something on mobile
and get it back to you ... give you a card, grade it and get it back." The
call posts these PNGs into its own thread (SendUserFile renders them inline)
and deals up to two multiSelect cards, 4 charts each, "tap every chart that
is an S"; his taps come back through ``--mark``.

    python research/sm_deck.py --build --n 8 [--date YYYY-MM-DD]
    python research/sm_deck.py --mark <deck_date> --s "<comma ids>" [--a "<ids>"] [--c "<ids>"]
    python research/sm_deck.py --report

WHERE THE CANDIDATES COME FROM. Never a backtest run here -- ``--build`` only
reads the honest baseline book (``research/tape/loop.json``'s active
``baseline_book``, i.e. ``research/tape/baseline_2026-09-13.json.gz``) and the
archive's own bars (``g80_ordertype_grid.day_pack``, "data preparation only;
no fill and no grade is computed here"). The pool is every row the baseline
already scored with Austin's classifier grade (``sgrade``, ``research/downgrade.py``'s
S/A/C ladder -- NOT the engine's legacy A+/A/B/C/X ``grade`` field, CLAUDE.md
"Two grade ladders exist and must never be mixed") at S or A, fired or gated --
a day the legacy engine skipped as do-not-trade is still a candidate Austin's
own marks say the engine under-fires (THE LANE). One entry/stop/target triple
is already sitting on every row; nothing is re-simulated.

ONE CHART PER SYMBOL-DAY, EVERY S BAR ON IT. Same fix as the H1 referee
(OMEN 10.0, ``daily_homework.py:991`` ``per_signal=False``): a card is the
symbol-day, not the signal, so every S bar that landed on that tape draws its
own entry/stop/PT1 rail on the one chart. A day with no S candidate (only A)
falls back to drawing its A rows so the card is never blank. No grade letter
is ever drawn -- levels only, same "held back" discipline as the s-blind deck,
just aimed at showing the call instead of hiding it.

THE NO-REPEAT CHECK. ``deck.marked_card_ids() | deck.served_card_ids()`` --
every symbol-day Austin has ever graded, in ANY corpus, OR that was ever put
in front of him on ANY deck, including this one's own past builds. A build
writes two manifests beside its PNGs: ``manifest.json`` (id/symbol/day/png/
engine_grade -- what the caller and ``--mark`` read) and a sidecar
``manifest.jsonl`` (card_id/symbol/date/deck) purely so
``build_deck.served_card_ids()`` -- which globs ``research/**/*manifest*.jsonl``
-- can see this deck's served cards too. Never touches an existing mark file;
``--mark`` only ever writes its own ``research/marks/sm_deck_<date>.jsonl``.
"""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from research import build_deck as deck                # noqa: E402
from research import g80_lookahead_refute as rf         # noqa: E402
from research import g80_ordertype_grid as G            # noqa: E402
from research import probe_chart as pc                  # noqa: E402
from research import probe_page as pp                   # noqa: E402

DECKS_DIR = os.path.join(HERE, "decks")
MARKS_DIR = os.path.join(HERE, "marks")

WIN_START, WIN_END = "09:30:00", "11:00:00"

DEFAULT_BASELINE = os.path.join(HERE, "tape", "baseline_2026-09-13.json.gz")
LOOP_CONFIG = os.path.join(HERE, "tape", "loop.json")

PNG_W, PNG_H = 1200, 800


def _active_baseline_path() -> str:
    """``loop.json``'s active ``baseline_book``, else the pinned default."""
    if os.path.exists(LOOP_CONFIG):
        try:
            cfg = json.load(open(LOOP_CONFIG, encoding="utf-8"))
        except ValueError:
            cfg = {}
        book = cfg.get("baseline_book")
        if book:
            p = book if os.path.isabs(book) else os.path.join(ROOT, book)
            if os.path.exists(p):
                return p
    return DEFAULT_BASELINE


def _load_trades(path: str) -> list:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    return data["trades"] if isinstance(data, dict) else data


def _card_id(sym: str, day: str) -> str:
    return "%s_%s" % (sym, day)


def _candidate_pool(trades: list) -> dict:
    """{(sym, day): [signal, ...]} for every fired-or-gated S/A signal.

    Union, not intersection: one S or A row on a symbol-day is enough to put
    that day in the pool, whichever legacy engine status it carries.
    """
    pool = collections.defaultdict(list)
    for t in trades:
        if t.get("sgrade") in ("S", "A"):
            pool[(t.get("sym"), t.get("day"))].append(t)
    return pool


def _orh_orl(bars):
    orb = [c for c in bars if c.timestamp < "09:35:00"]
    if not orb:
        return None, None
    return max(c.high for c in orb), min(c.low for c in orb)


def _primary_signal(signals: list) -> dict:
    """The signal whose level/direction anchors the day's A/B/C candidate bars
    -- earliest fired signal, else earliest signal overall (a gated-only day
    has nothing that 'fired' but still has a level worth tracing).
    """
    fired = [t for t in signals if t.get("traded")]
    pool = fired or signals
    return min(pool, key=lambda t: t.get("et") or "99:99")


def _candidate_bars(bars_full: list, signal: dict) -> dict:
    """{"A": idx, "B": idx, "C": idx} -- up to three candidate bars, indices
    into ``bars_full``, for one signal's level/direction.

    C is the signal's own ``entry_i``, the bar the engine actually fired on.
    A and B come from g80_lookahead_refute.br_trace's read-only replay of the
    shipped break-and-retest state machine: A = break_i, the first 1-minute
    close through the level; B = retest_i, the first retest. Austin's first
    three sm_deck marks (research/marks/sm_deck_2026-09-14_comments.jsonl) all
    say the engine's C bar is late and his real entry was earlier -- A or B is
    meant to be that earlier bar. Any candidate the replay can't find (setup
    isn't break-and-retest, or the state machine never arms) is simply
    omitted -- up to three, not always three.
    """
    out = {}
    entry_i = signal.get("entry_i")
    if entry_i is None or not (0 <= entry_i < len(bars_full)):
        return out
    out["C"] = entry_i
    level, is_long = signal.get("level_px"), signal.get("dir") == "call"
    if level is None:
        return out
    tr = rf.br_trace(bars_full[:entry_i + 1], level, is_long)
    if tr:
        if tr.get("break_i") is not None:
            out["A"] = tr["break_i"]
        if tr.get("retest_i") is not None:
            out["B"] = tr["retest_i"]
    return out


def _fire_lag(sym: str, day: str, signals: list):
    """Bars between the day's A candidate and the engine's own C fire for its
    primary signal, or None when either can't be found. Drives --build's
    queue order only -- every candidate still gets its own chart and its own
    bars found when it is picked, this just decides who goes first.
    """
    bars_full, *_ = G.day_pack(sym, day)
    if not bars_full:
        return None
    cand = _candidate_bars(bars_full, _primary_signal(signals))
    if "A" in cand and "C" in cand:
        return cand["C"] - cand["A"]
    return None


def _build_chart(sym: str, day: str, signals: list):
    """(svg, engine_grade, bars) for one symbol-day, or None if the archive has no bars.

    Reads archived bars and levels only (``G.day_pack`` -- "data preparation
    only", never a fill or a grade) and draws straight off the baseline's own
    entry/stop/target numbers. No simulation runs here.
    """
    bars_full, pdh, pdl, pmh, pml = G.day_pack(sym, day)
    if not bars_full:
        return None
    bars = [c for c in bars_full if WIN_START <= c.timestamp <= WIN_END]
    if not bars:
        return None
    orh, orl = _orh_orl(bars_full)
    candles = [{"t": c.timestamp, "o": c.open, "h": c.high, "l": c.low,
                "c": c.close} for c in bars]
    at = {c["t"][:5]: i for i, c in enumerate(candles)}
    levels = {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
              "orh": orh, "orl": orl}

    # HOD/LOD as of the setup (entry) bar -- causal, same "as of entry_i"
    # convention as p21_target_availability.levels_for_entry -- so a card never
    # shows a running high/low the bar it drew hadn't printed yet.
    cand = _candidate_bars(bars_full, _primary_signal(signals))
    setup_bi = cand.get("C")
    if setup_bi is not None:
        levels["hod"] = max(c.high for c in bars_full[:setup_bi + 1])
        levels["lod"] = min(c.low for c in bars_full[:setup_bi + 1])

    # All S bars of the day on the one chart (H1 referee fix, OMEN 10.0). A
    # day whose only candidate is A falls back to that so the card is never
    # blank.
    s_sigs = [t for t in signals if t.get("sgrade") == "S"] or signals
    marks, hlines, engine_grade = [], [], "A"
    for t in s_sigs:
        i = at.get(t.get("et"))
        if i is None:
            continue
        marks.append({"i": i, "price": t.get("entry"), "stop": t.get("stop"),
                      "side": t.get("side", "L"), "tag": "ENTRY"})
        if t.get("target") is not None:
            hlines.append({"price": t["target"], "label": "PT1",
                           "cls": "tgt", "at": i})
        if t.get("sgrade") == "S":
            engine_grade = "S"

    # up to three candidate entry bars, letter-marked (A/B/C) so a graded card
    # can name which one Austin would actually have taken -- see
    # _candidate_bars.
    dots, bars_out, letter_ci = [], {}, {}
    for letter, bi in cand.items():
        ts = bars_full[bi].timestamp[:5]
        bars_out[letter] = ts
        ci = at.get(ts)
        letter_ci[letter] = ci
        if ci is not None:
            dots.append({"i": ci, "price": bars_full[bi].close, "label": letter})

    # G7.3 (2026-09-15), Austin on NVDA: "wick, not strong PA" -- shade the
    # break bar (A) so its body-vs-wick split is legible, and note the entry
    # bar's (C) body size against the pre-entry average so a wick posing as a
    # strong break stands out instead of reading like any other green candle.
    shade_i = letter_ci.get("A")
    notes = []
    entry_ci = letter_ci.get("C")
    if entry_ci is not None and entry_ci > 0:
        prior = candles[:entry_ci]
        avg_body = sum(abs(c["c"] - c["o"]) for c in prior) / len(prior)
        if avg_body > 0:
            entry_body = abs(candles[entry_ci]["c"] - candles[entry_ci]["o"])
            notes.append({"i": entry_ci,
                          "text": "body %.1fx avg" % (entry_body / avg_body)})

    svg = pc.render(candles, levels, marks=marks, hlines=hlines, dots=dots,
                    shade_i=shade_i, notes=notes,
                    label="%s %s  09:30-11:00" % (sym, day))
    return svg, engine_grade, bars_out


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


# .chart .hrail / .hrail-t is build_h2_deck.py's PT1-rail convention -- pc.render
# emits those classes for every hline but neither probe_page.CSS nor probe_chart
# itself styles them, so it must be added here. Font sizes are left at
# probe_page.CSS's native viewBox-unit values on purpose (g84_one_page.py's own
# note: "font sizes here are viewBox units" -- a 720-unit chart already lands
# noticeably bigger once stretched across a 1200-wide page than it does at the
# existing decks' native phone width, so a second CSS bump on top of that
# compounds through the viewBox transform and overflows the gutter). What DOES
# need help, same fix g84_one_page.py uses for its own crowded gutter: extra
# right padding plus `overflow:visible` so a level label that runs past
# probe_chart's PAD_R still renders instead of clipping.
_PNG_CSS = """
<style>
:root{--tgt:#0d6961;--brk:#a86a06}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--tgt:#54cfbe;--brk:#e0a340}}
:root[data-theme="dark"]{--tgt:#54cfbe;--brk:#e0a340}
html,body{margin:0}
.smpage{width:%dpx;height:%dpx;box-sizing:border-box;padding:22px 26px;
  background:var(--bg);display:flex;flex-direction:column}
.smhead{font-family:"IBM Plex Serif",Georgia,serif;font-weight:600;
  font-size:34px;color:var(--ink);margin:0 0 4px}
.smsub{font-family:"IBM Plex Mono",monospace;font-size:15px;color:var(--ink-2);
  margin:0 0 14px}
.smchart{background:var(--surface);border:1px solid var(--rule);
  border-radius:10px;padding:14px 64px 14px 14px}
.chart{overflow:visible}
.chart .hrail{stroke:var(--tgt);stroke-width:1.1;stroke-dasharray:7 4}
.chart .hrail-t{font-family:"IBM Plex Mono",monospace;font-size:9px;
  font-weight:600;fill:var(--tgt)}
.chart .bd.shade-bd{stroke:var(--brk);stroke-width:2}
.chart .wk.shade-wk{opacity:.35}
.chart .note{font-family:"IBM Plex Mono",monospace;font-size:9px;
  font-weight:600;fill:var(--ink-3)}
.smlegend{font-family:"IBM Plex Mono",monospace;font-size:14px;color:var(--ink-3);
  margin-top:14px;display:flex;gap:20px;flex-wrap:wrap}
</style>
""" % (PNG_W, PNG_H)

_SMLEGEND = (
    '<div class="smlegend"><span>PDH/PDL prior day</span>'
    '<span>PMH/PML premarket</span><span>ORH/ORL first 5 min</span>'
    '<span>HOD/LOD as of setup bar</span>'
    '<span>amber = entry &middot; red = stop</span>'
    '<span>teal dashed = PT1</span>'
    '<span>amber outline = break bar body vs dimmed wick</span>'
    '<span>body Nx avg = entry body vs pre-entry average</span></div>')


def _page_html(sym: str, day: str, svg: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>" + pp.FONTS
        + pp.CSS + _PNG_CSS + "</head><body><div class='smpage'>"
        + "<h1 class='smhead'>%s</h1>" % _esc(sym)
        + "<p class='smsub'>%s &middot; 09:30-11:00 ET</p>" % _esc(day)
        + "<div class='smchart'>%s</div>" % svg
        + _SMLEGEND + "</div></body></html>")


def _render_pngs(cards):
    """cards: [(sym, day, svg, out_path)]. One browser, one page, N screenshots."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": PNG_W, "height": PNG_H})
        try:
            for sym, day, svg, out_path in cards:
                page.set_content(_page_html(sym, day, svg), wait_until="load")
                page.screenshot(path=out_path)
        finally:
            browser.close()


# --------------------------------------------------------------------------- build

def cmd_build(args) -> int:
    n = args.n or 8
    deck_date = args.date or date.today().isoformat()
    out_dir = os.path.join(DECKS_DIR, "sm_%s" % deck_date)
    os.makedirs(out_dir, exist_ok=True)
    man_jsonl = os.path.join(out_dir, "manifest.jsonl")
    man_json = os.path.join(out_dir, "manifest.json")

    book_path = _active_baseline_path()
    trades = _load_trades(book_path)
    pool = _candidate_pool(trades)

    already = deck.marked_card_ids() | deck.served_card_ids(exclude=man_jsonl)
    # newest day first; symbol ascending within a day (stable sort, two passes)
    candidates = sorted(pool.keys(), key=lambda k: k[0])
    candidates.sort(key=lambda k: k[1], reverse=True)
    candidates = [k for k in candidates if _card_id(*k) not in already]
    # THE LANE: Austin's first three sm_deck marks all say the engine's fire
    # is late. Push days where it fired >=3 bars after the first close through
    # the level to the front of the queue (stable -- ties keep the order
    # above); a day with no A/C candidate at all just sorts as if lag were 0.
    candidates.sort(key=lambda k: (_fire_lag(*k, pool[k]) or 0) < 3)

    entries, jsonl_rows, to_render = [], [], []
    for sym, day in candidates:
        if len(entries) >= n:
            break
        built = _build_chart(sym, day, pool[(sym, day)])
        if built is None:
            continue
        svg, engine_grade, bars_out = built
        idx = len(entries) + 1
        png_name = "%d_%s_%s.png" % (idx, sym, day)
        png_path = os.path.join(out_dir, png_name)
        to_render.append((sym, day, svg, png_path))
        cid = _card_id(sym, day)
        entries.append({"id": cid, "symbol": sym, "day": day,
                        "png": os.path.relpath(png_path, ROOT).replace("\\", "/"),
                        "engine_grade": engine_grade, "bars": bars_out})
        jsonl_rows.append({"card_id": cid, "symbol": sym, "date": day,
                           "deck": "sm_%s" % deck_date})

    if to_render:
        _render_pngs(to_render)

    with open(man_json, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=1)
    with open(man_jsonl, "w", encoding="utf-8") as f:
        for row in jsonl_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    print("sm deck %s: %d cards, from %s" % (deck_date, len(entries), book_path))
    for e in entries:
        print("  %-18s  engine %s  %s" % (e["id"], e["engine_grade"], e["png"]))
    print("manifest -> %s" % man_json)
    return 0


# ---------------------------------------------------------------------------- mark

def cmd_mark(args) -> int:
    deck_date = args.mark
    out_dir = os.path.join(DECKS_DIR, "sm_%s" % deck_date)
    man_json = os.path.join(out_dir, "manifest.json")
    if not os.path.exists(man_json):
        print("no sm deck for %s -- build it first (%s)" % (deck_date, man_json))
        return 1
    with open(man_json, encoding="utf-8") as f:
        entries = json.load(f)

    def _ids(raw):
        return {x.strip() for x in (raw or "").split(",") if x.strip()}
    s_ids, a_ids, c_ids = _ids(args.s), _ids(args.a), _ids(args.c)

    os.makedirs(MARKS_DIR, exist_ok=True)
    out_path = os.path.join(MARKS_DIR, "sm_deck_%s.jsonl" % deck_date)
    rows = []
    for e in entries:
        cid = e["id"]
        if cid in s_ids:
            grade = "S"
        elif cid in a_ids:
            grade = "A"
        elif cid in c_ids:
            grade = "C"
        else:
            grade = "C" if args.default_c else "ungraded"
        rows.append({"type": "sm_deck", "card_id": cid, "symbol": e["symbol"],
                    "date": e["day"], "grade": grade,
                    "engine_grade": e["engine_grade"], "deck": "sm_%s" % deck_date})
    with open(out_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    his_s = sum(1 for r in rows if r["grade"] == "S")
    eng = collections.Counter(r["engine_grade"] for r in rows)
    print("sm mark %s: %d cards -> %s" % (deck_date, len(rows), out_path))
    print("agreement: his S=%d | engine on this deck -> S:%d A:%d C:%d"
         % (his_s, eng.get("S", 0), eng.get("A", 0), eng.get("C", 0)))
    return 0


# ------------------------------------------------------------------- mark-bar

def _minutes(ts: str) -> int:
    h, m = ts.split(":")[:2]
    return int(h) * 60 + int(m)


def cmd_mark_bar(args) -> int:
    """--picks 'id:A,id:B' -- his bar per card vs the engine's C, minutes early."""
    deck_date = args.mark_bar
    out_dir = os.path.join(DECKS_DIR, "sm_%s" % deck_date)
    man_json = os.path.join(out_dir, "manifest.json")
    if not os.path.exists(man_json):
        print("no sm deck for %s -- build it first (%s)" % (deck_date, man_json))
        return 1
    with open(man_json, encoding="utf-8") as f:
        entries = {e["id"]: e for e in json.load(f)}

    picks = {}
    for pair in (args.picks or "").split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        cid, letter = pair.split(":", 1)
        picks[cid.strip()] = letter.strip().upper()

    os.makedirs(MARKS_DIR, exist_ok=True)
    out_path = os.path.join(MARKS_DIR, "sm_deck_%s_bars.jsonl" % deck_date)
    rows = []
    for cid, letter in picks.items():
        e = entries.get(cid)
        if e is None:
            print("skip %s -- not on this deck" % cid)
            continue
        bars = e.get("bars") or {}
        his_bar, eng_bar = bars.get(letter), bars.get("C")
        if his_bar is None or eng_bar is None:
            print("skip %s -- letter %s or engine bar missing" % (cid, letter))
            continue
        rows.append({"type": "sm_deck_bars", "card_id": cid, "symbol": e["symbol"],
                    "date": e["day"], "deck": "sm_%s" % deck_date,
                    "his_letter": letter, "his_bar": his_bar, "engine_bar": eng_bar,
                    "minutes_early": _minutes(eng_bar) - _minutes(his_bar)})
    with open(out_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    print("sm mark-bar %s: %d picks -> %s" % (deck_date, len(rows), out_path))
    for r in rows:
        print("  %-18s  his %s (%s) vs engine %s  -> %d min early"
             % (r["card_id"], r["his_bar"], r["his_letter"], r["engine_bar"],
                r["minutes_early"]))
    return 0


# -------------------------------------------------------------------------- report

def cmd_report(_args) -> int:
    paths = sorted(glob.glob(os.path.join(MARKS_DIR, "sm_deck_*.jsonl")))
    rows = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    if not rows:
        print("no sm_deck marks yet (research/marks/sm_deck_*.jsonl)")
        return 0

    graded = [r for r in rows if r.get("grade") not in (None, "ungraded")]
    his_s = [r for r in graded if r["grade"] == "S"]
    agree = sum(1 for r in his_s if r.get("engine_grade") == "S")
    sym_s = collections.Counter(r["symbol"] for r in his_s)

    print("sm_deck report: %d cards served across %d sitting(s)"
         % (len(rows), len(paths)))
    print("his S: %d/%d graded (%.0f%%)"
         % (len(his_s), len(graded), 100.0 * len(his_s) / len(graded) if graded else 0))
    print("engine agreement on his S picks: %d/%d (%.0f%%)"
         % (agree, len(his_s), 100.0 * agree / len(his_s) if his_s else 0))
    top = sym_s.most_common(5)
    print("symbols he marks S most: %s"
         % (", ".join("%s (%d)" % (s, c) for s, c in top) if top else "none yet"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build", action="store_true", help="build a new S deck")
    ap.add_argument("--n", type=int, default=8, help="cards to build (default 8)")
    ap.add_argument("--date", help="deck identity date, default today (YYYY-MM-DD)")
    ap.add_argument("--mark", metavar="DECK_DATE", help="write his grades for that deck date")
    ap.add_argument("--s", default="", help="comma ids he tapped S")
    ap.add_argument("--a", default="", help="comma ids he tapped A")
    ap.add_argument("--c", default="", help="comma ids he tapped C")
    ap.add_argument("--default-c", action="store_true",
                    help="unlisted ids grade C instead of 'ungraded'")
    ap.add_argument("--mark-bar", metavar="DECK_DATE",
                    help="write his A/B/C bar pick per card for that deck date")
    ap.add_argument("--picks", default="", help="comma 'id:LETTER' pairs for --mark-bar")
    ap.add_argument("--report", action="store_true", help="running tally across all sm_deck marks")
    args = ap.parse_args()

    if args.build:
        return cmd_build(args)
    if args.mark:
        return cmd_mark(args)
    if args.mark_bar:
        return cmd_mark_bar(args)
    if args.report:
        return cmd_report(args)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
