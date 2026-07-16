# G5 — YouTube Remainder Mine (458 skipped transcripts)

**Date:** 2026-07-14
**Task:** Omen queue G5. Mine the 458 YouTube transcripts B5 skipped (score <12, ranks 101–558) — swing/long-term focus, day-trade deltas secondary.
**Source set:** `youtube_data/*_transcript.txt` (558 files). B5 ranked → top 100 extracted into `scarface-rules-youtube-2.md`; 458 skipped.
**Baseline diffed against:** `hallucination-audit.md`, `scarface-rules-videos.md` (§swing incl. `bonus_How_To_Swing_Trade_Q_A`), `scarface-rules-youtube-2.md`, `scarface-rules-accelerator.md`, themed `youtube_batches/batch_001–019.md`.

---

## COVERAGE — exactly how many of the 458 were covered

- **458 / 458** title + full-text keyword-scanned (swing/HTF signal scored on entire transcript, not B5's 3KB title-biased window).
- **129 / 458** already cited in the themed `youtube_batches/batch_001–019.md` (their day-trade methodology was captured in the prior B1/B5 extraction and consolidated into `scarface-rules-youtube-2.md` top-100). These are "covered by prior pass," not re-extracted here.
- **329 / 458** were NEVER cited in any batch — the truly unmined set.
- **14 / 329** unmined deeply mined here:
  - **12** via DeepSeek (`research/g5_extract.py`, same key/env as `run_b1_extraction.py`; raw output `research/g5_deepseek_raw.md`, cached `research/_g5_interim/g5_00–11.md`): the top-12 unmined by swing-signal — all large weekly-recap / live-session files (100–190 KB each).
  - **2** full-read (small, 9.5 KB + 11 KB): the only swing-*titled* skipped files — `oIF2iRfSKxo` (NVDA SWING $18k) and `vgc5IVOBaoE` (TSLA & AAPL Swing $24k).
- **315 / 329** unmined NOT deeply mined — only keyword-scored. These are overwhelmingly trade-review / live-session chatter (210 live-sessions + 139 trade-reviews + 55 weekly-recaps + 54 other). **Honest gap:** I did not LLM-extract all 329. Cost/time cap. The 12 chosen were the highest-signal; the remaining 315 are lower-signal by the same score that put them in the skipped pile. Low expected yield, stated not assumed — but unverified.

**Verdict on the B5 hypothesis ("swing content was down-ranked by day-trade keywords"):** *Partially confirmed, weaker than expected.* The skipped set contains NO dedicated swing-teaching video (the dedicated swing course, `bonus_How_To_Swing_Trade_Q_A`, was already in B1's course set, not skipped here). What was down-ranked is swing-flavored *trade-review* and *live-session* content where HTF/swing mechanics appear inside day-trade reviews. The swing signal is real and additive, but it is *applied* swing technique scattered across recaps, not a missing swing curriculum.

---

## SECTION (a) — DAY-TRADE RULE DELTAS vs existing rulebooks

New rules or contradictions only. Existing rulebooks already cover core B&R, one-candle-rule≡OB, 84% reclaim-entry + thesis-gate + multi-try, OB (up/down-close, body, weekly), key levels, time-of-day/news, exits (scale 80–90% at key levels, scale up not down for 0DTE), 0DTE rules, A/A+ grading, QQQ alignment, displacement/FVG, stop-after-win (informal).

### A1. Opening-play hierarchy — NEW 3-tier entry ranking (contradicts ORBD-as-primary)
**Dip-in-rip > reclaim > opening-range break & retest.** OR break is the *last* entry model, not the first. Reclaim is "not usually recommended / we don't teach this one that much" — tension with 84%-rule reclaim-as-primary.
> "One of the best entry models is going to be a retest of some sort of dip coming to market open… Number two, you could be looking for the reclaim… number three… opening range break and retest." (1S50NNAGTs0, [2793s–2875s])
> "The opening range break is basically the last entry model, the last potential entry point." (1S50NNAGTs0, [2727s–2732s])
> "dip first because we already tap into your higher time frame objective… breaks back above your opening range candle… one of the most bullish setups." (FF4SsAn19go, [2234s–2284s])
Corroborated across 4 sources (1S50NNAGTs0, FF4SsAn19go, PBGB2UXaTVQ, Q0XC_SuWA4o). This is the strongest day-trade delta in the skipped set.

### A2. Five opening-play types — NEW structural framework
> "five different types of opening plays… opening drive, dip and rip, pop and drop, gap and go, gap fill… within the first 30 minutes." (Q0XC_SuWA4o, [692s–704s]; also PBGB2UXaTVQ [1974s])
Existing rulebooks list opening plays generically; this is a named 5-type taxonomy.

### A3. Opening play / OR-break requires an HTF objective — NEW gate
> "The opening play only happens whenever there's a clear higher time frame objective." (Q0XC_SuWA4o, [744s]; PBGB2UXaTVQ [1943s])
Without HTF context the B&R / OR-break model is ~50/50: "Without any higher timeframe context… this model itself is around like 50-50." (PBGB2UXaTVQ, [2409s]; FF4SsAn19go [1464s–1529s] "strictly five minute opening range break ~50% win rate"). Quantifies baseline edge = 0; HTF thesis is the edge.

### A4. Timeframe conditional on opening play — NEW rule
> "If you have an opening play, you're on the one minute. If you don't have an opening play, do not be on the one minute." (Q0XC_SuWA4o, [2289s–2308s])
1m only when there IS an opening play / HTF thesis; otherwise 5m. Reinforced by hFA1M_-mnJA "in chop 1m too choppy, 5m saves you" ([3479s]) and 92E4rnrCewE power-hour → 5m ([1878s]).

### A5. First-touch avoidance at major levels (esp. ATH) — CONTRADICTION
> "The first time price comes up to a key level, you don't really want to be buying the break and retest off a higher [level]… wait for a pullback." (SO38Y2XyLzU, [727s–745s])
Contradicts the implicit "any valid B&R is tradeable." First touch of ATH → do NOT buy B&R; wait for pullback then second break.

### A6. Displacement is OPTIONAL for B&R — CONTRADICTION
> "You don't have to have displacement on a break and retest… price will have an uptrend, sometimes doesn't have displacement, bases, then launches." (SO38Y2XyLzU, [549s–560s])
> "Immediate rebalance… no displacement whatsoever… super weak / super strong." (92E4rnrCewE, [2999s–3034s])
Contradicts the displacement-as-B&R-validity-component reading. Displacement grades *strength*, not *validity*. (Note: 92E4rnrCewE also defines displacement = FVG, three-candle non-overlapping wicks [2944s] — a precise definition to reconcile against Omen's `displacement_gate`.)

### A7. "Open-and-dry" / immediate-retest subtypes — NEW
> "Within the first 30 minutes price may tap a key level and launch immediately, no displacement. Entry window 10–20 seconds." (SO38Y2XyLzU, [564s–577s])
Distinct B&R subtype with a 10–20s execution window.

### A8. Order-block drawing = wick-to-body (top of wick → top of body) — NEW precision
> "The highest probability order blocks happen from the wick to the body. Stop goes at the bottom of the full candle." (SO38Y2XyLzU, [1303s–1314s]; 6o0XFgLEHp8 [2143s], [3141s]; Q0XC_SuWA4o [1636s])
Refines OB beyond "down-close candle, body strength." Bounce zone is wick-top→body-top; stop = full-candle bottom. If no top wick, draw body-to-wick.

### A9. Continuation OB vs reversal OB — NEW classification
> "Reversal order block needs break of structure / market-structure shift. Continuation order block only needs a candle closure above the level." (SO38Y2XyLzU, [1773s–1793s])
Omen's OB usage is the continuation variant; this names it and adds the reversal variant (BOS-required) Omen does not code.

### A10. Pre-market order blocks invalid — NEW rule
> "Don't mark order blocks on the pre-market — only key levels." (SO38Y2XyLzU, [3202s–3210s])
Pre-market: key levels only, no OBs (no order-flow confirmation yet).

### A11. Failure to retest = bullishness signal — NEW diagnostic
> "If price doesn't come back to retest, that's when price is so bullish and in a hurry." (SO38Y2XyLzU, [3116s–3128s])
Absence of retest is itself a trend-strength signal, not a missed entry.

### A12. Internal vs external liquidity — NEW unifying frame
> "All entry models (OB, B&R, OR-retest, PMH/PML retest) are *internal liquidity* tools targeting *external liquidity* (PDH/PDL, weekly H/L). Internal→external = continuation; external→internal = reversal." (ZFPnTRx_gQI, [363s–552s])
Reframes B&R/OB not as standalone setups but as internal-liquidity-seeking tools. Gap-fill = external→internal = reversal = rarely taken.

### A13. Inside-bar day — NEW setup + diagnostic
> "Inside bar day = built-up liquidity; break of inside bar targets outer range, best on daily for trend continuation." (ZFPnTRx_gQI, [660s–883s]; mit6szJg9Xs [1026s–1114s]; 6ChwEX15uYI [2879s])
> "First 5 minutes reveals whether it expands or chops." (mit6szJg9Xs, [1085s–1114s])
> "Don't trade an inside-bar day — high chop risk, unless it produces an opening drive." (6ChwEX15uYI, [2780s])
Already partially noted in youtube-2.md (#8) from a top-100 source; the skipped sources add the *trade-the-break* spec and the avoid-unless-opening-drive caveat.

### A14. Gap-fill probability + breakaway gap — NEW numbers/concept
> "Gaps fill ~70% within 48 hours." (ZFPnTRx_gQI, [2458s]; Ng5MJTUFldg [343s]; 6o0XFgLEHp8 [1552s])
> "Breakaway gap = gap that does NOT fill, requires external news catalyst." (Ng5MJTUFldg, [370s–415s])
> "Gap-and-go = gap above key resistance + immediate bullish momentum + earnings catalyst." (ZFPnTRx_gQI, [1547s–1678s])
Quantifies gap-fill base rate and distinguishes non-filling breakaway variant (news-required).

### A15. Day-one earnings continuation — CONTRADICTION of "avoid overextended"
> "Day one earnings: expect continuation, rarely a day-one reversal (90% continuation)." (mit6szJg9Xs, [445s–449s], [1537s–1553s])
> "Red-folder 830 news ≠ earnings: red-folder = wick/reversal-prone, low continuation." (mit6szJg9Xs, [2832s–2870s])
Contradicts "avoid overextension" on earnings day specifically. Splits "news" into reversal-prone (red-folder econ data) vs continuation-prone (earnings).

### A16. Consolidation-before-news → big-move-after — NEW rule
> "If consolidating before a major news event → big move after. If big move before → news doesn't affect you." (mit6szJg9Xs, [1571s–1583s])
Operational news filter: pre-news range compression = post-news expansion play.

### A17. 11am cutoff refined (exceptions) — REFINEMENT
> "Don't take entries after 11 unless A+ setup or market trending." (92E4rnrCewE, [1832s–1859s])
Refines the cutoff-11:00 flag (validated in F1) with two named exceptions.

### A18. 10am macro-zone pullback — NEW time rule
> "Around 10 o'clock, reversals / pullback — macro zone 10min before/after, liquidity injection." (6o0XFgLEHp8, [1012s]; "second pullback into OB is often the better trade" [1171s])
Adds a second intraday time-node (10am) beyond the open and the 11am cutoff.

### A19. A+ failure rate + A+ = all-timeframes-aligned — NEW stat/definition
> "A+ setups rarely fail, ~90% of the time." (ZFPnTRx_gQI, [3148s–3167s])
> "A+ = all timeframes aligned, based off HTF setups." (92E4rnrCewE, [2911s–2916s])
Quantifies A+ (backtest showed A/A+ *inverted* vs B at 30.9%W vs 36.6%W — this source claims ~90% for A+; flag for the hallucination audit: source-claimed vs backtest-observed diverge).

### A20. Confirmation vs aggressive entry trade-off — NEW explicit
> "Wait for confirmation → higher win rate, lower R:R. Buy on tap → lower win rate, higher R:R." (92E4rnrCewE, [2742s–2814s])
Existing rules describe only the confirmation entry; this names the trade-off and the aggressive variant.

### A21. First-scale timing + max-drawdown by setup — NEW numbers
> "Best first scale ≈ 1 hour after entry." (92E4rnrCewE, [2903s])
> "A+ drawdown limit 20–30%; scalp 10–20%; beyond = bad entry." (PBGB2UXaTVQ, [760s–770s])
> "Scalp ~50% win rate, avoid in chop." (92E4rnrCewE, [899s–1703s])

### A22. Stop-width ties to entry timeframe — NEW
> "1-minute thesis = tight stop; higher-timeframe thesis = deeper stop." (1S50NNAGTs0, [1619s–1627s])
Entry timeframe dictates stop width — not in existing rules.

### A23. Instrument: futures > SPY/SPX options intraday; tech names for continuation — NEW preference
> "Futures preferred over SPX options intraday; don't like 0DTE SPX." (Q0XC_SuWA4o, [2564s–2575s]; hFA1M_-mnJA [3387s])
> "SPY/QQQ mostly range-bound (gap fills, reversals); tech names for continuation B&R." (FF4SsAn19go, [1627s–1655s])
Bears on Omen's SPY-options + QQQ-alignment design: source prefers futures for index intraday and individual names for continuation.

### A24. Position size = dollar-equivalent across tickers, not contract-equivalent — NEW
> "Same contract count on TSLA vs AAPL = ~4× risk discrepancy; size by dollar risk." (Ng5MJTUFldg, [1632s–1674s])
Omen uses flat-$ risk (D1) — this *confirms* Omen's sizing and gives the source citation for why.

### A25. IV/theta can break an underlying stop — NEW options nuance
> "Underlying stop didn't protect — juiced IV + theta wrecked the contracts." (Ng5MJTUFldg, [2286s–2294s])
Options-specific: a correct underlying stop can still lose on IV crush/theta. Relevant to Omen's stop placement on options.

### A26. Relative-strength threshold + divergence dispreferred — REFINEMENT
> "Relative strength only matters when extreme — one-second chart read." (Q0XC_SuWA4o, [2084s–2090s])
> "Don't like divergence; prefer relative strength/weakness; divergence can kill the thesis. News trumps everything — can trade divergence with a catalyst." (6ChwEX15uYI, [637s], [762s])
Refines C6/QQQ-alignment: RS must be extreme to be actionable; divergence is a weaker signal except post-news.

---

## SECTION (b) — SWING / LONG-TERM break-and-retest content

Diffed against `scarface-rules-videos.md` §swing (`bonus_How_To_Swing_Trade_Q_A`): baseline already covers swing = HTF-consolidation-after-move → impulse; trend intact via higher lows; entry 4H/1H, execute 10–15m; swing less about precision; scale in on retest; HTF thesis→1m OR else 5m; choppy 50% off HOD / trending 10–25% off; market designed to go up.

The skipped set ADDS concrete position-management, selection, and HTF-routine detail the course bonus lacks. **Swing-heavy sources** flagged below with ★.

### B1. HTF charting routine (top-down) — NEW concrete procedure ★ `oIF2iRfSKxo`
Full read of NVDA swing review yields a named top-down routine:
> "Daily: mark high/low of candle + pivots near higher low; green=HTF resistance, red=HTF support; note how the candle closes. → 4H: patterns + key pivots; flat-top consolidation break = momentum. → 1H: next support levels, wait for pre-market. → 1m: mark pivots where most touches. Cap: at most ~9 key levels — over that is noise." (oIF2iRfSKxo, [222s–437s])
This is the operational HTF-markup spec the course bonus only sketches.

### B2. Swing timeframe requirement — REFINEMENT
> "Swing needs weekly + daily + 1H aligned; the 5m can be bearish because you're in a higher-timeframe move. Buy swings when 5m is bearish (pullback) — as soon as 5m flips bullish, every chart aligns." (1S50NNAGTs0, [2021s–2062s])
> "Day trade needs only 1H + 5m. Swing needs every timeframe in check." (1S50NNAGTs0, [1951s–1968s])
> "If you can't build the thesis on higher timeframes, you have no business on lower timeframes." (1S50NNAGTs0, [3036s–3039s])
> "Swing: I like focusing on the one-hour — key timeframe — then drop lower for entries." (SO38Y2XyLzU, [3176s–3192s])
Refines baseline "entry 4H/1H": weekly+daily+1H *alignment* is the gate, not just 4H/1H. 5m bearish = entry opportunity, not a stop-out.

### B3. Swing = same B&R on higher timeframe — CONFIRMATION + twist ★ `FF4SsAn19go`
> "Swing is the exact same break-retest-continuation but on higher timeframes." (FF4SsAn19go, [3158s–3201s])
> "Swing needs more room on options contracts." ([3206s])
> "Swing lets the trade develop, reduces overtrading; clear thesis + clear risk level, wait." ([3224s–3265s])
> "Pre-earnings chop — don't trade inside range before catalyst; TSLA only interesting above 222/223." ([3377s–3399s])

### B4. Swing selection — consolidation-not-pullback = strength ★ `vgc5IVOBaoE` (strongest)
> "AAPL swing: clear uptrend → bull flag / flat top → break above previous highs. Consolidation (not pullback) = stock stronger than the rest." (vgc5IVOBaoE, [48s–123s])
> "For swings I'm looking for HTF consolidation after a move — that's where the impulse comes. Consolidation vs pullback = good signal for upside." (scarface-rules-videos baseline; reinforced here)
> "Long consolidation (2023→present) + news catalyst = strong swing; consolidation = accumulation." (Ng5MJTUFldg, [686s–701s])

### B5. Sympathy / correlation + leader-follower — NEW swing selection ★ `vgc5IVOBaoE`, `Q0XC_SuWA4o`
> "Don't play NVDA earnings directly (IV crush); play the correlation — strongest tech setting up = AAPL. New CFO news was a bonus catalyst." (vgc5IVOBaoE, [110s–168s])
> "SPY is the leader, QQQ second, tech names lag — if ES/SPY/QQQ push up, NVDA follows." (Q0XC_SuWA4o, [216s–489s])
> "NVDA/AMD both swing candidates simultaneously (correlated)." (hFA1M_-mnJA, [2242s–2288s])

### B6. Swing position management — sizing, scaling, drawdown ★ `vgc5IVOBaoE`, `oIF2iRfSKxo`, `hFA1M_-mnJA`, `Ng5MJTUFldg`
**Size down, not up:**
> "Don't size up aggressively on swings; play with profits from the prior week; let percentage work." (vgc5IVOBaoE, [412s–429s])
> "Swing = lower position size, wider stop (30–50% on options). Day trade = 10% stop; swing = 30–50% because price can be down 20–30% with thesis intact." (hFA1M_-mnJA, [4399s–4419s])
> "Size for −50% drawdown because news can happen." (Q0XC_SuWA4o, [1344s–1351s])
**Scale IN on drawdown (contra B10):**
> "AAPL was down 30–40% at one point — that's where I scaled more in for the next move." (vgc5IVOBaoE, [491s–498s])
> "Swing: starter position, then ADD ON STRENGTH (not on drawdown)." (hFA1M_-mnJA, [2891s–2895s]) — ⚠ **internal contradiction across sources** (vgc5IVOBaoE scales in on drawdown; hFA1M_-mnJA adds on strength). Flag both; do not ingest as one rule.
**Scale OUT ladder:**
> "Swing scaling: 25% at first key level, 25% at next, 25% at next, leave 25% with a hard stop; use OBs as trailing support." (Ng5MJTUFldg, [2867s–3074s])
> "Swing: scale in quarters toward upside." (6ChwEX15uYI, [3225s])
**Hold through pullback / let runners go:**
> "Maintain through intraday pullbacks; ~1.5 weeks to expiry, price comes down but holds key areas." (1S50NNAGTs0, [2569s–2578s])
> "Hold trailers overnight; let last contracts go to −60% or to zero if thesis intact (hold through AMD earnings)." (oIF2iRfSKxo, [65s–138s])
> "For deep-ITM swings, set alerts and walk away — don't micromanage." (Ng5MJTUFldg, [3060s–3074s])
**Exit before news:**
> "Offload 50%+ before FOMC — you don't know what happens." (hFA1M_-mnJA, [4326s–4337s])

### B7. Swing stop = HTF level break (deeper than day trade) — CONFIRMED + specified ★
> "Swing stop is deeper — all the way down at the HTF level." (1S50NNAGTs0, [1578s–1586s])
> "Bottom of the HTF order block is your stop." (SO38Y2XyLzU, [2884s–2888s])
> "Stop = break below key HTF level (e.g., daily OB 922)." (6ChwEX15uYI, [1088s])
> "Risk is based off the underlying, not the options contract." (hFA1M_-mnJA, [4088s–4115s])

### B8. Swing contract selection — NEW
> "Swing: a couple strikes OTM for targets; weeklies or next-week's contracts (avoid theta)." (1S50NNAGTs0, [650s]; hFA1M_-mnJA [4099s])
> "vgc5IVOBaoE: couldn't ride AAPL swing to ATH because Friday-expiry contracts + theta decay — exit when expiry forces it." (vgc5IVOBaoE, [199s–237s])
> "Use delta (not options price) for swing stops; options price for intraday." (Q0XC_SuWA4o, [2860s–2873s])

### B9. Swing targets — HTF external levels, fibs, psych, old pivots — NEW hierarchy ★
> "Swing targets = external HTF levels (old highs/old lows), not PDH/PDL." (6ChwEX15uYI, [3014s]; ZFPnTRx_gQI [1815s–1841s] "weekly objective 161→164")
> "After all-time highs met, targets shift to fib extensions + key psychological levels + old pivot highs." (Ng5MJTUFldg, [492s–512s])
> "Swing PDL as profit zone — trend traders sell at/under PDL." (92E4rnrCewE, [1063s–1092s], [1231s–1243s])
> "Swing first scale ≈ 1 hour after entry." (92E4rnrCewE, [2903s])

### B10. Swing thesis patterns — NEW named setups ★
- **Flat-top break** (4H/1H) = strength: "Flat top break, holding majority, not selling until major targets." (1S50NNAGTs0, [1705s–1715s]; oIF2iRfSKxo flat-top from 4H+1H [49s–55s])
- **Daily wedge breakout + flip zone** (resistance→support): (6ChwEX15uYI, [786s], [1697s])
- **Downtrend break + higher-low formation**: (Q0XC_SuWA4o, [69s–91s], [593s–597s])
- **Inverse H&S on daily/1H**: (6o0XFgLEHp8, [1381s])
- **Daily OB as support for pullback in uptrend**: (6o0XFgLEHp8, [3067s–3120s]; Q0XC_SuWA4o [1844s]; 6ChwEX15uYI [2379s])
- **One down-close candle in a multi-day run = the daily OB**: "9-day run with one down-close candle = your daily OB." (SO38Y2XyLzU, [2498s–2508s])
- **Stair-stepping via down-close candles**: (SO38Y2XyLzU, [2538s–2549s])
- **First major dip after a news event = high-quality swing entry**: (Ng5MJTUFldg, [2348s–2386s])
- **Inside-bar day on a stock = next-day continuation swing**: (hFA1M_-mnJA, [4638s–4650s])

### B11. Swing market-regime / bias — NEW rules ★
> "Bull market: 80–90% of trades are long; don't short the bull / guess the top." (SO38Y2XyLzU, [182s–195s])
> "Above prior ATH → always look for longs." (SO38Y2XyLzU, [127s–133s])
> "Down days are when you want to be looking to buy." (SO38Y2XyLzU, [1008s–1011s])
> "Don't try to guess the top — shorting TSLA through the run = ~10% chance." (1S50NNAGTs0, [750s–841s])
> "V-shape recovery after a strong move is rare — can hold through pullbacks." (92E4rnrCewE, [2196s–2206s])
> "News = exit liquidity for reversals." (SO38Y2XyLzU, [833s–843s])
> "Trending HTF = trade; consolidating HTF = chop, size down or skip." (SO38Y2XyLzU, [2579s–2604s]; FF4SsAn19go [3329s–3363s])
> "Post-earnings volatility window — tradeable for weeks/months." (mit6szJg9Xs, [1661s–1683s])

### B12. Swing vs day-trade distinction (entry precision) — CONFIRMED + expanded
> "Swing is not about precision — you can be wrong on entry; day trade wants the exact candle." (baseline; reinforced mit6szJg9Xs [2089s–2116s], [2213s–2258s])
> "Entry anywhere in the zone; the risk level is what matters." (mit6szJg9Xs, [1845s–1865s])
> "Swing = momentum trade, target HOD/LOD, OTM contracts; day trade = target pivot levels." (92E4rnrCewE, [3246s–3272s])
> "Swing: lower timeframes ONLY for entries, exits on HTF objectives." (Ng5MJTUFldg, [3149s–3156s])

### B13. "Context is king, zoom out" — NEW swing judgment heuristic ★
> "If zoomed in on lower TF you'd think the market's crashing; on higher TF you see how small the pullback is." (SO38Y2XyLzU, [1219s–1247s])
> "Context is king. When in doubt, zoom out." (SO38Y2XyLzU, [1393s–1396s])

### B14. Swing performance judgment — NEW criteria
> "Getting killed on swings lately = no solid HTF setups, not strategy failure." (Q0XC_SuWA4o, [1313s–1318s])
> "Apple repeatedly failing at key level because of recurring news — news is the disruptor." (Q0XC_SuWA4o, [1357s–1371s])
Trade-review judgment: attribute swing loss to *absence of HTF setup* or *news disruption*, not to the swing framework itself.

---

## HEADLINE FINDINGS

**Coverage:** 14/329 truly-unmined deeply mined (12 DeepSeek + 2 full-read); all 458 keyword-scanned; 129 already in themed batches. 315 unmined only keyword-scored — honest gap.

**(a) Day-trade deltas — material, not nothing.** Highest-value:
1. **Opening-play 3-tier hierarchy (dip > reclaim > OR-break-last)** — contradicts OR-break-as-primary; 4-source concord.
2. **Displacement is OPTIONAL for B&R** — contradicts displacement-as-validity; regrades it as a strength grade. Reconcile vs Omen `displacement_gate` + 92E4rnrCewE's FVG definition.
3. **First-touch avoidance at major levels / ATH** — new entry filter.
4. **Internal/external liquidity frame** — reframes B&R/OB as liquidity-seeking tools.
5. **Day-one-earnings continuation** — contradicts "avoid overextension" on earnings.
6. **Order-block wick-to-body drawing** + continuation-vs-reversal OB split — new precision.
7. **Numbers:** gap-fill ~70%/48h; OR-break base rate ~50%; A+ source-claimed ~90% (vs backtest 30.9%W — audit flag); A+ drawdown 20–30%, scalp 10–20%; first scale ≈1h after entry.

**(b) Swing/long-term — the bigger, less-contradictory yield.** The skipped set does NOT contain a missing swing curriculum (course bonus already captured). It DOES add:
- **Concrete HTF charting routine** (daily→4H→1H→1m, ~9-level cap) — `oIF2iRfSKxo`.
- **Swing timeframe alignment gate** (weekly+daily+1H; 5m bearish = entry).
- **Position management**: size down / 30–50% options stop / scale-out 25-25-25-25+hard-stop / hold through 20–60% drawdown if thesis intact / exit 50% before FOMC. ⚠ **source contradiction on scaling in**: vgc5IVOBaoE adds on drawdown, hFA1M_-mnJA adds on strength — do not ingest as one rule.
- **Selection**: consolidation-not-pullback = strength; sympathy/correlation (NVDA→AAPL); leader-follower (SPY>QQQ>tech).
- **Stop = HTF level break (bottom of daily OB)**; risk off underlying not contract.
- **Targets**: external HTF old H/L, fibs, psych, old pivots; swing-PDL as zone.
- **Named patterns**: flat-top break, daily wedge+flip, downtrend break+HL, inverse H&S, daily-OB-as-support, first-dip-after-news.
- **Bias**: 80–90% longs in bull market; down days = buy; no top-guessing; V-shape rare.

**Swing-heavy sources** (for future swing-bot ingestion): ★ `oIF2iRfSKxo` (NVDA swing, full HTF routine), ★ `vgc5IVOBaoE` (AAPL/TSLA swing, sizing+scaling+correlation), ★ `SO38Y2XyLzU` (HTF/DRAW-on-liquidity doctrine), ★ `1S50NNAGTs0` (swing vs day timeframe gates), ★ `FF4SsAn19go` (swing=same-B&R-on-HTF), ★ `Ng5MJTUFldg` (swing scaling ladder + targets), ★ `Q0XC_SuWA4o` (swing sizing/contracts/leader-follower), ★ `6o0XFgLEHp8` (weekly OB + post-impulse pullback), ★ `mit6szJg9Xs` (earnings swing thesis).

**Honest "nothing new" verdict:** NOT claimed — real additive content found in both sections. But (a) deltas lean on trade-review commentary (lower-confidence than course rules); (b) has one cross-source contradiction (scale-in timing) and one source-vs-backtest divergence (A+ 90% claimed vs 30.9%W observed) that must be flagged, not silently ingested.
