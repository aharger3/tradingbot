"""OMEN 6 T60 -- the baseline every later number is measured against.

Ticket 03. One run, one report, four questions:

  1. HEADLINE      what the engine's own trades do under the settled exit ladder
  2. MONEY GATE    win rate vs 55%, annualised dollars at Austin's sizing
  3. DURABILITY    the same headline sliced per quarter / per symbol / per pool,
                   because the gate is that no single slice carries the result
  4. RECALL GATE   the engine scored against Austin's 120 graded day-cards, plus
                   the explicit list of days he traded and it stayed silent

Everything here is reproducible from committed inputs. The 5.2 scorecard was
not -- only its markdown output survives, with no script behind it -- which is
why this file exists rather than a re-run of that one.

    python research/t60_baseline.py

Writes research/t60_baseline.md and research/t60_silent_days.jsonl.
"""

from __future__ import annotations
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import research.exit_lab as exit_lab  # noqa: E402
from research.v52_scaleout_run import corpus_b_trades, bars_for  # noqa: E402
from universe import pool_for, MIN_SAMPLE_N  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_MD = os.path.join(HERE, "t60_baseline.md")
OUT_SILENT = os.path.join(HERE, "t60_silent_days.jsonl")

# The settled exit, from 5.2 T5 and re-measured after the ticket 02 fix.
POLICY = "30_30_30_10"

# Sizing, settled in the 2026-08-23 Q&A. Austin priced max stop slippage at
# -1.25R = $1,250, so 1R = $1,000. That implies roughly a $100k account at 1%
# risk, NOT the $52k on record from omen-5.0 T4 -- every dollar figure published
# before 2026-08-23 is scaled to the wrong number.
#
# The instrument is options, not shares. R-multiples survive that translation;
# dollars are a sizing layer on top and are reported as an indication only.
R_DOLLARS = 1_000.0
RISK_DOLLARS = R_DOLLARS
TRADING_DAYS_PER_YEAR = 252

# The money gate, restated 2026-08-23. Austin: "the six figures should be a
# correlation with average trade at 2R, which may or may not correlate to the
# winrate number." So mean R is the gate and win rate is a secondary read.
MEAN_R_GATE = 2.0
WIN_RATE_GATE = 0.55
DOLLAR_GATE = 100_000.0

# Durability slice, tightened 2026-08-23 from quarterly to monthly: "How about
# every month green?" -- 3x as many chances to fail, which is the point.

ENTRY_TOL = 3  # +/- bars for an entry to count as matching Austin's


# ---------------------------------------------------------------------------
# stats helpers
# ---------------------------------------------------------------------------

def max_consec_losers(rs):
    worst = run = 0
    for r in rs:
        if r < 0:
            run += 1
            worst = max(worst, run)
        else:
            run = 0
    return worst


def summarise(rows):
    """rows: list of (r_multiple, date). Returns the headline dict."""
    rs = [r for r, _ in rows]
    if not rs:
        return None
    days = {d for _, d in rows}
    per_year = len(rs) * TRADING_DAYS_PER_YEAR / max(len(days), 1)
    mean = statistics.fmean(rs)
    return {
        "n": len(rs),
        "mean_r": mean,
        "median_r": statistics.median(rs),
        "win_rate": sum(1 for r in rs if r > 0) / len(rs),
        "worst": min(rs),
        "mcl": max_consec_losers(rs),
        "trading_days": len(days),
        "trades_per_year": per_year,
        "ann_dollars": mean * RISK_DOLLARS * per_year,
    }


def month_of(date_str):
    return date_str[:7]


def quarter_of(date_str):
    y, m, _ = date_str.split("-")
    return "%s-Q%d" % (y, (int(m) - 1) // 3 + 1)


def row(label, s):
    # G6/T5: a slice under the shared sample floor is still shown in full --
    # never dropped, never pulled out of any total -- just tagged so a thin
    # slice cannot be mistaken for a finding (research/p12_sample_floor.md).
    tag = " _(low n)_" if s["n"] < MIN_SAMPLE_N else ""
    return ("| %s%s | %d | %+.4f | %+.4f | %.3f | %.2f | %d | %s |"
            % (label, tag, s["n"], s["mean_r"], s["median_r"], s["win_rate"],
               s["worst"], s["mcl"], format(round(s["ann_dollars"]), "+,")))


HEAD = ("| slice | N | mean R | median R | win | worst | max consec losers | ann $ |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|")


# ---------------------------------------------------------------------------
# marks
# ---------------------------------------------------------------------------

def load_day_cards():
    """Austin's 120 graded day-cards, and his trade sub-rows."""
    days, trades = {}, []
    for path in exit_lab.MARKS_FILES:
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("type") == "day":
                days[(d["symbol"], d["date"])] = d
            elif d.get("type") == "trade":
                trades.append(d)
    return days, trades


def main():
    # ---- corpus B under the settled ladder -------------------------------
    fn = exit_lab.POLICIES[POLICY]
    results, skipped = [], 0
    for t in corpus_b_trades():
        bars = bars_for(t)
        if not bars or t["entry"] is None or t["stop"] is None or t["entry_i"] >= len(bars):
            skipped += 1
            continue
        r = fn(bars, t["entry_i"], t["entry"], t["stop"], t["side"])
        results.append({"r": r, "symbol": t["symbol"], "date": t["date"],
                        "entry_i": t["entry_i"], "side": t["side"]})

    allrows = [(x["r"], x["date"]) for x in results]
    head = summarise(allrows)

    # ---- durability slices -----------------------------------------------
    by_q, by_sym, by_pool = defaultdict(list), defaultdict(list), defaultdict(list)
    by_m = defaultdict(list)
    for x in results:
        by_m[month_of(x["date"])].append((x["r"], x["date"]))
        by_q[quarter_of(x["date"])].append((x["r"], x["date"]))
        by_sym[x["symbol"]].append((x["r"], x["date"]))
        by_pool[pool_for(x["symbol"])].append((x["r"], x["date"]))

    # ---- recall scorecard -------------------------------------------------
    days, trade_marks = load_day_cards()
    fired = defaultdict(list)
    for x in results:
        fired[(x["symbol"], x["date"])].append(x)

    graded = set(days)
    trade_days = {k for k, d in days.items() if (d.get("grade") or "").strip() not in ("", "none")}
    none_days = {k for k, d in days.items() if (d.get("grade") or "").strip() == "none"}
    s_days = {k for k, d in days.items() if (d.get("grade") or "").strip() == "S"}

    fired_graded = {k for k in graded if k in fired}
    hits = fired_graded & trade_days
    s_hits = fired_graded & s_days
    silent = sorted(trade_days - fired_graded)

    # entry match: does any engine entry land within +/-3 bars of a marked entry
    matched = 0
    for m in trade_marks:
        key = (m["symbol"], m["date"])
        if any(abs(x["entry_i"] - m["entry_i"]) <= ENTRY_TOL for x in fired.get(key, [])):
            matched += 1

    with open(OUT_SILENT, "w", encoding="utf-8") as f:
        for sym, date in silent:
            d = days[(sym, date)]
            f.write(json.dumps({
                "card_id": d.get("card_id"), "symbol": sym, "date": date,
                "grade": d.get("grade"), "day_type": d.get("day_type"),
                "n_trades": d.get("n_trades"), "notes": d.get("notes"),
                "pool": pool_for(sym),
            }) + "\n")

    # ---- report -----------------------------------------------------------
    L = []
    L.append("# T60 — the OMEN 6 baseline")
    L.append("")
    L.append("Generated by `research/t60_baseline.py`. Exit policy: **`%s`**, the ladder "
             "settled in 5.2 T5 and re-measured after the ticket 02 stop fix." % POLICY)
    L.append("")
    L.append("**Assumptions:**")
    L.append("")
    L.append("- Sizing: **1R = $%s**, settled 2026-08-23 from Austin's own -1.25R = $1,250. "
             "The instrument is **options**, not shares — R-multiples carry across, dollars "
             "do not, so read the dollar column as an indication and the R column as the "
             "result." % format(int(R_DOLLARS), ","))
    L.append("- **SPY is excluded**, per `universe.INCLUDE_SPY_IN_BACKTEST = False` — and the "
             "corpus predates that flag, so it never contained SPY trades. SPY is 30 of "
             "Austin's 120 graded days, so every recall figure below ignores a quarter of his "
             "graded set. Ratification is **Q12**; flipping it requires a fresh engine run, "
             "not a re-run of this script.")
    L.append("- Annualised dollars project the corpus's own trade rate onto %d trading days."
             % TRADING_DAYS_PER_YEAR)
    L.append("")
    L.append("## 1. Headline")
    L.append("")
    L.append(HEAD)
    L.append(row("all trades", head))
    if skipped:
        L.append("")
        L.append("_%d of %d ledger rows skipped (no bars, or entry beyond the session)._"
                 % (skipped, skipped + len(results)))
    L.append("")

    L.append("## 2. Money gate")
    L.append("")
    L.append("| gate | target | actual | verdict |")
    L.append("|---|---:|---:|---|")
    L.append("| **mean R (the gate)** | **%.2fR** | **%+.4fR** | **%s** |"
             % (MEAN_R_GATE, head["mean_r"], "PASS" if head["mean_r"] >= MEAN_R_GATE else "FAIL"))
    L.append("| win rate | %.0f%% | %.1f%% | %s |"
             % (WIN_RATE_GATE * 100, head["win_rate"] * 100,
                "PASS" if head["win_rate"] >= WIN_RATE_GATE else "FAIL"))
    L.append("| annual $ | $%s | $%s | %s |"
             % (format(int(DOLLAR_GATE), ","), format(int(head["ann_dollars"]), ","),
                "PASS" if head["ann_dollars"] >= DOLLAR_GATE else "FAIL"))
    L.append("")
    L.append("Win rate is measured **after** the ladder (Q4 default). Tranche 1 fills often, "
             "so this is structurally higher than a flat-exit win rate and the two are not "
             "comparable.")
    L.append("")
    rs = [x["r"] for x in results]
    sd = statistics.pstdev(rs) if len(rs) > 1 else 0.0
    half = 1.96 * sd / (len(rs) ** 0.5) if rs else 0.0
    lo, hi = head["mean_r"] - half, head["mean_r"] + half
    floor = round(min(rs), 4)
    at_floor = sum(1 for r in rs if round(r, 4) == floor)
    L.append("95%% CI on mean R: **%+.4f to %+.4f** (n=%d, sd %.3f). "
             "Decisive means the whole interval sits above zero." % (lo, hi, len(rs), sd))
    L.append("")
    L.append("> **What changed on 2026-08-23.** The previous baseline read `+1.5148R` mean "
             "with a `0.648` win rate. Both were artifacts. `exit_lab` stopped trades out on "
             "**wicks**, against a rule Austin had settled five times, and then filled every "
             "break-even stop **exactly at entry**, so the runner could not lose and the "
             "distribution had no left tail. Ticket 17 made the stop trigger on the candle "
             "close and fill at that close, floored at Austin's stated `-1.25R`. The left "
             "tail now exists: worst trade `%+.2fR`, **%d of %d trades on the floor**, and "
             "the **median trade is `%+.4fR`** — more than half the book is a full stop-out. "
             "The 5.2 conclusion that *exits are solved* was solved by a bug."
             % (floor, at_floor, len(rs), head["median_r"]))
    L.append("")
    L.append("The annualisation also assumes every engine trade is taken at full risk with no "
             "capital constraint, no commissions and no options spread — none of which is "
             "modelled anywhere in OMEN.")
    L.append("")

    L.append("## 3. Durability — no slice may carry the result alone")
    L.append("")
    L.append("The slice gate is **every month green** (Austin, 2026-08-23), tightened from "
             "quarterly. Per-pool and per-symbol are read for *concentration* — no single "
             "name may carry the book.")
    L.append("")
    L.append("Slices tagged `(low n)` are under %d trades (`universe.MIN_SAMPLE_N`) -- too "
             "few for the number to mean anything yet. Still shown, still counted in every "
             "total above; just not evidence on its own." % MIN_SAMPLE_N)
    L.append("")
    for title, group in (("Per month", by_m), ("Per quarter", by_q),
                         ("Per pool", by_pool), ("Per symbol", by_sym)):
        L.append("### %s" % title)
        L.append("")
        L.append(HEAD)
        for k in sorted(group):
            s = summarise(group[k])
            if s:
                L.append(row(k, s))
        L.append("")
        neg = [k for k in sorted(group) if (summarise(group[k]) or {}).get("mean_r", 0) < 0]
        L.append("**Negative slices:** %s" % (", ".join(neg) if neg else "_none_"))
        L.append("")

    top = max(by_sym, key=lambda k: sum(r for r, _ in by_sym[k]))
    total_r = sum(x["r"] for x in results)
    top_r = sum(r for r, _ in by_sym[top])
    L.append("**Concentration:** the single best symbol is **%s**, carrying %+.1fR of %+.1fR "
             "total (%.0f%%). The Q2 default gate is that no symbol carries more than 25%%."
             % (top, top_r, total_r, 100 * top_r / total_r if total_r else 0))
    L.append("")

    L.append("## 4. Recall gate — the engine against Austin's eyes")
    L.append("")
    L.append("Scored over his **%d graded day-cards** only." % len(graded))
    L.append("")
    L.append("| metric | value | note |")
    L.append("|---|---:|---|")
    L.append("| S-day recall **(the gate)** | %d/%d = %.3f | target 0.90 |"
             % (len(s_hits), len(s_days), len(s_hits) / len(s_days) if s_days else 0))
    L.append("| day recall (any tradeable grade) | %d/%d = %.3f | |"
             % (len(hits), len(trade_days), len(hits) / len(trade_days) if trade_days else 0))
    L.append("| day precision | %d/%d = %.3f | of days it fired on, how many you'd trade |"
             % (len(hits), len(fired_graded), len(hits) / len(fired_graded) if fired_graded else 0))
    L.append("| entry match ±%d bars | %d/%d = %.3f | measured, never gated |"
             % (ENTRY_TOL, matched, len(trade_marks),
                matched / len(trade_marks) if trade_marks else 0))
    L.append("| false fires on refused days | %d/%d | days you graded `none` |"
             % (len(fired_graded & none_days), len(none_days)))
    L.append("| **silent on days you traded** | **%d** | → `t60_silent_days.jsonl`, input to 09 |"
             % len(silent))
    L.append("")
    if silent:
        L.append("### The silent set")
        L.append("")
        bysym = Counter(s for s, _ in silent)
        L.append("| symbol | silent days |")
        L.append("|---|---:|")
        for s, c in bysym.most_common():
            L.append("| %s | %d |" % (s, c))
        L.append("")
    L.append("## Caveats that ride with every number here")
    L.append("")
    L.append("- The break-even stop fills **exactly at entry**, so the runner cannot lose. "
             "That is a modelling artifact — mean R is a ceiling (ticket 02, Q9).")
    L.append("- Corpus B is the engine's own trade ledger. It is **in-sample**: the rules were "
             "fitted on these days. The only real holdout is the forward clock (ticket 13).")
    L.append("- Austin has only ever graded QQQ, SPY and TSLA, so every recall figure rests on "
             "**three symbols** — and SPY is excluded from the engine, leaving two.")

    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")

    print("wrote %s" % OUT_MD)
    print("wrote %s (%d days)" % (OUT_SILENT, len(silent)))
    print("  N=%d mean=%+.4fR win=%.3f worst=%.2f ann=$%s"
          % (head["n"], head["mean_r"], head["win_rate"], head["worst"],
             format(int(head["ann_dollars"]), ",")))
    print("  S-day recall %d/%d   day recall %d/%d   precision %d/%d   silent %d"
          % (len(s_hits), len(s_days), len(hits), len(trade_days),
             len(hits), len(fired_graded), len(silent)))


if __name__ == "__main__":
    main()
