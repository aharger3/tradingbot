# Extraction agent instructions (OMEN tradingbot research)

You are one of 36 parallel extraction agents. Your prompt names a GROUP NUMBER (0-indexed).

1. Read `C:\Users\aharg\tradingbot\research\video_transcripts\_extract_groups.json`. Your group = the list at your index. Each entry is a filename in `C:\Users\aharg\tradingbot\research\video_transcripts\`.
2. Read each transcript IN FULL. They are whisper transcripts of trading-course videos (Scarface/J-Dub, break-and-retest options day trading; performance-coaching files are by Neto).
3. Extract EVERY concrete trading rule:
   - setup definitions (B&R, order block, reclaim, reversal, dip&rip, gap fill, gap&go, opening drive, pop&fade, PMH/PML retest, etc.)
   - entry/exit/stop/target mechanics, confirmation candles, invalidation
   - numeric thresholds: %, cents, R:R, times of day, candle counts, level counts
   - level-drawing rules, sizing rules, risk-management rules
   - market-structure / index-alignment (QQQ/SPY) rules
   - options contract selection (strike, expiration, delta)
   - KPI/journaling rules; psychology ONLY if actionable (e.g. "2 losses = done for the day")
   - internal contradictions between statements
4. If the exact phrase "one candle rule" or "84%" appears, capture the FULL definition verbatim — high priority.
5. Format: each rule = a bullet with a verbatim quote + `(filename, [Ns-Ns])` timestamp from the transcript line. Skip generic motivation/biography/UI walkthroughs.
6. Write output to `C:\Users\aharg\tradingbot\research\videos_extract\part_NN.md` (NN = your zero-padded group number), one H2 section per source file.
7. Final message: one line per file — `filename: N rules`. Nothing else.
