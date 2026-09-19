# OMEN loop queue plan (2026-09-19)

~84 env flags total: signal_runner.py 53, backtest_week.py 27, entry_fill.py 2, loss_halt.py 2. day_policy.py has none (MAX_FIRES/LOSS_STOP are hardcoded Python constants, not env-wired, despite being in book_stamp.FLAG_SOURCES).

## Already priced -- exclude
MIN_PT1_R, RULE84_DECIDED, OCR_RETEST_DISPLACEMENT, TREND_DEF, DAY_POLICY, HODLOD_DEF, RETEST_REQUIRED: real book pairs + a cycles.md row (all held). ARRIVAL_LADDER, SAC_LADDER_VARSET, X_LIFT: priced by their own standalone research scripts (t14_arrival_ladder.py, w1_sac_ladder_ab.py) with a verdict already stated in the code comment ("nothing ships" / a documented NULL) -- do not re-run.

## Excluded -- wrong lane, not a real toggle, or fill honesty
S_GATE, RULE_710_ENABLED, day_policy.MAX_FIRES/LOSS_STOP: hardcoded constants, no os.getenv -- setting the env var is a silent no-op. ENABLE_STRUCTURAL_RISK_FLOOR/MIN_RISK_FILL_CLAMP/ATR_SCALED_MIN_RISK/DOWNGRADE_GRADER, RULE84_STOP_QUALIFIER, VETO_1D, FIRE_A_WHEN_NO_S, ENTRY_WINDOW_END: real flags but absent from book_stamp.FLAG_SOURCES, same law-5 defect that blocked SIX_LEVELS_ONLY. ENTRY_FILL (the phantom), ON_WATCH (self-labeled "a FILL rule"), and every backtest_week.py stop/scale/ladder/scratch flag (STOP_ON_CLOSE, PESSIMISTIC_FILL, DISASTER_STOP, TARGET_ON_CLOSE, SCALE_PLAN, ENTRY_SCRATCH, SCRATCH_PROBE_ON, LADDER_*), plus STOP_PLACEMENT/STOP_FILL_ORDER/INTRABAR_STOP_AT_BAR/MIN_STOP_PCT: change fill/exit honesty, not a setup rule.

## Untested, registered (FLAG_SOURCES), env-wired -- candidate pool
| flag | default | rule |
|---|---|---|
| BNR_DISPLACEMENT_GATE | 1 (on) | caps break-and-retest to C unless a real displacement candle broke the level; C4/C5 tried this OFF, blocked only by the archive-drift bug LAND P fixed 09-13 |
| HTF_BIAS_GATE | 0 (off) | caps any signal fighting the daily-candle trend to C/alert-only |
| OCR_STRICT | 0 (off) | full one-candle-rule clause list (OCR_RETEST_DISPLACEMENT only tested one clause); own comment: ~5,394 -> ~139 detections |
| COUNTER_TREND_CAP | 0 (off) | caps counter-day-trend setups |
| GRADE_FIX | 0 (off) | reclaim grading fix (cap-at-B, blocks clear-road promotion on 84% re-entries) |
| RULE84_OFF/STRICT/ARM_SGRADE/ARM_NOGATE/SOURCE | 0 each | 5 more 84%-rule variants, same family as priced RULE84_DECIDED, lower priority |
| NO_REPEAT_ENTRIES, MESH_S_VETO, TRADE_RETIRED_SETUPS, CONFLUENCE_SETUP_ROUTES, S_PLUS_PER_DAY, LEVEL_RETIRE_TOUCHES/COOLDOWN, RETEST_TOL_FRAC, PIVOT_* | various | smaller/numeric knobs, fine for later rows |

## Pick order (queued below)
1. BNR_DISPLACEMENT_GATE=0 -- lowest risk, explicitly wanted twice already, root cause now fixed
2. HTF_BIAS_GATE=1 -- clean boolean, different mechanism (daily trend, not setup quality)
3. OCR_STRICT=1 -- distinct from the already-priced OCR_RETEST_DISPLACEMENT clause, largest a-priori effect size
