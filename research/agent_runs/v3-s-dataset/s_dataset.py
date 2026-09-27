"""v3-s-dataset: every S / one-off (A) / two-off (C) mark -> matched engine signal -> 1-min bars 09:30-11:00,
features, honest outcomes at 1R/2R/3R + 4-tier ladder. Read-only on marks/tape/bars. Paper research only."""
import sys, os, re, json, gzip, csv, random, statistics as st
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.dirname(RES)
sys.path.insert(0, RES); sys.path.insert(0, ROOT)
import marks_pool as mp, build_deck as bd

ARCH = os.path.join(ROOT, "data_archive")
TICK, COMM = 0.01, 0.005          # $/sh slippage (1 tick) per side, $/sh commission per side
FLAT = "11:00"
RANK = {"S": 0, "A": 1, "C": 2}
LAB = {"S": "S", "A": "one-off", "C": "two-off"}

# ---------------------------------------------------------------- marks
TRE = re.compile(r"\b(9|10|11):([0-5]\d)\b")
def side_of(v):
    t = str(v or "").strip().lower()
    if t in ("l", "long", "call", "calls", "buy", "c"): return 1
    if t in ("s", "short", "put", "puts", "sell", "p"): return -1
    return 0
def mark_rows():
    out, why = [], Counter()
    for p in bd.mark_sources():
        src = os.path.basename(p)
        for row in bd._rows(p):
            g = mp.row_grade(row)
            if g not in RANK: continue
            key = mp._judgement_key(row) or ""
            sym = row.get("symbol"); day = row.get("day") or row.get("date")
            if (not sym or not day) and "_" in key: sym, day = key.split("_", 1)
            if not sym or not day: why["no_key_" + g] += 1; continue
            t, tsrc = None, None
            for k in ("entry_t", "tod", "eng_et"):
                if row.get(k): t, tsrc = str(row[k])[:5], k; break
            if not t and row.get("entry_time"): t, tsrc = str(row["entry_time"])[:5], "entry_time"
            if not t and isinstance(row.get("entry_i"), int):
                m = 570 + row["entry_i"]; t, tsrc = "%02d:%02d" % divmod(m, 60), "entry_i"
            if not t:
                m = TRE.search(json.dumps(row.get("notes") or row.get("note") or row.get("his_note") or ""))
                if m: t, tsrc = "%02d:%s" % (int(m.group(1)), m.group(2)), "note_text"
            if not t: why["no_time_" + g] += 1; continue
            sd = side_of(row.get("side")) or side_of(row.get("direction")) or side_of(row.get("eng_side"))
            out.append(dict(src=src, grade=g, sym=sym, day=day, t=t, tsrc=tsrc, side=sd,
                            his_setup=row.get("setup") or row.get("claimed_setup") or row.get("setup_on_file") or "",
                            his_stop=row.get("stop_p") or row.get("stop"),
                            note=str(row.get("note") or row.get("notes") or row.get("his_note") or "")[:160]))
    return out, why

def mins(hhmm): h, m = hhmm.split(":"); return int(h) * 60 + int(m)

# ---------------------------------------------------------------- bars
_bc = {}
def bars(sym, day):
    k = (sym, day)
    if k in _bc: return _bc[k]
    fp = os.path.join(ARCH, sym, day + ".csv"); b = None
    if os.path.exists(fp):
        b = []
        for r in csv.DictReader(open(fp, encoding="utf-8")):
            ts = r["Datetime"]
            try: b.append((ts[11:16], float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"]), float(r["Volume"] or 0)))
            except ValueError: pass
    _bc[k] = b
    return b
def prev_day_hl(sym, day):
    d = os.path.join(ARCH, sym)
    try: days = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv") and f[:-4] < day)
    except FileNotFoundError: return None
    for pd_ in reversed(days[-3:]):
        b = [x for x in bars(sym, pd_) or [] if "09:30" <= x[0] < "16:00"]
        if b: return max(x[2] for x in b), min(x[3] for x in b), b[-1][4]
    return None

# ---------------------------------------------------------------- sim (honest: next-bar open +1 tick, intrabar stop, gap -> open, stop wins ties)
def sim(rth, i_sig, d, stop, tgt_r):
    if i_sig + 1 >= len(rth): return None
    fill = rth[i_sig + 1][1] + d * TICK
    risk = (fill - stop) * d
    if risk <= 0: return {"r": -1.0, "why": "stop_thru_fill", "risk": risk, "fill": fill}
    tgt = fill + d * tgt_r * risk
    cost = 2 * COMM + TICK
    for j in range(i_sig + 1, len(rth)):
        ts, o, h, l, c, v = rth[j]
        if ts >= FLAT: return {"r": ((o - fill) * d - cost) / risk, "why": "flat", "risk": risk, "fill": fill}
        if (l <= stop) if d > 0 else (h >= stop):
            ex = stop if (o - stop) * d > 0 else o
            return {"r": ((ex - fill) * d - cost) / risk, "why": "stop", "risk": risk, "fill": fill}
        if (h >= tgt + TICK) if d > 0 else (l <= tgt - TICK):
            return {"r": ((tgt - fill) * d - 2 * COMM) / risk, "why": "tgt", "risk": risk, "fill": fill}
    return None

def ladder(rth, i_sig, d, stop, pt1_px, named):
    """s04 4-tier: PT1 HOD/LOD at entry (drop <0.2R), PT2 nearest named level beyond PT1, PT3 2R, PT4 4R; 30/30/30/10,
    renormalised; BE after PT1 fills; flat 11:00; same-bar stop wins."""
    if i_sig + 1 >= len(rth): return None
    fill = rth[i_sig + 1][1] + d * TICK; risk = (fill - stop) * d
    if risk <= 0: return None
    R = lambda px: (px - fill) * d / risk
    cand = []
    if pt1_px is not None and R(pt1_px) >= 0.2: cand.append(("PT1", R(pt1_px), 0.3))
    beyond = sorted(R(x) for x in named if x is not None and R(x) > (cand[0][1] if cand else 0.2))
    if beyond: cand.append(("PT2", beyond[0], 0.3))
    cand += [("PT3", 2.0, 0.3), ("PT4", 4.0, 0.1)]
    cand.sort(key=lambda x: x[1]); rungs = []
    for c in cand:
        if rungs and c[1] - rungs[-1][1] < 0.2: continue
        rungs.append(list(c))
    wsum = sum(r[2] for r in rungs)
    for r in rungs: r[2] /= wsum
    cur_stop, left, pnl, filled = stop, 1.0, 0.0, 0
    for j in range(i_sig + 1, len(rth)):
        ts, o, h, l, c, v = rth[j]
        if ts >= FLAT: return pnl + left * (R(o) - (TICK + 2 * COMM) / risk), filled
        if (l <= cur_stop) if d > 0 else (h >= cur_stop):
            ex = cur_stop if (o - cur_stop) * d > 0 else o
            return pnl + left * (R(ex) - (TICK + 2 * COMM) / risk), filled
        hiR = R(h if d > 0 else l)
        for r in rungs[filled:]:
            if hiR >= r[1] + TICK / risk:
                pnl += r[2] * (r[1] - 2 * COMM / risk); left -= r[2]; filled += 1
                if filled == 1: cur_stop = fill
            else: break
        if left <= 1e-9: return pnl, filled
    return None

# ---------------------------------------------------------------- features
def feats(sym, day, sig, d, eng):
    b = bars(sym, day)
    if not b: return None, None
    rth = [x for x in b if "09:30" <= x[0] <= "16:00"]
    pre = [x for x in b if x[0] < "09:30"]
    idx = {x[0]: i for i, x in enumerate(rth)}
    i = idx.get(sig)
    if i is None or i < 1: return None, rth
    orb = rth[:5]; or15 = rth[:15]
    orh, orl = max(x[2] for x in orb), min(x[3] for x in orb)
    lvl = float(eng["level_px"]) if eng.get("level_px") is not None else (orh if d > 0 else orl)
    # first 1-min close beyond level (from 09:30; OR levels only count from 09:35)
    start = 5 if "OR" in str(eng.get("level", "")) or eng.get("setup_label", "").startswith("ORB") else 0
    brk = next((k for k in range(start, i + 1) if (rth[k][4] - lvl) * d > 0), None)
    f = dict(orh5=orh, orl5=orl, or5_pts=round(orh - orl, 4), orh15=max(x[2] for x in or15), orl15=min(x[3] for x in or15),
             level_px=lvl, min_after_open=mins(sig) - 570)
    def atr(k):
        w = rth[max(0, k - 14):k] or rth[:1]
        return st.mean(x[2] - x[3] for x in w) or 1e-9
    A = atr(brk if brk is not None else i)
    f["atr1m"] = round(A, 4)
    px = rth[i][4]
    if brk is None:
        f.update(break_t="", disp_pts="", disp_atr="", n_disp_candles="", retest_depth_pts="", retest_depth_atr="",
                 closed_thru="", bars_break_to_sig="")
    else:
        leg = rth[brk:i + 1]
        ext = max((x[2] - lvl) if d > 0 else (lvl - x[3]) for x in leg)
        f["break_t"] = rth[brk][0]; f["bars_break_to_sig"] = i - brk
        f["disp_pts"] = round(ext, 4); f["disp_atr"] = round(ext / A, 3)
        f["disp_pct"] = round(100 * ext / lvl, 4)
        strong = 0
        for x in leg:
            rg = x[2] - x[3]; body = (x[4] - x[1]) * d
            if rg > 0 and body >= 0.6 * rg and rg >= A: strong += 1
        f["n_disp_candles"] = strong
        post = rth[brk + 1:i + 1]
        dep = min(((x[3] - lvl) if d > 0 else (lvl - x[2])) for x in post) if post else ""
        f["retest_depth_pts"] = round(dep, 4) if post else ""
        f["retest_depth_atr"] = round(dep / A, 3) if post else ""
        f["closed_thru"] = int(any((x[4] - lvl) * d < 0 for x in post))
    # trigger (signal) candle
    ts, o, h, l, c, v = rth[i]; rg = (h - l) or 1e-9
    lw, uw = (min(o, c) - l) / rg, (h - max(o, c)) / rg
    f["trig_body_frac"] = round(abs(c - o) / rg, 3)
    f["trig_rej_wick_frac"] = round(lw if d > 0 else uw, 3)
    f["trig_far_wick_frac"] = round(uw if d > 0 else lw, 3)
    f["trig_close_pos"] = round(((c - l) if d > 0 else (h - c)) / rg, 3)
    f["trig_colour_with"] = int((c - o) * d > 0)
    f["trig_close_vs_lvl_atr"] = round((c - lvl) * d / A, 3)
    f["trig_range_atr"] = round(rg / A, 3)
    f["trig_type"] = ("hammer/pin" if f["trig_rej_wick_frac"] >= .5 and f["trig_close_pos"] >= .6 else
                      "strong-body" if f["trig_body_frac"] >= .6 and f["trig_colour_with"] else
                      "against" if not f["trig_colour_with"] and c != o else "normal")
    # trend context
    pv = sum((x[2] + x[3] + x[4]) / 3 * x[5] for x in rth[:i + 1]); vv = sum(x[5] for x in rth[:i + 1]) or 1
    f["vs_vwap_atr"] = round((px - pv / vv) * d / A, 3)
    f["vs_open_atr"] = round((px - rth[0][1]) * d / A, 3)
    f["day_move_with"] = int((px - rth[0][1]) * d > 0)
    pdh = prev_day_hl(sym, day)
    f["gap_pct"] = round(100 * (rth[0][1] / pdh[2] - 1), 3) if pdh else ""
    f["gap_with"] = int((rth[0][1] - pdh[2]) * d > 0) if pdh else ""
    f["spy_trend"] = eng.get("spy_trend", ""); f["eng_bias"] = eng.get("bias", "")
    # OCR block: last opposite-colour candle within 10 bars before the break
    ocr = ""
    if brk is not None:
        for k in range(brk - 1, max(-1, brk - 11), -1):
            x = rth[k]
            if (x[4] - x[1]) * d < 0: ocr = k; break
    f["ocr_block"] = int(ocr != "")
    if ocr != "":
        bh, bl = rth[ocr][2], rth[ocr][3]
        post = rth[brk + 1:i + 1]
        tip = min(x[3] for x in post) if d > 0 and post else (max(x[2] for x in post) if post else None)
        inside = tip is not None and bl <= tip <= bh
        f["retest_in_ocr"] = int(inside)
        f["ocr_pos"] = round(((tip - bl) / ((bh - bl) or 1e-9)) if d > 0 else ((bh - tip) / ((bh - bl) or 1e-9)), 3) if inside else ""
    else:
        f["retest_in_ocr"] = ""; f["ocr_pos"] = ""
    f["eng_ocr_label"] = int("OCR" in str(eng.get("setup_label", "")))
    # outcomes: engine structural stop (as s01) and trigger-wick stop (futures rig)
    stop_e = float(eng["stop"]); stop_w = (l - TICK) if d > 0 else (h + TICK)
    for nm, sp in (("eng", stop_e), ("wick", stop_w)):
        for tr in (1, 2, 3):
            r = sim(rth, i, d, sp, tr)
            f["R%d_%s" % (tr, nm)] = round(r["r"], 3) if r else ""
            if tr == 2: f["exit2_%s" % nm] = r["why"] if r else ""
        r = sim(rth, i, d, sp, 99)
        if r and r["risk"] > 0:
            fill, risk = r["fill"], r["risk"]
            seg = [x for x in rth[i + 1:] if x[0] < FLAT]
            f["mfe_R_%s" % nm] = round(max(((x[2] - fill) if d > 0 else (fill - x[3])) for x in seg) / risk, 2) if seg else ""
            f["risk_pts_%s" % nm] = round(risk, 4)
        else:
            f["mfe_R_%s" % nm] = ""; f["risk_pts_%s" % nm] = ""
    sess = rth[:i + 1]
    pt1 = max(x[2] for x in sess) if d > 0 else min(x[3] for x in sess)
    named = []
    if pdh: named += [pdh[0] if d > 0 else pdh[1]]
    if pre: named += [max(x[2] for x in pre) if d > 0 else min(x[3] for x in pre)]
    lr = ladder(rth, i, d, stop_e, pt1, named)
    f["R_ladder_eng"] = round(lr[0], 3) if lr else ""; f["ladder_rungs_hit"] = lr[1] if lr else ""
    return f, rth

# ---------------------------------------------------------------- main
def main():
    marks, why = mark_rows()
    tape = json.load(gzip.open(os.path.join(RES, "tape", "baseline_2026-09-13.json.gz")))["trades"]
    eng = defaultdict(list)
    for t in tape: eng[(t["sym"], t["day"])].append(t)
    sig = {}; cnt = Counter()
    for m in marks:
        cs = [t for t in eng.get((m["sym"], m["day"]), [])
              if abs(mins(t["et"]) - mins(m["t"])) <= 3 and (not m["side"] or side_of(t["side"]) == m["side"])]
        if not cs:
            cnt["unmatched_" + m["grade"]] += 1; continue
        cnt["matched_" + m["grade"]] += 1
        t = min(cs, key=lambda t: (abs(mins(t["et"]) - mins(m["t"])), mins(t["et"]) < mins(m["t"])))
        k = (t["sym"], t["day"], t["et"], t["side"])
        cur = sig.get(k)
        if cur is None or RANK[m["grade"]] < RANK[cur["grade"]]:
            sig[k] = dict(grade=m["grade"], mark=m, eng=t, n_marks=(cur["n_marks"] + 1 if cur else 1))
        else: cur["n_marks"] += 1
    rows, barsout = [], []
    for k, s in sorted(sig.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        sym, day, et, sd = k; d = side_of(sd); t = s["eng"]
        f, rth = feats(sym, day, et, d, t)
        sid = "%s_%s_%s_%s" % (sym, day, et.replace(":", ""), "L" if d > 0 else "S")
        base = dict(sig_id=sid, grade=LAB[s["grade"]], sym=sym, date=day, sig_t=et, side="L" if d > 0 else "S",
                    mark_t=s["mark"]["t"], mark_time_src=s["mark"]["tsrc"], mark_src=s["mark"]["src"], n_marks=s["n_marks"],
                    his_setup=s["mark"]["his_setup"], his_stop=s["mark"]["his_stop"] or "",
                    eng_setup=t.get("setup_label", ""), eng_level=t.get("level", ""), eng_tags="|".join(t.get("tags", [])),
                    eng_stop=t.get("stop"), half="H1" if day < "2025-09-29" else "H2",
                    idx_etf=int(sym in ("SPY", "QQQ", "IWM")), has_bars=int(bool(rth)))
        if f: base.update(f)
        base["note"] = s["mark"]["note"].replace("\n", " ")
        rows.append(base)
        if rth:
            for x in rth:
                if x[0] <= "11:00": barsout.append([sid] + list(x))
    cols = []
    for r in rows:
        for c in r:
            if c not in cols: cols.append(c)
    with open(os.path.join(HERE, "s_trades.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); [w.writerow(r) for r in rows]
    with gzip.open(os.path.join(HERE, "s_bars_0930_1100.csv.gz"), "wt", newline="") as fh:
        w = csv.writer(fh); w.writerow(["sig_id", "t", "o", "h", "l", "c", "v"]); w.writerows(barsout)
    json.dump({"why_dropped": why, "match": cnt, "signals": Counter(r["grade"] for r in rows),
               "with_features": Counter(r["grade"] for r in rows if "orh5" in r)},
              open(os.path.join(HERE, "counts.json"), "w"), indent=1)
    print("marks", len(marks), dict(why)); print(dict(cnt)); print(Counter(r["grade"] for r in rows),
          Counter(r["grade"] for r in rows if "orh5" in r))
    summarize(rows)

def num(v):
    try: return float(v)
    except (TypeError, ValueError): return None
def auc(a, b):
    if not a or not b: return None
    s = sum((x > y) + 0.5 * (x == y) for x in a for y in b); return s / (len(a) * len(b))
def summarize(rows):
    random.seed(7)
    R = [r for r in rows if "orh5" in r]
    G = ["S", "one-off", "two-off"]
    numf = ["min_after_open", "disp_atr", "disp_pts", "n_disp_candles", "bars_break_to_sig", "retest_depth_atr",
            "trig_body_frac", "trig_rej_wick_frac", "trig_close_pos", "trig_close_vs_lvl_atr", "trig_range_atr",
            "vs_vwap_atr", "vs_open_atr", "gap_pct", "or5_pts", "ocr_pos", "mfe_R_eng", "mfe_R_wick"]
    binf = ["closed_thru", "trig_colour_with", "day_move_with", "gap_with", "ocr_block", "retest_in_ocr", "eng_ocr_label", "idx_etf"]
    outs = ["R1_eng", "R2_eng", "R3_eng", "R_ladder_eng", "R1_wick", "R2_wick", "R3_wick"]
    res = {"n": {g: sum(1 for r in R if r["grade"] == g) for g in G}, "num": {}, "bin": {}, "cat": {}, "out": {}}
    def perm_p(vals_s, vals_o, stat, iters=2000):
        allv = vals_s + vals_o; obs = abs(stat(vals_s, vals_o) - 0.5); n = len(vals_s); c = 0
        for _ in range(iters):
            random.shuffle(allv)
            if abs(stat(allv[:n], allv[n:]) - 0.5) >= obs: c += 1
        return c / iters
    for fn in numf:
        v = {g: [num(r.get(fn)) for r in R if r["grade"] == g and num(r.get(fn)) is not None] for g in G}
        s, o = v["S"], v["one-off"] + v["two-off"]
        a = auc(s, o)
        res["num"][fn] = {g: (round(st.median(v[g]), 3) if v[g] else None, len(v[g])) for g in G}
        res["num"][fn]["auc"] = round(a, 3) if a is not None else None
        res["num"][fn]["p"] = perm_p(list(s), list(o), auc, 1000) if s and o else None
    for fn in binf:
        v = {g: [num(r.get(fn)) for r in R if r["grade"] == g and num(r.get(fn)) is not None] for g in G}
        res["bin"][fn] = {g: (round(100 * st.mean(v[g]), 1) if v[g] else None, len(v[g])) for g in G}
        s, o = v["S"], v["one-off"] + v["two-off"]
        if s and o:
            obs = st.mean(s) - st.mean(o); allv = s + o; n = len(s); c = 0
            for _ in range(2000):
                random.shuffle(allv)
                if abs(st.mean(allv[:n]) - st.mean(allv[n:])) >= abs(obs): c += 1
            res["bin"][fn]["p"] = c / 2000
    for fn in ["eng_setup", "trig_type", "eng_level", "spy_trend"]:
        res["cat"][fn] = {g: Counter(str(r.get(fn)) for r in R if r["grade"] == g).most_common(6) for g in G}
    for fn in outs:
        o = {}
        for g in G:
            v = [num(r.get(fn)) for r in R if r["grade"] == g and num(r.get(fn)) is not None]
            h1 = [num(r.get(fn)) for r in R if r["grade"] == g and r["half"] == "H1" and num(r.get(fn)) is not None]
            h2 = [num(r.get(fn)) for r in R if r["grade"] == g and r["half"] == "H2" and num(r.get(fn)) is not None]
            o[g] = dict(n=len(v), mean=round(st.mean(v), 3) if v else None, win=round(100 * sum(x > 0 for x in v) / len(v), 1) if v else None,
                        H1=(round(st.mean(h1), 3) if h1 else None, len(h1)), H2=(round(st.mean(h2), 3) if h2 else None, len(h2)))
        res["out"][fn] = o
    # S subset on SPY/QQQ/IWM
    res["idx_S"] = {fn: (lambda v: (round(st.mean(v), 3), len(v)) if v else None)(
        [num(r.get(fn)) for r in R if r["grade"] == "S" and r["idx_etf"] and num(r.get(fn)) is not None]) for fn in outs}
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "summary.json"), "w"), indent=1)
    print(json.dumps(res))

if __name__ == "__main__":
    main()
