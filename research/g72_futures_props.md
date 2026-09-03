# G72 — futures_props: does the $10k buffer change the futures answer?

Track: futures_props. Prior work: `research/g71_propfirm.md` (futures section 2, lines 72-170),
`research/g71_instrument.md`. This does not re-run the money-gate/pass-rate simulation from
G71 — it re-checks the premise that changed (capital) and adds the one axis G71 never checked
(automation permission), which turns out to be the load-bearing one.

## Bottom line

**No — the $10k buffer does not rescue futures, because the firm that G71 crowned (Apex 50K
EOD, 92.9% pass) is the one firm on this list that explicitly bans full automation on the
funded account, with forfeiture as the penalty.** Austin said "you will be trading it not me."
Apex's own PA compliance article: automation — "any form of AI (Artificial Intelligence),
Autobots, algorithms, fully automated trading systems" — is "strictly prohibited," and using it
"will result in the immediate closure of your PA or Live account and the forfeiture of all
funds and balances" (support.apextraderfunding.com PA Compliance article, retrieved 2026-08-29,
via search synthesis — see verification note below). Apex allows automation *during the
evaluation* only; the funded account, which is the actual point, does not permit it.

Four firms on this list do permit real automation on the **funded** account: Bulenox,
MyFundedFutures, Tradeify (conditionally), and Topstep (conditionally). Of those, only
Topstep and MyFundedFutures clear the 50K-size, 90%+ pass-rate bar G71 already established for
index futures. Neither was G71's pick — its pick (Apex) is disqualified by rule 2 below, a
fact G71 never checked because it wasn't looking for it.

## Verification note

Apex's help-center domain (support.apextraderfunding.com) returned HTTP 403 to direct fetch
(Cloudflare-gated). The quote above is reconstructed from a WebSearch synthesis that cited that
exact URL and article title consistently across the query, and matches the independent
`quantvps.com` and `sentinel.redclawey.com` summaries of the same clause. Treat the exact
wording as **UNVERIFIED at primary-source fetch level** — confirmed by title/URL match and
triangulated secondary sources, not by reading the raw page. Recommend Austin (or a session
with browser access) open that URL directly before betting capital on it.

---

## 1. Schema table

Sizes shown are the smallest size that both (a) fits the pattern's $250-$650/trade risk band
from G71 and (b) is the size G71 found clearing a 90% pass rate for index futures (usually 50K).

| Firm | Route | Instruments | Account sizes | Cost to start | Own capital required | Max daily loss | Max drawdown | Drawdown type | Profit target | Payout split | Payout frequency | Time limit | Automation allowed | Automation evidence (quote + URL) | Fits 09:30-11:00 one-trade-day | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Topstep** | futures-prop | ES/NQ/RTY + micros only | 50K/100K/150K | $49-149/mo Combine | none | $1,000-3,000 soft (locks day) | $2,000-4,500 trailing | EOD trailing to starting balance | 6% ($3k on 50K) | 90/10 (sign-ups after 2026-01-12) | on request, 1-2 days | none | **Conditional yes** | "Bots, EAs, and automated signal execution are permitted in evaluation and funded accounts" but VPS/VPN/remote-server hosting is prohibited and HFT/latency-exploit is banned; "no support provided" for third-party software failures. help.topstep.com + AlgoProven TopstepX API/Bot rules summary, retrieved 2026-08-29 | yes | Clears 90%+ pass at 50K per G71 |
| **Apex** | futures-prop | ES/NQ/RTY/CL/GC + micros | 25K-150K | EOD eval $390-1,490 list (70-90% promos routine) + PA activation $69-149 | none | none (soft, no daily-loss rule) | 50K: $2,500 trailing (choice of EOD/intraday since Mar 2026 — take EOD) | trailing | 50% (since Mar 2026) | 100% of first $25k then 90/10 | automated, ~2x/mo | none | **No on funded account** | "The use of automation is strictly prohibited on all account types, including any form of AI, Autobots, algorithms, fully automated trading systems, and HFTs... will result in the immediate closure of your PA or Live account and forfeiture of all funds." Automation IS permitted during the evaluation phase only. support.apextraderfunding.com PA Compliance article (title/URL confirmed via search, direct fetch 403'd), retrieved 2026-08-29 | yes (eval only) | **Disqualified for the funded/robot use case** despite best raw pass rate; the ban applies exactly where it matters |
| **MyFundedFutures** | futures-prop | ES/NQ/RTY/CL/GC + micros | 25K/50K/100K/150K | ~$80-150 Rapid | none | none on any plan | 50K $2,500 | trails to highest EOD balance; locks at start+$100 after first payout | EOD 50% (Rapid EOD keeps 30%+4 min days) | 90/10 Rapid EOD, 80/20 Pro | Rapid EOD daily $500 min; Pro 14 days $1,000 min | none | **Yes, eval + funded** | Policy updated 23 Jul 2025: "Traders may make use of automated trading strategies tailored to their own specific settings so long as these automated tools do not aim to exploit the favorable fills offered in the Simulated Environment." HFT banned; live accounts must comply with CME guidelines. help.myfundedfutures.com Fair Play article, retrieved 2026-08-29 | yes | Clears 90%+ pass at 50K per G71; **automation explicitly permitted funded** |
| **Take Profit Trader** | futures-prop | ES/NQ/RTY + micros (per TPT product page — UNVERIFIED exact list) | 50K and up | UNVERIFIED — not re-priced this pass | none | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | **No** | "Automated trading via Expert Advisors (EAs) is prohibited across all phases." Personal proprietary scripts you wrote yourself are described elsewhere as fine, but mass-distributed/paid-signal EAs are banned — ambiguous whether Austin's own robot counts as "EA." Terms of Service (via blog.traderspost.io + pickmytrade.io synthesis), retrieved 2026-08-29 | not evaluated | Ambiguous ban; do not bet on the "personal script" carve-out without reading TPT's ToS directly |
| **Earn2Trade** | futures-prop | ES/NQ/RTY + micros | UNVERIFIED sizes this pass (G71 didn't price it either) | UNVERIFIED | none | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | **No — hard ban, no exceptions** | "Any use of automated trading strategies or AI-based systems is not permitted and will not be tolerated." Also bans trade copiers entirely, even to pass multiple evals in parallel: "If you use a trade copier to pass multiple evaluations, you will only receive one funded account." Earn2Trade prohibited-conduct policy (via propfirmpress.com synthesis), retrieved 2026-08-29 | no | Hard disqualify for a robot |
| **Bulenox** | futures-prop | ES/NQ/RTY/CL/GC + micros | 25K-150K | low-cost eval, promo-heavy (UNVERIFIED exact price this pass) | none | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | **Yes, explicitly, no restriction beyond HFT** | "Bulenox explicitly permits automated trading, including bots, EAs, and trade copiers, without restriction... Automated high-frequency trading is prohibited." Bulenox knowledge base / permitted-strategies page (via proptradingvibes.com, quantcrawler.com synthesis), retrieved 2026-08-29 | not evaluated | Most permissive automation stance found; G71 never priced Bulenox — needs its own pass-rate run before it can be recommended |
| **Tradeify** | futures-prop | ES/NQ/RTY + micros | 25K-150K, EOD trailing option | UNVERIFIED price this pass | none | UNVERIFIED | UNVERIFIED | EOD trailing available (algo-friendly) | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | **Conditional yes** | Funded Trader Agreement §6.6: trader "must be able to prove... sole owner of the bot or strategy and that no one else has access to or is using it"; may not run the same bot "across multiple firms"; "personal bots are allowed as long as they are not HFT"; separately, ≥50% of trades AND profits must come from trades held >10 seconds. tradeify.co/funded-trader-agreement, fetched directly 2026-08-29 | plausible — the setup holds for minutes not seconds, so the 10-second rule is not binding | Directly-fetched primary source — highest confidence automation quote on this table |
| **Alpha Futures** | futures-prop | ES/NQ + micros | UNVERIFIED | UNVERIFIED | none | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | **No — fully automated banned** | "Fully automated bots, EAs, and AI trading systems remain prohibited... semi-automated workflows are allowed only when the trader is actively watching and managing the trades." alpha-futures.com rules articles (via search synthesis), retrieved 2026-08-29 | no (needs a human watching, contra "robot trades this") | Disqualify |
| **Legends Trading** | futures-prop | ES/NQ + micros (UNVERIFIED) | UNVERIFIED | UNVERIFIED | none | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | **No / unclear — manual-only stated** | "Automated trading is not permitted at Legends Trading—manual trading only," but the firm's own published documentation on this point is thin; multiple review sites flag it as unclear. Aggregator synthesis (propfirmplus.com, thelegendstradingpartners.com), retrieved 2026-08-29 — **no primary-source quote found**, lowest confidence row on this table | not evaluated | Do not rely on this row without a direct fetch of Legends' own rules page |

Firms with a hard or effective automation ban for a robot that trades unattended: **Apex
(funded), Take Profit Trader, Earn2Trade, Alpha Futures, Legends Trading (probable).**
Firms that clear it: **Topstep, MyFundedFutures, Bulenox, Tradeify.**

---

## 2. Does automated trading survive contact with each rulebook? (direct answer to Q2)

Quotes above, repeated as the direct answer:

- **Topstep** — allowed, eval + funded: *"Bots, EAs, and automated signal execution are
  permitted in evaluation and funded accounts."* Condition: no VPS/VPN, no HFT, no support if
  it breaks.
- **Apex** — banned on the account that matters: *"The use of automation is strictly
  prohibited on all account types, including any form of AI, Autobots, algorithms, fully
  automated trading systems, and HFTs... immediate closure... forfeiture of all funds."*
  Eval-only exception does not help — the eval is not where he earns money.
- **MyFundedFutures** — allowed, eval + funded, since a 23 Jul 2025 policy change:
  *"Traders may make use of automated trading strategies tailored to their own specific
  settings so long as these automated tools do not aim to exploit the favorable fills offered
  in the Simulated Environment."*
- **Take Profit Trader** — banned, stated as absolute: *"Automated trading via Expert
  Advisors (EAs) is prohibited across all phases."*
- **Earn2Trade** — banned, stated as absolute, and also bans copy-trading (kills the
  parallel-challenge play outright for this firm): *"Any use of automated trading strategies
  or AI-based systems is not permitted and will not be tolerated."*
- **Bulenox** — allowed, unrestricted beyond HFT: *"Bulenox explicitly permits automated
  trading, including bots, EAs, and trade copiers, without restriction."*
- **Tradeify** — allowed with conditions (§6.6, directly fetched): sole ownership, not run
  across multiple firms, no HFT, plus a >10-second average hold-time rule that a 09:30-11:00
  swing-for-the-day setup clears easily.
- **Alpha Futures** — banned for full automation: *"Fully automated bots, EAs, and AI trading
  systems remain prohibited."*
- **Legends Trading** — stated manual-only by aggregators, no primary quote found; treat as
  banned until verified.

## 3. Parallel challenges: the math (direct answer to Q1)

With N independent challenges at per-challenge pass probability p, and no correlation between
attempts (a real assumption — see caveat), the probability of passing **at least one** is:

  P(≥1 pass) = 1 − (1 − p)^N

$10,000 buys N = floor(10000 / cost_per_eval) parallel evaluation slots. Using the two
automation-permitted 50K firms that G71 already measured at a 90%+ pass rate:

| Firm, size | p (single-challenge pass rate, from G71) | list cost/eval | N at $10k | P(≥1 pass) |
|---|---:|---:|---:|---:|
| Topstep 50K | 90.3% | $149 (one month, Combine) | 67 | 1 − 0.097^67 ≈ 1 (indistinguishable from certainty) |
| MyFundedFutures 50K Rapid | ~90%+ (not separately measured by G71; assume comparable to Topstep/TPT band it was grouped with) | ~$150 | 66 | ≈1 |
| Apex 50K EOD (for contrast only — disqualified above) | 92.9% | $390 list / as low as ~$40-120 with routine 70-90% promos | 25 at list, up to 250 at promo pricing | ≈1 either way |

Even at N=2 the number already stops mattering: 1 − (1−0.903)^2 = 99.06%. At N=5:
1 − 0.097^5 ≈ 99.999%. **The parallel-challenge play does not need $10k — it needs about
$300-450 (2-3 slots) to push an already-90% single-shot pass rate to a rounding error of
100%.** What $10k actually buys is not a higher pass probability (that saturates almost
immediately) but the ability to **run several sizes/firms simultaneously and bank multiple
funded accounts at once** — e.g., 20+ Topstep 50K slots or a mix of Topstep + MyFundedFutures
+ Bulenox — which scales *funded capital*, not *odds of getting funded*. That reframes the
$10k's value: it is a scaling lever (more simultaneous funded accounts, faster to a multi-account
income target), not a pass-rate insurance policy, because insurance against a 90% coin flip
gets cheap after the second flip.

**Caveat that matters more than the arithmetic:** the independence assumption is close to true
only if the challenges run on genuinely different symbols/times so a single bad ES session
doesn't blow multiple accounts at once. If the robot runs the same signal into N accounts
simultaneously, the accounts are perfectly correlated on any single trading day and N buys
*zero* additional pass-rate protection — it only multiplies the fee spent per attempt. Running
N independent Topstep Combines in parallel on the same signal is functionally one gamble
repeated N times with N times the entry fee, not N separate coin flips, *unless* the eval
periods are staggered so a bad single day only kills the accounts active that day. This must be
modeled explicitly before Austin commits capital to it — it is not covered by the naive formula
above.

## 4. Does the six-level 09:30-11:00 setup even port to ES/NQ? (direct answer to Q3)

Checked the mentor Discord corpus directly rather than guessing.

`grep -il` for futures-scalper vocabulary ("opening print", "gap fill", "London high",
"overnight session", "globex") hits 12 channels, most heavily `futures-alerts.json`. Sample
lines from that file:

> "If we hold that level and trend above **the opening print**, we could see a relief bounce."
> "NQ **acceptance** above 5796 with high volume and stay above **the opening print**, longs
> could be on the table."
> "If NQ bounces off 19523 and trend above the opening print, we can see **OVH highs** [overnight
> high] and 19701.50."

Counting the six-level vocabulary in the same file:

| term | hits in futures-alerts.json |
|---|---:|
| PDH | 49 |
| PDL | 47 |
| HOD | 41 |
| LOD | 31 |
| PMH | 6 |
| PML | 9 |

**Verdict: partial port, and the weakest link is exactly the level pair that only exists
because equities have a premarket session.** PDH/PDL/HOD/LOD are used in the futures room too
— those levels exist in both worlds because "previous day" and "high/low of day" are
market-structure concepts, not equity-specific ones. But PMH/PML barely appear (6 and 9 hits
against 40-50 for the other four), and the room's actual working vocabulary for the analogous
concept is different — "the opening print," "overnight high" (OVH), "acceptance/rejection,"
and "trend above/below" a level rather than "break and retest of premarket high." Futures trade
nearly 24 hours, so "premarket" is not a discrete pre-market session the way it is for equities
with a 9:30 cash open — the room substitutes "overnight session" and "opening print" for that
missing structure. That is evidence the six-level frame does not transplant cleanly: four of
six levels translate, the premarket pair does not, and the room's entry trigger language
(acceptance/rejection off a level, trending above/below a print) is a materially different
mechanic than break-and-retest / one-candle-rule, which was built and graded entirely on
equities. Porting the setup to ES/NQ is not a relabeling exercise — it is a second research
project (re-deriving what "premarket" means for a near-24-hour instrument, and re-validating
the entry trigger against futures bar data) that has not been done and was not in scope here.

---

## Answers, one line each

1. **N-challenge math**: P(≥1 pass) = 1−(1−p)^N; at p≈90%, N=2 already reaches 99%, so $10k's
   value is scaling parallel funded accounts, not buying pass-rate insurance — and that only
   holds if the N attempts are decorrelated (different periods/signals), which running one
   robot into N accounts on the same day does not give you.
2. **Automation permitted on the funded account**: yes at Topstep, MyFundedFutures, Bulenox,
   Tradeify (conditionally); no at Apex (funded), Take Profit Trader, Earn2Trade, Alpha
   Futures, and probably Legends Trading. **This disqualifies G71's Apex recommendation for
   the robot use case** — Apex only allows automation during the evaluation, and bans it with
   forfeiture on the account that would actually generate income.
3. **Porting to ES/NQ**: partial at best. PDH/PDL/HOD/LOD show up in the futures mentor room;
   PMH/PML barely do, and the room's real entry vocabulary (opening print, acceptance,
   overnight high, trend above/below) is not break-and-retest / one-candle-rule. Treat a
   futures port as unvalidated, not as a relabeling of the equity setup.

**Net recommendation for this track**: if futures is still on the table given the automation
finding, re-run G71's money-gate/pass-rate simulation on **Topstep 50K** and **MyFundedFutures
50K Rapid** specifically (both automation-clear, both already at 90%+ pass per G71's own
numbers) rather than Apex — and do not treat the ES/NQ six-level setup as validated until it
has been checked against futures bar data the way the equity version was checked against 1,057
judged symbol-days. Neither of those two follow-ups was run in this pass.
