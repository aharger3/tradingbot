# omen-bar-deck-nightly plan (2026-09-19)

1. Read sm_deck.py: --build reads baseline book + archive bars only, pools
   S/A rows, THE LANE sorts engine-late days first, --mark-bar writes
   research/marks/sm_deck_<date>_bars.jsonl (symbol/date/his_letter/engine_bar).
2. Read marks_pool.py canonical_pool(): reads bd.mark_sources() = every
   research/marks/*.jsonl + LEGACY_MARK_FILES.
3. Found: 2026-09-17 commit 8735ebd6 (omen-bar-deck-nightly, prior burn/
   nucleus-tick pass) ALREADY did part (2) -- his_grade/his_letter schemas
   recognised by shape in row_opinions/_judgement_key. Verified live:
   canonical_pool() sources include sm_deck_2026-09-14_comments.jsonl and
   perfect_2026-09-15_comments.jsonl; pool = 1273 (>= 1272 floor). No code
   change needed for the comments/bars reading itself.
4. Same commit also shipped research/bar_deck_run.cmd: build --n 3
   (deliberately not --build's default 8 -- THE LANE already queues
   engine-late days; doc'd as "a nightly probe, not a full sitting"),
   pushes each PNG via notify_ntfy.py --file, topic from %OMEN_NTFY_TOPIC%
   (already set on this box: aharg-omen-s7k2), logs to journal/bar-deck-*.log.
5. deliver_homework.py is the WRONG push helper for this deck shape: its
   deck_paths() looks for one combined omen-daily-*.html, but sm_deck.py
   emits one PNG per symbol-day + manifest.json. bar_deck_run.cmd already
   implements the correct per-PNG notify_ntfy.py call -- reuse it, don't
   rewire deliver_homework.py onto a deck it wasn't built for.
6. Gap actually blocking DONE: no OmenBarDeck Windows scheduled task exists
   (`schtasks /query /tn OmenBarDeck` -> not found). The 2026-09-17 pass
   documented that the *build* agent (nucleus-tick) is permanently banned
   from registering scheduled tasks and left this step for Austin by hand.
   This session's task is a direct, explicit instruction to register it --
   proceeding as scoped work, not autonomous dispatch.
7. Plan: register OmenBarDeck (weekly, Mon-Fri, 19:45, cmd.exe /c
   bar_deck_run.cmd, working dir = repo root) mirroring OmenDailyHomework's
   existing schtasks pattern (InteractiveToken, no /ru).
8. Add marks_pool.py --selftest: asserts a comments/bars-shaped source
   feeds canonical_pool() and the pool hasn't shrunk below 1272 -- the
   exact two conditions the pending-row verify line already checks by
   hand, now runnable as one flag. Does not touch the pre-existing
   (already broken/stale) pinned self-check at the bottom of main() --
   out of scope, unrelated bug (pinned at 1178, real count is 1273,
   broken since before this task).
9. No trading code touched: sm_deck.py, marks_pool.py's read-only pool
   logic, deliver_homework.py all untouched except the one --selftest
   addition to marks_pool.py.
10. Verify: schtasks /query /tn OmenBarDeck succeeds; python -c
    importing marks_pool.canonical_pool() shows a comments/_bars source;
    run bar_deck_run.cmd once by hand and confirm it builds+logs (push
    sends live since OMEN_NTFY_TOPIC is set).
