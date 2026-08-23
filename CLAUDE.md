# tradingbot — OMEN

Intraday signal engine. Break-and-retest / one-candle-rule setups on the 09:30–11:00 window.
Repo `aharger3/tradingbot`, working copy `C:\Users\aharg\Desktop\Projects\tradingbot`.

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
is 599 rows built over months, and the number only goes up by him sitting down and doing
more.

### Where they live

| file | rows | what it is |
|---|---:|---|
| `research/austin_marks_v7.jsonl` | 479 | the terminal mark file; v2–v6 are fully contained in it |
| `research/blind_marks_all.jsonl` | 260 | blind grading pass |
| `research/recovered_reviews.jsonl` | 176 | prose reviews mined back out of chat |
| `research/marks_clean.jsonl` | 117 | cleaned early corpus |
| `research/marks/deck_marks_*.jsonl` | 184 | deck exports, one per grading session |
| `research/mark_batch_0{2,3,4}_*.jsonl` | 123 | standalone batches |
| `research/derived_marks_v{1,2}.jsonl` | 31 | derived, low confidence |
| `research/rule_ballot_batch01.jsonl` | 20 | rule ballot — his rules, not his grades |
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
| `research/omen6_forward.py` | frozen-engine forward scoring; `freeze --force` VOIDS the book |

`universe.py` is the single source of truth for symbols. Six modules used to keep private
lists; a test fails the build if a new one appears.

### Rules that hold everywhere

- **Stops trigger on the candle CLOSE**, fill at that close, floored at **−1.25R**.
  Wicks stop nothing out. Austin settled this five times in one batch of marks.
- **One tolerance unit: 25% of the previous candle's range** (`BAR_EXTREME_FRAC`). It
  governs the ON WATCH entry trigger, the 84% reclaim window, and stop slippage.
- **The money gate is mean R = 2.0.** Win rate is a secondary read. Durability = **every
  month green**.
- **R-multiples are the result; dollars are a sizing skin.** 1R = $1,000, and the instrument
  is options, not shares.
- **A = one downgrade, C = two**, off the eight variables in `omen-rulebook.md`.
- Reproducibility is not assumed: 5.2's committed scale-out table could not be regenerated
  from committed code. **If you publish a number, commit the script that made it.**

---

## Security

`POLYGON_API_KEY` is interpolated into request URLs and **appears in full in any traceback**.
Filter tool output (`grep -v apiKey`) before showing it. `youtube_oauth_token.json`,
`client_secret.json` and `*.credentials.json` are credentials and are never committed.
