# OMEN 7.2 — MASTER SPEC

Written 2026-08-29 from Austin's session message. Supersedes `PHASES.md` as the dispatch
board for this version; `DIRECTION.md` still holds the invariants and `CLAUDE.md` still
holds the things you must not break.

**Rule for this document and everything it produces: plain English.** No track IDs, no
T-numbers, no R-numbers-as-tickets, no phase codes in anything Austin reads. He said it
straight: *"One track of 22 failed outright — stuff like that makes no sense to me, dont
speak in code."*

---

## 1. What this is actually for

> *"im overthinking everything the purpose of this was to make money, thats the simple
> layer, but also i wasnt sucessful on my own because i didnt have a system, were creating
> that system."*

The deliverable is **dollars per month from a prop account, produced by a robot, without
Austin watching**. Everything below is instrumental to that. Every report leads with the
dollar figure. R-multiples are the engineering unit and are never the headline.

Capital is a **prop firm account funded off a 0% APR credit line**, not his own money.
That makes the firm's drawdown rules **hard constraints**, and it sets the sizing objective
he stated: risk per trade is whatever gives a **90% chance of passing the challenge**.

---

## 2. The one thing that changed today

The whole book has been measured wrong, and Austin supplied the correction himself:

> *"all these s trades would not be done in one day, what would happen is we trade the s
> trade that comes up first, and if it wins, were done for the day."*

Every money number in this repo was computed over **every candidate the engine found**.
That is not the strategy. The strategy is:

1. Take the **first** good setup of the day.
2. If it wins — **stop. Day over.**
3. If it loses — take the next one, until the day is green (with some loss cap, which is a
   measurement question, not a question for him).

This is why the "money gate is unreachable" conclusion may have been an artifact. The unit
was wrong. The correct unit is **dollars per day**, and a one-trade-per-day selection was
already measured at **+2.2125R at 76.6% win** as an "oracle" ceiling. That ceiling was
never a fantasy — it was a description of how he trades.

**Nothing else in this spec is worth doing before this is measured.**

The full set of eleven rules he stated in the same message is recorded verbatim in
`Austin's Vault/Projects/omen-rulebook.md`, section *"Session 2026-08-29"*.

---

## 3. The four lanes

Four categories, four dispatchers. Each lane owns one question, has its own definition of
done, and does not need the other three to finish before it starts.

### Lane A — ACCURACY: does the engine see what Austin sees?

**The question:** when Austin says a day is an S trade, does the engine agree?

Today: **52.9%** (18 of 34 held-out S days). Target: **90%**.

**Done when:** held-out recall on a sample large enough to distinguish 53% from 90% at 95%
confidence, measured on the correct router, with S pooled consistently across every mark
corpus.

Known problems this lane owns:
- Recall is currently measured on the wrong router (last commit says so).
- S "is not pooling as the same" — the same symbol-day may carry different grades in
  different corpora.
- Measurements run on 25 or 100 cards when 1,057 judged symbol-days exist. Find out why.
- The 84% rule fires **3 times** in two years and the one-candle rule **67**, against
  break-and-retest's **947**. Both are almost certainly broken, not rare.
- Break-and-retest **plus** the one-candle rule together is a third setup and has never
  been represented as one.

### Lane B — INTEGRITY: is the code doing what the rules say?

**The question:** *"how much of it is just bugs and the codebase not following the rules."*

**Done when:** every rule in the rulebook has a row saying implemented / reachable /
matches-his-sentence, and every row is green or has a ticket.

Known problems this lane owns:
- The risk-reward cap was reported fixed and is not.
- `capture_runner` and `backtest_week.py` were never brought in line with the fill fix.
- 45,193 "signals" in two years against 2 actual promotions. A signal count that means
  "the engine looked at this" is not a signal count.
- A higher-timeframe level set is polluting the six levels Austin watches, which corrupts
  targets, which corrupts risk-reward, which corrupts scaling.
- Max drawdown is claimed to be a non-issue and is visible in the chart.
- The legacy `A+`/`A`/`B`/`C`/`X` letters. Ratified for deletion five sessions ago. Still
  there. **The delay is itself the finding.**
- The recurring bug class: a real rule becomes a branch that can never be true.

### Lane C — MONEY: what does it make, and how is it sized?

**The question:** *"what +r for money should i be targeting? … i need the financial
numbers."*

**Done when:** there is one page giving expected dollars per month, chance of a green
week, chance of a green month, worst drawdown, and the risk-per-trade that yields a 90%
prop-challenge pass rate — under the one-trade-a-day policy.

Owns:
- The day policy grid: first-trade-only vs stop-on-win vs 2-loss halt vs trade-till-green.
- The four-point scale-out he stated: 30% HOD / 30% at 2R-or-nearest-level / 30% break of
  structure / 10% runner at break-even. And the runner fraction sweep, because he correctly
  identified that as the only lever that makes 2R average reachable.
- Stop placement: level vs bottom-of-entry-candle vs pivot structure, chosen per trade by
  best tradable risk-reward, with a disaster stop underneath.
- **Tradability filter:** a stop too tight to survive spread plus slippage is not a valid
  stop, no matter what it does to the backtest. *"i want trades that can realistically be
  done by a robot."*
- Weekly green as a second durability gate.
- Which prop firm, which account size, and whether the instrument is options, shares, or
  index futures.
- What options data service to buy, and what it costs.

### Lane D — CORPUS: use the years of data already on disk

**The question:** *"it has trade reviews from scarface years of data, it could pool all of
those."*

He is right and it is bigger than he thought. `discord_data/` holds roughly **77,000
messages**: 6,692 Scarface alerts, 4,274 from jdub, 4,789 futures alerts, 670 written trade
reviews, 591 premarket chart posts with levels drawn, 21,441 P&L posts, 17,564 Q&A.

**Done when:** every extractable trade instance is pooled, deduplicated, checked for bar
availability, and the mentor rules are on a yes/no ballot for Austin.

**Hard boundary:** Scarface's judgements are **not** Austin's marks. They live in
`research/corpus_sf/` and are never merged. A mentor rule Austin has never stated is a
**ballot line**, never an engine change. The corpus validates rules Austin states; it never
invents them.

Also owns: are the videos and chart images stale, and is a multi-agent extraction team
actually needed or is it one backfill script.

---

## 4. What is running right now, unattended

| lane | dispatcher | what it is doing |
|---|---|---|
| A + B + C | **recon** (31 parallel tracks) | One track per sentence Austin wrote. Diagnosis only — produces exact diffs, applies nothing. Every measured claim is adversarially verified by an independent agent told to refute it. |
| D | **corpus mine** | Writes a deterministic parser per channel, mines 77k messages, hand-checks 45 rows per channel for precision, pools and dedupes, checks bar availability, builds the mentor-rule ballot. |

Neither needs Austin. Neither touches a mark file. Neither commits.

**Fires automatically when recon lands:**

| lane | dispatcher | gate |
|---|---|---|
| B | **fix** | Applies the verified diffs, re-runs the recall gate after each. Only diffs that survived adversarial verification. |
| C | **money** | Re-measures the day policy, scale ladder and stops on the fixed engine, then produces the dollar page. |

They are gated deliberately: measuring the money on a broken engine is what produced the
last five sessions of numbers Austin could not act on.

---

## 5. Unattended vs attended

Austin: *"hard to decide what should be unattended or attended."* Here is the line.

**Agents do without asking:**
- Any measurement, any A/B, any diagnosis.
- Any bug fix where the rule is already stated in the rulebook and the code diverges from it.
- Building homework pages (but not serving them).
- Corpus extraction, pooling, deduplication, bar-coverage accounting.
- Deleting code that is proven unreachable.
- External research — prop firm rules, data vendor pricing, model pricing.

**Only Austin:**
- Grading charts. This is the scarce input and nothing else can produce it.
- Any rule he has not stated. A mentor rule, a corpus pattern, an agent's good idea — all
  become ballot lines, never code.
- Money out the door: which prop firm, which subscription.
- Anything irreversible or outward-facing.

**Explicitly delegated to measurement, do not ask him:** the 2-loss halt versus
trade-till-green question. He said *"subagents will find the medium."*

---

## 6. Definition of done for 7.2

Three gates, unchanged in spirit, one added:

| gate | target |
|---|---|
| Accuracy | fires on ≥90% of Austin's S days it has never seen |
| Money | ≥55% win rate and mean **2.0R per day** under the one-trade-a-day policy — note **per day**, not per candidate |
| Durability | every month green **and** every week green |
| Sizing | a risk-per-trade that passes the chosen prop challenge ≥90% of the time |

Plus the standing method rule: **every A/B this project has ever run moved less than its
own ±1.5799R error bar.** Gate on held-out accuracy, never on mean R. If two arms are
inside the bar, say so instead of picking a winner.

---

## 7. The short list only Austin can clear

Each of these is under two minutes. Nothing below blocks the agents that are running.

1. **Which prop firm family** — futures (Topstep / Apex / MyFundedFutures) or stocks
   (Trade The Pool / Sure Leverage)? Most futures firms do not allow options, and the
   engine's best measured numbers are on options. Research is running; the pick is his.
2. **The three symbols for the next homework** — SPY plus two. He leans NVDA and TSLA and
   flagged his own bias. Data-driven ranking is running; he confirms or overrides.
3. **The mentor-rule ballot** — up to 15 yes/no lines from Scarface's years of posts,
   arriving from the corpus lane.
4. **The homework itself** — three symbols, chart with only the timeframe and his six
   levels drawn, the engine's guess at which setup it is, and he answers yes-this-is-S or
   no-and-here-is-why. Being built now, not served until the accuracy lane says the batch
   composition is right.

---

## 8. Things deliberately not being done

- Nothing involving creating accounts or working around provider limits. Austin floated it;
  it is off the table.
- No freezing or version-snapshotting the forward book. Retired 2026-08-28 on his
  instruction.
- Fair-value-gap and flag detection stay computed and stay unpromoted. He does not trade
  them and they never gate anything or appear in a report as setups.
- The "take a later setup when a higher-timeframe target is better" exception is parked as
  a second-order overlay. Measure the plain first-trade policy first. He named the
  distraction risk himself.
