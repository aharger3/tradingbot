"""build_augur_understanding.py -- AUGUR's onboarding homework.

Austin asked for "any onboarding we should do so it understands my system." This is
that page: 40 statements of what AUGUR believes your trading system is, in its own
words, each with a source and a confidence tag, built exactly like build_qa.py --
one question per card, the shared probe_page.py shell, no chart.

Companion doc: research/augur_understanding.md (same 40 statements, same order,
grouped and sourced in full). Keep the two in sync by hand -- this file is the only
generator, per the deck standard (omen-decks.md: "one file may define a card").
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import probe_page

OUT = os.path.join(HERE, "probes", "augur-understanding.html")

VERDICT_OPTS = [
    ("right", "Right"),
    ("wrong", "Wrong"),
    ("partly", "Partly"),
]

# (id, group, confidence, statement, source_html)
STATEMENTS = [
    # --- Setups ---
    ("S1", "setups", "settled",
     "Break-and-retest is your bread-and-butter setup: price breaks a level, then "
     "comes back to retest it before you take the trade.",
     "947 of 1,017 traded rows in the two-year book are break-and-retest "
     "(<code>omen-rulebook.md</code>, &ldquo;Kill B and A+ outright,&rdquo; 2026-08-29)."),
    ("S2", "setups", "settled",
     "The one-candle rule (OCR) is your name for an order block: one candle the "
     "opposite color of the trend, that price is expected to respect, then break, "
     "and retest.",
     "&ldquo;i forgot my OCR definition is simple, it's in the name 'one candle' &mdash; "
     "one candle that's the opposite color of the way it's trending.&rdquo; "
     "&mdash; Austin, 2026-08-23."),
    ("S3", "setups", "settled",
     "An OCR candle only counts if it would work as the stop &mdash; the test is "
     "&ldquo;would the candle be good to use as the stop?&rdquo;, not how big or "
     "clean it looks.",
     "<code>omen-rulebook.md</code>, card 11, ratified &ldquo;Round two,&rdquo; 2026-08-28."),
    ("S4", "setups", "settled",
     "The 84% rule is a re-entry modifier that fires after a stop-out, not a "
     "standalone setup &mdash; it re-enters the price you originally entered on "
     "(not just the level), on a candle close that reclaims it.",
     "rule ballot batch01 q12/q13 &mdash; Austin, 2026-08-23."),
    ("S5", "setups", "settled",
     "Break-and-retest with an OCR at the same level (BR+OCR) is its own third "
     "setup, and it's worth a +1 upgrade to the grade &mdash; not just a rebate "
     "against a downgrade.",
     "&ldquo;remember BR and OCR is also a setup when both of them are together&rdquo; "
     "and &ldquo;we also need to work BR and OCR as +1 upgrade not downgrade "
     "confluence.&rdquo; &mdash; Austin, 2026-08-29."),
    ("S6", "setups", "measured",
     "Order block is a setup family you rate highly &mdash; 9 of 12 tagged cards "
     "graded S &mdash; that the engine currently has no detector for at all: a "
     "coverage hole, not a weak signal.",
     "<code>research/MORNING_REPORT.md</code> &sect;3 HINTS. n=12, thin &mdash; "
     "flagged as a hint in its own source."),

    # --- Levels ---
    ("L1", "levels", "settled",
     "The six levels you break, retest and target are PDH, PDL, PMH, PML, ORH, "
     "ORL &mdash; the opening range counts, HOD and LOD do not.",
     "&ldquo;the level confusion was probably me, the 6 levels have always been "
     "correct.&rdquo; &mdash; Austin, 2026-08-29 (superseding an earlier answer the "
     "same day that named HOD/LOD instead)."),
    ("L2", "levels", "settled",
     "Pivot-structure levels can be drawn on a chart for context, but they never "
     "gate an entry, a stop, or a target.",
     "&ldquo;only the 6 levels, but you can still visualize those pivots.&rdquo; "
     "&mdash; Austin, 2026-08-29."),
    ("L3", "levels", "settled",
     "PDH and PDL are good levels to trade, full stop &mdash; even though a "
     "measured backtest found avoiding them adds real edge, you ruled that a flag "
     "to watch, not a rule to ship.",
     "&ldquo;PDHPDL are good levels.&rdquo; &mdash; Austin, 2026-09-03 evening "
     "(<code>AUGUR.md</code>, &ldquo;Rulings 2026-09-03, evening&rdquo;)."),
    ("L4", "levels", "settled",
     "There is no higher-timeframe bias rule in your system today &mdash; you've "
     "said twice you'd need to be told what one even means, so nothing gets to "
     "veto a trade on &ldquo;the higher timeframe disagrees.&rdquo;",
     "&ldquo;we dont have any higher timeframe bias yet youll need to tell me what "
     "that is then.&rdquo; &mdash; Austin, ballot batch02 c6, 2026-08-27."),

    # --- Entry ---
    ("EN1", "entry", "settled",
     "You enter as the candle is forming, not waiting for its close &mdash; "
     "especially near HOD/LOD, so you don't pay a bad price.",
     "&ldquo;as candle forming not lod/HOD&rdquo; recurs across the mark corpus "
     "(14 of 58 graded note fields, per <code>OMEN.md:124</code>); most recently "
     "&ldquo;candle close for most, some as candle forming so i dont get a bad fill "
     "at high of day&rdquo; &mdash; Austin, 2026-08-30. Restated 20+ times."),
    ("EN2", "entry", "settled",
     "That forming-candle entry is not a separate rule &mdash; it belongs to ON "
     "WATCH, the state where the engine watches a level mid-bar instead of waiting "
     "for the close.",
     "&ldquo;it should exist already its called ON WATCH... it had to do with on "
     "watch and mid candle entries.&rdquo; &mdash; Austin, 2026-08-28/30."),
    ("EN3", "entry", "settled",
     "Most entries are fine waiting for the close &mdash; the early-entry "
     "exception exists specifically for setups running toward the high or low of "
     "day, where waiting would wreck the risk-reward.",
     "&ldquo;most entries work at candle close, but some that are close to hod, "
     "you want to get a good fill and not one that will have bad RR.&rdquo; "
     "&mdash; Austin, ballot batch02 b3, 2026-08-27."),
    ("EN4", "entry", "settled",
     "Earlier in the day is better, and you'd rather end the day early &mdash; the "
     "earliest S setup usually has the best odds, though you've named one "
     "exception: a later setup with a materially better target can beat an "
     "earlier one.",
     "&ldquo;a golden rule the earlier in the day you trade, the more common it is "
     "for S trades and higher probability. you want to end the day early.&rdquo; "
     "&mdash; Austin, 2026-08-28; exception from &ldquo;sometimes we dont want to "
     "take the earliest s because...&rdquo; &mdash; Austin, 2026-08-29."),

    # --- Stop ---
    ("ST1", "stop", "settled",
     "A stop triggers on the candle's CLOSE beyond the level &mdash; a wick "
     "through it, alone, does not take you out.",
     "rule ballot batch01 q1 &mdash; Austin, 2026-08-23; reaffirmed &ldquo;stop "
     "losses are candle close you're right&rdquo; &mdash; Austin, 2026-08-30. "
     "Restated at least thirteen dated times, per the rulebook's own count."),
    ("ST2", "stop", "settled",
     "The hard floor on any one loss is &minus;1R &mdash; the earlier &minus;1.25R "
     "disaster-stop clamp has been dropped for a simpler number.",
     "&ldquo;1R is simpler so why not go with that? no stocks should be running to "
     "&minus;10R&rdquo; &mdash; Austin, 2026-09-03 evening (<code>AUGUR.md</code>, "
     "&ldquo;Rulings 2026-09-03, evening&rdquo;)."),
    ("ST3", "stop", "settled",
     "A break-even stop is close-based too, not wick-based, and because it fills "
     "at that close it can book a small loss instead of landing at exactly zero.",
     "<code>omen-rulebook.md</code>, &ldquo;Break-even slippage &mdash; same rule "
     "as the initial stop,&rdquo; 2026-08-28."),
    ("ST4", "stop", "settled",
     "The stop is picked per-trade from three structural candidates &mdash; the "
     "wick of the OCR, the candle you entered on, or the level that broke on a "
     "break-and-retest &mdash; whichever gives the best tradable risk-reward, "
     "with a disaster stop underneath.",
     "&ldquo;stops go where they make sense... wick of OCR, candle entered on, "
     "break and retest of a level stop loss that level.&rdquo; &mdash; Austin, "
     "2026-08-29."),
    ("ST5", "stop", "inferred",
     "AUGUR infers you don't have one fixed answer for wick-vs-level on a stop: "
     "your own marks name three different anchors on three different cards (a "
     "candle's body, its low, its wick), and you've called the tension genuinely "
     "unresolved.",
     "&ldquo;if its tight and you have to chose the wick or the level, choose the "
     "wick&rdquo; (AMZN 2026-01-14) vs. &ldquo;those 3 green candles even though i "
     "dont like bodies that wouldve been a better stop&rdquo; (NVDA 2024-09-03) "
     "vs. &ldquo;stop body of opening range&rdquo; (GOOGL 2024-10-15) &mdash; "
     "<code>research/g92_master_spec.md</code>, Contradictions &sect;5. n&asymp;6 "
     "cards. Never stated by you as one rule."),

    # --- Target and exits ---
    ("EX1", "exits", "settled",
     "The target isn't a flat 2R &mdash; it's the next real structural level (a "
     "PDH/PMH/whole dollar), with 2R used as the fallback only when nothing else "
     "sits close.",
     "&ldquo;its about sizing for the mean 2rr, so if there are no other levels to "
     "target... harder to trade.&rdquo; &mdash; Austin, ballot batch02 b4, "
     "2026-08-27; ratified as &ldquo;the target is the next structural level, not "
     "2x risk,&rdquo; 2026-08-28."),
    ("EX2", "exits", "settled",
     "Your stated scale-out ladder is 30% off at HOD (LOD on puts), 30% at 2R or "
     "the nearest of your six levels, 30% on a break of trend/structure, and a "
     "10% runner trailed to break-even.",
     "&ldquo;scalling 30 HOD, 30, 2r or nearest level, other 30 break of "
     "trend/structure/10 runner stop loss break even.&rdquo; &mdash; Austin, "
     "2026-08-29. His stated numbers &mdash; not yet what the shipped code runs."),
    ("EX3", "exits", "settled",
     "One trade a day is the actual goal: you take the first S setup that shows "
     "up, and if it wins, you're done for the day.",
     "&ldquo;we trade the s trade that comes up first, and if it wins, were done "
     "for the day.&rdquo; &mdash; Austin, 2026-08-29."),
    ("EX4", "exits", "settled",
     "The two-loss-halt question was left open on purpose, and the answer that "
     "came back: three losses ends the day, with a &minus;$2,000 floor &mdash; "
     "not the two-loss rule you first mentioned, once the money showed a trade "
     "taken after two losses still profits on average.",
     "&ldquo;we dont know if 2 losers in a row is a stopping point, keep trading s "
     "trades until youve hit profit... 2 consecutive halts is bad, but "
     "overtrading is too, subagents will find the medium&rdquo; &mdash; Austin, "
     "2026-08-29; resolved same day, <code>omen-rulebook.md</code> &ldquo;The day "
     "rule &mdash; settled.&rdquo;"),
    ("EX5", "exits", "settled",
     "Green weeks are a target you watch &mdash; 87% &mdash; not a hard "
     "constraint the whole strategy has to bend around, since chasing 100% costs "
     "most of the income.",
     "&ldquo;87% is the target, keep the money.&rdquo; &mdash; Austin, 2026-08-29."),

    # --- Grading ---
    ("GR1", "grading", "settled",
     "Your grade is arithmetic, not a feel call: S is clean, A is one tripped "
     "downgrade, C is two &mdash; S minus downgrades plus a confluence bonus, "
     "floored at C once three or more variables trip.",
     "&ldquo;S = clean. A = one variable downgrade. C = two variable "
     "downgrade.&rdquo; &mdash; Austin, 2026-08-23; floor rule from Q&amp;A "
     "batch 04, 2026-08-28."),
    ("GR2", "grading", "settled",
     "Confluence &mdash; BR+OCR together, or price on the right side of most of "
     "the levels you watch &mdash; is worth one upgrade point, capped: the two "
     "upgrade paths don't stack, and you've called confluence rare, under 1 in "
     "5 setups.",
     "ballot batch02 b5, 2026-08-27; &ldquo;rare, under 1 in 5&rdquo; &mdash; "
     "Austin, 2026-08-24/28."),
    ("GR3", "grading", "settled",
     "Nine variables can cost a grade: no displacement, a stale retest, a level "
     "not being respected, an exhausted stock, disrespected counter-trend "
     "candles, a break that got rejected, no retest at all, an OCR not honored, "
     "and &mdash; added later &mdash; an oversized red-body candle sitting inside "
     "recent chop.",
     "<code>omen-rulebook.md</code>, &ldquo;The downgrade list &mdash; settled "
     "2026-08-23&rdquo; plus ballot batch02 b6."),
    ("GR4", "grading", "measured",
     "AUGUR reads chop &mdash; closing at, or chopping around, a level instead of "
     "reacting off it &mdash; as your sharpest tell between an S day and a "
     "refusal: it shows up in 2% of your S-day notes against 20% of your non-S "
     "notes, a 10x gap.",
     "<code>research/MORNING_REPORT.md</code> &sect;3, &ldquo;Chop is the "
     "discriminator&rdquo; (n=295 S-day notes, 453 non-S notes). From your own "
     "marks &mdash; not a sentence you've said this way."),
    ("GR5", "grading", "settled",
     "C is graded and logged for the record, but never surfaced as an alert and "
     "never traded &mdash; only S ever gets traded.",
     "&ldquo;i dont need physical alerts, its just to collect data. the priority "
     "is always S.&rdquo; &mdash; Austin, Q&amp;A batch 04, 2026-08-28."),
    ("GR6", "grading", "inferred",
     "AUGUR infers displacement is not a hard requirement for S but one of "
     "several substitutable signals &mdash; displacement, an OCR holding, a wick "
     "reclaim of the level, strong price action, or being early with an HTF read "
     "&mdash; because you have both demanded it flatly and graded S trades that "
     "had none.",
     "&ldquo;just always need that displacement for S trades&rdquo; (rule "
     "ballot, rule_03) against &ldquo;9:46 as candle forming above ORH, no "
     "displacement but 9:30 ocr wick confluence with pmh&rdquo; (NVDA "
     "2025-06-03, graded S) and two more S grades carrying no displacement "
     "&mdash; <code>research/g92_master_spec.md</code>, Contradictions &sect;2. "
     "n&asymp;20 cards across three homework sections. You have never been asked "
     "whether displacement should be one variable among several."),

    # --- Instrument and sizing ---
    ("IN1", "instrument", "settled",
     "All three instruments &mdash; options, shares through a prop firm, and "
     "futures &mdash; stay open; nothing has been narrowed to just one.",
     "&ldquo;Option one is fine... Index and futures is a good option too, so "
     "leave options open.&rdquo; &mdash; Austin, 2026-08-30."),
    ("IN2", "instrument", "settled",
     "Position size is meant to come from whichever prop firm's own drawdown "
     "rules you're trading under, not from a dollar figure you're personally "
     "comfortable with.",
     "&ldquo;the way i would decide risk per trade now is based on the prop firm "
     "im going to be using, read its rules and what makes sense for my strategy "
     "and profit goals.&rdquo; &mdash; Austin, 2026-08-29."),
    ("IN3", "instrument", "settled",
     "The near-term prop target is Vanquish Trader's $50k Advanced Options plan: "
     "a 10% profit target, a 5% end-of-day trailing drawdown, a 4-day minimum, "
     "and a 100% profit split once funded &mdash; the only fee-based evaluation "
     "found that permits options, and the engine is meant to fire separately for "
     "whichever firm you're under.",
     "<code>AUGUR.md</code>, &ldquo;Decided 2026-09-03&rdquo; and its Research "
     "section (verified against Vanquish's own pages; underlyings and same-day "
     "expiry unconfirmed); &ldquo;the trading bot would need to have its "
     "separate firing that works with the prop firm stocks&rdquo; &mdash; Austin, "
     "2026-09-03."),
    ("IN4", "instrument", "measured",
     "AUGUR infers a $1,000 account cannot actually run this in options: on real "
     "option prices, one contract is the whole sizing grid, and a typical stop "
     "cannot be bought at 1% of $1,000 &mdash; the arithmetic needs roughly "
     "$12,000 before one contract matches what a prop evaluation would allow you "
     "to risk.",
     "<code>research/MORNING_REPORT.md</code> &sect;5, &ldquo;The $1,000 "
     "question&rdquo; (priced against 276 real Alpaca 0DTE ATM option prints). "
     "Derived from real option prices &mdash; not something you've stated."),

    # --- What he has refused ---
    ("RF1", "refused", "settled",
     "The legacy A+/A/B/C/X engine grade ladder is dead &mdash; you've never used "
     "it and have said so more than once; only your own S/A/C/none ladder counts "
     "anywhere a number is reported.",
     "&ldquo;a+ shouldnt exist. a+ and b shouldnt exist if they do.&rdquo; "
     "&mdash; Austin, 2026-08-28 (&ldquo;the fifth time of asking,&rdquo; per "
     "<code>omen-rulebook.md</code>, 2026-08-29)."),
    ("RF2", "refused", "settled",
     "Nobody gets to refute your S marks &mdash; they're ground truth backed by "
     "real work, and a report may say the engine's own label disagrees with you, "
     "but never that your judgement was wrong or noisy.",
     "&ldquo;you cant refute my s marks they are important and hard work and "
     "stats have been backing them up.&rdquo; &mdash; Austin, 2026-08-28."),
    ("RF3", "refused", "settled",
     "A symbol-day you've already graded must never be shown to you again "
     "&mdash; even being served the repeat counts as wasting your time, whether "
     "or not you re-grade it.",
     "&ldquo;i never want to see stock repeats of stocks i have already graded, "
     "beacuse how is that worth my time?&rdquo; &mdash; Austin, 2026-08-29."),
    ("RF4", "refused", "settled",
     "A stop too tight to survive real spread and slippage is not a valid stop, "
     "no matter how good it makes the backtested R look &mdash; "
     "&ldquo;robot-tradable&rdquo; is a hard constraint, not a nice-to-have.",
     "&ldquo;i want trades that can realistically be done by a robot and where it "
     "wont get killed or destroyed by fills or too tight rr.&rdquo; &mdash; "
     "Austin, 2026-08-29."),
    ("RF5", "refused", "settled",
     "FVG and flag patterns stay computed in the code but never gate a trade and "
     "never get counted as one of your setups &mdash; you keep them visible "
     "without trading them.",
     "&ldquo;sure keep fvg and flag but they are not setups i trade and they "
     "dont do anything im sure.&rdquo; &mdash; Austin, 2026-08-29."),
    ("RF6", "refused", "settled",
     "You've refused to widen the graded set past QQQ, SPY and TSLA for now, and "
     "refused to re-open the 47 extra low-confidence rows from old chat mining "
     "just to grow the S-day count &mdash; not because they're wrong, just not "
     "the best use of your time right now.",
     "Q&amp;A batch01 defaults (&ldquo;no, that is OMEN 7&rdquo; / &ldquo;No. "
     "Gate on 154.&rdquo;) &mdash; Austin, 2026-08-23/24; "
     "<code>omen-blockers.md</code>, &ldquo;Already settled&rdquo; table."),
]

GROUP_LABEL = {
    "setups": "Setups",
    "levels": "Levels",
    "entry": "Entry",
    "stop": "Stop",
    "exits": "Target &amp; exits",
    "grading": "Grading",
    "instrument": "Instrument &amp; sizing",
    "refused": "What he has refused",
}

CONF_LABEL = {"settled": "settled", "measured": "measured", "inferred": "inferred"}


def main():
    cards, last_group = [], None
    total = len(STATEMENTS)
    n_settled = sum(1 for s in STATEMENTS if s[2] == "settled")
    n_measured = sum(1 for s in STATEMENTS if s[2] == "measured")
    n_inferred = sum(1 for s in STATEMENTS if s[2] == "inferred")

    for i, (sid, group, conf, statement, source) in enumerate(STATEMENTS, 1):
        if group != last_group:
            cards.append(
                '<p class="eyebrow" style="margin:26px 0 10px">%s</p>'
                % GROUP_LABEL[group])
            last_group = group

        conf_tag = ('<span class="tag%s">%s</span>'
                    % (" warn" if conf == "inferred" else "", CONF_LABEL[conf]))
        source_block = (
            '<div class="q" style="border-top:0;padding-bottom:0">'
            '<p class="hint" style="margin:0 0 8px"><b style="font-family:\'IBM Plex '
            'Mono\',monospace;font-size:10px;letter-spacing:.1em;text-transform:uppercase;'
            'color:var(--accent)">Source</b></p>'
            '<div style="border-left:3px solid var(--accent);padding:8px 0 8px 12px;'
            'font-size:13.5px;color:var(--ink-2)">%s</div></div>' % source)

        export = json.dumps({"group": group, "confidence": conf, "statement_id": sid})

        cards.append("".join([
            '<article class="card" data-cid="%s" data-done="0" data-export=\'%s\'>'
            % (sid, export.replace("'", "&#39;")),
            '<header><span class="idx">%02d/%02d</span>'
            '<span style="font-family:\'IBM Plex Serif\',Georgia,serif;font-size:17px;'
            'font-weight:600;flex:1 1 100%%;line-height:1.35">%s</span>'
            '<span class="tags">%s<span class="done-dot"></span></span></header>'
            % (i, total, statement, conf_tag),
            source_block,
            probe_page.question(
                "verdict", "Right, wrong, or partly?",
                "Tap one, then correct AUGUR below &mdash; the comment is the point, "
                "not the tap.",
                VERDICT_OPTS, multi=False, required=True,
                note_placeholder="Correct me — what's actually true"),
            "</article>",
        ]))

    foot = (
        "<h2>How this gets used</h2>"
        "<p>Every tap and every note saves in this page as you go. Hit <b>Export</b> at "
        "the top, then <b>Copy all</b>, and paste it into the chat &mdash; the export "
        "returns to <code>research/marks/</code> with no round trip.</p>"
        "<p>%d statements, %d settled (your own words, dated), %d measured (a number "
        "counted from your marks, not a sentence you said), %d inferred (AUGUR pieced "
        "this together across contradicting marks and has never asked you directly). "
        "The <b>inferred</b> ones are the ones most worth a wrong or partly tap.</p>"
        "<p>Full sourcing for every statement: "
        "<code>research/augur_understanding.md</code>.</p>"
        % (total, n_settled, n_measured, n_inferred))

    html = probe_page.shell(
        "AUGUR — does it understand your system?",
        "AUGUR &middot; onboarding",
        "AUGUR states your system back to you.",
        "%d statements, one per card, each with where it came from. Tap "
        "<b>right</b>, <b>wrong</b>, or <b>partly</b>, and write the correction "
        "&mdash; that comment is the whole point of this page, more than the tap "
        "is. About <strong>20&ndash;25 minutes</strong> for all of it, or do it in "
        "pieces; it saves as you go." % total,
        "".join(cards), foot, "augur-understanding")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%d statements, %d bytes)" % (OUT, total, len(html)))


if __name__ == "__main__":
    main()
