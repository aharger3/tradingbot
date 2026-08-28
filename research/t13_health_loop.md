# T13 — the health loop

`research/x9_live_gap_premortem.md` priced why: this book runs 2.45 trades/day at sd 2.3189R,
so a daily loop learning from money needs 33,726 trades (+0.05R) or 13.7 years (+0.10R) to
detect anything. **A daily loop cannot learn from money.** What *can* update daily is (a)
agreement with a new mark, (b) fired-or-silent on a day Austin graded, (c) execution health.
This track builds (c) — the one x9 measured as already broken, four ways, all live right now.
Script: `research/t13_health_loop.py`. Run it: `python research/t13_health_loop.py`.

---

## 1. The blind-feed alarm — fixed

`sentry_scanner.py` alerted on the **age** of `journal/scanner_status.json`, never on whether
the scan behind it saw anything. `live_scanner._write_scanner_status()` is called
unconditionally at the end of every cycle, including a cycle where every symbol's fetch
failed — so the file stays perpetually fresh while the feed is dead. Measured by x9: **12
straight fully-blind sessions**, 2026-08-19 through 2026-08-28, and the sentry never fired once.

**Fix:**
- `live_scanner.scan_once()` now counts `bars_fetched` — the number of symbols that returned
  ≥1 candle this cycle — and passes it into `_write_scanner_status()`, which writes it into
  `scanner_status.json` as a new field (`bars_fetched`, `null` on the early-halt return path
  where the fetch loop never ran).
- `sentry_scanner.staleness()` now returns a fourth value, `blind`, true when
  `bars_fetched == 0 and signals_fired_today == 0` — a cycle that ran, wrote a fresh timestamp,
  and saw nothing.
- The alert decision is now `sentry_scanner.decide(age_min, blind, now, in_rth=...)`, a pure
  function pulled out of `main()` for testability: age-based staleness is checked exactly as
  before, but a **fresh, blind** file now also trips `"blind-feed"` — checked *inside* the
  "fresh" branch, because a blind cycle keeps re-writing a young timestamp forever and age alone
  would never catch it.
- `build_alert()` grew a distinct `"🚨 OMEN Scanner BLIND"` embed for this reason so a Discord
  alert doesn't read "may be down" when the process is provably up and just seeing nothing.

**Test** (`test_blind_feed_trips_alarm` in `research/t13_health_loop.py`): writes a synthetic
`scanner_status.json` with a fresh timestamp, `bars_fetched: 0`, `signals_fired_today: 0`, and
asserts `staleness()` reads `blind=True` even though `age_min < STALE_MIN`, and that `decide()`
returns `"blind-feed"`. A control case with `bars_fetched: 3` on the same fresh timestamp
asserts no alert. A third control reproduces the pre-existing `"stale-during-rth"` path
unchanged. All three pass.

---

## 2. The DST bug — three functions, fixed, plus one inline duplicate

`research/x9_live_gap_premortem.md` §2.8 named the pattern: `utcnow() - timedelta(hours=4)` is
hardcoded EDT (UTC-4) and is wrong by one hour Nov–Mar (EST is UTC-5). Found and fixed:

| location | what it computes | fixed to |
|---|---|---|
| `paper_trader._now_et_iso()` (line 41–42) | the paper-ledger OPEN/CLOSE timestamp | `datetime.now(ZoneInfo("America/New_York"))` |
| `paper_trader.PaperBook._log()` (line ~241) | back-fills the date onto an `HH:MM:SS`-only ledger timestamp | same fix — this is a fourth occurrence of the identical pattern in the same file, not a separate bug, so it's fixed alongside the other three named in the track brief |
| `options_sizer.nearest_expiration()` (line ~165) | picks 0DTE vs next-trading-day expiry | same fix |
| `options_sizer.weekly_expiration()` (line ~177) | picks the nearest Friday expiry | same fix |

`live_scanner.now_et()`, `polygon_feed.py`, `market_data.py`, and `tastytrade_feed.py` were
already `ZoneInfo("America/New_York")`-correct (confirmed by grep) — those three-plus-one were
the only survivors of the hardcode.

**Consequence while broken:** wrong timestamps in the paper ledger year-round in the wrong
direction Nov–Mar, and — the sharper one — `nearest_expiration()`'s 14:30 ET cutoff and
`weekly_expiration()`'s Friday computation would evaluate against a clock **one hour fast**
in winter, misclassifying which expiry is "today" or "this Friday" right at the boundary.

**Test** (`test_dst_boundary`): mocks `datetime.now` inside `paper_trader` and `options_sizer`
to a fixed UTC instant and checks the resolved ET wall-clock hour against the known UTC offset
for two dates — 2026-01-15 (EST, UTC-5) and 2026-07-15 (EDT, UTC-4). A sanity assertion inside
the test confirms the old `-timedelta(hours=4)` hardcode really would disagree with the correct
answer in the EST case (it wouldn't in the EDT case, which is exactly why the bug survived this
long — it's invisible five months a year and wrong the other seven). A third case exercises
`PaperBook._log`'s inline duplicate across a UTC-day boundary in both regimes and checks the
date it backfills. All pass.

---

## 3. Scan cadence — measured, not yet fixed

Reused `research/x9_live_gap_premortem.py:scanner_health()` rather than re-deriving the parse
(38 log files, `journal/scanner-*.log`):

```
scan-cycle duration (gap - fixed 60s sleep): median 44s  p75 312s  p95 402s  max 979s
inter-scan gaps that skip >=1 one-minute bar: 410 / 772 = 53.1%
```

**What the p95 has to be for a 1-minute engine:** the loop is `scan_once(); sleep(60)` — free
running, never aligned to the minute boundary. For a cycle to never skip a bar, the *scan*
itself — not the sleep — has to fit inside the 60-second window at the **tail**, not just the
median, because every cycle over budget eats into the next minute's bar. That means **p95 scan
duration must be under 60 seconds**. Measured p95 is 402s — **6.7x over budget**. (On sessions
with zero feed failures the median cycle alone is 291s, already 4.9x over — this isn't only a
failure-mode cost.)

Not fixed in this track (out of scope — x9 §Top-5 #4 names the fix: `fetch_candles()` burns
its full 10-second timeout per symbol with no early exit once it has the requested window;
2, drop the forming bar; 3, dedupe `_parse_candle_feed_data` by timestamp). This track's check
was to *report* the cadence with the script that made it, which is done above.

---

## 4. Tastytrade auth — diagnosed, not touched

**Do not touch a live credential.** This section is diagnosis only, from code and logs.

The error changed shape between 2026-08-26 and 2026-08-28, and that shape change is the whole
diagnosis:

| session | error |
|---|---|
| 2026-07-06 → 2026-08-26 (every failing session) | `HTTP 403 {"code":"device_challenge_required", "message":"Device authentication challenge required", "redirect":{"url":"/device-challenge", ...}}` |
| 2026-08-28 (today, 1,466 occurrences — the whole session) | `HTTP 400 {"code":"missing_request_token","message":"The request token is missing"}` |

Read against the code:

- `tastytrade_feed.TastytradeFeed._session_auth()` (line 119) POSTs to `/sessions` with either
  `remember-token` (if `TASTYTRADE_REMEMBER_TOKEN` is set in `.env`) or `password`. **It has no
  handler for a device challenge at all** — no code anywhere in `tastytrade_feed.py` reads
  `X-Tastyworks-Challenge-Token` or POSTs to `/device-challenge`. On a 403, it just raises
  `RuntimeError` and the caller (`live_scanner.scan_once`) falls back to yfinance.
- `tasty_device_auth.py` **is** the handler — a standalone, interactive, one-time script whose
  own docstring says exactly this: "Tastytrade now blocks new API sessions with a device
  challenge... Run this ONCE interactively... It logs in, triggers the challenge, asks for the
  code Tastytrade emails/texts you, submits it, then saves a remember-me token to `.env`." It
  is not wired into `live_scanner.py` or `tastytrade_feed.py` — it exists and has never been
  run to completion, or its token has since gone stale.
- `.env`'s `TASTYTRADE_REMEMBER_TOKEN` was last written **2026-07-26** (file mtime). Every
  session since has been hitting `device_challenge_required`, meaning that token has not
  cleared the challenge since before this failure streak started, or Tastytrade re-triggers the
  device challenge periodically regardless of the remember-token.
- The shift from `403 device_challenge_required` (every prior session) to `400
  missing_request_token` (today only) is consistent with Tastytrade's account-side challenge
  state having advanced: after enough session attempts against an unresolved challenge, the
  `/sessions` endpoint appears to now expect a challenge/request token to accompany the login
  body — which `_session_auth()` never sends — producing "the request token is missing" instead
  of re-issuing the challenge notice. This repo has no code that reads or interprets Tastytrade's
  challenge-state machine beyond the initial 403, so this is inference from the error-message
  change, not a confirmed API contract, and is written down as such.

**What Austin must do** — this requires a code entered on his phone/email, so it cannot be run
unattended:

1. From this machine, run `python tasty_device_auth.py` (already in the repo root).
2. It logs in with the `.env` username/password, triggers the device challenge, and prompts
   `Tastytrade texted a code to <phone>. Enter it:` — enter the code Tastytrade sends.
3. On success it writes a fresh `TASTYTRADE_REMEMBER_TOKEN` into `.env` and prints the new
   session token's last 8 characters to confirm.
4. If it still fails with `missing_request_token`, the account's challenge state has advanced
   further than this script's flow (built for the initial 403, not this text) — Tastytrade's
   own web/mobile app login is the next thing to try, since that is the flow guaranteed to
   clear whatever server-side challenge state is now blocking the API.

Not done and not attempted: running `tasty_device_auth.py` myself (it requires a code sent to
Austin's phone), and changing anything in `.env`.

---

## Check

- `python research/t13_health_loop.py` → `ALL T13 TESTS PASSED` (blind-feed alarm test, DST
  boundary test, and a regression-gate-stays-green self-check, run with a clean env stripped of
  the pre-existing `.env`-leaked `ENABLE_SAC_LADDER` var so this track's edits are judged in
  isolation — see the note in `test_bars_fetched_default_off_byte_identical`).
- `python research/regression_gate.py` → `PASS: no baseline-fired mark went silent.` — none of
  this track's edits touch detection.
- Cadence figure printed above, script named (`research/x9_live_gap_premortem.py`,
  `scanner_health()`, reused not re-derived).

## Not done, named as such

- The cadence fix itself (early exit on `fetch_candles`, dedupe, drop the forming bar) — x9
  §Top-5 #4, out of this track's scope.
- Wiring `tasty_device_auth.py`'s challenge flow into `tastytrade_feed._session_auth()` so this
  doesn't require a manual one-off script every time the remember-token lapses — flagged, not
  built, since it touches the live auth path and this track's instruction is diagnose-and-stop.
- A general fix for `_load_env_file` leaking `.env` vars (e.g. `ENABLE_SAC_LADDER=1`) into
  every subprocess spawned from a process that has imported any module importing `.env` — hit
  as a false failure while building this track's own self-check, worked around there, not fixed
  at the source. Out of scope for T13.

## Provenance

- `research/t13_health_loop.py` — cadence report + all three tests, run it.
- `research/x9_live_gap_premortem.py` / `.md` — source of the cadence figures and the four
  numbered problems this track fixes/diagnoses.
- `journal/scanner-*.log` (38 files) — read directly for the auth-error timeline.
- `.env` mtime — read via filesystem, not printed (credential file).
