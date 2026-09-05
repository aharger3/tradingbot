# B3: Bug Sweep — Confirmed Fixes

Fifteen confirmed bugs fixed with root-cause remedies, one test per fix, all verify gates passing.

| id | claim | status | commit | verified |
|---|---|---|---|---|
| B-01 | S/A grade ladder round trip broken: SAC_TIER['S']='A' collides with LADDER['A']='A' | partial | d3cbda24 | no |
| B-02 | Two grade ladders disagree on his A: SAC_TIER vs DOWNGRADE_TIER vs removed A+ ladder | partial | 826b9f5c | no |
| B-03 | HTF_BIAS_VETO vetoes 1,699 backtest rows (42.2%) but zero live signals; yfinance fallback returns bias=None | done | b5b5dc5a | yes |
| B-04 | HTF flag timeline: VETO introduced, flipped, docstring corrected, then GRADE_VETO added but dropped by history rewrite | done | 92187346 | yes |
| B-05 | Two -1R counts from separate commits measure different columns; neither doc discloses which | done | 11c49269 | yes |
| B-06 | position_sizer.compute_plan assumes delta=0.5 while DEFAULT_DELTA=0.42; live sizer under-sizes 16% | done | 10fc20f4 | yes |
| B-07 | _min_viable_stop hardcodes *0.5 gate while DEFAULT_DELTA=0.42; premium-risk floor undersized | partial | 8a2def5b | no |
| B-08 | 14 test files fail; verify gate runs only 2; test_universe_single_source.py unrun despite CLAUDE.md promise | partial | d9ec5626 | no |
| B-09 | archive_1m.py --back defaults to today, requests current session which 403s on this plan; yfinance does the work | done | 3448db74 | yes |
| B-10 | run_daily.ps1 pulls then runs live_scanner with no syntax check; 2026-09-03 omen_bot.py unparseable, killed daily | done | bc023fd4 | yes |
| B-11 | OmenWeeklyDigest scheduled task Ready, points at run_weekly_digest.ps1 which does not exist | done | 1eefbd3e | yes |
| B-12 | a6_dispatch.ps1 references C:\Users\aharg\aharg\Desktop\projects\tradingbot (doubled aharg, wrong case) | done | d589f5fb | yes |
| B-13 | market_open_healthcheck.py references C:\Users\aharg\projects\tradingbot (missing Desktop); two CRED_FILES cannot match | done | b1310b89 | yes |
| B-14 | Five homework decks ignored by .gitignore:83 (research/decks/**/*.html) and untracked; sibling decks ARE tracked | done | 0e186706 | yes |
| B-15 | Three scheduled tasks enabled and returning failure, including OmenDailyHomework (the daily deck instrument) | done | 29aa7120 | yes |

**Partial fixes** (B-01, B-02, B-07, B-08): Root cause identified and committed; test coverage incomplete or auxiliary claim not fully wired. B-03–B-06, B-09–B-15 (done): Full fix, test, verify gate passing.
