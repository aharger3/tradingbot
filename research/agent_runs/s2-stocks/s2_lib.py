"""S2: does Austin's S setup have edge on STOCKS, entered causally?  Paper research, not investment advice, no orders.

Reads only: s_trades.csv (his S/A/C marks matched to engine signals), the engine tape (all candidates), stock 1-min bars
(data_archive), and stock.csv.gz from the s-matcher run (only for the 'lab' column = which candidates he marked).
Causal rule: decision = close of the signal bar (label sig_t, bar covers sig_t..sig_t+1); fill = OPEN of the next bar
+1 tick adverse; stop touched in a bar beats the target in the same bar (stop first); gap through stop fills at the open;
target needs price through it by 1 tick; flat at the 11:00 bar open. Costs: $0.01 slip on entry and on stop/flat exits,
$0.005/sh/side commission. Same convention as v3-s-dataset/s_dataset.sim.
"""
import os, csv, gzip, json
import numpy as np

ROOT = os.environ.get("OMEN_DATA_DIR", r"C:\Users\aharg\Desktop\Projects\tradingbot")
ARCH = os.path.join(ROOT, "data_archive")
TAPE = os.path.join(ROOT, r"research\tape\baseline_2026-09-13.json.gz")
S_TRADES = os.path.join(ROOT, r"research\agent_runs\v3-s-dataset\s_trades.csv")
LABELS = r"C:\Users\aharg\Desktop\life-plan\07-money\omen\night-1003\s-matcher-data\stock.csv.gz"
FIT0, FIT1 = "2024-09-26", "2026-09-25"
TICK, COMM, MIN_RISK_FRAC = 0.01, 0.005, 0.0005
RTH0, FLAT = 570, 660           # minutes after midnight: 09:30, 11:00


def mins(hhmm):
    h, m = hhmm.split(":")[:2]
    return int(h) * 60 + int(m)


_cache = {}
def load_day(sym, day):
    """-> dict O,H,L,C arrays indexed by (minute - RTH0), NaN where the bar is missing, 390 slots; None if no file."""
    k = (sym, day)
    if k in _cache:
        return _cache[k]
    if len(_cache) > 400:
        _cache.clear()
    fp = os.path.join(ARCH, sym, day + ".csv")
    out = None
    if os.path.exists(fp):
        a = np.full((4, 390), np.nan)
        with open(fp, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                ts = r["Datetime"]
                m = int(ts[11:13]) * 60 + int(ts[14:16]) - RTH0
                if 0 <= m < 390:
                    try:
                        a[:, m] = (float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"]))
                    except ValueError:
                        pass
        out = dict(O=a[0], H=a[1], L=a[2], C=a[3])
    _cache[k] = out
    return out


def sim(day, m_sig, side, stop, tgt_r=2.0, flat=FLAT):
    """m_sig = signal-bar minute (after midnight). Returns (R, how) or None. See module doc for the rules."""
    O, H, L = day["O"], day["H"], day["L"]
    i = m_sig - RTH0                      # signal bar slot; entry bar = i+1
    fl = flat - RTH0
    if i < 0 or i + 1 >= fl or not np.isfinite(O[i + 1]):
        return None
    d = 1 if side > 0 else -1
    fill = O[i + 1] + d * TICK
    risk = (fill - stop) * d
    if not np.isfinite(risk):
        return None
    if risk <= 0:                         # next open already through the stop: stopped out at once, count -1R (both groups)
        return -1.0, "stop_thru_fill"
    if risk < MIN_RISK_FRAC * fill:       # stop closer than 0.05% of price: not a tradable setup (same floor as the tape)
        return None
    tgt = fill + d * tgt_r * risk
    cost = 2 * COMM + TICK
    for j in range(i + 1, fl):
        if not np.isfinite(O[j]):
            continue
        if (L[j] <= stop) if d > 0 else (H[j] >= stop):          # stop first, also when target is in the same bar
            ex = stop if (O[j] - stop) * d > 0 else O[j]
            return ((ex - fill) * d - cost) / risk, "stop"
        if (H[j] >= tgt + TICK) if d > 0 else (L[j] <= tgt - TICK):
            return ((tgt - fill) * d - 2 * COMM) / risk, "tgt"
    k = fl
    while k < 390 and not np.isfinite(O[k]):
        k += 1
    if k >= 390:
        return None
    return ((O[k] - fill) * d - cost) / risk, "flat"


# ---------------------------------------------------------------- data
def load_candidates():
    """Engine candidates in the fit window (signal before 10:59), with the s-matcher 'lab' (who he marked)."""
    B = json.load(gzip.open(TAPE))["trades"]
    lab = {}
    with gzip.open(LABELS, "rt") as f:
        for r in csv.DictReader(f):
            lab[int(r["idx"])] = r["lab"]
    out = []
    for i, t in enumerate(B):
        if t["et"] >= "10:59" or not (FIT0 <= t["day"] <= FIT1):
            continue
        out.append(dict(idx=i, sym=t["sym"], day=t["day"], m=mins(t["et"]), side=1 if t["dir"] == "call" else -1,
                        stop=float(t["stop"]), lab=lab.get(i, "unmarked")))
    return out


def load_s_rows():
    """His marks matched to engine signals (grade S / one-off=A / two-off=C), fit window only."""
    GR = {"S": "S", "one-off": "A", "two-off": "C"}
    out = []
    with open(S_TRADES, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not (FIT0 <= r["date"] <= FIT1) or r["eng_stop"] in ("", None) or r["grade"] not in GR:
                continue
            out.append(dict(sym=r["sym"], day=r["date"], m=mins(r["sig_t"]), side=1 if r["side"] == "L" else -1,
                            stop=float(r["eng_stop"]), g=GR[r["grade"]], raw_side=r["side"], R2_eng=r["R2_eng"]))
    return out


def run_sim(rows):
    """add r/how to each row (rows whose sim is None get r=None)."""
    for x in rows:
        d = load_day(x["sym"], x["day"])
        res = sim(d, x["m"], x["side"], x["stop"]) if d else None
        x["r"], x["how"] = (res if res else (None, None))
    return rows
