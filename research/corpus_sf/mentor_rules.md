# The mentor rulebook — a ballot, not a change set

**These are Scarface's, Jdub's, Neto's, Lauren's, Mamba's and Hayden's rules. They are not
yours.** Nothing in this file has been wired into the engine and nothing will be until you
say so. The standing rule holds: the corpus validates rules you state, it never invents them.

Three lists below.

- **Agrees** — a mentor says the same thing you already said. That is free evidence for a rule
  the engine already has. Nothing to decide.
- **Conflicts** — a mentor says the opposite of something you said. Surfaced, not resolved.
- **New** — a mentor says something you never have. **This is the ballot.** Fifteen lines,
  each a yes/no. Everything you skip stays parked.

---

## How this was built, and how much to trust it

A deterministic parser, not a model reading messages. `parse_mentor_rules.py` pools every
mentor sentence out of the mined channels, keeps only the ones that are *instructions*
(they tell you to do something, they name something in trading, they are not about one chart
on one morning), buckets them into eight topics, and pools restatements.

| | |
|---|---|
| mentor sentences scanned | 8,790 |
| survived the rule filter | 238 |
| distinct rules after pooling restatements | 225 |
| hand-checked precision | **25 of 30 (83%)** |

The 5 misses in the hand-check were trade stories and platform how-to that read like rules.
Earlier versions scored 27% and 60%; the fixes were dropping the live-alert channels to a
stricter filter, and throwing out any sentence that names a ticker, a price, or "today".

**One honest negative.** You would expect a core rule to be said forty times. It is not.
The most-repeated rule in this corpus was said **7 times**; only 21 of the 225 were said 5
times or more. These men teach in prose, once, and then trade. So frequency ranks the ballot
but it does not carry it — how much a rule would change the engine matters more, and that
is what the ordering below is weighted on.

---

## Agrees — 31 rules, and the five that matter

Free validation. No action.

**Closes are evidence, wicks are not.** You settled this five times. Five mentors say it
independently, in five different channels:

> "cutting your Trade only if the candle **closes** beyond your invalidation level" — Neto
>
> "I'd have my Stop Loss at the top of the previous candle and **wouldn't close my Trade
> unless a candle closing above that SL**" — Neto
>
> "waiting for **candle closes** is important to ensure price action is bullish/bearish" — Scarface
>
> "Never got a **5m body close** below level" — Mamba
>
> "we should only trade a **strong closure** above that level, anything below is chop" — Scarface

**You don't need a higher-timeframe bias for an opening-range break.** You said *"we dont have
any higher timeframe bias yet"* and the veto was deleted. Jdub, unprompted:

> "Typically you don't need a higher time frame bias for the opening range break"

**One good trade a day.** Your day policy, in the mouth of the man your rulebook already
credits it to:

> "Remember **1 good trade is all you need a day**, don't over trade and get greedy — the
> market will be here all the time, your capital may not" — Scarface

**Your three stop placements are the mentors' three stop placements.** You said *"level,
bottom of candle entered on, pivot structure."* Lauren, across three separate posts: stop
just below the retest level; stop below the wick of the rejection candle; *"Swing Highs/Lows
— use recent pivots as stop points."* Nobody named a fourth.

**Size off the stop, not off a fixed number.** You reopened fixed $1,000 risk this week
because the stop is no longer fixed. Lauren already trades that way:

> "I usually size my contracts based on **the stop level and structure, not a fixed number**"

The other 26 agreements cover displacement before the retest, HOD as the first target, letting
runners go to the next level, not sizing up on confidence, and not every opposite-colour candle
being an order block.

---

## Conflicts — 14, surfaced and left open

I am not resolving these. Three are worth your eyes.

**1. Scarface waits out the first five minutes. You say the opposite, and the tape backs you.**

> "wait for first 5 min to form and only take a trade after that if it presents with strong
> price action" — Scarface

Your golden rule is *"the earlier in the day you trade, the more common it is for S trades."*
Your held-out S entries run 9:34–10:19, median 9:42, 65% before 9:45. The 09:40 floor already
costs 10 of your 34 S days. Jdub pushes the same direction, harder — *"if your stats show
the majority of your losses come from the first 5 minutes, there should be no reason you trade
for the first 30 minutes."* **This is the largest disagreement in the corpus.**

**2. Everyone else takes a fixed 2R. You proved a fixed 2R can never average 2R.**

> "The primary TP1 should **always** be set at a 1:2 risk-to-reward ratio" — Lauren
>
> "1–3 cons I generally say sell your whole position anyways at around **1.5–2R** as a rule
> of thumb" — Hayden

Hayden's is the sharper clash: selling the whole position removes the runner you named as the
only lever that reaches the money gate.

**3. The first scale-out slice: three mentors, three different numbers, none of them yours.**
Yours is 30% at HOD. Jdub takes ~80% off at HOD when scalping. Hayden takes 75% inside 3:1R.
Your own 30/30/30/10 vs 50/20/20/10 question is still parked — these are votes in it.

The rest: trade caps (Lauren 1–2 a day, Mamba 8–15 a month, against your deleted cap),
Scarface switching to the 5-minute chart after 11:00, Lauren adding an ATR volatility stop as
a fourth family, Mamba resting a hard stop where Neto uses a mental one, and Jdub contradicting
*himself* on whether PMH/PML are worth marking.

---

## The ballot — 15 things they say and you never have

Ranked by how much the engine would move, then by how often it was said. Yes / no / ignore.

| # | The rule, in their words | Who | Said | What it would change |
|---|---|---|---|---|
| 1 | *"the **Retest** on a level is **never to the penny**, is always close to the line"* | Neto | 3 | A retest touch has no stated tolerance in the code. Your 25%-of-previous-candle unit governs the entry trigger, the 84% reclaim and stop slippage — this would be its fourth use, and it is nearly free. |
| 2 | *"the reclaim entry is stopping us from trading chop... we should only trade a **strong closure above that level**, anything below is chop"* | Scarface | 2 | A different anchor for `level_not_respected` — your highest-trip downgrade, which has failed three implementations and currently points backwards. Chop measured by the *strength of the breaking close*, not by bars after it. |
| 3 | Break → displacement → retest → **"strong reaction on the key level"**; and *"wait for how price **reacts** to your interest levels"*, not for more candles | Neto | 3+4 | Adds a fourth required element after the retest. The engine enters on the retest; this gates on the reaction to it. |
| 4 | *"Ideally if you want to take a trade intraday you **need this to break to hod or lod**"* | Scarface | 4 | Target availability as an *entry* gate. This is your own b4 (*"if there are no other levels to target... harder to trade"*) stated as a hard precondition. |
| 5 | The break-and-retest works everywhere, but **which level family works best is per-ticker** — *"backtest and define if it works better for your ticker on the Pre Market levels, Previous Day levels, 1min/5min ORB"* | Neto | 3 | Your six levels are closed and applied uniformly. This says the *weighting* among them should be per-symbol. Cheap to measure — you already asked for per-symbol, per-level slices. |
| 6 | *"If reward potential is smaller, I'll usually **secure profits more aggressively**"* | Neto | 2 | Unparks your own q4: *"30 percent is when better chance stock runs, 50 for choppier — we must identify this."* He names the discriminator: available reward at entry. |
| 7 | Higher-timeframe context = *"weekly, daily, 4H to identify the overall trend, key levels, and liquidity zones"*, and *"it needs to be paired with market conditions and HTF trend"* | Lauren, Mamba, Jdub | 5+4+4 | You asked *"youll need to tell me what that is then."* Three mentors answer. Adopting it would re-gate what you deleted, so it is a definition question first. |
| 8 | *"Highest probability trades are always generally **outside of previous days ranges** or above/below key levels"* | Hayden | 3 | A prior-day-range containment feature. Computable at 09:29, joins the premarket filter that already ships. |
| 9 | *"**hammer or inverted hammer** candles with long wicks inside our key level but **bodies respecting it**"* | Neto | 3 | A named retest candle shape. You said you find trends respect wicky candles better; you never named the shape. |
| 10 | *"I use **op** [the opening price] when there's no level or level is too far, so it gives me a reference point"* | Mamba | 2 | A concrete answer to your Q8 (*"find other targets"*). It would be a seventh reference, and your six are closed — so it is a ballot line, not a change. |
| 11 | **Specialise**: *"I only trade 4 names on a consistent basis"* · *"stick to one ticker one setup for a decent period"* · *"trade 1 ticker and backtest, then repeat"* | Neto, Scarface | 3+2+2 | You flagged that the book is unbalanced (COIN is 104 of 1,017 rows). Three mentors say concentration is the point, not the bug. |
| 12 | *"We **always take 1OTM** or contracts with the most volume"* — and strike matters less when scalping | Jdub, Neto | 3+6 | The options skin has no strike rule. You want reports led in dollars; this is the missing parameter that makes them real. |
| 13 | *"predefined trading hours · maximum number of trades per day · **mandatory break after a loss** · only trading predefined setups"* | Neto | 2 | A third option in the halt question you delegated to measurement. Not "stop at 2 losses" and not "trade until green" — pause after **one**. |
| 14 | *"On A+ setups I will **take starters** sometimes as I don't want to miss out on the move, so I don't mind if I don't have the greatest entry"* | Jdub | 3 | Scaling **in**. The engine has scale-out only; a starter position has never been on the board. |
| 15 | *"a wider stop-loss — usually **18–25% of the contract premium** at entry"* | Neto | 2 | A premium-side bound on the stop, feeding your *"won't get killed by fills or too tight RR"* constraint. Your stop is on the underlying; this caps what it may cost in the contract. |

---

## Files

| file | what it is |
|---|---|
| `research/corpus_sf/mentor_rules.jsonl` | 225 pooled rules, every verbatim restatement, author, timestamp, message id, and the agrees/conflicts/new verdict |
| `research/corpus_sf/parse_mentor_rules.py` | the parser — filters, topic buckets, clustering, frequency |
| `research/corpus_sf/xref_austin.py` | the cross-reference, with the rulebook line each verdict was matched against |

Read-only on every Austin mark corpus. Nothing was written to `research/austin_marks_v7.jsonl`,
`research/marks/`, or any other file holding your judgements.
