"""E4 (OMEN canon section 5): does Austin's own 8-variable rubric reproduce his letter grades?

Scores every row of v3-s-dataset/s_trades.csv (266 stock S / one-off / two-off marks matched to
engine signals, 1-min bars 09:30-11:00) with the rubric as he stated it, then compares with his grade.
Paper research only. Not investment advice. Nothing here fits anything: the PRIMARY spec is fixed
before any row is scored, and GRID is a declared sensitivity table (max 34 variants, all reported).

Rubric sources (vault Projects/omen-rulebook.md):
  2026-08-23  grade = S - (downgrades tripped) + (BR+OCR confluence bonus); S=0, A=1, C=2, 3+ floors at C.
              eight variables; displacement exempt under BR+OCR confluence.
  2026-08-27  a2 "put a number on it, 2" (level respect), a5 "lets say 2" (counter-trend), b11 STALE_BARS=10,
              b6 optional ninth variable (75% body candle inside its neighbours), b5 second +1 (needs
              PDH/PDL/PMH/PML, which the 09:30-11:00 bars cannot supply -> NOT scorable here).
The canon calls a2/a5 "weights"; the rulebook uses them as counts. PRIMARY follows the rulebook (counts);
the weight reading is the w2 grid axis.
Every other threshold is a first guess carried over unchanged from research/downgrade.py (not fitted).
"""
from __future__ import annotations

import argparse, csv, gzip, json, os, random, statistics as st
from collections import Counter, defaultdict
from dataclasses import dataclass, replace

# ---- constants (guesses carried over from research/downgrade.py; Austin set only the ones marked) ----
DISP_BODY_MULT = 1.5     # break-candle body vs avg body of the 10 bars before it (guess)
REJECT_BARS = 2          # bars after the break in which a close back through = rejection (guess)
EXHAUSTED_ATR = 10.0     # |close - session open| in ATR that counts as spent (guess)
ATR_WINDOW = 14
OCR_LOOKBACK = 20
LARGE_BODY_FRAC = 0.75   # Austin (b6)
LARGE_BODY_WINDOW = 12
LARGE_BODY_CONTAIN = 3
CHASE_PCT = 0.005        # R22, added 08-29 (after the 08-23/08-27 rubric); extra variant only
COUNTER_WINDOW = 12

VARIABLES = ("no_displacement", "stale_retest", "level_not_respected", "exhausted",
             "counter_trend_not_respected", "break_then_rejection", "no_retest", "ocr_not_respected")
TIER = {"S": 0, "A": 1, "C": 2}
HIS_MAP = {"S": "S", "one-off": "A", "two-off": "C", "A": "A", "C": "C"}


@dataclass(frozen=True)
class Spec:
    t3: int = 2                       # closes through the level that trip "level not respected" (a2)
    t5: int = 2                       # un-bought-back counter candles that trip variable 5 (a5)
    w2: bool = False                  # weight reading: level (3) and counter-trend (5) cost 2 downgrades each
    disp_exempt: bool = True          # displacement downgrade forgiven under BR+OCR confluence (08-23 / q18)
    ninth: bool = False               # b6 ninth downgrade
    chase: bool = False               # R22 chase downgrade (extra variant)
    nobreak_trips_disp: bool = False  # engine convention: no identifiable break = "no displacement"
    counter_post_break: bool = False  # variable 5 looks only at bars after the break, not the last 12
    stale: int = 10                   # STALE_BARS (Austin, b11)
    start: int = 1                    # first bar index a break may occur on (5 for OR levels: they lock at 09:35)


def _name(sp):
    return "t3=%d|w2=%d|ex=%d|b6=%d|cpb=%d" % (sp.t3, sp.w2, sp.disp_exempt, sp.ninth, sp.counter_post_break)


PRIMARY = _name(Spec())
GRID = [(_name(Spec(t3=a, w2=b, disp_exempt=c, ninth=d, counter_post_break=e)),
         Spec(t3=a, w2=b, disp_exempt=c, ninth=d, counter_post_break=e))
        for a in (2, 1) for b in (False, True) for c in (True, False) for d in (False, True) for e in (False, True)]
GRID += [("P0+chase", Spec(chase=True)), ("P0+nobreak-trips-disp", Spec(nobreak_trips_disp=True))]
MAX_VARIANTS = 34
GRID.sort(key=lambda kv: (kv[0] != PRIMARY, kv[0]))


# ---------------------------------------------------------------------------------------------- bar helpers
def _body(b): return abs(b["c"] - b["o"])
def _rng(b): return b["h"] - b["l"]
def _up(b): return b["c"] >= b["o"]


def _atr(bars, i):
    rows = bars[max(1, i - ATR_WINDOW + 1):i + 1]
    return sum(_rng(b) for b in rows) / len(rows) if rows else 0.0


def _eps(bars, i):
    return 0.25 * _atr(bars, i)


def break_bar(bars, i, level, is_long, start=1):
    """The FIRST bar (index >= start, up to the entry bar) whose close crossed the level; None if price never
    crossed. First, not most recent: a close back through followed by a re-cross must stay visible to
    'level not respected' and 'break then rejection' (the most-recent rule hid both)."""
    for j in range(max(1, start), i + 1):
        p, c = bars[j - 1]["c"], bars[j]["c"]
        if (p <= level < c) if is_long else (p >= level > c):
            return j
    return None


def _retest_bar(bars, i, level, is_long, after):
    e = _eps(bars, i)
    for j in range(after + 1, i + 1):
        if (bars[j]["l"] <= level + e) if is_long else (bars[j]["h"] >= level - e):
            return j
    return None


# ---------------------------------------------------------------------------------------------- the variables
def no_displacement(bars, i, level, is_long, sp):
    br = break_bar(bars, i, level, is_long, sp.start)
    if br is None:
        return sp.nobreak_trips_disp
    prior = bars[max(0, br - 10):br]
    avg = sum(_body(b) for b in prior) / len(prior) if prior else 0.0
    return False if avg <= 0 else _body(bars[br]) < DISP_BODY_MULT * avg


def stale_retest(bars, i, level, is_long, sp):
    br = break_bar(bars, i, level, is_long, sp.start)
    if br is None:
        return False
    rt = _retest_bar(bars, i, level, is_long, br)
    return rt is not None and (rt - br) > sp.stale


def level_not_respected(bars, i, level, is_long, sp):
    """a2/a3: wicks through the level are fine; only CLOSES through it count. Trips at sp.t3 closes."""
    br = break_bar(bars, i, level, is_long, sp.start)
    if br is None:
        return False
    n = sum(1 for j in range(br + 1, i + 1) if ((bars[j]["c"] < level) if is_long else (bars[j]["c"] > level)))
    return n >= sp.t3


def exhausted(bars, i, level, is_long, sp):
    a = _atr(bars, i)
    return a > 0 and abs(bars[i]["c"] - bars[0]["o"]) >= EXHAUSTED_ATR * a


def counter_trend_not_respected(bars, i, level, is_long, sp):
    lo = max(1, i - COUNTER_WINDOW)
    if sp.counter_post_break:
        br = break_bar(bars, i, level, is_long, sp.start)
        if br is None:
            return False
        lo = max(lo, br + 1)
    bad = 0
    for j in range(lo, i):
        b = bars[j]
        if not ((not _up(b)) if is_long else _up(b)):
            continue
        rec = any((bars[k]["c"] > b["h"]) if is_long else (bars[k]["c"] < b["l"])
                  for k in range(j + 1, min(j + 3, i + 1)))
        if not rec:
            bad += 1
    return bad >= sp.t5


def break_then_rejection(bars, i, level, is_long, sp):
    br = break_bar(bars, i, level, is_long, sp.start)
    if br is None:
        return False
    return any(((bars[j]["c"] < level) if is_long else (bars[j]["c"] > level))
               for j in range(br + 1, min(br + 1 + REJECT_BARS, i + 1)))


def no_retest(bars, i, level, is_long, sp):
    br = break_bar(bars, i, level, is_long, sp.start)
    return br is not None and _retest_bar(bars, i, level, is_long, br) is None


def find_ocr(bars, i, is_long, lookback=OCR_LOOKBACK):
    """Most recent ISOLATED counter-coloured candle before the entry bar (neighbours are trend-coloured)."""
    for j in range(i - 1, max(1, i - lookback) - 1, -1):
        b = bars[j]
        if not ((not _up(b)) if is_long else _up(b)):
            continue
        left = _up(bars[j - 1]) if is_long else (not _up(bars[j - 1]))
        right = _up(bars[j + 1]) if is_long else (not _up(bars[j + 1]))
        if left and right:
            return j
    return None


def ocr_not_respected(bars, i, level, is_long, sp=None):
    j = find_ocr(bars, i, is_long)
    if j is None:
        return False
    edge = bars[j]["l"] if is_long else bars[j]["h"]
    return any(((bars[k]["c"] < edge) if is_long else (bars[k]["c"] > edge)) for k in range(j + 1, i + 1))


def has_confluence(bars, i, level, is_long, sp=None):
    """BR + OCR: a break exists, an isolated OCR exists whose far edge could hold a stop, and it was honoured."""
    if break_bar(bars, i, level, is_long, sp.start if sp else 1) is None:
        return False
    j = find_ocr(bars, i, is_long)
    if j is None:
        return False
    edge = bars[j]["l"] if is_long else bars[j]["h"]
    usable = (edge <= bars[i]["c"]) if is_long else (edge >= bars[i]["c"])
    return usable and not ocr_not_respected(bars, i, level, is_long)


def large_counter_body(bars, i, level, is_long, sp=None):
    base = max(0, i - LARGE_BODY_WINDOW)
    for j in range(base, i + 1):
        b = bars[j]
        r = _rng(b)
        if r <= 0 or not ((not _up(b)) if is_long else _up(b)) or _body(b) / r < LARGE_BODY_FRAC:
            continue
        nb = [bars[k] for k in range(max(0, j - LARGE_BODY_CONTAIN), min(i, j + LARGE_BODY_CONTAIN) + 1) if k != j]
        if nb and b["h"] <= max(x["h"] for x in nb) and b["l"] >= min(x["l"] for x in nb):
            return True
    return False


def chase(bars, i, level, is_long):
    px = bars[i]["c"]
    return bool(px) and ((px - level) if is_long else (level - px)) / px >= CHASE_PCT


_CHECKS = {"no_displacement": no_displacement, "stale_retest": stale_retest,
           "level_not_respected": level_not_respected, "exhausted": exhausted,
           "counter_trend_not_respected": counter_trend_not_respected,
           "break_then_rejection": break_then_rejection, "no_retest": no_retest,
           "ocr_not_respected": ocr_not_respected}


def trips(bars, i, level, is_long, sp):
    """Names of the downgrade variables that fire on the entry bar (raw: no exemption, no weights)."""
    out = [n for n in VARIABLES if _CHECKS[n](bars, i, level, is_long, sp)]
    if sp.ninth and large_counter_body(bars, i, level, is_long):
        out.append("large_counter_body")
    if sp.chase and chase(bars, i, level, is_long):
        out.append("chase")
    return out


def net_to_grade(net):
    return "S" if net <= 0 else ("A" if net == 1 else "C")


def score(bars, i, level, is_long, sp):
    if not bars or i >= len(bars) or level is None:
        return None
    t = trips(bars, i, level, is_long, sp)
    confl = has_confluence(bars, i, level, is_long, sp)
    if sp.disp_exempt and confl and "no_displacement" in t:
        t.remove("no_displacement")
    heavy = ("level_not_respected", "counter_trend_not_respected") if sp.w2 else ()
    cost = sum(2 if n in heavy else 1 for n in t)
    net = cost - (1 if confl else 0)
    return {"grade": net_to_grade(net), "tripped": t, "cost": cost, "confluence": confl, "net": net}


# ---------------------------------------------------------------------------------------------- metrics
def metrics(his, rub):
    n = len(his)
    conf = {h: {r: 0 for r in "SAC"} for h in "SAC"}
    for h, r in zip(his, rub):
        conf[h][r] += 1
    exact = sum(conf[g][g] for g in "SAC") / n if n else 0.0
    hs, rs, tp = sum(conf["S"].values()), sum(conf[h]["S"] for h in "SAC"), conf["S"]["S"]
    cnt = Counter(his)
    return {"n": n, "exact": exact, "confusion": conf,
            "s_recall": (tp / hs) if hs else None, "s_precision": (tp / rs) if rs else None,
            "majority_baseline": (max(cnt.values()) / n) if n else 0.0}


def shuffle_p(his, rub, iters=2000, seed=11):
    rnd = random.Random(seed)
    obs = sum(a == b for a, b in zip(his, rub))
    r = list(rub)
    hit = 0
    for _ in range(iters):
        rnd.shuffle(r)
        hit += sum(a == b for a, b in zip(his, r)) >= obs
    return (hit + 1) / (iters + 1)


def day_perm_p(days, flag, rvals, iters=2000, seed=11):
    """Two-sided day-level permutation p for mean R (flag) - mean R (not flag).
    Flags are permuted between days that have the same number of rows, so day clustering is kept."""
    rnd = random.Random(seed)
    byday = defaultdict(list)
    for k, d in enumerate(days):
        byday[d].append(k)
    groups = defaultdict(list)                       # row-count -> [day,...]
    for d, ix in byday.items():
        groups[len(ix)].append(d)

    def stat(fl):
        a = [rvals[k] for k in range(len(rvals)) if fl[k]]
        b = [rvals[k] for k in range(len(rvals)) if not fl[k]]
        return (st.mean(a) - st.mean(b)) if a and b else 0.0
    obs = abs(stat(flag))
    hit = 0
    for _ in range(iters):
        fl = list(flag)
        for ds in groups.values():
            order = list(ds)
            rnd.shuffle(order)
            for d_from, d_to in zip(ds, order):
                for a, b in zip(byday[d_from], byday[d_to]):
                    fl[b] = flag[a]
        hit += abs(stat(fl)) >= obs - 1e-12
    return (hit + 1) / (iters + 1)


def pick_mismatches(rows, k=5):
    """The k most informative mismatches. Group by what the rubric got wrong: each tripped variable when the
    rubric is too harsh, one 'lenient' group when it is too kind. Groups are ranked by size (a mismatch that
    crosses the S boundary counts double, because S is what money goes to). One example per group: the
    cleanest (fewest other tripped variables), then the largest tier gap, then the earliest date."""
    mm = [r for r in rows if r["his"] != r["rub"]]
    groups = defaultdict(list)
    for r in mm:
        if TIER[r["rub"]] > TIER[r["his"]]:
            for v in r["tripped"]:
                groups[v].append(r)
        else:
            groups["lenient"].append(r)
    wt = lambda r: 2 if "S" in (r["his"], r["rub"]) else 1
    ranked = sorted(groups, key=lambda g: (-sum(wt(r) for r in groups[g]), g))
    out, used = [], set()
    for g in ranked:
        cands = [r for r in groups[g] if r["sig_id"] not in used]
        if not cands:
            continue
        best = min(cands, key=lambda r: (len(r["tripped"]), -abs(TIER[r["rub"]] - TIER[r["his"]]), r["date"], r["sig_id"]))
        used.add(best["sig_id"])
        out.append(dict(best, group=g, group_size=len(groups[g])))
        if len(out) == k:
            break
    return out


# ---------------------------------------------------------------------------------------------- data
def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_rows(dirpath):
    """Read s_trades.csv + s_bars_0930_1100.csv.gz. Returns (rows, n_skipped)."""
    bars = defaultdict(list)
    with gzip.open(os.path.join(dirpath, "s_bars_0930_1100.csv.gz"), "rt", newline="") as fh:
        for r in csv.DictReader(fh):
            bars[r["sig_id"]].append((r["t"], dict(o=float(r["o"]), h=float(r["h"]), l=float(r["l"]), c=float(r["c"]))))
    rows, skipped = [], 0
    with open(os.path.join(dirpath, "s_trades.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            seq = bars.get(r["sig_id"])
            lvl = _f(r.get("level_px"))
            if r.get("has_bars") not in ("1", 1) or not seq or lvl is None:
                skipped += 1
                continue
            seq.sort(key=lambda x: x[0])
            ts = [t for t, _ in seq]
            if r["sig_t"] not in ts:
                skipped += 1
                continue
            rows.append(dict(sig_id=r["sig_id"], date=r["date"], sym=r["sym"], sig_t=r["sig_t"], half=r.get("half", ""),
                             his=HIS_MAP[r["grade"]], level=lvl, is_long=(r["side"] == "L"),
                             bars=[b for _, b in seq], i=ts.index(r["sig_t"]),
                             start=5 if "OR" in (r.get("eng_level") or "") else 1,
                             R2_wick=_f(r.get("R2_wick")), R2_eng=_f(r.get("R2_eng")),
                             note=(r.get("note") or "").strip(), his_setup=r.get("his_setup", "")))
    return rows, skipped


def run_spec(rows, sp):
    out = []
    for r in rows:
        s = score(r["bars"], r["i"], r["level"], r["is_long"], replace(sp, start=r["start"]))
        out.append(dict(sig_id=r["sig_id"], date=r["date"], sym=r["sym"], sig_t=r["sig_t"], half=r["half"], his=r["his"],
                        rub=s["grade"], tripped=s["tripped"], confluence=s["confluence"], net=s["net"],
                        note=r["note"], R2_wick=r["R2_wick"], R2_eng=r["R2_eng"]))
    return out


# ---------------------------------------------------------------------------------------------- reporting
def _fmt(x, pct=True):
    return "n/a" if x is None else ("%.1f%%" % (100 * x) if pct else "%.3f" % x)


def r_table(scored, key, field):
    """R by tier (n, mean, win%, H1, H2) plus S-vs-not-S day-level permutation p and top-5-days share."""
    out = []
    for g in "SAC":
        sub = [r for r in scored if r[key] == g and r[field] is not None]
        v = [r[field] for r in sub]
        h1 = [r[field] for r in sub if r["half"] == "H1"]
        h2 = [r[field] for r in sub if r["half"] == "H2"]
        pd_ = defaultdict(float)
        for r in sub:
            pd_[r["date"]] += r[field]
        tot = sum(pd_.values())
        top5 = sum(sorted(pd_.values(), reverse=True)[:5])
        out.append(dict(tier=g, n=len(v), mean=(st.mean(v) if v else None),
                        win=(sum(x > 0 for x in v) / len(v) if v else None),
                        h1=(st.mean(h1) if h1 else None), n1=len(h1), h2=(st.mean(h2) if h2 else None), n2=len(h2),
                        top5=(top5 / tot if tot > 0 else None)))
    sub = [r for r in scored if r[field] is not None]
    p = day_perm_p([r["date"] for r in sub], [r[key] == "S" for r in sub], [r[field] for r in sub])
    return out, p


def build_report(rows, skipped):
    res = {"n_scored": len(rows), "n_skipped": skipped, "grid": [], "primary": None}
    all_scored = {}
    for name, sp in GRID:
        sc = run_spec(rows, sp)
        all_scored[name] = sc
        his, rub = [r["his"] for r in sc], [r["rub"] for r in sc]
        m = metrics(his, rub)
        h1 = [r for r in sc if r["half"] == "H1"]
        h2 = [r for r in sc if r["half"] == "H2"]
        m1 = metrics([r["his"] for r in h1], [r["rub"] for r in h1])
        m2 = metrics([r["his"] for r in h2], [r["rub"] for r in h2])
        res["grid"].append(dict(name=name, exact=m["exact"], s_recall=m["s_recall"], s_precision=m["s_precision"],
                                exact_h1=m1["exact"], exact_h2=m2["exact"], recall_h1=m1["s_recall"], recall_h2=m2["s_recall"],
                                rub_s=sum(r["rub"] == "S" for r in sc), rub_a=sum(r["rub"] == "A" for r in sc),
                                rub_c=sum(r["rub"] == "C" for r in sc)))
    p = all_scored[PRIMARY]
    his, rub = [r["his"] for r in p], [r["rub"] for r in p]
    res["primary"] = dict(metrics=metrics(his, rub), shuffle_p=shuffle_p(his, rub),
                          trip_rate={v: sum(v in r["tripped"] for r in p) / len(p) for v in VARIABLES},
                          confluence_rate=sum(r["confluence"] for r in p) / len(p),
                          trip_rate_by_his={g: {v: (sum(v in r["tripped"] for r in p if r["his"] == g) /
                                                    max(1, sum(r["his"] == g for r in p))) for v in VARIABLES} for g in "SAC"},
                          mismatches=pick_mismatches(p, 5),
                          r2wick_by_his=r_table(p, "his", "R2_wick"), r2wick_by_rub=r_table(p, "rub", "R2_wick"),
                          r2eng_by_his=r_table(p, "his", "R2_eng"), r2eng_by_rub=r_table(p, "rub", "R2_eng"))
    fit = max(res["grid"], key=lambda g: (g["exact_h1"], g["name"]))          # best on H1 only
    res["holdout"] = dict(best_on_h1=fit["name"], exact_h1=fit["exact_h1"], exact_h2=fit["exact_h2"],
                          recall_h1=fit["recall_h1"], recall_h2=fit["recall_h2"])
    res["no_break_rows"] = sum(break_bar(r["bars"], r["i"], r["level"], r["is_long"], r["start"]) is None for r in rows)
    return res, all_scored


def md_tables(res):
    P = res["primary"]
    m = P["metrics"]
    L = []
    L.append("### Primary spec (`%s`), n=%d scored, %d skipped\n" % (PRIMARY, res["n_scored"], res["n_skipped"]))
    L.append("| measure | value | bar |\n|---|---|---|")
    L.append("| exact tier match | %s | >= 70%% |" % _fmt(m["exact"]))
    L.append("| S recall (his S the rubric calls S) | %s | >= 80%% |" % _fmt(m["s_recall"]))
    L.append("| S precision (rubric S that are his S) | %s | none set |" % _fmt(m["s_precision"]))
    L.append("| majority-class baseline (always say S) | %s | n/a |" % _fmt(m["majority_baseline"]))
    L.append("| shuffle p for exact match (2000 shuffles) | %.4f | n/a |\n" % P["shuffle_p"])
    L.append("Confusion matrix (rows = his grade, columns = rubric grade):\n")
    L.append("| his \\ rubric | S | A | C | total |\n|---|---|---|---|---|")
    for h in "SAC":
        c = m["confusion"][h]
        L.append("| %s | %d | %d | %d | %d |" % (h, c["S"], c["A"], c["C"], sum(c.values())))
    L.append("\nVariable trip rates (primary), overall and by his grade:\n")
    L.append("| variable | all | his S | his A | his C |\n|---|---|---|---|---|")
    for v in VARIABLES:
        L.append("| %s | %s | %s | %s | %s |" % (v, _fmt(P["trip_rate"][v]), *[_fmt(P["trip_rate_by_his"][g][v]) for g in "SAC"]))
    L.append("| BR+OCR confluence (+1) | %s | | | |\n" % _fmt(P["confluence_rate"]))
    L.append("### Declared grid (all %d variants, none hidden)\n" % len(res["grid"]))
    L.append("| variant | exact | S recall | S prec | exact H1 | exact H2 | recall H1 | recall H2 | rubric S/A/C |\n|---|---|---|---|---|---|---|---|---|")
    for g in res["grid"]:
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %d/%d/%d |" % (
            g["name"], _fmt(g["exact"]), _fmt(g["s_recall"]), _fmt(g["s_precision"]), _fmt(g["exact_h1"]), _fmt(g["exact_h2"]),
            _fmt(g["recall_h1"]), _fmt(g["recall_h2"]), g["rub_s"], g["rub_a"], g["rub_c"]))
    h = res["holdout"]
    L.append("\nBest variant chosen on H1 (2024-09 to 2025-09-28) only: `%s`, exact H1 %s -> H2 %s, S recall H1 %s -> H2 %s.\n" % (
        h["best_on_h1"], _fmt(h["exact_h1"]), _fmt(h["exact_h2"]), _fmt(h["recall_h1"]), _fmt(h["recall_h2"])))
    L.append("### 5 most informative mismatches (primary)\n")
    L.append("| # | date | symbol | his | rubric | variables tripped (confluence) | group | his note |\n|---|---|---|---|---|---|---|---|")
    for k, r in enumerate(P["mismatches"], 1):
        note = (r["note"] or "").replace("|", "/")[:110]
        L.append("| %d | %s %s | %s | %s | %s | %s%s | %s (%d) | %s |" % (
            k, r["date"], r["sig_t"], r["sym"], r["his"], r["rub"], ", ".join(r["tripped"]) or "none",
            " +1 confluence" if r["confluence"] else "", r["group"], r["group_size"], note))
    for field, lab in (("r2wick", "R2_wick (2R target, wick stop, next-open fill)"), ("r2eng", "R2_eng (2R target, engine structural stop)")):
        L.append("\n### Mean R by tier, %s\n" % lab)
        for key, who in (("his", "his grade"), ("rub", "rubric grade")):
            rows_, p = P["%s_by_%s" % (field, key)]
            L.append("By %s (day-level permutation p for S vs not-S = %.3f):\n" % (who, p))
            L.append("| tier | n | mean R | win% | H1 (n) | H2 (n) | top-5-days share |\n|---|---|---|---|---|---|---|")
            for t in rows_:
                L.append("| %s | %d | %s | %s | %s (%d) | %s (%d) | %s |" % (
                    t["tier"], t["n"], _fmt(t["mean"], False), _fmt(t["win"]), _fmt(t["h1"], False), t["n1"],
                    _fmt(t["h2"], False), t["n2"], _fmt(t["top5"])))
            L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--data", default=os.environ.get("OMEN_S_DATASET",
                    r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v3-s-dataset"))
    ap.add_argument("--json", default=os.path.join(here, "e4_report.json"))
    ap.add_argument("--md", default=None)
    a = ap.parse_args(argv)
    rows, skipped = load_rows(a.data)
    res, _ = build_report(rows, skipped)
    with open(a.json, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    md = md_tables(res)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
