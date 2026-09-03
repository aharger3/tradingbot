"""Independent misfire probe: replay the FSM on every fired B&R row in the book
and count where the engine fired against its own stated geometry."""
import json, sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import polygon_feed as pf

WINDOW, MAXGAP = 12, 3

def trace(candles, level, is_long, window=WINDOW):
    """Byte-mirror of omen_bot.detect_break_retest, returning the FSM trace."""
    out = {"pass": False}
    if len(candles) < 4:
        return out
    w = candles[-window:]
    cur = w[-1]
    if (cur.close <= level) if is_long else (cur.close >= level):
        out["fail"] = "no_confirm_close"; return out
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = 0.10 * avg_rng
    rtol = 0.0
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size:
        out["fail"] = "adverse_wick"; return out
    state, retest_idx = "seek_break", None
    break_idx = leave_idx = first_retest_idx = None
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long \
                else (p.close >= level and c.close < level - eps)
            if crossed:
                state = "seek_leave"; break_idx = i
        elif state == "seek_leave":
            left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left:
                state = "seek_retest"; leave_idx = i
            elif failed:
                state = "seek_break"; break_idx = None
        elif state == "seek_retest":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back:
                retest_idx, first_retest_idx, state = i, i, "hold"
        elif state == "hold":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back:
                retest_idx = i
    if retest_idx is None:
        out["fail"] = "no_" + state.split("_")[1]; return out
    if (len(w) - 1) - retest_idx > MAXGAP:
        out["fail"] = "stale_retest"; return out
    out.update(**{"pass": True, "n": len(w), "eps": eps, "avg_rng": avg_rng,
                  "break_idx": break_idx, "leave_idx": leave_idx,
                  "retest_idx": retest_idx, "first_retest_idx": first_retest_idx,
                  "gap": (len(w) - 1) - retest_idx})
    # --- invariants -------------------------------------------------------
    # A wrong-side CLOSE anywhere between the leave bar and the entry bar:
    # the FSM's "failed break resets to step 1" only runs in seek_leave, so a
    # bar closing back through the level after the retest never resets.
    lo = (leave_idx if leave_idx is not None else 0)
    wrongside = [j for j in range(lo + 1, len(w) - 1)
                 if ((w[j].close < level - eps) if is_long else (w[j].close > level + eps))]
    out["wrongside_after_leave"] = wrongside
    out["wrongside_after_retest"] = [j for j in wrongside if j > first_retest_idx]
    # How many separate wrong-side excursions (a "chop count")
    out["level_close_crossings"] = sum(
        1 for a, b in zip(w[:-1], w[1:]) if (a.close - level) * (b.close - level) < 0)
    return out


def main(limit_rows=None):
    book = json.load(open(ROOT / "research/bt2y_trades_retest_on.json"))
    rows = [r for r in book["trades"]
            if r["status"] == "fired" and r["setup"] == "break_and_retest"]
    if limit_rows:
        rows = rows[:limit_rows]
    by_symday = collections.defaultdict(list)
    for r in rows:
        by_symday[(r["sym"], r["day"])].append(r)

    C = collections.Counter()
    RS = collections.defaultdict(list)
    ex = collections.defaultdict(list)
    for (sym, day), rr in sorted(by_symday.items()):
        try:
            rth = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            C["bars_missing"] += 1; continue
        if not rth:
            C["bars_missing"] += 1; continue
        for r in rr:
            i = r["entry_i"]
            if i >= len(rth):
                C["idx_oob"] += 1; continue
            lv = r["level_px"]
            is_long = r["dir"] == "call"
            t = trace(rth[:i + 1], lv, is_long)
            C["rows"] += 1
            if not t["pass"]:
                C["reproduce_fail:" + t.get("fail", "?")] += 1
                continue
            C["reproduced"] += 1
            C["gap=%d" % t["gap"]] += 1
            if t["gap"] == 0:
                C["retest_is_entry_bar"] += 1
            tag = "disp" if "disp" in r["tags"] else ("nodisp" if "nodisp" in r["tags"] else "?")
            C["tag:" + tag] += 1
            if t["break_idx"] is not None:
                brk_from_end = (t["n"] - 1) - t["break_idx"]
                C["break_bars_back=%d" % brk_from_end] += 1
                if brk_from_end > 5:
                    C["break_outside_disp_window"] += 1
                    C["break_outside_disp_window/" + tag] += 1
                else:
                    C["break_inside_disp_window/" + tag] += 1
            if t["wrongside_after_retest"]:
                C["wrongside_close_after_retest"] += 1
                if len(ex["wrongside"]) < 8:
                    ex["wrongside"].append((sym, day, r["et"], r["level_name"],
                                            r["dir"], t["wrongside_after_retest"],
                                            r["r"], r["traded"]))
            if t["wrongside_after_leave"]:
                C["wrongside_close_after_leave"] += 1
                if r["traded"]:
                    C["wrongside_after_leave_TRADED"] += 1
                    RS["wrongside"].append(r["r"])
            elif r["traded"]:
                RS["clean"].append(r["r"])
            if r["traded"]:
                (RS["gap0"] if t["gap"] == 0 else RS["gapN"]).append(r["r"])
                if t["wrongside_after_retest"]:
                    RS["ws_after_retest"].append(r["r"])
            if t["level_close_crossings"] >= 3:
                C["window_crossings>=3"] += 1
    print(json.dumps(dict(C), indent=1, sort_keys=True))
    import statistics
    print("--- R by slice (traded rows only) ---")
    for k, v in sorted(RS.items()):
        if v:
            print("%-18s n=%5d meanR=%+0.4f  win=%.1f%%" % (
                k, len(v), statistics.fmean(v), 100*sum(1 for x in v if x > 0)/len(v)))
    print("--- examples ---")
    for e in ex["wrongside"]:
        print(e)

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
