#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
xref_austin.py -- cross-reference the mentor rulebook against Austin's.

Reads  research/corpus_sf/mentor_rules.jsonl  (mentor rule clusters)
Reads  Austin's Vault/Projects/omen-rulebook.md  (READ-ONLY, never written)
Writes research/corpus_sf/mentor_rules.jsonl    (same file, + xref fields)

The verdict map below is a judgement call recorded explicitly so it can be
argued with. Each entry names the Austin rulebook line it was matched against.
Nothing here is an engine change: NEW items are ballot lines, CONFLICTS are
surfaced unresolved.
"""
from __future__ import annotations
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
JSONL = os.path.join(HERE, "mentor_rules.jsonl")

# cluster_id -> (verdict, austin_anchor, note)
VERDICTS = {
    # ---------------------------------------------------------- AGREES
    "SF183": ("AGREES", "ballot q1 -- a 1-minute candle CLOSE below is the exit; wicks stop nothing",
              "Neto states the same close-triggered exit independently."),
    "SF100": ("AGREES", "ballot q1 -- close is the trigger",
              "Would not close the trade unless a candle CLOSES beyond the stop."),
    "SF117": ("AGREES", "ballot q1 / 'closes are evidence, wicks are not' (settled 5x)",
              "Scarface: waiting for candle closes is how you know PA is bullish/bearish."),
    "SF068": ("AGREES", "ballot q1 -- close-based invalidation",
              "Mamba reads the trade off a 5m BODY close, not the wick."),
    "SF199": ("AGREES", "ballot q1 + a2/a3 level respect -- a close THROUGH is disrespect",
              "Scarface calls anything short of a strong closure above the level chop."),
    "SF063": ("AGREES", "ballot q18 -- no displacement is a downgrade; B&R is the core setup",
              "Neto names the same sequence: break, displacement, retest."),
    "SF055": ("AGREES", "ballot q18 -- displacement",
              "Neto dislikes the immediate retest; wants displacement first."),
    "SF021": ("AGREES", "the B&R machinery is the engine",
              "Wait for break and retest of a key level, never a trend line."),
    "SF050": ("AGREES", "ballot q18 -- displacement",
              "Lauren only took trades with strong displacement out of the range."),
    "SF029": ("AGREES", "ballot q4 -- tranche 1 at HOD",
              "Scarface needs the name able to break to HOD/LOD."),
    "SF070": ("AGREES", "ballot q4 -- tranche 1 at HOD",
              "Jdub always targets HOD/LOD on a B&R."),
    "SF196": ("AGREES", "ballot q4 -- tranche 1 at HOD",
              "Hayden: HOD is normally the first target."),
    "SF075": ("AGREES", "batch 02 a2/b9 -- wicking the level is respect; trends respect wicky candles",
              "Neto describes Austin's level-respect test in candle-shape terms."),
    "SF067": ("AGREES", "OCR defined 2026-08-23 + 'only if isolated, hard to dispute'",
              "Neto: not every opposite-to-trend candle is an order block."),
    "SF169": ("AGREES", "2026-08-29 day policy -- '1 trade a day is all we need and want'",
              "Scarface states the day policy Austin's rulebook already credits to him."),
    "SF192": ("AGREES", "2026-08-29 -- 'level, bottom of candle entered on, pivot structure'",
              "Lauren names pivots as stop points -- Austin's third placement family."),
    "SF182": ("AGREES", "2026-08-29 -- stop at the broken level on a B&R",
              "Lauren puts the stop just below the retest level."),
    "SF184": ("AGREES", "2026-08-29 -- 'wick of the OCR' / candle entered on",
              "Lauren puts the stop below the zone and the rejection candle's wick."),
    "SF073": ("AGREES", "batch 02 c6 -- 'we dont have any higher timeframe bias yet'; HTF_BIAS_VETO deleted",
              "Jdub independently says an ORB needs no HTF bias. Validates the deletion."),
    "SF045": ("AGREES", "2026-08-28 -- 'the target is the next structural level, not 2x risk'",
              "Hayden: let winners ride TO NEXT LEVELS."),
    "SF048": ("AGREES", "2026-08-29 -- 30% at 2R or the nearest of the six levels",
              "Mamba targets liquidity / reversal areas inside a range."),
    "SF197": ("AGREES", "2026-08-29 -- 30% at break of trend/structure",
              "Neto holds until the market gives a reason to exit."),
    "SF178": ("AGREES", "2026-08-29 -- size comes from the prop firm's rules, 10% failure tolerance",
              "Neto: do not size up on confidence."),
    "SF181": ("AGREES", "2026-08-29 -- sizing has an objective function",
              "Position size should come from design, not feeling."),
    "SF164": ("AGREES", "2026-08-29 -- sizing has an objective function", "Same rule, restated."),
    "SF086": ("AGREES", "2026-08-29 -- 'if im not trading fixed 2:1 ... maybe i have the wrong idea risking 1k everytime'",
              "Lauren sizes off the stop distance, not a fixed contract count. Directly supports reopening fixed $1k risk."),
    "SF092": ("AGREES", "2026-08-29 -- 'overtrading is too [bad]'", "Avoid overtrading."),
    "SF166": ("AGREES", "2026-08-29 -- overtrading is a stopping-rule question, not a chart question",
              "Neto: overtrading is not solved with market analysis."),
    "SF001": ("AGREES", "2026-08-29 scale-out ladder -- 2R slice plus a trailed runner",
              "Lauren's 2-contract version has the same shape."),
    "SF102": ("AGREES", "ballot q1 -- always have and respect a stop", "Generic but consistent."),
    "SF058": ("AGREES", "1R is defined before entry", "Neto never enters without knowing risk."),

    # ---------------------------------------------------------- CONFLICTS
    "SF126": ("CONFLICTS", "2026-08-28 golden rule -- 'the earlier in the day you trade, the more common S trades are'",
              "Scarface: wait for the first 5 minutes to form before taking anything. "
              "Austin's held-out S entries run 9:34-10:19, median 9:42, 65% before 9:45, and the "
              "existing 09:40 floor already costs 10 of his 34 S days."),
    "SF203": ("CONFLICTS", "2026-08-28 golden rule -- earliest is best",
              "Scarface: the 5-minute retest is the only thing to look for. Same clash."),
    "SF008": ("CONFLICTS", "2026-08-28 golden rule -- earliest is best",
              "Jdub: if your stats say the first 5 minutes lose, skip the first 30 minutes. "
              "Austin's 09:30-09:45 block books +1.1619R at 60.7% against a book mean of +0.9551R."),
    "SF112": ("CONFLICTS", "2026-08-28 -- 'the target is the next structural level, not 2x risk'",
              "Lauren: TP1 should ALWAYS be a fixed 1:2. This is the assumption Austin's own "
              "arithmetic killed -- mean R = wT-(1-w) cannot reach 2.0 at T=2."),
    "SF049": ("CONFLICTS", "2026-08-29 -- 'cant reach 2r gate unless ... letting more then 10 percent run past 2r'",
              "Hayden sells the WHOLE position at 1.5-2R on small size. That removes the runner "
              "Austin named as the only lever that reaches the money gate."),
    "SF061": ("CONFLICTS", "2026-08-28 -- GOVERNOR_S_CAP deleted, 'however many engine sees we trade S'",
              "Lauren caps at 1-2 trades a day. Austin removed the cap. (The A+-setups-only half "
              "of her sentence agrees with 'we only trade S'.)"),
    "SF042": ("CONFLICTS", "2026-08-28 -- no per-day and no per-symbol cap",
              "Mamba targets 8-15 trades a month. Same cap clash, monthly."),
    "SF200": ("CONFLICTS", "2026-08-29 -- after 11:00 it is management only, 10% runner; the engine is 1-minute",
              "Scarface says trade the 5-minute timeframe after 11:00. Two clashes: that there is "
              "trading after 11:00 at all, and that the timeframe changes."),
    "SF188": ("CONFLICTS", "2026-08-29 -- 'level, bottom of candle entered on, pivot structure'",
              "Lauren adds a 1.5-2x ATR volatility stop. A fourth placement family Austin has not named."),
    "SF105": ("CONFLICTS", "ballot q1 -- the level stop triggers on the close, not on touch",
              "Mamba rests a hard stop on the chart and lets it work. Neto (SF183) says the "
              "opposite. Austin is with Neto for the level stop -- but his disaster stop IS a "
              "resting intrabar stop, so the mentors bracket his two-stop design."),
    "SF047": ("CONFLICTS", "2026-08-29 ladder -- 30% at HOD",
              "Jdub takes ~80% off at HOD when scalping. Austin's first slice is 30%. "
              "Hayden's SF019 is a third number (75% inside 3:1R). Austin's q4/q5 tension "
              "(30/30/30/10 vs 50/20/20/10) is unresolved and these are votes in it."),
    "SF019": ("CONFLICTS", "2026-08-29 ladder -- 30/30/30/10",
              "Hayden: 75% as a scalp inside 3:1R, 25% continuation."),
    "SF006": ("CONFLICTS", "2026-08-29 -- 'you know the 6 levels i watch thats it'",
              "Jdub demotes PMH/PML when price is in a range -- and contradicts himself in SF065, "
              "where PMH/PML are the only premarket levels worth marking. A conditional level set "
              "against Austin's closed six."),
    "SF007": ("CONFLICTS", "2026-08-29 -- the six levels are closed",
              "Jdub: 'I personally don't use PMH and PML often.'"),

    # ---------------------------------------------------------- NEW (ballot)
    "SF066": ("NEW", "one tolerance unit governs entry trigger / 84% reclaim / stop slippage -- NOT the retest touch",
              "Neto: the retest is never to the penny, always close to the line."),
    "SF030": ("NEW", "no stated rule on what confirms a retest",
              "Neto: wait for how price REACTS to the level, not for more candles."),
    "SF064": ("NEW", "the six levels are uniform across symbols in the engine",
              "Neto: which level family works best is per-ticker; backtest it per ticker."),
    "SF193": ("NEW", "ballot q4/q5 parked the regime question -- '30 percent is when better chance stock runs, 50 for choppier, we must identify this'",
              "Neto names the discriminator: available reward potential at entry."),
    "SF005": ("NEW", "batch 02 c6 -- 'youll need to tell me what that is then'",
              "Lauren: start on weekly/daily/4H for trend, key levels, liquidity zones."),
    "SF040": ("NEW", "batch 02 c6 -- HTF bias undefined",
              "Mamba: the setup must be paired with market conditions and HTF trend."),
    "SF037": ("NEW", "batch 02 c6 -- HTF bias undefined",
              "Jdub names the timeframes: daily and hourly."),
    "SF069": ("NEW", "premarket bottom-quartile filter exists; prior-day-range containment does not",
              "Hayden: highest-probability trades are outside the previous day's range."),
    "SF146": ("NEW", "2026-08-29 Q8 -- 'we just need to find other targets'",
              "Mamba names one: the opening price, when there is no level or it is too far."),
    "SF083": ("NEW", "no per-symbol specialisation rule; COIN is 104 of 1,017 traded rows",
              "Neto trades 4 names consistently, 2 more occasionally."),
    "SF165": ("NEW", "no specialisation rule", "Neto: one ticker, one setup, for a decent period."),
    "SF116": ("NEW", "no specialisation rule", "Scarface: backtest one ticker at a time, separately."),
    "SF099": ("NEW", "the engine is instrument-free; no strike rule exists",
              "Jdub: always 1 OTM or the contract with the most volume."),
    "SF171": ("NEW", "no strike rule", "Neto trades 1 OTM because expected moves are close."),
    "SF014": ("NEW", "no strike rule", "Neto: 1 OTM or most volume when there is an HTF thesis."),
    "SF015": ("NEW", "no strike rule", "Neto: strike matters less when scalping."),
    "SF162": ("NEW", "the 2-loss halt vs trade-until-green tension, delegated to measurement 2026-08-29",
              "Neto adds a third option nobody has measured: a mandatory break after ONE loss."),
    "SF056": ("NEW", "the engine has scale-OUT only; scale-IN has never been stated",
              "Jdub takes a starter on A+ setups rather than miss the move."),
    "SF170": ("NEW", "2026-08-29 -- 'wont get killed or destroyed by fills or too tight rr'",
              "Neto bounds the stop at 18-25% of contract premium at entry."),
    "SF053": ("NEW", "card 11 -- the large-candle boundary case, resolved on stop usability",
              "Hayden: entering ON the retest candle is rare and wants a massive hammer."),
    "SF154": ("NEW", "the 10:45-11:00 bad window is kept by instruction; no time-on-screen rule exists",
              "Mamba: the longer you look at bad price action, the likelier you take a bad trade."),
    "SF039": ("NEW", "stop family 3 is 'pivot structure', unqualified",
              "Mamba: intraday pivots work best; the last 30 minutes do not count."),
    "SF121": ("NEW", "2026-08-29 -- the ATH exception ('nvda approaching all time highs')",
              "Neto: passing on ATH breakouts is fine if they measure worse. Austin's exception "
              "assumes you take them for the better target. Same regime, opposite default."),
    "SF135": ("NEW", "no stop-confluence list exists", "Lauren places stops just beyond key levels."),
    "SF104": ("NEW", "wicks stop nothing (close-triggered), which is a different mechanism",
              "Lauren places stops outside wicks to survive stop hunts."),
    "SF189": ("NEW", "no stop-hunt model exists",
              "Lauren: market makers hunt stops above previous highs/lows."),
    "SF191": ("NEW", "|entry - stop| is the R denominator; nothing links entry quality to stop width",
              "Neto: a poor entry forces a wider stop."),
}


def main():
    rows = [json.loads(l) for l in open(JSONL, encoding="utf-8") if l.strip()]
    by_id = {r["cluster_id"]: r for r in rows}
    missing = [k for k in VERDICTS if k not in by_id]
    if missing:
        print("WARNING: verdict ids not present in the jsonl:", missing)
    for r in rows:
        v = VERDICTS.get(r["cluster_id"])
        if v:
            r["xref_verdict"], r["austin_anchor"], r["xref_note"] = v
        else:
            r["xref_verdict"] = "UNCLASSIFIED"
            r["austin_anchor"] = None
            r["xref_note"] = None
    with open(JSONL, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    import collections
    c = collections.Counter(r["xref_verdict"] for r in rows)
    print("clusters:", len(rows), dict(c))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
