"""g82_master_homework.py -- one page, seven questions, about fifteen minutes.

Austin, 2026-08-30:

    "a master homework of variety with all the different angles is good --
     doesn't just have to be S-grade accuracy."

So this is not another S deck. It is seven short sections, each one aimed at a
different open question, on one page he can finish on a phone in a sitting:

  1  IS THIS AN S?            8 charts. The control -- the same instrument as the
                              deck he graded last night, built the same way, so
                              everything else on the page has something to be
                              read against.
  2  WHICH SIGNAL?            6 charts that carry TWO plausible setups, each
                              marked with a small labelled dot and nothing else.
                              He picks one, or neither. This is the question
                              research/g77_wrongchart.md proved we had been
                              getting wrong: the card never showed him WHICH
                              signal it was asking about, so a yes could only
                              ever mean "there is a trade on this chart".
  3  WHAT MINUTE?             6 charts, nothing marked, a free-text minute box.
                              Twenty of the thirty cards he graded last night
                              carried a stated minute, and the minute is what
                              made them useful -- it is the only field that says
                              WHICH trade he meant. Asked deliberately this time.
  4  DOES THE HIGHER          6 pairs: the 1-minute morning chart, and the same
     TIMEFRAME AGREE?         symbol's daily chart as it stood at the close
                              BEFORE that morning. Agrees / disagrees / cannot
                              tell. He raised this himself and it has no author:
                              research/g81_htf_thesis.md measured four candidate
                              definitions and all four are ties, so the next move
                              is to ask him which one is his, not to guess again.
  5  IS THERE DISPLACEMENT?   8 charts, yes/no and one line of why. He named
                              displacement in four of nine refusals last night
                              without being asked. research/g81_displacement.md
                              showed the shipped check measures a fat candle
                              while every sentence he and the mentors have said
                              measures distance from the level -- and that on the
                              three cards he refused FOR no displacement, neither
                              implementation trips. Charts here deliberately
                              straddle that boundary.
  6  WHERE IS THE STOP?       6 charts with the entry given and four labelled
                              candidate stop lines drawn -- bottom of the entry
                              candle, the broken level, prior pivot structure,
                              and a wider disaster stop. He taps one, or none.
                              research/g71_stops.md measured 80 of his 114 real
                              stops at the bottom of the entry candle; this tests
                              that against fresh eyes rather than against the
                              same marks it was derived from.
  7  THE MENTOR RULE BALLOT   15 yes/no lines, no charts. Rules Scarface, Jdub,
                              Neto, Lauren, Mamba or Hayden state and Austin
                              never has (research/corpus_sf/mentor_rules.md,
                              the "New" list), quoted in the mentor's own words
                              and ordered by how much each would move the engine
                              -- not by how often it was said, which that file
                              shows does not rank anything (the most-repeated
                              rule in the corpus was said seven times).

NO REPEATS. Every chart card is a symbol-day he has never been shown -- judged in
any mark corpus OR served in any deck, `build_deck.seen_card_ids()`, which is the
only correct test. Being served counts; that is the guarantee's third failure
mode. No symbol-day appears twice on this page either, and no symbol more than
twice in total.

THE ANSWER KEY STAYS OFF THE PAGE. What the engine did, what it graded, whether
it traded, which separation the displacement check measured, which higher-
timeframe definition agrees -- all of it goes to the manifest and none of it into
the HTML. `main()` re-reads the rendered page and fails the build if any of it
leaked.

    python research/g82_master_homework.py [--seed 82]

Output:
    research/probes/omen-master-homework.html
    research/probes/omen-master-homework-manifest.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd                    # noqa: E402  the no-repeat guarantee
import g71_homework_build as hb            # noqa: E402  the S-card construction
import g77_realtrade_pick as realtrade     # noqa: E402  "which signal is this about"
import g81_displacement as disp            # noqa: E402  separation, not body size
import g81_htf_thesis as htf               # noqa: E402  the four HTF candidates
import probe_chart                         # noqa: E402
import probe_page                          # noqa: E402
import t21_card_filter as card_filter      # noqa: E402  the shipped deck pre-filter
import signal_runner as sr                 # noqa: E402  pivot_levels, BAR_EXTREME_FRAC

BOOK = os.path.join(HERE, "bt2y_trades.json")
HTF_CACHE = os.path.join(HERE, "g81_htf_cache.json")
OUT_DIR = os.path.join(HERE, "probes")
OUT_HTML = os.path.join(OUT_DIR, "omen-master-homework.html")
OUT_MANIFEST = os.path.join(OUT_DIR, "omen-master-homework-manifest.jsonl")
DECK_ID = "omen-master-homework"

# Austin's six, named by him 2026-08-29. Same set g71_homework_build serves on.
HIS_SIX = hb.HIS_SIX

MAX_PER_SYMBOL = 2

# How many charts each section gets. Fifteen minutes on a phone is the budget.
N_S = 8            # 1  is this an S
N_WHICH = 6        # 2  which signal on this chart
N_MINUTE = 6       # 3  what minute would you enter
N_HTF = 6          # 4  does the higher timeframe agree
N_DISP = 8         # 5  is there displacement
N_STOP = 6         # 6  where is the stop

# Section 4's daily chart. It ends on the session BEFORE the morning being
# judged -- the day's own daily candle closes at 16:00 and would show him how the
# morning turned out, which is the answer, not the question.
DAILY_SESSIONS = 60

# Section 6's fourth candidate. "you pick a disaster stop" -- research/g71_stops.md
# put the shipped book's 90th-percentile stop at 0.405% of entry and used 0.60%
# of price as the disaster ceiling, so 0.60% is the widest stop that rig calls
# tradeable. It is a stated constant, not a fitted one.
DISASTER_PCT = 0.0060

# Section 5's separation buckets, in average candles past the level
# (research/g81_displacement.md). The boundary bucket is the one the argument is
# actually about, so it gets the most cards.
DISP_BUCKETS = [("tiny", 0.0, 0.5, 2),
                ("boundary", 0.75, 1.25, 3),
                ("clear", 1.25, 2.0, 1),
                ("big", 2.0, 99.0, 2)]

SETUP_WORDS = {"break_and_retest": "break and retest",
               "one_candle_rule": "one candle rule",
               "reentry_84_rule": "84% rule re-entry"}
DIR_WORDS = {"call": "LONG", "put": "SHORT"}


# ---------------------------------------------------------------- the ballot
#
# research/corpus_sf/mentor_rules.md, the "New" list -- 15 things a mentor says
# and Austin never has. Order is that file's own: by how much the rule would move
# the engine, then by how often it was said. Quotes are the mentor's words.

MENTOR_BALLOT = [
    dict(who="Neto", said=3,
         quote="the <b>Retest</b> on a level is <b>never to the penny</b>, is always "
               "close to the line",
         change="A retest touch has no stated tolerance in the code. Your 25%-of-the-"
                "previous-candle unit already governs the entry trigger, the 84% "
                "reclaim and stop slippage. This would be its fourth use, and it is "
                "nearly free."),
    dict(who="Scarface", said=2,
         quote="the reclaim entry is stopping us from trading chop&hellip; we should "
               "only trade a <b>strong closure above that level</b>, anything below "
               "is chop",
         change="A different anchor for the level-not-respected downgrade &mdash; your "
                "highest-tripping one, which has failed three implementations. Chop "
                "measured by the strength of the breaking close, not by the bars "
                "after it."),
    dict(who="Neto", said=7,
         quote="a break, then displacement, then the retest, and lastly <b>strong "
               "reaction on the key level</b> &mdash; wait for how price <b>reacts</b> "
               "to your interest levels",
         change="Adds a fourth required element after the retest. The engine enters "
                "ON the retest; this would make it wait for the reaction to it."),
    dict(who="Scarface", said=4,
         quote="Ideally if you want to take a trade intraday you <b>need this to break "
               "to hod or lod</b>",
         change="Target availability as an ENTRY gate. This is your own line &mdash; "
                "&ldquo;if there are no other levels to target it is harder to "
                "trade&rdquo; &mdash; stated as a hard precondition instead of a "
                "preference."),
    dict(who="Neto", said=3,
         quote="backtest and define if it works better for your ticker on the Pre "
               "Market levels, Previous Day levels, 1min/5min ORB",
         change="Your six levels are closed and applied to every symbol equally. This "
                "says the WEIGHTING among them should be per-ticker. Cheap to measure."),
    dict(who="Neto", said=2,
         quote="If reward potential is smaller, I'll usually <b>secure profits more "
               "aggressively</b>",
         change="Unparks your own scale-out question &mdash; &ldquo;30 percent is when "
                "better chance stock runs, 50 for choppier, we must identify "
                "this&rdquo;. He names the discriminator: how much reward is available "
                "at entry."),
    dict(who="Lauren, Mamba and Jdub", said=13,
         quote="weekly, daily, 4H to identify the overall trend, key levels and "
               "liquidity zones &mdash; it needs to be paired with market conditions "
               "and HTF trend",
         change="You said &ldquo;you'll need to tell me what that is then&rdquo;. Three "
                "mentors answer. Section 4 above is the measured version of this "
                "question; this line is whether it becomes a rule at all."),
    dict(who="Hayden", said=3,
         quote="Highest probability trades are always generally <b>outside of previous "
               "days ranges</b> or above/below key levels",
         change="A prior-day-range containment filter. Computable at 9:29, and it joins "
                "the premarket filter that already ships."),
    dict(who="Neto", said=3,
         quote="<b>hammer or inverted hammer</b> candles with long wicks inside our key "
               "level but <b>bodies respecting it</b>",
         change="A named shape for the retest candle. You have said trends respect "
                "wicky candles better; you never named the shape."),
    dict(who="Mamba", said=2,
         quote="I use <b>op</b> (the opening price) when there's no level or the level "
               "is too far, so it gives me a reference point",
         change="A concrete answer to &ldquo;find other targets&rdquo;. It would be a "
                "seventh reference and your six are closed &mdash; so it is a ballot "
                "line, not a change."),
    dict(who="Neto and Scarface", said=7,
         quote="I only trade 4 names on a consistent basis &mdash; stick to one ticker "
               "one setup for a decent period",
         change="You flagged the book as unbalanced (one symbol is 104 of 1,017 rows). "
                "Three mentors say concentration is the point, not the bug."),
    dict(who="Jdub and Neto", said=9,
         quote="We <b>always take 1 OTM</b> or the contracts with the most volume",
         change="The options skin has no strike rule at all. You want reports led in "
                "dollars; this is the missing parameter that makes those dollars real."),
    dict(who="Neto", said=2,
         quote="predefined trading hours, a maximum number of trades per day, a "
               "<b>mandatory break after a loss</b>, only trading predefined setups",
         change="A third option in the halt question. Not &ldquo;stop at two "
                "losses&rdquo; and not &ldquo;trade until green&rdquo; &mdash; pause "
                "after ONE."),
    dict(who="Jdub", said=3,
         quote="On A+ setups I will <b>take starters</b> sometimes as I don't want to "
               "miss out on the move, so I don't mind if I don't have the greatest entry",
         change="Scaling IN. The engine has scale-out only; a starter position has "
                "never been on the board."),
    dict(who="Neto", said=2,
         quote="a wider stop-loss &mdash; usually <b>18&ndash;25% of the contract "
               "premium</b> at entry",
         change="A premium-side bound on the stop, feeding your &ldquo;won't get killed "
                "by fills or too tight risk-reward&rdquo; constraint. Your stop is on "
                "the underlying; this caps what it may cost in the contract."),
]


# ------------------------------------------------------------------- helpers

def bars_of(candles):
    """probe/downgrade bar dicts from omen_bot Candles."""
    return [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
            for c in candles]


def mins(et):
    return int(et[:2]) * 60 + int(et[3:5])


def tol_unit(candles, i):
    """One tolerance unit: 25% of the previous candle's range."""
    prev = candles[max(0, i - 1)]
    return max(sr.BAR_EXTREME_FRAC * (prev.high - prev.low), 0.005)


def static_six(sym, day):
    """The four of his six that are fixed before the bell. HOD/LOD are running
    levels and need an anchor bar, so they are added only where a card has one."""
    pdh, pdl, pmh, pml = hb.static_levels(sym, day)
    return {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml}


def six_at(sym, day, candles, i):
    """All six, with HOD/LOD as they stood strictly BEFORE bar i."""
    return hb.levels_for(sym, day, candles, i)


def round_levels(lv):
    return {k: (round(v, 2) if v is not None else None) for k, v in lv.items()}


def daily_candles(sym, day, n=DAILY_SESSIONS):
    """Daily OHLC built from the 1-minute archive, regular hours only, for the n
    sessions ending the day BEFORE `day`.

    Ending the day before is the whole point: the card's own daily candle closes
    at 16:00 and would show him how the morning he is judging turned out.
    """
    d = os.path.join(ROOT, "data_archive", sym)
    if not os.path.isdir(d):
        return []
    days = sorted(f[:-4] for f in os.listdir(d)
                  if f.endswith(".csv") and f[:-4] < day)[-n:]
    out = []
    for dd in days:
        c = bd.rth_candles(sym, dd)
        if not c:
            continue
        out.append({"t": dd, "o": round(c[0].open, 2),
                    "h": round(max(x.high for x in c), 2),
                    "l": round(min(x.low for x in c), 2),
                    "c": round(c[-1].close, 2),
                    "v": int(sum(x.volume for x in c))})
    return out


class Pool:
    """The no-repeat bookkeeping, shared by every section.

    `seen` is judged-or-served, from build_deck. `used` grows as this page picks
    cards, so no symbol-day is asked about twice here either. Both rejection
    reasons are counted separately, because "how many candidates did the
    no-repeat check reject" is a number this build has to report.
    """

    def __init__(self, seen):
        self.seen = seen
        self.used = set()
        self.per_symbol = Counter()
        self.rejected_seen = set()
        self.rejected_reused = set()
        self.rejected_symbol_cap = 0
        self.rejected_prefilter = 0
        self.rejected_thin = 0
        self.considered = set()
        self.considered_by = {}
        self.per_section_symbol = set()

    def note_candidates(self, section, ids):
        """Every symbol-day a section found structurally suitable, BEFORE the
        no-repeat check. How many of these the guarantee turns away is the number
        this build has to report, and it is per section: section 3 will take any
        morning, section 6 needs four separable stop prices."""
        ids = set(ids)
        self.considered_by[section] = ids
        self.considered |= ids

    def take(self, sym, day, et, section=None):
        """(candles, prefilter features) if this symbol-day may be served, else None.

        Two symbol caps: at most MAX_PER_SYMBOL cards on the whole page, and at
        most one inside any single section -- six stop cards on three symbols
        reads as a smaller sample than it is.
        """
        cid = "%s_%s" % (sym, day)
        if cid in self.seen:
            self.rejected_seen.add(cid)
            return None
        if cid in self.used:
            self.rejected_reused.add(cid)
            return None
        if self.per_symbol[sym] >= MAX_PER_SYMBOL                 or (section and (section, sym) in self.per_section_symbol):
            self.rejected_symbol_cap += 1
            return None
        candles = bd.session_candles(sym, day)
        if len(candles) < 60:
            self.rejected_thin += 1
            return None
        feat = card_filter.features(sym, day, et)
        if feat is None:
            self.rejected_prefilter += 1
            return None
        ok, _why = card_filter.verdict(feat)
        if not ok:
            self.rejected_prefilter += 1
            return None
        return candles, feat

    def commit(self, sym, day, section=None):
        self.used.add("%s_%s" % (sym, day))
        self.per_symbol[sym] += 1
        if section:
            self.per_section_symbol.add((section, sym))


# ------------------------------------------------------------------ the book

def load_book():
    with open(BOOK, encoding="utf-8") as fh:
        book = json.load(fh)
    byday = defaultdict(list)
    for r in book["trades"]:
        byday[(r["sym"], r["day"])].append(r)
    return book, byday


def usable(r, max_bar=90):
    """A row this page can build a chart card from: it has a minute, an entry bar
    inside the 09:30-11:00 window, and an entry price."""
    return bool(r.get("et")) and bool(r.get("entry_i")) \
        and r["entry_i"] < max_bar and r.get("entry") is not None


# ------------------------------------------------------------------ pickers

_S_DAYS = [None]


def s_days_cached():
    """`hb.load_s_days()` is half a minute; a rebuild retry should not pay it twice."""
    if _S_DAYS[0] is None:
        _S_DAYS[0] = hb.load_s_days()
    return _S_DAYS[0]


def pick_is_s(pool, rng, n=N_S):
    """Section 1. The control: exactly the construction of last night's deck --
    an S on his ladder, at one of his six levels, and either the engine's own
    booked trade for that session or a chart it refused all morning. Half and
    half, the same quota that deck states."""
    days, _n_s_rows, _census, _levels = s_days_cached()
    pool.note_candidates("is_this_an_s", ["%s_%s" % k for k in days])
    by_role = defaultdict(list)
    for (sym, day), v in days.items():
        by_role[v["role"]].append((sym, day, v))
    for role in ("traded", "silent"):
        rng.shuffle(by_role[role])
        # Belief strength first, same as the deck: a zero-downgrade S is a
        # stronger claim than one that reached S on the confluence bonus.
        by_role[role].sort(key=lambda t: int(t[2]["rep"].get("tripped") or 0))

    # The deck he graded last night ran slates of three -- one 84% rule, one
    # one-candle rule, one break-and-retest -- because he asked for the first two
    # to be over-weighted ("those are probably broken"), with break-and-retest as
    # the control arm. Eight cards cannot hold ten slates, so the shape is kept
    # rather than the ratio: every arm present, break-and-retest carrying the
    # rest, and still half the engine's own trades and half mornings it refused.
    # A slot whose arm is exhausted falls through to break-and-retest, which is
    # the only arm with a deep pool (84% has four traded days in two years).
    slots = [("84", None), ("OCR", "traded"), ("OCR", "silent"),
             ("BR", "traded"), ("BR", "traded"), ("BR", "traded"),
             ("BR", "silent"), ("BR", "silent")][:n]
    by_bucket_role = defaultdict(list)
    for role in ("traded", "silent"):
        for sym, day, v in by_role[role]:
            by_bucket_role[(v["bucket"], role)].append((sym, day, v))

    out = []
    taken_ids = set()
    for bucket, role in slots:
        roles = (role,) if role else ("silent", "traded")
        pools = [by_bucket_role[(bucket, rr)] for rr in roles]
        pools += [by_bucket_role[("BR", rr)] for rr in (roles if role else ("traded",))]
        got = False
        for cand in pools:
            if got:
                break
            for sym, day, v in cand:
                if "%s_%s" % (sym, day) in taken_ids:
                    continue
                r = v["rep"]
                if not usable(r):
                    continue
                fetched = pool.take(sym, day, r.get("et"), "is_this_an_s")
                if not fetched:
                    continue
                candles, feat = fetched
                if r["entry_i"] >= len(candles):
                    continue
                lv = six_at(sym, day, candles, r["entry_i"])
                if lv.get(v["level"].lower()) is None:
                    continue
                pool.commit(sym, day, "is_this_an_s")
                taken_ids.add("%s_%s" % (sym, day))
                out.append({"section": "is_this_an_s", "symbol": sym, "day": day,
                            "candles": candles, "levels": lv, "rep": r,
                            "level": v["level"], "level_how": v["level_how"],
                            "anchor_i": r["entry_i"], "role": v["role"],
                            "prefilter": feat["reach_r"],
                            "bucket": v["bucket"]})
                got = True
                break
    return out


def pick_which_signal(pool, rng, byday, n=N_WHICH):
    """Section 2. Two plausible setups on one chart.

    One of them is the trade the engine actually booked that session; the other
    is a signal the engine graded S on the same chart, at least five minutes
    away, and a different setup or a different direction. Which one gets the
    letter A is decided by a coin, not by time or by which one the engine took.
    """
    cands = []
    for (sym, day), rs in byday.items():
        t = realtrade.day_trade(rs)
        if t is None or not usable(t):
            continue
        alts = [r for r in rs
                if r.get("sgrade") == "S" and usable(r)
                and abs(mins(r["et"]) - mins(t["et"])) >= 5
                and (r["setup"] != t["setup"] or r["dir"] != t["dir"])]
        if not alts:
            continue
        # The clearest card is the one where the two disagree most: opposite
        # direction first, then the furthest apart in time.
        alts.sort(key=lambda r: (r["dir"] == t["dir"],
                                 -abs(mins(r["et"]) - mins(t["et"]))))
        cands.append((sym, day, t, alts[0]))
    pool.note_candidates("which_signal", ["%s_%s" % (c[0], c[1]) for c in cands])
    rng.shuffle(cands)
    cands.sort(key=lambda c: c[3]["dir"] == c[2]["dir"])   # opposite pairs first

    out = []
    for sym, day, t, alt in cands:
        if len(out) >= n:
            break
        got = pool.take(sym, day, t.get("et"), "which_signal")
        if not got:
            continue
        candles, feat = got
        if max(t["entry_i"], alt["entry_i"]) >= len(candles):
            continue
        pair = [t, alt]
        rng.shuffle(pair)
        pool.commit(sym, day, "which_signal")
        out.append({"section": "which_signal", "symbol": sym, "day": day,
                    "candles": candles, "levels": static_six(sym, day),
                    "pair": pair, "engine_trade_et": t["et"],
                    "prefilter": feat["reach_r"]})
    return out


def pick_minute(pool, rng, byday, n=N_MINUTE):
    """Section 3. Nothing marked, and only the four levels that are fixed before
    the bell -- HOD and LOD are drawn where they stood when a setup formed, and
    on a card that asks him for the minute that line would be the answer.

    Half are sessions the engine traded, half are sessions it refused outright:
    a minute on a refused chart is a pure miss.
    """
    traded, silent = [], []
    for (sym, day), rs in byday.items():
        t = realtrade.day_trade(rs)
        if t is not None and usable(t):
            traded.append((sym, day, t))
        elif t is None:
            silent.append((sym, day, None))
    pool.note_candidates("what_minute",
                         ["%s_%s" % (s_, d) for s_, d, _t in traded + silent])
    rng.shuffle(traded)
    rng.shuffle(silent)

    out = []
    for group, want in ((traded, n // 2), (silent, n - n // 2)):
        got_n = 0
        for sym, day, t in group:
            if got_n >= want:
                break
            got = pool.take(sym, day, t.get("et") if t else None, "what_minute")
            if not got:
                continue
            candles, feat = got
            pool.commit(sym, day, "what_minute")
            got_n += 1
            out.append({"section": "what_minute", "symbol": sym, "day": day,
                        "candles": candles, "levels": static_six(sym, day),
                        "rep": t, "role": "traded" if t else "silent",
                        "prefilter": feat["reach_r"]})
    rng.shuffle(out)
    return out


def pick_htf(pool, rng, byday, blob, n=N_HTF):
    """Section 4. Pairs that straddle the higher-timeframe candidates.

    Two cards where the daily read agrees with the trade and everything else
    lines up, two where the daily read disagrees and so does the hourly, and two
    where the two split. Nothing here is applied -- the four definitions in
    research/g81_htf_thesis.md are all ties, so this is elicitation, not a test.
    """
    have_days = set(blob.get("index", {}))
    groups = {"all_agree": [], "all_against": [], "split": []}
    for (sym, day), rs in byday.items():
        if day not in have_days:
            continue
        t = realtrade.day_trade(rs)
        if t is None or not usable(t):
            continue
        f = htf.row_features(blob, t)
        d = htf.score("daily_bias", f)
        h = htf.score("hourly_bias_incumbent", f)
        stack = htf.score("alignment_stack", f)
        if d > 0 and h > 0 and stack >= 4:
            g = "all_agree"
        elif d < 0 and h < 0 and stack <= 1:
            g = "all_against"
        elif d * h < 0:
            g = "split"
        else:
            continue
        groups[g].append((sym, day, t, f, {"daily": d, "hourly": h, "stack": stack}))
    pool.note_candidates("htf_agree", ["%s_%s" % (c[0], c[1])
                                       for g in groups for c in groups[g]])
    for g in groups:
        rng.shuffle(groups[g])

    per = {"all_agree": 2, "all_against": 2, "split": n - 4}
    out = []
    for g, want in per.items():
        got_n = 0
        for sym, day, t, f, sc in groups[g]:
            if got_n >= want:
                break
            got = pool.take(sym, day, t.get("et"), "htf_agree")
            if not got:
                continue
            candles, feat = got
            if t["entry_i"] >= len(candles):
                continue
            dcs = daily_candles(sym, day)
            if len(dcs) < 25:
                continue
            pool.commit(sym, day, "htf_agree")
            got_n += 1
            out.append({"section": "htf_agree", "symbol": sym, "day": day,
                        "candles": candles,
                        "levels": six_at(sym, day, candles, t["entry_i"]),
                        "rep": t, "daily": dcs, "htf_group": g, "htf_score": sc,
                        "anchor_i": t["entry_i"], "prefilter": feat["reach_r"]})
    rng.shuffle(out)
    return out


def pick_displacement(pool, rng, byday, n=N_DISP):
    """Section 5. Charts that straddle the separation boundary.

    Separation is measured by research/g81_displacement.separation_atr -- the
    furthest price got past the level between the break and the entry bar, in
    average candles. That is Neto's "actual separation from the candles to the
    key level" and it is what Austin's own sentences describe. The shipped check
    measures the break candle's BODY instead; where the two disagree is exactly
    where his answer is worth the most, so the buckets are picked on separation
    and the shipped verdict is recorded beside it, never shown.
    """
    buckets = defaultdict(list)
    for (sym, day), rs in byday.items():
        t = realtrade.day_trade(rs)
        if t is None or not usable(t) or t.get("level_px") is None:
            continue
        if t.get("level_name") not in HIS_SIX:
            continue        # the card names the level, so it must be one of his
        candles = bd.session_candles(sym, day)
        if len(candles) < 60 or t["entry_i"] >= len(candles):
            continue
        sep, _br = disp.separation_atr(bars_of(candles), t["entry_i"],
                                       t["level_px"], t["side"] == "L")
        if sep is None:
            continue
        for name, lo, hi, _want in DISP_BUCKETS:
            if lo <= sep < hi:
                buckets[name].append((sym, day, t, sep, candles))
                break
    pool.note_candidates("displacement", ["%s_%s" % (c[0], c[1])
                                          for k in buckets for c in buckets[k]])
    for k in buckets:
        rng.shuffle(buckets[k])
        # Inside a bucket, prefer the cards where the two definitions DISAGREE --
        # the shipped body-size check says displaced and the separation reading
        # says it never left the level, or the reverse. Those are the cards his
        # eye actually settles. Note the test has to be per card, not "shipped
        # trips": in the tiny-separation bucket a shipped trip is agreement.
        # Interleaved, not sorted: a page of nothing but disagreements has no
        # case where both definitions already agree to read his answer against.
        dis = [c for c in buckets[k] if _definitions_disagree(c[2], c[3])]
        agr = [c for c in buckets[k] if not _definitions_disagree(c[2], c[3])]
        mixed = []
        while dis or agr:
            if dis:
                mixed.append(dis.pop(0))
            if agr:
                mixed.append(agr.pop(0))
        buckets[k] = mixed

    out = []
    for name, lo, hi, want in DISP_BUCKETS:
        got_n = 0
        for sym, day, t, sep, candles in buckets[name]:
            if got_n >= want or len(out) >= n:
                break
            got = pool.take(sym, day, t.get("et"), "displacement")
            if not got:
                continue
            _candles, feat = got
            pool.commit(sym, day, "displacement")
            got_n += 1
            out.append({"section": "displacement", "symbol": sym, "day": day,
                        "candles": candles,
                        "levels": six_at(sym, day, candles, t["entry_i"]),
                        "rep": t, "sep_atr": round(sep, 3), "sep_bucket": name,
                        "shipped_trips": _shipped_trips(t),
                        "anchor_i": t["entry_i"], "prefilter": feat["reach_r"]})
    rng.shuffle(out)
    return out


def _shipped_trips(r):
    return "no_displacement" in (r.get("downgrades") or [])


def _definitions_disagree(r, sep):
    """True when the shipped body-size check and the separation reading land on
    opposite sides. Separation calls it displaced at or above one average candle
    (research/g81_displacement.py::DISP_SEP_ATR)."""
    return (sep >= disp.DISP_SEP_ATR) == _shipped_trips(r)


def stop_candidates(candles, i, is_long, level_px):
    """The four families, at the entry bar. None where a family has no candidate.

    Names are his: "level, bottom of candle entered on, pivot structure" and
    "you pick a disaster stop". Pivots come from signal_runner.pivot_levels --
    the engine's own swing definition, including its no-lookahead rule -- and are
    not reimplemented here.
    """
    bar = candles[i]
    close = bar.close
    out = {"candle": bar.low if is_long else bar.high,
           "level": level_px,
           "pivot": None,
           "disaster": close * (1 - DISASTER_PCT) if is_long
           else close * (1 + DISASTER_PCT)}
    ps = sr.pivot_levels(candles, as_of=i, lookback=sr.PIVOT_LOOKBACK)
    want = "low" if is_long else "high"
    px = [p["price"] for p in ps if p["kind"] == want
          and ((p["price"] < close) if is_long else (p["price"] > close))]
    if px:
        out["pivot"] = max(px) if is_long else min(px)
    return out


def pick_stop(pool, rng, byday, n=N_STOP):
    """Section 6. Four labelled candidate stop lines, one tap.

    A card is only served when all four families produce a price, every one of
    them sits on the losing side of the entry bar's close, and no two are inside
    one tolerance unit of each other -- otherwise two of the four letters are the
    same answer and the tap means nothing.
    """
    cands = []
    for (sym, day), rs in byday.items():
        t = realtrade.day_trade(rs)
        if t is None or not usable(t) or t.get("level_px") is None:
            continue
        candles = bd.session_candles(sym, day)
        if len(candles) < 60 or t["entry_i"] >= len(candles):
            continue
        i = t["entry_i"]
        is_long = t["side"] == "L"
        c = stop_candidates(candles, i, is_long, t["level_px"])
        if any(v is None for v in c.values()):
            continue
        # The reference is the ENTRY PRICE, not the bar's close. A fill can land
        # at the level, and a "stop" drawn on the wrong side of the price he was
        # filled at is not a stop -- the first render of this section put one
        # candidate above a long's entry and it read as a bug.
        ref = t["entry"]
        if not all((v < ref) if is_long else (v > ref) for v in c.values()):
            continue
        vals = sorted(list(c.values()) + [ref])
        if min(b - a for a, b in zip(vals, vals[1:])) <= tol_unit(candles, i):
            continue
        cands.append((sym, day, t, c, candles))
    pool.note_candidates("where_is_the_stop", ["%s_%s" % (c[0], c[1]) for c in cands])
    rng.shuffle(cands)

    out = []
    for sym, day, t, c, candles in cands:
        if len(out) >= n:
            break
        got = pool.take(sym, day, t.get("et"), "where_is_the_stop")
        if not got:
            continue
        _candles, feat = got
        families = list(c.items())
        rng.shuffle(families)          # the letter carries no tell about family
        pool.commit(sym, day, "where_is_the_stop")
        out.append({"section": "where_is_the_stop", "symbol": sym, "day": day,
                    "candles": candles,
                    "levels": six_at(sym, day, candles, t["entry_i"]),
                    "rep": t, "families": families,
                    "anchor_i": t["entry_i"], "prefilter": feat["reach_r"]})
    return out


# ---------------------------------------------------------------- rendering

LEGEND_SIX = ('<div class="legend">'
              '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
              '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> pre-market</span>'
              '<span><b style="color:var(--lvl-hl)">- - HOD/LOD</b> the day\'s high '
              'and low as they stood when the setup formed</span></div>')

LEGEND_FOUR = ('<div class="legend">'
               '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
               '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> pre-market</span>'
               '<span>no high-of-day or low-of-day line here &mdash; it is drawn where '
               'a setup formed, and on this card that would be the answer</span></div>')


def card_shell(cid, section, idx, symbol, day, tag, chart_html, meta_html,
               questions, export):
    return ('<article class="card" data-cid="%s" data-section="%s" '
            'data-export="%s" data-done="0">'
            '<header><span class="idx">%02d</span><span class="tick">%s</span>'
            '<span class="when">%s</span><span class="tags">'
            '<span class="tag">%s</span><span class="done-dot"></span></span></header>'
            '%s%s%s</article>'
            % (cid, section, export, idx, symbol, day, tag,
               chart_html, meta_html, questions))


def export_blob(d):
    return json.dumps(d, sort_keys=True).replace('"', "&quot;")


def chart_of(c, marks=None, dots=None, hlines=None, label=""):
    lv = round_levels(c["levels"])
    return probe_chart.render([bd.candle_dict(x) for x in c["candles"]], lv,
                              marks=marks or [], dots=dots, hlines=hlines,
                              label=label or "%s %s 1-minute 09:30-11:00"
                              % (c["symbol"], c["day"]))


def render_is_s(idx, c):
    cid = "s1_%s_%s" % (c["symbol"], c["day"])
    label = hb.card_setup_label(c["rep"], c["bucket"])
    svg = chart_of(c)
    off = hb.offchart_note(svg, round_levels(c["levels"]), c["candles"])
    meta = (LEGEND_SIX + off +
            '<div class="legend" style="padding-top:0">'
            '<span><b>engine claims:</b> %s</span>'
            '<span><b>at:</b> %s &mdash; %s%s</span></div>'
            % (hb.SETUP_LABEL[label], c["level"], hb.LEVEL_BLURB[c["level"]],
               hb.SOURCE_BLURB.get(c["level_how"], "")))
    q = probe_page.question(
        "is_s", "Is this an S trade?",
        "Nothing on this chart is marked &mdash; the timeframe and your six levels "
        "are all there is.",
        [("yes", "YES &mdash; this is an S"), ("no", "NO &mdash; not an S")],
        required=True,
        note_placeholder="if yes: anything you'd mark here (entry, stop, level) "
                         "&mdash; optional")
    q += probe_page.question(
        "why_not", "If no &mdash; why not?",
        "Pick every one that applies. Skip this if you said yes.",
        hb.NO_REASONS, multi=True, required=False, tone="veto",
        note_placeholder="in your own words (optional)")
    return card_shell(cid, "is_this_an_s", idx, c["symbol"], c["day"],
                      "1-min &middot; 09:30&ndash;11:00 ET", '<div class="chartwrap">%s</div>' % svg,
                      meta, q, export_blob({"section": "is_this_an_s",
                                            "symbol": c["symbol"], "date": c["day"],
                                            "claimed_setup": label,
                                            "claimed_level": c["level"]}))


def render_which(idx, c):
    cid = "s2_%s_%s" % (c["symbol"], c["day"])
    letters = ["A", "B"]
    dots = [{"i": r["entry_i"], "price": r["entry"], "label": letters[k]}
            for k, r in enumerate(c["pair"])]
    svg = chart_of(c, dots=dots)
    meta = (LEGEND_FOUR +
            '<div class="legend" style="padding-top:0"><span><b>two setups on this '
            'chart.</b> The dots say WHERE and WHEN only &mdash; no entry line, no '
            'stop, no direction. A is at %s, B is at %s.</span></div>'
            % (c["pair"][0]["et"], c["pair"][1]["et"]))
    q = probe_page.question(
        "which_signal", "Which one is the trade?",
        "One of them, or neither.",
        [("A", "A &mdash; %s" % c["pair"][0]["et"]),
         ("B", "B &mdash; %s" % c["pair"][1]["et"]),
         ("neither", "NEITHER &mdash; no trade on this chart")],
        required=True,
        note_placeholder="which way, and why that one and not the other &mdash; optional")
    return card_shell(cid, "which_signal", idx, c["symbol"], c["day"],
                      "two marked bars", '<div class="chartwrap">%s</div>' % svg,
                      meta, q, export_blob({"section": "which_signal",
                                            "symbol": c["symbol"], "date": c["day"],
                                            "dot_A_et": c["pair"][0]["et"],
                                            "dot_B_et": c["pair"][1]["et"]}))


def render_minute(idx, c):
    cid = "s3_%s_%s" % (c["symbol"], c["day"])
    svg = chart_of(c)
    meta = (LEGEND_FOUR +
            '<div class="legend" style="padding-top:0"><span>Nothing is marked and '
            'nothing is claimed. Just the morning.</span></div>')
    q = probe_page.question(
        "entry_minute", "What minute would you enter, and which way?",
        "Type the minute in the box &mdash; 9:43, 10:07. If there is no trade here, "
        "say so and leave the box empty.",
        [("long", "LONG"), ("short", "SHORT"),
         ("none", "NO TRADE &mdash; I'd sit this one out")],
        required=True,
        note_placeholder="the minute, e.g. 9:43 &mdash; and the level, if you want")
    return card_shell(cid, "what_minute", idx, c["symbol"], c["day"],
                      "nothing marked", '<div class="chartwrap">%s</div>' % svg,
                      meta, q, export_blob({"section": "what_minute",
                                            "symbol": c["symbol"], "date": c["day"]}))


def render_htf(idx, c):
    cid = "s4_%s_%s" % (c["symbol"], c["day"])
    r = c["rep"]
    dots = [{"i": r["entry_i"], "price": r["entry"],
             "label": "%s %s" % (DIR_WORDS.get(r["dir"], ""), r["et"])}]
    svg = chart_of(c, dots=dots)
    dsvg = probe_chart.render(
        c["daily"], {},
        # Labelled on the plot: the daily pane is half-width beside the morning
        # chart and a right-gutter label runs off the card.
        hlines=[{"price": c["daily"][-1]["c"], "label": "last close",
                 "cls": "dclose", "at": max(6, len(c["daily"]) // 5)}],
        label="%s daily, the %d sessions before this morning"
              % (c["symbol"], len(c["daily"])),
        xfmt=lambda t: t[5:10])
    meta = ('<div class="legend"><span><b>left / top:</b> the morning, with the '
            'setup marked</span><span><b>right / below:</b> the same symbol\'s '
            '<b>daily</b> chart, ending at the close <b>before</b> that morning '
            '&mdash; nothing on it knows how the day went</span></div>'
            '<div class="legend" style="padding-top:0">'
            '<span><b>the setup:</b> %s, %s, at %s</span></div>'
            % (DIR_WORDS.get(r["dir"], "?"),
               SETUP_WORDS.get(r["setup"], r["setup"]), r["et"]))
    q = probe_page.question(
        "htf", "Does the higher timeframe agree with that setup?",
        "Your call on the daily chart beside it.",
        [("agrees", "AGREES"), ("disagrees", "DISAGREES"),
         ("cannot_tell", "CAN'T TELL")],
        required=True,
        note_placeholder="what you looked at to decide &mdash; and would it change the "
                         "trade? (optional)")
    chart = ('<div class="pair"><div class="pane">%s</div>'
             '<div class="pane">%s</div></div>' % (svg, dsvg))
    return card_shell(cid, "htf_agree", idx, c["symbol"], c["day"],
                      "1-min + daily", '<div class="chartwrap">%s</div>' % chart,
                      meta, q, export_blob({"section": "htf_agree",
                                            "symbol": c["symbol"], "date": c["day"],
                                            "setup_et": r["et"],
                                            "setup_dir": DIR_WORDS.get(r["dir"], "")}))


def render_disp(idx, c):
    cid = "s5_%s_%s" % (c["symbol"], c["day"])
    r = c["rep"]
    dots = [{"i": r["entry_i"], "price": r["entry"], "label": r["et"]}]
    svg = chart_of(c, dots=dots)
    off = hb.offchart_note(svg, round_levels(c["levels"]), c["candles"])
    meta = (LEGEND_SIX + off +
            '<div class="legend" style="padding-top:0">'
            '<span><b>the setup:</b> %s at %s</span>'
            '<span><b>the level it broke:</b> %s &mdash; %s</span></div>'
            % (DIR_WORDS.get(r["dir"], "?"), r["et"], r["level_name"],
               hb.LEVEL_BLURB.get(r["level_name"], "")))
    q = probe_page.question(
        "displacement", "Is there displacement here?",
        "Yes or no, then one line on what you measured it from.",
        [("yes", "YES &mdash; it displaced"), ("no", "NO &mdash; no displacement"),
         ("cannot_tell", "CAN'T TELL")],
        required=True,
        note_placeholder="displacement from WHAT &mdash; the level, the candles it came "
                         "from, something else?")
    return card_shell(cid, "displacement", idx, c["symbol"], c["day"],
                      "one marked bar", '<div class="chartwrap">%s</div>' % svg,
                      meta, q, export_blob({"section": "displacement",
                                            "symbol": c["symbol"], "date": c["day"],
                                            "setup_et": r["et"],
                                            "level": r["level_name"]}))


STOP_LETTERS = ["A", "B", "C", "D"]
# Spread the five on-plot labels so they never stack on each other.
STOP_LABEL_BARS = [8, 28, 48, 68]
ENTRY_LABEL_BAR = 85


def render_stop(idx, c):
    cid = "s6_%s_%s" % (c["symbol"], c["day"])
    r = c["rep"]
    hlines = [{"price": r["entry"], "label": "ENTRY", "cls": "entryrail",
               "at": min(ENTRY_LABEL_BAR, len(c["candles"]) - 3)}]
    hlines += [{"price": px, "label": STOP_LETTERS[k], "cls": "cand",
                "at": STOP_LABEL_BARS[k]}
               for k, (_fam, px) in enumerate(c["families"])]
    dots = [{"i": r["entry_i"], "price": r["entry"], "label": ""}]
    svg = chart_of(c, dots=dots, hlines=hlines)
    meta = (LEGEND_SIX +
            '<div class="legend" style="padding-top:0">'
            '<span><b style="color:var(--entry)">&mdash; ENTRY</b> %s at %s</span>'
            '<span><b>A B C D</b> four candidate stops, drawn solid</span></div>')
    meta = meta % (DIR_WORDS.get(r["dir"], "?"), r["et"])
    opts = [(STOP_LETTERS[k], "%s &mdash; %.2f" % (STOP_LETTERS[k], px))
            for k, (_fam, px) in enumerate(c["families"])]
    opts.append(("none", "NONE OF THESE"))
    q = probe_page.question(
        "stop_pick", "Where does the stop go?",
        "Tap the line you'd use. If none of them is right, say where instead.",
        opts, required=True,
        note_placeholder="if none of these &mdash; where, and why?")
    return card_shell(cid, "where_is_the_stop", idx, c["symbol"], c["day"],
                      "entry given", '<div class="chartwrap">%s</div>' % svg,
                      meta, q, export_blob({"section": "where_is_the_stop",
                                            "symbol": c["symbol"], "date": c["day"],
                                            "entry_et": r["et"],
                                            "prices": {STOP_LETTERS[k]: round(px, 2)
                                                       for k, (_f, px)
                                                       in enumerate(c["families"])}}))


def render_ballot(idx, k, b):
    cid = "rule_%02d" % k
    body = ('<div class="ruleq">'
            '<blockquote class="mentor">&ldquo;%s&rdquo;'
            '<cite>&mdash; %s</cite></blockquote>'
            '<p class="change"><b>What it would change:</b> %s</p></div>'
            % (b["quote"], b["who"], b["change"]))
    q = probe_page.question(
        "ballot", "Is this a rule of yours?",
        "Nothing here becomes code without a yes.",
        [("yes", "YES"), ("no", "NO"), ("skip", "SKIP &mdash; park it")],
        required=True,
        note_placeholder="a sentence, if you have one (optional)")
    return ('<article class="card" data-cid="%s" data-section="mentor_ballot" '
            'data-export="%s" data-done="0">'
            '<header><span class="idx">%02d</span>'
            '<span class="tick">RULE %d</span>'
            '<span class="when">%s</span><span class="tags">'
            '<span class="tag">said %d&times;</span>'
            '<span class="done-dot"></span></span></header>%s%s</article>'
            % (cid, export_blob({"section": "mentor_ballot", "rule_no": k,
                                 "who": b["who"]}),
               idx, k, b["who"], b["said"], body, q))


# ------------------------------------------------------------------- the page

PAGE_CSS = """
<style>
.sec{margin:34px 0 14px; padding:16px; border:1px solid var(--rule-2);
     border-radius:10px; background:var(--surface-2); scroll-margin-top:64px}
.sec h2{font-family:"IBM Plex Serif",Georgia,serif; font-size:20px; font-weight:600;
        margin:0 0 6px; color:var(--ink)}
.sec p{margin:0 0 8px; font-size:14px; color:var(--ink-2)}
.sec p:last-child{margin-bottom:0}
.sec blockquote{margin:10px 0 0; padding:8px 0 8px 12px;
                border-left:3px solid var(--accent); font-size:14px;
                color:var(--ink); font-style:italic}
.sec blockquote cite{display:block; margin-top:5px; font-style:normal;
                     font-size:12px; color:var(--ink-3)}
.toc{display:flex; flex-wrap:wrap; gap:7px; margin:0 0 18px}
.toc a{font:600 12.5px/1 "IBM Plex Sans",sans-serif; text-decoration:none;
       color:var(--accent); border:1px solid var(--accent); border-radius:999px;
       padding:9px 12px; min-height:36px; display:flex; align-items:center}
.pair{display:flex; gap:8px; flex-wrap:wrap}
.pair .pane{flex:1 1 320px; min-width:0}
.ruleq{padding:14px 16px}
.mentor{margin:0; padding:0 0 0 12px; border-left:3px solid var(--accent);
        font-size:15.5px; line-height:1.45; color:var(--ink)}
.mentor cite{display:block; margin-top:6px; font-style:normal; font-size:12px;
             color:var(--ink-3); font-family:"IBM Plex Mono",monospace}
.change{margin:10px 0 0; font-size:13.5px; color:var(--ink-2)}
/* The level prices sit just outside the 720-wide viewBox on a three-digit
   symbol, so the chart must not clip them, and the card needs the room. */
.chart{overflow:visible}
.chartwrap{padding-right:16px}
.chart .dot{stroke:var(--entry); fill:var(--surface); stroke-width:2.2}
/* A label sitting on top of candles is unreadable without a halo. */
.chart .dot-t,.chart .hrail-t{paint-order:stroke; stroke:var(--surface);
                              stroke-width:3.5px; stroke-linejoin:round}
.chart .dot-t{font-family:"IBM Plex Mono",monospace; font-size:11px;
              font-weight:600; fill:var(--entry)}
.chart .hrail.cand{stroke:var(--stop); stroke-width:1.2; stroke-dasharray:none}
.chart .hrail-t.cand{font-family:"IBM Plex Mono",monospace; font-size:11px;
                     font-weight:600; fill:var(--stop)}
.chart .hrail.entryrail{stroke:var(--entry); stroke-width:1.6}
.chart .hrail-t.entryrail{font-family:"IBM Plex Mono",monospace; font-size:11px;
                          font-weight:600; fill:var(--entry)}
.chart .hrail.dclose{stroke:var(--ink-3); stroke-width:1; stroke-dasharray:4 4}
.chart .hrail-t.dclose{font-family:"IBM Plex Mono",monospace; font-size:9px;
                       fill:var(--ink-3)}
@media (max-width:520px){.toc a{flex:1 1 calc(50% - 4px)}}
</style>
"""

PAGE_JS = """
<script>
/* One row per ANSWER, not one row per card -- seven different questions live on
   this page and they are not the same shape. The single-row export in
   probe_page.py is untouched for every other page; this hook replaces it here. */
window.probeRows = function(card, row){
  var out = [], seen = {}, keys = [];
  function add(o){ Object.keys(o || {}).forEach(function(k){
    if (!seen[k]){ seen[k] = 1; keys.push(k); } }); }
  add(row.answers); add(row.notes);
  keys.forEach(function(k){
    out.push({type: 'probe', probe: row.probe,
              section: card.getAttribute('data-section'),
              card_id: row.card_id, question: k,
              answer: (row.answers || {})[k] || [],
              text: (row.notes || {})[k] || '',
              symbol: row.symbol || null, date: row.date || null});
  });
  return out;
};
</script>
"""

SECTIONS = [
    ("sec1", "is_this_an_s", "Is this an S?", N_S,
     "<p>The control, and it is the same instrument you graded last night: an S "
     "on your ladder, at one of your six levels, nothing marked. Half of them are "
     "trades the engine actually took, half are mornings it refused outright, and "
     "the card does not say which.</p>"
     "<p>Everything else on this page gets read against this section, so it goes "
     "first.</p>", None),

    ("sec2", "which_signal", "Which signal on this chart?", N_WHICH,
     "<p>Every one of these mornings carries two setups that both look like "
     "trades. Both are marked with a dot &mdash; where and when, and nothing "
     "else. No entry line, no stop, no direction.</p>"
     "<p>This is the question we have been getting wrong. On the cards you have "
     "graded, the page never showed you which signal it was asking about, so a "
     "yes could only ever mean <i>there is a trade on this chart</i> &mdash; and "
     "on nineteen of the twenty-five cards where you wrote a minute, a different "
     "signal sat closer to your minute than the one the card was built from. "
     "Pick the one you would take.</p>", None),

    ("sec3", "what_minute", "What minute would you enter?", N_MINUTE,
     "<p>Nothing marked, nothing claimed &mdash; just the morning and the four "
     "levels that exist before the bell.</p>"
     "<p>Twenty of the thirty cards you graded last night carried a minute you "
     "wrote yourself, and that minute turned out to be the most useful field on "
     "the whole page: it is the only thing that says <i>which</i> trade you "
     "meant. So this time we are asking for it on purpose.</p>", None),

    ("sec4", "htf_agree", "Does the higher timeframe agree?", N_HTF,
     "<p>Two charts per card: the morning with the setup marked, and the same "
     "symbol's <b>daily</b> chart ending at the close <b>before</b> that morning "
     "&mdash; so nothing on it knows how the day went.</p>"
     "<p>You raised this and it has no author. Four candidate definitions were "
     "measured and every one of them is a tie: the best is worth $41 a day "
     "against a band four times wider than that, and the gentlest version costs "
     "twelve of the S days the book reaches. Rather than guess a fifth "
     "definition, here are six mornings &mdash; tell us whether the higher "
     "timeframe agrees, and in the box, what you looked at.</p>",
     ("An S trade happens at 9:30 &mdash; but it would have been a better S trade "
      "20 minutes later if I knew the longer time frame. I could have been more "
      "selective. That's why the higher time frame thesis and how it shapes the "
      "trades is now very important&hellip; take a look at a signal when it "
      "happens and be like, the higher time frame doesn't look as good&hellip; "
      "But all that's very ambiguous and hard to track.", "you, 29 August")),

    ("sec5", "displacement", "Is there displacement?", N_DISP,
     "<p>You named displacement in four of the nine refusals last night without "
     "being asked, so it is the strongest un-ratified thing in your marks.</p>"
     "<p>Here is the problem. The code measures displacement as <b>a fat break "
     "candle</b>. Every sentence you have said about it &mdash; and every "
     "sentence the mentors have said &mdash; measures <b>distance from the "
     "level</b>. And on the three charts you refused <i>for</i> no displacement, "
     "neither version trips. These eight straddle the line on purpose: some have "
     "barely any separation, some have a lot. Yes or no, and one line on what you "
     "measured it from.</p>",
     ("really no displacement from the original candles so i have to "
      "downgrade&hellip; it didnt displace from that wick&hellip; a break retest "
      "with no dispacement happens at 9:45, its not of the level just the wicks "
      "at the beginning of the day.", "you, three cards on 29 August")),

    ("sec6", "where_is_the_stop", "Where is the stop?", N_STOP,
     "<p>The entry is given. Four candidate stops are drawn and lettered: the "
     "bottom of the candle entered on, the level that broke, prior pivot "
     "structure, and a wider disaster stop. They are shuffled, so the letter "
     "tells you nothing about which family it is.</p>"
     "<p>Of the 114 stops in your own marks that carry a price, 80 sit at the "
     "bottom of the candle you entered on and only 7 sit on pivot structure "
     "&mdash; even though pivots come up fifteen times in what you typed. This "
     "section asks the question on fresh charts instead of on the same marks that "
     "produced the number.</p>",
     ("stops go where they make sense&hellip; from my head right now the answer "
      "is level, bottom of candle entered on, pivot structure, and you decide "
      "which one based on the best risk to reward tradable. you pick a disaster "
      "stop.", "you, 29 August")),

    ("sec7", "mentor_ballot", "The mentor rule ballot", len(MENTOR_BALLOT),
     "<p>No charts. Fifteen things Scarface, Jdub, Neto, Lauren, Mamba or Hayden "
     "say and <b>you never have</b>, in their words, with what each one would "
     "change underneath.</p>"
     "<p>Ordered by how much the rule would move the engine, not by how often it "
     "was said &mdash; the most-repeated rule in that whole corpus was said seven "
     "times, so frequency ranks nothing. Yes, no, or skip. <b>Nothing here "
     "becomes code without a yes.</b></p>", None),
]


def section_header(sid, title, n, i, body, quote):
    q = ""
    if quote:
        q = '<blockquote>&ldquo;%s&rdquo;<cite>%s</cite></blockquote>' % quote
    unit = "yes/no lines" if sid == "sec7" else ("chart" if n == 1 else "charts")
    return ('<section class="sec" id="%s"><p class="eyebrow">Section %d of 7 '
            '&middot; %d %s</p><h2>%s</h2>%s%s</section>'
            % (sid, i, n, unit, title, body, q))


def build(cards_by_section):
    parts = [PAGE_CSS]
    toc = ['<nav class="toc">']
    for i, (sid, key, title, n, _b, _q) in enumerate(SECTIONS, 1):
        toc.append('<a href="#%s">%d &middot; %s</a>' % (sid, i, title))
    toc.append("</nav>")
    parts.append("".join(toc))

    idx = 0
    for i, (sid, key, title, n, body, quote) in enumerate(SECTIONS, 1):
        got = cards_by_section.get(key, [])
        parts.append(section_header(sid, title, len(got), i, body, quote))
        for c in got:
            idx += 1
            parts.append(c["html"](idx, c) if callable(c.get("html")) else c["html"])
    total = idx

    lede = ("Seven questions, %d cards, about fifteen minutes. Every chart is a "
            "morning you have <strong>never been shown</strong> &mdash; not "
            "graded, not served in any earlier deck. Each section asks something "
            "different, and the first one is the control so the rest has "
            "something to be read against. <strong>Answers save to this browser "
            "as you tap</strong> and come back if you close the page; tap "
            "<strong>Export</strong> at the top when you are done." % total)
    footer = ("<h2>When you're done</h2><p>Tap <b>Export</b> at the top, then "
              "<b>Copy all</b> and paste it into the chat &mdash; or "
              "<b>Download .jsonl</b>. One line comes out per answer, with the "
              "section it belongs to and anything you typed.</p>"
              "<p>You do not have to finish it in one sitting. Everything you tap "
              "is saved in this browser as you go, and the page comes back the "
              "way you left it.</p>"
              "<p><b>One thing about the high-of-day and low-of-day lines:</b> "
              "where they are drawn, they sit where they stood <i>when the setup "
              "formed</i>, not at the end of the session &mdash; so that line can "
              "sit below later highs on the chart. Two sections leave them off "
              "entirely, because on those cards the line would be the answer.</p>")
    html = probe_page.shell(
        title="OMEN &mdash; master homework",
        eyebrow="OMEN homework &middot; seven angles, one sitting",
        h1="Master homework",
        lede=lede, cards_html="".join(parts), footer_html=footer, deck_id=DECK_ID)
    # The export hook is read at click time, so it can be defined after the shell.
    return html + PAGE_JS


# -------------------------------------------------------------------- manifest

def manifest_rows(cards_by_section):
    """The served record AND the answer key. None of this is in the HTML."""
    rows = []
    for key, cards in cards_by_section.items():
        if key == "mentor_ballot":
            for k, b in enumerate(MENTOR_BALLOT, 1):
                rows.append({"card_id": "rule_%02d" % k, "deck": DECK_ID,
                             "section": key, "rule_no": k, "who": b["who"],
                             "times_said": b["said"]})
            continue
        for c in cards:
            r = c.get("rep") or {}
            row = {"card_id": "%s_%s" % (c["symbol"], c["day"]),
                   "symbol": c["symbol"], "date": c["day"], "deck": DECK_ID,
                   "section": key,
                   "drawn_levels": round_levels(c["levels"]),
                   "prefilter_reach_r": c.get("prefilter"),
                   # ---- answer key, deliberately never rendered ----
                   "engine_setup": r.get("setup"), "et": r.get("et"),
                   "dir": r.get("dir"), "entry": r.get("entry"),
                   "entry_i": r.get("entry_i"), "traded": r.get("traded"),
                   "sgrade": r.get("sgrade"), "legacy_grade": r.get("grade"),
                   "tripped": r.get("tripped"), "downgrades": r.get("downgrades"),
                   "outcome": r.get("out"), "r": r.get("r"),
                   "level_name": r.get("level_name"), "level_px": r.get("level_px")}
            if key == "is_this_an_s":
                row.update(role=c["role"], bucket=c["bucket"],
                           claimed_level=c["level"], claimed_level_source=c["level_how"])
            if key == "which_signal":
                row.update(engine_trade_et=c["engine_trade_et"],
                           dots=[{"letter": L, "et": p["et"], "dir": p["dir"],
                                  "setup": p["setup"], "sgrade": p.get("sgrade"),
                                  "traded": bool(p.get("traded")),
                                  "entry_i": p["entry_i"]}
                                 for L, p in zip(["A", "B"], c["pair"])])
                row.pop("engine_setup", None)
            if key == "what_minute":
                row.update(role=c["role"])
            if key == "htf_agree":
                row.update(htf_group=c["htf_group"], htf_score=c["htf_score"],
                           daily_sessions=len(c["daily"]))
            if key == "displacement":
                row.update(sep_atr=c["sep_atr"], sep_bucket=c["sep_bucket"],
                           shipped_check_trips=c["shipped_trips"])
            if key == "where_is_the_stop":
                row.update(stop_letters={L: {"family": f, "price": round(px, 4)}
                                         for L, (f, px)
                                         in zip(STOP_LETTERS, c["families"])},
                           disaster_pct=DISASTER_PCT)
            rows.append(row)
    return rows


def write_manifest(rows, path=OUT_MANIFEST):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


# ------------------------------------------------------------------------ main

# Terms that would give the answer away if they reached the page. `role` and
# `traded` are the same secret wearing two names; `sgrade` and `sep_atr` are the
# gradings this homework exists to test.
LEAK_TERMS = ["sgrade", "\"traded\"", "&quot;traded&quot;", "\"role\"",
              "&quot;role&quot;", "sep_atr", "shipped_check", "htf_score",
              "legacy_grade", "\"family\"", "&quot;family&quot;", "tripped"]


def selfcheck(path=OUT_HTML):
    """Read the page back off disk and check the delivery contract.

    Not a proxy for opening it in a browser -- that was done too -- but these are
    the failures a rebuild could reintroduce silently: a duplicate card id makes
    two cards share one localStorage slot; a duplicate question key inside a card
    makes the second one un-restorable; a duplicate chip value inside a question
    makes restore light the wrong chip.
    """
    import re as _re
    html = open(path, encoding="utf-8").read()
    fails = []

    def check(ok, msg):
        print("%s  %s" % ("PASS" if ok else "FAIL", msg))
        if not ok:
            fails.append(msg)

    cards = _re.findall(r'<article class="card"(.*?)</article>', html, _re.S)
    cids = _re.findall(r'<article class="card" data-cid="([^"]+)"', html)
    check(len(cards) == len(cids) == N_S + N_WHICH + N_MINUTE + N_HTF + N_DISP
          + N_STOP + len(MENTOR_BALLOT),
          "%d cards on the page" % len(cards))
    check(len(set(cids)) == len(cids),
          "every card id is unique -- one localStorage slot each")
    for cid, body in zip(cids, cards):
        qs = _re.findall(r'data-q="([^"]+)"', body)
        check(len(set(qs)) == len(qs) and qs,
              "%s: question keys unique (%s)" % (cid, ",".join(qs)))
        for q in _re.findall(r'<section class="q"(.*?)</section>', body, _re.S):
            vs = _re.findall(r'data-v="([^"]+)"', q)
            if vs and len(set(vs)) != len(vs):
                check(False, "%s: duplicate chip value" % cid)
        req = body.count('data-required="1"')
        check(req == 1, "%s: exactly one required question" % cid)

    check(probe_page.JS in html, "the shared save/restore/export script is "
                                 "shipped verbatim")
    check("window.probeRows" in html, "the one-row-per-answer export hook is on "
                                      "the page")
    check('name="viewport"' in html, "the mobile viewport tag is there")
    check("localStorage.setItem" in html and "restore()" in html,
          "saves to localStorage and restores on load")
    check(html.count('<svg class="chart"') == N_S + N_WHICH + N_MINUTE
          + N_HTF * 2 + N_DISP + N_STOP,
          "%d charts, all static SVG in the markup"
          % html.count('<svg class="chart"'))
    check("<canvas" not in html, "no canvas anywhere")
    check(html.count('class="dot ') == N_WHICH * 2 + N_HTF + N_DISP + N_STOP,
          "%d labelled dots" % html.count('class="dot '))
    check(html.count('class="hrail cand"') == N_STOP * 4,
          "%d candidate stop lines (four per card)"
          % html.count('class="hrail cand"'))
    check(not [t for t in LEAK_TERMS if t in html], "no answer-key term on the page")
    print("SELFCHECK %s" % ("OK" if not fails else "FAILED: %d" % len(fails)))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=82)
    ap.add_argument("--selfcheck", action="store_true",
                    help="re-read the built page and check the delivery contract")
    a = ap.parse_args()
    if a.selfcheck:
        raise SystemExit(0 if selfcheck() else 1)
    rng = random.Random(a.seed)

    _book, byday = load_book()
    print("book: %d symbol-days" % len(byday))
    blob = json.load(open(HTF_CACHE, encoding="utf-8"))

    render = {"is_this_an_s": render_is_s, "which_signal": render_which,
              "what_minute": render_minute, "htf_agree": render_htf,
              "displacement": render_disp, "where_is_the_stop": render_stop}

    # Another builder can serve cards while this one is picking -- it happened on
    # the first run of this script, and the guard below caught it. So the seen set
    # is re-read AFTER picking and the whole pick is redone if anything collided.
    blocked = set()
    for attempt in range(1, 4):
        judged = bd.marked_card_ids()
        served = bd.served_card_ids(OUT_MANIFEST)
        seen = judged | served | blocked
        print("no-repeat guard: %d judged + %d served-only = %d symbol-days he "
              "has already seen%s"
              % (len(judged), len(served - judged), len(seen),
                 "" if not blocked else " (+%d served by another build mid-pick)"
                 % len(blocked)))

        pool = Pool(seen)
        cards = {}
        cards["is_this_an_s"] = pick_is_s(pool, rng)
        cards["which_signal"] = pick_which_signal(pool, rng, byday)
        cards["what_minute"] = pick_minute(pool, rng, byday)
        cards["htf_agree"] = pick_htf(pool, rng, byday, blob)
        cards["displacement"] = pick_displacement(pool, rng, byday)
        cards["where_is_the_stop"] = pick_stop(pool, rng, byday)

        chart_cards = [c for key in render for c in cards[key]]
        ids = ["%s_%s" % (c["symbol"], c["day"]) for c in chart_cards]
        assert len(set(ids)) == len(ids), "the same morning appears twice on the page"
        repeats = sorted(set(ids) & bd.seen_card_ids(OUT_MANIFEST))
        if not repeats:
            break
        print("  another build served %d of these while this one was picking "
              "(%s) -- re-picking" % (len(repeats), ", ".join(repeats)))
        blocked |= set(repeats)
    assert not repeats, "page repeats a judged/served symbol-day: %s" % repeats

    for key, fn in render.items():
        for c in cards[key]:
            c["html"] = fn
    cards["mentor_ballot"] = [
        {"symbol": None, "day": None,
         "html": (lambda i, c, k=k, b=b: render_ballot(i, k, b))}
        for k, b in enumerate(MENTOR_BALLOT, 1)]

    for key, want in (("is_this_an_s", N_S), ("which_signal", N_WHICH),
                      ("what_minute", N_MINUTE), ("htf_agree", N_HTF),
                      ("displacement", N_DISP), ("where_is_the_stop", N_STOP)):
        got = len(cards[key])
        print("  %-18s %d/%d%s" % (key, got, want,
                                   "   ** SHORT **" if got < want else ""))

    html = build(cards)
    leaked = [t for t in LEAK_TERMS if t in html]
    assert not leaked, "answer key leaked into the page: %s" % leaked
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    rows = manifest_rows(cards)
    write_manifest(rows)

    n_charts = len(chart_cards)
    print()
    print("Wrote %s (%d bytes)" % (OUT_HTML, os.path.getsize(OUT_HTML)))
    print("Wrote %s (%d rows)" % (OUT_MANIFEST, len(rows)))
    print("cards: %d charts + %d ballot lines = %d"
          % (n_charts, len(MENTOR_BALLOT), n_charts + len(MENTOR_BALLOT)))
    print("no-repeat: the guarantee holds %d symbol-days he has already judged or "
          "been served. Candidates each section had to choose from, and how many "
          "of them it had to throw away as already seen:" % len(pool.seen))
    for key in ("is_this_an_s", "which_signal", "what_minute", "htf_agree",
                "displacement", "where_is_the_stop"):
        cons = pool.considered_by.get(key, set())
        blk = cons & pool.seen
        print("    %-18s %6d suitable  %5d rejected as already seen (%.1f%%)  "
              "%6d left" % (key, len(cons), len(blk),
                            100.0 * len(blk) / max(1, len(cons)),
                            len(cons) - len(blk)))
    print("    %-18s %6d suitable  %5d rejected as already seen"
          % ("ALL SECTIONS", len(pool.considered),
             len(pool.considered & pool.seen)))
    print("           during selection the check turned away %d candidates it "
          "actually reached, and %d already used by an earlier section of this page"
          % (len(pool.rejected_seen), len(pool.rejected_reused)))
    print("            %d rejected by the deck pre-filter, %d thin sessions, "
          "%d over the 2-per-symbol cap"
          % (pool.rejected_prefilter, pool.rejected_thin, pool.rejected_symbol_cap))
    print("symbols: %d distinct, max per symbol %d"
          % (len(set(c["symbol"] for c in chart_cards)),
             max(Counter(c["symbol"] for c in chart_cards).values())))
    # Section 2 has no single representative row -- one of its two dots IS the
    # engine's booked trade -- so it is counted on its own rather than folded in
    # as a refusal, which is what a naive `rep.traded` tally would do.
    single = [c for c in chart_cards if c["section"] != "which_signal"]
    eng = Counter(bool((c.get("rep") or {}).get("traded")) for c in single)
    print("of the %d single-signal chart cards, the engine booked a trade on %d "
          "and refused the morning outright on %d; the other %d cards each carry "
          "the engine's own trade AND a signal it passed over"
          % (len(single), eng[True], eng[False], len(cards["which_signal"])))
    print("REPEAT CHECK: %s" % ("PASS" if not repeats else "FAIL"))
    print()
    selfcheck()


if __name__ == "__main__":
    main()
