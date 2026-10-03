"""s-matcher step 1: build the decision-time feature table.

stock.csv.gz : every engine candidate (tape baseline_2026-09-13, signal < 10:59) with its label (S/A/B/C/none from the
               canonical marks, matched +-3 min same side exactly as t04), decision-time features, forward R (2R/flat 11:00).
nq.csv.gz    : every OR5 break+retest+trigger event on real NQ (sessions after the reserved B1 window), same features, R.
Usage: python sm_build.py OUTDIR
"""
import os, sys, gzip, json, re, collections as C
from multiprocessing import Pool
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sm_features as F
import sm_data as D

ROOT = D.ROOT
TAPE = os.path.join(ROOT, r"research\tape\baseline_2026-09-13.json.gz")


def mins(hm):
    h, m = hm.split(":")[:2]
    return int(h) * 60 + int(m)


# ---------------------------------------------------------------- labels (t04 matching, unchanged)
TK = ["entry_t", "entry_time", "et", "eng_et", "entry_et", "setup_et", "tod", "entry_minute"]
RANK = {"S": 0, "A": 1, "B": 2, "C": 3, "none": 4}


def mark_minute(r):
    for f in ("entry_i", "eng_entry_i"):
        v = r.get(f)
        if isinstance(v, (int, float)) and 0 <= v < 390:
            return 570 + int(v)
    for f in TK:
        v = r.get(f)
        if isinstance(v, str):
            m = re.search(r"(\d{1,2}):(\d{2})", v)
            if m:
                return int(m.group(1)) * 60 + int(m.group(2))
    return None


def mark_side(r):
    for f in ("side", "direction", "eng_side", "dir", "setup_dir"):
        v = str(r.get(f) or "").lower()
        if v in ("call", "long", "bull", "l", "buy", "up", "bullish", "c"):
            return True
        if v in ("put", "short", "bear", "s", "sell", "down", "bearish", "p"):
            return False
    return None


def bucket(g):
    g = str(g).upper()
    return g if g in ("S", "A", "B", "C") else "none"


def load_labels(cand_by_symday):
    """-> {candidate_index: grade}, plus judged (sym, day) set and stats."""
    os.chdir(ROOT)
    sys.path.insert(0, os.path.join(ROOT, "research"))
    import marks_pool as mp, build_deck as bd
    marks, stat = {}, C.Counter()
    for p in bd.mark_sources():
        for r in bd._rows(p):
            k = mp._judgement_key(r)
            g = mp.row_grade(r)
            if not k or g is None:
                continue
            g = bucket(g)
            mm = mark_minute(r)
            if mm is None:
                stat["no_time"] += 1
                continue
            sym, day = k.split("_", 1)
            sd = mark_side(r)
            best = None
            for idx, t in cand_by_symday.get((sym, day), []):
                if sd is not None and (t["dir"] == "call") != sd:
                    continue
                d = abs(mins(t["et"]) - mm)
                if d <= 3 and (best is None or d < best[0]):
                    best = (d, idx)
            if not best:
                stat["unmatched"] += 1
                continue
            stat["matched"] += 1
            idx = best[1]
            if idx not in marks or RANK[g] < RANK[marks[idx]]:
                marks[idx] = g
    judged = {(v.symbol, v.date) for v in mp.canonical_pool().values()}
    return marks, judged, stat


# ---------------------------------------------------------------- stock worker
def work_symbol(args):
    sym, items = args          # items: [(idx, day, et, dir, stop)]
    dates = D.stock_dates(sym)
    pos = {d: i for i, d in enumerate(dates)}
    cache = {}

    def get(day):
        if day not in cache:
            if len(cache) > 6:
                cache.clear()
            cache[day] = D.load_stock_day(sym, day)
        return cache[day]

    out = []
    for idx, day, et, direction, stop in sorted(items, key=lambda x: x[1]):
        d = get(day)
        if d is None:
            continue
        side = 1 if direction == "call" else -1
        m = mins(et)
        prev = None
        i = pos.get(day)
        if i:
            pd_ = dates[i - 1]
            if (pd.Timestamp(day) - pd.Timestamp(pd_)).days <= 5:
                prev = get(pd_)
        f = F.features_at(d, prev, m, side, float(stop))
        r = F.simulate(d, m, side, float(stop))
        if r is None:
            continue
        row = dict(idx=idx, m=m, side=side, R=r[0], how=r[1])
        row.update(f)
        out.append(row)
    return out


def build_stock(outdir):
    B = json.load(gzip.open(TAPE))["trades"]
    cands, by_sd = [], C.defaultdict(list)
    for i, t in enumerate(B):
        if t["et"] >= "10:59":
            continue
        cands.append(i)
        by_sd[(t["sym"], t["day"])].append((i, t))
    marks, judged, stat = load_labels(by_sd)
    print("labels:", dict(stat), C.Counter(marks.values()), flush=True)
    per_sym = C.defaultdict(list)
    for i in cands:
        t = B[i]
        per_sym[t["sym"]].append((i, t["day"], t["et"], t["dir"], t["stop"]))
    with Pool(10) as p:
        res = p.map(work_symbol, sorted(per_sym.items()), chunksize=1)
    rows = [r for rs in res for r in rs]
    df = pd.DataFrame(rows).set_index("idx")
    meta = pd.DataFrame([{"idx": i, "sym": B[i]["sym"], "day": B[i]["day"], "et": B[i]["et"], "status": B[i]["status"],
                          "eng_grade": B[i].get("grade")} for i in df.index]).set_index("idx")
    df = meta.join(df)
    df["lab"] = [marks.get(i, "unmarked_judged" if (B[i]["sym"], B[i]["day"]) in judged else "unmarked")
                 for i in df.index]
    df.reset_index().to_csv(os.path.join(outdir, "stock.csv.gz"), index=False)
    print("stock rows", len(df), df["lab"].value_counts().to_dict(), flush=True)
    return df


# ---------------------------------------------------------------- NQ
def build_nq(outdir, nq=None):
    import nq_candidates as NC
    nq = nq or D.build_nq_days()
    rows = []
    for dt in sorted(nq):
        day, prev = nq[dt]
        A = {k: day[K][F.RTH0:F.RTH0 + 91] for k, K in (("open", "O"), ("high", "H"), ("low", "L"), ("close", "C"))}
        for c in NC.detect_candidates(A, dt, "MNQ"):
            side = 1 if c.direction == "long" else -1
            m = F.RTH0 + int(c.features["minutes_after_open"])
            f = F.features_at(day, prev, m, side, float(c.stop))
            r = F.simulate(day, m, side, float(c.stop), slip=0.25, comm_side=0.31, tgt_extra=0.25)   # $1.24 RT per micro = 0.62 pt RT
            if r is None:
                continue
            row = dict(day=dt, et="%02d:%02d" % divmod(m, 60), m=m, side=side, R=r[0], how=r[1],
                       grade_hint=c.grade_hint, first_of_day=int(c.features["first_signal_of_day"]),
                       trig_strong=int(c.features["trigger_strong"]), trig_pin=int(c.features["trigger_pin"]))
            row.update(f)
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(outdir, "nq.csv.gz"), index=False)
    print("nq rows", len(df), "sessions", df["day"].nunique(), df["day"].min(), df["day"].max(), flush=True)
    return df


def add_nq_ctx(stock_df, nq, outdir):
    """join NQ market context at the label's session/minute (labeled rows only; sessions after the reserved window)."""
    lab = stock_df[stock_df["lab"].isin(list(RANK))].copy()
    cols = {k: [] for k in F.NQ_CTX}
    for _, r in lab.iterrows():
        nd = nq.get(r["day"])
        c = F.nq_context(nd[0] if nd else None, nd[1] if nd else None, int(r["m"]), int(r["side"]))
        for k in cols:
            cols[k].append(c[k])
    for k in cols:
        lab[k] = cols[k]
    lab.to_csv(os.path.join(outdir, "labeled_nqctx.csv.gz"), index=False)
    print("labeled", len(lab), "with NQ ctx", int(lab["nq_mom15_atr"].notna().sum()), flush=True)


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    nq = D.build_nq_days()
    print("NQ sessions", len(nq), min(nq), max(nq), flush=True)
    build_nq(out, nq)
    sdf = build_stock(out)
    add_nq_ctx(sdf, nq, out)
