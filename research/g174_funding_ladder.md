# g174 — rank the funding ladder

**What is different now (wave 2, W4):** the core-10 lane Austin asked for is now measured
alongside full/index on the identical one-trade-a-day unit, H1/H2 — `universe.CORE_SYMBOLS`
(11 symbols today, not 10: SPY was re-added 2026-08-11 and overlaps `INDEX_POOL`). It changes no
ladder verdict: core is **−$0.34/day** full 2y (H1 +$34.46, H2 **−$35.00**), between the index and
full-pool streams and still negative in H2. Everything below this paragraph is the standing
wave-1 ladder, unchanged except the new stream row in the table under "The three streams".

**What is different now:** every funding arm measured tonight sits in one table, in Austin's own
ladder order, and the answer is that **no rung is fundable** — not because of the account type, but
because all three candidate streams lose money in the last twelve months (H2: −$68/day index,
−$70/day full pool, −$122/day S-only). The rung he wants most (automatic futures prop) is also the
one whose numbers are least trustworthy: its arm was refuted, and its most automation-friendly firm
(Lucid) is a blank row because every primary page 403s.

**Fill, everywhere below:** signal-bar CLOSE entry, `stop_rule.stop_fill_price()` stops, size-gated
on `signal_runner.min_risk_floor`, `research/bt2y_trades_retest_on.json` (RETEST_REQUIRED=1, shipped
default, 498 sessions 2024-09-03 → 2026-09-02). One-trade-a-day unit. 1R = $1,000 unless a row says
otherwise. H1 = day < 2025-09-01, H2 = day ≥ 2025-09-01.

**Scripts:** this file's own cells come from `research/g174_funding_ladder.py`
(→ `g174_funding_ladder.json`). Firm verdicts are reproduced from the arm JSONs:
`g171_futures_proxy_arms.json` (P1), `g172_vanquish_refresh.json` (P2),
`g173_shares_personal_refresh.json` (P3). Firm rules from `g170_futures_firms_2026-09.md` (P0) and
`research/execution_prep_2026-09.md`.

---

## THE ANSWER

1. **No rung is fundable on tonight's book.** Rungs 1–3 are prop evaluations and every one of them
   fails: 13 of 13 futures firms, 8 of 8 Trade The Pool rows, and every Vanquish risk level from
   $100 to $500/trade in both classifier states.
2. **Rung 4 (automatic personal) is the only rung that can be *operated*** — it has no eval to
   fail — and at a professional 1% risk on $10k it pays **$3.56/day** against his **$397/day** bar.
   At the book's native $1,000/trade it pays $35.56/day but draws down $21,577, i.e. **216% of a
   $10k account**; it survived only because the profits arrived before the drawdown, and H2 alone
   is −$17,192.
3. **The one number that would change it: the one-trade-a-day stream's mean R, which is currently
   negative in the last twelve months on every lane.** For the cheapest rung-1 eval (Apex 50K EOD,
   $35) to clear even 50% of start days, the index stream must go from **−0.0135R to +0.0565R** per
   trade — a **+0.07R swing**. For the cheapest rung-2 eval (TTP 25K FLEX, $97) the full-pool stream
   must go from **+0.0356R to +0.5456R** — a **+0.51R swing**, which is not a tuning distance.
4. **The account type is not the blocker. The edge is.** This restates 2026-09-01's finding with a
   third quarter of data behind it.

---

## The ladder

Automation column: **primary** = the firm's own page, fetched and quoted; **secondary** = a summary
of the firm's own page, primary 403'd; **unverified** = no clause found either way.

| rung | arm | instrument | firm | automation allowed? | risk/trade | months to pass | cost to pass | all-starts pass rate | net after fees | green months (stream) | verdict |
|---|---|---|---|---|---:|---|---:|---:|---:|---:|---|
| **1** | P1 (**REFUTED**) | index futures MES/MNQ/M2K | **Lucid Trading** | **yes**, secondary ("algorithmic trading … fully permitted on all account types"); primary `lucidtrading.com/general-faq/` 403 | — | — | — | — | — | — | **BLOCKED — no specs exist to test** |
| 1 | P1 (REFUTED) | index futures | MFFU Rapid 50K | conflicting, secondary (2025 policy permits algos; primary intercom page 403) | $1,000 nominal, contract-floored | never (fails in 13 arm-days) | $80 | 20.1% (refuter3) | −$1,696 | 12/24 | FAIL trailing_drawdown |
| 1 | P1 (REFUTED) | index futures | MFFU Rapid 100K | as above | $1,000 | never (14 arm-days) | $150 | 12.0% | −$2,754 | 12/24 | FAIL trailing_drawdown |
| 1 | P1 (REFUTED) | index futures | Apex 50K Eval EOD | unverified (apexfunded.com 403) | $1,000 | never (14 arm-days) | **$35** (cheapest) | **26.5%** (refuter3) / 26.9% (g174, shares-R) | −$2,639 | 12/24 | FAIL trailing_drawdown |
| 1 | P1 (REFUTED) | index futures | Apex 100K / 150K | unverified | $1,000 | never (14 / 18 days) | $85 / $105 | 12.0% / 12.8% | −$2,689 / −$4,858 | 12/24 | FAIL trailing_drawdown |
| 1 | P1 (REFUTED) | index futures | Topstep 50K Combine | not stated on own pages (fetched 200 OK 2026-09-05) | $1,000 | never (13 arm-days) | $49/mo | 20.1% (refuter3) / 12.0% (g174) | −$1,665 | 12/24 | FAIL trailing_drawdown |
| 1 | P1 (REFUTED) | index futures | Topstep 100K / 150K | not stated | $1,000 | never (14 / 18 days) | $99 / $149 per mo | 12.0% / 12.8% | −$2,703 / −$4,902 | 12/24 | FAIL trailing_drawdown |
| 1 | P1 (REFUTED) | index futures | TPT Test 50K/100K/150K | unverified | $1,000 | never (13–18 days) | $102 / $150 / $200 | 20.1% / 12.0% / 12.8% | −$1,718 / −$2,754 / −$4,953 | 12/24 | FAIL trailing_drawdown |
| 1 | P1 (REFUTED) | index futures | Earn2Trade TCP 25K | unverified | $1,000 | never (**1 day**) | $150 | 25.6% | −$150 | 12/24 | FAIL daily_loss_limit |
| 1 | P1 (REFUTED) | index futures | OneUp 100K | unverified | $1,000 | never (15 days) | $105 | 15.4% | −$3,695 | 12/24 | FAIL trailing_drawdown |
| **2** | P3 | US shares | TTP 25K MAX / FLEX | **explicitly banned**, primary (T&C §11: "may not use any custom, algorithmic, or other automated trading software"; AI-bots page: "a human person must personally place and authorize every single trade") | share-count model, $100–$1,612 realised (mean $372) | never | **$97** | 26.1% (FLEX, g174 flat-$1,000/R) | −$97 | 13/25 | FAIL daily_loss_limit / trailing_drawdown |
| 2 | P3 | US shares | TTP 50K MAX / FLEX | banned, primary | as above | never | $230 | 14.5% (FLEX) | −$230 | 13/25 | FAIL |
| 2 | P3 | US shares | TTP 100K MAX / FLEX | banned, primary | as above | never | $435 | — | −$435 | 13/25 | FAIL |
| 2 | P3 | US shares | TTP 200K MAX / FLEX | banned, primary | as above | never | $1,100 | — | −$1,100 | 13/25 | FAIL |
| **3** | P2 | equity options, $50k sim | Vanquish, S=1R, classifier **OFF** | **unverified** — no automation clause on `vanquishtrader.com/terms` (fetched 2026-09-03); manual by default | $1,000 (= S's live 1R) | never (fails 2024-09-20, 0.56 mo) | $499/mo + $249 reset | **0.4%** (254 starts; H1 0.6%, H2 0.0%) | −$748 | 12/25 | FAIL trailing_drawdown |
| 3 | P2 | equity options | Vanquish, S=1R, classifier **ON** | unverified | $1,000 | never (same day, 0.56 mo) | $499/mo + $249 | 0.4% (identical) | −$748 | 12/25 | FAIL trailing_drawdown |
| 3 | P2 | equity options w/ options skin | Vanquish, delta 0.42 + $0.05 spread (**low confidence**) | unverified | $1,000 | never (fails 2024-09-05, 0.07 mo) | $499 + $249 | — | −$748 | 12/25 | FAIL — the spread alone kills it in 2 days |
| 3 | P2 | SPX/XSP single-leg | Vanquish index-only insurance arm | unverified | $1,000 | never | $9,481 (19 mo) + $249 | 0 starts (too few candidates) | −$9,730 | — | FAIL profit_target_not_reached — **n = 10 SPY-only S candidates in 18 months** |
| **4** | P3 | US shares/options, own account | **personal $10k @ $100/trade (1%)** | **yes** — own account, no firm ban; Tastytrade + IBKR APIs documented | $100 | n/a (no eval) | $0 | n/a | **+$1,760 over 2y = $3.56/day** | 13/25 | **operable, not fundable** — 21.6% account drawdown, never wiped |
| 4 | P3 | US shares/options, own account | personal $10k @ $1,000/trade (book-native) | yes | $1,000 | n/a | $0 | n/a | +$17,601 = $35.56/day | 13/25 | **not survivable** — max DD $21,577 = 216% of account; H2 alone −$17,192 |

---

## The three streams underneath the ladder, on one ruler

Every rung above is a rulebook wrapped around one of these three streams. This is the same table for
all three, at a common $1,000/R price, so the rungs are comparable at all
(`research/g174_funding_ladder.py`).

| stream | window | n days | $/day | mean R | win% | green months | max DD |
|---|---|---:|---:|---:|---:|---:|---:|
| index pool QQQ/SPY/IWM, first of day (**rung 1**) | full 2y | 234 | **−$13.50** | −0.0135 | 48.3% | 12/24 | $12,529 |
| | H1 | 112 | +$46.15 | +0.0462 | 49.1% | 7/12 | $7,855 |
| | H2 | 122 | **−$68.27** | −0.0683 | 47.5% | 5/12 | $11,797 |
| core 11, `universe.CORE_SYMBOLS`, first of day (**not on the ladder — his explicit ask, W4**) | full 2y | 495 | **−$0.34** | −0.0003 | 46.5% | 12/25 | $23,687 |
| | H1 | 247 | +$34.46 | +0.0345 | 45.3% | 6/12 | $18,243 |
| | H2 | 248 | **−$35.00** | −0.0350 | 47.6% | 6/13 | $19,424 |
| full pool, first of day / A_base (**rungs 2 & 4**) | full 2y | 495 | **+$35.56** | +0.0356 | 46.3% | 13/25 | $21,577 |
| | H1 | 248 | +$140.29 | +0.1403 | 49.6% | 9/12 | $13,980 |
| | H2 | 247 | **−$69.60** | −0.0696 | 42.9% | 4/13 | $21,577 |
| S-graded only, first of day (**rung 3**) | full 2y | 313 | **−$49.07** | −0.0491 | 42.8% | 12/25 | $32,346 |
| | H1 | 161 | +$19.46 | +0.0195 | 44.1% | 7/12 | $13,619 |
| | H2 | 152 | **−$121.66** | −0.1217 | 41.4% | 5/13 | $19,236 |

**Every stream's H2 is negative, including the core-10 slice added in wave 2, and the S-only stream
— the one the live engine actually sizes — is the worst of the four.** That is the finding the whole
ladder rests on. It also means the ladder
cannot be reordered into a pass: there is no rung whose rulebook is loose enough to survive a
−0.07R-per-trade stream for 120 sessions.

### Denominator note (so no one re-derives a different $/day)

`omen_metrics.first_of_day_arm` on the unfiltered book gives **498 days, $33.94/day, +0.0339R,
13/25 green**. P3's arm loads traded-only rows first and so reports **495 days, $35.56/day** — the
same trades, three fewer denominator days. CLAUDE.md's "$25/day, full pool, retest ON" is the same
arm with the pre-2026-09-03 pick-then-gate bug (`size_gate=False`): **498 days, $25.31/day**, which
this script reproduces exactly. All three are the same book; quote the one whose construction you
name.

---

## Rung 1 carries a refuted arm — read this before quoting any futures number

P1 (`g171_futures_proxy_arms.md`) was **REFUTED** by two independent refuters
(`g171_refute_r2_sampling.md`, `g171_refute3_reproduce.md`). What survives and what does not:

| P1 claim | status |
|---|---|
| ratios, mapping mechanics, tick sizes, contract flooring, $−11.83/day, 12/24 green | **reproduces byte for byte** |
| "13 of 13 firms FAIL from the book's first session" | **true, as a single walk-forward from day 0** |
| "rolling-252-session pass rate **0.0%** for every firm" | **FALSE — do not quote.** `window = min(252, n)` with n = 234 gives exactly **one** window (`rolling_252_windows: 1` in the JSON), so 0.0% means "the one eval starting 2024-09-03 failed", restated as a rate. Corrected all-starts rate: **12.0%–26.5%** |
| "fails in 13–18 days" | those are **arm-trading days**, not sessions — 17 to 23 book sessions — so monthly-fee firms bill twice, not once |
| overlap check "basis is tight" | **untested, not tight.** n = 2 matched pairs; the σ = 0.0012 is the internal spread of two intraday ratios and never differences daily-vs-intraday, which is the error the mapping depends on. `MES=F` is fetched and discarded |
| $/day figures as findings | CI is **[−$107.10, +$84.44]** full 2y; H1−H2 gap CI **[−$76.20, +$312.67]**, p = 0.122 — the H1/H2 gap on this stream is not resolved by a two-sided test |
| same-day close ratio used to size a 09:35 entry | real lookahead, **immaterial**: prior-day ratio gives −$11.78/day vs −$11.83 |

The **direction** survives every refutation: a stream with mean R −0.0135 does not fund a futures
account, and no sizing rescues it (the refuter's $50→$3,000 sweep passes nothing from day 0). But
"0.0% pass rate" and "12–27% at $35 a try" are materially different pictures, and only the second is
true. A 12–27% one-shot clear rate at $35–$150 a go is a **lottery ticket, not an edge**: the eval
is a coin flip on a zero-mean walk (Apex 50K's 2.5R trail against a 3R target is 45.5% for a pure
random walk before fees), and the funded account that follows faces the same trail forever.

Two more rung-1 facts that no amount of measurement fixes tonight:

- **Lucid is the only firm on the whole ladder that explicitly permits automation, and it is a blank
  row.** Every primary page (`lucidtrading.com`, `/general-faq/`, `/evaluations`) returned 403 on
  2026-09-05; account sizes, targets, drawdown and cost are unconfirmed. P0 correctly refused to
  fabricate them, so the rung he wants most has never actually been priced.
- **Topstep, Apex, TPT, Earn2Trade and OneUp state no automation policy on their own pages.** An
  automatic futures lane at any of them is an unanswered legal question, not a green light.

---

## Rung-by-rung, in his order

### Rung 1 — automatic futures prop
Blocked on two independent things: the stream has no edge (−0.0135R), and the one firm that would
legally let a bot run it has no published numbers. Cheapest attempt is Apex 50K at $35 with a ~27%
one-shot clear rate — which is a $35 lottery ticket, and passing it would hand him a funded account
running a negative-mean stream into a $2,500 trail.

### Rung 2 — manual prop (shares, Trade The Pool)
**Automation is banned in writing here** (T&C §11 and the AI-bots page, both fetched from TTP's own
site 2026-09-03), so this rung is manual by rule, not by choice. All 8 real account/plan rows fail
on the same 495-session stream; MAX plans die on the daily loss limit (as early as day 0 on the 25K),
FLEX plans on the trailing drawdown. Cheapest attempt $97. Caveat carried from P3: the plan's own
60/120-day evaluation window is **not enforced** by `evaluate_prop_challenge`, so a "months to event"
above the cap would be flagged, not silently counted — no row passed, so nothing was flagged.

### Rung 3 — Vanquish options, manual, one account
The most decisively dead rung, and the most important one, because it is priced on the stream the
live engine actually sizes: **S = 1R, A and C size to $0** (row L5). n = 313 S candidates in two
years — already only 0.63/day against the 1–3/day the lane calls for. No risk level from $100 to
$500/trade passes in either classifier state; the classifier changes nothing (identical fail day,
identical 0.4% rolling-start rate; F7 refuted it anyway). The eval dies on **2024-09-20, 17 days in**,
having burned $499. The options skin (delta 0.42 + $0.05 spread, **low confidence** — this repo has
no real options tape) dies on **2024-09-05**, in two trading days: the round-trip spread alone
outweighs the edge. The SPX/XSP index-only insurance arm is not a result — **10 candidates in 18
months** cannot pass a min-4-day, 10%-target eval and the arm says so.

### Rung 4 — automatic personal
The only rung with no rulebook to fail, and the only place automation is unambiguously permitted
(own account; Tastytrade and IBKR both document a bracket-in-one-call). It is also the only rung
that ends the two years positive. But at a survivable 1% risk it pays **$3.56/day**, 0.9% of his
$397 bar; and at the sizing that pays $35.56/day the drawdown is 216% of the account, so the
positive total is an artifact of the order the trades arrived in — H2 on its own is −$17,192, which
wipes a $10k account outright.

**Live-lane caveat that applies only to this rung:** it is the one rung whose automation depends on
a broker connection, and as of 2026-09-01 **Tastytrade returns HTTP 401 invalid_credentials** and
the live scanner silently falls through to yfinance with no higher-timeframe bias at all. Rung 4 is
the cheapest to start and the only one whose plumbing is currently broken.

---

## What would change the verdict — measured, not asserted

`research/g174_funding_ladder.py::required_mean_r` adds a constant R offset to every trade and finds
the smallest offset at which the eval clears 50% of all start days (every start day in the stream,
capped at the firm's own `max_days`, `omen_metrics.evaluate_prop_challenge`).

| rung | firm | stream | mean R now | mean R needed for a 50% clear | swing required |
|---|---|---|---:|---:|---:|
| 1 (cheapest) | Apex 50K Eval EOD, $35 | index pool, 234 days | **−0.0135R** | **+0.0565R** | **+0.07R/trade** |
| 2 (cheapest) | TTP 25K FLEX, $97 | full pool, 495 days | +0.0356R | +0.5456R | +0.51R/trade |

Rung 1's +0.07R is the smallest number on this page and the honest target: **it is roughly the size
of the H1→H2 decay the engine already suffered** (index stream H1 +0.046R → H2 −0.068R, a −0.11R
swing), so it is a plausible ask for a selection fix rather than a fantasy. Rung 2's +0.51R is not a
tuning distance — a shares prop's daily loss limit is simply the wrong container for this stream.

**But a 50% eval clear is not the bar and should not be sold as one.** The bar that matters is
CLAUDE.md's: **mean R = 2.0 as the money gate, every month green, past $397/day**. Against that, the
best stream on this page (full pool, +0.0356R, 13/25 green) is 1.8% of the money gate and just over
half the months. The gap between "could pass a $35 eval half the time" and "is a fundable edge" is
the entire project.

---

## Rows this file deliberately does not rank

- **Lucid Trading** — reported as BLOCKED, not ranked. It is the only firm with an explicit
  automation permission and it has no numbers; ranking it on anything would be fabrication.
- **P1's whole futures block** — reported with its refutation attached. Refuted arms are reported as
  refuted; none of them is presented as fundable.
- **The options skin** — carried through at low confidence, because there is no options tape in this
  repo to check a flat $0.05 spread against. It is a direction (the spread is large relative to the
  edge), not a price.

## What a human still has to do

| task | minutes | done-signal |
|---|---:|---|
| Get Lucid's account sizes / target / trailing-DD type / cost, by support ticket or from a logged-in page (every anonymous fetch 403s) | 10 to send | numbers land in `g71_propfirm_sim.py::FIRMS` and rung 1's blank row fills in |
| Ask Vanquish support, in writing, whether an EA/API may trade the account | 10 | the "unverified" in rung 3's automation column becomes primary-sourced either way |
| Re-authenticate Tastytrade (HTTP 401 since at least 2026-09-01) | 15 | `journal/scanner-*.log` stops printing `HTF unknown` on every symbol |

None of these unblocks funding. All three only make the ladder's cells honest.
