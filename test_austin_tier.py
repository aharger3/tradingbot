"""omen-3.9 T4 checks. Plain asserts, no pytest:  python test_austin_tier.py

Covers austin_tier becoming a COMPUTED value (Trading-Bot-Rulesets.md,
"Austin's Tiers (S / A / C / X)"):
  1. Each clause helper, on its own — setup_is_s_eligible, bar_extreme_veto,
     idea_key.
  2. The tiering arithmetic — four clauses = S, one or two missing = A, three
     or HOD/LOD or a non-setup = C, and never X.
  3. Clause 4 is a SWITCH: both arms of HTF_OPPOSITION_VETO behave as written.
  4. The row is ADDITIVE — _route stamps the tier on fired AND skipped signals
     and changes neither, and TRADE_S_ONLY is read nowhere.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import signal_runner as sr
from omen_bot import Candle, SignalType, TradeGrade

FAILS = []


def check(cond, label):
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILS.append(label)


def c(o, h, l, cl, ts="09:45:00", v=100000):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=cl, volume=v)


def sig(signal_type=SignalType.BREAK_AND_RETEST, direction="call",
        level="OR high", entry=100.40, symbol="TSLA"):
    return {"signal_type": signal_type, "direction": direction,
            "stop_level_name": level, "entry": entry, "symbol": symbol}


# Same bar (range 100.00-101.00) entered mid-range vs at the top: the whole of
# clause 2 is where the close sits inside THIS bar, nothing about a later one.
MID = c(100.00, 101.00, 100.00, 100.40)   # top of the band starts at 100.75
TOP = c(100.00, 101.00, 100.00, 100.90)
BOT = c(101.00, 101.00, 100.00, 100.10)   # bottom band ends at 100.25


print("1. the clause helpers")

check(sr.setup_is_s_eligible(sig(SignalType.BREAK_AND_RETEST)),
      "clause 1: break-and-retest is S-eligible")
check(sr.setup_is_s_eligible(sig(SignalType.ONE_CANDLE_RULE)),
      "clause 1: the one candle rule (order block) is S-eligible")
check(sr.setup_is_s_eligible(sig(SignalType.REENTRY_84_RULE)),
      "clause 1: the armed 84% re-entry is S-eligible")
check(not sr.setup_is_s_eligible(sig(SignalType.FAIR_VALUE_GAP)),
      "clause 1: a fair-value-gap entry is NEVER S")
check(not sr.setup_is_s_eligible(sig(SignalType.FLAG)),
      "clause 1: a flag breakout is NEVER S")

check(not sr.bar_extreme_veto(sig(entry=100.40), MID),
      "clause 2: a long filled mid-bar is not vetoed")
check(sr.bar_extreme_veto(sig(entry=100.90), TOP),
      "clause 2: a long filled in the top 25% of its own bar IS vetoed")
check(sr.bar_extreme_veto(sig(direction="put", level="OR low", entry=100.10), BOT),
      "clause 2: a short filled in the bottom 25% IS vetoed")
check(not sr.bar_extreme_veto(sig(direction="put", level="OR low", entry=100.60),
                              c(101.00, 101.00, 100.00, 100.60)),
      "clause 2: a short filled mid-bar is not vetoed")
check(not sr.bar_extreme_veto(sig(SignalType.REENTRY_84_RULE, entry=100.90), TOP),
      "clause 2: the 84% re-entry is exempt — its close-through IS the signal")
check(not sr.bar_extreme_veto(sig(entry=100.00), c(100.0, 100.0, 100.0, 100.0)),
      "clause 2: a zero-range bar cannot place the close, so it does not veto")

check(sr.idea_key(sig()) == ("TSLA", "call", "OR high"),
      "clause 3: idea_key is (symbol, direction, level NAME)")
check(sr.idea_key(sig(entry=100.40)) == sr.idea_key(sig(entry=100.90)),
      "clause 3: the same level at a different price is the SAME idea")
check(sr.idea_key(sig(level="PDH")) != sr.idea_key(sig(level="OR high")),
      "clause 3: a different reference level is a different idea")
check(sr.idea_key(sig(direction="put")) != sr.idea_key(sig(direction="call")),
      "clause 3: the other direction on the same level is a different idea")


print("2. tiering")

tier = sr.compute_austin_tier
check(tier(sig(entry=100.40), [MID], set(), None) == "S",
      "all four clauses -> S")
check(tier(sig(entry=100.90), [TOP], set(), None) == "A",
      "clause 2 alone missing -> A")
check(tier(sig(entry=100.40), [MID], {("TSLA", "call", "OR high")}, None) == "A",
      "clause 3 alone missing (idea already had its S today) -> A")
check(tier(sig(entry=100.40), [MID], set(), "bearish") == "A",
      "clause 4 alone missing (HTF opposes a long) -> A")
check(tier(sig(entry=100.90), [TOP], {("TSLA", "call", "OR high")}, None) == "A",
      "two of 2/3/4 missing -> still A")
check(tier(sig(entry=100.90), [TOP], {("TSLA", "call", "OR high")}, "bearish") == "C",
      "three of 2/3/4 missing -> C")
check(tier(sig(SignalType.FAIR_VALUE_GAP, entry=100.40), [MID], set(), None) == "C",
      "clause 1 failing -> C, however good the fill")
check(tier(sig(level="HOD", entry=100.40), [MID], set(), None) == "C",
      "targeting the session HOD -> C")
check(tier(sig(level="LOD", direction="put", entry=100.60),
           [c(101.0, 101.0, 100.0, 100.60)], set(), None) == "C",
      "targeting the session LOD -> C")
check(tier(sig(SignalType.REENTRY_84_RULE, entry=100.90), [TOP],
           {("TSLA", "call", "Original stop")}, None) == "S",
      "the armed 84% re-entry is exempt from clauses 2 AND 3 — allowed to be second")
check(tier(sig(entry=100.40), [MID], set(), "bullish") == "S",
      "an ALIGNED higher timeframe does not fail clause 4")
check(tier(sig(entry=100.40), [MID], set(), "neutral") == "S",
      "a neutral higher timeframe opposes nothing")
check(all(tier(s, [MID], set(), b) != "X"
          for s in (sig(), sig(SignalType.FLAG), sig(level="HOD"))
          for b in (None, "bullish", "bearish")),
      "compute_austin_tier NEVER returns X — that is Austin's own marker")


print("3. clause 4 is a switch, not a constant")

check(sr.HTF_OPPOSITION_VETO == "hard",
      "HTF_OPPOSITION_VETO defaults to 'hard' — today's behaviour")
try:
    sr.HTF_OPPOSITION_VETO = "fill_override"
    check(tier(sig(entry=100.40), [MID], set(), "bearish") == "S",
          "fill_override: a good fill carries an opposing higher timeframe to S")
    check(tier(sig(entry=100.90), [TOP], set(), "bearish") == "A",
          "fill_override: a BAD fill does not — clause 2 is what earns the override")
finally:
    sr.HTF_OPPOSITION_VETO = "hard"
check(sr.HTF_OPPOSITION_VETO == "hard", "the switch is restored to hard")


print("4. additive — the tier reports, it does not route")

check(sr.AUSTIN_TIER_ENABLED is True, "AUSTIN_TIER_ENABLED ships ON (nothing branches on it)")
check(sr.TRADE_S_ONLY is False, "TRADE_S_ONLY ships OFF")
src = (pathlib.Path(__file__).resolve().parent / "signal_runner.py").read_text()
code = [l.split("#", 1)[0] for l in src.splitlines()]   # comments may name it
check(sum("TRADE_S_ONLY" in l for l in code) == 1,
      "TRADE_S_ONLY is DEFINED and read nowhere — T8 A/Bs it, Austin arms it")

runner = sr.SignalRunner(post_to_discord=False, symbol="TSLA", log_signals=False)
runner.candles = [MID] * 12

kept = []
keep_sig = {"signal_type": SignalType.BREAK_AND_RETEST, "reason": "t",
            "entry": 100.40, "stop": 99.00, "direction": "call",
            "grade": TradeGrade.B.value, "stop_level_name": "OR high",
            "stop_width_pct": 1.4}
runner._route(kept, keep_sig)
check(len(kept) == 1, "_route still accepts a B-grade signal")
check(kept[0]["grade"] == "B", "_route did not touch the engine grade")
check(kept[0]["austin_tier"] == "S", "a fired signal carries its computed tier")
check(sr.idea_key(keep_sig) in runner._fired_ideas,
      "the fired S is recorded, so clause 3 can see it next time")

again = []
runner._route(again, dict(keep_sig))
check(len(again) == 1, "the same idea still ROUTES the second time (additive row)")
check(again[0]["austin_tier"] == "A",
      "...but the second one is A, not S — clause 3 saw the first")

skipped = []
skip_sig = {"signal_type": SignalType.BREAK_AND_RETEST, "reason": "t",
            "entry": 100.40, "stop": 99.00, "direction": "put",
            "grade": TradeGrade.X.value, "stop_level_name": "OR low",
            "stop_width_pct": 1.4}
runner._route(skipped, skip_sig)
check(skipped == [], "_route still drops an X-grade (skip) signal")
check(skip_sig["austin_tier"] in ("S", "A", "C"),
      "a SKIPPED signal carries a tier too — every signal is tiered")
check(sr.idea_key(skip_sig) not in runner._fired_ideas,
      "a skipped signal never 'fired', so it does not consume its idea")


print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")
