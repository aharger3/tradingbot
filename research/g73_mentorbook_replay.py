"""g73_mentorbook_replay.py — the mentor book, built honestly.

Austin, 2026-08-29: "we need to figure out why scarface and jdub average higher,
if you can collect all there trade reviews and put them in there own backtest to
pool the results."

Two things get built here, and they are NOT the same thing:

  A. **The OMEN-on-mentor-days book.** For every pooled mentor instance whose
     (symbol, session) the two-year book already replayed, book OMEN's own
     traded signals for that symbol-day. That is the like-for-like question:
     *if OMEN traded the days Scarface called, how would it do?* No engine
     re-run: `research/bt2y_trades.json` IS the OMEN replay of those sessions
     (backtest_2y.py -> backtest_week.simulate_day), so joining to it is the
     same engine, same stop rule, same exits, and it is reproducible.

  B. **The synthetic mentor trade.** Only 49 of 3,547 instances state an entry
     price and 19 a stop, so a mentor's own P&L cannot be computed. What CAN be
     computed is: from the minute the mentor posted, in the direction he stated,
     with a risk unit taken from the tape (ATR of the 15 bars BEFORE the post,
     so no hindsight), does a 2R bracket win? Exits follow OMEN's own risk model
     -- resting disaster stop at -1R on touch (stop_rule.disaster_stop_hit),
     target at +2R on touch, else marked out at the close of the session.
     This is the only instrument that can test the mentors' claimed results
     against the tape.

Reads only. Writes research/g73_mentorbook_data.json. No mark file is opened,
nothing is pulled from the network (cache-first bars only; days with no CSV on
disk are skipped and counted).

Run: python research/g73_mentorbook_replay.py
"""
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf                                    # noqa: E402
from stop_rule import disaster_stop_hit, disaster_stop_price  # noqa: E402
POOL = ROOT / "research" / "corpus_sf" / "pooled_trades.jsonl"
BOOK = ROOT / "research" / "bt2y_trades.json"
OUT = ROOT / "research" / "g73_mentorbook_data.json"
ARCHIVE = ROOT / "data_archive"

RISK_DOLLARS = 1000.0
TARGET_R = 2.0          # every OMEN row plans exactly 2.000 R:R
ATR_LOOKBACK = 15       # bars before the post minute, hindsight-free
MIN_ATR_PCT = 0.0005    # floor the risk unit at 5bp of price (degenerate quiet bars)


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------
def load_pool():
    return [json.loads(l) for l in POOL.open(encoding="utf-8") if l.strip()]


def load_book():
    d = json.loads(BOOK.read_text(encoding="utf-8"))
    return d["meta"], d["trades"]


def has_csv(sym, day):
    return (ARCHIVE / sym / f"{day}.csv").exists()


_BARS = {}


def rth_bars(sym, day):
    """Cache-first RTH bars. Returns [] rather than reaching the network."""
    key = (sym, day)
    if key not in _BARS:
        _BARS[key] = pf.rth(pf.fetch_day(sym, day)) if has_csv(sym, day) else []
    return _BARS[key]


# ---------------------------------------------------------------------------
# B. the synthetic mentor trade
# ---------------------------------------------------------------------------
def atr(bars, i, n=ATR_LOOKBACK):
    """True range mean over the n bars ending at i-1. No bar at or after i."""
    lo = max(1, i - n)
    if i - lo < 3:
        return None
    trs = []
    for j in range(lo, i):
        p = bars[j - 1].close
        trs.append(max(bars[j].high - bars[j].low,
                       abs(bars[j].high - p), abs(bars[j].low - p)))
    return statistics.fmean(trs) if trs else None


def synth_trade(bars, i, long):
    """A 2R bracket entered on the close of bar i, risk = ATR(15) before i.

    Disaster stop rests at -1R and fills on TOUCH (stop_rule); target at +2R
    fills on touch; anything still open at the last RTH bar is marked out at
    that close. Returns dict or None.
    """
    if i is None or i < ATR_LOOKBACK or i >= len(bars) - 5:
        return None
    a = atr(bars, i)
    entry = bars[i].close
    if not a or not entry:
        return None
    risk = max(a, MIN_ATR_PCT * entry)
    stop = disaster_stop_price(entry, risk, long)
    target = entry + TARGET_R * risk if long else entry - TARGET_R * risk
    mfe = mae = 0.0
    for j in range(i + 1, len(bars)):
        c = bars[j]
        up = (c.high - entry) if long else (entry - c.low)
        dn = (c.low - entry) if long else (entry - c.high)
        mfe = max(mfe, up / risk)
        mae = min(mae, dn / risk)
        hit_stop = disaster_stop_hit(c.high, c.low, stop, long)
        hit_tgt = (c.high >= target) if long else (c.low <= target)
        if hit_stop and hit_tgt:
            # same bar: the loss is assumed first (no intrabar sequence on 1m)
            return dict(r=-1.0, out="loss", bars=j - i, mfe=mfe, mae=mae,
                        risk_pct=risk / entry * 100, ambiguous=True)
        if hit_stop:
            return dict(r=-1.0, out="loss", bars=j - i, mfe=mfe, mae=mae,
                        risk_pct=risk / entry * 100, ambiguous=False)
        if hit_tgt:
            return dict(r=TARGET_R, out="win", bars=j - i, mfe=mfe, mae=mae,
                        risk_pct=risk / entry * 100, ambiguous=False)
    last = bars[-1].close
    r = ((last - entry) if long else (entry - last)) / risk
    return dict(r=round(r, 4), out="eod", bars=len(bars) - 1 - i, mfe=mfe,
                mae=mae, risk_pct=risk / entry * 100, ambiguous=False)


def bar_index_for_minute(bars, et_minute):
    """et_minute is minutes past midnight ET. RTH bar 0 is 09:30 = 570."""
    if et_minute is None:
        return None
    k = int(et_minute) - 570
    if k < 0 or k >= len(bars):
        return None
    return k


# ---------------------------------------------------------------------------
# stats helpers
# ---------------------------------------------------------------------------
def agg(rs):
    if not rs:
        return dict(n=0, win=None, mean_r=None, dollars=None, total=None)
    wins = sum(1 for r in rs if r > 0)
    m = statistics.fmean(rs)
    return dict(n=len(rs), win=round(wins / len(rs) * 100, 1),
                mean_r=round(m, 4), dollars=round(m * RISK_DOLLARS, 2),
                total=round(sum(rs) * RISK_DOLLARS, 2))


def boot_ci(rs, n=2000, seed=73):
    import random
    if len(rs) < 5:
        return None
    rng = random.Random(seed)
    ms = []
    for _ in range(n):
        ms.append(statistics.fmean(rng.choices(rs, k=len(rs))))
    ms.sort()
    return [round(ms[int(.025 * n)], 4), round(ms[int(.975 * n)], 4)]


def main():
    pool = load_pool()
    meta, book = load_book()
    bsyms, first, last = set(meta["symbols"]), meta["first"], meta["last"]

    # OMEN's book, indexed by symbol-day (traded signals only)
    by_day = defaultdict(list)
    for t in book:
        if t["traded"]:
            by_day[(t["sym"], t["day"])].append(t)
    all_book_days = {(t["sym"], t["day"]) for t in book}

    # ---- funnel from 3,547 pooled instances to what can actually be replayed
    funnel = Counter()
    inst = []
    for r in pool:
        funnel["pooled"] += 1
        if r.get("instrument") == "futures":
            funnel["futures — no data product"] += 1
            continue
        sym, day = r.get("symbol"), r.get("trade_date")
        if not sym or not day:
            funnel["no symbol or date"] += 1
            continue
        if sym not in bsyms:
            funnel["symbol not in OMEN universe"] += 1
            continue
        if not (first <= day <= last):
            funnel["outside the 2y book window"] += 1
            continue
        if (sym, day) not in all_book_days:
            funnel["book saw no setup at all that day"] += 1
            continue
        funnel["replayable"] += 1
        inst.append(r)

    called_days = {(r["symbol"], r["trade_date"]) for r in inst}

    # ---- A. OMEN on mentor days vs OMEN everywhere else
    on_called, off_called = [], []
    for k, ts in by_day.items():
        tgt = on_called if k in called_days else off_called
        tgt += [t["r"] for t in ts]
    A = dict(called_symbol_days=len(called_days),
             called_days_omen_traded=sum(1 for k in called_days if k in by_day),
             on=agg(on_called), off=agg(off_called),
             on_ci=boot_ci(on_called), off_ci=boot_ci(off_called))

    # one-trade-a-day (first traded signal of each session, account-wide),
    # restricted to sessions where a mentor called something
    first_of_day = {}
    for t in book:
        if not t["traded"]:
            continue
        k = t["day"]
        if k not in first_of_day or t["et"] < first_of_day[k]["et"]:
            first_of_day[k] = t
    called_sessions = {d for _, d in called_days}
    A["otd_all"] = agg([t["r"] for t in first_of_day.values()])
    A["otd_called_sessions"] = agg([t["r"] for d, t in first_of_day.items()
                                    if d in called_sessions])

    # ---- direction agreement, and OMEN's result when it agreed
    agree, disagree, omen_silent = [], [], 0
    dir_tab = Counter()
    for r in inst:
        md = r.get("direction")
        ts = by_day.get((r["symbol"], r["trade_date"]), [])
        if not ts:
            omen_silent += 1
            continue
        if md not in ("long", "short"):
            continue
        want = "call" if md == "long" else "put"
        for t in ts:
            dir_tab[(md, t["dir"])] += 1
            (agree if t["dir"] == want else disagree).append(t["r"])
    A["dir_agree"] = agg(agree)
    A["dir_disagree"] = agg(disagree)
    A["dir_table"] = {f"{a}->{b}": n for (a, b), n in dir_tab.items()}
    A["mentor_called_omen_silent_days"] = omen_silent

    # per-mentor: OMEN's book on the days that mentor called
    per_mentor = {}
    by_author = defaultdict(set)
    for r in inst:
        by_author[r.get("author") or "?"].add((r["symbol"], r["trade_date"]))
    for au, days in by_author.items():
        rs = [t["r"] for d in days for t in by_day.get(d, [])]
        if len(days) >= 20:
            per_mentor[au] = dict(called_days=len(days),
                                  omen_traded_days=sum(1 for d in days if d in by_day),
                                  **agg(rs))
    A["per_mentor"] = dict(sorted(per_mentor.items(),
                                  key=lambda kv: -kv[1]["called_days"]))

    # ---- B. the synthetic mentor trade, on every replayable instance with a
    # stated direction and a post minute inside RTH
    synth = []
    skipped = Counter()
    for r in inst:
        md = r.get("direction")
        if md not in ("long", "short"):
            skipped["no stated direction"] += 1
            continue
        bars = rth_bars(r["symbol"], r["trade_date"])
        if len(bars) < 60:
            skipped["no bars on disk"] += 1
            continue
        i = bar_index_for_minute(bars, r.get("et_minute"))
        if i is None:
            skipped["posted outside 09:30-16:00"] += 1
            continue
        s = synth_trade(bars, i, md == "long")
        if s is None:
            skipped["too late in session / flat tape"] += 1
            continue
        s.update(symbol=r["symbol"], day=r["trade_date"], author=r.get("author"),
                 src=r.get("primary_src"), claimed=r.get("outcome"),
                 conf=r.get("confidence"), direction=md,
                 et_minute=r.get("et_minute"), setup=r.get("setup"),
                 quote_len=len(r.get("quote") or ""))
        synth.append(s)
    B = dict(n=len(synth), skipped=dict(skipped))

    def slice_synth(pred):
        rs = [s["r"] for s in synth if pred(s)]
        return dict(**agg(rs), ci=boot_ci(rs),
                    mfe=round(statistics.fmean([s["mfe"] for s in synth if pred(s)]), 3)
                    if rs else None)

    B["all"] = slice_synth(lambda s: True)
    B["claimed_win"] = slice_synth(lambda s: s["claimed"] == "win")
    B["claimed_loss"] = slice_synth(lambda s: s["claimed"] == "loss")
    B["claimed_be"] = slice_synth(lambda s: s["claimed"] == "be")
    B["claimed_none"] = slice_synth(lambda s: s["claimed"] is None)
    B["by_src"] = {}
    for src in sorted({s["src"] for s in synth}):
        B["by_src"][src] = {
            "all": slice_synth(lambda s, x=src: s["src"] == x),
            "claimed_win": slice_synth(lambda s, x=src: s["src"] == x and s["claimed"] == "win"),
            "claimed_loss": slice_synth(lambda s, x=src: s["src"] == x and s["claimed"] == "loss"),
            "unreported": slice_synth(lambda s, x=src: s["src"] == x and s["claimed"] is None),
        }
    B["by_author"] = {}
    au_ct = Counter(s["author"] for s in synth)
    for au, n in au_ct.most_common():
        if n < 20:
            continue
        B["by_author"][au] = {
            "all": slice_synth(lambda s, x=au: s["author"] == x),
            "claimed_win": slice_synth(lambda s, x=au: s["author"] == x and s["claimed"] == "win"),
            "unreported": slice_synth(lambda s, x=au: s["author"] == x and s["claimed"] is None),
        }

    # ---- C. reporting rate — the survivorship test that needs no bars at all
    C = {}
    for scope, rows in (("all pooled", pool),
                        ("replayable", inst)):
        d = {}
        for src in sorted({r["primary_src"] for r in rows}):
            g = [r for r in rows if r["primary_src"] == src]
            oc = Counter(r.get("outcome") for r in g)
            stated = oc["win"] + oc["loss"] + oc["be"]
            d[src] = dict(instances=len(g), stated=stated,
                          report_rate=round(stated / len(g) * 100, 1),
                          win=oc["win"], loss=oc["loss"], be=oc["be"],
                          claimed_win_rate=round(oc["win"] / (oc["win"] + oc["loss"]) * 100, 1)
                          if (oc["win"] + oc["loss"]) else None,
                          silent=len(g) - stated)
        C[scope] = d
    # per author, all pooled
    ca = {}
    for au, n in Counter(r.get("author") for r in pool).most_common():
        if n < 25:
            continue
        g = [r for r in pool if r.get("author") == au]
        oc = Counter(r.get("outcome") for r in g)
        stated = oc["win"] + oc["loss"] + oc["be"]
        ca[au] = dict(instances=n, stated=stated,
                      report_rate=round(stated / n * 100, 1),
                      win=oc["win"], loss=oc["loss"],
                      claimed_win_rate=round(oc["win"] / (oc["win"] + oc["loss"]) * 100, 1)
                      if (oc["win"] + oc["loss"]) else None)
    C["by_author"] = ca

    # ---- D. entry timing — when they post vs when OMEN enters
    mins = [r["et_minute"] - 570 for r in inst
            if r.get("et_minute") and 570 <= r["et_minute"] < 960]
    omen_mins = [(int(t["et"][:2]) * 60 + int(t["et"][3:5])) - 570
                 for t in book if t["traded"]]
    D = dict(mentor_median_min_after_open=statistics.median(mins) if mins else None,
             mentor_n=len(mins),
             omen_median_min_after_open=statistics.median(omen_mins),
             omen_n=len(omen_mins),
             mentor_pct_in_first_90=round(sum(1 for m in mins if m <= 90) / len(mins) * 100, 1) if mins else None,
             omen_pct_in_first_90=round(sum(1 for m in omen_mins if m <= 90) / len(omen_mins) * 100, 1))
    # synthetic result by time-of-day bucket — is timing where the edge is?
    D["synth_by_slot"] = {}
    for lo, hi, name in ((0, 30, "09:30-10:00"), (30, 60, "10:00-10:30"),
                         (60, 90, "10:30-11:00"), (90, 180, "11:00-12:30"),
                         (180, 390, "12:30-16:00")):
        D["synth_by_slot"][name] = slice_synth(
            lambda s, a=lo, b=hi: a <= (s["et_minute"] - 570) < b)

    # ---- E. symbol selection
    E = {}
    msym = Counter(r["symbol"] for r in inst)
    osym = Counter(t["sym"] for t in book if t["traded"])
    for sym in sorted(set(msym) | set(osym)):
        rs = [t["r"] for t in book if t["traded"] and t["sym"] == sym]
        E[sym] = dict(mentor_instances=msym.get(sym, 0),
                      omen_trades=osym.get(sym, 0),
                      omen_mean_r=round(statistics.fmean(rs), 4) if rs else None)

    out = dict(generated_by="research/g73_mentorbook_replay.py",
               book_meta={k: meta[k] for k in ("generated", "first", "last",
                                               "sessions", "signals", "traded")},
               funnel=dict(funnel), A_omen_on_mentor_days=A,
               B_synthetic_mentor_trade=B, C_reporting_rate=C,
               D_timing=D, E_symbols=E,
               # every synthetic trade, one row each, so downstream rigs
               # (g73_mentorbook_why.py) re-slice these WITHOUT re-deriving them
               _synth_rows=synth)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", OUT)
    for k, v in funnel.items():
        print(f"  {k:38s} {v:5d}")
    print("A  OMEN on mentor days :", A["on"])
    print("A  OMEN elsewhere      :", A["off"])
    print("B  synthetic all       :", B["all"])
    print("B  claimed win         :", B["claimed_win"])
    print("B  claimed loss        :", B["claimed_loss"])
    print("B  never reported      :", B["claimed_none"])


if __name__ == "__main__":
    main()
