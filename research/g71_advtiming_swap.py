"""ADVERSARIAL re-run of G71/timing's T12-section-4 swap table.

Independent of research/g71_timing.py's k=0 re-run: the baseline for every
traded row is the BOOK's own published r (research/bt2y_trades.json), not a
re-managed clone. The swapped trade is built and managed through the shipped
backtest_week._ladder_bar via g71_timing.build/manage (shipped code, reused on
purpose so any difference is population/statistics, not a re-implementation).

Emits, for the NEAREST-earlier-candidate arm:
  * n, mean R taken / swapped, paired delta, paired bootstrap CI (own seed),
  * a SAME-SIZE delta that neutralises the 1R-denominator change,
  * the status/grade census of the picked candidates,
  * how many picks are rows the engine ALREADY TRADED in the same book.
"""
import json, os, statistics, random, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

import g71_timing as G                                     # noqa: E402
from signal_runner import min_risk_floor                   # noqa: E402
from backtest_week import RISK_DOLLARS                     # noqa: E402

book = json.load(open(G.BOOK, encoding="utf-8"))
rows = [r for r in book["trades"] if r["status"] == "fired" and r["traded"]]
print("book traded rows: %d  meanR %+.4f" % (len(rows), statistics.fmean(r["r"] for r in rows)))

unbound = G.load_or_build_index(rows)
print("bound %d unbound %d" % (len(G._MATCH), unbound))

# --- support: buildable at every k in -2..+2 (bounds only; no management) ---
support = []
for n, row in enumerate(rows):
    src = G.match(n)
    if src is None:
        continue
    ctx = G.day_ctx(row["sym"], row["day"])
    if ctx is None:
        continue
    L = len(ctx[0]); i0 = src.entry_idx
    if all(5 <= i0 + k < L - 1 for k in (-2, -1, 0, 1, 2)) and i0 < L:
        support.append(n)
print("support (buildable at all k): %d of %d" % (len(support), len(rows)))

# --- candidate filter, exactly as the claim ran it ---------------------------
dropped = Counter(); kept = {}
for n in support:
    keep = []
    for c in G._CANDS.get(n, []):
        if c["status"] == "skipped_tight_stop":
            dropped["skipped_tight_stop"] += 1
        elif abs(c["entry"] - c["stop"]) < min_risk_floor(c["entry"]):
            dropped["under_floor"] += 1
        else:
            keep.append(c)
    if keep:
        kept[n] = keep
print("dropped: %s ; rows with a takeable candidate: %d (%.2f%%)"
      % (dict(dropped), len(kept), 100 * len(kept) / len(support)))

# --- traded-row fingerprints, to detect picks the book ALREADY holds ---------
traded_fp = set()
for r in rows:
    traded_fp.add((r["sym"], r["day"], r["entry_i"], r["dir"]))

took, swap, rk_t, rk_s, offs = [], [], [], [], []
st, gr, dup = Counter(), Counter(), 0
for n in sorted(kept):
    c = kept[n][0]                       # nearest first (cache is sorted -off)
    row = rows[n]
    ctx = G.day_ctx(row["sym"], row["day"])
    t = G.build(G._Src(c), ctx[0], ctx[1], ctx[2], ctx[3], ctx[4], 0, "T")
    if t is None:
        continue
    G.manage(t, ctx[0], G._StubRunner(ctx[0]))
    took.append(row["r"])                          # BOOK's own r — independent
    swap.append(t.pnl / RISK_DOLLARS)
    rk_t.append(abs(row["entry"] - row["stop"]))
    rk_s.append(abs(t.entry - t.stop))
    offs.append(c["off"]); st[c["status"]] += 1; gr[c["grade"]] += 1
    if (c["symbol"], c["day"], c["entry_idx"], c["direction"]) in traded_fp:
        dup += 1

d = [swap[i] - took[i] for i in range(len(swap))]
# same-size: hold position size to the ENGINE row's, so the swapped trade's
# dollars are not re-scaled by its own (smaller) risk.
ds = [swap[i] * (rk_s[i] / rk_t[i]) - took[i] for i in range(len(swap))]


def boot(xs, reps=20000, seed=917):
    rnd = random.Random(seed); n = len(xs); ms = []
    for _ in range(reps):
        ms.append(statistics.fmean(rnd.choices(xs, k=n)))
    ms.sort()
    return ms[int(0.025 * reps)], ms[int(0.975 * reps)]


def line(name, xs):
    lo, hi = boot(xs)
    sd = statistics.stdev(xs)
    print("  %-16s n=%d mean %+.4f  sd %.3f  se %.4f  95%% boot [%+.4f, %+.4f]"
          % (name, len(xs), statistics.fmean(xs), sd, sd / len(xs) ** .5, lo, hi))


print("\nNEAREST earlier candidate — n=%d median offset %+0.1f" % (len(swap), statistics.median(offs)))
print("  engine took (BOOK r): mean %+.4f WR %.1f%% total %+.1fR"
      % (statistics.fmean(took), 100 * sum(1 for x in took if x > 0) / len(took), sum(took)))
print("  swapped             : mean %+.4f WR %.1f%% total %+.1fR"
      % (statistics.fmean(swap), 100 * sum(1 for x in swap if x > 0) / len(swap), sum(swap)))
line("delta R", d)
line("delta SAME-SIZE", ds)
print("  median 1R taken $%.3f -> swapped $%.3f (%.2fx); mean ratio %.2fx"
      % (statistics.median(rk_t), statistics.median(rk_s),
         statistics.median(rk_s) / statistics.median(rk_t),
         statistics.fmean(rk_s[i] / rk_t[i] for i in range(len(rk_s)))))
print("  picked candidate status %s" % dict(st))
print("  picked candidate legacy grade %s" % dict(gr))
print("  picks that are THEMSELVES traded rows in the same book: %d" % dup)

json.dump({"n": len(swap), "took": statistics.fmean(took), "swap": statistics.fmean(swap),
           "delta": statistics.fmean(d), "delta_ci": boot(d),
           "delta_samesize": statistics.fmean(ds), "delta_samesize_ci": boot(ds),
           "status": dict(st), "grade": dict(gr), "dup_traded": dup,
           "support": len(support), "rows_with_cand": len(kept)},
          open(os.path.join(HERE, "g71_advtiming_swap.json"), "w"), indent=1)
print("wrote g71_advtiming_swap.json")
