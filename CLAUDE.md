# tradingbot — OMEN

**New here? Read `SWARM.md` first** — the base-hash rule, the done rule, and the
never-lose-a-mark rule, in one page. This file is the detail underneath it.

Intraday signal engine. Break-and-retest / one-candle-rule setups on the 09:30–11:00 window.
Repo `aharger3/tradingbot`, working copy `C:\Users\aharg\Desktop\Projects\tradingbot`.

verify: python research/regression_gate.py && python research/test_runner_stop.py

---

# THE LANE — read this before starting anything (set 2026-08-30)

**One lane at a time. Nothing else gets worked on until the lane closes.**

## What we are building, in his words

> *"S trades are something — if I see it, I trade it every time. But obviously too many trades is
> bad. So the goal is S trade accuracy be good, backtest numbers will continue to go up, and engine
> is better at identifying the 1-3 S setups to take each day."* — Austin, 2026-08-30

**This is a classifier, not a ranker.** Do not build anything that picks the best of the day's
candidates, scores them against each other, or asks him which of two dots was better. He does not
work that way and asking him to is wasting the only scarce input this project has.

The target: **fire 1–3 times a day, and be right about them.**

## Where the project actually stands

| honest fill, one trade a day | $/day | win | green months |
|---|---:|---:|---:|
| the engine's first setup of the day | **$28** | 45.5% | 11/25 |
| the same day's best setup (oracle ceiling) | **$2,948** | 99.6% | **25/25** |
| a coin flip among the day's setups | −$25 | | |
| **his bar** | **$397** | | |

The oracle row is **not a plan** — it is proof the setups are there, every month, in the book we
already have. The engine surfaces ~18.6 candidates a day and he takes 1–3. It currently trades a
day he refused **62 times out of every 100** it trades (precision 39.5%). That gap is the project.

`research/g86_honest_ceiling.py` prints the table. Run it rather than quoting it.

## Why every dollar figure before 2026-08-30 was wrong

The engine filled at the level even when the level sat **outside the bar** — a price that did not
exist. Only **105 of 4,508 trades** were obtainable at the book's own price. That is where
"$721/day, 66.7% win, +0.8R" came from, and it is why the honest rebuild reads $28/day. The number
did not get worse; the ruler got honest. **Kill any figure that does not name its fill.**

## The three things his own marks say are broken

From `research/marks/probe_g84_all_in_one_2026-08-30.jsonl`, 2026-08-30:

1. **Precision.** On 3 of 6 cards he answered "neither" — both engine candidates were wrong.
2. **Entry timing, even when the candle is right.** *"b candle right but entry is 3 candles
   earlier."* *"9:44 S entry as candle forming."* The engine is a median 24 minutes behind him.
3. **The retest tolerance is the wrong unit.** *"it doesn't follow the 25 percent candle unit, its
   just if its close but didnt actually touch, within a few cents give or take."*
   `BAR_EXTREME_FRAC` does not govern the retest. **Swept and answered 2026-08-30**
   (`research/g87_retest_tol.py`): the best tolerance is **zero** — a limit resting exactly at the
   level. Every widened tolerance loses money, because `intrabar_stop` collapses the risk
   denominator to the tolerance itself. The follow-on `research/g88_level_limit.py` then killed
   that arm's headline: 89.6% of its fills landed **before the signal bar**. Honest version —
   limit resting strictly after the signal — is **$275/day against the shipped entry's $33**.
   Real direction, not shippable: 69% of the bar, 27% win, 15/25 green.

## The working agreement

- **Decide once, then build it until it works.** A report is not a deliverable. Working code with
  a passing test is. Debug it to confidence before bringing it back.
- **Think like a premier trader, not like Austin.** His words: *"you encapsulate my brain too much
  … my thoughts and ideas are not gold, I'm just a regular guy trying to make some money."* Bring
  trading judgement. His time buys the eye test on charts — nothing else.
- **One lane at a time.** No parallel fan-out across unrelated questions.
- **Every claim routes through a committed script**, and every dollar figure names its fill.
- **Size-gate every money number.** 1R is a fixed $1,000, so a fill landing a cent from its stop is
  a 100,000-share position and an R-multiple with a one-cent denominator. Ungated, the g87 sweep
  printed **$15,119/day** — arithmetic, not money. `signal_runner.min_risk_floor` is the gate.

## What closes this lane

An S classifier that, on the honest book, fires **1–3 times a day**, lifts precision above 39.5%
without losing S-day recall, and carries one-trade-a-day past **$397/day with every month green** —
shipped in `signal_runner.py` behind a flag, with a test, re-measured end to end. Nothing else
counts as done.



---

## THE ONE RULE: never lose a mark

Austin's judgements are the only scarce input in this project. Bars can be re-pulled,
backtests re-run, engines rewritten. **A grading session cannot be recreated.** What exists
is **1,057 distinct judged symbol-days** built over months (count it with
`research/build_deck.py::marked_card_ids()`, never by hand), and the number only goes up by
him sitting down and doing more.

### Where they live

| file | rows | what it is |
|---|---:|---|
| `research/austin_marks_v7.jsonl` | 479 | the terminal mark file; v2–v6 are fully contained in it |
| `research/blind_marks_all.jsonl` | 260 | blind grading pass |
| `research/recovered_reviews.jsonl` | 176 | prose reviews mined back out of chat |
| `research/marks_clean.jsonl` | 117 | cleaned early corpus |
| `research/marks/*.jsonl` | 518 | deck + probe exports, one file per grading session |
| `research/mark_batch_0{2,3,4}_*.jsonl` | 123 | standalone batches |
| `research/derived_marks_v{1,2}.jsonl` | 31 | derived, low confidence |
| `research/rule_ballot_batch0{1,2}.jsonl` | 48 | rule ballots — his rules, not his grades |
| `research/austin_verdicts.json` | — | a JSON list, not jsonl |

`research/marks/LEDGER.md` is the provenance record: how human marks were separated from
engine output, and why each file counts. Read it before touching any of them.

### The trap, and it has already fired twice

`.gitignore` carries `research/*.jsonl` and `research/*.html`. Those rules exist for the
tens of thousands of regenerable corpus artifacts, and they are **wider than they look**:

- 5.2's T6 decks were written, ignored, and silently discarded.
- `research/t60_silent_days.jsonl` and `research/rule_ballot_batch01.jsonl` both needed
  `git add -f`, and nothing warned.

Explicit un-ignore rules for judgement files are now in `.gitignore`. Even so:

1. **After writing any file holding a human judgement, run `git status` and confirm it is
   staged.** Not "assume the add worked" — look.
2. If it is ignored, `git add -f` it AND add an un-ignore rule so the next one is safe.
3. Never `git clean -fdx` in this repo.
4. Never delete or rewrite a mark file. Superseded corpora stay; `LEDGER.md` records that
   they are superseded.

### The no-repeat guarantee

`research/build_deck.py::marked_card_ids()` reads **every** corpus above and refuses to put
a symbol-day in a new deck if Austin has already judged it — including `grade: "none"`,
which is a judgement (an explicit refusal to trade), not a blank. Until 2026-08-22 it read
only `research/marks/` and was blind to 386 symbol-days; a deck he was about to grade held
4 repeats. If you add a mark corpus, add it to `LEGACY_MARK_FILES` in the same commit.

---

## Homework instruments

Anything put in front of Austin must **save as he works and export without a round trip**.
He does homework away from this machine.

- `research/build_deck.py` — the 60-card deck. Standard lives in `Projects/omen-decks.md`.
- `research/build_probes.py` — silent-day autopsy (09), head-to-head (10).
- `research/build_qa.py` — the open-questions page.
- `research/probe_page.py` / `probe_chart.py` — shared shell: localStorage save, restore on
  load, visible save indicator, Export → Copy all / Download `.jsonl`.

Charts render to **static SVG in Python**, not canvas: these also publish as claude.ai
Artifacts, and a phone cannot mark a chart with a pointer.

**Do not rely on the claude.ai `artifact` capability to save answers.** It was tried
2026-08-22 and nothing persisted — the pages own their persistence now.

---

## Measurement rigs

| script | question |
|---|---|
| `research/t60_baseline.py` | the baseline: money gate, durability slices, recall |
| `research/t61_onwatch_ab.py` | A/B any detection flag over the 120 graded day-cards |
| `research/test_runner_stop.py` | stops fire on closes, floor at −1.25R, wicks stop nothing |
| `research/test_universe_single_source.py` | no module keeps a private ticker list |
| `backtest_2y.py` + `research/build_bt2y_report.py` | the 2-year book and its interactive report — **this is the money/durability rig** |
| ~~`research/omen6_forward.py`~~ | **retired 2026-08-28.** Austin: *"no freezing, version snapshots for rollback."* The book has 0 trades booked; do not re-freeze without him saying so |

`universe.py` is the single source of truth for symbols. Six modules used to keep private
lists; a test fails the build if a new one appears.

### Rules that hold everywhere

- **Max loss is −1R hard. There is no −1.25R clamp.** Austin, 2026-09-03: *"1R is
  simpler so why not go with that? no stocks should be running to −10R."* Two stops,
  both his (R1/R2, 2026-08-29): the **level stop** triggers on the candle CLOSE and
  fills at that close, and the **disaster stop** is a resting order at exactly 1R from
  entry that fills on an intrabar TOUCH. Because `DISASTER_STOP_R = 1.0`, the disaster
  order sits *on* the level stop, so nothing books worse than **−1.000R** — 0 of 2,216
  losses in the two-year book do, **on the blended trade-level `r` column**
  (`backtest_week.py`'s `t.pnl / RISK_DOLLARS`, netting every scale-out fill against
  the eventual stop-out). That is a different question from the **per-fill** column
  (`stop_rule.per_fill_r_multiple`): on the pre-`ece08845` engine, 70 of 4,022
  traded rows landed worse than −1.000R per fill (53 after the size gate, worst
  −1.3333R) even though the blended column read 0 — ticket 19 (B-05), reconciled
  2026-09-05, see `stop_rule.py`'s docstring. **Every −1R claim names its column.**
  The old "wicks stop nothing out / floored at −1.25R"
  line described `research/exit_lab.py`, a lab model with no disaster stop that the
  shipped book never calls; the `verify:` gate was testing it instead of the real path
  until 2026-09-03. `stop_rule.py` owns the trigger, the fill and the floor.
  **`stop_rule.stop_fill_price()` is the one fill definition** — every rig routes through it.
  Before 2026-08-28 `backtest_week` triggered on the close and then filled at `t.stop`, so
  every loss was −1.000R by construction and the floor was unreachable code; 458 of 474
  stop-outs had already closed past 1R (`research/t11_stop_fill_fix.md`). Never re-implement
  a fill locally.
- **One tolerance unit: 25% of the previous candle's range** (`BAR_EXTREME_FRAC`). It
  governs the ON WATCH entry trigger, the 84% reclaim window, and stop slippage.
- **The money gate is mean R = 2.0.** Win rate is a secondary read. Durability = **every
  month green**.
- **R-multiples are the result; dollars are a sizing skin.** 1R = $1,000, and the instrument
  is options, not shares.
- **Two grade ladders exist and must never be mixed.** Austin's is `S`/`A`/`C`/`none`
  (`research/downgrade.py`, measured only, **not wired into detection**). The engine's legacy
  ladder is `A+`/`A`/`B`/`C`/`X` (`signal_runner.py::_grade_pa`) and it is the one that gates
  trades. `A+` fires twice in two years; `B` is 98% of the book; **`X` is not a grade**, it
  means the engine should not have fired. Every new measurement carries both side by side.
- **A = one downgrade, C = two**, off the eight variables in `omen-rulebook.md`.
  `score = tripped − confluence`, floored at C.
- Reproducibility is not assumed: 5.2's committed scale-out table could not be regenerated
  from committed code. **If you publish a number, commit the script that made it.**

---

## Security

`POLYGON_API_KEY` is interpolated into request URLs and **appears in full in any traceback**.
Filter tool output (`grep -v apiKey`) before showing it. `youtube_oauth_token.json`,
`client_secret.json` and `*.credentials.json` are credentials and are never committed.

---

# Session 2026-09-01/02 — what changed

**The g84 marks were 4.5% saved.** `probe_g84_all_in_one_2026-08-30.jsonl` held
7 rows; Austin had answered **154**. The other 147 lived only in the page's
localStorage. Every read of "the g84 marks" between 2026-08-30 and 2026-09-01 was
a read of seven cards. Recovered verbatim as
`research/marks/probe_g84_all_in_one_STANDING154_2026-09-01.jsonl`, verified a
strict superset. **The page is not storage. Export the standing set at the end of
every grading session and check `git status` by eye.**

**Every dollar figure before 2026-08-30 was the fill, not the edge.** Isolated
this session on the same trades, same count:

| book | trades | total | $/day | mean R | win |
|---|---:|---:|---:|---:|---:|
| published (unobtainable fill) | 4,508 | **+$2,633,850** | $5,278 | +0.584R | 59.4% |
| honest (obtainable fill) | 4,329 | **−$141,561** | −$283 | −0.033R | 44.1% |

The $2.6M he remembers is real and it is in `bt2y_trades_published_fill.json`.
It is also entirely the fill. When he points at the old artifacts, show him this
table rather than arguing.

**The lane is measured, not argued** (`research/g91_lane_slice.py`). Index
QQQ/SPY/IWM: 2.3 cand/day, $51/day, 13/25 green. Full pool: 18.6 cand/day,
$28/day, 11/25 green. **Pool stays FULL** — the index oracle ceiling is $437/day
against his $397 bar, so narrowing caps the project at its own target even with a
perfect classifier; the full pool's $2,948/day ceiling is the only one with room.
At a $2,500 funded trailing drawdown every lane sizes to 1R ≈ $77–187. **No lane
is fundable yet; the account type is not the blocker, the edge is.** Prop firms
are futures desks and do not fund equity-options traders — that fork is real and
premature.

**`RETEST_REQUIRED` is ON by default** (`signal_runner.py`, 2026-09-02).
`downgrade.no_retest` was a ratified variable with no consumer; it trips on **99
of the 500 days' first picks**. Priced on a MATCHED book pair — same commit, same
498 sessions, only the flag differs
(`research/bt2y_trades_retest_{off,on}.json`, `research/g94_retest_book_compare.py`):

| lane | cand/day | $/day | green months | max DD |
|---|---:|---:|---:|---:|
| full pool | 18.8 → 16.5 | $27 → **$25** | 10 → **13**/25 | $25.6k → **$21.7k** |
| index QQQ/SPY/IWM | 2.3 → 2.2 | $49 → **$65** | 13 → **15**/25 | $19.4k → **$15.7k** |

**Shipped for durability, not $/day.** −$2/day on the full pool is inside the
±1.58R error bar; +3 green months and −15% drawdown is the gate this file names.

**`research/g93_retest_gate_ab.py` is a superseded FORECAST — do not quote it.**
It predicted $36/day and 14.2 cand/day; the real book says $25 and 16.5. A
selection arm cannot model `backtest_week.DEDUPE_FIRES_ONLY`: only a *fired*
signal claims the dedupe suppression window, so capping one to C **releases** it
and previously-suppressed candidates on the same level become rows. Any C-cap
gate in this engine adds candidates as well as removing them.

**`research/bt2y_trades.json` is stale** — built 2026-08-30, different commit,
`downgrade.py` dirty, 500-session window, `RETEST_REQUIRED` not stamped. It is
the OFF-arm book for the pre-2026-09-02 figures only. The current-default book is
`research/bt2y_trades_retest_on.json`. Never A/B against a book built on a
different day: `--days 730` counts back from today. All four books travel as `research/bt2y_trades*.json.gz`
(7 MB each, 18x); after a clone run `gzip -dk research/bt2y_trades*.json.gz`.

**Do not re-propose wiring `research/downgrade.py` as the fire gate.** It is
measured and negative: gating on `sgrade=='S'` is **−$29/day**, and
`research/r3_downgrade_grader_ab.md` had already priced it (S recall +0, false
fires 29%→33%, traded signals 1,017→1,310). `ENABLE_DOWNGRADE_GRADER=0` is a
decision, not an oversight.

**`compute_austin_tier` is reported only** — "nothing below branches on it". Its
T11(a) no-displacement→C cap therefore costs no recall today, but it contradicts
his marks: `NVDA_2025-06-03` and `PLTR_2025-07-17` are both graded **S** with "no
displacement" in the note, rescued by OCR confluence. Two cards is a hint, not a
rule — but it falsifies a hard cap.

**His scope call, 2026-09-01:** *"I want signals only. A does nothing. Just A
signals, then we're going to turn A into actually fire for money."* S fires. A is
recorded and does not trade, pending promotion later.

## The daily pass

`research/daily_run.cmd`, scheduled task **OmenDailyHomework**, weekdays 16:15
ET → `research/daily_fetch.py` then `research/daily_homework.py`, deck to
`research/decks/omen-daily-<day>.html`, log to `journal/daily-<day>.log`.
One card per **symbol**, not per signal: 2026-09-01 produced 269 candidates and
fired 50 across 29 symbols against the 1–3 he takes.

## Data sources, as of 2026-09-01

- **Polygon: 403 NOT_AUTHORIZED** on recent timeframes. `data_archive` stopped at
  2026-08-27 and cannot reach today on this plan.
- **Tastytrade: HTTP 401 invalid_credentials.** The live scanner does not fail on
  this — it falls through to yfinance and logs `HTF unknown` on every symbol, so
  live runs currently have **no higher-timeframe bias at all**
  (`journal/scanner-2026-09-01.log`). Unfixed.
- **yfinance** is the only source reaching the current session. ~30 days of
  1-minute history, premarket included.
