"""w11_tz_exit_efficiency.py -- W11: Austin's own book already recorded the give-back.

Read-only against `data/tradezella_trades.csv` (350 rows, NVDA + TSLA, 2024-01-03 ->
2025-01-30, recovered from git history at 26ba3f48 by W6). Every row carries
`Account Name = Backtesting` -- this is Austin's hand-replay journal, not a live
executed fill record (W6 already made this correction; W11 repeats it because every
number below inherits it).

No engine run, no bar fetch, no default changed. `--selfcheck` runs 6 assertions
against known rows so a future reader does not have to trust the prose.

Produces `research/w11_tz_exit_efficiency.md`.
"""
import csv
import statistics
import sys
from datetime import datetime, timedelta

CSV_PATH = "data/tradezella_trades.csv"


def load_rows(path=CSV_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(row, key):
    v = row.get(key, "")
    if v is None or v.strip() == "":
        return None
    return float(v)


def parse_open_dt(row):
    # "Open Date" = 2024-01-03, "Open Time" = "09:43:59 EST" / "09:43:59 EDT"
    date_s = row["Open Date"]
    time_s, tz = row["Open Time"].rsplit(" ", 1)
    naive = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M:%S")
    return naive, tz


def parse_best_exit_dt_local(row):
    # "Best Exit Time" = "2024-01-03 15:18:00 UTC" -> convert to the row's own
    # local clock using the SAME EST/EDT offset its Open Time already carries
    # (TradeZella prints the correct local abbreviation per DST, so borrowing it
    # is exact, not approximate).
    v = row.get("Best Exit Time", "")
    if not v or v.strip() == "":
        return None
    date_s, time_s, _utc = v.split(" ")
    utc_dt = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M:%S")
    _, tz = row["Open Time"].rsplit(" ", 1)
    offset_hours = 5 if tz == "EST" else 4  # EDT = UTC-4
    return utc_dt - timedelta(hours=offset_hours)


def risk_per_share(row):
    trade_risk = fnum(row, "Trade Risk")
    qty = fnum(row, "Quantity")
    if trade_risk is None or qty in (None, 0):
        return None
    return abs(trade_risk) / qty


def split_adjusted_scale(row):
    """`Price MFE`/`Price MAE` are stored SPLIT-ADJUSTED for NVDA rows before its
    2024-06-07 10:1 split, while `Entry Price`/`Exit Price` are NOT -- a real
    scale inconsistency in the source CSV (confirmed: Entry/PriceMFE ~= 10.0 for
    every NVDA row opened before 2024-06, ~= 1.0 for every TSLA row and every
    post-split NVDA row). Detected per-row from the ratio itself, not a hardcoded
    date cutoff, so it self-corrects if the export ever changes shape."""
    entry = fnum(row, "Entry Price")
    price_mfe = fnum(row, "Price MFE")
    if not entry or not price_mfe or price_mfe == 0:
        return 1.0
    ratio = entry / price_mfe
    return 10.0 if ratio > 5.0 else 1.0


def mfe_r(row):
    """MFE in R, derived the same way W6 derives the stop: risk_per_share from
    Trade Risk / Quantity, then the favourable side's price move over that risk,
    correcting the NVDA pre-split scale artifact above."""
    rps = risk_per_share(row)
    price_mfe = fnum(row, "Price MFE")
    entry = fnum(row, "Entry Price")
    if rps is None or rps == 0 or price_mfe is None or entry is None:
        return None
    price_mfe *= split_adjusted_scale(row)
    if row["Side"] == "long":
        return (price_mfe - entry) / rps
    else:
        return (entry - price_mfe) / rps


def realized_r(row):
    return fnum(row, "Realized RR")


def pct(x, n):
    return 100.0 * x / n if n else float("nan")


def summarize(vals):
    vals = sorted(vals)
    n = len(vals)
    return {
        "n": n,
        "mean": statistics.mean(vals),
        "median": statistics.median(vals),
        "p25": vals[int(0.25 * (n - 1))],
        "p75": vals[int(0.75 * (n - 1))],
        "min": vals[0],
        "max": vals[-1],
    }


def month_key(row):
    return row["Open Date"][:7]


def build(rows):
    out = {}
    out["n_total"] = len(rows)
    out["accounts"] = sorted(set(r["Account Name"] for r in rows))

    # ---- Q1: Exit Efficiency ----
    wins = [r for r in rows if r["Status"] == "Win"]
    losses = [r for r in rows if r["Status"] == "Loss"]
    ee_present = [(r, fnum(r, "Exit Efficiency")) for r in rows]
    ee_wins_populated = [(r, v) for r, v in ee_present if v is not None]
    ee_wins_blank = [r for r in wins if fnum(r, "Exit Efficiency") is None]
    ee_losses_blank = [r for r in losses if fnum(r, "Exit Efficiency") is None]

    out["n_win"] = len(wins)
    out["n_loss"] = len(losses)
    out["ee_populated_n"] = len(ee_wins_populated)
    out["ee_blank_win_n"] = len(ee_wins_blank)
    out["ee_blank_loss_n"] = len(ee_losses_blank)
    # confirm: every EE-blank win has Realized RR == Reward Ratio (perfect-target exit)
    perfect_target_wins = 0
    for r in ee_wins_blank:
        rr, rw = fnum(r, "Realized RR"), fnum(r, "Reward Ratio")
        if rr is not None and rw is not None and abs(rr - rw) < 1e-6:
            perfect_target_wins += 1
    out["ee_blank_win_perfect_target_n"] = perfect_target_wins

    ee_vals = [v for _, v in ee_wins_populated]
    out["ee_summary"] = summarize(ee_vals)

    # Realized RR vs Reward Ratio (349 rows with Realized RR)
    rr_pairs = [
        (fnum(r, "Realized RR"), fnum(r, "Reward Ratio"))
        for r in rows
        if fnum(r, "Realized RR") is not None and fnum(r, "Reward Ratio") is not None
    ]
    out["rr_pairs_n"] = len(rr_pairs)
    out["realized_rr_summary"] = summarize([a for a, b in rr_pairs])
    out["reward_ratio_summary"] = summarize([b for a, b in rr_pairs])

    # Aggregate "share of MFE" the way h1_2y_nowatch.md computes it for the engine:
    # sum(realized R) / sum(MFE R), over the full 350-row book (losses included),
    # so it is denominator-comparable to the engine's 21.9%.
    r_and_mfe = []
    for r in rows:
        rv = realized_r(r)
        mv = mfe_r(r)
        if rv is not None and mv is not None:
            r_and_mfe.append((rv, mv))
    out["mfe_pairs_n"] = len(r_and_mfe)
    sum_r = sum(a for a, b in r_and_mfe)
    sum_mfe = sum(b for a, b in r_and_mfe)
    out["mean_realized_r_mfe_pop"] = sum_r / len(r_and_mfe)
    out["mean_mfe_r"] = sum_mfe / len(r_and_mfe)
    out["share_of_mfe_captured"] = sum_r / sum_mfe

    # per-trade capture ratio (only where MFE_R > 0, avoids div-by-~0 noise), for a median read
    per_trade_capture = [rv / mv for rv, mv in r_and_mfe if mv > 0.05]
    out["per_trade_capture_n"] = len(per_trade_capture)
    out["per_trade_capture_summary"] = summarize(per_trade_capture)

    # ---- Q2: Best Exit Time - Open Time ----
    # One row (2025-01-13, NVDA) has a 1423-minute (23.7h) gap and is the SAME
    # single row with no Realized RR / Reward Ratio -- a paired data anomaly, not
    # an intraday hold. Excluded from the "clean" population below; both are
    # reported so the exclusion is visible, not silent.
    gaps_min_all = []
    gaps_min_clean = []
    gaps_by_status = {"Win": [], "Loss": []}
    for r in rows:
        best_local = parse_best_exit_dt_local(r)
        if best_local is None:
            continue
        open_dt, _tz = parse_open_dt(r)
        delta_min = (best_local - open_dt).total_seconds() / 60.0
        gaps_min_all.append(delta_min)
        if realized_r(r) is not None:
            gaps_min_clean.append(delta_min)
            gaps_by_status[r["Status"]].append(delta_min)

    out["best_exit_gap_n_all"] = len(gaps_min_all)
    out["best_exit_gap_n_clean"] = len(gaps_min_clean)
    out["best_exit_gap_blank_n"] = len(rows) - len(gaps_min_all)
    out["best_exit_gap_summary_all"] = summarize(gaps_min_all)
    out["best_exit_gap_summary"] = summarize(gaps_min_clean)
    out["best_exit_gap_win_summary"] = summarize(gaps_by_status["Win"])
    out["best_exit_gap_loss_summary"] = summarize(gaps_by_status["Loss"])

    # bucket against the master-spec S1.4 clock: 100% to 10:30, 40-50% to 11:00, <=10% past 11:00
    # express as minutes-since-open buckets relative to open (approx, since entries
    # cluster 09:3x-10:0x): <=60min (roughly "before 10:30 if entered ~09:30-09:45"),
    # 60-90min, >90min. Also report by absolute best-exit clock time (local) directly,
    # which is the cleaner read since the schedule is clock-anchored, not open-anchored.
    buckets = {"<=10:30": 0, "10:30-11:00": 0, ">11:00": 0}
    for r in rows:
        best_local = parse_best_exit_dt_local(r)
        if best_local is None or realized_r(r) is None:
            continue
        t = best_local.time()
        if t <= datetime.strptime("10:30:00", "%H:%M:%S").time():
            buckets["<=10:30"] += 1
        elif t <= datetime.strptime("11:00:00", "%H:%M:%S").time():
            buckets["10:30-11:00"] += 1
        else:
            buckets[">11:00"] += 1
    out["best_exit_clock_buckets"] = buckets
    out["best_exit_clock_buckets_n"] = sum(buckets.values())

    # ---- Q3: Initial Target / Trade Risk (intended R) vs W2's flat_2.5r optimum ----
    reward_vals = [fnum(r, "Reward Ratio") for r in rows if fnum(r, "Reward Ratio") is not None]
    out["reward_ratio_full_summary"] = summarize(reward_vals)
    binned = {}
    for v in reward_vals:
        b = round(v / 0.25) * 0.25
        binned[b] = binned.get(b, 0) + 1
    out["reward_ratio_binned"] = dict(sorted(binned.items()))
    at_2r = sum(c for b, c in binned.items() if abs(b - 2.0) < 1e-9)
    at_25r = sum(c for b, c in binned.items() if abs(b - 2.5) < 1e-9)
    out["reward_ratio_at_2r_n"] = at_2r
    out["reward_ratio_at_25r_n"] = at_25r
    out["reward_ratio_n"] = len(reward_vals)

    # ---- Q4: Mistakes / Rating ----
    out["mistakes_populated_n"] = sum(1 for r in rows if r["Mistakes"].strip() not in ("", "nan"))
    out["rating_populated_n"] = sum(1 for r in rows if r["Rating"].strip() not in ("", "nan"))
    out["reviewed_true_n"] = sum(1 for r in rows if r["Reviewed"].strip().lower() == "true")

    # ---- Q5: Playbook ----
    playbooks = set(r["Playbook"] for r in rows)
    out["playbook_values"] = sorted(playbooks)
    out["playbook_uniform"] = len(playbooks) == 1

    return out


def selfcheck():
    rows = load_rows()
    ok = True

    def check(name, cond):
        nonlocal ok
        status = "PASS" if cond else "FAIL"
        if not cond:
            ok = False
        print(f"[{status}] {name}")

    check("350 rows loaded", len(rows) == 350)
    check("all rows Account Name = Backtesting", all(r["Account Name"] == "Backtesting" for r in rows))
    check("Playbook uniform", len(set(r["Playbook"] for r in rows)) == 1)
    check("Mistakes fully blank", all(r["Mistakes"].strip() == "" for r in rows))
    check("Rating fully blank", all(r["Rating"].strip() == "" for r in rows))

    # row 2 (0-indexed 1): Best Exit Time 2024-01-03 15:18:00 UTC, Open Time 09:48:59 EST
    # -> local best exit = 10:18:00 EST, gap = 29.017 minutes
    r1 = rows[1]
    best_local = parse_best_exit_dt_local(r1)
    open_dt, _ = parse_open_dt(r1)
    gap = (best_local - open_dt).total_seconds() / 60.0
    check("row2 best-exit gap ~= 29.02 min", abs(gap - 29.0167) < 0.01)

    # NVDA pre-split Price MFE scale correction: row0 is NVDA, opened 2024-01-03,
    # so Entry Price (480.37) should be ~10x its raw Price MFE (48.16).
    r0 = rows[0]
    check("NVDA pre-split scale detected as 10x", split_adjusted_scale(r0) == 10.0)
    tsla_row = next(r for r in rows if r["Symbol"] == "TSLA")
    check("TSLA scale untouched (1x)", split_adjusted_scale(tsla_row) == 1.0)

    out = build(rows)
    check("one row anomaly excluded from clean gap pop", out["best_exit_gap_n_all"] - out["best_exit_gap_n_clean"] == 1)
    check("Reward Ratio 2.0-bin is the largest bin", max(out["reward_ratio_binned"], key=out["reward_ratio_binned"].get) == 2.0)

    if ok:
        print("\nALL SELFCHECKS PASS")
    else:
        print("\nSELFCHECK FAILURE")
        sys.exit(1)


def main():
    if "--selfcheck" in sys.argv:
        selfcheck()
        return
    rows = load_rows()
    out = build(rows)
    for k, v in out.items():
        print(k, "=", v)


if __name__ == "__main__":
    main()
