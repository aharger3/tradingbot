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

# omen-4.0 T6 shipped NO_REPEAT_ENTRIES=True, which SUPPRESSES the second entry
# on the same symbol+direction+level outright — so the omen-3.9 expectation of a
# second additive row has been wrong (and this file unrunnable) since that row
# landed. Settled behaviour: no second row; the 84% re-entry is the one exemption.
again = []
second = dict(keep_sig)
runner._route(again, second)
check(sr.NO_REPEAT_ENTRIES is True, "NO_REPEAT_ENTRIES ships ON (omen-4.0 T6)")
check(again == [], "the same idea does NOT route a second time — first available entry wins")
check("repeat entry" in second["reason"], "...and the suppressed row says why")
check(second["austin_tier"] == "A",
      "...it is still tiered A, not S — clause 3 saw the first")

reentry = []
re_sig = dict(keep_sig, signal_type=SignalType.REENTRY_84_RULE,
              stop_level_name="Original stop")
runner._route(reentry, re_sig)
check(len(reentry) == 1,
      "the armed 84% re-entry is the ONE exemption — it still routes on a taken level")

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


print("5. omen-5.0 T3 — session window, intrabar fill, session-extreme veto, 84% caps")

# (a) the window lives in the detector
check(sr.SESSION_START == "09:30:00" and sr.SESSION_END == "11:00:00",
      "(a) the session window is 09:30-11:00 — Austin: 'I dont trade past 11 am'")
check(sr.bar_time("09:31:00") == "09:31:00" and sr.bar_time("09:31") == "09:31:00"
      and sr.bar_time("2026-08-11T09:31:00-04:00") == "09:31:00",
      "(a) bar_time normalises bare, short and ISO stamps alike")
check(sr.in_session("09:30:00") and sr.in_session("10:59:00"),
      "(a) bars inside the window are in session")
check(not sr.in_session("09:29:00") and not sr.in_session("11:00:00")
      and not sr.in_session("11:30:00"),
      "(a) 09:29, 11:00 and 11:30 are all OUT — the end is exclusive")


def _br_day(start_hh_mm=(9, 30)):
    """The --dry-run synthetic clean B&R day, anchored at an arbitrary time."""
    h, m = start_hh_mm
    def ts(k):
        tot = h * 60 + m + k
        return f"{tot // 60:02d}:{tot % 60:02d}:00"
    bars = [Candle(ts(i), 100.0, 100.5, 99.9, 100.2, 1000) for i in range(5)]
    bars += [Candle(ts(5 + i), 100.1, 100.4, 100.0, 100.2, 1000) for i in range(15)]
    bars += [Candle(ts(20), 100.3, 102.0, 100.2, 101.9, 5000),
             Candle(ts(21), 101.9, 102.3, 101.7, 102.1, 2000),
             Candle(ts(22), 102.1, 102.2, 101.3, 101.6, 1500),
             Candle(ts(23), 101.6, 101.7, 100.4, 100.9, 1800),
             Candle(ts(24), 101.0, 101.6, 100.8, 101.5, 1600)]
    return bars


def _fresh(symbol="TSLA"):
    return sr.SignalRunner(post_to_discord=False, symbol=symbol, log_signals=False)


in_win = _fresh()
in_win.candles = _br_day((9, 30))          # last bar 09:54
fired_in = in_win.detect_signals()
check(len(fired_in) >= 1, "(a) the clean B&R day still fires inside the window")

late = _fresh()
late.candles = _br_day((11, 6))            # last bar 11:30
check(late.detect_signals() == [],
      "(a) the SAME setup on a bar timestamped 11:30 is not emitted at all")

# (b) intrabar fill on an extreme close
check(sr.fill_price(100.00, MID, is_long=True) == MID.close,
      "(b) a mid-bar close fills at the close")
check(sr.fill_price(100.00, TOP, is_long=True) == 100.00,
      "(b) a long closing in the top 25% fills INTRABAR at the level instead")
check(sr.fill_price(99.00, TOP, is_long=True) == TOP.low,
      "(b) a level below the bar is clamped into the bar's own range")
check(sr.fill_price(100.90, BOT, is_long=False) == 100.90,
      "(b) a short closing in the bottom 25% fills at the level")
check(sr.fill_price(102.00, BOT, is_long=False) == BOT.high,
      "(b) a level above the bar is clamped to its high")
check(callable(sr.fill_price) and '"entry": current.close' not in src,
      "(b) no detection site fills at the close unconditionally any more")

# (c) session HOD/LOD proximity is a VETO, not a demotion. It ships DISABLED
# (SESSION_EXTREME_FRAC = 0.0) because the A/B in research/t3_session_extreme.md
# came back negative — the mechanic is what this checks, armed explicitly.
vr = _fresh()
vr.candles = [c(100.0, 105.0, 100.0, 101.0, ts="09:30:00")] + \
             [c(101.0, 101.5, 100.5, 101.0, ts="09:%02d:00" % (31 + i)) for i in range(10)]
check(sr.SESSION_EXTREME_FRAC == 0.0,
      "(c) ships at the fitted chosen_frac 0.0 — the A/B picked the control arm")
check(not vr.session_extreme_veto({"entry": 104.9, "direction": "call"}),
      "(c) at the shipped 0.0 the veto is a no-op")
_frac = sr.SESSION_EXTREME_FRAC
try:
    sr.SESSION_EXTREME_FRAC = 0.10
    check(vr.session_extreme_veto({"entry": 104.9, "direction": "call"}),
          "(c) armed: a long filled at the session high is vetoed")
    check(not vr.session_extreme_veto({"entry": 101.0, "direction": "call"}),
          "(c) armed: a long filled mid-session-range is not")
    check(vr.session_extreme_veto({"entry": 100.1, "direction": "put"}),
          "(c) armed: a short filled at the session low is vetoed")
    held = []
    vr._emit(held, {"signal_type": SignalType.BREAK_AND_RETEST, "reason": "t",
                    "entry": 104.9, "stop": 100.0, "direction": "call",
                    "grade": TradeGrade.B.value, "stop_level_name": "OR high",
                    "stop_width_pct": 4.9})
    check(held == [], "(c) a vetoed signal never reaches _route — it is not emitted")
finally:
    sr.SESSION_EXTREME_FRAC = _frac

# (d) 84% rule: two attempts on one idea, reclaim before 11:00
check(sr.RULE84_MAX_ATTEMPTS == 2,
      "(d) 2 attempts total on one idea — the original plus a single re-entry")

def _reclaim_runner():
    r = _fresh()
    bars = [c(100.0, 105.0, 100.0, 104.0, ts="09:30:00")]
    bars += [c(103.0, 103.2, 100.5, 101.0, ts="09:%02d:00" % (31 + i)) for i in range(12)]
    bars.append(c(101.0, 101.6, 100.9, 101.5, ts="09:45:00"))   # bullish reclaim
    r.candles = bars
    r.session.entry_price, r.session.entry_direction = 101.0, "call"
    r.session.entry_stop, r.session.entry_target = 100.0, 104.0
    return r

r84 = _reclaim_runner()
first = [s for s in r84.detect_signals()
         if s["signal_type"] is SignalType.REENTRY_84_RULE]
check(len(first) == 1, "(d) attempt 2 of the idea — the armed re-entry — fires")
r84.session.entry_price, r84.session.entry_direction = 101.0, "call"   # re-arm same idea
r84.session.entry_stop, r84.session.entry_target = 100.0, 104.0
third = [s for s in r84.detect_signals()
         if s["signal_type"] is SignalType.REENTRY_84_RULE]
check(third == [], "(d) attempt 3 on the same idea is refused — the cap is 2")

sr84 = _reclaim_runner()
sr84.candles = sr84.candles[:-1] + [c(101.0, 101.6, 100.9, 101.5, ts="11:30:00")]
check(sr84.detect_signals() == [],
      "(d) a reclaim landing at 11:30 arms nothing — it is past the window")
det_src = __import__("inspect").getsource(sr.SignalRunner.detect_signals)
check(det_src.count("RULE84_MAX_ATTEMPTS") == 4 and det_src.count("caps_ok") == 4
      and det_src.count("bar_time(current.timestamp) < SESSION_END") == 2,
      "(d) both 84% sites carry the attempt cap and the reclaim-time clause")


print("6. omen-5.0 T10 — pivot structure as a first-class level")

# A series with an obvious swing high at index 2 and index 9, swing low at 6.
PIV = [c(h, h, h - 1.0, h, ts="09:%02d:00" % (30 + i))
       for i, h in enumerate([5, 6, 9, 6, 5, 4, 3, 4, 5, 8, 5, 4, 3])]

lv = sr.pivot_levels(PIV)
check(bool(lv), "pivot_levels finds the swings in a series with an obvious one")
check(all(l.get("index") is not None for l in lv),
      "every pivot carries the bar index it formed on")
check({l["kind"] for l in lv} == {"high", "low"},
      "both a pivot high and a pivot low are found")
check(any(l["name"].startswith("pivot high @") for l in lv)
      and any(l["name"].startswith("pivot low @") for l in lv),
      "levels are named 'pivot high @HH:MM' / 'pivot low @HH:MM' so idea_key still works")

first = min(lv, key=lambda l: l["index"])
check(first["usable_from"] == first["index"] + sr.PIVOT_STRENGTH + 1,
      "a pivot is usable only from index + PIVOT_STRENGTH + 1")
check(sr.pivot_levels(PIV, as_of=first["usable_from"] - 1) == [],
      "NO LOOKAHEAD: the pivot is invisible on the bar before it completes")
check([l["index"] for l in sr.pivot_levels(PIV, as_of=first["usable_from"])] == [first["index"]],
      "...and visible on the bar it completes, not before")
check(sr.pivot_levels(PIV, as_of=12, lookback=2) == [],
      "the lookback horizon drops pivots that are no longer live structure")
check(len(sr.pivot_levels(PIV, strength=4)) < len(lv),
      "PIVOT_STRENGTH is tunable — a wider swing requirement finds fewer pivots")
check(sr.PIVOT_STRENGTH == 2 and isinstance(sr.PIVOT_LOOKBACK, int),
      "PIVOT_STRENGTH ships at 2 — Austin's '2-candle structure' read literally")


def _pivot_br_day():
    """A pivot high at 09:38 that is broken, left, retested and confirmed."""
    def b(i, o, h, l, cl, v=1500):
        tot = 9 * 60 + 30 + i
        return Candle(f"{tot // 60:02d}:{tot % 60:02d}:00", o, h, l, cl, v)
    bars = [b(i, 100.0, 100.2, 99.9, 100.1) for i in range(5)]
    bars += [b(5, 100.1, 100.4, 100.0, 100.3), b(6, 100.3, 100.7, 100.2, 100.6),
             b(7, 100.6, 101.0, 100.5, 100.9), b(8, 100.9, 101.4, 100.8, 101.3, 4000),
             b(9, 101.3, 101.35, 100.9, 101.0), b(10, 101.0, 101.1, 100.6, 100.7),
             b(11, 100.7, 100.9, 100.5, 100.8), b(12, 100.8, 101.0, 100.7, 100.9),
             b(13, 100.9, 101.1, 100.8, 101.0),
             b(14, 101.0, 102.0, 100.95, 101.9, 6000),   # displaced break of 101.40
             b(15, 101.9, 102.2, 101.7, 102.0),          # leave
             b(16, 102.0, 102.1, 101.3, 101.5),          # retest
             b(17, 101.5, 102.0, 101.38, 101.95)]        # confirm close above
    return bars


class _Capture(sr.SignalRunner):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.seen = []

    def _route(self, signals, sig):
        self.seen.append(sig)
        super()._route(signals, sig)


cap = _Capture(post_to_discord=False, symbol="TSLA", log_signals=False)
cap.candles = _pivot_br_day()
cap.detect_signals()
piv_sigs = [s for s in cap.seen if s.get("level_kind") == "pivot"]
check(len(piv_sigs) == 1,
      "break-and-retest consumes pivot levels exactly as it consumes named ones")
check(piv_sigs[0]["stop_level_name"].startswith("pivot high @"),
      "...and the signal is keyed to the pivot by name")
check(piv_sigs[0]["level_rank"] == 0,
      "a pivot-keyed B&R ranks ABOVE a named-level one — 'pivot structure break > level break'")
check("ranked_below_pivot" in src and "level_rank" in src,
      "the pivot-over-named ordering is RECORDED on the signal, not silently applied")

# T3(b)/T10 interaction: an intrabar fill landing on a level-stop
ENTRY_BAR = c(101.50, 102.00, 101.38, 101.95)
check(sr.intrabar_stop(101.40, 101.40, ENTRY_BAR, is_long=True) == 101.38,
      "an intrabar fill sitting ON the level-stop moves the stop to the bar he entered on")
check(sr.intrabar_stop(101.95, 101.40, ENTRY_BAR, is_long=True) == 101.40,
      "a normal close fill keeps its structural stop untouched")
check(sr.intrabar_stop(101.38, 101.38, c(101.50, 102.00, 101.38, 101.95),
                       is_long=True) == 101.38,
      "a fill already at the bar's own low has nothing left to give — stop unchanged")
check(piv_sigs[0]["entry"] > piv_sigs[0]["stop"],
      "so the pivot B&R has real risk to size instead of dying at zero")


print("7. omen-5.0 T11 — S has a quality bar it has to earn")

check(sr.BNR_DISPLACEMENT_GATE is True,
      "(a) the displacement gate is ARMED — rulebook clause 5")
check(sr.RULE7_MAX_BARS == 8 and sr.RULE_710_ENABLED is False,
      "(a) Rule 7's window is fitted to his S marks (8 bars) and left disarmed — it "
      "separates nothing at that value")
check(sr.LEVEL_RETIRE_TOUCHES == 2, "(a2) the third break-and-retest retires the level")
check(sr.S_PLUS_PER_DAY <= 3, "(e) S+ is capped at 3 a day")

# (a) a B&R with no displacement can never be S, whatever the other clauses say
no_disp = dict(sig(entry=100.40), displacement=False, stop=99.0)
yes_disp = dict(sig(entry=100.40), displacement=True, stop=99.0)
check(tier(yes_disp, [MID], set(), None) == "S",
      "(a) a displaced break-and-retest with a clean fill is S")
check(tier(no_disp, [MID], set(), None) == "C",
      "(a) the SAME setup without break-leg displacement is not S")
check(tier(dict(sig(SignalType.ONE_CANDLE_RULE, entry=100.40), displacement=False),
           [MID], set(), None) == "S",
      "(a) the displacement clause is a B&R clause — it does not touch the one candle rule")

# (c) in-between mesh is a hard S-veto, reusing the LEVEL_BLOCK_CAP computation
mesh_sig = {"entry": 100.0, "stop": 99.0, "direction": "call"}
check(sr.blocking_levels(mesh_sig, [101.5]) == [101.5],
      "(c) a level inside the entry-to-2R path is a blocking level")
check(sr.blocking_levels(mesh_sig, [103.0, 98.0]) == [],
      "(c) levels outside the path, and the traded level itself, are not")
check(tier(dict(sig(entry=100.40), mesh_blocked=True), [MID], set(), None) == "C",
      "(c) an entry meshed between levels cannot be S — a veto, not a demotion")
check(tier(dict(sig(entry=100.40), mesh_blocked=False), [MID], set(), None) == "S",
      "(c) ...and clear road stays S")

# (e) S+ ranking: a rank inside S, nothing discarded
day_sigs = [{"day": "2026-08-11", "timestamp": "09:%02d:00" % (35 + i),
             "austin_tier": "S", "grade": "B", "confluence": False}
            for i in range(5)]
sr.rank_s_plus(day_sigs)
check([s["s_rank"] for s in day_sigs] == ["S+", "S+", "S+", "S", "S"],
      "(e) the earliest 3 S of the day are S+, the rest stay S")
check(all(s["austin_tier"] == "S" for s in day_sigs),
      "(e) nothing is discarded and nothing changes tier — S+ is a rank, not a letter")
two_days = [{"day": "2026-08-10", "timestamp": "10:00:00", "austin_tier": "S", "grade": "B"},
            {"day": "2026-08-11", "timestamp": "10:00:00", "austin_tier": "S", "grade": "B"}]
sr.rank_s_plus(two_days)
check(all(s["s_rank"] == "S+" for s in two_days),
      "(e) the cap is per DAY, not per set")
tie = [{"day": "d", "timestamp": "09:40:00", "austin_tier": "S", "grade": "B"},
       {"day": "d", "timestamp": "09:40:00", "austin_tier": "S", "grade": "A+"}]
sr.rank_s_plus(tie, per_day=1)
check(tie[1]["s_rank"] == "S+" and tie[0]["s_rank"] == "S",
      "(e) same-bar ties break by engine grade")

# (d) confluence + (a2) retirement, through the runner
conf = _fresh()
conf.candles = [MID] * 12
kept2 = []
for st, lvl in ((SignalType.BREAK_AND_RETEST, "OR high"),
                (SignalType.ONE_CANDLE_RULE, "Order block low")):
    conf._bar_setups = getattr(conf, "_bar_setups", {})
    conf._emit(kept2, {"signal_type": st, "reason": "t", "entry": 100.40,
                       "stop": 99.00 if st is SignalType.BREAK_AND_RETEST else 98.90,
                       "direction": "call", "grade": TradeGrade.B.value,
                       "stop_level_name": lvl, "stop_width_pct": 1.4})
check(len(kept2) == 2, "(d) two different setups on the same bar both route")
check(conf._bar_setups.get("call") ==
      {"break_and_retest", "one_candle_rule"},
      "(d) both S-eligible setups are recorded on the bar for the confluence flag")

ret = _fresh()
rounds = []
for k in range(3):
    ret.candles = [MID] * (12 + k * 40)      # 40 bars apart = separate events
    got = []
    ret._route(got, {"signal_type": SignalType.BREAK_AND_RETEST, "reason": "t",
                     "entry": 100.40, "stop": 99.00 - k, "direction": "call",
                     "grade": TradeGrade.B.value, "stop_level_name": "OR high",
                     "stop_width_pct": 1.4})
    rounds.append(bool(got))
check(rounds == [True, True, False],
      "(a2) the third break-and-retest of the same level is not taken — the level is done")


print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")
