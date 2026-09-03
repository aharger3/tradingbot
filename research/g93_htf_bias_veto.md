# OMEN 8.0 R4 -- HTF_BIAS_VETO: the note and the code disagreed, now fixed

## What the rulebook says

`omen-rulebook.md:855` (aharger3/obsidian-vault): *"`HTF_BIAS_VETO` shipped **ON** and
gated **47.0% of the two-year book** on a formula (SMA20-of-hourly) nobody wrote.
**Deleted 2026-08-28.** The value is still computed and reported, so it can be re-gated on
the day he defines the rule."* Austin's own words, same batch: *"we dont have any higher
timeframe bias yet youll need to tell me what that is then."*

## What actually shipped, before this row

The literal env var `HTF_BIAS_VETO` genuinely is gone -- `grep -c 'HTF_BIAS_VETO'
omen_bot.py` returned **0** before this row touched the file, on `main` and every branch,
same as `g4_dropped_s`/`OMEN-7.3.md` for R1 and R3: a real deletion the rulebook accurately
records. **But the veto BEHAVIOR the deleted flag named was never actually removed.**
`PriceActionAnalyzer.grade_trade` (`omen_bot.py`) has always carried this, unconditionally,
no flag anywhere:

```python
if htf_bias in ("bullish", "bearish"):
    aligned = (htf_bias == "bullish") == is_long
    if not aligned:
        return TradeGrade.D
```

`htf_bias` is not a dormant parameter -- it is populated with a real value on every run,
live and backtest both: `research/t8_two_year.py`'s `bias_from()` (a daily-close SMA20
proxy, matching the rulebook's "formula nobody wrote" description almost exactly) feeds
`backtest_week.simulate_day`, and `live_scanner.py:185` calls `tasty_feed.fetch_htf_bias`
for the live path. So this hard veto has been firing on every single backtest run in this
spec so far (R1, R2, R3 all called `bw.simulate_day` with a real `bias` argument) and on
every live scan. **The rulebook's "not a rule, so it is not a veto" ruling was violated the
whole time** -- not by the named flag, which really was deleted, but by an un-flagged
survivor of it.

## The fix

`HTF_GRADE_VETO` (`omen_bot.py`, default OFF via `os.getenv("HTF_GRADE_VETO", "0")`) gates
the hard D-return. Default OFF matches the rulebook exactly: `htf_bias` is still computed
and threaded through -- the softer "neutral caps A+/A to B" line is untouched, in scope or
out -- but an opposed bias no longer hard-vetoes to D. Turning `HTF_GRADE_VETO=1` on
restores the exact old behavior byte-for-byte, which is the "re-gate on the day he defines
the rule" path the rulebook promised and the code had actually foreclosed.

**Scope, deliberately narrow.** `signal_runner.HTF_OPPOSITION_VETO` ("hard", ungated) is a
*different* mechanism -- Austin's S/A/C tier clause 4, not the engine's A+/A/B/C/D grade --
and its own code comment already documents it as unsettled and awaiting a T8 A/B
("the ONE clause Austin has not settled"). That is a separate open question with its own
citation, not the deleted `HTF_BIAS_VETO`, and this row does not touch it.
`signal_runner.HTF_BIAS_GATE` (flag-gated, default OFF, caps to C rather than vetoing to D)
was already correctly dormant before this row and is untouched.

## What this changes going forward

R1/R2/R3's committed numbers are NOT retroactively altered -- they measured the code as it
shipped at the time, honestly, and stay as published. But **any future re-run of
`research/g90_fill_arms.py`, `g92_x_lift.py`, or `t8_two_year.py` from a fresh clone will
now produce different numbers than the ones already committed**, because the HTF-opposition
D-veto that was silently active in all of them is now off by default. That is a real,
disclosure-worthy side effect of fixing this row, not a bug -- flagged here so nobody is
surprised by a future diff.

## Independent adversarial review (2026-09-03)

A separate reviewer tried to refute six claims: that the veto was genuinely live on real
trades (not dormant) before this fix; that the fix is correctly scoped away from
`signal_runner.HTF_OPPOSITION_VETO`; that `HTF_GRADE_VETO=True` restores byte-identical old
behavior everywhere `grade_trade` is called; that nothing else silently depended on the old
unconditional veto; that the test fixtures are sound, not tautological; and that the
verify script's cross-repo check is genuine, not theater. **All six CONFIRMED**, with one
real gap found that doesn't affect verify's pass/fail but was worth fixing immediately: two
call sites in `signal_runner.py` (`_route`'s long and short B&R grade-promotion logic, ~4
occurrences) used `self.htf_bias != "bearish"`/`"bullish"` as a proxy for "this D was
HTF-caused, not PA-caused" -- a proxy that was only valid while the veto was unconditional.
With `HTF_GRADE_VETO` now off by default, a D is always PA-caused, and the stale proxy would
have silently withheld real B/C promotions whenever `htf_bias` happened to be opposed for
unrelated reasons. **Fixed in the same commit**: both guards now check
`omen_bot.HTF_GRADE_VETO and self.htf_bias == "..."` instead, so the exclusion only applies
when the veto is actually live. `signal_runner.py` now imports the `omen_bot` module object
(not just names) specifically so it sees runtime flips of `HTF_GRADE_VETO`, matching the
`bw.LADDER_MODE`/`sr.fill_price` monkeypatch pattern already used throughout `research/`.
The reviewer also flagged a test-coverage gap (short-side, `is_long=False`, was untested) --
added five short-side checks to `test_htf_grade_veto_default.py`, all passing. One minor
wording overstatement was noted (the code comment says `bias_from`/`fetch_htf_bias`
"always populate a real value"; in fact `bias_from` returns `None` during each symbol's
~19-day SMA warm-up and `fetch_htf_bias` can return `None` on a fetch failure) -- true
often enough that the substantive claim holds, but not literally "always."

## Verify

`research/g93_verify.py` checks, mechanically:

1. `grep -c 'HTF_BIAS_VETO' omen_bot.py` (now 1 -- a citation in the R4 comment block, not a
   symbol) equals the count `omen-rulebook.md` explicitly states.
2. `python3 test_htf_grade_veto_default.py` exits 0 -- the shipped default (`HTF_GRADE_VETO`
   reads `False`), the veto's absence at that default, and its restoration when explicitly
   turned on, all asserted directly against `PriceActionAnalyzer.grade_trade`.
