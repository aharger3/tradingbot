# SWARM.md — read this first, every agent, every session

You have just cloned `aharger3/tradingbot`. Read this page, run the recall query, then run
the hash check. Nothing else comes first.

**The first command, every agent, every session.**

    python research/omen_recall.py "<your question>"        # (landing with O2)

It answers "has this already been decided?" from `Projects/omen-rulebook.md`, every spec's
settled table, `CLAUDE.md` and every mark comment, and returns the sentence, its date and
its source. Query it before you propose, measure or re-argue anything. Re-deciding a settled
question is the most expensive mistake an agent makes in this repo.

**Where truth lives.** `CLAUDE.md` = how this repo works, the `verify:` line, security.
`TASKS.md` = the queue; nothing lands in Done without a commit hash and the number that
moved. The vault (`C:\Users\aharg\Austin's Vault\`, **markdown only, never code**) holds the
live spec (`Projects/omen-10-0-spec.md` — its "What the call settled" table is law),
`.scratch/omen-8/map.md` (the map + tickets), `Projects/AUGUR.md` (the daily loop) and
`Projects/omen-rulebook.md` (Austin's rules, each with the sentence he said it in).

**The base rule.** A spec names the `origin/main` hash it starts from. Run:

    git fetch origin && git rev-parse --short origin/main

Mismatch = **stop and report**. Do not start. Noticing and continuing is the failure — on
2026-09-03 a cloud session rebuilt a night of work that sat unpushed on the box.

---

## The five laws of a change

**1 — One change per row.** A row touches **one flag or one function**. Two changes = two
rows. If your row needs a second change before its number means anything, stop and say so;
the phase chief splits it. A book that moved for two reasons has measured neither.

**2 — The no-regression gate.** Austin, 2026-09-05: *"NEVER mess with code if its going to
cause a regression in backtest results, minor declines are fine not major."* A change ships
as a **default** only if, on the current baseline trade unit, **green months do not fall**
and **$/day falls no more than 5%** — checked on **both halves**, H1 (before 2025-09-01) and
H2 (2025-09-01 onward). Fail either half and the change stays behind its flag, **OFF**, and
its stamped book is kept as a toggle column in the tape. Holding a change is a normal, good
outcome. Shipping one that regresses is the only failure.

**3 — Sample size before a verdict.** A cell under **30 trades** or **12 months** gets no
verdict. Report the count and the interval and write **"not enough"**. Nearly every A/B in
this project moves less than its own error bar; say that plainly instead of naming a winner.

**4 — A different model referees.** A **Sonnet** build is refereed by **Opus told to refute
it**; an **Opus** verdict is refereed by **Sonnet told to refute it**. A builder never grades
its own number. A refuted result is **written up as refuted and kept** — it is evidence, and
deleting it only means the next agent re-runs it.

**5 — Stamped books only.** Every book records **every flag value**, the **base hash**, the
date, the session window and the script that made it. A/B only books built on the **same day
from the same base**: `--days 730` counts back from today, so two books a day apart are
different universes. **Every dollar names its fill, its exit, its unit and its script.** If
you publish a number, commit the script that made it, in the same commit.

## The fill, said once, so nobody re-argues it

The biggest regression in this project's history was **the fill model, not a rule**. Books
before 2026-08-30 bought at the level even when the bar never traded there — **105 of 4,508
trades were obtainable**. That is the entire source of the $2.6M / +0.55R / 25-of-25-green
result. **The honest fill is the ruler.** The phantom book survives as a side-by-side
**column in the tape**, never as a target, and no row proposes returning to it. `CLAUDE.md`
carries the comparison table; show it rather than arguing from memory.

---

**The done rule.** A row is done when its `verify:` exits 0 *on the pinned base* AND the
push landed. Green on a stale base is not done. Never claim done on code you did not run.

    python research/regression_gate.py && python research/test_runner_stop.py && python research/test_universe_single_source.py

**Commit and push every landed piece.** Commit as work lands — no branches, no worktrees.
A post-commit hook pushes `main`; still run `git status -sb` and confirm **0 ahead**.
Never `git clean`. An uncommitted tree is invisible and has corrupted published numbers.

**Never lose a mark.** Austin's judgements are the only scarce input here: bars can be
re-pulled and engines rewritten, a grading session cannot be recreated. `.gitignore`
carries `research/*.jsonl` and has silently swallowed judgement files twice. After
writing any file holding a human judgement, run `git status` and **look** that it is
staged; if ignored, `git add -f` it AND add an un-ignore rule in the same commit. Never
delete or rewrite a mark file. A new corpus goes into `LEGACY_MARK_FILES`
(`research/build_deck.py`) and `research/marks/LEDGER.md` in that same commit. Full
detail: `CLAUDE.md`, "THE ONE RULE".

## How to run commands here

- **Write files with the Write tool.** A shell hook rewrites commands and breaks bash
  heredocs — a heredoc that looked like it worked may have written nothing.
- **Bound every command with a timeout.** An unbounded replay loop hung a whole wave for
  3.5 hours. Long backtests and replays run in the **background with a log file** you poll.
- **Keep `POLYGON_API_KEY` out of anything you print** — filter with `grep -v apiKey`. It is
  interpolated into request URLs and appears in full in every traceback.
- Paper only. Never place a real order.

## Who does what

One **Opus chief per phase** owns the row list and the merges. **Sonnet builders** write the
code and produce the books. **Haiku researchers** do the reading and the bulk mechanical
work. **Fable** writes the reconcile verdict and spec text only. **A different model
referees every number, and a builder never grades its own.** Thirty agents on Opus at high
effort is waste — pick the cheapest model that can do the row.

**One namespace.** Spec rows are letters+numbers (R1, T8, g117). Austin's rulings are
dated ("Austin, 2026-09-03"). Do not mix them or invent a third scheme.

**One ticket per session, and how to claim it.** Take ONE ticket from the map's Frontier
(open, unblocked, unclaimed). Claim it by editing its issue file to
`Status: claimed — <who>, <YYYY-MM-DD>` and committing that before you start, so a
parallel agent sees it. When you finish, set it done with the commit hash and move its
line out of Frontier in the map.

**Plain English for Austin.** Anything he reads — a push, a brief, a homework card, a
summary — is plain English: no ticket ids, no flag names, no jargon. His time is for
charts and comments. **Never re-ask anything already settled**: the live spec's "What the
call settled" table, `Projects/AUGUR.md` ("Decided 2026-09-03") and `omen-blockers.md`
("Already settled"). Run `omen_recall.py` before you ask him a single question.

**Current map:** `C:\Users\aharg\Austin's Vault\.scratch\omen-8\map.md`
