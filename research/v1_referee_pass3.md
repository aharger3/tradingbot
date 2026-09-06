# V1 repair -- pass 3 (2026-09-06)

## Refereed

Pass 2 refuted V1: `_yf_batch_premarket_today` filtered premarket bars by clock
only (`df.index.time < dt.time(9, 30)`), no date filter. `yf.download(period='1d')`
returns the most recent session with data, so on any day with no premarket bars
yet (weekend/holiday run, or before the feed populates), the previous session's
PMH/PML print as if they were today's, and `format_message` renders a stale
number identically to a fresh one (no staleness marker, `n/a` only on `None`).

## What changed

- `_yf_batch_premarket_today(symbols, today)` now takes `today` and the mask is
  `(df.index.time < dt.time(9, 30)) & (df.index.date == today)` -- a bar from a
  prior session no longer satisfies the premarket filter.
- `fetch_levels`'s call site passes its own `today` through.
- No change to `format_message`: with the date fix, a day with no premarket
  bars yet now correctly yields an empty frame -> `None` -> the existing
  `n/a` path. The "stale renders identically to fresh" defect was downstream of
  the date bug; fixing the source made the existing `n/a` path correct rather
  than needing a second display change.

## Verified

`python research/premarket_list.py --dry-run` on 2026-09-06 (Sunday, no
premarket bars posted): all 11 core symbols show PDH/PDL populated and
**PMH/PML both `n/a`** -- previously this would have printed Friday
09-04's premarket range. No traceback, no API key in output.

## Not fixed in this row (kept as limitation, does not block the date-bug fix)

- **Scheduled task holiday calendar.** `\OmenPremarketList` is still a plain
  MON-FRI weekly trigger with no holiday awareness, so it will still fire on
  2026-09-07 (Labor Day). With the date fix landed, that firing is now
  harmless -- it will correctly print premarket `n/a` for every symbol instead
  of a stale range -- but the task itself still runs on a day markets are
  closed. Building a holiday calendar into a Windows scheduled task is a
  second change (a different function/mechanism from the one-line date-mask
  fix this row makes) and is left for its own row if Austin wants the task to
  skip market holidays outright rather than degrade gracefully.
- Reporting/tracking of `research/premarket_list_run.cmd` was already resolved
  in the prior V1 session (commit `3c8e586d`); untouched here.

## Result

Core defect (stale premarket numbers rendered as fresh) is fixed and verified
live. Refereed pass 1's push-tag findings stand as before (kept verbatim in
`research/v1_referee.md`).
