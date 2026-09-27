# g-news-days: do Austin's S marks and the engine leads behave differently on FOMC/CPI/NFP days,
# first/last trading day of month, Mon vs Thu? Date-level permutation p, BH, train/test split = o2 (2026-03-04).
import json, sys
import numpy as np, pandas as pd
import os
HERE = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(7)
NPERM = 5000
SPLIT = "2026-03-04"
# free calendars: federalreserve.gov fomccalendars; bls.gov news-release archives (cpi, empsit). Sep-2024 rows from BLS 2024 schedule.
FOMC = "2024-09-18 2024-11-07 2024-12-18 2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10 2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16".split()
CPI = "2024-09-11 2024-10-10 2024-11-13 2024-12-11 2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11 2025-07-15 2025-08-12 2025-09-11 2025-10-24 2025-12-18 2026-01-13 2026-02-13 2026-03-11 2026-04-10 2026-05-12 2026-06-10 2026-07-14 2026-08-12 2026-09-11".split()
NFP = "2024-09-06 2024-10-04 2024-11-01 2024-12-06 2025-01-10 2025-02-07 2025-03-07 2025-04-04 2025-05-02 2025-06-06 2025-07-03 2025-08-01 2025-09-05 2025-11-20 2025-12-16 2026-01-09 2026-02-11 2026-03-06 2026-04-03 2026-05-08 2026-06-05 2026-07-02 2026-08-07 2026-09-04".split()

Z = json.load(open(f"{HERE}/zar_trades.json"))
sess = sorted(Z["sessions"])
# trading calendar = NQ RTH sessions (495); marks outside it fall back to business days
ser = pd.Series(pd.to_datetime(sess))
ym = ser.dt.strftime("%Y-%m")
first = set(ser.groupby(ym).min().dt.strftime("%Y-%m-%d"))
last = set(ser.groupby(ym).max().dt.strftime("%Y-%m-%d"))
first.discard(sess[0]); last.discard(sess[-1])  # partial months at the edges

from functools import lru_cache
def flags(D):
    return _flags(str(D))
@lru_cache(None)
def _flags(D):
    wd = pd.Timestamp(D).dayofweek
    f = dict(FOMC=D in FOMC, CPI=D in CPI, NFP=D in NFP, FTD=D in first, LTD=D in last,
             Mon=wd == 0, Tue=wd == 1, Wed=wd == 2, Thu=wd == 3, Fri=wd == 4)
    f["news"] = f["FOMC"] or f["CPI"] or f["NFP"]
    f["TOM"] = f["FTD"] or f["LTD"]
    return f
FLAGS = ["news", "FOMC", "CPI", "NFP", "FTD", "LTD", "TOM", "Mon", "Tue", "Wed", "Thu", "Fri"]

def perm_diff(dates, y, flag, g=None):
    """in-minus-out mean of y; two-sided p by shuffling the flag across unique dates."""
    dates = np.asarray(dates); y = np.asarray(y, float)
    ud, inv = np.unique(dates, return_inverse=True)
    fd = np.array([flags(d)[flag] for d in ud])
    m = fd[inv]
    if m.sum() < 3 or (~m).sum() < 3:
        return None
    obs = y[m].mean() - y[~m].mean()
    cnt = 0
    for _ in range(NPERM):
        mm = rng.permutation(fd)[inv]
        if mm.sum() == 0 or (~mm).sum() == 0: continue
        cnt += abs(y[mm].mean() - y[~mm].mean()) >= abs(obs) - 1e-12
    return dict(n_in=int(m.sum()), in_=y[m].mean(), out=y[~m].mean(), d=obs, p=(cnt + 1) / (NPERM + 1))

def split_sign(dates, y, flag):
    dates = np.asarray(dates); y = np.asarray(y, float)
    r = []
    for sel in (dates < SPLIT, dates >= SPLIT):
        m = np.array([flags(d)[flag] for d in dates[sel]])
        yy = y[sel]
        r.append(yy[m].mean() - yy[~m].mean() if m.sum() >= 2 and (~m).sum() >= 2 else np.nan)
    return r

rows = []
def run(set_name, dates, y, metric):
    for f in FLAGS:
        r = perm_diff(dates, y, f)
        if r is None: continue
        tr, te = split_sign(dates, y, f)
        rows.append(dict(set=set_name, metric=metric, flag=f, **r, train_d=tr, test_d=te))

s = pd.read_csv(f"{HERE}/s_trades.csv")
S = s[s.grade == "S"]; N = s[s.grade != "S"]
run("S marks", S.date.values, S.R2_eng.values, "R2_eng")
run("S marks", S.date.values, S.R2_wick.values, "R2_wick")
run("non-S marks", N.date.values, N.R2_eng.values, "R2_eng")
run("all marks", s.date.values, (s.grade == "S").astype(float).values, "S rate")
# eye (S - nonS) inside flag vs outside: permute at date level
def eye_perm(flag):
    ud, inv = np.unique(s.date.values, return_inverse=True)
    fd = np.array([flags(d)[flag] for d in ud]); isS = (s.grade == "S").values; y = s.R2_eng.values
    def eye(m):
        a, b = y[m & isS], y[m & ~isS]
        return a.mean() - b.mean() if len(a) >= 3 and len(b) >= 3 else np.nan
    m = fd[inv]; obs = eye(m) - eye(~m)
    if np.isnan(obs): return None
    ps = [eye(mm) - eye(~mm) for mm in (rng.permutation(fd)[inv] for _ in range(NPERM))]
    ps = np.array([p for p in ps if not np.isnan(p)])
    return dict(set="eye S-nonS", metric="R2_eng", flag=flag, n_in=int((m & isS).sum()), in_=eye(m), out=eye(~m), d=obs,
                p=((np.abs(ps) >= abs(obs)).sum() + 1) / (len(ps) + 1), train_d=np.nan, test_d=np.nan)
for f in FLAGS:
    r = eye_perm(f)
    if r: rows.append(r)

M = json.load(open(f"{HERE}/trades_MNQ_OR5_1030_D1_strong.json"))
run("MNQ mantra lead", [t["date"] for t in M], [t["R"] for t in M], "R")
for k in ("NONE", "NQ925"):
    run(f"Zarattini {k}", list(Z[k]), [v["R"] for v in Z[k].values()], "R")
    # per-session R (0 on no-trade days) -> does the flag change the day's expectancy
    run(f"Zarattini {k} per-day", sess, [Z[k].get(D, {"R": 0.0})["R"] for D in sess], "R/day")

df = pd.DataFrame(rows)
# BH within R-type tests (exclude S rate)
p = df.p.values; o = np.argsort(p); q = np.empty_like(p); m = len(p)
q[o] = np.minimum.accumulate((p[o] * m / np.arange(1, m + 1))[::-1])[::-1]
df["q"] = np.minimum(q, 1)
# Mon vs Thu head-to-head
def mon_thu(dates, y):
    dates = np.asarray(dates); y = np.asarray(y, float)
    wd = pd.to_datetime(dates).dayofweek.values
    keep = (wd == 0) | (wd == 3); d2, y2, w2 = dates[keep], y[keep], wd[keep]
    ud, inv = np.unique(d2, return_inverse=True); fd = np.array([pd.Timestamp(str(d)).dayofweek == 0 for d in ud])
    obs = y2[fd[inv]].mean() - y2[~fd[inv]].mean()
    ps = np.array([(lambda mm: y2[mm].mean() - y2[~mm].mean())(rng.permutation(fd)[inv]) for _ in range(NPERM)])
    return dict(n_mon=int(fd[inv].sum()), n_thu=int((~fd[inv]).sum()), mon=y2[fd[inv]].mean(), thu=y2[~fd[inv]].mean(), p=((np.abs(ps) >= abs(obs)).sum() + 1) / (NPERM + 1))
mt = {"S R2_eng": mon_thu(S.date.values, S.R2_eng.values), "non-S R2_eng": mon_thu(N.date.values, N.R2_eng.values),
      "S rate": mon_thu(s.date.values, (s.grade == "S").astype(float).values),
      "MNQ mantra": mon_thu([t["date"] for t in M], [t["R"] for t in M]),
      "Zar NONE": mon_thu(list(Z["NONE"]), [v["R"] for v in Z["NONE"].values()]),
      "Zar NQ925": mon_thu(list(Z["NQ925"]), [v["R"] for v in Z["NQ925"].values()])}
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
print(df.round(3).to_string())
print("\nMon vs Thu"); print(pd.DataFrame(mt).T.round(3))
print("\nmarked dates:", s.date.nunique(), "flag counts on sessions:", {f: sum(flags(d)[f] for d in sess) for f in FLAGS})
df.to_csv(f"{HERE}/news_days_results.csv", index=False)
json.dump({k: {kk: float(vv) for kk, vv in v.items()} for k, v in mt.items()}, open(f"{HERE}/mon_thu.json", "w"), indent=1)
