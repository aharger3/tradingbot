"""G7.1 / instrument -- friction cost per trade, three instruments, one book.

Question (Austin, 2026-08-29): "i want trades that can realistically be done by a
robot and where it wont get killed or destroyed by fills or too tight rr".

This file answers ONE thing: how many R does it cost to CROSS THE SPREAD and pay
commissions, per trade, if the same 2,595-row ratified book were executed as
(a) shares, (b) 0DTE ATM options, (c) ES / MES index futures.

It is a friction calculator, not a new backtest. It changes no engine file and
touches no mark file. Every premium comes from `research/t7_real_contracts.py`'s
`Contract` (prior-session Parkinson sigma x 1.2 -- NO same-day range, so no
look-ahead), which is the repo's live, un-retracted options pricer.

Fee constants are sourced, dated, and listed in FEES below.

Run:
    python research/g71_instrument_spread.py
    python research/g71_instrument_spread.py --selfcheck
"""

from __future__ import annotations

import csv
import json
import os
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for p in (_ROOT, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import t7_real_contracts as t7                                   # noqa: E402

BOOK = os.path.join(_HERE, "bt2y_trades.json")
ARCHIVE = os.path.join(_ROOT, "data_archive")

# ---------------------------------------------------------------------------
# FEES -- every number here has a source and a date. Nothing is invented.
#
# tastytrade "Commissions & Fees", last updated 2026-07-30
#   https://assets.contentstack.io/v3/assets/blt7dc2e3d4a7071563/
#          blt2b752fef372188fe/commissions-and-fees
#     stock/ETF   : $0.00 commission; clearing $0.0008/share; FINRA TAF
#                   $0.000195/share on sales; SEC fee $20.60 per $1,000,000 sold
#     stock option: $1.00/contract to open, $0.00 to close; clearing
#                   $0.10/contract (each way); ORF $0.02/contract;
#                   FINRA TAF $0.00329/contract on sales
#     futures     : $1.00/contract per side; clearing $0.30/contract;
#                   + CME exchange fee + NFA fee
#     micro futures: $0.75/contract per side; clearing $0.30/contract
#
# CME exchange fee, non-member individual (2026 schedule, via Optimus/EdgeClear)
#     ES  $1.18 / side      MES $0.25 / side      NFA $0.02 / side
# ---------------------------------------------------------------------------
FEES = {
    "share_clearing_per_share": 0.0008,       # each way
    "share_taf_per_share": 0.000195,          # sell side only
    "share_sec_per_dollar": 20.60 / 1_000_000,  # sell side only
    "opt_commission_open": 1.00,
    "opt_commission_close": 0.00,
    "opt_clearing_each_way": 0.10,
    "opt_orf": 0.02,                          # each way
    "opt_taf_sell": 0.00329,
    "es_commission_side": 1.00,
    "es_clearing_side": 0.30,
    "es_exchange_side": 1.18,
    "es_nfa_side": 0.02,
    "mes_commission_side": 0.75,
    "mes_clearing_side": 0.30,
    "mes_exchange_side": 0.25,
    "mes_nfa_side": 0.02,
}
ES_ROUND_TURN = 2 * (FEES["es_commission_side"] + FEES["es_clearing_side"]
                     + FEES["es_exchange_side"] + FEES["es_nfa_side"])      # $5.00
MES_ROUND_TURN = 2 * (FEES["mes_commission_side"] + FEES["mes_clearing_side"]
                      + FEES["mes_exchange_side"] + FEES["mes_nfa_side"])   # $2.64
OPT_ROUND_TURN = (FEES["opt_commission_open"] + FEES["opt_commission_close"]
                  + 2 * FEES["opt_clearing_each_way"] + 2 * FEES["opt_orf"]
                  + FEES["opt_taf_sell"])                                   # ~$1.24

R_DOLLARS = 1000.0        # CLAUDE.md: 1R = $1,000
ES_POINT = 50.0
MES_POINT = 5.0
ES_TICK = 0.25            # ES/MES both quote in 0.25 pt ticks
ES_TICK_USD = ES_TICK * ES_POINT      # $12.50
MES_TICK_USD = ES_TICK * MES_POINT    # $1.25


# --------------------------------------------------------------------------- book

def load_traded():
    with open(BOOK, encoding="utf-8") as f:
        d = json.load(f)
    return [r for r in d["trades"] if r.get("traded")]


_spy_cache = {}


def spy_close(day):
    """SPY RTH close for `day` from data_archive. ES ~= 10 x SPY."""
    if day in _spy_cache:
        return _spy_cache[day]
    path = os.path.join(ARCHIVE, "SPY", day + ".csv")
    out = None
    if os.path.exists(path):
        last = None
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                t = row["Datetime"][11:19]
                if "09:30:00" <= t < "16:00:00":
                    last = row["Close"]
        if last:
            out = float(last)
    _spy_cache[day] = out
    return out


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def med(xs):
    return statistics.median(xs) if xs else float("nan")


def pct(xs, p):
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))]


# --------------------------------------------------------------------------- rows

class Row:
    """One book row costed on all three instruments."""

    def __init__(self, r):
        self.r = r
        self.risk_u = abs(r["entry"] - r["stop"])          # $/share, = 1R on shares
        self.entry = r["entry"]

        # -- shares
        self.shares = R_DOLLARS / self.risk_u if self.risk_u > 0 else 0.0

        # -- 0DTE ATM contract, priced by the LIVE (t7) pricer, prior-session sigma
        c = t7.Contract(r, None)                           # quote=None -> modelled
        self.c_ok = c.ok
        self.prem_risk = c.risk if c.ok else None          # $/share of premium = 1R
        self.prem_entry = c.p0 if c.ok else None
        self.contracts = (R_DOLLARS / (self.prem_risk * 100.0)
                          if c.ok and self.prem_risk > 0 else None)

        # -- ES/MES: the SAME stop geometry (stop_pct) mapped onto the index
        spy = spy_close(r["day"])
        self.es_ok = spy is not None and r.get("stop_pct")
        if self.es_ok:
            es_px = 10.0 * spy
            raw = r["stop_pct"] / 100.0 * es_px
            # a real futures stop cannot be finer than one tick
            self.es_pts = max(ES_TICK, round(raw / ES_TICK) * ES_TICK)
            self.es_contracts = R_DOLLARS / (self.es_pts * ES_POINT)
            self.mes_contracts = R_DOLLARS / (self.es_pts * MES_POINT)
        else:
            self.es_pts = self.es_contracts = self.mes_contracts = None

    # ---- friction, expressed in R -----------------------------------------
    def share_spread_R(self, spread):
        """Round trip = pay half the spread each side = one full spread."""
        return spread / self.risk_u

    def share_fee_R(self):
        f = (2 * FEES["share_clearing_per_share"] * self.shares
             + FEES["share_taf_per_share"] * self.shares
             + FEES["share_sec_per_dollar"] * self.shares * self.entry)
        return f / R_DOLLARS

    def opt_spread_R(self, spread):
        return spread / self.prem_risk

    def opt_fee_R(self):
        return OPT_ROUND_TURN * self.contracts / R_DOLLARS

    def es_spread_R(self):
        """ES is one tick wide essentially always; crossing it once = 1 tick."""
        return ES_TICK_USD / (self.es_pts * ES_POINT)

    def es_fee_R(self):
        return ES_ROUND_TURN * self.es_contracts / R_DOLLARS

    def mes_fee_R(self):
        return MES_ROUND_TURN * self.mes_contracts / R_DOLLARS


# --------------------------------------------------------------------------- report

def build(book):
    rows = []
    for r in book:
        if abs(r["entry"] - r["stop"]) <= 0:
            continue
        rows.append(Row(r))
    return rows


def section_geometry(rows):
    print("\n=== 1. THE R DENOMINATOR ON EACH INSTRUMENT ===")
    print("    (1R = $1,000; a THIN denominator is what makes a fixed cent-cost hurt)")
    ru = [x.risk_u for x in rows]
    pr = [x.prem_risk for x in rows if x.c_ok]
    ep = [x.es_pts for x in rows if x.es_ok]
    print("  shares    risk $/share      n=%4d  p10 %.3f  median %.3f  p90 %.3f"
          % (len(ru), pct(ru, 10), med(ru), pct(ru, 90)))
    print("  0DTE ATM  premium risk $/sh n=%4d  p10 %.3f  median %.3f  p90 %.3f"
          % (len(pr), pct(pr, 10), med(pr), pct(pr, 90)))
    print("  ES        risk in points    n=%4d  p10 %.2f  median %.2f  p90 %.2f"
          % (len(ep), pct(ep, 10), med(ep), pct(ep, 90)))
    sh = [x.shares for x in rows]
    ct = [x.contracts for x in rows if x.c_ok]
    ec = [x.es_contracts for x in rows if x.es_ok]
    mc = [x.mes_contracts for x in rows if x.es_ok]
    print("\n  SIZE AT $1,000 RISK  (what the robot has to actually get filled)")
    print("  shares      median %8.0f   p90 %9.0f   max %10.0f"
          % (med(sh), pct(sh, 90), max(sh)))
    print("  contracts   median %8.1f   p90 %9.1f   max %10.1f"
          % (med(ct), pct(ct, 90), max(ct)))
    print("  ES          median %8.2f   p90 %9.2f   max %10.2f"
          % (med(ec), pct(ec, 90), max(ec)))
    print("  MES         median %8.1f   p90 %9.1f   max %10.1f"
          % (med(mc), pct(mc, 90), max(mc)))


def section_friction(rows):
    print("\n=== 2. FRICTION PER TRADE, IN R (spread crossed once round trip + fees) ===")
    base = mean([x.r["r"] for x in rows])
    print("  book underlying mean R (no friction) = %+.4f  on n=%d" % (base, len(rows)))

    print("\n  -- SHARES --   spread is per SHARE")
    print("  %-12s %10s %10s %10s %10s" % ("spread", "mean R", "median R", "p90 R", "+fees"))
    fee_sh = mean([x.share_fee_R() for x in rows])
    for s in (0.01, 0.02, 0.05, 0.10):
        c = [x.share_spread_R(s) for x in rows]
        print("  $%-11.2f %10.4f %10.4f %10.4f %10.4f"
              % (s, mean(c), med(c), pct(c, 90), mean(c) + fee_sh))
    print("  commissions+clearing+TAF+SEC alone: %.4f R (mean)" % fee_sh)

    ok = [x for x in rows if x.c_ok]
    print("\n  -- 0DTE ATM OPTIONS --   spread is per share of PREMIUM (x100/contract)")
    print("  %-12s %10s %10s %10s %10s" % ("spread", "mean R", "median R", "p90 R", "+fees"))
    fee_op = mean([x.opt_fee_R() for x in ok])
    for s in (0.01, 0.02, 0.05, 0.10, 0.15):
        c = [x.opt_spread_R(s) for x in ok]
        print("  $%-11.2f %10.4f %10.4f %10.4f %10.4f"
              % (s, mean(c), med(c), pct(c, 90), mean(c) + fee_op))
    print("  commissions+clearing+ORF+TAF alone: %.4f R (mean, n=%d)" % (fee_op, len(ok)))

    eok = [x for x in rows if x.es_ok]
    es_sp = [x.es_spread_R() for x in eok]
    fee_es = mean([x.es_fee_R() for x in eok])
    fee_ms = mean([x.mes_fee_R() for x in eok])
    print("\n  -- ES / MES FUTURES --   spread is ONE TICK ($12.50 ES / $1.25 MES)")
    print("  1-tick cross      mean %.4f R   median %.4f R   p90 %.4f R"
          % (mean(es_sp), med(es_sp), pct(es_sp, 90)))
    print("  ES  fees          mean %.4f R  ($%.2f round turn x median %.2f contracts)"
          % (fee_es, ES_ROUND_TURN, med([x.es_contracts for x in eok])))
    print("  MES fees          mean %.4f R  ($%.2f round turn x median %.1f contracts)"
          % (fee_ms, MES_ROUND_TURN, med([x.mes_contracts for x in eok])))
    print("  ES  all-in (1 tick + fees)  = %.4f R" % (mean(es_sp) + fee_es))
    print("  MES all-in (1 tick + fees)  = %.4f R" % (mean(es_sp) + fee_ms))


def section_breakeven(rows):
    print("\n=== 3. HOW MUCH SPREAD KILLS EACH INSTRUMENT ===")
    base = mean([x.r["r"] for x in rows])
    fee_sh = mean([x.share_fee_R() for x in rows])
    # shares: mean cost per $0.01 of spread
    per_cent_sh = mean([x.share_spread_R(0.01) for x in rows])
    be_sh = 0.01 * (base - fee_sh) / per_cent_sh
    print("  shares    : book %+.4f R, fees %.4f R -> dies at a $%.4f round-trip spread"
          % (base, fee_sh, be_sh))

    ok = [x for x in rows if x.c_ok]
    cbase = mean([x.r["r"] for x in ok])   # underlying R on the same subset
    fee_op = mean([x.opt_fee_R() for x in ok])
    per_cent_op = mean([x.opt_spread_R(0.01) for x in ok])
    be_op = 0.01 * (cbase - fee_op) / per_cent_op
    print("  0DTE ATM  : (using underlying R %+.4f on the same %d rows as the edge,"
          % (cbase, len(ok)))
    print("               because T7 says contract R and underlying R are"
          " indistinguishable)")
    print("              fees %.4f R -> dies at a $%.4f round-trip option spread"
          % (fee_op, be_op))

    eok = [x for x in rows if x.es_ok]
    ebase = mean([x.r["r"] for x in eok])
    fee_es = mean([x.es_fee_R() for x in eok])
    per_tick = mean([x.es_spread_R() for x in eok])
    ticks = (ebase - fee_es) / per_tick
    print("  ES        : book %+.4f R, fees %.4f R -> survives %.1f TICKS of slippage"
          % (ebase, fee_es, ticks))
    print("              (ES is 1 tick wide in RTH; the strategy would need to eat"
          " %.0fx the posted spread to die)" % ticks)


def section_liquidity(rows):
    print("\n=== 4. CAN A ROBOT ACTUALLY GET FILLED? ===")
    ok = [x for x in rows if x.c_ok]
    ct = [x.contracts for x in ok]
    over = [c for c in ct if c >= 100]
    print("  0DTE ATM: median %.0f contracts, p90 %.0f, max %.0f; %d of %d rows (%.1f%%)"
          " want >=100 contracts"
          % (med(ct), pct(ct, 90), max(ct), len(over), len(ct),
             100.0 * len(over) / len(ct)))
    sh = [x.shares for x in rows]
    notional = [x.shares * x.entry for x in rows]
    print("  shares  : median %.0f shares (median $%.0f notional), p90 $%.0f, max $%.0f"
          % (med(sh), med(notional), pct(notional, 90), max(notional)))
    eok = [x for x in rows if x.es_ok]
    ec = [x.es_contracts for x in eok]
    print("  ES      : median %.2f contracts -- BELOW ONE CONTRACT on %d of %d rows"
          " (%.1f%%); MES median %.1f"
          % (med(ec), sum(1 for c in ec if c < 1), len(ec),
             100.0 * sum(1 for c in ec if c < 1) / len(ec),
             med([x.mes_contracts for x in eok])))

    print("\n=== 5. CAPITAL TIED UP PER TRADE (this is what options actually buy) ===")
    bp_share = [x.shares * x.entry / 4.0 for x in rows]   # 4:1 intraday reg-T margin
    debit = [x.prem_entry * 100.0 * x.contracts for x in ok]
    print("  shares  : $%.0f day-trading buying power at 4:1 (median), p90 $%.0f"
          % (med(bp_share), pct(bp_share, 90)))
    print("  0DTE ATM: $%.0f cash debit (median), p10 $%.0f, p90 $%.0f  -- capped loss"
          % (med(debit), pct(debit, 10), pct(debit, 90)))
    over = [d for d in debit if d > 10000]
    print("            %d of %d rows (%.1f%%) need a debit over $10,000 to risk $1,000"
          % (len(over), len(debit), 100.0 * len(over) / len(debit)))
    eok2 = [x for x in rows if x.es_ok]
    print("  ES      : ~$%s intraday margin per contract x median %.2f contracts"
          % ("500-2,500 (broker-set)", med([x.es_contracts for x in eok2])))

    print("\n=== 6. ES + MES BLEND (whole ES contracts, MES for the remainder) ===")
    blend = []
    for x in eok:
        n_es = int(x.es_contracts)
        n_mes = int(round((x.es_contracts - n_es) * 10))
        fee = n_es * ES_ROUND_TURN + n_mes * MES_ROUND_TURN
        blend.append(fee / R_DOLLARS)
    sp = [x.es_spread_R() for x in eok]
    print("  fees mean %.4f R   +1 tick %.4f R   = all-in %.4f R per trade"
          % (mean(blend), mean(sp), mean(blend) + mean(sp)))


def selfcheck(rows):
    print("\n=== SELFCHECK ===")
    ok = [x for x in rows if x.c_ok]
    # 1. no same-day range anywhere in the pricing path
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    _d = "d" + "range"
    for bad in ('["%s"]' % _d, ".get(\"%s\"" % _d, "row[%r]" % _d):
        assert bad not in src, "same-day range indexed off a book row"
    print("  [ok] no same-day range (`drange`) is ever read off a book row here")
    # 2. sigma traces to a prior session
    for x in ok[:50]:
        rng = t7.prior_session_range(x.r["sym"], x.r["day"])
        assert rng is not None and rng > 0
    print("  [ok] prior-session sigma present on sampled priced rows")
    # 3. fee arithmetic
    assert abs(ES_ROUND_TURN - 5.00) < 1e-9, ES_ROUND_TURN
    assert abs(MES_ROUND_TURN - 2.64) < 1e-9, MES_ROUND_TURN
    assert abs(OPT_ROUND_TURN - 1.24329) < 1e-9, OPT_ROUND_TURN
    print("  [ok] ES round turn $%.2f, MES $%.2f, option $%.5f/contract"
          % (ES_ROUND_TURN, MES_ROUND_TURN, OPT_ROUND_TURN))
    # 4. this file touches no engine file
    for f in ("backtest_2y.py", "backtest_week.py", "signal_runner.py"):
        s = open(os.path.join(_ROOT, f), encoding="utf-8").read()
        assert "g71_instrument" not in s
    print("  [ok] detection path does not import this file")
    # 5. share spread cost is exactly spread/risk
    x = rows[0]
    assert abs(x.share_spread_R(0.05) - 0.05 / x.risk_u) < 1e-12
    print("  [ok] share friction identity holds")
    print("ALL SELFCHECKS PASSED")


def main():
    book = load_traded()
    rows = build(book)
    print("book: research/bt2y_trades.json   traded rows n=%d   priced n=%d   ES-mappable n=%d"
          % (len(book), sum(1 for x in rows if x.c_ok), sum(1 for x in rows if x.es_ok)))
    if "--selfcheck" in sys.argv:
        selfcheck(rows)
        return
    section_geometry(rows)
    section_friction(rows)
    section_breakeven(rows)
    section_liquidity(rows)


if __name__ == "__main__":
    main()
