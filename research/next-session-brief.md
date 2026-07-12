# OMEN Next-Session Brief (updated 2026-07-12 ~00:00, post FABLE structural-levers session)

## State (verified, 12mo re-run 2026-07-11 late PM)
- 12mo / 28 symbols / unbiased: **760 traded, 36.0%W, +$61,489/yr** all signals
  (unchanged — F4 S-input is annotation-only, no routing).
- **Live take-tier UPGRADED: S>=4 + [hammer], max 2/day, stop-when-green = 90 tr/yr,
  44.4%W, $30,000/yr (~$2,500/mo @ $1k risk)** — was 83/43.4%/$2,083. Driver: F4
  QQQ Rule-4 alignment S-input (below). NOTE: live cards show the +1 only after
  live_scanner plumbs QQQ break tracking (open item).
- FABLE SPEC 2026-07-12 EXECUTED — full details `research/f2f1_runs/session-notes.md`,
  per-run charts jsons archived there. One change per run, all honest:
  - **F2 stop placement: REFUTED, kept at-level.** Retest-candle stop and buffer stop
    both lose on matched entries (identical 627-629 entries: −$24.5k / −$21.6k) — with
    target = 2×risk, widening the stop moves the target further; costs more wins (37/38)
    than wiggle-saves (28/31). Also floods S≥4 tier via the 0.3% structural component.
    Re-test only if exits ever stop being 2R-of-risk.
  - **F1 liquidity-ladder exits: REFUTED, kept blind 2R.** A (50% at HOD/LOD +
    runner to next level): −$12k full-pop, tier $5.9k. B (+BE after scale): tier hits
    58%W but $5.7k/yr — median scale fill only 0.66R, 30% of runner targets <1R.
    Ladder buys win rate, sells expectancy. The 55%W goal is cosmetically reachable
    this way; expectancy is the objective. LADDER_MODE stays None (code kept, flag-gated).
  - **F3 HOD/LOD break-retest detector: no edge, OFF.** 19 tr/yr standalone 33.3%W
    −$228 (≥30-min-old extreme + 11:00 cutoff = ~45-min firing window). Tier drag
    43.4→42.5. HODLOD_PAIR=False; re-test if entry cutoff ever moves later.
  - **F4 QQQ Rule-4 alignment: ENCODED (S+1 when aligned).** Proxy = QQQ's first RTH
    close through PDH/PMH (up) / PDL/PML (dn) before entry — NOT the refuted OR-break
    proxy. Full-pop split: aligned 38.6%W +$54k vs non-aligned 33.0%W −$1.7k (all
    system profit is in aligned trades). Hard gate = 38 tr 47.4%W $16k (max W%, half
    trades). S+1 = 90 tr 44.4%W $30k — took S+1. S now maxes 10; S-regexes fixed in
    analyze_aplus/daily_review/compare_runs.
- Infra fix (behavior-verified neutral): backtest dedupe key is now the broken LEVEL
  NAME for B&R (was round(stop,2) — variable stops made 760 tr look like 1811).
- Observation parked (threshold territory, don't sweep): min-risk D-gate may be
  over-aggressive — the ~520 extra trades it releases under wider stops were +$40k blind.
- News days / hour split unchanged from 2026-07-11 AM brief: tier news-skip 44.8%,
  <10:30 45.2%/$22k/62tr. **Candidate stack: qqqA-S+1 + news-skip + <10:30 — each
  measured positive separately, COMBINED EFFECT UNMEASURED — one run next session.**
- QQQ OR-break proxy stays dead (inverted, confirmed twice). Rule-4 key-level proxy
  replaces it everywhere going forward.
- Scanner: 28 symbols, 9:25 schtask, Python313 (NEVER hermes venv), paper mode.
  Monday 7/13 = first live run of hammer scores + expanded list. Tue 7/14 CPI,
  Wed 7/15 PPI (news-day ⚠ posts to Discord at startup).
- Uncommitted git pile in tradingbot grew (F2/F1/F3/F4 + dedupe fix) — Austin pushes,
  agents never commit.

## NEXT SESSION (priority order)
1. **Combined tier run**: qqqA-S+1 (encoded) + `--skip-news` + `--entry-cutoff 10:30`
   (GLM flags landed in backtest_12mo.py) — one run, measure the stack.
2. **live_scanner QQQ plumbing**: track QQQ PDH/PMH/PDL/PML breaks intraday, set
   runner.qqq_breaks per symbol so live cards carry the +1 and [qqqA]/[qqqX] tags.
   Touches live path — keep GLM off it, Fable session or Austin review.
3. 84% arm-quality gate (arm only off A/A+ or S>=4 stop-outs) — measure, n small.
4. TSLA exception (qqq-alignment-rules ambiguity #1: TSLA trades independent of
   index alignment) — measure TSLA-only qqqA split before exempting.

## DEEPSEEK SESSIONS (bulk extraction, cheap)
- ~~qqq-alignment-rules.md~~ LANDED + ENCODED 2026-07-11.
- `research/84rule-sizing-dossier.md` — resolves size-up conflict (keep 1× until then).
- Exit-management dossier (verbatim scaling quotes) — F1 refuted the literal ladder;
  dossier still useful to check our reading of "next draw of liquidity".
- discord_data mining (22,596 files) → `research/scarface-rules-discord.md`.
- circle_videos (82 files) whisper + extraction → `research/scarface-rules-videos.md`.
- Shorts "elevator down" playbook extraction (per-direction grading candidate).

## GLM SESSIONS (mechanical)
- ~~--entry-cutoff / --skip-news driver flags~~ LANDED 2026-07-11 (used next session).
- SPEC12 daily session review to Discord; dashboard live status file.
- KEEP OFF omen_bot.py / signal_runner.py / live_scanner.py core detection.

## Open items for Austin
- Monday: watch Discord cards — take S>=4 with [hammer] only, max 2, stop when green.
  Skip [chase]. (Cards won't show qqq +1 yet — if you want it live this week, say so.)
- Paste 25-ticker options-volume screener list if it differs from live 28.
- Vanquish decision pending (Basic $750 hold-to-2R vs Advanced $1,499 trailers).
- Long-term roadmap unchanged: HTF understanding → futures prop research → ES bot.
