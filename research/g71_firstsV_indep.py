"""Independent re-derivation of the g71_firsts paired-vs-P0seq numbers.

Written from the spec, not from research/g71_firsts_policy.py: candidate stream,
sequential one-at-a-time walk, day vectors, paired deltas. Adds sample-sd se,
a bootstrap CI, and a decomposition showing what the delta actually is.
"""
import json, random, statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
T = B["trades"]

counted = [r for r in T if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
day = defaultdict(list)
for r in counted:
    day[r["day"]].append(r)
for d in day:
    day[d].sort(key=lambda r: (r["entry_i"], r["et"], r["sym"]))
days = sorted(day)


def seq(rows, stop):
    """stop(n, wins, losses, cum) -> True to halt. Sequential, no overlap."""
    out, free = [], None
    w = l = 0
    cum = 0.0
    for c in rows:
        if stop(len(out), w, l, cum):
            break
        if free is not None and (c["entry_i"], c["et"], c["sym"]) < free:
            continue
        out.append(c)
        free = (c["entry_i"] + c["bars"], c["et"], c["sym"])
        if c["out"] == "win":
            w += 1
        elif c["out"] == "loss":
            l += 1
        cum += c["r"]
    return out


POL = {
    "P0seq": lambda n, w, l, c: False,
    "P1":    lambda n, w, l, c: n >= 1,
    "P2":    lambda n, w, l, c: w >= 1 or l >= 2,
    "P3":    lambda n, w, l, c: c > 0,
    "P4":    lambda n, w, l, c: c > 0 or l >= 3,
}
sday = {d: [r for r in day[d] if r["sgrade"] == "S"] for d in days}
sday = {d: v for d, v in sday.items() if v}

vecs = {}
for k, f in POL.items():
    vecs[k] = {d: sum(x["r"] for x in seq(day[d], f)) for d in days}
vecs["P5"] = {d: sum(x["r"] for x in seq(sday[d], POL["P2"])) for d in sday}

ctrl = vecs["P0seq"]
print("%-6s %10s %8s %8s %8s %10s %10s" % ("arm", "mean_d", "se_pop", "se_samp", "t", "boot_lo", "boot_hi"))
rows_out = {}
for k in ("P1", "P2", "P3", "P4", "P5"):
    v = vecs[k]
    d = [v.get(x, 0.0) - ctrl.get(x, 0.0) for x in days]
    m = st.fmean(d)
    sep = st.pstdev(d) / len(d) ** 0.5
    ses = st.stdev(d) / len(d) ** 0.5
    random.seed(7)
    bs = sorted(st.fmean(random.choices(d, k=len(d))) for _ in range(2000))
    print("%-6s %10.4f %8.4f %8.4f %8.2f %10.4f %10.4f"
          % (k, m, sep, ses, m / sep, bs[50], bs[1949]))
    rows_out[k] = (round(m, 4), round(sep, 4), round(m / sep, 2))

# ---- what IS the delta? P1 = strict prefix of P0seq. Decompose.
print()
drop = []
for d in days:
    s = seq(day[d], POL["P0seq"])
    drop += [r["r"] for r in s[1:]]
print("P0seq trades:", sum(len(seq(day[d], POL['P0seq'])) for d in days),
      " P1 trades:", len(days))
print("trades P1 forgoes (P0seq positions 2..n): n=%d mean_r=%+.4f total=%+.1fR"
      % (len(drop), st.fmean(drop), sum(drop)))
print("-> -sum/496 = %+.4f  (should equal P1 mean_day_delta)" % (-sum(drop) / len(days)))

# is P1 a strict prefix of P0seq? check
pref = all(seq(day[d], POL["P1"]) == seq(day[d], POL["P0seq"])[:1] for d in days)
print("P1 rows are exactly P0seq's first row every day:", pref)
nest = {}
for k in ("P2", "P3", "P4"):
    ok = all(seq(day[d], POL[k]) == seq(day[d], POL["P0seq"])[:len(seq(day[d], POL[k]))]
             for d in days)
    nest[k] = ok
print("nested prefixes of P0seq:", nest)
print()
print(json.dumps(rows_out, indent=0))
