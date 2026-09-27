import os, time, pandas as pd, opt_loader as L
cases = [("2024-10-15 09:45", 1, "SPY"), ("2025-03-10 09:50", -1, "QQQ"), ("2025-08-05 10:05", 1, "QQQ"),
         ("2026-04-08 09:40", -1, "SPY"), ("2026-09-24 10:15", 1, "SPY"), ("2026-09-24 10:15", 1, "SPX")]
rows = []
for ts, d, u in cases:
    for mode in ("atm", "otm1"):
        t0 = time.time()
        try:
            spot = None
            if u == "SPX":   # I:SPX not entitled -> spot = SPY x 10.0 approx, flagged
                spot = round(L.spot_at("SPY", pd.Timestamp(ts, tz=L.ET))[0] * 10.0, 1)
            m, b = L.load_option_bars(ts, d, u, mode, spot=spot)
            sig = pd.Timestamp(ts, tz=L.ET); nxt = b[b.index > sig]
            win = b[(b.index >= "{} 09:30".format(ts[:10])) & (b.index < "{} 11:00".format(ts[:10]))]
            rows.append(dict(ts=ts, u=u, dir=d, mode=mode, ticker=m["ticker"], dte=m["dte"], spot=round(m["spot"], 2),
                             spot_src=m["spot_src"], strike=m["strike"], bars_day=m["n_bars_day"], bars_930_1100=len(win),
                             entry_next_open=(round(float(nxt["o"].iloc[0]), 2) if len(nxt) else None),
                             entry_min=(nxt.index[0].strftime("%H:%M") if len(nxt) else None),
                             vol_930_1100=int(win["v"].sum()) if len(win) else 0, secs=round(time.time()-t0, 1)))
        except Exception as e:
            rows.append(dict(ts=ts, u=u, dir=d, mode=mode, err=str(e)[:140]))
        print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv("test5.csv", index=False)
