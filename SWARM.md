# SWARM.md — read this first, every agent, every session

You have just cloned `aharger3/tradingbot`. Read this, then run the hash check. Nothing
else comes first.

**Where truth lives.** `CLAUDE.md` = how this repo works, the `verify:` line, security.
`TASKS.md` = the queue; nothing lands in Done without a commit hash and the number that
moved. The vault (`C:\Users\aharg\Austin's Vault\`, **markdown only, never code**) holds
`.scratch/omen-8/map.md` (the current map + tickets; its Notes section is this contract),
`Projects/AUGUR.md` (the daily loop and what is already decided), and
`Projects/omen-rulebook.md` (Austin's rules, each with the sentence he said it in).

**The base rule.** A spec names the `origin/main` hash it starts from. First command:

    git fetch origin && git rev-parse --short origin/main

Mismatch = **stop and report**. Do not start. Noticing and continuing is the failure — on
2026-09-03 a cloud session rebuilt a night of work that sat unpushed on the box.

**The done rule.** A row is done when its `verify:` exits 0 *on the pinned base* AND the
push landed. Green on a stale base is not done. Never claim done on code you did not run.

    python research/regression_gate.py && python research/test_runner_stop.py

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

**One namespace.** Spec rows are letters+numbers (R1, T8, g117). Austin's rulings are
dated ("Austin, 2026-09-03"). Do not mix them or invent a third scheme.

**Plain English for Austin.** Anything he reads — a push, a brief, a homework card, a
summary — is plain English: no ticket ids, no flag names, no jargon. His time is for
charts and comments. Never re-ask a settled decision; what is settled is listed in
`Projects/AUGUR.md` ("Decided 2026-09-03") and `omen-blockers.md` ("Already settled").

**Model tiering.** Cheapest model that can do the job: cheap (haiku / deepseek / glm) for
research, bulk and mechanical work; opus for code judgment. **A different model verifies
than the one that built.** Thirty agents on opus at high effort is waste.

**One ticket per session, and how to claim it.** Take ONE ticket from the map's Frontier
(open, unblocked, unclaimed). Claim it by editing its issue file to
`Status: claimed — <who>, <YYYY-MM-DD>` and committing that before you start, so a
parallel agent sees it. When you finish, set it done with the commit hash and move its
line out of Frontier in the map.

**Current map:** `C:\Users\aharg\Austin's Vault\.scratch\omen-8\map.md`
