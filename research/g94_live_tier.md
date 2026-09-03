# OMEN 8.0 R5 -- the live promotion gate was still the retired ladder, now it is S

`2024-08-12` to `2026-08-11`, 29 symbols (MAJOR_15, INDEX_POOL, OTHER_POOL), **11,923
symbol-days**. `backtest_week.simulate_day` at the committed omen-5.0 defaults
(`STOP_ON_CLOSE=1`, `LADDER_MODE="B"`), replayed by `research/g94_live_tier.py`. Every
signal `SignalRunner._route` saw is captured with its engine `grade`, its shipped
`austin_tier` (computed by `compute_austin_tier` inside `_route` -- not reconstructed) and
the timestamp of the bar it fired on. **135,533 signals routed, 10,138 of them ACCEPTED**
-- the accepted set is what the live scanner sees, because `live_scanner` calls
`runner.detect_signals()`, which returns only what `_route` appended. Those 10,138 are
replayed per day, universe-wide, in timestamp order, through `live_scanner._emit_signal`'s
pre-`_tier` path (the 20-minute per symbol+direction cooldown, `WATCH_DAILY_CAP`,
`session.day_ended()`), with only the gate swapped underneath. `signal_runner.py`,
`omen_bot.py` and `backtest_week.py` are untouched; the two capture hooks are installed and
restored in-process, R1/R3 house style.

## The finding, before the numbers

**The gate was gating on the wrong classification system.** `live_scanner._tier()` promoted
a signal to TRADE (sized, paper-booked, counted against the daily governor) when

```python
if grade not in ("A+", "A") or ts[:5] < TRADE_FLOOR:
    return "WATCH"
```

`grade` is `PriceActionAnalyzer.grade_trade`'s **A+/A/B/C/D candle-shape ladder**. Austin's
own scheme is **S/A/C**, computed by `signal_runner.compute_austin_tier` from four clauses
that have nothing to do with candle shape (setup eligibility, bar-extreme fill quality,
freshness of the idea, HTF opposition). They are different classifications of different
things, and `signal_runner.py` says so outright at the top of the tier block: *"there is no
such mapping, and none is invented here."*

His trading set was settled on **2026-08-24** -- `Projects/omen-blockers.md`, "Already
settled -- do not re-ask": **`trading set | S only`**. Every other consumer of the tier
already implements that (`rank_s_plus`, `mark_s_plus`, `t8_two_year`'s book all filter
`austin_tier == "S"` before doing anything). The live path was the last place still gating
on the retired ladder. **So this is exactly the "leftover from the retired A+/B ladder" the
row asks about, and it is not intentional** -- there is no comment, flag, A/B or ticket
anywhere defending an A+/A live gate as a deliberate choice under the S/A/C scheme; the
comment block above `_tier` cites a 30-day sim from 2026-07-07, a month before
`compute_austin_tier` existed at all (omen-3.9 T4, 2026-08-09) and seven weeks before he
settled the trading set.

## The fix

```python
def _tier(runner: SignalRunner, sig: dict, ts: str) -> str:
    s = runner.session
    if getattr(sig["signal_type"], "value", "") == "reentry_84_rule":
        return "TRADE" if s.consecutive_losses < 2 else "WATCH"
    if sig.get("austin_tier") != "S" or ts[:5] < TRADE_FLOOR:
        return "WATCH"
    return "TRADE" if s.signals_today == 0 and s.consecutive_losses < 2 else "WATCH"
```

One clause changed. `grade` is gone from the signature and the call site as well as the
body, so a future edit cannot quietly re-introduce it without failing
`test_live_tier_s_gate.py` check (1).

### Every piece of the old gate, kept or changed, with the reason

| piece | verdict | why |
|---|---|---|
| `grade not in ("A+","A")` | **REPLACED** by `austin_tier != "S"` | classification, and the retired one. This is the row. |
| `ts[:5] < TRADE_FLOOR` (09:40) | **KEPT** | a time-of-day rule, not a grade rule. Sourced: 30d sim 2026-07-07, first-A+/A-after-09:40 12tr 58% +$10.8k vs first-B+-anytime 20tr 25% −$6k; the 09:30-09:40 chop is what the governor exists to skip. Costs **3 promotions in two years** (254 vs 257 with it removed) -- it barely binds even now. |
| `signals_today == 0` | **KEPT** | "quality over quantity, one trade and done" (Austin, 2026-07-07). An operational cap on how often we act, orthogonal to which signals count. |
| `consecutive_losses < 2` | **KEPT** | the session loss halt (`config.yaml consecutive_loss_halt`, `TradingSession.day_ended`). Same. |
| the 84% re-entry exemption | **KEPT, UNCHANGED** | see below. |
| missing / `None` `austin_tier` | **NEW, fail-closed** | see below. |

### The 84% re-entry: deliberately left alone

The exemption branch never referenced the ladder, so there is nothing in it to migrate --
the row's premise ("classification-scheme artifact vs operational safeguard") puts it
squarely on the operational side. Three further reasons, and one number:

1. It is a *separately sourced* Austin rule with its own A/B (Lesson 6 canonical, 2026-07-06:
   the B&R-only arm was the difference between −$2k and +$450 on 30 days), and it is already
   carved out of `ENFORCE_NO_REPEAT` and `NO_REPEAT_ENTRIES` in `signal_runner._route` for
   the same reason -- *"it IS by definition the sanctioned second bite at the same idea."*
2. It cannot be a back door for non-S ideas. `armed_84` is only ever populated by a
   **stop-out of a trade that already passed this gate** (`live_scanner.scan_once`, paper
   feedback path), so the idea behind a re-entry was S when it was taken.
3. `compute_austin_tier` auto-passes clauses 2 and 3 for a re-entry anyway (`bar_extreme_veto`
   returns False unconditionally for `REENTRY_84_RULE`; `fresh` is forced True). The only
   ways a re-entry is not S are the session-extreme veto, the mesh veto, and HTF opposition
   -- i.e. S-gating it would mostly re-litigate clause 4, the one clause Austin has **not**
   settled (`HTF_OPPOSITION_VETO`, still parked awaiting a T8 A/B).

**And it is worth 3 promotions in two years.** The `new_reentryS` arm below -- the new gate
with the re-entry *also* required to be S -- promotes 251 instead of 254, and hits the
identical 8 of Austin's S symbol-days. It drops all three re-entries in the accepted set
(two tier C, one tier A). So this judgment call is real but tiny, and if Austin wants it
S-gated the change is one clause and costs nothing measurable. **Also worth knowing: this
path is unreachable in a signal-only production run at all** -- `armed_84` is only filled
from `paper.mark`'s stop-out events, which require `--paper`. Live signal-only, the 84%
branch never fires.

### Fail-closed on a missing tier

`sig.get("austin_tier") != "S"` means a signal with no tier -- a dict from another producer,
or `signal_runner.AUSTIN_TIER_ENABLED` turned off -- can never promote; it posts as a WATCH
ding instead. That is the safe direction for a real-money gate, and it is asserted by the
test. **The disclosure that goes with it: `AUSTIN_TIER_ENABLED = False` now silently disarms
live trading** rather than reverting to the old behaviour. Nothing in the repo sets it False
today and it is a module constant, not an env var, so this is a note for whoever ever flips
it, not a live hazard.

## Result -- promotions over the sample

Every arm is scored on the same 10,138 accepted signals, with the same cooldown, watch cap
and daily governor; only `_tier` differs. `consecutive_losses` is held at 0 throughout,
because live it is only ever incremented from `--paper` mode, so a signal-only production
run never increments it -- that is the shipped behaviour, and it is identical across arms.

| arm | promotions | trade-days | of Austin's 118 S symbol-days |
|---|---:|---:|---:|
| `aplus_only` (the gate the *vault* describes) | 18 | 18 | 2 |
| **`old`** (the gate this repo actually shipped) | **37** | 34 | **3** |
| **`new`** (this row) | **254** | 253 | **8** |
| `new_notC` (new + "engine C is alert-only") | 218 | 217 | 8 |
| `new_reentryS` (new + 84% re-entry S-gated) | 251 | 251 | 8 |
| `new_nofloor` (new − the 09:40 floor) | 257 | 256 | 8 |

**The new gate promotes 6.9x more than the old one, and what it promotes is finally the
thing the system exists to select for.** Composition of the promotions:

| | `old` (37) | `new` (254) |
|---|---|---|
| by engine grade | `{A: 22, A+: 15}` | `{B: 201, C: 44, A: 6, A+: 3}` |
| by `austin_tier` | `{A: 16, C: 12, S: 9}` | `{S: 251, C: 2, A: 1}` |
| non-re-entry, by tier | `{A: 15, C: 10, S: 9}` | `{S: 251}` |
| by setup | `{B&R: 28, OCR: 6, 84%: 3}` | `{B&R: 226, OCR: 25, 84%: 3}` |

**Read the `old` row: 25 of its 34 non-re-entry promotions were tier A or C** -- signals
Austin's own settled rule says he does not trade. The old gate was not merely too tight, it
was aimed somewhere else: it traded 9 S signals in two years and 25 non-S ones. Under the
new gate every non-re-entry promotion is S by construction, and the 3 non-S promotions that
remain are exactly the three exempt 84% re-entries.

**Does the new gate recover the "zero entries on his S days" problem the row cites? Partly
and measurably: 3 of 118 S symbol-days -> 8 of 118.** The days are named so they can be
checked by hand:

- `old` hits `MARA 2026-07-09`, `TSLA 2025-11-21`, `TSLA 2026-01-14`.
- `new` hits `AAPL 2025-01-10`, `MSFT 2024-12-02`, `MU 2025-11-07`, `MU 2026-02-09`,
  `NVDA 2024-12-16`, `QQQ 2024-08-23`, `TSLA 2025-11-21`, `TSM 2026-02-23`.

Note the sets are **not nested**: `new` picks up six S symbol-days `old` missed and loses two
(`MARA 2026-07-09`, `TSLA 2026-01-14`) that `old` reached with an A+/A-graded signal Austin's
tier calls A or C. That is the correct behaviour under "S only" -- those were promotions the
settled rule says should not have happened -- but it should not be reported as a pure gain.

**8 of 118 is a lever moved, not a gate cleared.** The recall gate is 90%. This row moves the
live path from 2.5% to 6.8% of his S symbol-days, which is the same order as R3's held-out
6.6% -> 8.2%. Both rows keep hitting the same ceiling for the same reason, stated in the
adversarial section below.

## Adversarial pre-check -- does anything else silently block promotion?

The row's own required check, run by the implementer before handing off (an independent
reviewer will re-run it). Everything from `runner.detect_signals()` to the paper book was
read line by line. **Two real findings, one of them large.**

### 1. The retired ladder still gates the CANDIDATE POOL, upstream of `_tier` (large)

`signal_runner._route` refuses any signal whose engine grade is in `_SKIP_GRADES = ("X","D")`
before it is ever returned from `detect_signals()`. So `_tier` never sees it, whatever its
tier. Over this sample:

**8,775 signals were tier S. 8,329 of them -- 94.9% -- were refused by `_route` before the
live path could see them: 8,181 as engine-X/D, 140 on the tight-stop skip, 4 as a retired
level, 4 as a repeat entry. Only 446 tier-S signals, 5.1%, ever reached the live promotion
gate at all.**

That is R3's problem, on this sample, in the live path's own terms (the lost source's
"7,219 of 7,485" and this measurement's 8,181 of 8,775 are the same order, which is mild
independent corroboration of a figure neither of us can reproduce). **It is not fixed by this
row and it is not in this row's scope** -- R3 already measured the targeted regrade that
addresses it and landed at 1.62x the book for +1.6 points of held-out recall. But it is the
honest answer to "why is S-day recall still only 8/118 after fixing the gate": the gate was
the smaller of the two ladder leftovers on the live path, and the bigger one is a different
row. **Anyone reading this report as "the live bot now trades Austin's S set" should read
that sentence again: it trades the 5% of his S set the ladder did not throw away first.**

### 2. The 20-minute alert cooldown consumes its slot on WATCH dings (moderate)

`_cooled_down` runs **before** `_tier` in `_emit_signal` and is stateful per
(symbol, direction), so a WATCH ding at 09:35 can suppress a TRADE-worthy S at 09:50 on the
same symbol and side. Over the sample it suppresses **1,944 signals before they reach the
gate, 92 of them tier S, of which 39 were post-floor on a day that had not yet traded** --
i.e. 39 signals that would otherwise have promoted. Net effect on the book: **254 promotions
with the cooldown vs 279 without, 253 trade-days vs 278.** This is a legitimate anti-spam
rule with a real source (2026-07-06: GOOGL fired 4 alerts in 9 minutes) and it is orthogonal
to classification, so this row does not touch it -- but "the cooldown is spent by alerts and
then denies trades" is a design question worth a ticket, not a fact anyone had written down.

### 3-8. Checked and clean, or clean-but-worth-knowing

- **`WATCH_DAILY_CAP = 5`** only ever drops WATCH dings; the `if alert_only:` block a TRADE
  takes is not entered. Cannot block a promotion. Verified in the replay: 2,493 WATCH dings are
  posted under the new gate and the cap changes no promotion count.
- **`MAX_TRADES_PER_DAY = 3` / `session.day_ended()`** is looser than `signals_today == 0`
  inside `_tier`, so it is non-binding for non-re-entry promotions. It can only bind via
  re-entries, which is what it is for.
- **`build_options_plan`'s `try/except ValueError`** raises only on a wrong-sided stop
  (`stop >= entry` on a call) -- a degenerate signal, not a quality veto -- and returns False
  *without* incrementing `signals_today`, so a sizing failure does not burn the day. Not a
  hidden gate.
- **Zero-contract sizing was specifically checked** because the new gate promotes engine-C
  signals for the first time and `contracts = int(max_loss // per_contract_risk)` can floor to
  0. Re-priced all 254 promotions through `options_sizer`'s fallback premium model:
  **0 promotions size to zero contracts** under either gate. (Caveat: the live path prefers a
  real Tastytrade quote, so this is the estimate arm, not a proof for every real quote.)
- **`seen_signal_keys`**, the regime filter, `entries_ok` (news halt / `ENTRY_CUTOFF`) and the
  `len(candles) < 5` guard are all upstream, gate-independent and identical across arms.
- **`if sig["entry"] == sig["stop"]: return False`**, a degenerate-signal guard immediately
  inside `_emit_signal`, before `_tier`. Zero of 10,138 accepted rows have `entry == stop`
  on this sample, so it changes nothing here, but it is a real early-exit an adversarial pass
  found this report's first pass omitted.
- **`STOP_AFTER_WIN`** halts the whole day after the first recorded win, but defaults off and
  is only ever set from the `--paper` book-keeping path -- unreachable in a signal-only run,
  same as the 84% re-entry branch above. Also omitted from the first pass, also non-binding.
- **`_emit_futures_signal`** returns before `_tier` is reached and still uses `grade == "C"`
  for alert-only. That is a second, separate live promotion rule for the futures path, still
  expressed in the retired ladder. **It is out of this row's scope and it is still stale.**
  Flagged, not fixed -- it needs its own decision about whether the futures path trades S too.

### A blocker on real-money deployment, not just a note

**Position sizing still keys off the retired ladder, and this row's own gate change is what
makes that bite.** `_emit_signal` computes `size_pct = GRADE_SIZE_PCT.get(grade, 0.6)` --
`{A+: 1.0, A: 0.8, B: 0.6, C: 0.4}`. Before this row, the live domain of `grade` was `{A+,
A}` only -- every trade risked 80-100% of 1R, and the 0.4/0.6 buckets were dead code on the
live path. After this row, the domain is every grade a tier-S signal can carry, and the raw
lookup over the 254 promotions is **`{0.4: 44, 0.6: 201, 0.8: 6, 1.0: 3}`** -- as actually
shipped, three of those are re-entries at 2x size, so the real distribution is `{0.4: 44,
0.6: 201, 0.8: 3, 1.0: 3, 1.6: 3}`. **245 of the 251 non-re-entry S promotions would risk
$400-$600 against a settled 1R of $1,000, and 3 re-entries would risk $1,600 -- above 1R.**
This is a real, this-row-created side effect on real-money sizing, not a pre-existing one:
96% of promotions now land on grade buckets the live gate could never previously reach.
Nothing is blocked and nothing is broken in the code -- `Tier: S  Grade: C` prints side by
side and `austin_tier` is now logged, so the mismatch is visible on every alert rather than
silent -- and retuning `GRADE_SIZE_PCT` or inventing a tier-keyed size map here would mean
shipping an unsourced constant onto a money path with no measurement behind it, exactly what
R6 exists to do properly. So this row correctly does not fix it. But it should be read as
**a blocker on running this live with real money, not a nice-to-have for R6** -- the shipped
bot's dollar P&L would run roughly half the R-figures the rest of this repo publishes until
R6 lands. Paper/signal-only is unaffected; this only matters the day `--live` is real.

## Independent adversarial review (2026-09-03)

A separate reviewer tried to refute six claims: that `sig["austin_tier"]` is reliably
present on every live-path signal (not sometimes stale or missing); that the promotion
counts (37 -> 254, and specifically that 25 of the old gate's 34 non-re-entry promotions
were tier A or C) are real and reproducible; that the 84%-reentry exemption is correctly
left untouched; that the adversarial pre-check above is complete; the sizing-mismatch
finding; and regression safety. **All six CONFIRMED, no code bug found.** The reviewer
independently re-simulated one full day from raw bars (`TSM 2026-02-23`) end to end, pulled
and printed all 25 of the disputed A/C promotions by hand, and mutation-tested
`test_live_tier_s_gate.py` by reverting the fix (test fails, as it should) and by making the
gate fail-open instead of fail-closed (also fails, as it should) -- restoring the working
tree bit-identically afterward.

Three prose imprecisions were found and corrected in this report (no numbers changed): "the
two re-entries it drops" corrected to three (two tier C, one tier A); the sizing section's
"245 of 254 S-tier trades" corrected to 245 of the 251 non-re-entry S promotions, and the
distribution corrected to include three re-entries at 1.6x size (`{0.4: 44, 0.6: 201, 0.8:
3, 1.0: 3, 1.6: 3}`, not the flatter pre-doubling lookup). Two additional non-binding gates
the first pass missed (`entry == stop`, `STOP_AFTER_WIN`) are now listed in the pre-check
above -- both checked and confirmed to change nothing on this sample. The reviewer's one
substantive disagreement, adopted here: the sizing mismatch should be framed as **a blocker
on real-money deployment**, not a note for later, since this row's own gate change is what
exposed it (the live `grade` domain was `{A+, A}`, both >=0.8x, before this row; it is now
every grade a tier-S signal can carry). That framing is now in the section above.

## What could not be reconstructed

The row's three citations are all unreachable from this repo, the same situation R1
(`research/g90_fill_arms.md`) and R3 (`research/g92_x_lift.md`) documented for their own
sources -- consistent with `omen-blockers.md`'s note that the 2026-08-30 work happened on a
working copy that was never pushed.

1. **`live_scanner.py:546` is not the gate.** Line 546 today is inside an unrelated
   `except ValueError` block in `_emit_signal`. The gate is `_tier()`, ~40 lines earlier. The
   citation is stale, not wrong about *what* the gate did.
2. **The committed gate was never `grade == "A+"`.** The vault renders it as
   `if grade != "A+" or ts[:5] < TRADE_FLOOR` (`omen-next-session.md:43`,
   `.scratch/omen-6/map.md:232`). This repo has `grade not in ("A+", "A")` and always has:
   `git log --oneline -- live_scanner.py` returns exactly one commit, `998fbfec`, the initial
   import, and `git log -S` finds no earlier form on any branch. So the vault is describing a
   variant that does not exist here. **The `aplus_only` arm above prices the vault's gate
   anyway, for comparability: 18 promotions, not 2.**
3. **45,193, "fires twice", and "zero on his S days" are not reproducible and were not aimed
   at.** `OMEN-7.3.md`, the source `omen-blockers.md:102` cites for all three, is nowhere in
   the tree on any branch. The count of signals in this replay is 135,533 routed / 10,138
   accepted, so 45,193 does not correspond to either quantity at this configuration and no
   attempt was made to reverse-engineer a definition that would produce it. **Read the row's
   verify structurally -- "the count of promotions over the sample is reported" -- against
   this report's own sample, which is reproducible: `python3 research/g94_live_tier.py`.**

Two further gaps worth naming. (a) Austin's S **symbol-days** (118, from
`research/austin_marks_v7.jsonl`) are the denominator here; R3's headline denominator is 130
marked S **entries** split into DEV/HELD, and the vault's arm tables are over 15 days. Three
different objects -- the percentages are not comparable across reports. (b) This row's
recall figures are **not** split into DEV/HELD-OUT, because nothing here was tuned: the gate
is a settled rule transcribed into code, with no parameter chosen against the marks. If a
reviewer wants a held-out read, the same script produces it by filtering `s_symdays_hit` on
`day >= 2025-09-01`.

## Verify

`research/g94_verify.py` checks, mechanically:

1. `live_scanner._tier`'s **parsed AST** -- not a grep, so the docstring and the comment
   block are free to discuss the retired ladder while the code may not use it: no `grade`
   parameter, no `grade` name or `"grade"` subscript in the executable body, no A+/B/D/X
   ladder letters, and `"austin_tier"` present.
2. `_emit_signal` calls that gate with the new three-argument signature.
3. `python3 test_live_tier_s_gate.py` exits 0 (26 checks, including the behaviour that
   actually changed: `austin_tier` A or C at engine grade `A+` no longer promotes).
4. `research/g94_live_tier.md` states the sample size and both promotion counts, and those
   agree with `research/g94_live_tier_summary.json` -- the artifact the measurement script
   actually wrote -- and the two counts differ, which would fail if the rule change were a
   no-op.

## Verdict

**plain:** the live bot decided what to actually trade using an old grading system Austin
retired -- one that scores the shape of a candle -- instead of his own S/A/C rule, so over
two years it would have taken 37 trades of which only 9 were things he says he trades; now
it takes 254, all of them his S trades, and it lands on 8 of his own S days instead of 3.
The bigger problem is upstream and untouched: 93% of the S signals never reach this gate at
all because the same old grading system throws them away first.
