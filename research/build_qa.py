"""build_qa.py -- OMEN 6 ticket 07b: the Q&A queue as a phone page.

Every open question only Austin can answer, banked in one place with a recommended
default already written, so a tap is a complete answer and typing is optional.

Rebuilt 2026-08-23 after rule ballot batch 01 came back: four of the original
thirteen were answered by the ballot and are gone from here rather than re-asked,
and four new ones the ballot opened have taken their place. See
research/rule_ballot_batch01.jsonl.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import probe_page

OUT = os.path.join(HERE, "probes", "qa-queue.html")

DEFAULT_OPTS = [("default", "Take the default"), ("override", "Override — see my note")]

# (key, tier, heading, why, default_text, options, multi, placeholder)
Q = [
    ("capital", 1, "Six figures on what capital?",
     "Account size, risk per trade, shares or contracts. <code>$100k/yr on $52k at 1%</code> "
     "and <code>$100k/yr on $250k at 0.5%</code> are different engines and only one of them "
     "is reachable. Every dollar figure in the backtest scales off this one number.",
     "$52k account, 1% risk per trade, shares. The $52k is the only figure on record "
     "(omen-5.0 T4). Your ballot answer on stops puts max slippage at &minus;1.25R = "
     "$1,250, which is consistent with 1% of $52k being ~$520 &mdash; so if $1.25k is really "
     "1.25R, the account is closer to $100k. Worth correcting.",
     DEFAULT_OPTS, False, "Account size / risk % / anything about sizing"),

    ("slices", 1, "&ldquo;Consistent across all your elements&rdquo; — name the slices.",
     "You said expectancy has to hold across every angle, not be one good year in a suit. "
     "I need the actual cuts, because the durability gate is literally a loop over them.",
     "Every quarter positive, every pool positive, and no single symbol carrying more "
     "than 25% of total R.",
     DEFAULT_OPTS, False, "Other cuts that must hold: month? day-of-week? long vs short?"),

    ("decisive", 1, "How far above the benchmarks is &ldquo;decisive&rdquo;?",
     "55% win rate and $100k are the floor. How much daylight before it's real and not noise? "
     "Without this, a 55.4% result and a 68% result both read PASS.",
     "The 95% confidence interval on mean R sits entirely above zero, and win rate clears "
     "55% on the <i>lower</i> bound, not the point estimate.",
     DEFAULT_OPTS, False, None),

    ("winrate_basis", 1, "Is 55% measured before or after the scale-out ladder?",
     "<code>30/30/30/10</code> books a high win rate largely because tranche&nbsp;1 fills often. "
     "That number is not comparable to a flat-exit win rate, so the same &ldquo;55%&rdquo; "
     "means two different things.",
     "After the ladder — that's the system you'd actually trade — but reported beside the "
     "flat number every run so the inflation stays visible.",
     DEFAULT_OPTS, False, None),

    ("downgrade_vars", 1,
     "A = one downgrade, C = two. Which variables can downgrade?",
     "This is the one that turns grading into arithmetic. If S is a clean setup and each "
     "missing thing costs one grade, then the engine can <i>compute</i> the grade instead of "
     "guessing it — but only once the list of countable things exists. Tap everything that "
     "costs a grade when it's missing or wrong. Your ballot already ruled <b>HOD/LOD "
     "proximity</b> out, so it isn't on the list.",
     "No default — this list doesn't exist yet anywhere in the vault or the code.",
     [("no_displacement", "No displacement candle"),
      ("stale_retest", "Stale retest"),
      ("weak_level", "Weak / minor level"),
      ("no_confluence", "No BR+OCR confluence"),
      ("against_qqq", "Against QQQ trend"),
      ("low_volume", "Low volume"),
      ("late_session", "Late in the session"),
      ("thin_rr", "Thin R:R"),
      ("choppy", "Choppy structure into it"),
      ("no_htf", "No higher-timeframe thesis"),
      ("wide_stop", "Stop wider than normal"),
      ("gap_untested", "Gap left untested")],
     True, "Anything missing from this list, or which two of these usually pair to make a C"),

    ("prearm", 2, "The &ldquo;on watch&rdquo; mechanic — how should it actually work?",
     "Ballot q7: <i>&ldquo;we miss out on entries near HOD because they close too high for our "
     "entry risk to reward.&rdquo;</i> Ballot q8: <i>&ldquo;you want it to be probable of closing "
     "above that level. don't just enter when it taps a level.&rdquo;</i> Both point at the same "
     "missing state: the engine has no notion of <em>watching</em> a level and deciding "
     "mid-bar. Pick the shape and I'll build it.",
     "Two-bar arm: when price crosses a level intrabar, the engine goes ON WATCH. It enters "
     "on the <i>next</i> bar's open if the watch bar closed beyond the level with "
     "displacement. Stop still goes below the level, so an entry near HOD gets a wider stop "
     "and smaller size rather than being skipped for R:R.",
     [("two_bar", "Two-bar arm (the default above)"),
      ("close_then_pullback", "Wait for the close, then enter on the first pullback"),
      ("size_down", "Enter at the close anyway, size down to keep risk flat"),
      ("override", "None of these — see my note")],
     False, "How you actually do it when you're watching a level near HOD"),

    ("reclaim_tol", 2, "84% rule: how far from your original entry is &ldquo;too far&rdquo;?",
     "Ballot q12 settled that it's a re-entry at <b>the price you entered on</b>, not just the "
     "level. Ballot q13: <i>&ldquo;candle close as long as the close is not too far away from "
     "original entry.&rdquo;</i> That needs a number or it can't be coded.",
     "Within 0.25R of the original entry. Expressed in R rather than cents so it scales "
     "across TSLA and QQQ without a second rule.",
     [("quarter_r", "0.25R — the default"),
      ("half_r", "0.5R"),
      ("tenth", "A fixed 0.10% of price"),
      ("override", "Something else — see my note")],
     False, None),

    ("ladder_switch", 2, "Trend-vs-chop ladder switching — in scope, or OMEN 7?",
     "Ballot q4: <i>&ldquo;30 percent is when better chance stock runs, 50 for choppier. we must "
     "identify this.&rdquo;</i> But ballot q5 says stick with 30/30/30/10 for now. Those pull "
     "opposite ways. A regime detector is a whole subsystem and it would restart the frozen "
     "forward clock.",
     "Out of scope for OMEN 6. Ship 30/30/30/10 fixed, measure the edge, and make regime "
     "detection the first thing OMEN 7 does — when there's a trustworthy baseline to beat.",
     DEFAULT_OPTS, False, None),

    ("be_slippage", 2, "What does a break-even stop actually fill at?",
     "After ticket 02's fix the runner fills <i>exactly</i> at entry and literally cannot lose — "
     "a modelling artifact, not a market fact. It is why <code>+1.5148R</code> is a ceiling "
     "and not an expectation. You priced the <i>initial</i> stop at &minus;1.25R max; this is "
     "the break-even one.",
     "Haircut the BE fill by one tick against you. If TradeZella gives up real fills "
     "(ticket 16), replace the haircut with your measured slippage and never guess again.",
     [("one_tick", "One tick against me"),
      ("quarter_r", "0.25R against me — same as the initial-stop haircut"),
      ("zella", "Wait for TradeZella and measure it"),
      ("override", "Something else — see my note")],
     False, None),

    ("corpus_contract", 2, "What does &ldquo;the corpus validates a rule&rdquo; mean?",
     "You settled that the corpus is a validator, never a rule source. I still need the "
     "verdict vocabulary and what happens when it contradicts something you stated.",
     "<code>confirmed</code> / <code>contradicted</code> / <code>unmentioned</code>. A "
     "contradiction <b>flags, never blocks</b> — it's your strategy and you're the authority. "
     "Runs as one batch pass after the rulebook is rewritten, not per rule.",
     DEFAULT_OPTS, False, None),

    ("spy", 3, "Should SPY go back into the backtest universe?",
     "Dropped 2026-07-11 on a &ldquo;0-for-5&rdquo; note. Five trades is not a sample. SPY is "
     "fully archived, it sits in <code>INDEX_POOL</code>, and it is <b>30 of the 120 "
     "symbol-days you have ever graded</b> — so every recall number today ignores a quarter "
     "of your own judgements. One flag flips it everywhere.",
     "Yes, include it. Flip it before the next baseline so the number is computed once. "
     "Every published pre-ticket-14 figure moves, which is why it's your call and not mine.",
     DEFAULT_OPTS, False, None),

    ("extra_s_rows", 3, "Re-verify the 47 extra S-rows?",
     "Your S-day count is <b>154</b>, high confidence. It could be <b>201</b> if 47 S-tier rows "
     "from old chat-transcript mining were merged, but they carry no bar index and you already "
     "declined them once.",
     "No. Gate on 154. Re-opening 47 low-confidence rows to grow a sample that's already big "
     "enough is the wrong trade.",
     DEFAULT_OPTS, False, None),

    ("widen_graded", 3, "Should the graded set widen past QQQ / SPY / TSLA?",
     "Those three are <b>all you have ever graded</b>. The engine trades 29 symbols. A gate "
     "proven on three may not transfer — but widening is exactly the deck-hours this effort "
     "exists to cut.",
     "No, not for OMEN 6. Prove it on three, then test transfer as the first act of OMEN 7.",
     DEFAULT_OPTS, False, None),
]

TIER_NOTE = {
    1: "gates the destination itself",
    2: "unblocks one ticket each",
    3: "your call, but I can proceed either way",
}


def main():
    cards, last_tier = [], None
    total = len(Q)
    for i, (key, tier, heading, why, default, opts, multi, ph) in enumerate(Q, 1):
        if tier != last_tier:
            cards.append(
                '<p class="eyebrow" style="margin:26px 0 10px">Tier %d &middot; %s</p>'
                % (tier, TIER_NOTE[tier]))
            last_tier = tier
        rec = ('<div class="q" style="border-top:0;padding-bottom:0">'
               '<p class="hint" style="margin:0 0 8px">%s</p>'
               '<div style="border-left:3px solid var(--accent);padding:8px 0 8px 12px;'
               'font-size:14px;color:var(--ink)"><b style="font-family:\'IBM Plex Mono\','
               'monospace;font-size:10px;letter-spacing:.1em;text-transform:uppercase;'
               'color:var(--accent);display:block;margin-bottom:4px">Recommended</b>%s</div>'
               '</div>' % (why, default))
        cards.append("".join([
            '<article class="card" data-cid="%s" data-tier="%d" data-done="0">' % (key, tier),
            '<header><span class="idx">%02d/%02d</span>'
            '<span style="font-family:\'IBM Plex Serif\',Georgia,serif;font-size:17px;'
            'font-weight:600;flex:1 1 100%%;line-height:1.3">%s</span>'
            '<span class="tags"><span class="done-dot"></span></span></header>' % (i, total, heading),
            rec,
            probe_page.question("answer", "Your answer",
                                "Tap one. The note is optional — the tap is a complete answer."
                                if not multi else "Tap every one that counts.",
                                opts, multi=multi, note_placeholder=ph),
            "</article>",
        ]))

    foot = ("<h2>How this gets used</h2>"
            "<p>Every tap saves in this page as you make it. Hit <b>Export</b> at the top, "
            "then <b>Copy all</b>, and paste it into the chat. Anything you leave untapped "
            "stays open; anything you tap becomes a recorded decision that can be voided "
            "later.</p>"
            "<p>Four questions that were here on 2026-08-22 are gone: <b>rule ballot batch 01 "
            "answered them</b>. Four new ones the ballot opened have taken their place — "
            "the downgrade-variable list, the on-watch mechanic, the 84% reclaim tolerance, "
            "and whether ladder switching is OMEN 6's problem.</p>")

    html = probe_page.shell(
        "OMEN 6 Open Questions",
        "OMEN 6 &middot; the Q&amp;A queue",
        "Thirteen questions only you can answer.",
        "Each one ships with a recommended answer already written, so a single tap is a "
        "complete reply. Tier&nbsp;1 gates the destination — do those five and the map moves. "
        "About <strong>ten minutes</strong> for all of it.",
        "".join(cards), foot, "qa-queue")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%d questions, %d bytes)" % (OUT, total, len(html)))


if __name__ == "__main__":
    main()
