# T23 -- the instrument that could not record the answer, and the guard that keeps it fixed

Ticket: `research/p25_midcandle_entry.md` found `research/build_omen_test1.py:696`
writing `out.entry_p = closes[i]` unconditionally -- every graded entry read as an
at-close fill by construction, so 100% of the 56 entries measured came back "at
close" while 14 of the 58 note fields said otherwise in prose. The page could not
record the one thing Austin most wants measured.

## The fix was already live

Commit `cef00981` (T8, 2026-08-27, *"type the price"*) landed the fix before this
ticket started: the picked bar's close is the default, a typed price in the entry
question's note field overrides it, `bar_close_p` keeps the close so nothing that
compared against it breaks, and `entered_before_close` is set automatically when
the two differ -- the same escape hatch the stop field has had all along. It ships
in `research/probes/omen-test-2.html`, the deck this ticket's HARD RULE ("must
land before omen-test-2 is ever put in front of him") protects.

**The 100 graded rows in `research/marks/probe_omen_test1_2026-08-27.jsonl` were
not touched.** `research/build_omen_test1.py` was not re-run over Test 1; Test 1's
HTML is frozen as the record of what Austin was actually shown.

## The audit (item 2): every other field, checked for the same defect

THE RULE: a field that cannot differ from its default measures the page, not him.

A card exports two kinds of field:

1. **Direct capture** -- `grade`, `setup`, `eblock`/`emin` (via `entry_i`/`entry_t`),
   `why`, `comment`. These are read straight off whichever chip is pressed or
   whatever is typed, with no formula in between -- there is no default to get
   stuck at, so this class of bug cannot occur here by construction.
2. **Derived-with-override** -- `entry_p`, `stop_p`, and what's computed from them
   (`bar_close_p`, `entered_before_close`, `stop_src`, `side`). This is the only
   class where a formula can silently win over a typed override, which is exactly
   the shape of the original bug.

Read through `research/build_omen_test1.py`'s `mark()` function (the one place a
card's taps are read out of the DOM): `entry_p` and `stop_p` are the only two
fields with a default-formula-plus-override shape. **`entry_p` was the only one
with the override wired wrong** -- `stop_p` already had it right (the stop rail
has carried a typed-price escape hatch since Test 1 was first built). No other
field in `mark()` or `probeRow()` computes a value from a formula that a tap
cannot reach.

## The guard: `research/test_field_distinctness.py`

    python research/test_field_distinctness.py

Marks three cards with deliberately different taps and checks two different
invariants:

- **Direct-capture fields**: two different taps must produce two different
  recorded values (`grade`, `setup`, `entry_i`, `entry_t`, `comment`, `why`,
  `grade_std`).
- **Derived-with-override fields**: the real test is *within one row*, not
  across rows -- `closes[i]` differs by bar even under the old bug, so two rows
  on different bars would pass a naive cross-row distinctness check while the
  defect was still live. The test instead confirms an untouched card records the
  bar's close (`entry_p == bar_close_p`, `entered_before_close == False`) **and**
  a typed override actually changes what gets recorded (`entry_p` matches the
  typed price, differs from `bar_close_p`, flag flips to `True`) -- same shape
  for `stop_p`/`stop_src`.

Verified live: reverting the override wiring to the pre-T8 shape (`out.entry_p =
closes[i]` with the typed-override block removed) makes exactly one check fail --
`entry_p: typed override actually changes the recorded price` -- and every other
check still passes, confirming the guard is specific to the defect, not a general
tripwire that would mask a real regression under noise.

## What this changes

Nothing in the book or the corpus. `research/build_omen_test1.py` was not run
against Test 1's graded rows, and the fix predates this ticket. What T23 adds is
the audit (only `entry_p` had the defect; `stop_p` already didn't) and the
regression guard (`test_field_distinctness.py`), so the next homework instrument
inherits a check instead of a hope.

## Provenance

The fix: `research/build_omen_test1.py`, commit `cef00981` (T8). The guard:
`research/test_field_distinctness.py`, this commit.

## Check

    python research/test_field_distinctness.py
    -> all field-distinctness checks passed (3 rows)

Reintroducing the forced close (`out.entry_p = closes[i]` unconditional, override
block removed) turns exactly one check red:
`entry_p: typed override actually changes the recorded price`.
