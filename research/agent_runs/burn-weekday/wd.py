# burn-weekday: what does Austin's Mon-Thu live constraint cost, and do 10:00 ET news days hurt?
# Sets: MNQ mantra lead (105 frozen trades), Zarattini NQ925 (261, research/zarattini PR #44), S marks (v3-s-dataset).
# Paper/backtest R only. Permutation p shuffles the day-flag across unique dates (date-level, 10k perms).
import json, os, sys
import numpy as np, pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

HERE = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
NPERM = 10000
rng = np.random.default_rng(11)
SPLIT = "2026-03-04"  # same train/test cut as g-news-days

# ---- 10:00 ET release calendar 2024-09 .. 2026-09 ----
# JOLTS + UMich final: FRED release calendars (rid=192, rid=91), fetched 2026-09-27. 2024 rows from BLS/UMich 2024 schedule.
JOLTS = ("2024-09-04 2024-10-01 2024-10-29 2024-12-03 2025-01-07 2025-02-04 2025-03-11 2025-04-01 2025-04-29 2025-06-03 "
         "2025-07-01 2025-07-29 2025-09-03 2025-09-30 2025-12-09 2026-01-07 2026-02-05 2026-03-13 2026-03-31 2026-05-05 "
         "2026-06-02 2026-06-30 2026-08-04 2026-09-01 2026-09-29").split()
UM_FINAL = ("2024-09-27 2024-10-25 2024-11-22 2024-12-20 2025-01-24 2025-02-21 2025-03-28 2025-04-25 2025-05-30 2025-06-27 "
            "2025-08-01 2025-08-29 2025-09-26 2025-10-24 2025-11-21 2025-12-19 2026-01-23 2026-02-20 2026-03-27 2026-04-24 "
            "2026-05-22 2026-06-26 2026-07-31 2026-08-28 2026-09-25").split()
# UMich preliminary = the Friday two weeks before the final (FRED lists finals only) -> approximate
UM_PRELIM = [(pd.Timestamp(d) - pd.Timedelta(days=14)).strftime("%Y-%m-%d") for d in UM_FINAL]
# FOMC statement days (14:00 ET, included per brief), federalreserve.gov
FOMC = ("2024-09-18 2024-11-07 2024-12-18 2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 "
        "2025-12-10 2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16").split()
# ISM Manufacturing = 1st business day, ISM Services = 3rd business day of month (ISM's standing rule)
hol = USFederalHolidayCalendar().holidays("2024-01-01", "2026-12-31")
bd = pd.bdate_range("2024-09-01", "2026-09-30", freq="C", holidays=hol)
bym = pd.Series(bd).groupby(bd.strftime("%Y-%m"))
ISM_M = [g.iloc[0].strftime("%Y-%m-%d") for _, g in bym]
ISM_S = [g.iloc[2].strftime("%Y-%m-%d") for _, g in bym]
CAL = dict(ISM_M=set(ISM_M), ISM_S=set(ISM_S), JOLTS=set(JOLTS), UMICH=set(UM_FINAL) | set(UM_PRELIM), FOMC=set(FOMC))
NEWS10 = set().union(*[v for k, v in CAL.items() if k != "FOMC"])  # true 10:00 ET prints
NEWS = NEWS10 | CAL["FOMC"]
WD = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def load():
    M = json.load(open(f"{HERE}/trades_MNQ_OR5_1030_D1_strong.json"))
    Z = json.load(open(f"{HERE}/zar_trades.json"))
    s = pd.read_csv(f"{HERE}/s_trades.csv")
    S = s[s.grade == "S"].dropna(subset=["R2_eng"])
    sets = {
        "MNQ mantra (frozen)": pd.DataFrame({"date": [t["date"] for t in M], "R": [t["R"] for t in M]}),
        "Zarattini NQ925": pd.DataFrame({"date": list(Z["NQ925"]), "R": [v["R"] for v in Z["NQ925"].values()]}),
        "S marks (R2_eng)": pd.DataFrame({"date": S.date.values, "R": S.R2_eng.values}),
    }
    for df in sets.values():
        df["wd"] = pd.to_datetime(df.date).dt.dayofweek
    return sets, Z["sessions"]


def perm_p(dates, y, flag_fn):
    """two-sided p for mean(y|flag) - mean(y|~flag), flag shuffled across unique dates."""
    dates = np.asarray(dates); y = np.asarray(y, float)
    ud, inv = np.unique(dates, return_inverse=True)
    fd = np.array([flag_fn(d) for d in ud]); m = fd[inv]
    if m.sum() < 2 or (~m).sum() < 2:
        return np.nan, np.nan
    obs = y[m].mean() - y[~m].mean(); cnt = 0; tot = 0
    for _ in range(NPERM):
        mm = rng.permutation(fd)[inv]
        if mm.sum() == 0 or (~mm).sum() == 0: continue
        tot += 1; cnt += abs(y[mm].mean() - y[~mm].mean()) >= abs(obs) - 1e-12
    return obs, (cnt + 1) / (tot + 1)


def years(dates):
    d = pd.to_datetime(pd.Series(dates))
    return max((d.max() - d.min()).days / 365.25, 1e-9)


def stats(r):
    return dict(n=len(r), meanR=r.mean() if len(r) else np.nan, win=(r > 0).mean() * 100 if len(r) else np.nan, sumR=r.sum())


def main():
    sets, sess = load()
    out = ["# weekday table"]
    wk_rows, mt_rows, news_rows = [], [], []
    for name, df in sets.items():
        yrs = years(df.date) if name.startswith("S") else years(sess)
        for i, w in enumerate(WD):
            wk_rows.append(dict(set=name, day=w, **stats(df.R[df.wd == i])))
        mt, fr = df.R[df.wd <= 3], df.R[df.wd == 4]
        d, p = perm_p(df.date.values, df.R.values, lambda D: pd.Timestamp(D).dayofweek == 4)
        mt_rows.append(dict(set=name, n_MT=len(mt), meanR_MT=mt.mean(), win_MT=(mt > 0).mean() * 100,
                            n_Fri=len(fr), meanR_Fri=fr.mean(), win_Fri=(fr > 0).mean() * 100,
                            Fri_minus_rest=d, p=p, years=yrs, FriR_per_yr=fr.sum() / yrs, allR_per_yr=df.R.sum() / yrs))
        for lab, cal in [("any news (10:00 + FOMC)", NEWS), ("10:00 prints only", NEWS10)] + [(k, v) for k, v in CAL.items()]:
            f = df.date.isin(cal)
            d, p = perm_p(df.date.values, df.R.values, lambda D, c=cal: D in c)
            tr = df[df.date < SPLIT]; te = df[df.date >= SPLIT]
            dd = lambda x: x.R[x.date.isin(cal)].mean() - x.R[~x.date.isin(cal)].mean()
            news_rows.append(dict(set=name, flag=lab, n_news=int(f.sum()), R_news=df.R[f].mean(), win_news=(df.R[f] > 0).mean() * 100,
                                  n_other=int((~f).sum()), R_other=df.R[~f].mean(), diff=d, p=p, train_d=dd(tr), test_d=dd(te)))
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    W = pd.DataFrame(wk_rows); MT = pd.DataFrame(mt_rows); N = pd.DataFrame(news_rows)
    print(W.round(3).to_string()); print(); print(MT.round(3).to_string()); print(); print(N.round(3).to_string())
    print("\ncalendar counts:", {k: len(v) for k, v in CAL.items()}, "news days:", len(NEWS), "sessions w/ news:", sum(d in NEWS for d in sess), "/", len(sess))
    W.to_csv(f"{HERE}/weekday.csv", index=False); MT.to_csv(f"{HERE}/mon_thu_vs_fri.csv", index=False); N.to_csv(f"{HERE}/news10.csv", index=False)


if __name__ == "__main__":
    main()
