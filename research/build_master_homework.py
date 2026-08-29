"""build_master_homework.py -- one page, five lanes, one link.

Austin, 2026-08-28, after two rounds of grilling and a lot of repeating himself:

  "This should be a decently sized deck that will unblock a lot so you can have a
   massive master spec night queue of tasks, I want to go though each codebases
   and approve or deny and add or subtract facts, have this in the artifact."

So the lanes are his complaints, in the order he raised them:

  1  FACTS      every constant and convention the engine runs on, plain English,
                keep / kill / change. No chart. This is the lane that unblocks
                the overnight queue -- `research/master_facts.py`.
  2  VETOES     40 setups the engine found and refused. Should it have fired?
  3  RARE       one-candle-rule and 84%-rule setups the engine killed. He says
                these should fire nearer the break-and-retest rate.
  4  INDEX      QQQ / SPY / IWM days. 18 of 1,017 trades are indices and he
                trades indices first with real money.
  5  RUNNER     trades that ran past 2R. Where does he get out? This is the
                mean-R question answered by his eye instead of by an exit sweep.

Every chart lane obeys the no-repeat guarantee against ONE shared exclusion set
built once at the top, so no two lanes can serve the same symbol-day and no lane
can serve a day he has already been shown -- except lane 2, which deliberately
re-serves the 40 cards published as `omen-x-vetoes` an hour earlier so that page
can be retired rather than leaving him two links.

    python research/build_master_homework.py
    python research/build_master_homework.py --selfcheck

Output: research/probes/<name>.html + <name>-manifest.jsonl (the answer key,
which stays OUT of the HTML).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import probe_chart
import probe_page
from build_deck import candle_dict, seen_card_ids, session_candles
from master_facts import FACTS
from research.t4_engine_recall import prior_day_levels, premarket_extremes

BOOK = os.path.join(HERE, "bt2y_trades.json")
PROBES_DIR = os.path.join(HERE, "probes")
XVETO_MANIFEST = os.path.join(PROBES_DIR, "omen-x-vetoes-manifest.jsonl")
LEVEL_KEYS = ("pdh", "pdl", "pmh", "pml", "orh", "orl")

LANE_CSS = """
<style>
.lane{margin:38px 0 14px;padding:16px 18px;border-radius:10px;
  background:var(--surface2,#f5f7fa);border:1px solid var(--line,#d5dae4)}
.lane .n{font-size:11px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted,#5a6377);margin:0 0 5px}
.lane h2{font-size:21px;margin:0 0 7px;line-height:1.25}
.lane p{margin:0;color:var(--muted,#5a6377);font-size:14px;line-height:1.55;max-width:62ch}
.fact .where{font-family:ui-monospace,monospace;font-size:11.5px;
  color:var(--faint,#8a93a6);margin:2px 0 0;word-break:break-word}
.fact .cost{font-size:12.5px;margin:8px 0 0;padding:8px 10px;border-radius:7px;
  background:var(--surface2,#f5f7fa);border-left:3px solid var(--accent,#1f5fd1)}
</style>
"""


def load_book() -> list[dict]:
    with open(BOOK, encoding="utf-8") as f:
        return json.load(f)["trades"]


def card_shell(cid: str, sym: str, ord_: str, inner: str, export: dict,
               cls: str = "") -> str:
    return ('<article class="card %s" data-cid="%s" data-grade="none" '
            "data-done=\"0\" data-export='%s'>"
            '<header class="card-h"><span class="sym">%s</span>'
            '<span class="ord">%s</span></header>%s</article>'
            % (cls, cid, json.dumps(export, sort_keys=True), sym, ord_, inner))


def lane(n: str, title: str, body: str) -> str:
    return ('<div class="lane"><p class="n">%s</p><h2>%s</h2><p>%s</p></div>'
            % (n, title, body))


# ---------------------------------------------------------------- lane 1
def fact_cards() -> tuple[str, list[dict]]:
    html, man = [], []
    for i, f in enumerate(FACTS, 1):
        qs = probe_page.question(
            "verdict", f["q"], f["b"], f["opts"], required=True)
        extra = ('<section class="q fact" data-q="_where" data-required="0">'
                 '<p class="where">%s</p><p class="cost">Costs today: %s</p>'
                 "</section>" % (f["w"], f["c"]))
        note = probe_page.question(
            "note", "Anything to add or subtract",
            "Optional. If a fact here is wrong, say so -- that is the point of "
            "the lane.", [], required=False, note_placeholder="optional")
        html.append(card_shell("fact_" + f["k"], "FACT", "%d/%d" % (i, len(FACTS)),
                               qs + extra + note,
                               {"lane": "facts", "fact": f["k"]}))
        man.append({"card_id": "fact_" + f["k"], "lane": "facts",
                    "fact": f["k"], "where": f["w"], "costs": f["c"]})
    return "".join(html), man


# ---------------------------------------------------------------- chart lanes
def chart_card(sig: dict, question_html: str, lane_name: str,
               marks: list | None = None, label: str | None = None) -> str | None:
    candles = session_candles(sig["sym"], sig["day"])
    if len(candles) < 60:
        return None
    pdh, pdl, _o, _c = prior_day_levels(sig["sym"], sig["day"])
    pmh, pml = premarket_extremes(sig["sym"], sig["day"])
    levels = {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
              "orh": max(c.high for c in candles[:5]),
              "orl": min(c.low for c in candles[:5])}
    levels = {k: (round(v, 2) if v is not None else None) for k, v in levels.items()}
    svg = probe_chart.render([candle_dict(x) for x in candles], levels,
                             marks=marks or [],
                             label=label or "%s %s 09:30-11:00"
                                             % (sig["sym"], sig["day"]))
    return card_shell("%s_%s" % (sig["sym"], sig["day"]), sig["sym"],
                      sig.get("et", "&nbsp;"), svg + question_html,
                      {"lane": lane_name, "symbol": sig["sym"],
                       "date": sig["day"], "et": sig.get("et", "")})


def entry_mark(r: dict) -> dict:
    return {"i": r["entry_i"], "price": r["entry"], "stop": r["stop"],
            "side": r["side"], "tag": r["et"]}


def veto_lane(book: list[dict]) -> tuple[str, list[dict]]:
    """Exactly the 40 cards already published as omen-x-vetoes, re-served here."""
    want = []
    with open(XVETO_MANIFEST, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                want.append(json.loads(line))
    index = {(r["sym"], r["day"], r["et"]): r for r in book}
    html, man = [], []
    for w in want:
        r = index.get((w["symbol"], w["date"], w["et"]))
        if r is None:
            continue
        setup = ("break and retest" if r["setup"] == "break_and_retest"
                 else "one candle rule")
        qs = probe_page.question(
            "grade", "Should this have fired?",
            "A %s off the %s. The entry and stop it wanted are drawn. One tap."
            % (setup, r["level"]),
            [("s", "S"), ("a", "A"), ("c", "C"), ("no", "No trade")],
            required=True)
        qs += probe_page.question(
            "why", "If No, what kills it", "Optional.", [], required=False,
            note_placeholder="optional")
        c = chart_card(r, qs, "vetoes", marks=[entry_mark(r)],
                       label="%s %s &middot; proposed entry %s"
                             % (r["sym"], r["day"], r["et"]))
        if c:
            html.append(c)
            man.append({"card_id": "%s_%s" % (r["sym"], r["day"]), "lane": "vetoes",
                        "symbol": r["sym"], "date": r["day"], "et": r["et"],
                        "setup": r["setup"], "level": r["level"],
                        "engine_grade": r["grade"], "engine_sgrade": r["sgrade"],
                        "hindsight_r": r["r"]})
    return "".join(html), man


def rare_lane(book, seen, n, rng) -> tuple[str, list[dict], set]:
    """OCR and 84%-rule setups the engine detected and then killed."""
    pool = [r for r in book
            if r["setup"] in ("one_candle_rule", "reentry_84_rule")
            and not r["traded"]
            and "%s_%s" % (r["sym"], r["day"]) not in seen]
    best = {}
    for r in pool:
        k = (r["sym"], r["day"])
        if k not in best or r["et"] < best[k]["et"]:
            best[k] = r
    picks = list(best.values())
    rng.shuffle(picks)
    html, man, used = [], [], set()
    for r in picks:
        if len(html) >= n:
            break
        cid = "%s_%s" % (r["sym"], r["day"])
        if cid in used:
            continue
        name = ("one candle rule" if r["setup"] == "one_candle_rule"
                else "84% re-entry")
        qs = probe_page.question(
            "real", "Is this a real %s?" % name,
            "The engine found it here and killed it. Entry and stop drawn. "
            "You said these should fire nearer the break-and-retest rate -- this "
            "lane finds out whether the setups are there and being thrown away, "
            "or simply are not there.",
            [("yes", "Yes -- should fire"), ("weak", "Real but not tradeable"),
             ("no", "Not this setup at all")], required=True)
        qs += probe_page.question(
            "why", "What makes it one, or not", "Optional.", [], required=False,
            note_placeholder="optional")
        c = chart_card(r, qs, "rare", marks=[entry_mark(r)],
                       label="%s %s &middot; %s at %s"
                             % (r["sym"], r["day"], name, r["et"]))
        if c:
            html.append(c)
            used.add(cid)
            man.append({"card_id": cid, "lane": "rare", "symbol": r["sym"],
                        "date": r["day"], "et": r["et"], "setup": r["setup"],
                        "level": r["level"], "engine_grade": r["grade"],
                        "engine_status": r["status"], "hindsight_r": r["r"]})
    return "".join(html), man, used


def index_lane(book, seen, n, rng) -> tuple[str, list[dict], set]:
    """Index days, entry UNMARKED -- the same question as the S sweep."""
    idx = {(r["sym"], r["day"]) for r in book if r["cls"] == "etf"}
    picks = [{"sym": s, "day": d} for s, d in sorted(idx)
             if "%s_%s" % (s, d) not in seen]
    rng.shuffle(picks)
    html, man, used = [], [], set()
    for p in picks:
        if len(html) >= n:
            break
        qs = probe_page.question(
            "s", "Is this an S day?",
            "Six levels, 09:30 to 11:00, nothing drawn. Indices are 18 of the "
            "book's 1,017 trades and they are what you said you will trade first "
            "with real money -- so the engine needs your read on them "
            "specifically.",
            [("s", "S day"), ("no", "Not S")], required=True)
        qs += probe_page.question(
            "min", "The minute of the S entry candle",
            "Only if you said S. HH:MM.", [], required=False,
            note_placeholder="09:47")
        c = chart_card(p, qs, "index")
        if c:
            html.append(c)
            cid = "%s_%s" % (p["sym"], p["day"])
            used.add(cid)
            man.append({"card_id": cid, "lane": "index", "symbol": p["sym"],
                        "date": p["day"]})
    return "".join(html), man, used


def runner_lane(book, seen, n, rng) -> tuple[str, list[dict], set]:
    """Trades that ran past 2R. Where does he actually get out?"""
    pool = [r for r in book if r["traded"] and r["r"] >= 2.0
            and "%s_%s" % (r["sym"], r["day"]) not in seen]
    rng.shuffle(pool)
    html, man, used = [], [], set()
    for r in pool:
        if len(html) >= n:
            break
        cid = "%s_%s" % (r["sym"], r["day"])
        if cid in used:
            continue
        qs = probe_page.question(
            "exit", "Where do you get out of this one?",
            "Entry and stop drawn, the whole 09:30-11:00 path visible. The engine "
            "takes exactly 2x risk on every trade, which is why its average is "
            "half your gate -- a flat 2R target can never average 2R. Tell it "
            "what you would actually have done here.",
            [("2r", "2R, done"), ("level", "Next level past 2R"),
             ("trail", "Trail it behind structure"), ("hold", "Hold to 11:00")],
            required=True)
        qs += probe_page.question(
            "px", "The price you would have exited at",
            "Optional but the most useful thing on this card.", [],
            required=False, note_placeholder="e.g. 214.80")
        c = chart_card(r, qs, "runner", marks=[entry_mark(r)],
                       label="%s %s &middot; entry %s, stop drawn"
                             % (r["sym"], r["day"], r["et"]))
        if c:
            html.append(c)
            used.add(cid)
            man.append({"card_id": cid, "lane": "runner", "symbol": r["sym"],
                        "date": r["day"], "et": r["et"],
                        "engine_r": r["r"], "engine_exit": r["exit"],
                        "engine_target": r["target"]})
    return "".join(html), man, used


# ---------------------------------------------------------------- build
def build(name: str, n_rare: int, n_index: int, n_runner: int, seed: int):
    os.makedirs(PROBES_DIR, exist_ok=True)
    book = load_book()
    own = os.path.join(PROBES_DIR, "%s-manifest.jsonl" % name)
    seen = seen_card_ids(own)
    # Lane 2 re-serves the x-veto forty on purpose, so they must not block
    # themselves out of this page.
    veto_html, veto_man = veto_lane(book)
    seen |= {m["card_id"] for m in veto_man}
    rng = random.Random(seed)

    rare_html, rare_man, used = rare_lane(book, seen, n_rare, rng)
    seen |= used
    index_html, index_man, used = index_lane(book, seen, n_index, rng)
    seen |= used
    runner_html, runner_man, _ = runner_lane(book, seen, n_runner, rng)

    fact_html, fact_man = fact_cards()
    body = "".join([
        lane("Lane 1 &middot; %d cards &middot; no charts" % len(FACTS),
             "The facts the engine runs on",
             "Every constant and convention that is live right now, in plain "
             "English, with what it costs. Keep it, kill it, or change it. "
             "<b>This is the lane that unblocks the overnight queue</b> -- every "
             "answer here becomes a task while you sleep."),
        fact_html,
        lane("Lane 2 &middot; %d cards" % len(veto_man),
             "Setups the engine found and refused",
             "On your 34 fresh S days the engine was never blind and its timing "
             "was exact -- it reached your setup and graded it a no-trade. These "
             "are that population. Tell it which refusals were wrong."),
        veto_html,
        lane("Lane 3 &middot; %d cards" % len(rare_man),
             "The one-candle rule and the 84% rule",
             "947 break-and-retests traded against 67 one-candle-rule and 3 "
             "eighty-four-percents. You said that should be closer to even. These "
             "are setups it detected and killed -- are they real?"),
        rare_html,
        lane("Lane 4 &middot; %d cards" % len(index_man),
             "QQQ, SPY and IWM",
             "18 index trades out of 1,017, against COIN's 104 on its own -- and "
             "indices are what you said you will trade first with real money. "
             "Nothing is drawn on these."),
        index_html,
        lane("Lane 5 &middot; %d cards" % len(runner_man),
             "Where do you get out?",
             "Every one of these ran past 2R and the engine took exactly 2R, "
             "because that is all it ever takes. A flat 2R target can never "
             "average 2R at any win rate. Your answers here are what replaces it."),
        runner_html,
    ])

    total = len(fact_man) + len(veto_man) + len(rare_man) + len(index_man) + len(runner_man)
    html = probe_page.shell(
        title="OMEN Master Homework",
        eyebrow="OMEN &middot; 2026-08-28",
        h1="Five lanes, one page",
        lede="Saves every tap to this device as you go &mdash; close it, lose "
             "signal, come back tomorrow, your answers are still here. "
             "When you are done hit <b>Export &rarr; Copy all</b> and paste it "
             "into the chat. Start with Lane 1; it needs no charts and it "
             "unblocks the most.",
        cards_html=body,
        footer_html="%d cards. No symbol-day appears twice, and none of them is "
                    "a day you have graded before &mdash; except Lane 2, which is "
                    "the same forty published earlier today so you only need this "
                    "one link." % total,
        deck_id=name)
    html = html.replace("</title>", "</title>" + LANE_CSS, 1)

    path = os.path.join(PROBES_DIR, name + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    man_rows = fact_man + veto_man + rare_man + index_man + runner_man
    with open(own, "w", encoding="utf-8") as f:
        for m in man_rows:
            f.write(json.dumps(m, sort_keys=True) + "\n")
    return path, own, man_rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="omen-master-2026-08-28")
    ap.add_argument("--rare", type=int, default=20)
    ap.add_argument("--index", type=int, default=15)
    ap.add_argument("--runner", type=int, default=15)
    ap.add_argument("--seed", type=int, default=23)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        from master_facts import selfcheck
        return selfcheck()

    path, man, rows = build(a.name, a.rare, a.index, a.runner, a.seed)

    ids = [r["card_id"] for r in rows]
    assert len(set(ids)) == len(ids), "a card_id appears twice on the page"
    chart_ids = {r["card_id"] for r in rows if r["lane"] != "facts"}
    veto_ids = {r["card_id"] for r in rows if r["lane"] == "vetoes"}
    stale = (chart_ids - veto_ids) & seen_card_ids(man)
    assert not stale, "page serves a day he has already seen: %s" % sorted(stale)
    blob = open(path, encoding="utf-8").read()
    for leak in ("engine_grade", "hindsight_r", "skipped_d", "engine_r"):
        assert leak not in blob, "answer key leaked into the HTML: %s" % leak
    assert "localStorage" in blob, "the page lost its own save"

    per = {}
    for r in rows:
        per[r["lane"]] = per.get(r["lane"], 0) + 1
    print("Wrote %s" % path)
    print("       %s  (answer key -- not served)" % man)
    print("  lanes: %s" % per)
    print("  total=%d  size=%.1f MB" % (len(rows), len(blob.encode("utf-8")) / 1e6))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
