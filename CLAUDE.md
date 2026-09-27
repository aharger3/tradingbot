# tradingbot — CLAUDE.md

How this repo works: the `verify:` line, the production/worktree rule, security, and the
one rule that overrides everything else here. `README.md` has the current architecture map
(eye loop, gates, reports, scheduled tasks, data locations) — read it first for "what's
running today". `SWARM.md` is the shorter agent-onboarding page that points here.

```
verify: python research/regression_gate.py && python research/test_runner_stop.py && python research/test_universe_single_source.py && python research/test_propfirm_gate.py && python research/test_propfirm_luck_check.py
```

## Current reality (2026-09-27)

- **The v3 engine (`signal_runner.py`) does not survive out-of-sample.** MNQ −0.17R, n=46
  proxy book. Nothing routes it to a live order; paper only, everywhere.
- **The eye loop is the active build** (shipped 2026-09-26/27, PRs #39–#43): a phone card
  asks Austin S/Not-S on each candidate, a 120s gate on his answer, then a paper trade and a
  4:30pm ntfy report. **Replay mode only** — no live 1-minute feed is wired in; every card and
  journal row from it is clearly marked replay/test. No orders are ever placed, full stop.
- **eye1 classifier can't copy his eye**: AUC 0.54 against his marks, out-of-sample by date.
  Measured and negative — do not re-propose it as a fire gate without new evidence.
- Production checkout (`C:\Users\aharg\Desktop\Projects\tradingbot`) stays on `main`. See
  the worktree rule below before touching anything experimental.

## Production vs experiments — the worktree rule (Austin, 2026-09-26)

`C:\Users\aharg\Desktop\Projects\tradingbot` is **production**: stays on `main`, stays clean,
every scheduled task on the box runs from it. **Never `git checkout` a branch inside it.**

Anything experimental — a new signal idea, an S-accuracy chase, a classifier retrain — goes
in a separate worktree:

```
git worktree add ..\tradingbot-lab <branch>
```

Docs-only or any other change that must land in production goes on its own short-lived
branch/worktree too; only a fast-forward merge back to `main` touches the production folder,
and only after `main` is confirmed clean.

**After any build that switched branches anywhere on the box**, confirm production is back
before 19:30 ET (`OmenNightlyLoop` runs at 20:00):

```
cd C:\Users\aharg\Desktop\Projects\tradingbot; git checkout main; git status
```

`git status` must read clean. A dirty or off-`main` production folder at 20:00 is a broken
nightly run, not a future cleanup task.

---

# THE ONE RULE: never lose a mark

Austin's judgements are the only scarce input in this project. Bars can be re-pulled,
backtests re-run, engines rewritten. **A grading session cannot be recreated.** What exists
is **1,057+ distinct judged symbol-days** built over months (count with
`research/build_deck.py::marked_card_ids()`, never by hand), and the number only goes up by
him sitting down and doing more. Full inventory and provenance: `research/marks/LEDGER.md`.

### The trap, and it has already fired twice

`.gitignore` carries `research/*.jsonl` and `research/*.html` for the tens of thousands of
regenerable corpus artifacts — and it is wider than it looks. 5.2's T6 decks were written,
ignored, and silently discarded; two mark files needed `git add -f` with no warning.

1. **After writing any file holding a human judgement, run `git status` and look** that it
   staged. Assuming the add worked is how marks get lost.
2. If it is ignored, `git add -f` it AND add an un-ignore rule in the same commit.
3. Never `git clean -fdx` in this repo.
4. Never delete or rewrite a mark file. A new corpus goes into `LEGACY_MARK_FILES`
   (`research/build_deck.py`) and `research/marks/LEDGER.md` in the same commit.

`research/build_deck.py::marked_card_ids()` reads every corpus and refuses to put a
symbol-day in a new deck if Austin has already judged it — including `grade: "none"`, which
is a judgement, not a blank.

---

## Homework instruments

Anything put in front of Austin must **save as he works and export without a round trip** —
he does homework away from this machine.

- `research/build_deck.py` — the 60-card deck. Standard lives in `Projects/omen-decks.md`.
- `research/build_probes.py` — silent-day autopsy, head-to-head.
- `research/build_qa.py` — the open-questions page.
- `research/probe_page.py` / `probe_chart.py` — shared shell: localStorage save, restore on
  load, visible save indicator, Export → Copy all / Download `.jsonl`.
- `eye_card/` — the eye-loop phone card: chart PNG + ntfy S/Not-S buttons, tap logged
  immediately to `eye_card/labels.csv` via the local label server (port 9135).

Charts render to **static SVG/PNG in Python**, not canvas — these publish as claude.ai
Artifacts too, and a phone can't mark a canvas chart with a pointer. **Do not rely on the
claude.ai `artifact` capability to save answers** — tried 2026-08-22, nothing persisted; the
pages own their own persistence now.

---

## The five laws of a change (Austin's gate, unchanged since 2026-09-05)

1. **One change per row.** One flag or one function. Two changes = two rows, two numbers.
2. **The no-regression gate.** A change ships as a default only if, on the current baseline,
   green months don't fall and $/day falls no more than 5% — checked on both halves (H1
   before 2025-09-01, H2 after). Enforced by `research/regression_gate.py`. Fail either half
   and the change stays behind its flag, OFF. Holding a change is a normal, good outcome.
3. **Sample size before a verdict.** Under 30 trades or 12 months gets no verdict — report
   the count and interval and say "not enough."
4. **A different model referees.** A Sonnet build is refereed by an Opus told to refute it;
   an Opus verdict by a Sonnet told to refute it. A builder never grades its own number. A
   refuted result is written up as refuted and kept, never deleted.
5. **Stamped books only.** Every book records every flag value, the base hash, the date, the
   session window and the script that made it. A/B pairs come from the same day, same base.

**The done rule.** A row is done when its `verify:` exits 0 *on the pinned base* AND the push
landed. Green on a stale base is not done. Never claim done on code you did not run.

**Commit and push every landed piece.** No branches, no worktrees *inside production* — a
post-commit hook pushes `main` there; still run `git status -sb` and confirm 0 ahead.
Experimental branches/worktrees exist outside production only (see the rule above).

---

## Security

`POLYGON_API_KEY` is interpolated into request URLs and **appears in full in any traceback**.
Filter tool output (`grep -v apiKey`) before showing it. `youtube_oauth_token.json`,
`client_secret.json`, `.env` and any `*.credentials.json` are credentials and are never
committed, never printed, never pasted into a report.

**Paper only, always.** Nothing in this repo places a real order. The eye loop, the v3
engine, the classifier — every execution path here is paper or replay. Wiring a live order
is a decision Austin makes explicitly, not a refactor an agent lands quietly.

---

## Who does what

One **Opus chief** per phase owns the row list and the merges. **Sonnet builders** write the
code and produce the books. **Haiku researchers** do the reading and bulk mechanical work.
**Fable** writes the reconcile verdict and spec text only. **A different model referees every
number**, and a builder never grades its own. Pick the cheapest model that can do the row.

**One namespace.** Spec rows are letters+numbers (R1, T8, g117). Austin's rulings are dated
("Austin, 2026-09-05"). Don't mix them or invent a third scheme.

**One ticket per session.** Take ONE ticket from the current map's Frontier (open, unblocked,
unclaimed — `C:\Users\aharg\Austin's Vault\.scratch\omen-8\map.md`). Claim it by editing its
issue file to `Status: claimed — <who>, <YYYY-MM-DD>` and committing that before starting.
When done, set it done with the commit hash and move it out of Frontier.

**Plain English for Austin.** Anything he reads — a push, a brief, a homework card, a
summary — is plain English: no ticket ids, no flag names, no jargon. His time is for charts
and comments. **Never re-ask anything already settled** — the live spec's "What the call
settled" table, `Projects/AUGUR.md`, `omen-blockers.md` ("Already settled"). Run
`python research/omen_recall.py "<question>"` before asking him anything.

## Gaps

- Nightly-loop gate coverage for `eye_runner.py` specifically (beyond the five engine gates
  above, which target `signal_runner.py`) is not confirmed in this pass — check
  `OmenNightlyLoop`'s script list before assuming the eye loop is gated the same way.
- `eye1` (PR #39) and `eye4` (PR #42) are unmerged branches that `main`'s `eye_runner.py`
  (PR #43) already imports by path — a fresh `main`-only clone's runnability is
  [unverified] this pass.
