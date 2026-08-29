"""build_x_veto_deck.py -- grade the vetoes, before we build the arm that lifts them.

T1 (`research/t1_entry_minute_autopsy.md`, 2026-08-28) found the engine is never
silent on Austin's S days -- 0 of 34 -- and that on the 15 days it reaches his
setup its timing is exact. What it does instead is *find the trade and grade it
`X`*. All nine DETECTED days were X. Zero of his 34 S days were graded S.

`X` means "the engine should not have fired at all". So the recall wound is a
pile of 42,937 vetoes, and P26 is the proposal to lift a targeted slice of them.
The trouble with lifting vetoes is that W1 already showed the indiscriminate
version (`on_all`) buys 6/15 held-out recall and pays with a 12.5x book. Nobody
knows which vetoes are wrong because nobody has asked the only person who can
say.

This deck asks him, on the exact population P26 would regrade:

    status == "skipped_d"           the engine vetoed it
    sgrade == "S"                   his own downgrade ladder says it is clean
    setup in (break_and_retest, one_candle_rule)

7,190 signals across 5,004 symbol-days qualify. That disagreement -- his ladder
says S, `_grade_pa` says X -- IS the recall gap, one row at a time.

The card draws the engine's proposed entry and stop, because the question is
about a specific proposed trade, not about the day. That is the opposite of
`build_s_cards.py`, deliberately: this measures whether the veto is wrong,
that one measures whether the day is an S day.

    python research/build_x_veto_deck.py                  # 40 cards
    python research/build_x_veto_deck.py --n 8 --seed 3   # a smoke run
    python research/build_x_veto_deck.py --selfcheck      # no build, just checks

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
from research.t4_engine_recall import prior_day_levels, premarket_extremes

BOOK = os.path.join(HERE, "bt2y_trades.json")
PROBES_DIR = os.path.join(HERE, "probes")
LEVEL_KEYS = ("pdh", "pdl", "pmh", "pml", "orh", "orl")
SETUPS = ("break_and_retest", "one_candle_rule")


def vetoed_s_signals(book_path: str = BOOK) -> list[dict]:
    """The P26 population: engine vetoed it, Austin's own ladder calls it clean.

    One row per symbol-day -- the *earliest* qualifying signal of that day.
    Arrival order is what actually selects the engine's book
    (`research/g4_dropped_s.md` s6), so the first veto of a day is the one whose
    lift would change what he sees, and serving two cards off one chart would
    be a repeat by his own rule.
    """
    with open(book_path, encoding="utf-8") as f:
        rows = json.load(f)["trades"]
    best: dict[tuple[str, str], dict] = {}
    for r in rows:
        if r.get("status") != "skipped_d":
            continue
        if r.get("sgrade") != "S" or r.get("setup") not in SETUPS:
            continue
        key = (r["sym"], r["day"])
        cur = best.get(key)
        if cur is None or r["et"] < cur["et"]:
            best[key] = r
    return [best[k] for k in sorted(best)]


def pick(n: int, seed: int, own_manifest: str | None = None):
    """Sample n vetoed-S signals off symbol-days he has never been shown."""
    pool = vetoed_s_signals()
    seen = seen_card_ids(own_manifest)
    fresh = [r for r in pool if "%s_%s" % (r["sym"], r["day"]) not in seen]
    print("no-repeat guard: %d vetoed-S symbol-days -> %d fresh (%d already "
          "judged or served)" % (len(pool), len(fresh), len(pool) - len(fresh)))
    rng = random.Random(seed)
    rng.shuffle(fresh)

    cards, skipped = [], 0
    for r in fresh:
        if len(cards) >= n:
            break
        candles = session_candles(r["sym"], r["day"])
        if len(candles) < 60 or not (0 <= r["entry_i"] < len(candles)):
            skipped += 1
            continue
        pdh, pdl, _o, _c = prior_day_levels(r["sym"], r["day"])
        pmh, pml = premarket_extremes(r["sym"], r["day"])
        cards.append({
            "sig": r, "candles": candles,
            "pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
            "orh": max(c.high for c in candles[:5]),
            "orl": min(c.low for c in candles[:5]),
        })
    print("  built %d cards, skipped %d for short/unmappable sessions"
          % (len(cards), skipped))
    return cards


def render_card(c: dict) -> str:
    r = c["sig"]
    cid = "%s_%s" % (r["sym"], r["day"])
    candles = [candle_dict(x) for x in c["candles"]]
    levels = {k: (round(c[k], 2) if c.get(k) is not None else None)
              for k in LEVEL_KEYS}
    # The entry and stop ARE the question here, so unlike the S sweep they are
    # drawn. What is never drawn or named is the engine's verdict on them.
    mark = {"i": r["entry_i"], "price": r["entry"], "stop": r["stop"],
            "side": r["side"], "tag": r["et"]}
    svg = probe_chart.render(candles, levels, marks=[mark],
                             label="%s %s &middot; proposed entry %s"
                                   % (r["sym"], r["day"], r["et"]))
    setup = "break and retest" if r["setup"] == "break_and_retest" else "one candle rule"
    qs = "".join([
        probe_page.question(
            "grade", "Should this have fired?",
            "A %s off the %s. The entry and stop are drawn. One tap."
            % (setup, r["level"]),
            [("s", "S"), ("a", "A"), ("c", "C"), ("no", "No trade")],
            required=True),
        probe_page.question(
            "why", "If No, what kills it",
            "Optional, and only worth typing when the reason is not on the chart.",
            [], required=False, note_placeholder="optional"),
    ])
    export = json.dumps({"symbol": r["sym"], "date": r["day"], "et": r["et"],
                         "setup": r["setup"], "level": r["level"]},
                        sort_keys=True)
    return ('<article class="card" data-cid="%s" data-grade="none" data-done="0" '
            "data-export='%s'>"
            '<header class="card-h"><span class="sym">%s</span>'
            '<span class="ord">%s</span></header>%s%s</article>'
            % (cid, export, r["sym"], r["et"], svg, qs))


def build(cards: list, name: str) -> tuple[str, str]:
    os.makedirs(PROBES_DIR, exist_ok=True)
    html = probe_page.shell(
        title="The Vetoes",
        eyebrow="OMEN &middot; homework",
        h1="Should this have fired?",
        lede="Every chart here is a setup the engine found and then refused. "
             "The entry and stop it wanted are drawn. Tell it which refusals "
             "were wrong. Saves as you go &mdash; close it and come back.",
        cards_html="".join(render_card(c) for c in cards),
        footer_html="%d cards. Every one is a symbol-day you have never been "
                    "shown. The engine's own verdict is not on this page."
                    % len(cards),
        deck_id=name)
    path = os.path.join(PROBES_DIR, name + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    man = os.path.join(PROBES_DIR, name + "-manifest.jsonl")
    with open(man, "w", encoding="utf-8") as f:
        for c in cards:
            r = c["sig"]
            f.write(json.dumps({
                "card_id": "%s_%s" % (r["sym"], r["day"]),
                "symbol": r["sym"], "date": r["day"], "deck": name,
                "et": r["et"], "setup": r["setup"], "level": r["level"],
                "engine_grade": r["grade"], "engine_sgrade": r["sgrade"],
                "engine_status": r["status"], "downgrades": r["downgrades"],
                "hindsight_r": r["r"], "hindsight_out": r["out"],
            }, sort_keys=True) + "\n")
    return path, man


def selfcheck() -> int:
    """Cheap invariants on the population, no rendering."""
    pool = vetoed_s_signals()
    assert pool, "population is empty"
    assert all(r["status"] == "skipped_d" for r in pool), "a non-vetoed row got in"
    assert all(r["sgrade"] == "S" for r in pool), "a non-S row got in"
    assert all(r["setup"] in SETUPS for r in pool), "an off-setup row got in"
    keys = [(r["sym"], r["day"]) for r in pool]
    assert len(set(keys)) == len(keys), "two cards would share a symbol-day"
    print("selfcheck GREEN: %d vetoed-S symbol-days, one signal each" % len(pool))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="omen-x-vetoes")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()

    own = os.path.join(PROBES_DIR, "%s-manifest.jsonl" % a.name)
    cards = pick(a.n, a.seed, own)
    path, man = build(cards, a.name)

    ids = ["%s_%s" % (c["sig"]["sym"], c["sig"]["day"]) for c in cards]
    assert len(set(ids)) == len(ids), "duplicate card_id inside the deck"
    repeats = set(ids) & seen_card_ids(own)
    assert not repeats, "deck repeats a day he has seen: %s" % sorted(repeats)
    blob = open(path, encoding="utf-8").read()
    for leak in ("skipped_d", "engine_grade", "hindsight", '"X"'):
        assert leak not in blob, "answer key leaked into the HTML: %s" % leak

    print("Wrote %s" % path)
    print("       %s  (answer key -- not served)" % man)
    print("  cards=%d  size=%.1f MB" % (len(cards), len(blob.encode("utf-8")) / 1e6))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
