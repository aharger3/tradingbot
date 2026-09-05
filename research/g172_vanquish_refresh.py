"""g172 -- Vanquish refresh: S=1R, classifier ON/OFF, the O1 winner (none),
and the SPX/XSP index-only insurance arm.

    python research/g172_vanquish_refresh.py

OMEN 9.0 row P2. Re-runs `research/g120_prop_arms.py`'s Vanquish Advanced
Options $50k sweep on top of three landed/refuted decisions instead of the
old g116 A_base arm (first size-gated candidate of the day, ANY grade):

  1. S = 1R (row L5, LANDED, `research/g144_s_flat_1r.py` /
     `test_s_flat_sizing.py`). Live, only `sac_grade == 'S'` ever sizes a
     card, and it now sizes at the full $1,000 (1R), not 80% of it through
     the retired A+/A/B/C/X ladder. The candidate stream this file sweeps is
     therefore restricted to the book's own `sgrade == 'S'` rows -- trading
     the funding-arm math against a stream that does not exist live (e.g.
     the old A_base arm, which lets grade B/C rows through) would price an
     eval that could never actually be attempted with the shipped sizing.
  2. S_CLASSIFIER ON/OFF (row F7, LANDED then REFUTED three times --
     `research/g156_s_classifier_v0.md`, refuters 1-3). Reported here
     "for completeness" per the row's own instruction and per how
     `research/g160_tweak_grid.py` already treats it -- NOT leaned on for
     which arm is fundable. Predicate reused byte-for-byte from g160:
     drop a candidate whose `level` is 'OR high'/'OR low' AND carries the
     'no_retest' downgrade in the book's own `downgrades` field.
  3. The O1 winner (row O1, REFUTED -- `research/g160_tweak_grid.py` /
     `research/o1_refuter3...`): the 16-arm day/window/tier/veto grid swept
     DAY_POLICY x ENTRY_WINDOW x TIER_POLICY x VETO_1D and NO arm, baseline
     included, is positive in both H1 and H2. **There is no O1 winner to
     ship.** This file adds nothing on top of the S-only stream for those
     four levers -- the S-restriction alone (already the live sizing rule,
     landed) is the only selection change applied.

Then the SPX/XSP arm: the same S-only, classifier-off candidate stream
restricted to `sym == 'SPY'` only, in case Vanquish's Advanced Options
underlyings turn out to be index-only (AUGUR.md's open question -- see
g120's own CONDITIONAL note, still unresolved). "SPY signals x10 as SPX"
names the MECHANISM, not a separate dollar multiplier applied in this file:
this book's R-multiples are risk-dollars-invariant (pnl = r * risk_dollars,
the same convention every arm in g120/g116 uses) -- trading the identical
directional SPY signal via SPX (priced ~10x SPY's per-point value) needs
roughly 10x the dollar risk per contract to reach an equivalent practical
position, and the fine risk-dollar sweep already spans that range in either
instrument. No SPX-specific bid/ask, margin, or single-leg-vs-spread pricing
is available in this repo (real SPX options data does not exist here, same
gap g116's own tape citation flags for single-name) -- this arm is a
CANDIDATE-COUNT question (is there enough SPY-only S-tier signal to clear
Vanquish's min_trading_days and profit target at all), not a re-priced one.

Options skin (delta 0.42 + $0.05 round-trip spread, CONFIDENCE LOW): reuses
the exact formula `research/options_sizer.py`'s own R7 fix and
`test_options_spread.py` establish -- a round-trip spread charges
`spread_R = DEFAULT_SPREAD / (stock_risk * DEFAULT_DELTA)` off every trade's
R-multiple, win or lose, once (options_sizer.py:64-73, the board's own
worked "-0.2042R" example is this formula at that trade's own stock_risk).
`DEFAULT_DELTA=0.42` and `DEFAULT_SPREAD=0.05` are imported from
`options_sizer.py`, not restated, so this file cannot drift from the shipped
constants. Reported BESIDE the untouched stock-R numbers (no spread, delta
irrelevant -- the current model every other g11x/g12x file already used) so
neither number is mistaken for the other. LOW CONFIDENCE because this repo
has no real options bid/ask tape to check the flat $0.05 estimate against
(same citation gap DEFAULT_SPREAD's own docstring names) and because the
per-trade spread_R depends on each row's own stop distance, not a single
number.

Written: research/g172_vanquish_refresh.md
"""
from __future__ import annotations

import gzip
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from omen_metrics import evaluate_prop_challenge, min_risk_floor
from options_sizer import DEFAULT_DELTA, DEFAULT_SPREAD

BOOK_JSON = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g172_vanquish_refresh.json")
OUT_MD = os.path.join(HERE, "g172_vanquish_refresh.md")

H_SPLIT = "2025-09-01"   # CLAUDE.md: split H1/H2 here, report both

VANQUISH_ACCOUNT = 50000.0
VANQUISH_KW = dict(
    profit_target_pct=0.10,
    trailing_dd_pct=0.05,
    dd_mode="eod",
    daily_loss_limit_pct=1.0,   # Vanquish: no daily loss limit -- disabled
    min_trading_days=4,
    consistency_pct=0.30,
)
VANQUISH_MONTHLY_FEE = 499.0
VANQUISH_RESET_FEE = 249.0
VANQUISH_HEADLINE_RISK = 1000.0   # the book's own native unit == S = 1R

# Same fine grid as g120 (its own ADVERSARIAL FIX docstring explains why a
# coarse 9-point grid can straddle a real passing band without ever landing
# in it): g116's 9-point RISK_PCTS grid plus explicit points through the
# worked example and the band g120's reviewer found.
RISK_PCTS = [0.0025, 0.0050, 0.0075, 0.0100, 0.0125, 0.0150, 0.0175, 0.0200,
             0.0250, 0.0300]
FINE_EXTRA = {r / VANQUISH_ACCOUNT for r in
              (100, 110, 120, 125, 130, 140, 150, 160, 170, 175, 178.5, 180,
               190, 200, 220, 240, 260, 280, 300, 350, 400, 450, 500)}
VANQUISH_FINE_PCTS = sorted(set(RISK_PCTS) | FINE_EXTRA)


# ==========================================================================
# candidate streams
# ==========================================================================
def load_rows():
    if os.path.exists(BOOK_JSON):
        book = json.load(open(BOOK_JSON))
    else:
        gz = BOOK_JSON + ".gz"
        if not os.path.exists(gz):
            raise FileNotFoundError("%s (or its .gz) not found" % BOOK_JSON)
        book = json.loads(gzip.open(gz, "rt").read())
    rows = [r for r in book["trades"] if r.get("traded") and r.get("r") is not None]
    rows.sort(key=lambda r: (r["day"], r["et"], r["sym"]))
    return rows, book["meta"]


def sizeable(r):
    return abs(r["entry"] - r["stop"]) >= min_risk_floor(r["entry"])


def classifier_drop(r):
    """S_CLASSIFIER v0 predicate, F7, byte-for-byte off g160_tweak_grid.py's
    own `_classifier_drop`: OR high/OR low break with no retest."""
    return r.get("level") in ("OR high", "OR low") and \
        "no_retest" in (r.get("downgrades") or ())


def build_s_arm(rows, *, classifier_on, symbol_filter=None):
    """First sizeable, sgrade=='S' candidate of the day (S=1R live sizing,
    row L5). classifier_on drops the S_CLASSIFIER v0 predicate rows first,
    falling through to the day's next S candidate if one survives --
    exactly how the live engine's DROP (not cap) behaves (signal_runner.py
    ~2809-2827). symbol_filter restricts the day's own candidate list to
    one symbol (the SPX/XSP arm) before picking."""
    by_day = defaultdict(list)
    for r in rows:
        if r.get("sgrade") != "S":
            continue
        if symbol_filter is not None and r["sym"] != symbol_filter:
            continue
        by_day[r["day"]].append(r)
    out = []
    for day in sorted(by_day):
        v = sorted(by_day[day], key=lambda r: (r["et"], r["sym"]))
        if classifier_on:
            v = [r for r in v if not classifier_drop(r)]
        pick = next((r for r in v if sizeable(r)), None)
        if pick is not None:
            out.append(pick)
    return out


def months_between(d0, d1):
    from datetime import date
    a = date(*map(int, d0.split("-")))
    b = date(*map(int, d1.split("-")))
    return (b - a).days / 30.4375


def spread_r(row):
    """spread_R = DEFAULT_SPREAD / (stock_risk * DEFAULT_DELTA), the R7 round
    -trip formula (options_sizer.py:64-73), applied once per trade."""
    stock_risk = abs(row["entry"] - row["stop"])
    if stock_risk <= 0:
        return 0.0
    return DEFAULT_SPREAD / (stock_risk * DEFAULT_DELTA)


def prop_row(arm, risk_dollars, options_skin=False, account=VANQUISH_ACCOUNT, **kw):
    if options_skin:
        pnl = [(r["day"], (r["r"] - spread_r(r)) * risk_dollars) for r in arm]
    else:
        pnl = [(r["day"], r["r"] * risk_dollars) for r in arm]
    res = evaluate_prop_challenge(pnl, account_size=account, **kw)
    res["risk_dollars"] = risk_dollars
    return res


def pass_day(arm, risk_dollars, options_skin=False, account=VANQUISH_ACCOUNT, **kw):
    for i in range(1, len(arm) + 1):
        r = prop_row(arm[:i], risk_dollars, options_skin, account, **kw)
        if r["passed"]:
            return arm[i - 1]["day"], i
    return None, None


def vanquish_sweep(arm, options_skin=False):
    if not arm:
        return []
    d0, d_last = arm[0]["day"], arm[-1]["day"]
    total_months_book = months_between(d0, d_last)
    rows = []
    for rp in VANQUISH_FINE_PCTS:
        risk = rp * VANQUISH_ACCOUNT
        res = prop_row(arm, risk, options_skin, **VANQUISH_KW)
        if options_skin:
            pnls = [(r["r"] - spread_r(r)) * risk for r in arm]
        else:
            pnls = [r["r"] * risk for r in arm]
        cum, s = [], 0.0
        for p in pnls:
            s += p
            cum.append(s)
        total_net_full_book = cum[-1]

        if res["passed"]:
            pd_, pi = pass_day(arm, risk, options_skin, **VANQUISH_KW)
            months = months_between(d0, pd_) if pd_ else None
            equity_at_event = cum[pi - 1] if pi else None
            sub_months = max(1, math.ceil(months)) if months is not None else None
            sub_cost = sub_months * VANQUISH_MONTHLY_FEE if sub_months else None
            reset_cost = 0.0
            net_after_cost = (equity_at_event - sub_cost) if (equity_at_event is not None and sub_cost is not None) else None
        else:
            pd_, pi = None, None
            fail_day = res["fail_day"]
            months = months_between(d0, fail_day) if fail_day else total_months_book
            equity_at_event = 0.0
            sub_months = max(1, math.ceil(months))
            sub_cost = sub_months * VANQUISH_MONTHLY_FEE
            reset_cost = VANQUISH_RESET_FEE
            net_after_cost = -(sub_cost + reset_cost)

        rows.append(dict(
            risk_pct=rp, risk_dollars=risk,
            is_headline_1000=(abs(risk - VANQUISH_HEADLINE_RISK) < 1e-6),
            passed=bool(res["passed"]), fail_reason=res["fail_reason"],
            first_fail_day=res["fail_day"], pass_day=pd_, pass_day_index=pi,
            months_to_event=round(months, 3) if months is not None else None,
            subscription_months_charged=sub_months, subscription_cost=sub_cost,
            reset_cost=reset_cost,
            total_net_dollars_full_book_if_ungated=round(total_net_full_book, 2),
            equity_at_pass_or_book_end=round(equity_at_event, 2) if equity_at_event is not None else None,
            net_dollars_after_cost=round(net_after_cost, 2) if net_after_cost is not None else None,
            final_equity_pct=res["final_equity_pct"],
            max_drawdown_seen_pct=res["max_drawdown_seen_pct"],
        ))
    return rows


def passing_band(sweep):
    passing = [r for r in sweep if r["passed"]]
    if not passing:
        return None
    lo = min(passing, key=lambda r: r["risk_dollars"])
    hi = max(passing, key=lambda r: r["risk_dollars"])
    best = min(passing, key=lambda r: (r["months_to_event"], r["risk_dollars"]))
    return dict(low_dollars=lo["risk_dollars"], high_dollars=hi["risk_dollars"],
                n_passing=len(passing), n_tested=len(sweep), best=best)


def rolling_start(arm, risk_dollars, options_skin=False, window=252, min_len=60):
    """Same idea as research/g116b_floor_and_rolling.py's 5b: from every
    possible start day in the arm, does a fresh $50k eval PASS within the
    next `window` trading days (~12 months)? Split H1/H2 by each WINDOW's
    own start day (CLAUDE.md's H1/H2 split), not the book's absolute day --
    a rolling-start question is inherently about start points, not halves."""
    if len(arm) < min_len:
        return dict(starts=0, pass_pct=None, h1_starts=0, h1_pass_pct=None,
                    h2_starts=0, h2_pass_pct=None)
    starts = n_pass = 0
    h1_n = h1_pass = h2_n = h2_pass = 0
    for i in range(len(arm)):
        win = arm[i:i + window]
        if len(win) < min_len:
            break
        starts += 1
        p = prop_row(win, risk_dollars, options_skin, **VANQUISH_KW)["passed"]
        n_pass += p
        if win[0]["day"] < H_SPLIT:
            h1_n += 1
            h1_pass += p
        else:
            h2_n += 1
            h2_pass += p
    return dict(
        starts=starts, pass_pct=round(100 * n_pass / starts, 1) if starts else None,
        h1_starts=h1_n, h1_pass_pct=round(100 * h1_pass / h1_n, 1) if h1_n else None,
        h2_starts=h2_n, h2_pass_pct=round(100 * h2_pass / h2_n, 1) if h2_n else None,
    )


def h1_h2_split(arm):
    h1 = [r for r in arm if r["day"] < H_SPLIT]
    h2 = [r for r in arm if r["day"] >= H_SPLIT]
    return h1, h2


def arm_summary(name, arm, options_skin_flag=True):
    """headline + best_pass at the book's native unit and (optionally) the
    options-skin variant, plus H1/H2 candidate counts and rolling-start."""
    out = dict(name=name, n_candidates=len(arm))
    if not arm:
        out["note"] = "no candidates -- arm is empty"
        return out
    h1, h2 = h1_h2_split(arm)
    out["first_day"], out["last_day"] = arm[0]["day"], arm[-1]["day"]
    out["n_h1"], out["n_h2"] = len(h1), len(h2)

    sweep_stock = vanquish_sweep(arm, options_skin=False)
    out["sweep_stock_r"] = sweep_stock
    out["band_stock_r"] = passing_band(sweep_stock)
    hl_stock = next((r for r in sweep_stock if r["is_headline_1000"]), None)
    out["headline_stock_r"] = hl_stock

    if options_skin_flag:
        sweep_opt = vanquish_sweep(arm, options_skin=True)
        out["sweep_options_skin"] = sweep_opt
        out["band_options_skin"] = passing_band(sweep_opt)
        hl_opt = next((r for r in sweep_opt if r["is_headline_1000"]), None)
        out["headline_options_skin"] = hl_opt

    band = out["band_stock_r"]
    rd = band["best"]["risk_dollars"] if band else VANQUISH_HEADLINE_RISK
    out["rolling_start_at_best_or_headline"] = rolling_start(arm, rd, options_skin=False)
    return out


# ==========================================================================
def main():
    rows, meta = load_rows()
    print("book: %s  sessions=%s  %s .. %s" % (BOOK_JSON, meta.get("sessions"),
          meta.get("first"), meta.get("last")))

    out = {"meta": meta, "delta": DEFAULT_DELTA, "spread": DEFAULT_SPREAD}

    print("\nO1: REFUTED, no winner (research/g160_tweak_grid.py) -- no day/window/"
          "tier/veto lever added on top of the S-only stream below.")
    out["o1_winner"] = None
    out["o1_note"] = ("O1 (16-arm day/window/tier/veto grid, incl. S_CLASSIFIER "
                       "on/off) found no arm positive in both H1 and H2, baseline "
                       "included -- REFUTED, nothing shipped. This file adds no "
                       "selection lever beyond the S-only restriction (already "
                       "landed, live sizing, row L5).")

    arms = {}
    for cls_on in (False, True):
        key = "S_1R_classifier_%s" % ("on" if cls_on else "off")
        arm = build_s_arm(rows, classifier_on=cls_on)
        print("\n=== %s: n=%d ===" % (key, len(arm)))
        summ = arm_summary(key, arm)
        arms[key] = summ
        if summ.get("band_stock_r"):
            b = summ["band_stock_r"]
            print("  passing band (stock-R): $%.2f-$%.2f/trade (%d/%d tested)"
                  % (b["low_dollars"], b["high_dollars"], b["n_passing"], b["n_tested"]))
            print("  best pass: $%.0f/trade, %.1f months, net after cost $%.0f"
                  % (b["best"]["risk_dollars"], b["best"]["months_to_event"],
                     b["best"]["net_dollars_after_cost"]))
        else:
            print("  no passing risk level in the sweep (stock-R)")
        if summ.get("headline_stock_r"):
            h = summ["headline_stock_r"]
            print("  headline $1,000/trade (stock-R): %s" %
                  ("PASS %.1fmo net $%.0f" % (h["months_to_event"], h["net_dollars_after_cost"])
                   if h["passed"] else "FAIL %s" % h["fail_reason"]))
        if summ.get("headline_options_skin"):
            h = summ["headline_options_skin"]
            print("  headline $1,000/trade (options skin, delta 0.42+$0.05 spread, LOW CONF): %s" %
                  ("PASS %.1fmo net $%.0f" % (h["months_to_event"], h["net_dollars_after_cost"])
                   if h["passed"] else "FAIL %s" % h["fail_reason"]))
        rs = summ["rolling_start_at_best_or_headline"]
        if rs["starts"]:
            print("  rolling-start pass rate: %.1f%% overall (%d starts) | H1 %s%% (%d) | H2 %s%% (%d)"
                  % (rs["pass_pct"], rs["starts"], rs["h1_pass_pct"], rs["h1_starts"],
                     rs["h2_pass_pct"], rs["h2_starts"]))
        else:
            print("  rolling-start: too few candidates (<%d) for a 252-session window" % 60)

    # ---------------- SPX/XSP index-only insurance arm ---------------------
    print("\n=== SPX/XSP arm: SPY-only S candidates, classifier off ===")
    spx_arm = build_s_arm(rows, classifier_on=False, symbol_filter="SPY")
    spx_summ = arm_summary("SPX_XSP_spy_only", spx_arm)
    out["spx_xsp_arm"] = spx_summ
    print("  n=%d SPY-only S candidates, %s" %
          (len(spx_arm), ("%s .. %s" % (spx_arm[0]["day"], spx_arm[-1]["day"])) if spx_arm else "EMPTY"))
    if spx_summ.get("band_stock_r"):
        b = spx_summ["band_stock_r"]
        print("  passing band: $%.2f-$%.2f/trade (%d/%d tested)"
              % (b["low_dollars"], b["high_dollars"], b["n_passing"], b["n_tested"]))
    else:
        print("  no passing risk level in the sweep")
    if len(spx_arm) < VANQUISH_KW["min_trading_days"]:
        print("  NOTE: fewer candidates than Vanquish's own min_trading_days=%d -- "
              "structurally cannot pass regardless of sizing" % VANQUISH_KW["min_trading_days"])

    out["arms"] = arms
    json.dump(out, open(OUT_JSON, "w"), indent=1)
    print("\nwrote", OUT_JSON)
    write_md(out)
    print("wrote", OUT_MD)
    return out


def _fmt_money(x):
    return "-" if x is None else ("$%s%.0f" % ("-" if x < 0 else "", abs(x)))


def write_md(out):
    lines = []
    lines.append("# g172 -- Vanquish refresh: S=1R, classifier ON/OFF, no O1 winner, SPX/XSP arm\n")
    lines.append("**What is different now:** the Vanquish sweep is re-run against the candidate "
                 "stream S actually sizes live (row L5: S sizes to a flat 1R / $1,000, A and C "
                 "size to $0 and never trade), not the old any-grade first-of-day arm -- so this "
                 "file answers whether a real S-only account clears a Vanquish eval, not a "
                 "hypothetical one that also traded B/C.\n")
    lines.append("Book: `%s` (RETEST_REQUIRED=1, shipped default), %s sessions, %s .. %s.\n"
                 % (BOOK_JSON.split(os.sep)[-1], out["meta"].get("sessions"),
                    out["meta"].get("first"), out["meta"].get("last")))
    lines.append("**O1: no winner (REFUTED).** %s\n" % out["o1_note"])

    for key in ("S_1R_classifier_off", "S_1R_classifier_on"):
        a = out["arms"][key]
        lines.append("## %s (n=%d candidates)\n" % (key, a["n_candidates"]))
        if a["n_candidates"] == 0:
            lines.append("No candidates -- empty arm.\n")
            continue
        lines.append("%s .. %s, %d in H1 (< %s), %d in H2 (>= %s).\n"
                     % (a["first_day"], a["last_day"], a["n_h1"], H_SPLIT, a["n_h2"], H_SPLIT))
        b = a["band_stock_r"]
        if b:
            lines.append("- **Passing band (stock-R, no options skin): $%.2f-$%.2f/trade** "
                         "(%d of %d tested levels). Best case: $%.0f/trade, PASS on %s "
                         "(%.1f months in), net after subscription %s."
                         % (b["low_dollars"], b["high_dollars"], b["n_passing"], b["n_tested"],
                            b["best"]["risk_dollars"], b["best"]["pass_day"],
                            b["best"]["months_to_event"], _fmt_money(b["best"]["net_dollars_after_cost"])))
        else:
            lines.append("- **No risk level tested passes (stock-R).**")
        hl = a["headline_stock_r"]
        if hl:
            lines.append("- Headline $1,000/trade (stock-R, == S's live 1R unit): %s"
                         % ("PASS on %s (%.1f mo), net %s" % (hl["pass_day"], hl["months_to_event"],
                            _fmt_money(hl["net_dollars_after_cost"]))
                            if hl["passed"] else "FAIL (%s)" % hl["fail_reason"]))
        bo = a.get("band_options_skin")
        if bo:
            lines.append("- **Options skin (delta 0.42 + $0.05 round-trip spread, LOW CONFIDENCE) "
                         "passing band: $%.2f-$%.2f/trade** (%d of %d tested levels)."
                         % (bo["low_dollars"], bo["high_dollars"], bo["n_passing"], bo["n_tested"]))
        elif a.get("headline_options_skin"):
            hlo = a["headline_options_skin"]
            lines.append("- Options skin (delta 0.42 + $0.05 spread, LOW CONFIDENCE), headline "
                         "$1,000/trade: %s" %
                         ("PASS on %s (%.1f mo), net %s" % (hlo["pass_day"], hlo["months_to_event"],
                          _fmt_money(hlo["net_dollars_after_cost"]))
                          if hlo["passed"] else "FAIL (%s)" % hlo["fail_reason"]))
        rs = a["rolling_start_at_best_or_headline"]
        if rs["starts"]:
            lines.append("- **Rolling-start pass rate** (252-session windows, at the best/"
                         "headline risk level found above): **%.1f%%** overall (%d starts) -- "
                         "H1 starts %.1f%% (%d), H2 starts %.1f%% (%d)."
                         % (rs["pass_pct"], rs["starts"], rs["h1_pass_pct"], rs["h1_starts"],
                            rs["h2_pass_pct"], rs["h2_starts"]))
        else:
            lines.append("- Rolling-start: too few S-only candidates for a 252-session window "
                         "(book not long enough to test yet).")
        lines.append("")

    lines.append("## SPX/XSP arm -- SPY-only S candidates (index-only insurance)\n")
    spx = out["spx_xsp_arm"]
    lines.append("Same S-only, classifier-off candidate rule, restricted to `sym == 'SPY'`. "
                 "\"SPY signals x10 as SPX\" names the mechanism (SPX prices ~10x SPY's "
                 "per-point value, so an equivalent single-leg long position needs ~10x the "
                 "dollar risk per contract) -- it is not a separate multiplier applied in this "
                 "file, since the sweep already spans that dollar range and this book has no "
                 "real SPX/XSP bid-ask, margin, or contract-size data to re-price against. This "
                 "arm answers a CANDIDATE-COUNT question: is there enough SPY-only S-tier signal "
                 "at all, in case Vanquish's Advanced Options universe turns out to be index-only "
                 "(AUGUR.md's open question, still unresolved).\n")
    lines.append("- n=%d SPY-only S candidates%s"
                 % (spx["n_candidates"],
                    (", %s .. %s" % (spx["first_day"], spx["last_day"])) if spx["n_candidates"] else " -- EMPTY"))
    if spx["n_candidates"] < VANQUISH_KW["min_trading_days"]:
        lines.append("- **Fewer candidates (%d) than Vanquish's own min_trading_days=%d -- "
                     "structurally cannot pass at any sizing.** The index-only insurance plan "
                     "does not have enough SPY-only S-tier signal in this book to attempt an "
                     "eval, regardless of risk level."
                     % (spx["n_candidates"], VANQUISH_KW["min_trading_days"]))
    else:
        b = spx.get("band_stock_r")
        if b:
            lines.append("- Passing band (stock-R): $%.2f-$%.2f/trade (%d of %d tested)."
                         % (b["low_dollars"], b["high_dollars"], b["n_passing"], b["n_tested"]))
        else:
            lines.append("- No risk level tested passes.")

    lines.append("\n## Modeling choices stated explicitly\n")
    lines.append("- S=1R candidate stream: `sgrade == 'S'`, first sizeable per day -- the exact "
                 "restriction row L5 landed for live sizing (A/C size to $0 and never trade).")
    lines.append("- S_CLASSIFIER v0 predicate: `level in ('OR high','OR low') and 'no_retest' in "
                 "downgrades`, identical to `research/g160_tweak_grid.py::_classifier_drop` -- "
                 "REFUTED (F7), reported for completeness only, per the row's own instruction.")
    lines.append("- O1: REFUTED, no winner -- no day/window/tier/veto lever is layered on top "
                 "of the S-only stream here.")
    lines.append("- Options skin: `spread_R = DEFAULT_SPREAD / (stock_risk * DEFAULT_DELTA)` "
                 "(options_sizer.py's own R7 round-trip formula), subtracted from every trade's "
                 "R once. `DEFAULT_DELTA=%.2f`, `DEFAULT_SPREAD=%.2f`, imported not restated. "
                 "LOW CONFIDENCE: this repo has no real options bid/ask tape to check the flat "
                 "$0.05 estimate against."
                 % (DEFAULT_DELTA, DEFAULT_SPREAD))
    lines.append("- Vanquish rules unchanged from g120: 10%% profit target / 5%% EOD-anchored "
                 "trailing drawdown / no daily loss limit / min 4 trading days / no single day "
                 "over 30%% of accumulated profit. $499/mo while in eval, $249 reset once if the "
                 "eval never passes over the whole book." % ())
    lines.append("- SPX/XSP: CONDITIONAL and CANDIDATE-COUNT ONLY -- see the arm's own section "
                 "above. Not re-priced for SPX/XSP contract size, margin, or spread.")

    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
