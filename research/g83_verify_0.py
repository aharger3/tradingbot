"""Independent recheck of the g83 scale-out touch-fill dollar claims.

Adversarial verification, 2026-08-30. Recomputes the headline numbers straight
off the two two-year books WITHOUT importing g72_suppress_price -- own money
arithmetic, own one-trade-a-day selection, own month/week/drawdown code -- so a
bug in the shared helper cannot hide inside both the claim and its check.

1R = $1,000. The bar is $397/day ($100,000 / 252 sessions).

Usage:
    python research/g83_verify_0.py --touch A.json --close B.json
"""
import argparse, json
from datetime import date

RISK = 1000.0
BAR = 100_000 / 252


def worst_dd(pnls):
    cum = peak = worst = 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return worst


def summarize(rows, sessions):
    pnls = [r["pnl"] for r in rows]
    tot = sum(pnls)
    w = sum(1 for p in pnls if p > 0)
    l = sum(1 for p in pnls if p < 0)
    m, wk = {}, {}
    for r in rows:
        m[r["day"][:7]] = m.get(r["day"][:7], 0.0) + r["pnl"]
        y, ww, _ = date.fromisoformat(r["day"]).isocalendar()
        k = "%04d-W%02d" % (y, ww)
        wk[k] = wk.get(k, 0.0) + r["pnl"]
    return {"trades": len(rows), "total": round(tot),
            "win_pct": round(w / (w + l) * 100, 1) if w + l else 0.0,
            "per_trade": round(tot / len(rows)),
            "mean_r": round(tot / len(rows) / RISK, 4),
            "per_day": round(tot / sessions),
            "months_green": sum(1 for v in m.values() if v > 0), "months": len(m),
            "weeks_green": sum(1 for v in wk.values() if v > 0), "weeks": len(wk),
            "worst_drawdown": round(worst_dd(pnls))}


def arms(path):
    b = json.load(open(path, encoding="utf-8"))
    rows, n = b["trades"], b["meta"]["sessions"]
    key = lambda r: (r["day"], r["et"], r["sym"])
    shipped = sorted([r for r in rows if r.get("traded")], key=key)
    # one trade a day: first candidate of each session (traded fires + halted rows)
    byday = {}
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday.setdefault(r["day"], []).append(r)
    oneaday = [sorted(v, key=key)[0] for _, v in sorted(byday.items())]
    return n, summarize(shipped, n), summarize(oneaday, n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--touch", required=True)
    ap.add_argument("--close", required=True)
    a = ap.parse_args()
    nt, ts, to = arms(a.touch)
    nc, cs, co = arms(a.close)
    print("sessions: touch %d  close %d" % (nt, nc))
    for name, t, c in (("ONE A DAY", to, co), ("EVERY SIGNAL", ts, cs)):
        print("\n== %s ==" % name)
        print("  %-16s%>0s" % ("", "") if False else "  %-16s%14s%14s%12s"
              % ("", "TOUCH", "CLOSE", "delta"))
        for k in ("trades", "win_pct", "total", "per_trade", "per_day",
                  "months_green", "weeks_green", "worst_drawdown"):
            print("  %-16s%14s%14s%12s" % (k, t[k], c[k], round(t[k] - c[k], 1)))
        print("  %-16s%+14.0f%+14.0f%+12.0f"
              % ("vs $397/day", t["per_day"] - BAR, c["per_day"] - BAR,
                 t["per_day"] - c["per_day"]))


if __name__ == "__main__":
    main()
