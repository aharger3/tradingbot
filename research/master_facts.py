"""master_facts.py -- every fact the engine actually runs on, in plain English.

Austin, 2026-08-28: "I want to go though each codebases and approve or deny and
add or subtract facts, have this in the artifact."

So this is the codebase's own belief system, one line at a time. Each entry is a
constant, gate or convention that is LIVE right now -- not a proposal, not
history. `where` is the file and symbol so any answer can be acted on without
another archaeology pass. `costs` is what it does to the two-year book, measured,
or the honest word "unmeasured".

Rules for adding to this list:

* It must be reachable. Four rules in this project turned out to be branches that
  could never be true (`research/p15_level_respect.md` is the fourth). If a gate
  trips 10 times in 45,193 signals, that fact is "this gate is dead", not "this
  gate does X".
* `costs` never invents a number. Either a measurement exists and is cited, or
  the field says unmeasured and the card says so to his face.
* No fact he has already ratified appears here. Re-asking is the failure his
  no-repeat rule exists to stop.
"""
from __future__ import annotations

# key, question, plain-English body, where it lives, what it costs
FACTS: list[dict] = [
    # ---- the stop, which he raised first and loudest -----------------------
    dict(k="stop_floor_is_fiction",
         q="The -1.25R floor is bookkeeping, not an order",
         b="Right now the model triggers the stop on the candle close and then "
           "writes down -1.25R if the close was worse. Nothing actually gets you "
           "out at -1.25R. On the real tape 458 of 474 stop-outs closed past 1R, "
           "median -1.35R, worst -4.36R. To make the floor REAL the engine has to "
           "rest a hard stop order at the -1.25R premium that fires intrabar on "
           "touch -- a disaster stop sitting underneath your level stop.",
         w="stop_rule.stop_fill_price / MAX_LOSS_R = 1.25",
         c="the clamp is worth +0.138R of the book's +0.834R; without it the book "
           "is +0.726R and max drawdown goes 14.5R -> 19.3R",
         opts=[("hard", "Rest a real -1.25R stop order"),
               ("clamp", "Keep it as a clamp"),
               ("wider", "-1.25R is too tight, widen it")]),

    dict(k="two_stops",
         q="Does a wick ever take you out?",
         b="Your rule is closes, not wicks -- settled five times. But that rule is "
           "about the LEVEL stop. A disaster stop at -1.25R is a different animal: "
           "it is a risk cap, not a signal, and a cap that only checks closes is "
           "not a cap. These can coexist: level stop on the close, disaster stop "
           "on touch.",
         w="stop_rule.stop_hit_on_close / INTRABAR_STOP_AT_BAR",
         c="unmeasured -- nobody has run an intrabar disaster stop arm",
         opts=[("both", "Level stop on close, disaster stop on touch"),
               ("close", "Closes only, everywhere, no exceptions"),
               ("touch", "Both stops fire on touch")]),

    # ---- the setup imbalance he raised second ------------------------------
    dict(k="ocr_demote",
         q="One-candle-rule trades are demoted at the detection site",
         b="Every order-block / OCR signal is knocked from B to C the moment it is "
           "detected, and C does not trade. So the one-candle rule can never ship a "
           "tradeable grade on its own no matter how good the setup is. That is why "
           "you see 67 OCR trades against 947 break-and-retests.",
         w="signal_runner.py -- OCR B->C demote + 0.4% wide-stop gate",
         c="OCR: 4,390 detections -> 67 traded (1.5%) at +0.334R. B&R: 40,800 -> "
           "947 (2.3%) at +0.866R",
         opts=[("lift", "Lift the demote, let OCR trade on its own"),
               ("keep", "Keep it, OCR really is worse"),
               ("gate", "Lift it but only for tight stops")]),

    dict(k="ocr_min_risk",
         q="A flat $0.50 minimum stop kills OCR setups on cheap stocks",
         b="Break-and-retest had its flat $0.50 minimum replaced with a relative "
           "one (0.15% of price) because the flat number was benching every stock "
           "under $50. The one-candle rule never got that fix -- it still uses the "
           "flat $0.50. There is no A/B behind it; it is legacy.",
         w="signal_runner.py -- OCR/FVG/Flag min risk $0.50",
         c="unmeasured for OCR specifically; the same flat rule was measured as "
           "over-aggressive for B&R",
         opts=[("relative", "Give OCR the relative minimum too"),
               ("keep", "Keep the flat $0.50"),
               ("none", "No minimum at all, size to the stop")]),

    dict(k="rule84_arming",
         q="The 84% rule fires 3 times in two years, and it is the arming gate",
         b="The detector is not the problem. Of 472 chances to arm a re-entry, 7 "
           "survive the gate. Opening the gate produces 116 re-entries worth "
           "+0.792R -- positive, but under the book's own mean, so it was left "
           "shut. You have said the rule is rare in real life too.",
         w="signal_runner.RULE84_STRICT = 1",
         c="strict: 3 signals in 500 sessions at +1.986R. Open: 116 signals at "
           "+0.792R",
         opts=[("open", "Open it -- 3 in two years is not a rule"),
               ("keep", "Keep it strict, rare is correct"),
               ("mid", "Open it only off S-grade stop-outs")]),

    dict(k="rule84_arm_setups",
         q="The 84% rule can only arm off a break-and-retest",
         b="If a one-candle-rule trade stops you out and then reclaims your exact "
           "entry, the engine will not re-enter -- the re-entry is only armed by "
           "break-and-retest stop-outs. Your own statement of the rule does not "
           "mention the setup that failed.",
         w="signal_runner.RULE84_ARM_ON",
         c="unmeasured -- the arming gate above shuts the door before this matters",
         opts=[("any", "Arm off any setup that stops out"),
               ("bnr", "Break-and-retest only"),
               ("brocr", "Break-and-retest and one-candle-rule")]),

    # ---- the indices he raised third ---------------------------------------
    dict(k="index_share",
         q="Indices are 18 trades out of 1,017",
         b="QQQ 9, IWM 5, SPY 4 across two years, against COIN's 104 on its own. "
           "You said indices are the first thing you will trade with real money. "
           "Nothing in the engine deliberately suppresses them -- they just have "
           "smaller percentage moves, so the minimum-stop gates bite harder.",
         w="universe.INDEX_POOL / the min-risk gates",
         c="index rows: 18 trades. Equity rows: 999",
         opts=[("relative", "Scale every stop gate to the symbol's own range"),
               ("quota", "Give indices a guaranteed share of the book"),
               ("keep", "Leave it -- indices really do set up less often")]),

    dict(k="per_symbol_cap",
         q="COIN is 10% of the whole book",
         b="COIN 104, MU 82, PLTR 77, TSLA 75 -- while ACHR and SOFI have 2 each. "
           "There is no cap, so one symbol's regime can carry or sink a year of "
           "results, and per-symbol numbers under about 20 trades are noise being "
           "printed next to signal.",
         w="no cap exists",
         c="unmeasured -- no per-symbol cap arm has been run",
         opts=[("cap", "Cap any one symbol's share of the book"),
               ("keep", "No cap, take what sets up"),
               ("hide", "No cap, but grey out sub-20-trade rows in reports")]),

    # ---- the target, which is the money gate --------------------------------
    dict(k="blind_2r",
         q="Every single trade targets exactly 2x risk",
         b="Not the next level -- twice the risk, wherever that lands. You already "
           "chose to change this. What is not settled is what replaces it when "
           "there is NO level within reach: skip the trade, or take it with a "
           "smaller target.",
         w="signal_runner.py -- blind 2R target",
         c="296 of 1,017 rows run past +2R, max +14.264R, mean MFE +4.099R",
         opts=[("skip", "No level in reach = no trade"),
               ("take", "Take it anyway with whatever target exists"),
               ("size", "Take it smaller")]),

    dict(k="runner_size",
         q="The runner is half your position, you say you run 10%",
         b="The shipped plan takes 50% off at the first HOD/LOD and runs the other "
           "50%. You have said you manage 'a 10 percent position most of the "
           "time'. The 30/30/30/10 plan that leaves exactly a 10% runner was "
           "measured at a rounding error from the incumbent overall -- but better "
           "on the S subset.",
         w="backtest_week.SCALE_PLAN = hod_then_runner_be",
         c="+0.955R vs +0.957R overall; on S only, 30/30/30/10 is +1.357R vs "
           "+1.283R",
         opts=[("match", "Match what you actually do -- 30/30/30/10"),
               ("keep", "Keep 50/50"),
               ("full", "No scaling, one exit")]),

    dict(k="be_stop",
         q="The stop moves to break-even only when the first target is hit",
         b="Your own words: 'if we dont hit price target 1, we dont raise the stop "
           "to BE, but we need to run stats on with enough movement raising to "
           "BE.' You asked for that measurement and it has never been run.",
         w="backtest_week.py -- runner break-even move",
         c="break-even ends only 20 of 1,017 trades (2.0%)",
         opts=[("pt1", "Keep it -- PT1 or nothing"),
               ("move", "Raise to BE on enough movement, measure it"),
               ("never", "Never move the stop")]),

    # ---- the entry ---------------------------------------------------------
    dict(k="trade_floor",
         q="Nothing may be entered before 09:40 in the backtest",
         b="Your 34 S entries run from 09:34, median 09:42, and 65% land before "
           "09:45. The floor deletes ten of them outright. It was put in to avoid "
           "opening noise and it has never been ratified.",
         w="backtest_week.TRADE_FLOOR",
         c="cuts 10 of your 34 S days (29%); 09:30-09:45 is the best 15-min block "
           "measured",
         opts=[("drop", "Drop it -- take 09:30 onward"),
               ("keep", "Keep 09:40"),
               ("935", "Compromise at 09:35")]),

    dict(k="session_end",
         q="No new entries after 11:00, and the runner is also cut there",
         b="The entry half is clean -- the last entry in two years is 10:59. But "
           "the runner is also closed at 11:00 by the same clock, so a trade still "
           "working gets flattened because of the time, not because of the chart.",
         w="signal_runner.SESSION_END = 11:00:00",
         c="unmeasured for the runner half specifically",
         opts=[("manage", "11:00 stops new entries, runners keep running"),
               ("flat", "Flat at 11:00, no exceptions"),
               ("later", "Let runners go to a later clock")]),

    dict(k="on_watch",
         q="Entries can fill mid-candle, before the bar closes",
         b="ON WATCH is on: once price moves 25% of the previous bar's range past "
           "the level, the entry fills there rather than waiting for the close. "
           "89.8% of entries already fill this way. It was only ever A/B'd over "
           "120 day-cards, never against the full two years.",
         w="signal_runner.ON_WATCH = 1, BAR_EXTREME_FRAC = 0.25",
         c="+0 on every metric over the 120 graded day-cards; never run at 2-year "
           "scale",
         opts=[("keep", "Keep it on"),
               ("off", "Wait for the close"),
               ("measure", "Keep it on but run the 2-year A/B first")]),

    dict(k="min_risk_floor",
         q="A signal is dropped when its stop is too close to its entry",
         b="When the mid-candle fill lands right at the level, entry and stop can "
           "collapse together -- and then a minimum-risk check deletes the signal. "
           "This suppressed six of your S marks. It is the interaction of two "
           "reasonable rules producing an unreasonable result.",
         w="signal_runner.ENABLE_STRUCTURAL_RISK_FLOOR / ENABLE_MIN_RISK_FILL_CLAMP",
         c="the floor deletes 86.7% of moved-fill signals; 6 of your S marks "
           "suppressed",
         opts=[("stop", "Keep the fill, use the structural stop, not the collapsed one"),
               ("skip", "If risk collapses, skip the trade"),
               ("keep", "Leave it as is")]),

    dict(k="dedupe",
         q="The same setup cannot re-fire for 30 minutes",
         b="If a level breaks, retests, fails and sets up again inside half an "
           "hour, the second one is thrown away as a duplicate. Sometimes that is "
           "the same idea twice. Sometimes it is a genuine second chance.",
         w="backtest_week.DEDUPE_BARS = 30",
         c="unmeasured -- no dedupe-window sweep exists",
         opts=[("keep", "30 minutes is right"),
               ("shorter", "Too long, shorten it"),
               ("level", "Dedupe by level, not by clock")]),

    dict(k="no_repeat_entries",
         q="The same level cannot be traded twice in one day",
         b="Same symbol, same direction, same level -- blocked after the first "
           "entry. This is separate from the 30-minute dedupe and separate again "
           "from the 84% rule, which is specifically about re-entering the SAME "
           "price after a stop-out.",
         w="signal_runner.NO_REPEAT_ENTRIES = True",
         c="41.8% of traded signals are 2nd-or-later on their symbol-day and "
           "survive this rule; they book +0.767R vs +1.092R for firsts",
         opts=[("keep", "Keep it"),
               ("strict", "Stricter -- one trade per symbol per day"),
               ("off", "Off, the 84% rule already handles re-entries")]),

    # ---- grading -----------------------------------------------------------
    dict(k="arrival_order",
         q="The engine's real entry rule is 'first with the trend today'",
         b="968 of the 1,000 traded rows are tradeable ONLY because they were the "
           "first with-trend signal of the day inside 90 minutes. Not because of "
           "their grade. The grader is nearly binary -- alert or silent -- and "
           "arrival order picks 95.3% of the book.",
         w="signal_runner._calibration_grade",
         c="arrival order picks 95.3% of the book",
         opts=[("both", "Keep arrival order AND add the downgrade count"),
               ("grade", "Grade only -- drop arrival order"),
               ("order", "Arrival order is right, it is how you trade")]),

    dict(k="candle_shape",
         q="The engine grades candle SHAPES, and that is what kills your setups",
         b="Three shape rules do the damage: the entry candle must itself touch "
           "the level, must be the right colour, and must not oppose higher-"
           "timeframe bias. Your eight variables are about STRUCTURE. On your 34 "
           "fresh S days the engine reached the setup at the right minute nine "
           "times and graded every one of them a no-trade.",
         w="signal_runner._grade_pa",
         c="7,219 of 7,485 clean-by-your-ladder signals are killed here",
         opts=[("replace", "Replace shape grading with the downgrade count"),
               ("relax", "Keep it but drop the colour rule"),
               ("keep", "Keep it")]),

    dict(k="s_plus_per_day",
         q="At most 3 top-grade signals per day",
         b="A leftover cap from before you said 'trade every S the engine sees'. "
           "It has never bound in practice because the engine makes 2 S in two "
           "years, but it is still in the code and would bind the moment the "
           "grader is fixed.",
         w="signal_runner.S_PLUS_PER_DAY = 3",
         c="never binds today; would bind after the grader fix",
         opts=[("delete", "Delete it, no cap"),
               ("keep", "Keep 3"),
               ("keep5", "Raise it rather than delete it")]),

    dict(k="counter_trend",
         q="A signal against the day's trend is capped at alert-only",
         b="The 'trend' here is the stock's own move that day, used as a stand-in "
           "for market direction because the real rule was never written. It trips "
           "on 89.5% of everything, which is close to tripping on nothing.",
         w="signal_runner._calibration_grade counter-trend cap",
         c="trips 89.5% of the book",
         opts=[("qqq", "Use QQQ/SPY direction instead of the stock's own"),
               ("keep", "Keep the stock's own trend"),
               ("delete", "Delete it")]),

    dict(k="chase",
         q="Entering more than 0.5% past the level is tagged, not blocked",
         b="Your own 'don't buy the top' rule. It was measured -- those entries win "
           "28% against 37% for the rest -- and then left as a label that changes "
           "nothing, because the old tier already screened most of them out. That "
           "tier is being deleted.",
         w="signal_runner.CHASE_PCT = 0.005",
         c="chase entries 28.0% win vs 37.3% non-chase",
         opts=[("block", "Block them now the old tier is gone"),
               ("downgrade", "Make it a downgrade variable"),
               ("keep", "Keep it as a tag")]),

    dict(k="pm_levels",
         q="Premarket-level breaks can never trade, only alert",
         b="Break-and-retests off the premarket high or low are capped at alert. "
           "Negative in both backtest years, and you have said you rarely use "
           "premarket levels -- so data and you agree. Worth confirming it is "
           "still what you want, because premarket range is the strongest "
           "predictor of a good day the project has found.",
         w="signal_runner.py -- PMH/PML cap to C",
         c="negative both years; separately, premarket RANGE quartile spreads "
           "+0.902R across the book",
         opts=[("keep", "Keep them alert-only"),
               ("trade", "Let them trade"),
               ("first", "Trade them only as the first break of the day")]),

    dict(k="consolidation",
         q="If all the levels bunch together, the whole day is skipped",
         b="When the prior-day high/low and the opening range all sit inside 0.5% "
           "of each other, every signal that day is dropped as chop. The 0.5% is a "
           "guess nobody stated.",
         w="signal_runner._is_consolidation, 0.5%",
         c="unmeasured -- no sweep on the 0.5%",
         opts=[("keep", "Right idea, right number"),
               ("measure", "Right idea, sweep the number"),
               ("delete", "Delete it, I'll judge chop myself")]),

    dict(k="level_block",
         q="Another level sitting inside the 2R path caps the grade",
         b="Your rule, from your own 91-trade review: 'middle of a bunch of levels, "
           "probability goes down significantly.' It caps the setup at alert-only. "
           "With the 2R target going away, this rule needs re-stating -- a level "
           "in the path is now a TARGET, not an obstacle.",
         w="signal_runner.LEVEL_BLOCK_CAP = True",
         c="unmeasured since the target change",
         opts=[("target", "A level in the path becomes the target"),
               ("keep", "Keep it as a cap"),
               ("delete", "Delete it")]),

    dict(k="pivot_levels",
         q="The engine invents levels from swing pivots",
         b="Beyond the six levels you actually watch, it derives pivot highs and "
           "lows from the last 30 bars and treats them as breakable levels. Those "
           "pivots are the single biggest level category in the book -- 3,735 of "
           "the vetoed clean signals sit on one.",
         w="signal_runner.PIVOT_LEVELS = 1, strength 2, lookback 30",
         c="pivot high/low is the most common level in the book",
         opts=[("keep", "Keep them, they are real levels"),
               ("six", "Only the six levels I watch"),
               ("demote", "Keep them but never as an S")]),

    dict(k="level_retire",
         q="A level is retired after two touches",
         b="Once a level has been broken and retested twice, the engine stops "
           "watching it for 30 minutes. This is the closest thing in the code to "
           "your 'chopping around is not respecting the level' -- but it was "
           "written as housekeeping, not as your rule.",
         w="signal_runner.LEVEL_RETIRE_TOUCHES = 2, cooldown 30",
         c="unmeasured",
         opts=[("rule", "Make this the level-respect rule and tune it"),
               ("keep", "Keep as housekeeping"),
               ("delete", "Delete it")]),

    # ---- the instrument ----------------------------------------------------
    dict(k="options_model",
         q="The whole options model is one number: delta 0.5",
         b="Every contract calculation in the repo assumes the option moves 50 "
           "cents for every dollar the stock moves, forever, with no theta and no "
           "gamma. Scored properly as the 0DTE at-the-money contracts you actually "
           "trade, the SAME 1,017 trades read +1.4988R instead of +0.8341R -- "
           "because convexity pays the runners.",
         w="options_sizer.DEFAULT_DELTA = 0.5",
         c="contract read +1.4988R vs underlying +0.8341R; win rate falls 53% -> "
           "38% while mean R rises",
         opts=[("real", "Price real contracts, that is what I trade"),
               ("keep", "Keep scoring the stock, it is simpler"),
               ("both", "Report both every time")]),

    dict(k="strike",
         q="Nothing in the engine picks a strike or an expiry",
         b="You have said nearest expiry, at the money. No code implements it, so "
           "no report has ever told you how many contracts to buy or what the "
           "premium stop is -- which is the one output you have asked for since "
           "the first session.",
         w="nothing implements it",
         c="unmeasured",
         opts=[("atm0", "0DTE at-the-money"),
               ("atm1", "1DTE at-the-money"),
               ("sweep", "Sweep ATM +/-1 strike and tell me")]),

    dict(k="spread",
         q="Nothing models the bid-ask spread",
         b="Your oldest complaint in the whole project: 'an entry at $1.38 and a "
           "stop loss at $1.32 would be triggered almost immediately, and that "
           "spread makes it too hard to get an entry for a human or a robot.' No "
           "rig has ever charged a spread.",
         w="nothing implements it",
         c="unmeasured -- and it is the largest unpriced cost in the project",
         opts=[("model", "Charge a real spread, even a rough one"),
               ("filter", "Filter out contracts whose spread is too wide"),
               ("keep", "Ignore it for now")]),

    # ---- the loop ----------------------------------------------------------
    dict(k="loss_halt",
         q="Two losses in a row does not stop the day",
         b="Your rule from the very first session -- 'two losses consecutive in a "
           "row on the same day is a good signal to stop trading' -- exists as an "
           "environment variable in the live bot and is not in the backtest at "
           "all. So no published number includes it.",
         w="live env var only, not in backtest_week",
         c="unmeasured in the two-year book",
         opts=[("both", "Put it in the backtest and the live path"),
               ("live", "Live only"),
               ("drop", "Drop the rule")]),

    dict(k="risk_dollars",
         q="Every trade risks exactly $1,000",
         b="Flat, regardless of grade or conviction. You have mentioned wanting "
           "different size by grade since the A-to-D idea, and once the ladder is "
           "S/A/C that becomes expressible for the first time.",
         w="backtest_week.RISK_DOLLARS = 1000.0",
         c="a scale-in arm topped out at +1.4697R and was the only lever that "
           "moved the mean",
         opts=[("flat", "Flat $1,000, keep it simple"),
               ("grade", "Size by grade -- S bigger than A"),
               ("equity", "Percent of equity")]),

    dict(k="retired_setups",
         q="Two setups are built and permanently off",
         b="Fair-value-gap and flag detectors exist in the code and are disabled. "
           "The flag one was invented, never validated by you, and lost the "
           "equivalent of the whole system in a 12-month run. They are dead weight "
           "unless you want them rebuilt.",
         w="signal_runner.RETIRED_SETUPS",
         c="flag: 465 fires for -$57.6k over 12 months before it was benched",
         opts=[("delete", "Delete the code"),
               ("keep", "Leave them off but keep the code"),
               ("rebuild", "Rebuild the flag one properly")]),
]


def selfcheck() -> int:
    keys = [f["k"] for f in FACTS]
    assert len(set(keys)) == len(keys), "duplicate fact key"
    for f in FACTS:
        for field in ("k", "q", "b", "w", "c", "opts"):
            assert f.get(field), "fact %s is missing %s" % (f.get("k"), field)
        assert 2 <= len(f["opts"]) <= 4, "fact %s has %d options" % (f["k"], len(f["opts"]))
        assert len(f["b"]) > 120, "fact %s has no real body" % f["k"]
    print("master_facts selfcheck GREEN: %d facts" % len(FACTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(selfcheck())
