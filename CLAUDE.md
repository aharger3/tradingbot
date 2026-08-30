# tradingbot — OMEN

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
   `BAR_EXTREME_FRAC` does not govern the retest. `research/g87_retest_tol.py` is the sweep he
   asked for.

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

- **Stops trigger on the candle CLOSE**, fill at that close, floored at **−1.25R**.
  Wicks stop nothing out. Austin settled this five times in one batch of marks.
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
