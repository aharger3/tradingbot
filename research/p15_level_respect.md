# P15/P17 — `level_not_respected` wrong-side fix, and `STALE_BARS` ratification

Ballot: `research/rule_ballot_batch02.jsonl` (a1-a5, b11), 2026-08-27. Measured with
`research/p2_threshold_sweep.py` (`--selftest`, then a full run) against the same two rigs
as `research/p2_threshold_sweep.md`: Austin's 120 graded day-cards (1,250 signals) and the
2-year book (`research/bt2y_trades.json`, 45,175 signals / 1,016 traded).

**Result: STOP on `level_not_respected`, for the third time. P17 is committed and clean.**
Three different readings of ballot a2/a3, each a faithful attempt at what was asked, each
fails the money check in a different way. That is the finding: `level_not_respected`, as
specified, does not measure something Austin's money cares about — at least not through
the level the grader is actually handed (the trade's stop, used as a proxy for "the
level"). Nothing from any attempt is committed. `research/downgrade.py` and
`research/p2_threshold_sweep.py` are back at the P17-only committed state.

## P17 — done, committed, clean

`STALE_BARS` 15 -> 10, ratified by ballot b11. Committed `eff5a9e9`, `TASKS.md` row added.
`stale_retest` trips 3/1250 -> 8/1250 on cards (0.2% -> 0.6%), 98/45175 -> 263/45175 on
book (0.2% -> 0.6%) — near no-op, exactly as the ticket predicted.

## P15 — three attempts on `level_not_respected`, three failures

| attempt | test | window | trips (cards) | trips (book) | tripped mean R | clean mean R | delta | verdict |
|---|---|---|---:|---:|---:|---:|---:|---|
| baseline (committed) | `abs(close - level) <= eps` | fixed, `i-12..i` | 853/1250 (68.2%) | 28361/45175 (62.8%) | +0.996R (n=638) | +0.892R (n=378) | **+0.104R** | wrong sign |
| attempt 1 | close on wrong side, no eps | fixed, `i-12..i` (kept, per ticket) | 1057/1250 (84.6%) | 38866/45175 (86.0%) | +1.068R (n=724) | +0.683R (n=292) | **+0.385R** | wrong sign, **worse** |
| attempt 2 | close on wrong side, no eps | break-gated, `_break_bar+1..i` (per diagnosis: every other break-relative variable anchors on `_break_bar`; this one didn't) | 0/1250 (0.0%) | 13/45175 (0.03%) | +0.000R (n=**0**) | +0.957R (n=1016) | technically **not positive**, but **degenerate** | **dead** — never trips on a single traded signal |

Attempt 1 (P15 first pass, reported previously) kept the flat 12-bar window as literally
instructed; the window spans the pre-break approach, where a long's close sits below the
not-yet-broken level by construction. That is not chop, it's the setup, and testing every
close against "which side of the level" over that mixed window trips on almost everything
— trip rate went up, not down, and the sign got worse.

Attempt 2 (this pass) gated the window to `_break_bar() + 1` through `i`, matching every
other break-relative variable in the file (`no_displacement`, `stale_retest`,
`break_then_rejection`, `no_retest` all anchor on `_break_bar`) and Austin's own wording in
a3 ("has to hold the level **or candle period**" — a post-break condition). `_break_bar`
returns None -> `False`, same convention as a missing OCR in `ocr_not_respected`. Selftest
was green (`ok=400 bad=0 skipped=0`) — the harness and `downgrade.score` agree on what this
change actually computes. What it computes is: **almost nobody ever has two closes on the
wrong side of the level after the break, with no eps tolerance.** 13 signals in the entire
45,175-signal book trip it, and *zero* of the 1,016 traded signals do. The `%+.3fR` delta
formula divides by zero traded-tripped signals; there is no "tripped" population to have an
opinion about. The variable joins `break_then_rejection` as an effectively unreachable
branch — the report's own dead-variable detector groups them together automatically.

**Not attempted:** an eps-tolerant version of attempt 2 (a close on the wrong side by less
than eps still counts as "holding"). The coordinator's instruction was to report that
variant only if the strict delta came back positive — it didn't; it came back dead. Running
a fourth variant on the same variable, on my own initiative, is exactly the "tune around it"
the ticket says not to do. If Austin wants that fourth measurement it is a five-minute
re-run once someone decides it's worth taking.

## The rest of the sweep, attempt 2 vs baseline

| | S recall | false fire | day-level agreement | S money (n, win, mean R) | A mean R | C mean R | S>A>C |
|---|---|---|---|---|---|---|---|
| baseline | 12/28 | 30/61 | 21/58 | n=129, 66.7%, **+1.313R** | +1.010R | +0.865R | yes |
| attempt 2 (break-gated) | **18/28** | **46/61** | 23/58 | n=276, 59.8%, **+1.173R** | +0.980R | +0.784R | yes |

S recall improved (12/28 -> 18/28) but false fires got much worse (30/61 -> 46/61), moving
together in the same direction the report already calls out for `UNRESPECTED_COUNTER`:
"it is not re-sorting a subset, it is lifting the whole distribution at once." Removing a
downgrade that used to fire on 62-86% of the book knocks a point off nearly every signal's
tally at once, so a large share of the C bucket moves up to A/S — including days Austin
explicitly refused. S > A > C still holds on both mean R and win rate, but the S set's own
mean R and win rate both fell (66.7% -> 59.8%, +1.313R -> +1.173R) because it more than
doubled in size (129 -> 276) by absorbing signals that used to be graded A or C on this
variable alone.

## Status

- **P17 committed** (`eff5a9e9`), `TASKS.md` row added.
- **P15 not committed.** Three attempts, three distinct failure modes (wrong sign, worse
  wrong sign, dead variable). `research/downgrade.py` and `research/p2_threshold_sweep.py`
  are reverted to the P17-only committed state; `--selftest` is green against that state.
- `research/p2_threshold_sweep.md` is regenerated against the P17-only committed code (not
  against any P15 attempt) so the tracked report matches what's actually on `main`.
- Open question for Austin, now sharper than "should the window gate on the break": **is
  the trade's stop the right proxy for "the level" in this variable at all?** All three
  attempts used the same `level` argument (the stop) that every other downgrade uses;
  the existing report's finding #5 ("the level the grader is handed... is not the level
  Austin was looking at") was already suspicious before this, and three failed
  reformulations of the same test against that same level is more evidence for it, not
  less.
