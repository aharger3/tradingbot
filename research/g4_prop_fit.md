# G4 — Prop-firm fit memo (futures props, mass accounts + copy-trade)

**Date:** 2026-07-14 · **Method:** `d3_risk_of_ruin.py` fable_ror trade model
(+2R/−1R, seed 84, 20k trials) re-enveloped per firm · **Script:**
`research/g4_prop_fit.py` · **Analysis + web research only — no bot code
changes, no commits.**

## Verdict (one line)

**Apex Trader Funding $150K EOD is the vehicle: at the honest OOS win rates
(43–45.5%W) a $250–350 risk unit clears the <5% funded-ruin gate, and Apex's
20-account copy-stack at 100% split turns a small per-account edge
($900–1,600/mo) into $17k–32k/mo — 4x Topstep's ceiling (5 accounts) and 7x
MFF's (3 accounts). Kill line: below ~40%W the surviving risk unit collapses
to <$175 and the plan dies; at ≤36%W nothing clears 5%.**

## 1. Firm specs (2026, EOD-trailing plans only)

| spec | Apex $150K EOD | Topstep $150K → XFA | MFF Pro $150K |
|---|---|---|---|
| Eval price | $397/attempt, **30-day expiry** (promos routinely 80–90% off) | $149/mo, no time limit | $477/mo ($239 w/ code), no time limit |
| Eval profit target | $9,000 | $9,000 | $9,000 |
| Trailing DD | **$4,000 EOD** (4.0 lineup, cut from legacy $5k) | $4,500 EOD (MLL) | $4,500 EOD (3%) |
| DD type note | Intraday-trail variant cheaper but ratchets on open-trade highs — **excluded** (ruin strictly worse than model) | EOD only on Combine/XFA | Rapid plan is 4% intraday — **excluded** |
| DD lock | at start bal.; payout safety net = DD+$100 (+$4,100) | MLL locks at $0 once +$4,500 | locks at start+$100 once +$4,600 |
| Funded acct | PA: $99 activation (EOD), **no monthly fee** | XFA: ~$149 activation, no monthly | $0 activation, no monthly |
| Payout split | **100%** | 100% first $10k lifetime, then 90% | 80% (90% on Rapid) |
| Payout caps | 6-payout ladder $2,500→$5,000, then uncapped; 50% consistency-since-last-payout | 5 winning days ≥$150; 50% of balance ≤ $5,000/request | biweekly, uncapped, $1,000 min |
| **Max accounts** | **20 PAs** | 5 XFAs (Live = 1, kills the stack) | 10 total, but only **3** concurrent 100k/150k sim-funded |
| Copy own accounts | **Allowed** — 1 leader → 19 followers, same-direction only, no cross-trader copying | **Allowed** since Apr 2026 via TopstepX (Settings → Copy Trading); auto-disabled during payout processing; no VPS/VPN | **Allowed** across all account types (official help center); cross-trader copying = termination |

$100K tiers also modeled (Apex $297 / $3,000 DD / $6,000 target; Topstep
$99/mo / $3,000 MLL): strictly worse $/mo per slot than the $150K tiers at
every win rate — see script output — so the table below is $150K only.

## 2. RoR results (fable_ror model, per-firm envelope)

Two risk units per firm because eval and funded sizing may differ (allowed
everywhere): **R_eval** = aggressive size that minimizes expected eval spend
per funded account (Apex's 30-day expiry forces this — at 0.7 trades/day you
get ~13 trades/attempt, so passing +$9,000 needs $1.5–3k eval risk);
**R\*** = largest $25-grid risk unit with **pre-lock funded ruin <5%**
(reach the lock buffer before the trailing DD). Lifecycle = full account life
incl. post-lock floor, monthly withdraw-to-buffer with each firm's caps/split,
eval+activation cost netted out.

| firm | winrate | eval cost/funded | **funded R\*** | pre-lock ruin | net $/mo/acct | E[net]/acct life | ×N stack $/mo |
|---|---|---:|---:|---:|---:|---:|---:|
| **Apex $150K** | 43.0% | $1,006 | **$250** | 4.2% | $869 | $46.0k / 53 mo | **$17,370 (×20)** |
| | 45.5% | $928 | **$350** | 4.6% | $1,588 | $73.9k / 47 mo | **$31,769 (×20)** |
| | 50.6% | $811 | **$525** | 4.9% | $3,454 | $139.7k / 40 mo | **$69,072 (×20)** |
| Topstep $150K | 43.0% | $459 | $275 | 3.1% | $888 | $47.5k / 54 mo | $4,440 (×5) |
| | 45.5% | $413 | $400 | 4.8% | $1,666 | $77.9k / 47 mo | $8,328 (×5) |
| | 50.6% | $347 | $550 | 3.5% | $3,263 | $163.7k / 50 mo | $16,313 (×5) |
| MFF Pro $150K | 43.0% | $1,006 | $275 | 3.2% | $758 | $40.2k / 53 mo | $2,273 (×3) |
| | 45.5% | $840 | $400 | 4.7% | $1,453 | $66.3k / 46 mo | $4,359 (×3) |
| | 50.6% | $639 | $625 | 4.7% | $3,292 | $127.2k / 39 mo | $9,877 (×3) |

**Kill-line sweep (Apex $150K):** 40.0%W → R\* $175, $380/mo/acct ($7.6k/mo
×20 — churn-dominated, marginal); 38.0%W → R\* $125, $154/mo/acct (dead in
practice); **36.0%W → no risk unit ≥$100 clears <5%.** This matches F1's
"<40%W over ≥40 trades = red flag" line exactly.

Why these ruin numbers beat D3's (6.4–20.7% at $1k): the prop envelope is a
*different game* — the D3 Vanquish envelope had a $7,500 DD but an $8,625
buffer to reach; the 2026 firms lock the floor at DD+~$100, so with R scaled
to DD/R ≈ 11–16 the lock is reached 95–98% of the time. The cost is a small
R — which is exactly what the N-account copy stack is for.

## 3. Copy-trade scaling math (the honest version)

Copy-trading N accounts is **zero diversification**: every account takes the
same trade, so the whole stack passes, locks, and dies together. N multiplies
income AND wipe cost, not safety.

Apex $150K ×20 at 45.5%W (planning case):

- **Build cost:** 20 funded slots × $928 expected eval spend ≈ **$18.6k list**
  (Apex promo cycles at 80–90% off are near-permanent → realistically
  **$2–4k**) + 20 × $99 activation.
- **Income:** 20 × $1,588 ≈ **$31.8k/mo** expected while the stack lives
  (first-month ladder caps bind slightly: 20 × $2,500 = $50k max payout #1 —
  not binding at these R's).
- **Churn:** expected account life ≈ 47 months, but that's a skewed mean —
  ~5% of stacks die pre-lock (week one, −$18.6k rebuild), and post-lock the
  stack survives to month 60 only ~59% of the time. Model already nets eval
  cost per account, so $31.8k/mo is churn-adjusted; a full wipe-and-rebuild
  cycle is ~1 month of income at list price, days of income at promo price.
- Same math at 43%W: build ≈ $20k list, income ≈ **$17.4k/mo**.
  At 50.6% (in-sample, don't plan on it): **$69k/mo**.

Topstep ×5 and MFF ×3 are cleaner firms (Topstep's per-account economics are
actually the best: cheapest evals, no 30-day expiry) but their account caps
put ceilings of ~$8.3k/mo and ~$4.4k/mo at 45.5%W. Viable fallbacks if Apex's
copy-policy wording tightens (their help center has flip-flopped on
bots/copy language — see caveat 4).

## 4. Caveats (all load-bearing)

1. **The strategy stats are from EQUITY OPTIONS backtests.** Prop firms are
   futures-only. omen_bot has an `--futures` ES mode, but 43/45.5/50.6%W and
   the fixed 2:1 R:R have never been measured on ES. **An F2-style shadow on
   the ES mode is a prerequisite** — this memo prices the vehicle, not the
   edge transfer.
2. **Micro contracts required.** R\* of $250–350 on ES ($50/pt) means
   sub-1-contract risk on any normal stop; MES ($5/pt) makes it feasible
   (e.g., 8-pt stop → $40/contract → R $280 ≈ 7 MES). All three firms allow
   micros; Apex $150K PA allows 9 contracts (90 micros equiv).
3. **EOD plans only.** The ±R closed-trade model matches EOD trailing;
   intraday-trail plans (Apex Intraday, MFF Rapid) ratchet on unrealized
   highs and their true ruin is strictly worse than anything modeled here.
4. **Apex policy risk.** Own-account copy trading (1 leader → 19) is widely
   documented as permitted, but Apex's own help pages contain conflicting
   bot/copy language and were rewritten in the March 2026 (4.0) overhaul.
   Confirm in writing before buying 20 evals. Also: 2 profitable days
   (≥$50) per rolling 30 days per PA required to avoid dormancy — trivially
   met at 13 trades/mo, but a real rule if the bot pauses.
5. **Apex 50% consistency-since-last-payout** can delay (not deny) payouts
   in thin months at 2-trades/day scale; annual totals unaffected in model.
6. **Spec drift + third-party sources.** Prices/DD ($4,000 on Apex 150K,
   ladder caps, 30-day expiry) are post-March-2026 4.0 numbers sourced from
   review/aggregator sites (official help pages 403'd the fetcher); verify
   on checkout before spending.
7. Lifecycle sim assumes withdraw-to-buffer monthly, perfect ±R fills, no
   slippage/commission drag (real MES round-turn ~$1.30 + spread on 13
   trades/mo ≈ noise at these R's, but nonzero).

## 5. Recommendation

**Firm: Apex Trader Funding, $150K EOD plan. Risk unit: $250 flat (plan at
43%W; lift to $350 only if live ES shadow prints ≥45%W over ≥40 trades).
Eval sizing separate: ~$3k risk per trade in evals to beat the 30-day
expiry (44–48% pass/attempt, ~$1k expected spend per funded account).
N-account plan: start N=2–3 funded PAs during the F2 ES shadow (~$2.7k/mo
at 43%W if it holds), scale to the full N=20 leader+19-follower stack only
after ≥40 live ES trades ≥43%W — full stack is ~$17k/mo at 43%W, ~$32k/mo
at 45.5%W, ~$69k/mo if the in-sample 50.6% survives live. Buy evals only in
Apex promo windows (80–90% off is near-permanent), and get their copy-trade
permission for own-account stacks re-confirmed in writing first. What kills
it: a live OOS win rate below ~40% — R\* collapses to ≤$175 and churn eats
the stack; at ≤36%W no size clears the 5% ruin gate. That is the same
red-flag threshold F1 already set for the shadow, so F2's go/no-go decides
this plan too.**

## Sources

Apex — [Apex 4.0 specs/pricing/ladder (PropTradingVibes review)](https://proptradingvibes.com/prop-firms/apex-trader-funding) ·
[Apex copy-trading rules, 20-account stack (TradeDupe)](https://tradedupe.com/apex-copy-trading-rules) ·
[Apex 20-account copy playbook (PropTradingVibes)](https://proptradingvibes.com/blog/apex-copy-trading-rules) ·
[Apex rules 2026, 30-day window, EOD/Intraday (TradeTanto)](https://tradetanto.com/learn/apex-trader-funding-rules-what-you-need-to-know) ·
[Apex help center — EOD evaluations](https://apextraderfunding.com/help-center/eod-trailing-drawdown-accounts/eod-evaluations/) ·
[Apex 4.0 changes (Phidias)](https://phidiaspropfirm.com/education/apex-trader-funding-4-0-explained)

Topstep — [Combine parameters (official help)](https://help.topstep.com/en/articles/8284197-trading-combine-parameters) ·
[Payout policy: winning days, 50%/$5k caps, 100%-first-$10k (official help)](https://help.topstep.com/en/articles/8284233-topstep-payout-policy) ·
[XFA parameters (official help)](https://help.topstep.com/en/articles/8284215-express-funded-account-parameters) ·
[Copy trading via TopstepX (PropTradingVibes)](https://proptradingvibes.com/blog/topstep-copy-trading-rules) ·
[Account limits: 5 XFA / 1 Live (H2T)](https://h2tfunding.com/how-many-topstep-accounts-can-i-have/)

MyFundedFutures — [Copy trading policy (official help center)](https://help.myfundedfutures.com/en/articles/10771500-copy-trading-at-myfundedfutures) ·
[Plan lineup Core/Rapid/Pro/Flex (PropTradingVibes)](https://proptradingvibes.com/blog/myfundedfutures-account-types) ·
[Pro plan page (official)](https://myfundedfutures.com/plans/pro) ·
[Pro/Rapid 150K pricing (PropTradingVibes Pro review)](https://www.proptradingvibes.com/blog/myfundedfutures-pro-plan) ·
[Rules overview: 10 accts, 3 concurrent 100k/150k (PropTradingVibes)](https://proptradingvibes.com/blog/myfundedfutures-rules-overview)

Internal — `research/d3_risk_of_ruin.md` (model), `research/f1_walkforward.md`
(43.0% pooled OOS / 45.5% pure-forward / 50.6% in-sample), `research/g4_prop_fit.py`
(this run, seed 84).
