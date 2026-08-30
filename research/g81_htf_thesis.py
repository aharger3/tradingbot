"""g81_htf_thesis.py -- is a higher-timeframe read worth anything as a SELECTOR?

Austin, 2026-08-29, last thing at night:

    "An S trade happens at 9:30 -- but it would have been a better S trade 20
     minutes later if I knew the longer time frame. I could have been more
     selective. That's why the higher time frame thesis and how it shapes the
     trades is now very important... take a look at a signal when it happens
     and be like, the higher time frame doesn't look as good, or wasn't the
     strongest candle. I have a feeling that something better can happen. But
     all that's very ambiguous and hard to track."

He is describing a SELECTOR (which of the day's setups to take), not a veto.
`HTF_BIAS_VETO` is a veto, ships ON, gates 47% of the book, and has no author.
It is NOT this and is measured here only as one candidate among four, on equal
terms with the rest.

Five things get measured, in order, and step 1 can end the enquiry on its own:

  1. THE PRIZE, with no model at all. First setup of the day vs best setup of
     the day, one-trade-a-day, over research/bt2y_trades.json. Everything below
     is bounded by that gap.
  2. FOUR CANDIDATE DEFINITIONS of "higher-timeframe bias", each sourced to a
     sentence somebody actually said (Austin's rulebook, or the mentor/course
     corpora), each computable at 09:29 or from the day's own bars up to the
     decision minute. No look-ahead: every window is closed strictly before the
     bar being judged.
  3. EACH AS A SELECTOR: does it rank the day's best setup first more often
     than arrival order does? Hit-rate and dollars-a-day against the
     arrival-order baseline, with a paired day-level bootstrap.
  4. EACH AS A WAIT RULE: skip the 09:30-09:45 signal when the higher timeframe
     disagrees, take the next one that agrees. Dollars a day, months green, AND
     the recall cost on Austin's S days -- the gate he is furthest from.
  5. CROSS-CHECK against the 21 entry minutes Austin wrote on the 2026-08-29
     homework deck. On the days he named a minute later than 09:35, does the
     candidate explain why he waited?

NOTHING IS APPLIED. This file measures and writes a report; it changes no
engine default and touches no mark file (every corpus is opened read-only,
through research/marks_pool.py).

Usage:
    python research/g81_htf_thesis.py
    python research/g81_htf_thesis.py --no-cache      # rebuild the daily cache
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

BOOK = os.path.join(HERE, "bt2y_trades.json")
CACHE = os.path.join(HERE, "g81_htf_cache.json")
OUT_JSON = os.path.join(HERE, "g81_htf_thesis.json")
MARKS30 = os.path.join(HERE, "marks", "probe_g71_homework_s3_2026-08-29_complete.jsonl")

RISK = 1000.0                 # CLAUDE.md: 1R = $1,000
EARLY_CUTOFF = "09:45"        # "the 09:30-09:45 signal", from the brief
DEADBAND = 0.05               # percent; "a clear direction", see INDEX_NOTE
BOOT = 2000
SEED = 20260830


# ----------------------------------------------------------------- book loading

def load_book(path=BOOK):
    b = json.load(open(path, encoding="utf-8"))
    return b["meta"], b["trades"]


def ekey(r):
    return (r["day"], r["et"], r["sym"])


def candidates(rows):
    """The one-trade-a-day candidate stream, identical to
    research/g72_suppress_price.py::oneaday_rows -- fired-and-traded plus the
    rows the account-wide two-loss halt blocked (under one-a-day that halt
    cannot have fired yet, so those days are live again)."""
    byday = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday[r["day"]].append(r)
    for v in byday.values():
        v.sort(key=ekey)
    return dict(byday)


# ------------------------------------------------------------------- arithmetic

def iso_week(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return "%04d-W%02d" % (y, w)


def drawdown(pnls):
    peak = cum = worst = 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    return -worst


def book_stats(rows, n_days):
    """Same shape as g72_suppress_price.stats, recomputed here so this file
    stands alone if that one moves."""
    if not rows:
        return {"trades": 0}
    # Drawdown is order-sensitive, so the rows are put in clock order HERE
    # rather than trusting each caller's dict iteration order. Without this the
    # same baseline printed two different drawdowns in two sections.
    rows = sorted(rows, key=ekey)
    pnls = [r["pnl"] for r in rows]
    wins = sum(1 for r in rows if r["pnl"] > 0)
    losses = sum(1 for r in rows if r["pnl"] < 0)
    total = sum(pnls)
    by_m, by_w = defaultdict(float), defaultdict(float)
    for r in rows:
        by_m[r["day"][:7]] += r["pnl"]
        by_w[iso_week(r["day"])] += r["pnl"]
    return {
        "trades": len(rows),
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "total_dollars": round(total),
        "per_trade": round(total / len(rows)),
        "mean_r": round(total / len(rows) / RISK, 3),
        "per_day": round(total / n_days),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "weeks_green": sum(1 for v in by_w.values() if v > 0),
        "weeks": len(by_w),
        "worst_drawdown": round(drawdown(pnls)),
    }


def paired_bootstrap(a_by_day, b_by_day, n_days, boot=BOOT, seed=SEED):
    """Day-level paired bootstrap of (A - B) dollars per day.

    a_by_day/b_by_day: {day: dollars} (0 when the policy did not trade). The
    resample is over DAYS, which is the unit both policies share -- that is the
    honest pairing, and it is why the interval is wider than a per-trade one.
    """
    days = sorted(set(a_by_day) | set(b_by_day))
    diffs = [a_by_day.get(d, 0.0) - b_by_day.get(d, 0.0) for d in days]
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(boot):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n_days)
    means.sort()
    return (round(means[int(0.025 * boot)]), round(means[int(0.975 * boot)]))


# ------------------------------------------------ higher-timeframe feature build
#
# Everything in this section is built from bars that had already CLOSED before
# the bar being judged. The two rules that keep it honest:
#   * daily/weekly windows end on the PREVIOUS session's close;
#   * the intraday index read at minute T uses closes up to T-1 only.
# research/g72_after.md's spy_trend field is NOT used anywhere here: it is
# computed from an SMA window that includes the day's own close (backtest_2y.py
# spy_context(), line `sma = fmean(closes[max(0,i-19):i+1])`), so it knows the
# answer. That is exactly the bug class this file exists to avoid.

INDEX_SYM = "SPY"

INDEX_NOTE = (
    "0.05% deadband on the index move. The mentors say 'a clear direction', "
    "never a number; 0.05% is roughly a third of SPY's median 09:30-09:45 "
    "excursion and is reported with 0.00% and 0.10% beside it so the choice "
    "cannot hide a result."
)


def build_cache(days_needed, syms_needed, path=CACHE):
    """{sym: {day: close}} daily RTH closes, plus SPY's minute path per day.

    Slow (reads the 1-minute archive), so it is cached to research/
    g81_htf_cache.json. Delete that file or pass --no-cache to rebuild.
    """
    import polygon_feed as pf   # noqa: E402  (cache-first, reads data_archive)

    daily = {}
    for sym in sorted(syms_needed | {INDEX_SYM}):
        d = os.path.join(ROOT, "data_archive", sym)
        if not os.path.isdir(d):
            continue
        closes = {}
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".csv"):
                continue
            day = fn[:-4]
            try:
                rth = pf.rth(pf.fetch_day(sym, day))
            except Exception:
                continue
            if len(rth) < 30:
                continue
            closes[day] = rth[-1].close
        daily[sym] = closes
        print("  daily closes %-6s %4d sessions" % (sym, len(closes)), flush=True)

    # SPY's intraday path: for each session, the 09:30 open and the cumulative
    # percent move to the close of every minute.
    idx = {}
    for day in sorted(days_needed):
        try:
            rth = pf.rth(pf.fetch_day(INDEX_SYM, day))
        except Exception:
            continue
        if len(rth) < 30:
            continue
        o = rth[0].open
        walk = {}
        for c in rth:
            hhmm = str(c.timestamp)[:5]           # polygon_feed.Candle.timestamp is "HH:MM:SS"
            walk[hhmm] = round((c.close - o) / o * 100, 4) if o else 0.0
        idx[day] = walk
    print("  index path     %-6s %4d sessions" % (INDEX_SYM, len(idx)), flush=True)

    blob = {"daily": daily, "index": idx, "index_sym": INDEX_SYM}
    json.dump(blob, open(path, "w", encoding="utf-8"))
    return blob


def load_cache(days_needed, syms_needed, use_cache=True):
    if use_cache and os.path.exists(CACHE):
        blob = json.load(open(CACHE, encoding="utf-8"))
        have_days = set(blob.get("index", {}))
        have_syms = set(blob.get("daily", {}))
        if days_needed <= have_days and syms_needed <= (have_syms | {INDEX_SYM}):
            return blob
        print("cache incomplete, rebuilding", flush=True)
    print("building the daily/index cache (reads data_archive, ~3 min)", flush=True)
    return build_cache(days_needed, syms_needed)


def _dir_from(pct, deadband):
    if pct > deadband:
        return "bull"
    if pct < -deadband:
        return "bear"
    return "flat"


def daily_features(blob, sym, day):
    """Symbol's own daily and weekly read, both closed BEFORE today's open."""
    closes = blob["daily"].get(sym)
    if not closes:
        return {"daily": "flat", "weekly": "flat"}
    keys = sorted(k for k in closes if k < day)
    if len(keys) < 21:
        return {"daily": "flat", "weekly": "flat"}
    prev = closes[keys[-1]]
    sma20 = statistics.fmean(closes[k] for k in keys[-20:])
    dpct = (prev - sma20) / sma20 * 100 if sma20 else 0.0
    wk = closes[keys[-6]] if len(keys) >= 6 else prev
    wpct = (prev - wk) / wk * 100 if wk else 0.0
    return {"daily": _dir_from(dpct, 0.1), "weekly": _dir_from(wpct, 0.1),
            "daily_pct": round(dpct, 3), "weekly_pct": round(wpct, 3)}


def index_dir(blob, day, et, deadband=DEADBAND):
    """SPY's move from the 09:30 open to the close of the minute BEFORE `et`."""
    path = blob["index"].get(day)
    if not path:
        return "flat", None
    hh, mm = int(et[:2]), int(et[3:5])
    tot = hh * 60 + mm - 1                      # strictly the previous minute
    best = None
    for k, v in path.items():
        t = int(k[:2]) * 60 + int(k[3:5])
        if t <= tot and (best is None or t > best[0]):
            best = (t, v)
    if best is None:
        return "flat", None
    return _dir_from(best[1], deadband), best[1]


def want(direction):
    """Trade direction -> the bias that agrees with it."""
    return "bull" if direction == "call" else "bear"


HOURLY_MAP = {"bullish": "bull", "bearish": "bear", "neutral": "flat", "none": "flat"}


def row_features(blob, r):
    f = daily_features(blob, r["sym"], r["day"])
    f["hourly"] = HOURLY_MAP.get(r.get("bias", "none"), "flat")
    f["index"], f["index_pct"] = index_dir(blob, r["day"], r["et"])
    f["index0"], _ = index_dir(blob, r["day"], r["et"], 0.0)
    f["index10"], _ = index_dir(blob, r["day"], r["et"], 0.10)
    f["want"] = want(r["dir"])
    return f


# --------------------------------------------------------------- the candidates
#
# Each returns an alignment SCORE. Higher is better. A binary candidate returns
# 1 (agrees), 0 (no opinion / flat) or -1 (disagrees). The stack returns 0..4.

CANDIDATES = {
    "index_at_the_minute": {
        "one_line": ("Take the setup that is moving the same way the index is moving "
                     "right now, measured from the 09:30 open to the close of the "
                     "minute before the signal."),
        "source": ('course corpus, "Wait for indices direction": "usually I wait for '
                   'the indices to show me a clear direction or trend. Then after I '
                   'understand the indices trend or direction, I go look for the one '
                   'with relative strength or relative weakness"; and "A+ Setup '
                   'Requires QQQ Confluence": "you see the a plus setup on one '
                   'sticker only valid as an a plus when the conference with qqq is '
                   'there as well".'),
        "known_at": "the decision minute (index bars that already closed)",
    },
    "daily_bias": {
        "one_line": ("Take the setup that agrees with the symbol's own daily chart -- "
                     "yesterday's close above or below its 20-session average."),
        "source": ('mentor corpus, Jdub: "If you are day trading the timeframes you '
                   'want to be looking at are the daily and hourly charts for higher '
                   'timeframes" and "If you can consistently identify the daily bias '
                   'then it will make trading alot easier"; course corpus: "My '
                   'strategy my edge is so simple. It works with relevant key levels '
                   'on the daily and the 15 minute chart".'),
        "known_at": "09:29 (yesterday's close and the 20 before it)",
    },
    "hourly_bias_incumbent": {
        "one_line": ("Take the setup that agrees with the hourly chart -- the last "
                     "hourly close before the bell against its 20-hour average. This "
                     "is the formula already shipping inside HTF_BIAS_VETO, scored "
                     "here as a selector instead of a veto."),
        "source": ('backtest_week.htf_bias_for(); it has NO author -- Austin, twice: '
                   '"we dont have any higher timeframe bias yet youll need to tell me '
                   'what that is then." Carried as a candidate so the incumbent is '
                   'measured on the same rig as the three with sources.'),
        "known_at": "09:29 (hourly closes strictly before the session)",
    },
    "alignment_stack": {
        "one_line": ("Count how many timeframes agree with the setup -- week, day, "
                     "hour, and the index right now -- and take the setup with the "
                     "most agreement."),
        "source": ('course corpus, "Timeframe Alignment": "if you have an a plus '
                   'setup in the market what you want to see is the weekly align you '
                   'want to see the daily chart aligned you want to see the one hour '
                   'aligned... basically when every single time frame is aligning '
                   "that's when you're going to have an a plus opportunity\"."),
        "known_at": "the decision minute (three legs at 09:29, the index leg live)",
    },
}


def score(name, f):
    w = f["want"]
    if name == "index_at_the_minute":
        return 0 if f["index"] == "flat" else (1 if f["index"] == w else -1)
    if name == "daily_bias":
        return 0 if f["daily"] == "flat" else (1 if f["daily"] == w else -1)
    if name == "hourly_bias_incumbent":
        return 0 if f["hourly"] == "flat" else (1 if f["hourly"] == w else -1)
    if name == "alignment_stack":
        return sum(1 for leg in ("weekly", "daily", "hourly", "index") if f[leg] == w)
    raise KeyError(name)


def agrees(name, f):
    """Binary 'the higher timeframe agrees', for the wait rule.

    The stack needs a threshold; 3 of 4 is the mentors' own words ('every
    single time frame aligning'), relaxed by one so it fires often enough to
    measure. Reported with 2-of-4 and 4-of-4 beside it.
    """
    s = score(name, f)
    if name == "alignment_stack":
        return s >= 3
    return s > 0


# ------------------------------------------------------------- the measurements

def step1_prize(byday, n_days):
    firsts, bests, worsts, means = [], [], [], []
    first_is_best = 0
    for day in sorted(byday):
        v = byday[day]
        first, best = v[0], max(v, key=lambda r: r["r"])
        firsts.append(first)
        bests.append(best)
        worsts.append(min(v, key=lambda r: r["r"]))
        means.append(statistics.fmean(r["pnl"] for r in v))
        if first["r"] >= best["r"]:
            first_is_best += 1
    out = {
        "days": len(byday),
        "candidates_total": sum(len(v) for v in byday.values()),
        "candidates_per_day_median": statistics.median(len(v) for v in byday.values()),
        "first": book_stats(firsts, n_days),
        "best": book_stats(bests, n_days),
        "worst": book_stats(worsts, n_days),
        "coinflip_per_day": round(sum(means) / n_days),
        "first_is_best_days": first_is_best,
        "first_is_best_pct": round(100 * first_is_best / len(byday), 1),
        "chance_is_best_pct": round(100 * statistics.fmean(1 / len(v) for v in byday.values()), 1),
    }
    out["gap_per_day"] = out["best"]["per_day"] - out["first"]["per_day"]
    out["arrival_edge_over_chance_per_day"] = out["first"]["per_day"] - out["coinflip_per_day"]
    return out


def step2_signal_information(byday, feats):
    """Before any policy: does alignment separate a good signal from a bad one?

    Mean realised R of every candidate in the book, bucketed by what each
    definition says about it. If a definition carries information, the agrees
    bucket beats the disagrees bucket by more than its own noise. This is the
    cheapest possible test and it is upstream of every policy below.
    """
    out = {}
    for name in CANDIDATES:
        buckets = defaultdict(list)
        for v in byday.values():
            for r in v:
                buckets[score(name, feats[id(r)])].append(r["r"])
        rows = {}
        for k in sorted(buckets):
            rs = buckets[k]
            sd = statistics.pstdev(rs) if len(rs) > 1 else 0.0
            rows[str(k)] = {"n": len(rs), "mean_r": round(statistics.fmean(rs), 3),
                            "se": round(sd / (len(rs) ** 0.5), 3) if rs else 0.0}
        pos = [x for k, v2 in buckets.items() if k > 0 for x in v2]
        neg = [x for k, v2 in buckets.items() if k < 0 for x in v2]
        spread = None
        if pos and neg:
            se = ((statistics.pstdev(pos) ** 2 / len(pos)) +
                  (statistics.pstdev(neg) ** 2 / len(neg))) ** 0.5
            d = statistics.fmean(pos) - statistics.fmean(neg)
            spread = {"agrees_mean_r": round(statistics.fmean(pos), 3),
                      "disagrees_mean_r": round(statistics.fmean(neg), 3),
                      "difference_r": round(d, 3),
                      "ci95_r": [round(d - 1.96 * se, 3), round(d + 1.96 * se, 3)],
                      "n_agrees": len(pos), "n_disagrees": len(neg)}
        out[name] = {"by_score": rows, "agrees_vs_disagrees": spread}
    return out


def selector_pick(name, v, feats):
    """The day's pick under one candidate: highest alignment score, ties broken
    by arrival order (which is the baseline, so a candidate with no opinion
    reproduces the baseline exactly rather than shuffling)."""
    best_s = max(score(name, feats[id(r)]) for r in v)
    for r in v:
        if score(name, feats[id(r)]) == best_s:
            return r
    return v[0]


def step3_selector(byday, feats, n_days):
    base = {d: v[0] for d, v in byday.items()}
    best = {d: max(v, key=lambda r: r["r"]) for d, v in byday.items()}
    base_hits = sum(1 for d in byday if base[d]["r"] >= best[d]["r"])
    base_by_day = {d: base[d]["pnl"] for d in byday}
    rows = {"arrival_order": {
        "hit_best_days": base_hits,
        "hit_best_pct": round(100 * base_hits / len(byday), 1),
        **book_stats(list(base.values()), n_days),
        "vs_baseline_per_day": 0, "ci95": [0, 0],
        "changed_days": 0,
    }}
    for name in CANDIDATES:
        pick = {d: selector_pick(name, v, feats) for d, v in byday.items()}
        hits = sum(1 for d in byday if pick[d]["r"] >= best[d]["r"])
        by_day = {d: pick[d]["pnl"] for d in byday}
        st = book_stats(list(pick.values()), n_days)
        rows[name] = {
            "hit_best_days": hits,
            "hit_best_pct": round(100 * hits / len(byday), 1),
            **st,
            "vs_baseline_per_day": st["per_day"] - rows["arrival_order"]["per_day"],
            "ci95": list(paired_bootstrap(by_day, base_by_day, n_days)),
            "changed_days": sum(1 for d in byday if pick[d] is not base[d]),
        }
    return rows


def wait_pick(name, v, feats):
    """The wait rule: if the first candidate of the day is before 09:45 and the
    higher timeframe disagrees, skip it and take the next one that agrees.
    None means the day goes untraded."""
    first = v[0]
    if first["et"] >= EARLY_CUTOFF or agrees(name, feats[id(first)]):
        return first
    for r in v[1:]:
        if agrees(name, feats[id(r)]):
            return r
    return None


def step4_wait(byday, feats, n_days):
    base = {d: v[0] for d, v in byday.items()}
    base_by_day = {d: base[d]["pnl"] for d in byday}
    rows = {"arrival_order": {**book_stats(list(base.values()), n_days),
                              "days_traded": len(byday), "days_skipped": 0,
                              "days_moved": 0, "vs_baseline_per_day": 0, "ci95": [0, 0]}}
    picks_out = {}

    # The control: WAIT WITH NO MODEL. Skip everything before 09:45 and take
    # the first candidate after it. Any higher-timeframe arm that does not beat
    # this one is not buying a thesis, it is buying a clock.
    ctrl = {}
    for d, v in byday.items():
        later = [r for r in v if r["et"] >= EARLY_CUTOFF]
        ctrl[d] = later[0] if later else None
    taken = [r for r in ctrl.values() if r is not None]
    st = book_stats(taken, n_days)
    rows["wait_to_0945_no_model"] = {
        **st, "days_traded": len(taken),
        "days_skipped": sum(1 for r in ctrl.values() if r is None),
        "days_moved": sum(1 for d in byday if ctrl[d] is not None and ctrl[d] is not base[d]),
        "vs_baseline_per_day": st["per_day"] - rows["arrival_order"]["per_day"],
        "ci95": list(paired_bootstrap({d: (ctrl[d]["pnl"] if ctrl[d] else 0.0) for d in byday},
                                      base_by_day, n_days)),
    }
    picks_out["wait_to_0945_no_model"] = ctrl

    for name in CANDIDATES:
        pick = {d: wait_pick(name, v, feats) for d, v in byday.items()}
        picks_out[name] = pick
        taken = [r for r in pick.values() if r is not None]
        by_day = {d: (pick[d]["pnl"] if pick[d] else 0.0) for d in byday}
        st = book_stats(taken, n_days)
        rows[name] = {
            **st,
            "days_traded": len(taken),
            "days_skipped": sum(1 for r in pick.values() if r is None),
            "days_moved": sum(1 for d in byday if pick[d] is not None and pick[d] is not base[d]),
            "vs_baseline_per_day": st["per_day"] - rows["arrival_order"]["per_day"],
            "ci95": list(paired_bootstrap(by_day, base_by_day, n_days)),
        }
    return rows, picks_out


# ------------------------------------------------------ recall cost on his S days

def s_day_recall(byday, feats):
    """What the wait rule costs on Austin's S days.

    The unit here is the SYMBOL-DAY, not the session: recall asks 'did the
    engine reach a day he called S', and one-a-day's cross-symbol race is a
    different question. A symbol-day is KEPT if at least one signal on it
    survives the wait rule -- either the first signal is 09:45 or later, or the
    higher timeframe agrees with some signal on that chart.
    """
    import marks_pool                                  # read-only, every corpus
    pool = marks_pool.canonical_pool()
    s_keys = marks_pool.s_days(pool)

    bysd = defaultdict(list)
    for day, v in byday.items():
        for r in v:
            bysd["%s_%s" % (r["sym"], day)].append(r)
    for v in bysd.values():
        v.sort(key=ekey)

    reached = sorted(k for k in s_keys if k in bysd)
    early = sum(1 for k in reached if bysd[k][0]["et"] < EARLY_CUTOFF)
    out = {
        "s_days_total": len(s_keys),
        "s_days_the_book_trades": len(reached),
        "of_those_first_entry_before_0945": early,
        "of_those_first_entry_before_0945_pct":
            round(100 * early / len(reached), 1) if reached else 0.0,
        "by_candidate": {},
    }
    for name in CANDIDATES:
        kept = []
        for k in reached:
            v = bysd[k]
            if v[0]["et"] >= EARLY_CUTOFF or any(agrees(name, feats[id(r)]) for r in v):
                kept.append(k)
        out["by_candidate"][name] = {
            "s_days_kept": len(kept),
            "s_days_lost": len(reached) - len(kept),
            "kept_pct": round(100 * len(kept) / len(reached), 1) if reached else 0.0,
        }
    return out


# -------------------------------------------- cross-check vs his stated minutes
#
# The 21 minutes and the four exclusions are lifted verbatim from
# research/g81_marks30_score.py's STATED table so the two files cannot drift.
# Four notes contain a clock time that is NOT his entry -- twice he names the
# minute the ENGINE picked, once a candle, once a hypothetical break -- and
# folding those in would score the engine against itself.

NOT_HIS_ENTRY = {
    "MSFT_2024-09-13": 'names the engine\'s minute: "9:47 is what you liked"',
    "QQQ_2025-12-22": 'names the engine\'s minute: "9:45 its close i see what your seeing"',
    "TSM_2025-11-26": 'names a candle, not an entry: "the green candle at 9:35"',
    "AVGO_2025-12-03": 'a hypothetical break he rejects: "9:33 can be a great break"',
}
TIME_RE = re.compile(r"\b(\d{1,2})[:%](\d{2})\b")


def stated_minutes(path=MARKS30):
    """{card_id: 'HH:MM'} -- his own entry minute, yes-cards only."""
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        cid = row["card_id"]
        if cid in NOT_HIS_ENTRY:
            continue
        if (row.get("answers", {}).get("is_s") or [None])[0] != "yes":
            continue
        note = " ".join(str(x) for x in (row.get("notes") or {}).values())
        m = TIME_RE.search(note)
        if not m:
            continue
        hh, mm = int(m.group(1)), int(m.group(2))
        if "%" in m.group(0):                 # IWM "9:%5" -- shift held on the 5
            mm = 55
        out[cid] = "%02d:%02d" % (hh, mm)
    return out


def step5_cross_check(blob, all_rows):
    """On his late minutes, does the candidate explain the wait?"""
    said = stated_minutes()
    # EVERY signal the engine emitted on that chart, not only the traded ones.
    # The question is "does the candidate explain his wait", and to answer it
    # the candidate needs a signal to judge -- 25 of these 30 cards were
    # signals the engine refused to trade (research/g81_marks30_score.md), so
    # restricting to the traded stream leaves nothing to compare.
    bysd = defaultdict(list)
    for r in all_rows:
        bysd["%s_%s" % (r["sym"], r["day"])].append(r)
    for v in bysd.values():
        v.sort(key=ekey)

    cards, tally = [], defaultdict(lambda: {"explained": 0, "contradicted": 0, "unknown": 0})
    for cid, minute in sorted(said.items()):
        sym, day = cid.rsplit("_", 1)
        rec = {"card": cid, "his_minute": minute, "late": minute > "09:35"}
        v = bysd.get(cid, [])
        rec["engine_signals"] = [r["et"] for r in v]
        earlier = [r for r in v if r["et"] < minute]
        near = [r for r in v if abs((int(r["et"][:2]) * 60 + int(r["et"][3:5]))
                                    - (int(minute[:2]) * 60 + int(minute[3:5]))) <= 5]
        rec["had_earlier_signal"] = bool(earlier)
        # Directionless clarity read: was the index unclear at the earliest
        # signal and clear by his minute? This needs no trade direction, so it
        # is answerable on all of them.
        d_first, p_first = (index_dir(blob, day, v[0]["et"]) if v else ("n/a", None))
        d_his, p_his = index_dir(blob, day, minute)
        rec["index_at_first_signal"] = d_first
        rec["index_at_his_minute"] = d_his
        rec["index_clarified_by_his_minute"] = (d_first == "flat" and d_his != "flat")
        for name in CANDIDATES:
            if not rec["late"]:
                tally[name]["unknown"] += 1
                rec[name] = "not late"
                continue
            if not earlier or not near:
                tally[name]["unknown"] += 1
                rec[name] = "no comparable pair"
                continue
            fe = row_features(blob, earlier[0])
            fn = row_features(blob, near[0])
            if not agrees(name, fe) and agrees(name, fn):
                tally[name]["explained"] += 1
                rec[name] = "explains the wait"
            elif agrees(name, fe):
                tally[name]["contradicted"] += 1
                rec[name] = "would have taken the earlier one"
            else:
                tally[name]["unknown"] += 1
                rec[name] = "silent at both"
        cards.append(rec)
    n_earlier = sum(1 for c in cards if c["had_earlier_signal"])
    early = sum(1 for m in said.values() if m < EARLY_CUTOFF)
    at_or_before = sum(1 for m in said.values() if m <= EARLY_CUTOFF)
    return {"n_stated": len(said), "n_late": sum(1 for c in cards if c["late"]),
            "cards_with_an_earlier_engine_signal": n_earlier,
            "his_minutes_before_0945": early,
            "his_minutes_at_or_before_0945": at_or_before,
            "his_minutes_before_0945_pct": round(100 * early / len(said), 1) if said else 0.0,
            "tally": {k: dict(v) for k, v in tally.items()}, "cards": cards,
            "excluded": NOT_HIS_ENTRY}


# ------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=BOOK)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out", default=OUT_JSON)
    args = ap.parse_args()

    meta, rows = load_book(args.book)
    n_days = meta["sessions"]
    byday = candidates(rows)
    print("book %s   sessions %d   candidates %d over %d days"
          % (meta["generated"], n_days, sum(len(v) for v in byday.values()), len(byday)))

    print("\n== STEP 1: the prize, no model ==")
    prize = step1_prize(byday, n_days)
    for k in ("first", "best", "worst"):
        s = prize[k]
        print("  %-6s $%6d/day  mean R %+0.3f  win %4.1f%%" %
              (k, s["per_day"], s["mean_r"], s["win_pct"]))
    print("  coin flip among the day's candidates: $%d/day" % prize["coinflip_per_day"])
    print("  gap first->best: $%d/day" % prize["gap_per_day"])
    print("  first IS best on %d of %d days (%.1f%%); chance alone would be %.1f%%"
          % (prize["first_is_best_days"], prize["days"], prize["first_is_best_pct"],
             prize["chance_is_best_pct"]))

    days_needed = set(byday)
    syms_needed = {r["sym"] for v in byday.values() for r in v}
    blob = load_cache(days_needed, syms_needed, use_cache=not args.no_cache)

    feats = {}
    for v in byday.values():
        for r in v:
            feats[id(r)] = row_features(blob, r)

    print("\n== STEP 2: does alignment separate a good signal from a bad one? ==")
    info = step2_signal_information(byday, feats)
    for name, d in info.items():
        sp = d["agrees_vs_disagrees"]
        if sp:
            print("  %-24s agrees %+0.3fR (n=%d) vs disagrees %+0.3fR (n=%d)  diff %+0.3fR  95%% %s"
                  % (name, sp["agrees_mean_r"], sp["n_agrees"], sp["disagrees_mean_r"],
                     sp["n_disagrees"], sp["difference_r"], sp["ci95_r"]))
        else:
            print("  %-24s %s" % (name, "  ".join(
                "%s of 4: %+0.3fR (n=%d)" % (k, b["mean_r"], b["n"])
                for k, b in d["by_score"].items())))

    print("\n== STEP 3: each candidate as a SELECTOR ==")
    sel = step3_selector(byday, feats, n_days)
    print("  %-24s %8s %8s %10s %14s" % ("", "hit-best", "$/day", "vs base", "95% band"))
    for name, st in sel.items():
        print("  %-24s %7.1f%% %8d %10d   %s" %
              (name, st["hit_best_pct"], st["per_day"], st["vs_baseline_per_day"], st["ci95"]))

    print("\n== STEP 4: each candidate as a WAIT rule ==")
    wait, _ = step4_wait(byday, feats, n_days)
    print("  %-24s %6s %6s %6s %8s %8s %10s" %
          ("", "trades", "moved", "skips", "$/day", "months", "vs base"))
    for name, st in wait.items():
        print("  %-24s %6d %6d %6d %8d %5d/%-3d %9d  %s" %
              (name, st.get("trades", 0), st["days_moved"], st["days_skipped"],
               st["per_day"], st.get("months_green", 0), st.get("months", 0),
               st["vs_baseline_per_day"], st["ci95"]))

    print("\n== STEP 4b: what the wait rule costs on his S days ==")
    recall = s_day_recall(byday, feats)
    print("  S days in the pool %d; the book reaches %d of them; %d (%.1f%%) enter before 09:45"
          % (recall["s_days_total"], recall["s_days_the_book_trades"],
             recall["of_those_first_entry_before_0945"],
             recall["of_those_first_entry_before_0945_pct"]))
    for name, st in recall["by_candidate"].items():
        print("  %-24s keeps %3d, loses %3d (%.1f%% kept)"
              % (name, st["s_days_kept"], st["s_days_lost"], st["kept_pct"]))

    print("\n== STEP 5: against the minutes he wrote ==")
    cross = step5_cross_check(blob, rows)
    print("  %d stated minutes, %d of them later than 09:35; %d (%.1f%%) are before 09:45"
          % (cross["n_stated"], cross["n_late"], cross["his_minutes_before_0945"],
             cross["his_minutes_before_0945_pct"]))
    for name, t in cross["tally"].items():
        print("  %-24s explains %d, contradicts %d, silent/unpaired %d"
              % (name, t["explained"], t["contradicted"], t["unknown"]))
    print("  on %d of %d the engine had ANY signal earlier than his minute -- "
          "on the rest there is nothing for a wait rule to have rejected"
          % (cross["cards_with_an_earlier_engine_signal"], cross["n_stated"]))
    clar = sum(1 for c in cross["cards"] if c["index_clarified_by_his_minute"])
    print("  index was unclear at the engine's first signal and clear by his minute: %d of %d"
          % (clar, cross["n_stated"]))

    # deadband sensitivity for the index candidate, so the 0.05% cannot hide
    sens = {}
    for db, key in ((0.00, "index0"), (0.05, "index"), (0.10, "index10")):
        picks = {}
        for d, v in byday.items():
            sc = [(1 if feats[id(r)][key] == feats[id(r)]["want"]
                   else (0 if feats[id(r)][key] == "flat" else -1)) for r in v]
            m = max(sc)
            picks[d] = v[sc.index(m)]
        sens["%.2f%%" % db] = book_stats(list(picks.values()), n_days)["per_day"]
    print("\n  index deadband sensitivity ($/day as a selector): %s" % sens)

    out = {"book": {"generated": meta["generated"], "sessions": n_days,
                    "signals": meta["signals"], "traded": meta["traded"]},
           "risk_dollars": RISK, "early_cutoff": EARLY_CUTOFF,
           "index_deadband_pct": DEADBAND, "index_note": INDEX_NOTE,
           "candidates": CANDIDATES, "step1_prize": prize, "step3_selector": sel,
           "step2_signal_information": info,
           "step4_wait": wait, "step4b_recall": recall, "step5_cross_check": cross,
           "index_deadband_sensitivity": sens}
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()
