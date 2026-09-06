"""L2 referee, pass 4 (2026-09-06) -- independent re-derivation of row L2's gate.

Refutation pass over the builder's repaired report `research/l2_rule84_decided.md`
(builder commit 0866da4b, code commits 7fb977f7 / 5306416e).

This file imports NOTHING from research/loop_cycle.py, research/g72_suppress_price.py
or research/l2_referee3.py.  The unit is re-implemented from the spec sentence
("up to 3 S fires; stop after a win or after 2 losses", omen-10-0-spec.md "What the
call settled") and the arithmetic from first principles, so a shared bug in the
builder's chain cannot reproduce itself here.

Run:  python research/l2_referee4.py
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAPE = ROOT / "research" / "tape"
RISK = 1000.0
BOUNDARY = "2025-09-01"
CORE = {"TSLA", "NVDA", "AAPL", "AMD", "META", "GOOGL", "AMZN", "MSFT",
        "PLTR", "QQQ", "SPY"}


def load(name):
    with gzip.open(TAPE / name, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


# ---------------------------------------------------------------- the unit

def day_policy_rows(rows):
    """Up to 3 taken signals a day, in arrival order; stop after the first
    win or after the second loss.  Candidate pool = rows the engine actually
    traded, plus rows the account-wide halt suppressed (a halt this unit's own
    stop-rule has not reached yet must not erase the rest of the day)."""
    byday = defaultdict(list)
    for r in rows:
        took = (r.get("status") == "fired" and r.get("traded"))
        halted = r.get("status") == "halted"
        if took or halted:
            byday[r["day"]].append(r)
    out = []
    for day in sorted(byday):
        seq = sorted(byday[day], key=lambda r: ((r.get("et") or ""), (r.get("sym") or "")))
        losses = 0
        for i, r in enumerate(seq):
            if i >= 3:
                break
            out.append(r)
            p = r.get("pnl", 0.0)
            if p > 0:
                break
            if p < 0:
                losses += 1
                if losses >= 2:
                    break
    return out


def figures(rows, n_days):
    if not rows or not n_days:
        return {"trades": 0, "per_day": 0, "mean_r": 0.0, "months_green": 0,
                "months": 0, "total": 0.0, "win_pct": 0.0}
    total = sum(r["pnl"] for r in rows)
    bym = defaultdict(float)
    for r in rows:
        bym[r["day"][:7]] += r["pnl"]
    w = sum(1 for r in rows if r["pnl"] > 0)
    l = sum(1 for r in rows if r["pnl"] < 0)
    return {"trades": len(rows),
            "per_day": round(total / n_days),
            "mean_r": round(total / len(rows) / RISK, 4),
            "months_green": sum(1 for v in bym.values() if v > 0),
            "months": len(bym),
            "total": round(total),
            "win_pct": round(w / (w + l) * 100, 1) if (w + l) else 0.0}


def gate(before, after, max_drop_pct=5.0):
    """green months may not fall; $/day may not fall more than max_drop_pct.
    A negative baseline: the loss may not get more than N% worse."""
    if before["trades"] < 30 or before["months"] < 12:
        return None  # no verdict
    green_ok = after["months_green"] >= before["months_green"]
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        dollar_ok = a >= b * (1 - max_drop_pct / 100.0)
    elif b < 0:
        dollar_ok = a >= b * (1 + max_drop_pct / 100.0)
    else:
        dollar_ok = a >= 0
    return bool(green_ok and dollar_ok)


def slice_core(rows):
    """core-11.  Cross-checked two ways: the book's own `tier` column and the
    literal universe.CORE_SYMBOLS list, which must agree."""
    by_tier = [r for r in rows if r.get("tier") == "core"]
    by_sym = [r for r in rows if r.get("sym") in CORE]
    assert len(by_tier) == len(by_sym), (len(by_tier), len(by_sym))
    return by_tier


def report(name, rows, n_days):
    core = slice_core(rows)
    h1 = [r for r in core if r["day"] < BOUNDARY]
    h2 = [r for r in core if r["day"] >= BOUNDARY]
    days = sorted({r["day"] for r in rows})
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    return {"whole": figures(day_policy_rows(core), n_days),
            "h1": figures(day_policy_rows(h1), n1),
            "h2": figures(day_policy_rows(h2), n2),
            "n_days": n_days, "n1": n1, "n2": n2}


# ------------------------------------------------------- the 84% row readouts

def is84(r):
    return "84%" in (r.get("level_name") or "")


def funnel(rows, n_days, core_only=False):
    rs = slice_core(rows) if core_only else rows
    rs = [r for r in rs if is84(r)]
    fired = [r for r in rs if r.get("status") == "fired"]
    traded = [r for r in rs if r.get("traded")]
    mean_r = (sum(r["pnl"] for r in traded) / len(traded) / RISK) if traded else 0.0
    return {"all_rows": len(rs), "fired": len(fired), "traded": len(traded),
            "fired_per_day": round(len(fired) / n_days, 3),
            "traded_per_day": round(len(traded) / n_days, 3),
            "mean_r_traded": round(mean_r, 4)}


def originals_join(rows):
    """Exact key: an 84% row's level_px IS the original's entry price.  Find the
    same-symbol, same-day, strictly-earlier row whose `entry` equals level_px."""
    bysd = defaultdict(list)
    for r in rows:
        bysd[(r["sym"], r["day"])].append(r)
    for v in bysd.values():
        v.sort(key=lambda r: (r.get("et") or ""))
    any_status = Counter()
    fired_only = Counter()
    unresolved = ambiguous = 0
    unresolved_fired = 0
    for r in rows:
        if not is84(r):
            continue
        px = r.get("level_px")
        cands = [o for o in bysd[(r["sym"], r["day"])]
                 if o is not r and (o.get("et") or "") < (r.get("et") or "")
                 and px is not None and abs((o.get("entry") or -1e9) - px) < 1e-9]
        if not cands:
            unresolved += 1
            if r.get("status") == "fired":
                unresolved_fired += 1
            continue
        grades = {(o.get("sgrade") or o.get("grade")) for o in cands}
        if len(grades) > 1:
            ambiguous += 1
        g = (cands[-1].get("sgrade") or cands[-1].get("grade"))
        any_status[g] += 1
        if r.get("status") == "fired":
            fired_only[g] += 1
    return any_status, fired_only, unresolved, ambiguous, unresolved_fired


def key(r):
    """A row identity that is actually unique.  (sym, day, et, entry) alone
    collides on 14,592 rows in this book -- two different signals can fire at
    the same minute at the same price on the same symbol (e.g. COIN
    2026-05-01 10:43 is both a pivot-high retest and an 84% re-entry) -- so a
    diff keyed on it silently mixes them up.  Verified unique: 0 duplicate
    keys in both arms."""
    return (r["sym"], r["day"], r.get("et"), r.get("setup"), r.get("dir"),
            r.get("level_name"), round(r.get("entry") or 0.0, 4),
            round(r.get("stop") or 0.0, 4), round(r.get("target") or 0.0, 4))


def main():
    mo, off = load("book_RULE84_DECIDED_off.json.gz")
    mn, on = load("book_RULE84_DECIDED_on.json.gz")
    mb, base = load("baseline_2026-09-05.json.gz")

    print("== stamps ==")
    for nm, m in (("off", mo), ("on", mn), ("baseline", mb)):
        s = m["stamp"]
        print(" %-9s book_id=%s commit=%s dirty_py=%s engine_dirty=%s sessions=%s %s..%s"
              % (nm, s.get("book_id"), s["git"]["commit"][:8], s["git"]["dirty_py_count"],
                 s["git"]["dirty_engine_py"], m["sessions"], m["first"], m["last"]))
    fo, fn = mo["stamp"]["flags"], mn["stamp"]["flags"]
    diffs = {k: (fo.get(k), fn.get(k)) for k in set(fo) | set(fn) if fo.get(k) != fn.get(k)}
    print(" off-vs-on flag diffs:", diffs)
    print(" off book_id == baseline book_id:",
          mo["stamp"]["book_id"] == mb["stamp"]["book_id"])

    print("\n== gate, core-11, up_to_3_stop_win_or_2loss, close fill, shipped ladder ==")
    a = report("off", off, mo["sessions"])
    b = report("on", on, mn["sessions"])
    for half in ("whole", "h1", "h2"):
        g = gate(a[half], b[half])
        print(" %-5s trades %4d->%4d  $/day %5d->%5d  meanR %+0.4f->%+0.4f  green %2d/%2d->%2d/%2d  gate=%s"
              % (half, a[half]["trades"], b[half]["trades"],
                 a[half]["per_day"], b[half]["per_day"],
                 a[half]["mean_r"], b[half]["mean_r"],
                 a[half]["months_green"], a[half]["months"],
                 b[half]["months_green"], b[half]["months"],
                 {True: "pass", False: "FAIL", None: "not enough"}[g]))

    print("\n== 84%% funnel ==")
    for nm, rows, m in (("off", off, mo), ("on", on, mn)):
        print(" all-28 %-3s %s" % (nm, funnel(rows, m["sessions"])))
    for nm, rows, m in (("off", off, mo), ("on", on, mn)):
        print(" core11 %-3s %s" % (nm, funnel(rows, m["sessions"], core_only=True)))

    print("\n== originals join (exact level_px key) ==")
    for nm, rows in (("off", off), ("on", on)):
        anyst, fired, unres, amb, unres_f = originals_join(rows)
        tot84 = sum(1 for r in rows if is84(r))
        print(" %-3s any-status S/A/C = %d/%d/%d  resolved %d of %d  unresolved %d  ambiguous %d"
              % (nm, anyst.get("S", 0), anyst.get("A", 0), anyst.get("C", 0),
                 sum(anyst.values()), tot84, unres, amb))
        print("     fired-only S/A/C = %d/%d/%d  (total fired %d, unresolved-fired %d)"
              % (fired.get("S", 0), fired.get("A", 0), fired.get("C", 0),
                 sum(fired.values()), unres_f))

    print("\n== added / removed in the core-11 CANDIDATE pool (before the 3-cap) ==")
    def cand(rows):
        return [r for r in slice_core(rows)
                if (r.get("status") == "fired" and r.get("traded"))
                or r.get("status") == "halted"]
    qa = {key(r): r for r in cand(off)}
    qb = {key(r): r for r in cand(on)}
    cadd = [qb[k] for k in qb if k not in qa]
    crem = [qa[k] for k in qa if k not in qb]
    print("  added %d (84%%: %d) sum $%d | removed %d (84%%: %d) sum $%d | shared pnl diffs %d"
          % (len(cadd), sum(1 for r in cadd if is84(r)), round(sum(r["pnl"] for r in cadd)),
             len(crem), sum(1 for r in crem if is84(r)), round(sum(r["pnl"] for r in crem)),
             len([k for k in qa if k in qb and abs(qa[k]["pnl"] - qb[k]["pnl"]) > 1e-6])))
    for r in sorted(cadd, key=lambda r: (r["day"], r.get("et"))):
        print("   + %s %s %s pnl=%d is84=%s status=%s"
              % (r["sym"], r["day"], r.get("et"), round(r["pnl"]), is84(r), r.get("status")))

    print("\n== added / removed in the core-11 PRICED day-policy set (after the 3-cap) ==")
    pa = {key(r): r for r in day_policy_rows(slice_core(off))}
    pb = {key(r): r for r in day_policy_rows(slice_core(on))}
    added = [pb[k] for k in pb if k not in pa]
    removed = [pa[k] for k in pa if k not in pb]
    shared_diff = [k for k in pa if k in pb and abs(pa[k]["pnl"] - pb[k]["pnl"]) > 1e-6]
    print(" added %d (84%%-rows %d) total $%d" %
          (len(added), sum(1 for r in added if is84(r)), round(sum(r["pnl"] for r in added))))
    for r in sorted(added, key=lambda r: (r["day"], r.get("et"))):
        print("   + %s %s %s pnl=%d is84=%s" % (r["sym"], r["day"], r.get("et"), round(r["pnl"]), is84(r)))
    print(" removed %d (84%%-rows %d) total $%d" %
          (len(removed), sum(1 for r in removed if is84(r)), round(sum(r["pnl"] for r in removed))))
    print(" shared keys with a pnl difference:", len(shared_diff))

    print("\n== whole-book row status flips (all 28 syms) ==")
    ka = {key(r): r for r in off}
    kb = {key(r): r for r in on}
    flips = [k for k in ka if k in kb and
             (ka[k].get("status"), bool(ka[k].get("traded"))) !=
             (kb[k].get("status"), bool(kb[k].get("traded")))]
    non84 = [k for k in flips if not is84(ka[k])]
    print(" flipped rows %d, of which non-84%%: %d on %d distinct days"
          % (len(flips), len(non84), len({k[1] for k in non84})))
    print(" days:", sorted({k[1] for k in non84}))

    print("\n== ON fires absent from the OFF arm ==")
    off84fired = {key(r) for r in off if is84(r) and r.get("status") == "fired"}
    on84fired = [r for r in on if is84(r) and r.get("status") == "fired"]
    novel = [r for r in on84fired if key(r) not in off84fired]
    for r in sorted(novel, key=lambda r: (r["day"], r.get("et"))):
        print("   %s %s %s status=%s traded=%s pnl=%s" %
              (r["sym"], r["day"], r.get("et"), r.get("status"), r.get("traded"), round(r.get("pnl", 0))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
