# tradingbot — OMEN

Intraday signal engine. Break-and-retest / one-candle-rule setups on the 09:30–11:00 window.
Repo `aharger3/tradingbot`, working copy `C:\Users\aharg\Desktop\Projects\tradingbot`.

verify: python research/regression_gate.py && python research/test_runner_stop.py

---

# THE LANE — read this before starting anything (set 2026-08-30)

**One lane at a time. Nothing else gets worked on until the lane closes.**

## Where the project actually stands

| | honest fill (the default, today) |
|---|---:|
| one trade a day, first setup | **$28/day**, 45.5% win, 11/25 green months |
| the same day's **best** setup (oracle ceiling) | **$2,948/day**, 99.6% win, **25/25 green** |
| a coin flip among the day's setups | −$25/day |
| Austin's bar | **$397/day** (six figures a year) |

Read those four rows together, because they are the whole project:

1. **The entry rule is not broken.** A $2,948/day ceiling at 25/25 green months is 7.4× the bar.
   The setups are there, every month, in the book we already have.
2. **Selection is broken, completely.** Arrival order beats random by $53/day out of a $2,973/day
   spread. The engine takes the day's best setup on 12.8% of days; chance is 10.1%.
3. **The bar is 14% of the way to the oracle.** To reach $397/day from a coin flip you need
   $422 of the $2,973 spread. Not perfection — one seventh of it.
4. **Nothing else is the bottleneck.** Not exits (+0.06R). Not sizing (green months are
   scale-invariant). Not the grader. Not recall. **Which one of the day's setups to take.**

`research/g86_honest_ceiling.py` prints this table. It is the only place these four numbers come
from. If you want to quote them, run it.

## Why every dollar figure before 2026-08-30 was wrong

The engine filled at the level even when the level sat **outside the bar** — a price that did not
exist. Only **105 of 4,508 trades** were obtainable at the book's own price. That is where
"$721/day, 66.7% win, +0.8R" came from, and it is why the honest rebuild reads $28/day. The number
did not get worse; the ruler got honest. Kill any figure that does not name its fill.

## The working agreement

- **Decide once, then build it until it works.** When Austin settles something, it gets
  implemented, debugged, and tested to the point of confidence — not measured, reported, and left
  as a finding. A report is not a deliverable. Working code with a passing test is.
- **One lane at a time.** No parallel fan-out across unrelated questions. The measurement rigs
  exist; they do not need re-running to justify new work.
- **His time buys judgement, nothing else.** Charts and rule questions. Never a re-answered
  question, never a menu.
- **Every claim routes through a committed script.** No number without the file that made it.

## What closes this lane

A selector that, on the honest book, moves one-trade-a-day from $28/day toward $397/day **without
losing S-day recall**, shipped in `signal_runner.py` behind a flag, with a test, and re-measured
end to end. Nothing else counts as done.


Two gates, both must pass. `regression_gate.py` is the recall gate
(`research/t16_regression_gate.md`): it fails if any mark that currently fires goes silent. It
was RED for 16 days (`5e3677ea` → G12) with nobody noticing because nothing ran it. The Stop
hook now runs both after every edit in this repo and blocks the turn on a non-zero exit — see
`~/.claude/hooks/verify-before-done.py`. If the recall gate goes red, diagnose (stale baseline
vs. real regression) before touching `research/baseline_3.8.json` — do not silently re-lock it.

`test_runner_stop.py` is the runner-stop safety selftest (break-even enforcement, the -1.25R
floor, close-not-wick triggers, and the T24 stop-placement taxonomy in `signal_runner.py`).
It went unwired to any gate the same way the recall gate once did — see
`research/g72_stoptest_wiring.md`.

**Read next, in this order:** `DIRECTION.md` (the goal, the three gates, what an agent may
do unattended, the session pickup protocol) → `PHASES.md` (the dispatch board) → `TASKS.md`.

**Vault docs** (`C:\Users\aharg\Austin's Vault\`) — markdown only, never write code there:

| doc | what it owns |
|---|---|
| `Projects/OMEN.md` | current state + version history |
| `Projects/omen-rulebook.md` | **Austin's rules, with the sentence he said each one in** |
| `Projects/omen-decks.md` | the deck standard |
| `.scratch/omen-6/map.md` | the OMEN 6 wayfinder map + tickets |

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
