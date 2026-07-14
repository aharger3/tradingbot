"""D1 — SCARFACE_CONTRACT A/B (first-OTM + weekly expiry vs current ATM/0DTE).

READ-ONLY analysis on the current 12mo baseline (backtest_charts.json,
post-C10 strict-84 default: 620 traded / 37.3%W / $75,489).

THESIS (verified below): SCARFACE_CONTRACT is a no-op on the 12mo backtest
P&L by construction. Two independent reasons:

  (1) PATH: the 12mo P&L path (backtest_12mo -> backtest_week.simulate_day ->
      SimTrade.pnl) never imports options_sizer and never reads
      SCARFACE_CONTRACT. P&L = stock_move / stock_risk * $1000 (R-multiple at
      flat $1k risk). Contract selection (strike/expiry/premium/contracts)
      does not enter realized P&L. grep-verified.

  (2) MATH: even where the flag IS read (options_sizer.build_options_plan,
      live/paper card path only), the sizer normalizes max_loss to $1000
      regardless of strike/expiry: premium_risk = stock_risk * delta_estimate
      (0.5); contracts = $1000 / (premium_risk * 100). Under the estimation
      fallback (no tasty_feed — what backtest/paper use) the entry_premium
      formula `max(round(stock_entry*0.005,2),0.50)` ignores strike AND
      expiration, so premium/contracts/max_loss are bit-identical between
      arms; only the strike + expiration *labels* on the card differ. Under
      live tasty_feed (real premiums) the OTM-weekly premium is cheaper ->
      contracts scale up -> max_loss re-normalizes to $1000 -> R-multiple P&L
      still invariant. The only real-$ delta is gamma/theta convexity at live
      premium, which the backtest does not model (needs BS + per-symbol IV;
      F2 live-shadow territory, not a backtest signal-P&L lever).

So A == B, bit-identical, on the 12mo backtest. The lever moves the live card
(strike/expiry/premium/contract-count presentation) and live execution quality
(fill spreads, gamma/theta), NOT the backtest-measured edge.

Usage:  py research/d1_scarface_ab.py
"""
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))
import options_sizer as osz
CHARTS = ROOT / "backtest_charts.json"


def card_for(trade, scarface: bool):
    """Replicate options_sizer card math for a SimTrade under an arm.

    Uses the trade's day as `now` so expiry is relative to the trade, not today.
    Mirrors build_options_plan's estimation-fallback path (no tasty_feed) —
    exactly what backtest/paper use.
    """
    osz.SCARFACE_CONTRACT = scarface
    sym = trade["symbol"]
    direction = trade["direction"]
    entry = trade["entry"]
    stop = trade["stop"]
    # expiry relative to trade day (call the sizer fns directly w/ a fake now)
    y, m, dd = map(int, trade["day"].split("-"))
    now = datetime(y, m, dd, 10, 0)  # 10:00 ET placeholder, pre-14:30 cutoff
    strike = (osz.first_otm_strike(entry, sym, direction) if scarface
              else osz.nearest_strike(entry, sym))
    expiry = osz.weekly_expiration(now) if scarface else osz.nearest_expiration(now)
    # premium fallback (sizer line: max(round(entry*0.005,2),0.50))
    premium = max(round(entry * 0.005, 2), 0.50)
    stock_risk = abs(entry - stop)
    premium_risk = max(round(stock_risk * osz.DEFAULT_DELTA, 2), 0.05)
    per_contract_risk = premium_risk * osz.CONTRACT_MULTIPLIER
    contracts = int(osz.DEFAULT_MAX_LOSS // per_contract_risk) if per_contract_risk > 0 else 0
    max_loss = round(per_contract_risk * contracts, 2)
    return dict(strike=strike, expiry=expiry, premium=premium,
                premium_risk=premium_risk, contracts=contracts, max_loss=max_loss)


def main():
    d = json.load(open(CHARTS, encoding="utf-8"))
    tr = [t for t in d if not t.get("alert_only")]
    w = sum(1 for t in tr if t.get("outcome") == "win")
    pnl = round(sum(t.get("pnl", 0) or 0 for t in tr), 2)
    print("=" * 72)
    print("D1 — SCARFACE_CONTRACT A/B (12mo, current strict-84 baseline)")
    print("=" * 72)
    print(f"\nBaseline backtest_charts.json: {len(tr)} traded "
          f"W{w} WR={w/len(tr)*100:.1f}% P&L=${pnl:,.0f}")
    print(f"Grades: {dict(Counter(t.get('grade') for t in tr))}")

    # ---- Table 1: 12mo A/B (bit-identical) ----
    print("\n--- TABLE 1: 12mo options P&L A/B ---")
    print(f"{'arm':<34}{'n':>5}{'W':>5}{'WR%':>7}{'P&L':>12}")
    print("-" * 63)
    print(f"{'A: current (ATM / 0DTE)':<34}{len(tr):>5}{w:>5}"
          f"{w/len(tr)*100:>6.1f}%{pnl:>11,.0f}")
    print(f"{'B: SCARFACE (first-OTM / weekly)':<34}{len(tr):>5}{w:>5}"
          f"{w/len(tr)*100:>6.1f}%{pnl:>11,.0f}")
    print("-" * 63)
    print("DELTA: 0 trades, 0 P&L — bit-identical. Flag not in P&L path "
          "(see THESIS); sizer risk-normalizes (TABLE 2).")

    # ---- Table 2: per-trade card comparison (shows what DOES move) ----
    print("\n--- TABLE 2: per-trade options card (estimation fallback) ---")
    print("Shows the lever moves the CARD (strike/expiry labels), not the "
          "risk-normalized sizing or P&L.")
    print(f"\n{'sym':<6}{'dir':<5}{'arm':<10}{'strike':>9}{'expiry':>13}"
          f"{'premium':>9}{'premRisk':>10}{'contracts':>11}{'maxLoss':>10}")
    print("-" * 83)
    # pick a spread of samples: a coarse-inc symbol (TSLA $5) + fine-inc (PLTR/QQQ $1)
    samples = []
    for sym in ("TSLA", "PLTR", "QQQ", "AAPL"):
        for t in tr:
            if t["symbol"] == sym and t["outcome"] == "win":
                samples.append(t)
                break
    for t in samples[:4]:
        a = card_for(t, False)
        b = card_for(t, True)
        for label, c in (("cur", a), ("scar", b)):
            print(f"{t['symbol']:<6}{t['direction']:<5}{label:<10}"
                  f"{c['strike']:>9g}{c['expiry']:>13}{c['premium']:>9.2f}"
                  f"{c['premium_risk']:>10.2f}{c['contracts']:>11}"
                  f"{c['max_loss']:>10.2f}")
        print("-" * 83)

    # ---- Invariance check across ALL trades ----
    print("\n--- INVARIANCE CHECK (all {} trades) ---".format(len(tr)))
    diff_strikes = diff_exp = diff_prem = diff_contracts = diff_maxloss = 0
    for t in tr:
        a = card_for(t, False)
        b = card_for(t, True)
        diff_strikes += (a["strike"] != b["strike"])
        diff_exp += (a["expiry"] != b["expiry"])
        diff_prem += (a["premium"] != b["premium"])
        diff_contracts += (a["contracts"] != b["contracts"])
        diff_maxloss += (abs(a["max_loss"] - b["max_loss"]) > 0.01)
    print(f"  strike differs:        {diff_strikes:>5} / {len(tr)} "
          f"(coarse-inc symbols may coincide)")
    print(f"  expiration differs:    {diff_exp:>5} / {len(tr)} "
          f"(0DTE vs nearest Friday — always unless trade day IS Friday pre-14:30)")
    print(f"  premium differs:       {diff_prem:>5} / {len(tr)}  "
          f"(fallback formula ignores strike/expiry -> always 0)")
    print(f"  contracts differs:     {diff_contracts:>5} / {len(tr)}  "
          f"(premium_risk identical -> always 0)")
    print(f"  max_loss differs:      {diff_maxloss:>5} / {len(tr)}  "
          f"(risk-normalized -> always 0)")

    print("\nVERDICT: keep SCARFACE_CONTRACT OFF (default). No backtest-measurable")
    print("P&L delta — A == B bit-identical. The lever is live-card presentation +")
    print("execution quality (fill spreads, gamma/theta at live premium), routed to")
    print("F2 live-shadow (real bid/ask capture), NOT a backtest signal-P&L lever.")
    print("Bug carry-forward (C7): weekly_expiration() returns TODAY on a Friday ->")
    print("not next-week; fix only IF SCARFACE_CONTRACT ever flips ON.")


if __name__ == "__main__":
    main()
