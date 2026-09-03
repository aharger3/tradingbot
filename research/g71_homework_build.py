"""g71_homework_build.py -- "the 3 stocks I believe are S trades".

Austin, 2026-08-29:

    "next homework is the 3 stocks that you believe are s trades, dont mark just
     timeframe and 6 levels, and i say yes or no and mark what you need and if not
     s i say why. but 84 percent and ocr need to be higher in the batch because
     those are probably broken."

So this is a PRECISION instrument, the mirror of the recall decks. Every card is a
symbol-day the engine claims is an S. The chart carries the session timeframe and
his six levels and NOTHING else -- no entry, no stop, no grade, no annotation. The
only thing under the chart is the setup the engine claims and the level it claims
to have broken, because a re-entry card is unreadable without knowing it is a
re-entry.

WHAT CHANGED IN THE REBUILD (G7.2, 2026-08-29)
----------------------------------------------
The first cut of this page asked the wrong question three ways. All three are
fixed here, and nothing else about the instrument moved.

1. IT DREW THE WRONG LEVELS. probe_chart drew PDH/PDL/PMH/PML/ORH/ORL. Austin
   settled his six the same morning and they are **PDH, PDL, PMH, PML, HOD, LOD**
   -- the opening range is not one of them, and HOD is the level the engine misses
   most (413 symbol-days). probe_chart now knows HOD/LOD (new `lvl-hl` colour
   class); this page passes his six and simply omits `orh`/`orl` from the levels
   dict, so the opening range is not drawn here and every other page that wants it
   still gets it.

   HOD/LOD ANCHOR -- and this is the part that could have leaked the answer.
   They are running session extremes, so "the high of day" is a different number
   on every bar. They are computed over the session bars that had ALREADY CLOSED
   BEFORE the setup bar -- `candles[:entry_i]`, strictly prior, 09:30 up to the
   minute before the signal. That is the level that existed to be broken. Using
   the whole session would draw a line off bars that had not happened yet, which
   is hindsight printed on the card. Using bars up to AND INCLUDING the setup bar
   (which is what signal_runner does for its own 84%-rule RR check) would pin the
   line to the setup bar's own extreme whenever the setup broke it, which both
   looks wrong and points at the entry. Strictly prior is the conservative one.
   Consequence, stated plainly on the card: the HOD line can sit BELOW later
   highs. That is correct, not a rendering bug, and the legend says so.

2. TWENTY OF THIRTY CARDS SAID THE LEVEL WAS "other". Fixed upstream -- the book
   now labels the setup and the level on 100% of its 134,012 rows. Every card
   prints the real level name.

3. FOUR CARDS WERE PIVOT-LEVEL SETUPS. Austin ruled the same morning that pivot
   levels gate nothing. A card is now eligible ONLY if the level it is about is
   one of his six. See below -- that gate is the fiddly part.

WHICH LEVEL IS "THE LEVEL THIS CARD IS ABOUT"
---------------------------------------------
Only break-and-retest names a level. The other two setups do not, by construction,
and pretending otherwise would be inventing data:

* BR  -- the engine names it. `level_name` off the book row, straight through.
* 84% -- `backtest_2y.level_label` is explicit that this setup's own level is
         "the prior failed entry, not a level the detector named". But the 84%
         rule IS a second attempt at the level the first attempt broke, so the
         card chains back ONE hop: find the earlier row on the same symbol-day
         whose entry price is the 84% row's `level_px`, and take THAT row's
         level. 25 of the 70 84% rows chain back to one of his six.
* OCR -- the one candle rule's level is a one-minute order block, which is a
         candle, not a level on anybody's list. So the test is coincidence: does
         the order block sit ON one of his six? Within ONE TOLERANCE UNIT --
         25% of the previous candle's range, `signal_runner.BAR_EXTREME_FRAC`,
         the project's single tolerance unit, imported not re-typed. 84 of the
         964 OCR symbol-days sit on one of his six.

`downgrade.CONFLUENCE_LEVELS` is a DIFFERENT set (PDH, PDL, PMH, PML, ORH, ORL)
for a DIFFERENT job -- the confluence tally, which deliberately uses only levels
fixed at or before the open so it cannot leak hindsight
(research/p18_p19_new_variables.md:53). It is not touched here and must never be
merged with his six.

WHERE "I BELIEVE IT IS AN S" COMES FROM
---------------------------------------
`research/downgrade.py` -- Austin's own ladder, `sgrade` on every row of the
two-year book (`research/bt2y_trades.json`). NOT the legacy `A+/A/B/C/X` ladder,
which is not a grade and does not answer this question. Legacy grade, traded flag,
role and outcome are written to the manifest and kept OUT of the page: they are
the thing this homework is testing, not an input to it.

WHICH SIGNAL ON THE CHART A CARD IS ALLOWED TO BE (G8.2, 2026-08-30)
----------------------------------------------------------------------
research/g77_wrongchart.md: the first cut of this page picked its representative
signal by BELIEF alone (S-graded, fewest downgrades, earliest minute) and never
asked whether the engine TOOK it. 25 of 30 served cards were signals the engine
refused outright or traded something else on the same chart -- so the yes/no
Austin gave was not attached to a trade the engine will actually make.

Fixed here by restricting every card to one of exactly two honest roles:

* role "traded" -- the engine's own FIRST BOOKED TRADE of the session
  (`g77_realtrade_pick.day_trade`) IS the S-graded signal for this bucket. A yes
  confirms a trade the engine will actually take; that is the whole point of a
  precision instrument.
* role "silent" -- the engine booked NOTHING on this chart, all morning. The
  day's strongest eligible S signal stands in for the card. This is the case
  Austin's own fix request called the most valuable one: **a yes here is a pure
  miss** -- proof the engine should have fired and didn't.

A day where the engine booked a DIFFERENT signal than the one a bucket would
otherwise show -- the wrong-chart bug itself, 14 of the original 30 cards -- is
dropped from the candidate pool outright (`census[bucket]["traded_elsewhere"]`).
Showing that signal at all reproduces the exact defect this rebuild exists to fix.

BATCH COMPOSITION -- the stated quota, and why it is not the population
-------------------------------------------------------------------------
Austin asked for 84% and OCR to be over-weighted "because those are probably
broken". The batch is 10 slates of 3 -- his "3 stocks" -- and every slate holds
one of each bucket, shuffled inside the slate so the position carries no tell.

BR is not padding. Without a control arm a low yes-rate on OCR/84% cannot be told
apart from a low yes-rate on "engine thinks S at all", which is the actual open
question. A symbol-day lands in exactly one bucket -- by the role-"traded" row's
own setup when the engine booked something S-graded that day, otherwise by
priority 84% > OCR > BR among its silent S signals.

Within EACH bucket, `TRADED_QUOTA_FRAC` (0.5, matching `build_deck.py`'s own
"half fires, half silent" standard) states the target share of that bucket's
cards that must be role "traded", the rest role "silent" -- picked
belief-strongest-first within each role, traded exhausted before silent
backfills. The 84% arm has almost no traded candidates book-wide (4 raw
symbol-days in two years, against 398 for BR and 110 for OCR --
`g77_wrongchart.md` explains why: 84% is the arm that loses money and rarely
becomes the day's actual trade), so its bucket will usually run short of quota
and fall back to silent-role cards -- reported explicitly per bucket, never
padded silently.

GUARDS
------
* `build_deck.seen_card_ids()` -- judged (`marked_card_ids`) OR ever served. Being
  served counts; that is the guarantee's third failure mode. The build ABORTS on
  a collision rather than serving a repeat.
* `t21_card_filter` -- the shipped deck pre-filter, reach <= 8R at the proposed
  entry bar.
* Max 2 cards per symbol.

OUTPUT
------
    research/g71_homework.html                        the page (same path -- the
                                                      published link updates in
                                                      place, no second link)
    research/decks/g71-homework-s3-manifest.jsonl     the served record + answer key

    python research/g71_homework_build.py [--seed 71] [--slates 10]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd
import g77_realtrade_pick as realtrade
import probe_chart
import probe_page
import t21_card_filter as card_filter
from signal_runner import BAR_EXTREME_FRAC

BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT_HTML = os.path.join(HERE, "g71_homework.html")
OUT_MANIFEST = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
DECK_ID = "g71-homework-s3"

# Austin's six, named by him 2026-08-29 (Projects/omen-rulebook.md, "The six
# levels, named at last"): "you know the 6 levels i watch thats it." Same set as
# backtest_2y.HIS_SIX -- deliberately NOT downgrade.CONFLUENCE_LEVELS.
HIS_SIX = ("PDH", "PDL", "PMH", "PML", "HOD", "LOD")

# Bucket priority (silent-role days only -- see load_s_days). A symbol-day is
# filed under the first bucket whose setup it carries an eligible S-graded
# signal for, so the arms are disjoint.
BUCKETS = ("84", "OCR", "BR")
SETUP_OF = {"reentry_84_rule": "84", "one_candle_rule": "OCR",
            "break_and_retest": "BR"}

# G8.2 stated quota (research/g82_deck_fix.md): target share of EACH bucket's
# cards that must be role "traded" -- the engine's own booked trade -- with the
# rest role "silent" -- a day the engine refused outright. 0.5 matches
# build_deck.py's own "half fires, half silent" mix. A bucket that cannot
# supply enough traded candidates (84% especially -- see module docstring)
# falls back to silent and says so in the printed stats; it is never padded
# with a signal the engine set aside for a different trade that day.
TRADED_QUOTA_FRAC = 0.5
ROLES = ("traded", "silent")

SETUP_LABEL = {
    "84": "84% rule &mdash; re-entry after a stop-out",
    "OCR": "OCR &mdash; one candle rule",
    "BR": "BR &mdash; break and retest",
    "BR+OCR": "BR + OCR &mdash; both",
}

LEVEL_BLURB = {
    "PDH": "prior day high", "PDL": "prior day low",
    "PMH": "pre-market high", "PML": "pre-market low",
    "HOD": "high of day so far", "LOD": "low of day so far",
}

# How the card's level was read. Printed on the card so a chained or coincident
# level is never passed off as one the engine named.
SOURCE_BLURB = {
    "named": "",
    "chained": " &mdash; the level the first attempt broke",
    "coincident": " &mdash; the order block sits on it",
}

NO_REASONS = [
    ("no_displacement", "no displacement &mdash; the break had no force"),
    ("stale_retest", "stale retest &mdash; came back too late"),
    ("level_not_respected", "level not respected &mdash; closing on it / chopping on it"),
    ("exhausted", "exhausted &mdash; the move is already spent"),
    ("counter_trend_not_respected", "counter-trend candles not bought back"),
    ("break_then_rejection", "broke, then gave it straight back"),
    ("no_retest", "no retest &mdash; ran and never came back"),
    ("ocr_not_respected", "OCR present but not respected"),
    ("chase", "chase &mdash; too far past the level"),
    ("chop", "chop / no structure here"),
    ("late", "too late in the window"),
    ("wrong_level", "wrong level &mdash; that is not a level I watch"),
    ("not_a_trade", "not a trade at all &mdash; wrong chart to show me"),
    ("other", "other &mdash; say it below"),
]


# ------------------------------------------------------------------ levels

def static_levels(sym, day):
    """(pdh, pdl, pmh, pml) -- the four of his six that are fixed before 09:30."""
    pdh, pdl, _o, _c = bd.prior_day_levels(sym, day)
    pmh, pml = bd.premarket_extremes(sym, day)
    return pdh, pdl, pmh, pml


def running_extremes(candles, i):
    """(hod, lod) as they stood BEFORE session bar `i` -- see the module note.

    Strictly prior: `candles[:i]`, 09:30 through the minute before the setup bar.
    A level built from bars that had not closed yet is hindsight on the card.
    """
    pre = candles[:i]
    if not pre:
        return None, None
    return max(c.high for c in pre), min(c.low for c in pre)


def levels_for(sym, day, candles, i):
    """His six, keyed the way probe_chart wants them. No orh/orl: the opening
    range is not one of his six and this page does not draw it."""
    pdh, pdl, pmh, pml = static_levels(sym, day)
    hod, lod = running_extremes(candles, i)
    return {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
            "hod": hod, "lod": lod}


def tolerance(candles, i):
    """One tolerance unit: 25% of the PREVIOUS candle's range."""
    prev = candles[i - 1]
    return max(BAR_EXTREME_FRAC * (prev.high - prev.low), 0.005)


def resolve_level(row, day_rows, candles, six):
    """(level name in HIS_SIX or None, how it was read).

    One function, three readings -- see WHICH LEVEL IS "THE LEVEL THIS CARD IS
    ABOUT" at the top. Anything that does not land on one of his six comes back
    None and the card is not eligible.
    """
    setup = SETUP_OF.get(row.get("setup"))
    if setup == "BR":
        n = row.get("level_name")
        return (n, "named") if n in HIS_SIX else (None, "named")

    if setup == "84":
        # One hop back: the row whose ENTRY is this row's level_px is the
        # attempt that got stopped out, and its level is the level in play.
        px = row.get("level_px")
        if px is None:
            return None, "chained"
        prior = [q for q in day_rows
                 if (q.get("et") or "99:99") < (row.get("et") or "00:00")
                 and q.get("entry") is not None and abs(q["entry"] - px) < 0.011]
        if not prior:
            return None, "chained"
        q = max(prior, key=lambda q: q.get("et") or "")
        n = q.get("level_name")
        return (n, "chained") if n in HIS_SIX else (None, "chained")

    # OCR: the order block is a candle, not a level. Does it sit on one of his six?
    i, px = row.get("entry_i"), row.get("level_px")
    if not i or px is None or i >= len(candles):
        return None, "coincident"
    tol = tolerance(candles, i)
    for name in HIS_SIX:
        v = six.get(name.lower())
        if v is not None and abs(px - v) <= tol:
            return name, "coincident"
    return None, "coincident"


# ---------------------------------------------------------------- candidates

def load_s_days(book_path=BOOK):
    """symbol-day -> the card it would make, for every S day that survives the
    his-six gate; plus the per-bucket, per-role eligibility census.

    G8.2 (research/g82_deck_fix.md, fixing research/g77_wrongchart.md): every
    card is one of exactly two roles, chosen BEFORE belief strength ever plays
    a part --

    * "traded" -- the engine's own first booked trade of the session
      (`g77_realtrade_pick.day_trade`) is itself an S-graded signal. The bucket
      is that trade's own setup, not a priority guess.
    * "silent" -- the engine booked nothing at all that session. The bucket is
      chosen by priority (84 > OCR > BR) among the day's eligible S signals, and
      the representative is the strongest ELIGIBLE one: fewest downgrades
      tripped first, then earliest entry minute (Austin, rulebook "Earlier is
      better").

    A day where the engine booked something, but not the S signal a bucket
    would otherwise show, is neither -- it is the wrong-chart bug itself, and
    is dropped (counted under `census[bucket]["traded_elsewhere"]`).
    """
    with open(book_path, encoding="utf-8") as fh:
        book = json.load(fh)
    s_rows = [r for r in book["trades"] if r.get("sgrade") == "S"]
    s_by_day, all_by_day = defaultdict(list), defaultdict(list)
    for r in s_rows:
        s_by_day[(r["sym"], r["day"])].append(r)
    for r in book["trades"]:
        all_by_day[(r["sym"], r["day"])].append(r)

    out = {}
    census = defaultdict(Counter)     # bucket -> {"days", "eligible", role...}
    levels = Counter()
    for (sym, day), rs in s_by_day.items():
        day_rows = all_by_day[(sym, day)]
        trade = realtrade.day_trade(day_rows)
        setups = {SETUP_OF.get(r["setup"]) for r in rs}

        if trade is not None and trade.get("sgrade") == "S" \
                and SETUP_OF.get(trade.get("setup")) is not None:
            bucket = SETUP_OF[trade["setup"]]
            role = "traded"
            pool = [trade]
        elif trade is not None:
            # The engine booked something -- just not this day's S signal. The
            # exact wrong-chart bug. Bucket it (for the census only) by
            # priority same as a silent day, then drop it.
            bucket = next((b for b in BUCKETS if b in setups), None)
            if bucket is None:
                continue
            census[bucket]["traded_elsewhere"] += 1
            continue
        else:
            bucket = next((b for b in BUCKETS if b in setups), None)
            if bucket is None:
                continue
            role = "silent"
            pool = [r for r in rs if SETUP_OF.get(r["setup"]) == bucket]

        census[bucket]["days"] += 1
        census[bucket][role + "_days"] += 1

        candles = None
        if bucket == "OCR":                    # only OCR needs the bars to decide
            candles = bd.session_candles(sym, day)
            if len(candles) < 60:
                census[bucket]["thin_session"] += 1
                continue

        keep = []
        for r in pool:
            if bucket == "OCR":
                six_r = levels_for(sym, day, candles, r.get("entry_i") or 1)
            else:
                six_r = None
            name, how = resolve_level(r, day_rows, candles or [], six_r or {})
            if name:
                keep.append((r, name, how))
        if not keep:
            continue
        census[bucket]["eligible"] += 1
        census[bucket][role + "_eligible"] += 1
        r, name, how = min(keep, key=lambda t: (int(t[0].get("tripped") or 0),
                                                t[0].get("et") or "99:99"))
        levels[(bucket, name)] += 1
        out[(sym, day)] = {"bucket": bucket, "rep": r, "level": name,
                           "level_how": how, "n_s_signals": len(rs),
                           "setups": sorted(s for s in setups if s),
                           "role": role}
    return out, len(s_rows), census, levels


def card_setup_label(rep, bucket):
    """What the card claims. BR splits on confluence; OCR and 84% do not."""
    if bucket == "BR" and rep.get("confluence") == "yes":
        return "BR+OCR"
    return bucket


_LVL_DRAWN = re.compile(r'class="lvl-t [^"]*"[^>]*>([A-Z]{3}) ')


def offchart_note(svg, levels, candles):
    """Name the levels the chart could not fit, with their price and side.

    probe_chart only lets a level widen the frame by a quarter of the session's
    own range -- otherwise one far level flattens 90 candles into a ribbon.
    Austin asked for six levels, and a card silently showing four is a card
    missing two of his inputs. Rather than re-derive probe_chart's framing here,
    read back which labels the SVG actually drew and report the difference.
    """
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


def pick(n_slates, seed, max_per_symbol=2, max_probe_per_bucket=600,
        traded_quota=TRADED_QUOTA_FRAC):
    days, n_s_rows, census, level_census = load_s_days()
    judged = bd.marked_card_ids()
    served = bd.served_card_ids(OUT_MANIFEST)
    seen = judged | served
    print("no-repeat guard: %d judged + %d served-only = %d seen symbol-days"
          % (len(judged), len(served - judged), len(seen)))

    print("S-graded population: %d signals" % n_s_rows)
    print("his-six gate (PDH/PDL/PMH/PML/HOD/LOD), eligible symbol-days:")
    for b in BUCKETS:
        c = census[b]
        print("  %-3s %5d S days -> %4d eligible  (%.1f%%)  "
              "[traded %d/%d elig, silent %d/%d elig, dropped-traded-elsewhere %d]"
              % (b, c["days"], c["eligible"],
                 100.0 * c["eligible"] / max(1, c["days"]),
                 c["traded_eligible"], c["traded_days"],
                 c["silent_eligible"], c["silent_days"],
                 c["traded_elsewhere"]))
    print("  level of the eligible days: %s"
          % dict(sorted(level_census.items(), key=lambda kv: -kv[1])))

    rng = random.Random(seed)
    by_bucket_role = defaultdict(lambda: defaultdict(list))
    for (sym, day), v in days.items():
        if "%s_%s" % (sym, day) in seen:
            continue
        by_bucket_role[v["bucket"]][v["role"]].append((sym, day, v))
    for b in BUCKETS:
        print("  %-3s eligible after no-repeat: traded %d, silent %d"
              % (b, len(by_bucket_role[b]["traded"]),
                 len(by_bucket_role[b]["silent"])))

    target_traded = max(0, min(n_slates, round(n_slates * traded_quota)))
    print("stated quota: %d/%d traded per bucket (%.0f%%), rest silent, "
          "traded exhausted before silent backfills"
          % (target_traded, n_slates, 100.0 * traded_quota))

    chosen, per_symbol = {}, Counter()
    stats = {}
    for b in BUCKETS:
        pools = {}
        for role in ROLES:
            c = list(by_bucket_role[b][role])
            rng.shuffle(c)
            # Belief strength first: a day with a zero-downgrade S signal is a
            # stronger claim than one that reached S only via the confluence +1.
            c.sort(key=lambda t: int(t[2]["rep"].get("tripped") or 0))
            pools[role] = c
        idx = {role: 0 for role in ROLES}
        taken, probed, dropped, no_bars = [], 0, Counter(), 0
        role_counts = Counter()
        while len(taken) < n_slates and probed < max_probe_per_bucket:
            want_traded = role_counts["traded"] < target_traded
            role = "traded" if want_traded else "silent"
            if idx[role] >= len(pools[role]):
                other = "silent" if role == "traded" else "traded"
                if idx[other] >= len(pools[other]):
                    break             # both role pools exhausted
                role = other
            sym, day, v = pools[role][idx[role]]
            idx[role] += 1
            if per_symbol[sym] >= max_per_symbol:
                continue
            candles = bd.session_candles(sym, day)
            if len(candles) < 60:
                no_bars += 1
                continue
            i = v["rep"].get("entry_i")
            if not i or i >= len(candles):
                dropped["no_setup_bar"] += 1
                continue
            probed += 1
            feat = card_filter.features(sym, day, v["rep"].get("et"))
            if feat is None:
                dropped["no_features"] += 1
                continue
            ok, why = card_filter.verdict(feat)
            if not ok:
                for w in why:
                    dropped[w] += 1
                continue
            lv = levels_for(sym, day, candles, i)
            if lv.get(v["level"].lower()) is None:
                # The gate said this level exists; if the renderer cannot be
                # given a price for it the card would claim a level it does not
                # draw. Drop rather than draw a card that contradicts itself.
                dropped["level_unpriced"] += 1
                continue
            taken.append({"symbol": sym, "day": day, "bucket": b,
                          "candles": candles, "levels": lv, "rep": v["rep"],
                          "level": v["level"], "level_how": v["level_how"],
                          "setup_i": i, "role": role,
                          "n_s_signals": v["n_s_signals"], "setups": v["setups"],
                          "prefilter": {"reach_r": feat["reach_r"],
                                        "er_session": feat["er_session"],
                                        "impulse_atr": feat["impulse_atr"],
                                        "et": feat["et"]}})
            per_symbol[sym] += 1
            role_counts[role] += 1
        chosen[b] = taken
        stats[b] = {"probed": probed, "t21_dropped": dict(dropped),
                    "short_session": no_bars,
                    "eligible": census[b]["eligible"], "s_days": census[b]["days"],
                    "picked": len(taken), "wanted": n_slates,
                    "target_traded": target_traded,
                    "role_counts": dict(role_counts)}
        short = "" if len(taken) >= n_slates else "  ** SHORT **"
        quota_note = "" if role_counts["traded"] >= target_traded else \
            "  ** QUOTA SHORT: %d/%d traded **" % (role_counts["traded"], target_traded)
        print("  %-3s picked %d/%d (traded %d, silent %d; probed %d, T21 dropped "
              "%s, thin sessions %d)%s%s"
              % (b, len(taken), n_slates, role_counts["traded"], role_counts["silent"],
                 probed, dict(dropped) or "-", no_bars, short, quota_note))

    # Slates of three: one of each bucket, order shuffled inside the slate. A
    # bucket that could not fill leaves a short slate rather than a slate padded
    # with a level he does not watch.
    slates = []
    for i in range(n_slates):
        row = [chosen[b][i] for b in BUCKETS if i < len(chosen[b])]
        rng.shuffle(row)
        if row:
            slates.append(row)
    return slates, seen, stats, census, level_census


# ---------------------------------------------------------------- rendering

def render_card(idx, c):
    cid = "%s_%s" % (c["symbol"], c["day"])
    label = card_setup_label(c["rep"], c["bucket"])
    lv = {k: (round(v, 2) if v is not None else None) for k, v in c["levels"].items()}
    svg = probe_chart.render([bd.candle_dict(x) for x in c["candles"]], lv,
                             marks=[],
                             label="%s %s 1-minute 09:30-11:00" % (c["symbol"], c["day"]))
    off = offchart_note(svg, lv, c["candles"])
    export = json.dumps({"symbol": c["symbol"], "date": c["day"],
                         "claimed_setup": label, "claimed_level": c["level"],
                         "bucket": c["bucket"]},
                        sort_keys=True).replace('"', "&quot;")

    q_yes = probe_page.question(
        "is_s",
        "Is this an S trade?",
        "Yes or no. Nothing on this chart is marked &mdash; the timeframe and your six "
        "levels are all there is.",
        [("yes", "YES &mdash; this is an S"), ("no", "NO &mdash; not an S")],
        required=True,
        note_placeholder="if yes: anything you'd mark here (entry, stop, level) &mdash; optional")

    q_why = probe_page.question(
        "why_not",
        "If no &mdash; why not?",
        "Pick every one that applies. Skip this if you said yes.",
        NO_REASONS, multi=True, required=False, tone="veto",
        note_placeholder="in your own words (optional)")

    return ('<article class="card" data-cid="%s" data-export="%s" data-done="0">'
            '<header><span class="idx">%02d</span><span class="tick">%s</span>'
            '<span class="when">%s</span>'
            '<span class="tags"><span class="tag">1-min &middot; 09:30&ndash;11:00 ET</span>'
            '<span class="done-dot"></span></span></header>'
            '<div class="chartwrap">%s</div>'
            '<div class="legend">'
            '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
            '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> pre-market</span>'
            '<span><b style="color:var(--lvl-hl)">- - HOD/LOD</b> day\'s high/low '
            'as it stood when the setup formed</span></div>'
            '%s'
            '<div class="legend" style="padding-top:0">'
            '<span><b>engine claims:</b> %s</span>'
            '<span><b>at:</b> %s &mdash; %s%s</span></div>'
            '%s%s</article>'
            % (cid, export, idx, c["symbol"], c["day"], svg, off,
               SETUP_LABEL[label], c["level"], LEVEL_BLURB[c["level"]],
               SOURCE_BLURB.get(c["level_how"], ""), q_yes, q_why))


def build(slates):
    parts, n = [], 0
    for si, row in enumerate(slates, 1):
        parts.append('<p class="eyebrow" style="margin:30px 0 10px">'
                     'Slate %d &mdash; three stocks I believe are S</p>' % si)
        for c in row:
            n += 1
            parts.append(render_card(n, c))
    counts = Counter(c["bucket"] for row in slates for c in row)
    lede = ("Every chart here is a day <strong>the engine claims is an S</strong>, graded "
            "on your ladder &mdash; not the legacy letters. Nothing is marked: the "
            "1-minute 09:30&ndash;11:00 session and <strong>your six levels</strong> "
            "(PDH, PDL, PMH, PML, HOD, LOD &mdash; no opening range, it is not one of "
            "yours), and under it the setup the engine says it is and the level it says "
            "it broke. Every card is at one of your six; pivot levels are out, and every "
            "card is a signal the engine actually took, or a chart it refused all "
            "morning &mdash; never a signal it set aside for a different trade. "
            "<strong>You say yes or no</strong>, and if no, why. "
            "84%% rule and OCR are deliberately over-weighted to %d and %d of %d cards "
            "because you said they are probably broken; the %d break-and-retest cards "
            "are the control."
            % (counts["84"], counts["OCR"], n, counts["BR"]))
    footer = ("<h2>When you're done</h2><p>Tap <b>Export</b> at the top, then "
              "<b>Copy all</b> and paste it into the chat &mdash; or <b>Download .jsonl</b>. "
              "Answers save to this browser as you tap, and come back if you close the "
              "page.</p><p><b>One thing about HOD/LOD:</b> they are drawn where they "
              "stood <i>when the setup formed</i>, not at the end of the session, so the "
              "HOD line can sit below later highs on the chart. That is on purpose "
              "&mdash; drawing them off the whole session would be showing you bars the "
              "engine had not seen yet.</p>")
    return probe_page.shell(
        title="OMEN &mdash; three stocks I believe are S",
        eyebrow="OMEN homework &middot; precision, not recall",
        h1="The three stocks I believe are S trades",
        lede=lede, cards_html="".join(parts), footer_html=footer, deck_id=DECK_ID)


def write_manifest(slates, path=OUT_MANIFEST, target_traded=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in slates:
            for c in row:
                r = c["rep"]
                fh.write(json.dumps({
                    "card_id": "%s_%s" % (c["symbol"], c["day"]),
                    "symbol": c["symbol"], "date": c["day"], "deck": DECK_ID,
                    "bucket": c["bucket"],
                    "claimed_setup": card_setup_label(r, c["bucket"]),
                    "claimed_level": c["level"],
                    "claimed_level_source": c["level_how"],
                    "drawn_levels": {k: (round(v, 2) if v is not None else None)
                                     for k, v in c["levels"].items()},
                    "hodlod_anchor_bar": c["setup_i"],
                    # answer key -- deliberately NOT in the HTML. `role` is
                    # derived 1:1 from `traded` (G8.2, research/g82_deck_fix.md)
                    # and is exactly as sensitive -- never render it either.
                    "role": c["role"],
                    "traded_quota_frac": TRADED_QUOTA_FRAC,
                    "bucket_target_traded": target_traded,
                    "sgrade": r.get("sgrade"), "tripped": r.get("tripped"),
                    "confluence": r.get("confluence"),
                    "downgrades": r.get("downgrades"),
                    "legacy_grade": r.get("grade"), "traded": r.get("traded"),
                    "outcome": r.get("out"), "r": r.get("r"),
                    "engine_setup": r.get("setup"), "et": r.get("et"),
                    "level": r.get("level"), "level_name": r.get("level_name"),
                    "level_px": r.get("level_px"), "dir": r.get("dir"),
                    "s_signals_that_day": c["n_s_signals"],
                    "s_setups_that_day": c["setups"],
                    "prefilter": c["prefilter"],
                }, sort_keys=True) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slates", type=int, default=10)
    ap.add_argument("--seed", type=int, default=71)
    ap.add_argument("--traded-quota", type=float, default=TRADED_QUOTA_FRAC,
                    help="target share of each bucket's cards built from the "
                         "engine's own booked trade; the rest are silent-day "
                         "cards. Default matches build_deck.py's 0.5.")
    a = ap.parse_args()

    slates, seen, stats, census, level_census = pick(a.slates, a.seed,
                                                      traded_quota=a.traded_quota)
    cards = [c for row in slates for c in row]
    ids = ["%s_%s" % (c["symbol"], c["day"]) for c in cards]

    assert len(set(ids)) == len(ids), "duplicate card inside the batch"
    repeats = sorted(set(ids) & bd.seen_card_ids(OUT_MANIFEST))
    assert not repeats, "batch repeats a judged/served symbol-day: %s" % repeats
    bad = sorted({c["level"] for c in cards} - set(HIS_SIX))
    assert not bad, "card served on a level Austin does not watch: %s" % bad
    # G8.2 (research/g82_deck_fix.md), fixing G7.7 (research/g77_wrongchart.md):
    # nothing warned when 25 of the 30 served cards turned out to be signals the
    # engine REFUSED to trade or traded something else on the same chart. Every
    # card is now role "traded" (the engine's own booked trade) or role
    # "silent" (the engine booked nothing, all morning) by construction in
    # load_s_days -- this re-derives that from the rows served and refuses to
    # publish a deck where the two disagree.
    realtrade.role_guard(cards, label=DECK_ID)
    target_traded = max(0, min(a.slates, round(a.slates * a.traded_quota)))
    assert target_traded > 0 or a.slates == 0, \
        "stated quota rounds to zero traded cards per bucket -- raise --traded-quota"

    html = build(slates)
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    write_manifest(slates, target_traded=target_traded)

    counts = Counter(c["bucket"] for c in cards)
    roles = Counter(c["role"] for c in cards)
    labels = Counter(card_setup_label(c["rep"], c["bucket"]) for c in cards)
    print()
    print("Wrote %s (%d bytes)" % (OUT_HTML, len(html)))
    print("Wrote %s" % OUT_MANIFEST)
    print("cards=%d in %d slates" % (len(cards), len(slates)))
    print("buckets: %s" % dict(counts))
    print("stated quota: %.0f%% traded per bucket (target %d/%d) -- achieved: %s"
          % (100.0 * a.traded_quota, target_traded, a.slates, dict(roles)))
    for b in BUCKETS:
        s = stats[b]
        print("  %-3s %d/%d cards  (%d of %d S days passed the his-six gate)  "
              "role=%s"
              % (b, s["picked"], s["wanted"], s["eligible"], s["s_days"],
                 s["role_counts"]))
    print("claimed setup labels: %s" % dict(labels))
    print("card level distribution: %s"
          % dict(Counter(c["level"] for c in cards).most_common()))
    print("level read as: %s" % dict(Counter(c["level_how"] for c in cards)))
    print("symbols: %d distinct, max per symbol %d"
          % (len(set(c["symbol"] for c in cards)),
             max(Counter(c["symbol"] for c in cards).values())))
    print("REPEAT CHECK: %d of %d cards collide with the %d judged-or-served "
          "symbol-days -- %s"
          % (len(repeats), len(ids), len(bd.seen_card_ids(OUT_MANIFEST)),
             "PASS" if not repeats else "FAIL"))
    print("  (judged corpus alone: %d symbol-days)" % len(bd.marked_card_ids()))
    print("zero-downgrade (tripped=0) cards: %d of %d"
          % (sum(1 for c in cards if int(c["rep"].get("tripped") or 0) == 0), len(cards)))
    print("legacy grade of the same signals: %s"
          % dict(Counter(c["rep"].get("grade") for c in cards)))
    print("engine actually traded: %d of %d"
          % (sum(1 for c in cards if c["rep"].get("traded")), len(cards)))


if __name__ == "__main__":
    main()
