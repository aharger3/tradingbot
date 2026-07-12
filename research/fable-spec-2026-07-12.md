# FABLE Spec 2026-07-12 — structural levers toward 55%W tier

Context: hallucination audit done (`hallucination-audit.md`), filter-tweaking exhausted.
Current state (`next-session-brief.md`): 12mo/28sym = 760 tr, 36.0%W, +$61,489 blind-2R.
Take-tier S≥4+[hammer] max2/day stop-green = 83 tr, 43.4%W, $2,083/mo. Goal: 55%.

Hard rules:
- ONE behavior change per backtest run. `py -3.13 backtest_12mo.py 365 --snapshot` after each. Report honestly vs baseline — if a variant loses, keep current behavior and write that down.
- No threshold sweeping. Source-taught variants only.
- Never commit — Austin pushes. Python313, never hermes venv.
- Update `next-session-brief.md` + vault doc + Agent-Log when done.
- GLM is adding `--entry-cutoff` / `--skip-news` driver flags (glm-spec-2). Use if present; don't wait on them.

Run order: F2 → F1 → F3 (cheapest sim change first; F3 adds new signals last so runs aren't confounded). F4 whenever DeepSeek lands the file.

## F2. Stop-placement A/B (audit #6)
Source: "10-15 cents buffer below level for room" (mm 5.0), "stop loss at the break of the
candle that came back for the retest" (yt EIIiEtAEm3s). Ours = exactly at level → zone-wiggle stop-outs.
- Variant A: stop = retest-candle low (long) / high (short).
- Variant B: stop = level − max($0.10, 10% of avg 1-min range) (zones must scale with price).
- One 12mo run each. Interaction warning: stop width feeds S (structural ≥0.3% component) and stop_width_pct — report the S-distribution shift, don't let it silently move the tier population.

## F1. Liquidity-ladder exits — TOP LEVER (audit #7)
Blind 2R is our invention. Source: "exit some at high of day every single time", then next
draw of liquidity (PDH/PDL, psych whole numbers, gap fill); "2:1 is the MINIMUM aggregate
expectation, not the exit mechanism". MFE data: 25% of our losses touched +1R first.
Build in `backtest_week.py` sim, flag-gated like RULE6:
- **Variant A (canonical):** 50% off at first HOD/LOD touch after entry (session extremes as-of entry bar — no lookahead), stop unchanged until scale, then runner to first key level beyond (PDH/PDL/PMH/PML/psych whole dollar; fallback 2R), runner keeps original stop.
- **Variant B:** A + stop→BE after first scale (accelerator says do, mastermind says never — that's the A/B).
- Report tier + full-pop W%/$ vs blind-2R. Two runs. DeepSeek is extracting an exit-management dossier (verbatim scaling quotes) — consult if landed.

## F3. HOD/LOD intraday break-retest detector (audit #10)
Mastermind 5.0: "Wait for HOD break and retest or LOD break and retest. Nothing in between —
all noise." We don't code this setup at all.
- New pair in `level_pairs`: rolling session high/low, only once the extreme is ≥30 min old (avoid OR duplication); skip if within 0.1% of an existing level.
- Reuse `detect_break_retest` FSM + S scoring unchanged. stop_level_name "HOD"/"LOD" for split reporting.
- One run. Report stand-alone W%/$ for the new setup + tier impact.

## F4. QQQ 8 alignment rules (blocked on DeepSeek `qqq-alignment-rules.md`)
Encode verbatim rules as S-input/gate when file lands. NOT the OR-break proxy — inverted on
two independent measurements (aligned 34.8% vs non-aligned 43.1%).
