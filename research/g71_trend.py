"""G71/trend - does OMEN know how to follow the trend, and does trend filter it better?

Austin, 7.1 blocker 6: "we dont know if it knows how to follow the trend. this
can be archived but remembered it should be a filter to see if it shapes
results."

Three questions, one script.

(1) WHAT TREND MEANS TODAY  - written up in research/g71_trend.md, file:line.
(2) TREND AS A FILTER on the two-year book (research/bt2y_trades.json): six
    definitions x three arms (with-trend only / against-trend only /
    with+flat), each scored on mean R, win rate, months green, weeks green,
    and held-out S recall against the 34 S cards of
    research/marks/probe_s_sweep_2026-08-28.jsonl.
(3) HIS S DAYS - was the setup with-trend or counter-trend, per definition.

The six definitions, all causal (nothing reads a bar later than the entry):

  htf_h1sma20  the ENGINE'S OWN: last hourly close before the open vs SMA20 of
               hourly closes (backtest_week.htf_bias_for:713). Read straight
               off the book's `bias` column.
  dayopen      entry price vs today's 09:30 open - the "day trend so far" that
               signal_runner._calibration_grade:2020 actually computes.
  pd_dir       prior RTH session close vs its own open.
  dsma20       prior daily close vs the SMA20 of daily closes ending there.
  or15         09:44 close vs the 09:30 open. Signals before 09:45 are NOT
               labelled (that would be look-ahead); they land in `na`.
  ema20_5m     entry price vs a 20-period EMA of 5-minute RTH closes as of the
               last COMPLETED 5m bar before entry, EMA carried across sessions.

Filtering is a post-pass on the booked rows: the book is un-halted, filtered,
then the loss halt (loss_halt.apply_to_book, R31) is RE-RUN on the survivors,
because dropping a trade changes which days halt.

Usage:
  python research/g71_trend.py [--out research/g71_trend.json]
"""
from __future__ import annotations
import argparse, json, math, os, statistics as st, sys
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import loss_halt                                     # noqa: E402
from research import g71_trend_cache as tc           # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades.json")
SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
TOL = 0.001          # 0.1% dead band -> "flat"; mirrors htf_bias_for's 1.001/0.999

DEFS = ["htf_h1sma20", "dayopen", "pd_dir", "dsma20", "or15", "ema20_5m"]


# ------------------------------------------------------------------ helpers
def side(a, b, tol=TOL):
    """'bull' / 'bear' / 'flat' for a vs b with a 0.1% dead band."""
    if a is None or b is None or not b:
        return None
    if a > b * (1 + tol):
        return "bull"
    if a < b * (1 - tol):
        return "bear"
    return "flat"


def label(trend, direction):
    """aligned / opposed / flat / na for a trend side and a signal direction."""
    if trend is None:
        return "na"
    if trend == "flat":
        return "flat"
    want = "bull" if direction == "call" else "bear"
    return "aligned" if trend == want else "opposed"


def ema_at(rec, et):
    """The EMA of the last COMPLETED 5m bar at or before `et`."""
    best = None
    for end, v in rec.get("ema5m") or ():
        if end <= et:
            best = v
        else:
            break
    return best


def trend_sides(row, rec):
    """Every definition's trend side for one book row. None = not computable."""
    out = {}
    out["htf_h1sma20"] = {"bullish": "bull", "bearish": "bear",
                          "neutral": "flat"}.get(row.get("bias"))
    et = row.get("et") or ""
    entry = row.get("entry")
    if rec:
        out["dayopen"] = side(entry, rec.get("o"))
        out["pd_dir"] = side(rec.get("pd_c"), rec.get("pd_o"))
        out["dsma20"] = side(rec.get("pd_c"), rec.get("dsma20"))
        out["or15"] = side(rec.get("or_c"), rec.get("or_o")) if et >= "09:45" else None
        out["ema20_5m"] = side(entry, ema_at(rec, et))
    else:
        for k in ("dayopen", "pd_dir", "dsma20", "or15", "ema20_5m"):
            out[k] = None
    return out


def iso_week(day):
    y, m, d = (int(x) for x in day.split("-"))
    iy, iw, _ = date(y, m, d).isocalendar()
    return "%04d-W%02d" % (iy, iw)


def stats(rows):
    tr = [r for r in rows if r.get("traded")]
    rs = [r["r"] for r in tr]
    wins = sum(1 for r in tr if r["out"] == "win")
    losses = sum(1 for r in tr if r["out"] == "loss")
    by_m, by_w = defaultdict(float), defaultdict(float)
    for r in tr:
        by_m[r["ym"]] += r["r"]
        by_w[iso_week(r["day"])] += r["r"]
    sd = st.pstdev(rs) if len(rs) > 1 else 0.0
    return {
        "n": len(tr),
        "mean_r": st.fmean(rs) if rs else 0.0,
        "se_r": sd / math.sqrt(len(rs)) if rs else 0.0,
        "total_r": sum(rs),
        "win_rate": (wins / (wins + losses) * 100) if (wins + losses) else 0.0,
        "months": len(by_m), "months_green": sum(1 for v in by_m.values() if v > 0),
        "weeks": len(by_w), "weeks_green": sum(1 for v in by_w.values() if v > 0),
    }


def unhalt(rows):
    """Undo loss_halt.apply_to_book (same construction as research/t23_stack.py)."""
    tag = " [halt: %d consecutive losses]" % loss_halt.HALT_AFTER_CONSECUTIVE_LOSSES
    out = []
    for r in rows:
        if r.get("halted") or r.get("status") == "halted":
            r = dict(r)
            r["traded"] = True
            r["status"] = "fired"
            r.pop("halted", None)
            r["reason"] = r.get("reason", "").replace(tag, "")
        out.append(r)
    return out


def rehalt(rows):
    """Shallow-copy the rows, re-run R31 on this arm's survivors."""
    fresh = [dict(r) for r in rows]
    loss_halt.apply_to_book(fresh)
    return fresh


def read_sweep():
    S, refused, minute = set(), set(), {}
    with open(SWEEP, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            sym, _, day = r["card_id"].partition("_")
            key = (sym.upper(), day[:10])
            g = (r.get("answers") or {}).get("s") or []
            g = g[0].strip().lower() if g else ""
            (S if g == "s" else refused).add(key)
            m = (r.get("notes") or {}).get("min")
            if m and ":" in str(m):
                hh, _, mm = str(m).partition(":")
                minute[key] = "%02d:%02d" % (int(hh), int(mm))
    return S, refused, minute


def recall(rows, cards):
    fired = {(r["sym"].upper(), r["day"]) for r in rows if r.get("traded")}
    return len(fired & cards)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "g71_trend.json"))
    a = ap.parse_args()

    book = json.load(open(BOOK, encoding="utf-8"))
    rows = book["trades"]
    ctx = tc.load()
    S_cards, refused, minute = read_sweep()

    for r in rows:
        rec = (ctx.get(r["sym"]) or {}).get(r["day"])
        sides = trend_sides(r, rec)
        r["_trend"] = {k: label(v, r["dir"]) for k, v in sides.items()}

    base = rows
    base_unhalted = unhalt(rows)
    out = {"meta": dict(book["meta"]), "defs": {}, "coverage": {}, "agreement": {}}

    print("=" * 96)
    print("BOOK  %s -> %s   %d signals  %d traded"
          % (book["meta"]["first"], book["meta"]["last"],
             len(rows), sum(1 for r in rows if r["traded"])))
    b = stats(base)
    print("BASE  n=%d  mean %+.4fR (se %.4f)  win %.1f%%  months %d/%d  weeks %d/%d"
          % (b["n"], b["mean_r"], b["se_r"], b["win_rate"],
             b["months_green"], b["months"], b["weeks_green"], b["weeks"]))
    print("      S recall %d/%d   fires on his refusals %d/%d"
          % (recall(base, S_cards), len(S_cards), recall(base, refused), len(refused)))
    b["s_recall"] = recall(base, S_cards)
    b["false_fire"] = recall(base, refused)
    out["base"] = b

    print("\nCOVERAGE  (label mix; `na` = not computable / pre-09:45 for or15)")
    for d in DEFS:
        c_all = Counter(r["_trend"][d] for r in rows)
        c_tr = Counter(r["_trend"][d] for r in rows if r["traded"])
        out["coverage"][d] = {"all": dict(c_all), "traded": dict(c_tr)}
        print("  %-12s all %-58s traded %s"
              % (d, dict(c_all), dict(c_tr)))

    # how much do the six definitions even agree with each other?
    print("\nAGREEMENT between definitions on the traded book (aligned/opposed rows only)")
    tr = [r for r in rows if r["traded"]]
    for i, d1 in enumerate(DEFS):
        cells = []
        for d2 in DEFS:
            both = [r for r in tr if r["_trend"][d1] in ("aligned", "opposed")
                    and r["_trend"][d2] in ("aligned", "opposed")]
            same = sum(1 for r in both if r["_trend"][d1] == r["_trend"][d2])
            pct = same / len(both) * 100 if both else float("nan")
            cells.append("%5.1f" % pct)
            out["agreement"]["%s|%s" % (d1, d2)] = round(pct, 1)
        print("  %-12s %s" % (d1, " ".join(cells)))
    print("  %-12s %s" % ("", " ".join("%5s" % d[:5] for d in DEFS)))

    print("\nFILTER ARMS  (book un-halted, filtered, R31 re-run on survivors)")
    hdr = ("%-12s %-10s %6s %9s %10s %7s %7s %8s %7s %7s"
           % ("def", "arm", "n", "mean R", "move", "win%", "mo", "wk",
              "S rec", "false"))
    print(hdr)
    print("-" * len(hdr))
    for d in DEFS:
        for arm, keep in (("with", {"aligned"}),
                          ("against", {"opposed"}),
                          ("with+flat", {"aligned", "flat", "na"})):
            kept = rehalt([r for r in base_unhalted if r["_trend"][d] in keep])
            s = stats(kept)
            move = s["mean_r"] - b["mean_r"]
            bar = 1.96 * math.sqrt(s["se_r"] ** 2 + b["se_r"] ** 2)
            s.update({"move": move, "bar": bar, "null": abs(move) <= bar,
                      "s_recall": recall(kept, S_cards),
                      "false_fire": recall(kept, refused)})
            out["defs"].setdefault(d, {})[arm] = s
            print("%-12s %-10s %6d %+9.4f %9s%s %7.1f %3d/%-3d %3d/%-3d %4d/%-2d %4d/%d"
                  % (d, arm, s["n"], s["mean_r"], "%+.4f" % move,
                     "*" if abs(move) > bar else " ", s["win_rate"],
                     s["months_green"], s["months"], s["weeks_green"], s["weeks"],
                     s["s_recall"], len(S_cards), s["false_fire"], len(refused)))
    print("  * = the move exceeds its own 95% error bar. Everything else is a NULL.")

    # -------------------------------------------------------- (3) his S days
    print("\nHIS 34 S CARDS - with-trend or counter-trend?")
    by_card = defaultdict(list)
    for r in rows:
        k = (r["sym"].upper(), r["day"])
        if k in S_cards:
            by_card[k].append(r)

    per_card, tally = [], {d: Counter() for d in DEFS}
    for k in sorted(S_cards):
        sigs = by_card.get(k) or []
        et = minute.get(k)
        pick = None
        if sigs and et:
            pick = min(sigs, key=lambda r: abs(
                (int(r["et"][:2]) * 60 + int(r["et"][3:])) -
                (int(et[:2]) * 60 + int(et[3:]))))
        elif sigs:
            pick = sigs[0]
        rec = (ctx.get(k[0]) or {}).get(k[1])
        row = {"card": "%s_%s" % k, "marked_min": et, "in_book": bool(sigs),
               "n_signals": len(sigs), "archive": bool(rec),
               "engine_dir": pick["dir"] if pick else None,
               "engine_et": pick["et"] if pick else None,
               "engine_grade": pick["grade"] if pick else None,
               "traded": any(r["traded"] for r in sigs)}
        if pick:
            for d in DEFS:
                row[d] = pick["_trend"][d]
                tally[d][pick["_trend"][d]] += 1
        elif rec:
            sides = trend_sides({"bias": None, "et": et or "09:45",
                                 "entry": rec.get("c")}, rec)
            for d in DEFS:
                row[d] = (sides.get(d) or "-") + "?"
        per_card.append(row)

    out["s_cards"] = {"cards": per_card,
                      "tally": {d: dict(c) for d, c in tally.items()},
                      "n_S": len(S_cards),
                      "with_engine_signal": sum(1 for r in per_card if r["in_book"]),
                      "traded": sum(1 for r in per_card if r["traded"])}
    print("  %d of %d S cards produce any engine signal; %d produce a TRADE."
          % (out["s_cards"]["with_engine_signal"], len(S_cards),
             out["s_cards"]["traded"]))
    print("  Tally over the %d cards the engine has a signal for "
          "(direction = the engine signal nearest his marked minute):"
          % out["s_cards"]["with_engine_signal"])
    for d in DEFS:
        print("    %-12s %s" % (d, dict(tally[d])))
    print("\n  card                 min   dir  gr  trd  %s"
          % " ".join("%-9s" % d[:9] for d in DEFS))
    for r in per_card:
        print("  %-20s %-5s %-4s %-3s %-4s %s"
              % (r["card"], r["marked_min"] or "-", r["engine_dir"] or "-",
                 r["engine_grade"] or "-", "Y" if r["traded"] else ".",
                 " ".join("%-9s" % (r.get(d) or "-") for d in DEFS)))
    print("  (a trailing ? = no engine signal on that card, so the DAY's trend "
          "side is shown and no direction is known)")

    json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1, default=str)
    print("\nwrote %s" % a.out)


if __name__ == "__main__":
    main()
