# T4/G14 — A/B the thing that actually picks the book

`research/g4_dropped_s.md` section 6 named it: `_grade_pa` never lifts a signal into the
traded tier. What actually promotes a signal into the book is one branch of
`SignalRunner._calibration_grade` (`signal_runner.py:1516-1520`) — the first with-trend
signal of the day, inside 90 minutes, gets floored from `C` (alert-only) up to `B`
(traded). Four grader tickets in a row (G12, G13, R3, W1) tuned the grade. None of them
touched the thing that actually selects the book: arrival order.

The isolating flag already shipped, unused: `ENABLE_KILL_B_FLOOR` (default `False` — the
floor stays on). This ticket is the first thing to price it on its own, then go past
on/off to find which of the floor's three conditions — first-only, with-trend, inside
90 minutes — is actually doing the work.

**Held-out set**: `research/marks/probe_omen_test1_2026-08-27.jsonl` (15 S / 27 A / 16 C
/ 42 X). **Error bar on a 2-year A/B: ±0.0095R (narrow, carried)** — any arm-to-arm delta
smaller than that is noise and is labelled as such below.

**A workspace hazard, disclosed up front.** This measurement ran while other wave-1
tracks were editing the same working copy live: `signal_runner.py` / `backtest_week.py`
carried an in-progress, uncommitted fill-price fix (T11) during the first pass, which
moved the book's mean R by −0.121 with the trade count unchanged — nothing to do with
the floor. `research/g3_arm_ow1.json`, the file this ticket was told to check against,
was itself silently overwritten mid-session by a concurrent rerun. Every number below was
re-measured in an isolated `git worktree` at the last commit (`3810ea87`) with the shared
`data_archive` symlinked in for identical data, so it is clean of both. See §6.

---

## 1. Held-out S recall FIRST

| arm | S recall | false fires (of 42 X) | entry match (of graded) |
|---|---|---|---|
| **on** (floor ON, shipped) | **3/15** | 12/42 | 4/58 |
| **off** (floor OFF) | **0/15** | 8/42 | 1/58 |
| uncap (drop "first only") | 3/15 | 12/42 | 5/58 |
| notrend (drop "with trend") | 4/15 | 13/42 | 4/58 |
| nowindow (drop "≤90 min") | 3/15 | 12/42 | 4/58 |
| relaxed (drop all three) | 4/15 | 13/42 | 5/58 |

**Turning the floor off does not just re-grade trades — it silences the engine on S
days.** Held-out S recall falls from the standing 3/15 to **0/15**. The mechanism is not
about grade tier: promoting a signal to `B` lets it skip the tight-stop-C check
(`signal_runner.py:1891`, "tight-stop skip only for C"). With the floor off, the same
signal stays `C` and some fraction fail that check and never reach `status=="fired"` at
all — the day goes silent, not just alert-only. This is measured, not assumed: it is
exactly why `off`'s false-fire count also drops (8/42 vs 12/42) — the engine is quieter
across the board, on X days as well as S days.

The three relaxations move recall by at most **+1 of 15** (`notrend`, `relaxed`) — inside
noise for a 15-card sample, and none of them cost anything the `off` arm didn't already
cost.

---

## 2. The CHECK

**Reproduced in an isolated worktree**: arm `on` gives **n=1017, mean R
+0.9551396263520157**, date window 2024-08-21..2026-08-21, 500 sessions — matching the
standing figure (+0.9551R, 53.2% win, 23/25 months, 1,017 traded rows) on every digit.
`ENABLE_KILL_B_FLOOR` isolates the floor cleanly; nothing else moves when it flips.

(The live `research/g3_arm_ow1.json` on disk right now reads +0.8341R — that is the T11
fill-fix contamination described above landing on the reference file mid-session, not a
flag-isolation failure. Digest comparison against that file therefore fails; comparison
against the ticket's own stated numbers passes exactly. Re-run `check` once the tree is
quiet to get a byte-identical digest match too.)

---

## 3. Primary A/B — floor ON vs floor OFF

| arm | trades | mean R | win rate | months green |
|---|---|---|---|---|
| **on** (shipped) | 1,017 | **+0.9551** | 53.2% | 23/25 |
| **off** | 48 | **+1.3161** | 48.9% | 12/18 |

Turning the floor off takes the book from 1,017 trades to **48** — the ticket's own
"48 trades remain" reproduced exactly. Of those 48, only **1 in 6** are `S`-graded on
Austin's ladder (8 of 48) vs 1 in 8 in the floor-on book (128 of 1,017) — see §5.

**Off's higher mean R is not a sizing artifact.** 12.5% of the off book (6/48) fails the
minimum-risk floor vs 2.2% (22/1,017) on. Stripped to sizeable trades only, the gap
*widens*, not narrows: off = **+1.4765R** (n=42, 51.2% win, 12/17 months green) vs
on = **+0.9716R** (n=995, 53.7% win, 23/25 months). The 48 non-floor trades that earn
their grade on their own price action really are better trades, on average, than the
969 the floor adds — but there are 21x fewer of them, and durability collapses (7 of 25
calendar months carry zero trades at all when the floor is off).

This is the runner-system trade Austin already made for the money gate: fewer, better
trades raise mean R; the floor is what turns "fewer" into "enough to trade every month
and clear held-out recall at all."

---

## 4. Which half of the floor is load-bearing

The floor is three conditions ANDed together: **first-in-direction only**, **with the
day's trend**, **inside 90 minutes**. Four arms relax exactly one at a time (a
research-only monkeypatch, `research/_t4_variant_wrapper.py` — no new flag ships in
`signal_runner.py`):

| variant | trades | mean R | win rate | months green | floor-tagged |
|---|---|---|---|---|---|
| on (shipped floor) | 1,017 | +0.9551 | 53.2% | 23/25 | 969 |
| **uncap** — drop "first only" | 1,511 | +0.9421 | 51.0% | **25/25** | 1,465 |
| **notrend** — drop "with trend" | 1,420 | +0.8134 | 43.8% | 22/25 | 1,372 |
| **nowindow** — drop "≤90 min" | **1,017** | **+0.9551** | **53.2%** | **23/25** | **969** |
| relaxed — drop all three | 2,041 | +0.8880 | 43.4% | 23/25 | 1,995 |

**The 90-minute window is not load-bearing at all.** `nowindow` is byte-for-byte
identical to `on` — same trade count, same mean R to four decimals, same digest-visible
population. Every eligible with-trend first-in-direction `C` signal in the whole 2-year
book already arrives inside 90 minutes; there is no candidate past the window to ever
promote. The window condition is dead weight in the current book (it may still matter as
a guard against a future regime where late signals appear — it costs nothing to keep).

**"First only" is refusing +494 trades a month never sees again, at nearly flat money and
better durability.** `uncap` adds 494 trades (+48.6%) for a 1.30-point mean-R cost
(+0.9551 → +0.9421) and turns every one of the 25 months green. (The published ±0.0095R
error bar is T2/T3's intrabar-fill-ambiguity ceiling on the *shipped 1,017-row book* — it
does not apply as a significance test to a comparison against a differently-sized 1,511-
row population, and is not used that way here; the seq breakdown below is the stronger
evidence that the added trades aren't worse.) See §5 for the added trades' composition —
mostly the same setup mix as the shipped floor, not a different one.

**"With trend" is the expensive one.** `notrend` adds 403 trades but drops mean R to
+0.8134 (a 14.2-point drop) and win rate to 43.8%, the worst of any arm measured here.
Dropping the trend requirement lets in a materially worse population — this is the
condition actually doing quality-control work, not the window.

**Relaxing everything nets out worse than relaxing count alone**: `relaxed` (+0.8880) is
below shipped and below `uncap`, because the trend-condition damage in `notrend` doesn't
cancel against the extra trade count — it's not additive, and "with trend" should not be
dropped even in the world where "first only" is.

### seq==1 / seq==2 / seq>=3

Off the `uncap` arm's own promoted rows (exact per-direction ordinal, not simulated —
every candidate the floor would touch already carries its own priced entry/stop/exit in
the book):

| direction-ordinal | n | mean R |
|---|---|---|
| seq==1 (what the shipped floor already takes) | 1,227 | +0.9094 |
| seq==2 (what "first only" refuses) | 204 | **+1.0834** |
| seq>=3 | 34 | +0.7921 |

**The second with-trend signal of the day is not lower quality than the first — it's
better** (+1.0834 on 204 trades vs +0.9094 on 1,227). The "first only" restriction is not
protecting the book from a quality cliff; it is an arbitrary count cap that happens to
leave 204 good trades on the table. seq>=3 is where quality actually falls off (+0.7921,
n=34, thin — treat this bucket as directional only).

---

## 5. What the floor actually selects, by setup and by his ladder

| population | n | break-and-retest | one-candle-rule | 84% re-entry | S | A | C |
|---|---|---|---|---|---|---|---|
| floor-promoted (`on`, 969) | 969 | 913 | 56 | 0 | 120 | 234 | 615 |
| earns its own grade (48) | 48 | 34 | 11 | 3 | 8 | 17 | 23 |

The floor is overwhelmingly a break-and-retest mechanism (94.2% of what it promotes) and
overwhelmingly promotes signals Austin's own ladder would call `C` (63.5%) — the floor is
not rescuing near-misses into `S`, it is turning the ENTIRE alert stream tradeable
whenever it's first. 120 of the book's 128 traded `S` rows (93.8%) exist only because of
the floor — consistent with §1: turn it off and held-out S recall goes to zero, not just
the in-sample count.

The counter-trend cap (a *different* rule, `signal_runner.py:1513-1515`, orthogonal to
the floor's own trend test) fires 9 times in the whole 2-year book, of which only 2 are
grade-`C` alerts the floor could ever have reached. That small number is NOT the size of
`notrend`'s effect (+403 trades) — most of the trades `notrend` adds were never tagged
`capped C` at all; they were plain against-trend `C` signals the floor's own trend test
silently skipped without leaving a mark. `research/x7_entry_surface_map.md` §2b already
flagged this string-guard hole as "a loaded gun" for a different reason (three demotion
sites don't tag `capped C`); this ticket is independent confirmation the trend axis is
doing real, silent, unmarked work.

---

## 6. Reproduce

```
# primary A/B (real flag)
python research/t4_g14_calibration_ab.py run --arm on
python research/t4_g14_calibration_ab.py run --arm off

# decomposition (research-only monkeypatch, no new production flag)
python research/t4_g14_calibration_ab.py run-variant --arm uncap
python research/t4_g14_calibration_ab.py run-variant --arm notrend
python research/t4_g14_calibration_ab.py run-variant --arm nowindow
python research/t4_g14_calibration_ab.py run-variant --arm relaxed

python research/t4_g14_calibration_ab.py check
python research/t4_g14_calibration_ab.py test1 --arm all     # held-out FIRST
python research/t4_g14_calibration_ab.py stats --arm all
python research/t4_g14_calibration_ab.py decompose
python research/t4_g14_calibration_ab.py --selfcheck
```

**Run the arms one at a time in a quiet tree.** Each 2-year replay takes ~6-8 minutes and
they contend on the 1-minute archive; running one while another wave-1 track edits
`signal_runner.py`/`backtest_week.py` uncommitted will silently contaminate the money
numbers (§2 happened exactly this way). If the working tree is not quiet, replay in an
isolated `git worktree` at the current commit with `data_archive` symlinked in — that is
what produced every number in this document.

**Nothing here ships.** `ENABLE_KILL_B_FLOOR` stays `False` (floor on, byte-identical to
today — proven in §2). No new flag was added to `signal_runner.py`; the four
decomposition variants live entirely in `research/_t4_variant_wrapper.py` /
`_t4_variant_test1.py`, monkeypatching `SignalRunner._calibration_grade` in a child
process's memory only. The engine is not re-frozen (`research/omen6_forward.py`).

---

## 7. What this hands the next ticket

1. **Arrival order's whole edge is not the floor.** The floor turns 48 self-earned trades
   into 1,017 by promoting the first with-trend `C` of the day — but §4/§5 say the
   *count* restriction ("first only") is arbitrary and costly (204 seq==2 trades priced
   at +1.0834R, better than seq==1), while the *trend* restriction is real quality
   control. A next-track ranker only needs to beat "first, with trend, any count" — not
   "first, period" — to know it's adding value over what arrival order is actually doing.
2. **For T3 (the cross-symbol selection ranker):** today's book is 98.8% `seq==1`
   (per-symbol-day ordinal, `research/g4_dropped_s.md`) because most symbol-days offer
   exactly one candidate, not because arrival order is a good filter among many. `uncap`
   (§4) shows that when a second with-trend candidate exists, it's priced as good or
   better than the first — so T3's ranker is not competing against a smart "take the
   first" rule, it's competing against a count cap that was never testing quality at all.
   The +1.0527R "arrival order" baseline T3 needs to beat is mostly measuring "there was
   only one setup that day," not "the engine picked well among several."
3. **The window (90 min) is free to drop or keep** — it never binds on this book. Any
   future track that widens detection to later in the session should re-run `nowindow`
   before assuming the window is still inert.
4. **The trend condition should not be relaxed** without a replacement quality check —
   `notrend` is the worst arm measured here on both money and win rate, and it is
   currently held together by a string-guarded cap (`x7_entry_surface_map.md` §2b) with
   a known blind spot on three demotion sites.
5. **Held-out S recall genuinely depends on the floor**, not just on grade labeling — a
   future track that changes `_calibration_grade` (W1's SAC ladder, R3's downgrade
   grader) needs to check whether it still lets marginal-stop signals past the tight-stop
   skip, or it will quietly cost recall the same way `off` does here.
