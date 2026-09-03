"""build_deck.py — THE OMEN deck generator. There is no other one.

Standard (settled 2026-08-21, Projects/omen-decks.md):
  * 60 cards per deck. Never 100, never 200 — a deck Austin can finish in a sitting.
  * Mixed: half days the engine fires on, half it is silent on, shuffled, with no
    tell in the card as to which is which.
  * Card = grade (S/A/C/none + legend) + trade type + entry + stop. No R:R.
  * Never repeats a symbol-day Austin has already judged, in ANY mark corpus --
    research/marks/*.jsonl plus the older files listed in LEGACY_MARK_FILES.
  * Every FIRE card passes the T21 pre-filter (research/t21_card_filter.py)
    before it can reach him. Austin, 2026-08-29: "you know better not to give me
    old trades that don't fit my system." Silent-day cards pass untouched --
    filtering them was measured and costs 9 of his 34 held-out S days for no
    lift (research/t21_card-selection.md). --no-prefilter turns it all off.
  * Front-end comes from deck_ui.py. This file supplies data only.

    python research/build_deck.py                       # default mixed deck
    python research/build_deck.py --name omen-5.3-mixed --n 60 --seed 7

Output: research/decks/<name>.html and research/decks/<name>-manifest.jsonl
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import deck_ui
import grade_read
import t21_card_filter as card_filter
from research.t4_engine_recall import (run_day, rth_candles, prior_day_levels,
                                       premarket_extremes)

ARCHIVE = os.path.join(ROOT, "data_archive")
MARKS_DIR = os.path.join(HERE, "marks")
DECKS_DIR = os.path.join(HERE, "decks")

SESSION_START = "09:30"
SESSION_END = "11:00"


# Every artifact carrying a human judgement, per research/marks/LEDGER.md (OMEN 6
# ticket 01). research/marks/*.jsonl is globbed on top of this, so new deck
# exports are picked up automatically; these are the older corpora that live
# OUTSIDE that directory and were invisible to the guard until 2026-08-22.
#
# Deliberately NOT here: decks/*-manifest.jsonl and decks/_retired/*-key.json
# (engine answer keys, not Austin's judgements).
LEGACY_MARK_FILES = [
    # H2 tri-lane deck, lane 1 (B-remap), graded 2026-08-28 -- Austin's S/A/C/X
    # verdicts on engine-proposed B-only signals. Pasted into chat, not exported
    # to disk by the page, so this file is the only copy in the repo.
    "marks/deck_marks_h2_3lane_2026-08-28.jsonl",
    # Two confirmed regrades (TSLA 2026-05-21, QQQ 2026-07-24, both S -> A),
    # captured in-session 2026-09-03. Already inside the research/marks/ glob;
    # named here as well so the guard survives the file being moved. Listing a
    # path twice is harmless -- mark_sources() feeds a set union.
    "marks/regrade_confirm_2026-09-03.jsonl",
    "austin_marks_v7.jsonl",      # terminal file; v2-v6 are fully contained in it
    "blind_marks_all.jsonl",
    "marks_clean.jsonl",
    "mark_batch_02_grades.jsonl",
    "mark_batch_03_regrades.jsonl",
    "mark_batch_04_grades.jsonl",
    "derived_marks_v1.jsonl",
    "derived_marks_v2.jsonl",
    "recovered_reviews.jsonl",
    "austin_verdicts.json",       # a JSON list, not jsonl
    "marks/zz-ingest-selftest_2026-09-03.jsonl",
]

# The schemas disagree. Canonical day-cards carry card_id/symbol/date; the older
# bar-level corpora carry id/symbol/day; one batch carries only `id`. The join is
# always symbol + date.
#
# The grade itself is read by `research/grade_read.py` and nowhere else -- it is
# spelled eight different ways across these corpora, two of them inside the
# `answers` dict where no grade-field reader could see them. This tuple is kept
# only as the alias every caller already imports.
_GRADE_KEYS = grade_read.SCALAR_FIELDS

# A card_id may be prefixed by its section and suffixed by a bar index --
# `cal_QQQ_2026-06-29_b10`, `sr_TSLA_2026-03-12`, `TSLA_2026-05-21_36`. Pull the
# SYMBOL_DATE pair out of wherever it sits rather than assuming it is at the front.
_ID_RE = re.compile(r"(?:^|_)([A-Z][A-Z0-9.\-]{0,7})_(\d{4}-\d{2}-\d{2})(?:_|$)")


def _judgement_key(row: dict) -> str | None:
    """Normalise any mark row to ``SYMBOL_YYYY-MM-DD``, or None if it isn't a judgement.

    A row counts as a judgement when it carries a non-empty human grade, OR when
    it is a probe row carrying at least one answer. Note that ``grade: "none"``
    IS a judgement -- an explicit refusal to trade the day -- so it must exclude
    the day from future decks. Rows with no grade and no answers (e.g. the
    unmarked remainder of blind_marks_all.jsonl) are not judgements and do not
    exclude anything.

    Two holes, both found on the 2026-08-26 master homework export and both fixed
    here (OMEN Test 1):

    * **Prefixed card_ids parsed to garbage.** ``cal_QQQ_2026-06-29_b10`` split on
      ``_`` and yielded the key ``cal_QQQ``. All 51 rows of
      ``marks/probe_master_homework_2026-08-26.jsonl`` collapsed to six useless
      keys, so every day on that page was still eligible for a future deck.
    * **A probe answer is a judgement even with no grade field.** The 25
      ``sr_`` S-recall rows carry ``grade: null`` and ``answers.s_call`` -- Austin
      looked at the chart and said yes/no. That is exactly the thing the
      guarantee exists to protect, and it was invisible.
    * **``_no_trade`` rows were not judgements.** 143 rows of
      ``blind_marks_all.jsonl`` are bare ``{symbol, day, _no_trade: true}`` --
      Austin looked and said "nothing here". No grade key, no answers dict, so
      the row fell out at the first gate and all 143 stayed eligible. Two of
      them (BABA 2024-12-12, PLTR 2025-05-08) reached the 100-card S sweep on
      2026-08-28 and he spotted the repeat before the code did. ``_no_trade`` is
      the same thing as ``grade: "none"`` wearing a different field name.
    * **The grade was spelled eight ways and this read five.** ``answers.s`` and
      ``answers.s_call`` -- the yes/no S cards -- were only ever caught by the
      catch-all "any answer at all" test below. ``grade_read.has_judgement`` is
      the union of that old test and the eight-spelling reader, so the pool can
      only grow (research/g72_onespelling.md).
    """
    if not grade_read.has_judgement(row):
        return None
    symbol = row.get("symbol")
    day = row.get("date") or row.get("day")
    if not (symbol and day):
        # mark_batch_04_grades.jsonl carries only `id`; probe exports carry a
        # section-prefixed card_id.
        ident = row.get("card_id") or row.get("id") or row.get("card")
        if not ident:
            return None
        m = _ID_RE.search(str(ident))
        if not m:
            return None
        symbol, day = m.group(1), m.group(2)
    return "%s_%s" % (symbol, day)


def _rows(path: str):
    """Yield dict rows from a .jsonl or a .json list."""
    if not os.path.exists(path):
        return
    if path.endswith(".json"):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except ValueError:
            return
        for row in data if isinstance(data, list) else data.values():
            if isinstance(row, dict):
                yield row
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def mark_sources() -> list[str]:
    """Every path the no-repeat guard reads. Order is stable for reporting."""
    return sorted(glob.glob(os.path.join(MARKS_DIR, "*.jsonl"))) + [
        os.path.join(HERE, name) for name in LEGACY_MARK_FILES
    ]


def marked_card_ids(per_source: dict | None = None) -> set[str]:
    """Every symbol-day Austin has already judged, across EVERY mark corpus.

    This is the no-repeats guarantee. A deck that re-asks a day he already
    answered wastes the only scarce input in this project.

    Until 2026-08-22 this globbed research/marks/ alone and was blind to the 386
    symbol-days in austin_marks_v7.jsonl and the standalone batches -- see OMEN 6
    ticket 15. Pass ``per_source`` (a dict) to have it filled with
    ``{path: n_keys}`` for reporting.
    """
    seen: set[str] = set()
    for path in mark_sources():
        found = {k for k in (_judgement_key(r) for r in _rows(path)) if k}
        if per_source is not None:
            per_source[path] = len(found)
        seen |= found
    return seen


def graded_days() -> dict[str, set[str]]:
    """``{SYMBOL_YYYY-MM-DD: {every grade any corpus gives that day}}``.

    Grades come out of ``research/grade_read.py`` -- the one reader -- so a day
    graded S in ``answers.s`` counts exactly like one graded S in ``austin_tier``.
    A day appears here only if some corpus states a grade for it; days that are
    judgements by attention alone (a stop price, ``_no_trade``) show as ``none``.
    """
    out: dict[str, set[str]] = {}
    for path in mark_sources():
        for row in _rows(path):
            key = _judgement_key(row)
            if not key:
                continue
            g = grade_read.read_grade(row)
            if g is not None:
                out.setdefault(key, set()).add(g)
    return out


def s_days() -> set[str]:
    """**The one S-day count.** Every symbol-day Austin called S, any spelling.

    Union rule: if any row in any corpus grades the day S, the day is S. The
    recall question is "did the engine trade the day he liked", so one S bar is
    an S day. 35 of these are contested -- S in one sitting, not-S in another --
    and they are listed in ``research/g72_onespelling.md``; the union counts them
    as S. Anything that needs a different rule must say so out loud and show its
    own script.
    """
    return {k for k, grades in graded_days().items() if "S" in grades}


def served_card_ids(exclude: str | None = None) -> set[str]:
    """Every symbol-day that has ever been PUT IN FRONT of him, graded or not.

    Grading is not the only thing that spends his attention -- looking is. A card
    served in an earlier deck and never exported back is still a chart he has
    seen, and re-serving it is the waste his no-repeats rule exists to stop.

    Every deck builder writes ``<name>-manifest.jsonl`` beside its HTML, so the
    manifests are the served record. On 2026-08-28 there were 602 symbol-days
    served but never graded back, all of them eligible for a new deck, which is
    why the 100-card S sweep felt repetitive to him before any code noticed.
    """
    skip = os.path.abspath(exclude) if exclude else None
    out: set[str] = set()
    for path in sorted(glob.glob(os.path.join(HERE, "**", "*manifest*.jsonl"),
                                 recursive=True)):
        # A deck must not block itself: rebuilding under the same name would
        # otherwise read the manifest it is about to overwrite and empty the pool.
        if skip and os.path.abspath(path) == skip:
            continue
        for row in _rows(path):
            ident = row.get("card_id") or row.get("id")
            if isinstance(ident, str):
                m = _ID_RE.search(ident)
                if m:
                    out.add("%s_%s" % (m.group(1), m.group(2)))
    return out


def seen_card_ids(exclude: str | None = None) -> set[str]:
    """Judged OR served. This is what a new deck must exclude.

    ``exclude`` is the manifest path this build is about to write, so a rebuild
    under an existing name does not treat its own previous output as history.
    """
    return marked_card_ids() | served_card_ids(exclude)


def universe() -> list[tuple[str, str]]:
    """(symbol, day) for every archived trading day."""
    out = []
    for sym in sorted(os.listdir(ARCHIVE)):
        d = os.path.join(ARCHIVE, sym)
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, "*.csv")):
            out.append((sym, os.path.basename(f)[:-4]))
    return out


def session_candles(symbol: str, day: str) -> list:
    candles = rth_candles(symbol, day)
    if not candles:
        return []
    out = []
    for c in candles:
        t = c.timestamp[11:16] if "T" in c.timestamp else c.timestamp[:5]
        if SESSION_START <= t < SESSION_END:
            out.append(c)
    return out


def candle_dict(c) -> dict:
    return {"t": c.timestamp, "o": round(c.open, 2), "h": round(c.high, 2),
            "l": round(c.low, 2), "c": round(c.close, 2), "v": int(c.volume)}


def fire_count(symbol: str, day: str) -> int:
    return day_fires(symbol, day)[0]


def day_fires(symbol: str, day: str):
    """(number of entries the engine would take, first entry minute "HH:MM"|None)."""
    try:
        entries, _sigs, _raw = run_day(symbol, day)
    except Exception:
        return 0, None
    if not entries:
        return 0, None
    return len(entries), entries[0]["timestamp"][:5]


def pick(n: int, seed: int, max_probe: int, own_manifest: str | None = None,
         prefilter: bool = True):
    """Half fire days, half silent days, drawn at random, never already marked,
    and -- since T21 -- never a card the pre-filter says does not fit his system.

    Austin, probe_master_2026-08-29.jsonl: "you know better not to give me old
    trades that don't fit my system." He refused 64 of 90 cards in that probe.
    ``prefilter`` runs research/t21_card_filter over every FIRE candidate before
    it can reach a deck -- one rule: reject a card whose furthest watched level
    ahead is more than 8R away. Silent-day candidates pass untouched, because
    filtering them was measured and is pure cost (9 of his 34 held-out S days,
    for a null lift). See research/t21_card-selection.md. Pass
    ``prefilter=False`` only to reproduce a pre-T21 deck.
    """
    want = n // 2
    per_source: dict[str, int] = {}
    judged = marked_card_ids(per_source)
    served = served_card_ids(own_manifest)
    seen = judged | served
    full = universe()
    pool = [(s, d) for s, d in full if "%s_%s" % (s, d) not in seen]
    print("no-repeat guard: %d judged + %d served-only = %d seen symbol-days "
          "across %d mark sources; pool %d -> %d archived days"
          % (len(judged), len(served - judged), len(seen), len(per_source),
             len(full), len(pool)))
    for path, cnt in sorted(per_source.items(), key=lambda kv: -kv[1]):
        if cnt:
            print("    %5d  %s" % (cnt, os.path.relpath(path, ROOT)))
    rng = random.Random(seed)
    rng.shuffle(pool)

    fire, silent = [], []
    probed = 0
    dropped = 0
    drop_reasons: dict[str, int] = {}
    for sym, day in pool:
        if len(fire) >= want and len(silent) >= want:
            break
        if probed >= max_probe:
            break
        candles = session_candles(sym, day)
        if len(candles) < 60:
            continue
        probed += 1
        n_fires, first_et = day_fires(sym, day)
        bucket = fire if n_fires > 0 else silent
        if len(bucket) >= want:
            continue
        verdict = None
        if prefilter:
            feat = card_filter.features(sym, day, first_et)
            if feat is None:
                continue
            ok, why = card_filter.verdict(feat)
            if not ok:
                dropped += 1
                for w in why:
                    drop_reasons[w] = drop_reasons.get(w, 0) + 1
                continue
            verdict = {"er_session": feat["er_session"], "reach_r": feat["reach_r"],
                       "impulse_atr": feat["impulse_atr"], "et": feat["et"]}
        pdh, pdl, _o, _c = prior_day_levels(sym, day)
        pmh, pml = premarket_extremes(sym, day)
        # Opening range = first 5 RTH bars, same definition backtest_week.py:808,
        # backtest_12mo.py:144 and backtest_30d_report.py:40 all use.
        orh = max(c.high for c in candles[:5]) if len(candles) >= 5 else None
        orl = min(c.low for c in candles[:5]) if len(candles) >= 5 else None
        bucket.append({"symbol": sym, "day": day, "candles": candles,
                       "pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
                       "orh": orh, "orl": orl, "fires": n_fires,
                       "prefilter": verdict})
        if probed % 25 == 0:
            print("  probed %d  fire=%d silent=%d prefilter-dropped=%d"
                  % (probed, len(fire), len(silent), dropped))

    if prefilter:
        kept = len(fire) + len(silent)
        print("T21 pre-filter: %d of %d probed days dropped (%.1f%%), %d kept"
              % (dropped, dropped + kept,
                 100 * dropped / (dropped + kept) if dropped + kept else 0, kept))
        for w, c in sorted(drop_reasons.items(), key=lambda kv: -kv[1]):
            print("    %-13s %d" % (w, c))
    else:
        print("T21 pre-filter: DISABLED -- this deck may repeat the cards "
              "Austin refused 64 of 90 times")

    cards = fire + silent
    rng.shuffle(cards)          # no positional tell
    return cards, len(fire), len(silent), probed, len(seen)


def write_deck(cards, name: str, label: str) -> str:
    os.makedirs(DECKS_DIR, exist_ok=True)
    day_data, prior, card_ids, htmls = {}, {}, [], []
    for c in cards:
        cid = "%s_%s" % (c["symbol"], c["day"])
        card_ids.append(cid)
        day_data[cid] = [candle_dict(x) for x in c["candles"]]
        # All six levels deck_ui.LEVEL_KEYS knows how to draw. Supplying only
        # PDH/PDL left four of them silently blank, and break-and-retest is
        # defined ON these levels -- a card without them cannot be graded.
        prior[cid] = {k: (round(c[k], 2) if c.get(k) else None)
                      for k in ("pdh", "pdl", "pmh", "pml", "orh", "orl")}
        htmls.append(deck_ui.render_card(cid, c["symbol"]))

    out = deck_ui.HTML_HEAD.replace("__LABEL__", label).replace("__TOTAL__", str(len(card_ids)))
    out += "\n".join(htmls)
    script = deck_ui.HTML_SCRIPT_PREAMBLE
    script = script.replace("__DAY_DATA__", json.dumps(day_data))
    script = script.replace("__PRIOR_LEVELS__", json.dumps(prior))
    script = script.replace("__CARD_IDS__", json.dumps(card_ids))
    script = script.replace("__SETUPS__", json.dumps(deck_ui.SETUPS))
    script = script.replace("__DECK_ID__", name)
    out += script

    path = os.path.join(DECKS_DIR, name + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)

    # The answer key stays OUT of the HTML — the deck must not tell him which
    # days the engine saw.
    man = os.path.join(DECKS_DIR, name + "-manifest.jsonl")
    with open(man, "w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps({"card_id": "%s_%s" % (c["symbol"], c["day"]),
                                "symbol": c["symbol"], "date": c["day"],
                                "deck": name,
                                "engine_fires_that_day": c["fires"],
                                # T21: why this card was allowed in front of him
                                "prefilter": c.get("prefilter")},
                               sort_keys=True) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="omen-5.3-mixed")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--max-probe", type=int, default=1200)
    ap.add_argument("--no-prefilter", action="store_true",
                    help="skip the T21 card pre-filter (reproduces a pre-T21 deck)")
    ap.add_argument("--label", default=None)
    a = ap.parse_args()

    if a.n > 60:
        raise SystemExit("deck standard caps a deck at 60 cards (asked for %d)" % a.n)

    cards, nf, ns, probed, nseen = pick(a.n, a.seed, a.max_probe,
                                        prefilter=not a.no_prefilter)
    label = a.label or ("mixed — %d cards, engine-fire days and silent days shuffled" % len(cards))
    path = write_deck(cards, a.name, label)

    ids = ["%s_%s" % (c["symbol"], c["day"]) for c in cards]
    assert len(set(ids)) == len(ids), "duplicate card_id inside the deck"
    # Checked against EVERY mark corpus, not just research/marks/ -- ticket 15.
    repeats = set(ids) & seen_card_ids()
    assert not repeats, "deck repeats already-judged days: %s" % sorted(repeats)

    print("Wrote %s" % path)
    print("  cards=%d  fire=%d  silent=%d" % (len(cards), nf, ns))
    print("  probed=%d days  excluded %d already-judged symbol-days" % (probed, nseen))


if __name__ == "__main__":
    main()
