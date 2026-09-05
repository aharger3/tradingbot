# g156 refuter #3 — F7 "S classifier v0" — REFUTED

**What is different now:** the F7 headline numbers reproduce byte for byte from the named
script, and that is precisely the problem — the script measures a post-hoc drop from a
frozen candidate stream, while the flag that shipped in `signal_runner.py` X-grades the
same row inside `_route`, which releases three separate suppression windows the script
cannot model. `$47.44/day` is not the shipped flag's `$/day`; it is an arm's `$/day` that
the shipped flag was never run against.

Lens assigned: reproduce from the script, byte for byte. Verdict **REFUTED** on three
independent grounds; the reproduction lens itself came back clean.

## 1. Reproduction — CLEAN, byte for byte

`python research/g154_rule_or-break-without-retest.py` (4.3 s, book
`research/bt2y_trades_retest_on.json`, 498 sessions, entry = signal bar CLOSE, stops via
`stop_rule.stop_fill_price`, size-gated on `omen_metrics._row_is_sizeable`, 1R = $1,000,
one-trade-a-day unit `omen_metrics.first_of_day_arm`):

```
candidates/day: 16.52
baseline $/day: 33.93  candidate $/day: 47.44  control $/day: 37.92
survivor: False  or_specificity_real: True
```

Regenerated `.json` and `.md` are **`diff`-identical to the committed copies**. Every
figure in the claim checks out: +$13.51/day whole book, H1 +$8.56, H2 +$18.46, precision
30.5% -> 30.5% (18/59 both arms), probe recall 44.1% -> 44.1%, bar-backed S recall
49.0% -> 48.7% (345 days), fires/day 1.000 both arms, candidates/day 16.52 unchanged.

Two sub-checks that could have broken it and did not:

- **Field identity.** The arm keys on the book's `level` (parsed from `t.reason` by
  `backtest_2y.LEVEL_RE`); the shipped gate keys on `sig["stop_level_name"]`. Different
  provenance, but they agree exactly: 21,479 rows match on `level in ("OR high","OR low")`
  and 21,479 on `level_name in ("not-his: OR high","not-his: OR low")`, intersection
  21,479 — zero disagreement in 127,152 rows.
- **Lookahead.** `downgrade.no_retest` -> `_break_bar` scans `range(i, i-30, -1)` and
  `_retest_bar` scans `range(after+1, i+1)`. Neither reads past bar `i`, and the book
  stamps `downgrades` at `dg.score(dbars, t.entry_idx, ...)`. **No lookahead.**

`python research/test_s_classifier.py` -> 4/4 OK, exit 0.
`python research/regression_gate.py && python research/test_runner_stop.py` -> both green.

## 2. Ground A — the measured arm is not the shipped gate (decisive)

The script drops a row from a **frozen** arrival stream and takes the next survivor. The
shipped code sets `sig["grade"] = TradeGrade.X.value`, and `X` is in `_SKIP_GRADES`
(`signal_runner.py:262`), so the row never reaches the accepted branch. Three suppression
mechanisms are released as a direct consequence:

| mechanism | where | what the X grade releases |
|---|---|---|
| dedupe window | `backtest_week.py:1400` — `claims = sig.get("status") == "fired"` | a non-fired row neither opens nor extends the window, so previously-suppressed same-idea candidates become rows |
| `NO_REPEAT_ENTRIES` | `signal_runner._route`, `self._fired_levels` | never registered, so a later entry on the same level is no longer skipped |
| `ENFORCE_NO_REPEAT` / `_fired_ideas` | same branch | same, keyed on the idea |

`CLAUDE.md` already names this exact failure and its cost: *"A selection arm cannot model
`backtest_week.DEDUPE_FIRES_ONLY` … Any C-cap gate in this engine adds candidates as well
as removing them."* The precedent is `g93`, which forecast $36/day from a selection arm;
the real matched book came back **$25/day** — a 31% over-estimate in the same optimistic
direction. Here the gate is stronger than a C-cap (X, not C), so the release is larger, and
**563 fired rows** would flip to X across the book.

The suppressed rows this would release are not merely unmeasured — they are **absent from
the book by construction**: the book's status vocabulary is `fired / halted / skipped_d /
skipped_tight_stop`, and 0 rows carry a repeat-entry or repeat-idea reason. The arm cannot
add back a row that was never written. **Only a matched book pair — same commit, same 498
sessions, `S_CLASSIFIER` the only difference — can price this flag, and it was not built.**

## 3. Ground B — the effect is 12 sessions and one day

Recomputed from the same book, same unit and size gate as the script:

| | value |
|---|---:|
| sessions in book | 498 |
| sessions whose pick actually changes | **12 (2.41%)** |
| total delta | +$6,729 (= exactly the $13.51/day claimed) |
| **top single day's share of the gain** | **50.1%** (2025-11-20, +$3,370) |
| top-3 days' share | 55.7% |
| H1 changed days / delta | 8 days / +$2,133 |
| H2 changed days / delta | **4 days** / +$4,596 |

H2's headline +$18.46/day — the half that is supposed to be the out-of-sample validation —
is four sessions, of which 2025-11-20 alone is 73%. On that day the baseline pick is
09:43 META OR-high (−$1,000); the rule drops it and 09:44 ORCL OR-low, and the pick lands
on 09:46 IWM PMH (+$2,370). That single substitution is half the entire claim. Note also
that under the shipped gate, dropping those two OR fires releases their level windows, so
a later META/ORCL entry could take the 09:46 slot instead — the one day the claim rests on
is the one most exposed to Ground A.

## 4. Ground C — multiplicity, and the split was used to select

Placebo, 1,000 trials, seed 7: drop a **random** 262 rows (the same 3.18% of the 8,227-row
stream the predicate drops) and rerun the arm.

| placebo test | result |
|---|---:|
| P(whole-book delta >= +$13.51/day) | **9.0%** |
| P(H1 > 0 **and** H2 > 0) — the criterion F7 used to pick this rule | **21.7%** |
| delta quantiles 5 / 50 / 95 | −$19.84 / −$0.61 / +$16.16 |

The both-halves-positive test is passed by a random drop of the same size **more than one
time in five**. F7 applied it across the candidate pool: with 25 candidates measured,
E[chance passes] ≈ 5.4 and FWER ≈ 99.8%. Finding one candidate positive in both halves is
the expected outcome of the search, not evidence about the rule.

Worse, the report states the selection rule in its own words: *"only one improves `$/day`
in **both halves**"*. The spec (F7) says forward-select on H1 and **validate** on H2. H2 was
read to choose the candidate, so H2's +$18.46 is the selection statistic, not a held-out
result. There is no untouched half left.

Two further facts about the pool: 10 of the 25 `g154_rule_*.json` files carry
`h1_delta_usd_day: null` and were never comparable on this axis at all; and
`stop-placement-routed` (H1 +$9.73, H2 +$16.27, `survivor: true`) beats this candidate on
H1 — the shipped rule was chosen from the **non-survivor** pool, i.e. it is a rule that
dodged the F6 three-refuter gate on a 0.3pp recall technicality and therefore carries
*weaker* evidentiary standing than the eight rules that were formally refuted.

## Verdict

**REFUTED.** The claim's arithmetic is exact and its fill is honest; what fails is the
inference. (1) The number was produced by an arm that structurally cannot model what the
shipped flag does to dedupe and no-repeat, the documented g93 failure mode. (2) The effect
is 12 of 498 sessions with half the gain in one substitution. (3) The both-halves test that
selected it is cleared by chance 21.7% of the time, was applied 25 times, and was applied
to the validation half.

What the report gets right and should be kept verbatim: **v0 does not clear the bar** —
precision is flat at 30.5% (18/59, identical numerator and denominator), the target is
39.5%, and bar-backed S recall dips 0.3pp. The honest zero stands. The `+$13.51/day` should
be struck from the summary, or restated as *"an unshipped selection arm's number on 12
sessions; the shipped flag's book was never built."*

Everything above: book `research/bt2y_trades_retest_on.json` (498 sessions), entry = signal
bar CLOSE, stops via `stop_rule.stop_fill_price`, size-gated, 1R = $1,000, one-trade-a-day
unit `omen_metrics.first_of_day_arm`, H1/H2 split 2025-09-01. Scripts:
`research/g154_rule_or-break-without-retest.py` (re-run unmodified) plus the day-change and
placebo recomputation quoted inline. No mark file read or written.
