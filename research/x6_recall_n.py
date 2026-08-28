"""x6_recall_n.py -- why 160 S trades in two years when his eye sees three a week.

Austin, 2026-08-28:
  "s trade accuracy is not good, still 160 trades over two years and the average
   needs to increase because i see way more trades... especially on the top 10
   stocks, my eye sees more trades i could find 3 s trades on one of those stocks
   in 1 week."
  "2 year backtest results finicky, shows too many random s categories."

Two complaints pointing opposite ways -- too FEW S trades and too MANY random ones.
Both are true if the engine's S set and his S set barely overlap. This script measures
the overlap and prices the three ways to get more S trades.

Substrate: research/g3_arm_ow1.json (the shipped 2-year book, 45,193 detections /
1,017 traded, 2024-08-21..2026-08-21, 500 sessions, 28 symbols).
Marks: research/build_deck.py::marked_card_ids / mark_sources -- the canonical reader,
called not reimplemented, so every corpus in CLAUDE.md is covered.
Held-out: research/marks/probe_omen_test1_2026-08-27.jsonl (100 unseen cards).

    python research/x6_recall_n.py            # print every section
    python research/x6_recall_n.py --json OUT # also dump the numbers

Writes nothing unless --json is given. Touches no mark file.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import build_deck as bd  # noqa: E402  the canonical mark reader

BOOK = os.path.join(HERE, "g3_arm_ow1.json")
HELDOUT = os.path.join(HERE, "marks", "probe_omen_test1_2026-08-27.jsonl")
W4 = os.path.join(HERE, "w4_candidate_days.jsonl")

# Austin's ladder is S/A/C/none. `X` in his hand means the same thing as `none`
# ("should not have fired" / "I would not take it") -- probe_omen_test1 carries
# both `grade: "X"` and `grade_std: "none"` on the same row, which is the mapping
# stated by the page that collected it. `B` is legacy-ladder leakage (3 rows in
# austin_marks_v7, 14 in recovered_reviews) and is counted separately, never
# folded into a tier.
_TIER = {"s": "S", "a": "A", "c": "C", "x": "none", "none": "none"}
_GRADE_KEYS = bd._GRADE_KEYS


def norm_tier(row: dict):
    """-> ('S'|'A'|'C'|'none', raw) or (None, raw) when it is not on Austin's ladder."""
    raw = ""
    for k in ("grade_std",) + _GRADE_KEYS:
        v = str(row.get(k, "")).strip()
        if v:
            raw = v
            break
    if not raw:
        # a probe answer with no grade field (sr_ rows): answers.grade
        ans = row.get("answers")
        if isinstance(ans, dict):
            g = ans.get("grade")
            if isinstance(g, list) and g:
                raw = str(g[0]).strip()
            elif isinstance(g, str):
                raw = g.strip()
    return _TIER.get(raw.lower()), raw


# Setup vocabularies collide across a decade of files. Everything reduces to
# BR (break and retest), OCR (one candle rule), or OTHER.
def norm_setup(v) -> str | None:
    if isinstance(v, list):
        v = " ".join(str(x) for x in v)
    s = str(v or "").strip().lower()
    if not s:
        return None
    if "one candle" in s or "one_candle" in s or s in ("ocr", "one candle rule"):
        return "OCR"
    if "break" in s and "retest" in s:
        return "BR"
    if s in ("br", "b&r", "bnr", "break & retest", "break and retest"):
        return "BR"
    if "retest" in s or "break" in s:
        return "BR"
    return "OTHER"


def load_marks():
    """Every human judgement, keyed SYMBOL_DATE, with tier / setup / entry_i.

    A symbol-day can be judged more than once across corpora. Keep the best tier
    seen (S > A > C > none) so a day Austin ever called S counts as an S day, and
    keep the setup / entry_i from the S row when there is one.
    """
    rank = {"S": 3, "A": 2, "C": 1, "none": 0}
    best: dict[str, dict] = {}
    per_file = collections.Counter()
    off_ladder = []
    for path in bd.mark_sources():
        base = os.path.basename(path)
        for row in bd._rows(path):
            key = bd._judgement_key(row)
            if not key:
                continue
            tier, raw = norm_tier(row)
            if tier is None:
                if raw:
                    off_ladder.append((base, key, raw))
                continue
            per_file[(base, tier)] += 1
            setup = norm_setup(row.get("setup") or row.get("setups"))
            ei = row.get("entry_i")
            try:
                ei = int(ei)
            except (TypeError, ValueError):
                ei = None
            sym, date = key.rsplit("_", 1)
            cur = best.get(key)
            if cur is None or rank[tier] > rank[cur["tier"]]:
                best[key] = {"key": key, "symbol": sym, "date": date, "tier": tier,
                             "setup": setup, "entry_i": ei, "src": base}
            else:
                # same-or-lower tier: only fill blanks
                if cur["setup"] is None and setup:
                    cur["setup"] = setup
                if cur["entry_i"] is None and ei is not None:
                    cur["entry_i"] = ei
    return best, per_file, off_ladder


def pct(a, b):
    return 0.0 if not b else 100.0 * a / b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    OUT = {}

    book = json.load(open(BOOK, encoding="utf-8"))
    meta, T = book["meta"], book["trades"]
    traded = [r for r in T if r.get("traded")]
    syms = meta["symbols"]
    first, last = meta["first"], meta["last"]
    sessions = meta["sessions"]

    print("=" * 78)
    print("X6 -- WHY 160 S TRADES IN TWO YEARS")
    print("book %s  %s..%s  %d sessions  %d symbols  %d detections  %d traded"
          % (os.path.basename(BOOK), first, last, sessions, len(syms), len(T), len(traded)))
    print("=" * 78)

    # ---------------------------------------------------------------- 1. COUNT
    print("\n## 1. COUNT -- the engine's S supply\n")
    s_traded = [r for r in traded if r["sgrade"] == "S"]
    s_all = [r for r in T if r["sgrade"] == "S"]
    symdays = {(r["sym"], r["day"]) for r in T}
    symdays_per_sym = collections.Counter(s for s, _ in symdays)
    s_days = {(r["sym"], r["day"]) for r in s_traded}

    print("traded rows            %5d" % len(traded))
    print("  sgrade == S          %5d  (%.1f%%)" % (len(s_traded), pct(len(s_traded), len(traded))))
    print("  distinct S symbol-days %3d" % len(s_days))
    print("detections (all)       %5d" % len(T))
    print("  sgrade == S          %5d  (%.1f%%)" % (len(s_all), pct(len(s_all), len(T))))
    print("symbol-days replayed   %5d" % len(symdays))
    OUT["s_traded"] = len(s_traded)
    OUT["s_detected"] = len(s_all)
    OUT["traded"] = len(traded)
    OUT["symdays"] = len(symdays)

    # Austin's implied rate: 3 S per week on a top-10 name.
    #   3 / 5 sessions = 0.60 S per symbol-day; x 252 sessions = 151.2 per symbol-year.
    IMPLIED_PER_SESSION = 3.0 / 5.0
    SESSIONS_PER_YEAR = 252.0
    IMPLIED_PER_SYM_YEAR = IMPLIED_PER_SESSION * SESSIONS_PER_YEAR

    yrs = len(symdays) and (sessions / SESSIONS_PER_YEAR)
    print("\nAustin's implied rate: 3 S / week / symbol = %.2f per symbol-day = %.0f per symbol-year"
          % (IMPLIED_PER_SESSION, IMPLIED_PER_SYM_YEAR))
    print("book spans %.2f years of sessions\n" % yrs)

    print("%-7s %8s %6s %6s %10s %10s %8s" %
          ("symbol", "symdays", "S_trd", "S_det", "S/sym-day", "S/sym-yr", "gap x"))
    rows = []
    for sym in sorted(syms, key=lambda s: -symdays_per_sym[s]):
        nd = symdays_per_sym[sym]
        st = sum(1 for r in s_traded if r["sym"] == sym)
        sd = sum(1 for r in s_all if r["sym"] == sym)
        rate = st / nd if nd else 0.0
        per_yr = rate * SESSIONS_PER_YEAR
        gap = IMPLIED_PER_SYM_YEAR / per_yr if per_yr else float("inf")
        rows.append({"symbol": sym, "symdays": nd, "s_traded": st, "s_detected": sd,
                     "s_per_symday": round(rate, 4), "s_per_sym_year": round(per_yr, 1),
                     "gap_x": None if gap == float("inf") else round(gap, 1)})
        print("%-7s %8d %6d %6d %10.4f %10.1f %8s" %
              (sym, nd, st, sd, rate, per_yr, "inf" if gap == float("inf") else "%.1f" % gap))
    tot_rate = len(s_traded) / len(symdays)
    print("%-7s %8d %6d %6d %10.4f %10.1f %8.1f" %
          ("ALL", len(symdays), len(s_traded), len(s_all), tot_rate,
           tot_rate * SESSIONS_PER_YEAR, IMPLIED_PER_SYM_YEAR / (tot_rate * SESSIONS_PER_YEAR)))
    OUT["per_symbol"] = rows
    OUT["implied_per_sym_year"] = IMPLIED_PER_SYM_YEAR
    OUT["measured_per_sym_year"] = round(tot_rate * SESSIONS_PER_YEAR, 2)

    # THE SUPPLY LADDER -- four different things the word "S" can mean, one rate each.
    strict = [r for r in T if r["sgrade"] == "S" and str(r["tripped"]) == "0"]
    print("\n  THE SUPPLY LADDER (per symbol-year, %d symbol-days replayed)" % len(symdays))
    ladder = [
        ("Austin's eye, implied (3 S/wk/symbol)", None, IMPLIED_PER_SYM_YEAR),
        ("engine DETECTIONS graded S by downgrade.py", len(s_all),
         len(s_all) / len(symdays) * SESSIONS_PER_YEAR),
        ("...of those, STRICT S (zero downgrades tripped)", len(strict),
         len(strict) / len(symdays) * SESSIONS_PER_YEAR),
        ("engine ALERTS graded S", sum(1 for r in T if r["sgrade"] == "S" and (r.get("alert") or r.get("traded"))),
         sum(1 for r in T if r["sgrade"] == "S" and (r.get("alert") or r.get("traded"))) / len(symdays) * SESSIONS_PER_YEAR),
        ("engine TRADES graded S (the book)", len(s_traded),
         len(s_traded) / len(symdays) * SESSIONS_PER_YEAR),
    ]
    for label, n, rate in ladder:
        print("    %-48s %7s   %7.1f /symbol-year" % (label, "-" if n is None else n, rate))
    OUT["supply_ladder"] = [{"label": l, "n": n, "per_sym_year": round(v, 2)} for l, n, v in ladder]

    # CONFLUENCE RESCUE -- how many S rows are S only because of the +1 credit
    def rescue(rows):
        resc = sum(1 for r in rows if str(r["tripped"]) != "0" and r["confluence"] == "yes")
        return resc, len(rows)
    r_t, n_t = rescue(s_traded)
    r_a, n_a = rescue(s_all)
    conf_all = sum(1 for r in T if r["confluence"] == "yes")
    print("\n  CONFLUENCE RESCUE (score = tripped - confluence; S means score <= 0)")
    print("    S trades that tripped a downgrade and were rescued to S by the +1  %d/%d = %.1f%%"
          % (r_t, n_t, pct(r_t, n_t)))
    print("    S detections likewise                                              %d/%d = %.1f%%"
          % (r_a, n_a, pct(r_a, n_a)))
    print("    and the +1 is handed to %d of %d detections = %.1f%% of the book"
          % (conf_all, len(T), pct(conf_all, len(T))))
    OUT["confluence_rescue_traded"] = [r_t, n_t]
    OUT["confluence_rescue_detected"] = [r_a, n_a]
    OUT["confluence_rate_book"] = [conf_all, len(T)]

    print("\nS traded by month:")
    bym = collections.Counter(r["ym"] for r in s_traded)
    allm = collections.Counter(r["ym"] for r in traded)
    for ym in sorted(allm):
        print("  %s  S=%3d / traded=%3d" % (ym, bym.get(ym, 0), allm[ym]))
    OUT["s_by_month"] = {k: bym.get(k, 0) for k in sorted(allm)}

    print("\nS traded by detector:")
    for k, v in collections.Counter(r["setup"] for r in s_traded).most_common():
        det = sum(1 for r in s_all if r["setup"] == k)
        print("  %-20s traded %4d   detected %6d   %.2f%% of detections traded"
              % (k, v, det, pct(v, det)))
    OUT["s_by_detector"] = dict(collections.Counter(r["setup"] for r in s_traded))

    # -------------------------------------------------------------- 2. OVERLAP
    print("\n\n## 2. OVERLAP -- his S set vs the engine's S set\n")
    marks, per_file, off_ladder = load_marks()
    tiers = collections.Counter(m["tier"] for m in marks.values())
    print("judged symbol-days (marked_card_ids parity): %d" % len(bd.marked_card_ids()))
    print("tiers resolved on Austin's ladder: %s   (off-ladder rows dropped: %d)"
          % (dict(tiers), len(off_ladder)))
    OUT["judged_symdays"] = len(marks)
    OUT["judged_tiers"] = dict(tiers)

    a_S = {k for k, m in marks.items() if m["tier"] == "S"}
    a_none = {k for k, m in marks.items() if m["tier"] == "none"}

    def in_book(key):
        sym, d = key.rsplit("_", 1)
        return (sym, d) in symdays

    a_S_book = {k for k in a_S if in_book(k)}
    a_none_book = {k for k in a_none if in_book(k)}
    e_S = {"%s_%s" % (s, d) for s, d in s_days}
    e_S_det = {"%s_%s" % (r["sym"], r["day"]) for r in s_all}
    e_traded_days = {"%s_%s" % (r["sym"], r["day"]) for r in traded}

    print("\nAustin S symbol-days                     %4d" % len(a_S))
    print("  ... that the book actually replays      %4d  (in-window, in-roster)" % len(a_S_book))
    print("Engine S symbol-days (traded)             %4d" % len(e_S))
    print("Engine S symbol-days (any detection)      %4d" % len(e_S_det))

    inter = a_S_book & e_S
    inter_det = a_S_book & e_S_det
    print("\nDAY-LEVEL AGREEMENT (both called S on the same symbol-day)")
    print("  engine-traded-S  n= %3d   = %.1f%% of his replayable S days   = %.1f%% of the engine's S days"
          % (len(inter), pct(len(inter), len(a_S_book)), pct(len(inter), len(e_S))))
    print("  engine-detected-S n= %3d  = %.1f%% of his replayable S days"
          % (len(inter_det), pct(len(inter_det), len(a_S_book))))
    print("  engine traded ANYTHING on %d of his %d replayable S days (%.1f%%)"
          % (len(a_S_book & e_traded_days), len(a_S_book), pct(len(a_S_book & e_traded_days), len(a_S_book))))
    OUT["austin_S_days"] = len(a_S)
    OUT["austin_S_days_in_book"] = len(a_S_book)
    OUT["engine_S_days"] = len(e_S)
    OUT["day_agreement"] = len(inter)

    # setup + entry-bar agreement on the intersection
    by_day = collections.defaultdict(list)
    for r in s_traded:
        by_day["%s_%s" % (r["sym"], r["day"])].append(r)

    def grade_mix(keys, label):
        rows = [r for r in traded if "%s_%s" % (r["sym"], r["day"]) in keys]
        c = collections.Counter(r["sgrade"] for r in rows)
        days = len({(r["sym"], r["day"]) for r in rows})
        print("  %-34s %3d trades on %3d days   %s"
              % (label, len(rows), days, dict(c)))
        return {"trades": len(rows), "days": days, "mix": dict(c)}
    print("\nWHAT GRADE THE ENGINE PUTS ON HIS DAYS (traded rows only)")
    OUT["grade_mix_on_S_days"] = grade_mix(a_S_book, "on his 207 replayable S days")
    OUT["grade_mix_on_none_days"] = grade_mix(a_none_book, "on his refused (none) days")

    by_day_any = collections.defaultdict(list)
    for r in traded:
        by_day_any["%s_%s" % (r["sym"], r["day"])].append(r)

    def agree(keys, index, label):
        """Setup and entry-bar agreement over `keys`, against `index`'s traded rows."""
        sh = ss = b3 = b1 = bs = 0
        dl = []
        det = []
        for k in sorted(keys):
            m = marks[k]
            cands = index[k]
            if not cands:
                continue
            eset = {("OCR" if c["setup"] == "one_candle_rule" else "BR") for c in cands}
            ok_setup = None
            if m["setup"] in ("BR", "OCR"):
                ss += 1
                ok_setup = m["setup"] in eset
                sh += int(ok_setup)
            d = None
            if m["entry_i"] is not None:
                bs += 1
                d = min(abs(c["entry_i"] - m["entry_i"]) for c in cands)
                dl.append(d)
                b3 += int(d <= 3)
                b1 += int(d <= 1)
            det.append({"key": k, "austin_setup": m["setup"], "engine_setup": sorted(eset),
                        "austin_entry_i": m["entry_i"],
                        "engine_entry_i": [c["entry_i"] for c in cands],
                        "engine_sgrade": [c["sgrade"] for c in cands],
                        "bar_delta": d, "setup_ok": ok_setup, "src": m["src"]})
        print("\n  %s  (n=%d days)" % (label, len(det)))
        print("    setup agreement      %3d/%-3d  %5.1f%%" % (sh, ss, pct(sh, ss)))
        print("    entry bar +/-3       %3d/%-3d  %5.1f%%   +/-1  %d/%d  %.1f%%"
              % (b3, bs, pct(b3, bs), b1, bs, pct(b1, bs)))
        if dl:
            sd = sorted(dl)
            print("    bar delta            min %d  median %d  mean %.1f  max %d"
                  % (sd[0], sd[len(sd) // 2], sum(sd) / len(sd), sd[-1]))
        return {"n_days": len(det), "setup": [sh, ss], "bar3": [b3, bs], "bar1": [b1, bs],
                "deltas": dl, "detail": det}

    OUT["agree_both_S"] = agree(inter, by_day, "AGREEMENT where BOTH called it S")
    OUT["agree_he_S_engine_traded"] = agree(
        a_S_book & e_traded_days, by_day_any,
        "AGREEMENT where HE called S and the engine traded ANY grade")

    detail = OUT["agree_both_S"]["detail"]
    print("\n  the %d days where both called S:" % len(detail))
    for dd in detail:
        print("    %-22s his=%-5s eng=%-22s bar his=%-5s eng=%-14s d=%s"
              % (dd["key"], dd["austin_setup"], ",".join(dd["engine_setup"]),
                 dd["austin_entry_i"], dd["engine_entry_i"], dd["bar_delta"]))
    print("\n  the %d days he called S where the engine traded ANY grade:"
          % OUT["agree_he_S_engine_traded"]["n_days"])
    for dd in OUT["agree_he_S_engine_traded"]["detail"]:
        print("    %-22s his=%-5s eng=%-8s grades=%-16s bar his=%-5s eng=%-16s d=%s"
              % (dd["key"], dd["austin_setup"], ",".join(dd["engine_setup"]),
                 ",".join(dd["engine_sgrade"]), dd["austin_entry_i"],
                 dd["engine_entry_i"], dd["bar_delta"]))

    # ------------------------------------------------------- 3. THE "RANDOM S"
    print("\n\n## 3. THE 'RANDOM S' -- engine S on days Austin refused\n")
    false_S = [r for r in s_traded if "%s_%s" % (r["sym"], r["day"]) in a_none_book]
    true_S = [r for r in s_traded if "%s_%s" % (r["sym"], r["day"]) in a_S_book]
    unjudged = [r for r in s_traded
                if "%s_%s" % (r["sym"], r["day"]) not in marks]
    print("engine traded-S rows on days he graded NONE : %d  (on %d symbol-days)"
          % (len(false_S), len({(r['sym'], r['day']) for r in false_S})))
    print("engine traded-S rows on days he graded S    : %d" % len(true_S))
    print("engine traded-S rows on days he never saw   : %d  (%.1f%% of all S trades)"
          % (len(unjudged), pct(len(unjudged), len(s_traded))))
    OUT["false_S_rows"] = len(false_S)
    OUT["true_S_rows"] = len(true_S)
    OUT["unjudged_S_rows"] = len(unjudged)

    FEATURES = ["level", "side", "slot", "seq", "bias", "aligned", "stopb", "gapb",
                "rangeb", "vol_regime", "spy_trend", "confluence", "tripped",
                "setup", "out", "scaled"]

    def profile(rows, name):
        print("\n  -- %s (n=%d)" % (name, len(rows)))
        if not rows:
            return {}
        prof = {}
        for f in FEATURES:
            c = collections.Counter(str(r.get(f)) for r in rows)
            top = c.most_common(3)
            prof[f] = {k: round(pct(v, len(rows)), 1) for k, v in c.items()}
            print("     %-12s %s" % (f, "  ".join("%s=%.0f%%" % (k, pct(v, len(rows))) for k, v in top)))
        tags = collections.Counter(t for r in rows for t in (r.get("tags") or []))
        prof["_tags"] = {k: round(pct(v, len(rows)), 1) for k, v in tags.items()}
        print("     %-12s %s" % ("tags", "  ".join("%s=%.0f%%" % (k, pct(v, len(rows))) for k, v in tags.most_common(5))))
        dg = collections.Counter(t for r in rows for t in (r.get("downgrades") or []))
        prof["_downgrades"] = {k: round(pct(v, len(rows)), 1) for k, v in dg.items()}
        print("     %-12s %s" % ("downgrades", "  ".join("%s=%.0f%%" % (k, pct(v, len(rows))) for k, v in dg.most_common(5)) or "(none)"))
        rs = [r["r"] for r in rows]
        prof["mean_r"] = round(sum(rs) / len(rs), 4)
        prof["win_rate"] = round(pct(sum(1 for r in rows if r["out"] == "win"), len(rows)), 1)
        print("     %-12s mean R %+.4f   win %.1f%%" % ("money", prof["mean_r"], prof["win_rate"]))
        return prof

    # The traded-S sample on judged days is tiny (see counts above), so the same
    # comparison is repeated at DETECTION granularity, where the population is
    # three orders of magnitude bigger.
    det_none = [r for r in s_all if "%s_%s" % (r["sym"], r["day"]) in a_none_book]
    det_S = [r for r in s_all if "%s_%s" % (r["sym"], r["day"]) in a_S_book]
    print("\n  at DETECTION granularity (bigger n):")
    print("    detected-S rows on days he graded NONE : %d  on %d of his %d refused days"
          % (len(det_none), len({(r['sym'], r['day']) for r in det_none}), len(a_none_book)))
    print("    detected-S rows on days he graded S    : %d  on %d of his %d S days"
          % (len(det_S), len({(r['sym'], r['day']) for r in det_S}), len(a_S_book)))
    print("    confluence-rescued share, refused days %.1f%%   S days %.1f%%"
          % (pct(*rescue(det_none)), pct(*rescue(det_S))))
    print("    -> the engine emits an S detection on %.1f%% of the days he REFUSED"
          % pct(len({(r['sym'], r['day']) for r in det_none}), len(a_none_book)))
    print("       and on %.1f%% of the days he called S"
          % pct(len({(r['sym'], r['day']) for r in det_S}), len(a_S_book)))
    OUT["det_S_on_none_days"] = [len({(r['sym'], r['day']) for r in det_none}), len(a_none_book)]
    OUT["det_S_on_S_days"] = [len({(r['sym'], r['day']) for r in det_S}), len(a_S_book)]

    p_false = profile(false_S, "S on days he graded NONE")
    p_true = profile(true_S, "S on days he graded S")
    p_all = profile(s_traded, "all engine S trades")
    OUT["profile_false_S"] = p_false
    OUT["profile_true_S"] = p_true
    OUT["profile_all_S"] = p_all

    # The traded-S profiles above are n=4 each and are printed for completeness
    # only -- no feature gap on n=4 is a finding. The comparison that carries the
    # answer is the detection-granularity one below, n=157 vs n=146.
    p_dnone = profile(det_none, "DETECTED S on days he graded NONE")
    p_dS = profile(det_S, "DETECTED S on days he graded S")
    OUT["profile_det_S_none_days"] = p_dnone
    OUT["profile_det_S_S_days"] = p_dS

    if det_none and det_S:
        print("\n  biggest feature gaps, refused-day S vs S-day S, DETECTION granularity "
              "(n=%d vs n=%d, pp):" % (len(det_none), len(det_S)))
        gaps = []
        for f in FEATURES + ["_tags", "_downgrades"]:
            a, b = p_dnone.get(f, {}), p_dS.get(f, {})
            for k in set(a) | set(b):
                if k in ("mean_r", "win_rate"):
                    continue
                gaps.append((abs(a.get(k, 0) - b.get(k, 0)), f, k, a.get(k, 0), b.get(k, 0)))
        gaps.sort(reverse=True)
        for g, f, k, av, bv in gaps[:14]:
            print("     %-12s %-24s refused %5.1f%%  vs S-day %5.1f%%   gap %.1f" % (f, k, av, bv, g))
        OUT["feature_gaps"] = [{"feature": f, "value": k, "refused_pct": av, "sday_pct": bv,
                                "gap_pp": round(g, 1)} for g, f, k, av, bv in gaps[:12]]

    # ------------------------------------------------------- 4. THE W4 CEILING
    print("\n\n## 4. WHERE THE MISSING N IS -- w4's 198 candidates today\n")
    cand = [json.loads(l) for l in open(W4, encoding="utf-8") if l.strip()]
    judged_now = bd.marked_card_ids()
    covered = [c for c in cand if c["key"] in judged_now]
    new = [c for c in cand if c["key"] not in judged_now]
    print("w4 candidates                       %4d" % len(cand))
    print("  already judged as of today        %4d" % len(covered))
    print("  still NEW (never judged)          %4d" % len(new))
    prov = collections.Counter(c["provenance"] for c in new)
    print("  by provenance: %s" % dict(prov))
    in_roster = [c for c in new if c["symbol"] in syms]
    in_win = [c for c in new if first <= c["date"] <= last]
    print("  new AND on a book symbol          %4d" % len(in_roster))
    print("  new AND inside the book window    %4d" % len(in_win))
    print("  new AND both                      %4d" % len({c["key"] for c in new
                                                           if c["symbol"] in syms and first <= c["date"] <= last}))
    print("\n  ceiling on graded symbol-days if every candidate were harvested:")
    print("    today                  %4d" % len(judged_now))
    print("    + all 198 candidates   %4d   (+%.1f%%)"
          % (len(judged_now) + len(new), pct(len(new), len(judged_now))))
    a_S_now = len(a_S)
    print("\n  and the S count is the binding number, not the day count:")
    print("    Austin S symbol-days today      %4d" % a_S_now)
    s_share = a_S_now / len(marks)
    print("    his S share of judged days      %.1f%%" % (100 * s_share))
    print("    expected S from 198 new days    %4.0f  (at his own historical S rate)"
          % (s_share * len(new)))
    OUT["w4_total"] = len(cand)
    OUT["w4_covered"] = len(covered)
    OUT["w4_new"] = len(new)
    OUT["w4_new_by_provenance"] = dict(prov)
    OUT["judged_now"] = len(judged_now)
    OUT["ceiling_judged"] = len(judged_now) + len(new)
    OUT["expected_new_S"] = round(s_share * len(new), 1)

    # ------------------------------- 5. THE THREE WAYS, PRICED ON THE HELD-OUT
    print("\n\n## 5. THE THREE WAYS TO GET MORE S TRADES, PRICED\n")
    ho = [json.loads(l) for l in open(HELDOUT, encoding="utf-8") if l.strip()]
    ho_t = collections.Counter()
    for c in ho:
        t, _ = norm_tier(c)
        ho_t[t] += 1
        c["_tier"] = t
    print("held-out set: %d cards  %s" % (len(ho), dict(ho_t)))
    ho_S = [c for c in ho if c["_tier"] == "S"]
    ho_X = [c for c in ho if c["_tier"] == "none"]

    # index the book by symbol-day
    idx = collections.defaultdict(list)
    for r in T:
        idx["%s_%s" % (r["sym"], r["day"])].append(r)

    cov = sum(1 for c in ho if "%s_%s" % (c["symbol"], c["date"]) in idx)
    cov_S = sum(1 for c in ho_S if "%s_%s" % (c["symbol"], c["date"]) in idx)
    print("  of those, symbol-days this book carries at least one DETECTION for: %d of %d "
          "(S cards %d of %d)" % (cov, len(ho), cov_S, len(ho_S)))
    print("  the rest are days the engine was structurally silent -- no arm below can reach them.")
    print("  NOTE: the published held-out figures (3/15 S recall, 12/42 false fire) come from")
    print("  research/t70_test1_score.py, which drives t4_engine_recall.run_day, a DIFFERENT")
    print("  replay from this book. The arms below are all measured on THIS book, so the")
    print("  deltas between them are comparable; the A0 absolute is not the published one.")
    OUT["heldout_book_coverage"] = [cov, len(ho)]
    OUT["heldout_S_book_coverage"] = [cov_S, len(ho_S)]

    ARMS = [
        ("A0 shipped (traded=True)", lambda r: r.get("traded")),
        ("A1 alert or traded", lambda r: r.get("traded") or r.get("alert")),
        ("A2 any detection graded S by downgrade.py", lambda r: r["sgrade"] == "S"),
        ("A3 any detection graded S or A", lambda r: r["sgrade"] in ("S", "A")),
        ("A4 any detection at all", lambda r: True),
    ]
    print("\n%-42s %-14s %-16s %-8s %s" % ("arm", "S recall", "false fire (X)", "gate", "book n"))
    arm_rows = []
    for name, f in ARMS:
        hit_S = sum(1 for c in ho_S if any(f(r) for r in idx.get("%s_%s" % (c["symbol"], c["date"]), [])))
        hit_X = sum(1 for c in ho_X if any(f(r) for r in idx.get("%s_%s" % (c["symbol"], c["date"]), [])))
        n_book = sum(1 for r in T if f(r))
        gate = hit_S / len(ho_S) - hit_X / len(ho_X)
        print("%-42s %2d/%-2d %6.1f%% %3d/%-3d %7.1f%% %+8.3f %8d"
              % (name, hit_S, len(ho_S), pct(hit_S, len(ho_S)),
                 hit_X, len(ho_X), pct(hit_X, len(ho_X)), gate, n_book))
        arm_rows.append({"arm": name, "s_recall": [hit_S, len(ho_S)],
                         "false_fire": [hit_X, len(ho_X)], "gate": round(gate, 4),
                         "book_n": n_book})
    OUT["heldout_arms"] = arm_rows

    # The money price of each arm. NOTE: rows the engine did not trade carry an R
    # computed from an un-clamped risk denominator -- 1,044 of the 7,326 dropped S
    # detections have |entry - stop| < $0.01 and the max R in that population is
    # +16,350. Mean R over any arm that includes non-traded rows is therefore
    # UNUSABLE and is printed only to show how broken it is; read the win rate and
    # the median, which are denominator-free.
    print("\n  money price of each arm (win rate and MEDIAN R; mean is unusable off-book)")
    print("  %-42s %7s %8s %9s %12s" % ("arm", "n", "win%", "median R", "mean R (bad)"))
    for (name, f), row in zip(ARMS, arm_rows):
        rows = [r for r in T if f(r)]
        rs = sorted(r["r"] for r in rows)
        w = pct(sum(1 for r in rows if r["out"] == "win"), len(rows))
        med = rs[len(rs) // 2]
        mean = sum(rs) / len(rs)
        untraded = sum(1 for r in rows if not r.get("traded"))
        print("  %-42s %7d %7.1f%% %+9.3f %+12.1f   (%d non-traded rows)"
              % (name, len(rows), w, med, mean, untraded))
        row["win_pct"] = round(w, 2)
        row["median_r"] = round(med, 4)
        row["mean_r_unusable"] = round(mean, 3)
        row["non_traded_rows"] = untraded
    tiny = sum(1 for r in T if r["sgrade"] == "S" and not r.get("traded")
               and abs(r["entry"] - r["stop"]) < 0.01)
    print("  evidence the mean is unusable: %d dropped-S rows have |entry-stop| < $0.01, "
          "max R in that population %+.0f" % (tiny, max(r["r"] for r in T if r["sgrade"] == "S")))
    OUT["dropped_S_subcent_rows"] = tiny

    # (b) widen the universe
    ho_off = [c for c in ho if c["symbol"] not in syms]
    ho_S_off = [c for c in ho_S if c["symbol"] not in syms]
    a_S_off = [k for k in a_S if k.rsplit("_", 1)[0] not in syms]
    a_S_out_win = [k for k in a_S if k.rsplit("_", 1)[0] in syms
                   and not (first <= k.rsplit("_", 1)[1] <= last)]
    print("\n(b) WIDEN THE UNIVERSE")
    print("  held-out cards on a symbol the book does not carry : %d of %d" % (len(ho_off), len(ho)))
    print("  held-out S cards off-roster                        : %d of %d" % (len(ho_S_off), len(ho_S)))
    print("  Austin S days off-roster                           : %d of %d  (%s)"
          % (len(a_S_off), len(a_S),
             dict(collections.Counter(k.rsplit('_', 1)[0] for k in a_S_off).most_common(8))))
    print("  Austin S days on-roster but outside the 2y window  : %d" % len(a_S_out_win))
    print("  w4 new candidates off-roster                       : %d of %d"
          % (sum(1 for c in new if c["symbol"] not in syms), len(new)))
    OUT["heldout_offroster"] = len(ho_off)
    OUT["heldout_S_offroster"] = len(ho_S_off)
    OUT["austin_S_offroster"] = len(a_S_off)
    OUT["austin_S_outside_window"] = len(a_S_out_win)

    # (c) accept the count, improve R
    print("\n(c) ACCEPT THE COUNT, IMPROVE PER-TRADE R")
    for name, rows in (("S", s_traded),
                       ("A", [r for r in traded if r["sgrade"] == "A"]),
                       ("C", [r for r in traded if r["sgrade"] == "C"]),
                       ("whole book", traded)):
        rs = [r["r"] for r in rows]
        w = sum(1 for r in rows if r["out"] == "win")
        print("  %-11s n=%4d  mean R %+.4f  win %.1f%%  total %+.1fR"
              % (name, len(rows), sum(rs) / len(rs), pct(w, len(rows)), sum(rs)))
    # what average win is needed at the S win rate to reach 2.0R
    wr = sum(1 for r in s_traded if r["out"] == "win") / len(s_traded)
    need = (2.0 + (1 - wr)) / wr
    print("  to reach mean R 2.0 at the S win rate (%.1f%%), wins must average %+.2fR "
          "(they average %+.2fR today)"
          % (100 * wr, need,
             sum(r["r"] for r in s_traded if r["out"] == "win") /
             max(1, sum(1 for r in s_traded if r["out"] == "win"))))
    OUT["s_mean_r"] = round(sum(r["r"] for r in s_traded) / len(s_traded), 4)
    OUT["s_win_rate"] = round(100 * wr, 2)
    OUT["s_needed_avg_win"] = round(need, 3)

    if args.json:
        json.dump(OUT, open(args.json, "w", encoding="utf-8"), indent=1)
        print("\nwrote %s" % args.json)


if __name__ == "__main__":
    main()
