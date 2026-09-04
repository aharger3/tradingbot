# probes/ — the homework board

**This file is the one list of what is open.** An artifact's update date is
not a signal: on 2026-09-03 eight artifacts were republished in one pass and
three of them were already exported or over the card cap. If a homework is
not in the ACTIVE table it is closed, whatever its artifact looks like.

Adding homework = add a row here in the same commit. Closing one = `git mv`
the HTML into `_archived/` and move its row. Manifests (`*-manifest.jsonl`)
stay in this directory: `x11_homework_roi.py`, `g84_one_page.py`,
`t10_x_lift_fitted.py` and `g82_verify_4.py` read them by path.

## ACTIVE (2026-09-04)

| homework | cards | artifact | export to |
|---|---:|---|---|
| `decks/omen-daily-2026-09-03-s10.html` — every S bar, main 10 + SPY, blind | 22 | https://claude.ai/code/artifact/9a20c14e-8f54-47e1-a2fe-c2b27bad0549 | `Projects/_augur-inbox.md` |
| `augur-understanding.html` — 40 statements, right / wrong / partly | 40 | https://claude.ai/code/artifact/085bcaba-9a08-47ea-b9d2-36dcbde8d6b2 | `Projects/_augur-inbox.md` |
| `omen-test-2.html` — grade, entry, stop | 97 | https://claude.ai/code/artifact/1afda097-c54a-4225-b30b-eb84ecbcc276 | `Projects/_augur-inbox.md` |
| `omen-x-vetoes.html` — should this have fired? (your own X days, by design) | 40 | https://claude.ai/code/artifact/0d96269b-21e7-4473-b818-d15177a493a7 | `Projects/_augur-inbox.md` |
| `qa-queue.html` — open questions, one tap each | 13 | https://claude.ai/code/artifact/77d5456a-0726-4b64-987e-2e343461894a | `Projects/_augur-inbox.md` |

The standing daily homework is one S deck a day from `daily_run_1105.cmd`
(`--pool core --per-signal`, 60 cap). When several days pile up ungraded,
keep the highest-leverage day of the week and retire the rest
(`decks/_retired/`) — Austin, 2026-09-04.

## ARCHIVED — do not send, do not regrade

| file (now in `_archived/`) | why closed |
|---|---|
| `silent-day-autopsy.html` | 15/15 exported → `marks/probe_autopsy_2026-08-23.jsonl` |
| `omen-h2-3lane.html` | 59/120 exported → `marks/deck_marks_h2_3lane_2026-08-28.jsonl`; 34 of the remaining 61 are symbol-days judged elsewhere. Superseded by the daily S deck |
| `omen-s-sweep.html` | 250 cards, 4x the 60 cap; 3 repeats; never graded. Its 100-card sibling is `marks/probe_s_sweep_2026-08-28.jsonl` |
| `s-sweep-selftest.html` | builder self-test, never homework |
| `omen-test-1.html` | 100/100 exported → `marks/probe_omen_test1_2026-08-27.jsonl` |
| `omen-master-homework*.html`, `omen-master-2026-08-28.html` | exported → `marks/probe_master_homework_2026-08-26.jsonl`, `marks/probe_master_2026-08-29.jsonl` |
| `omen-all-in-one.html`, `omen-deep-batch.html` | exported → `marks/probe_g84_all_in_one_STANDING154_2026-09-01.jsonl` |
| `head-to-head.html` | exported → `marks/probe_head2head_2026-08-24.jsonl` |
| `grader-calibration.html` | folded into the master homework |
| `decks/_retired/omen-daily-2026-09-0{1,2}.html`, `-s.html` for 09-02/03/04 | one-day S stacks superseded by the 09-03 per-signal deck |

Archived pages still open and still export — their browser-stored marks are
not lost. Old artifact URLs for archived pages stay live; ignore them.
