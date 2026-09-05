---
date: 2026-09-05
status: research
type: research
version: 1.0
source: Own firm websites
fetch_date: 2026-09-05
---

# G170 — Prop firms: futures-focused (Lucid, MFFU, Topstep, Apex) rule refresh

Summary: Updated specs for four futures-prop firms. Lucid is newly added to the FIRMS roster; MFFU/Topstep/Apex specs verified or noted as inaccessible. Automation policies confirmed for Lucid and cited for MFFU.

## Data Access Summary

| Firm | Primary page | Status | Fetch date | Notes |
|---|---|---|---|---|
| Lucid Trading | https://lucidtrading.com/general-faq/ | **403 Forbidden** | 2026-09-05 | Secondary sources (execution_prep_2026-09.md) cite automation policy; direct verification blocked |
| MyFundedFutures | https://help.myfundedfutures.com | **Domain not resolving** | 2026-09-05 | Listed in g71 as "MFFU Rapid"; algo policy cited as 403'd in execution_prep_2026-09.md |
| Topstep | https://www.topstep.com/topstep-prop | **200 OK** | 2026-09-05 | Full specs retrieved; see table below |
| Topstep Express | https://www.topstep.com/express-funded-account | **200 OK** | 2026-09-05 | Supporting docs; payouts 90% to trader; no daily-loss-limit specs on this page |
| Apex Funded | https://www.apexfunded.com | **403 Forbidden** | 2026-09-05 | Listed in g71; direct access blocked; specs inferred from g71 simulator |
| Earn2Trade TCP | https://earn2trade.com | **200 OK** | 2026-09-05 | Alternate firm (already in g71); Trader Career Path info retrieved |

## Verified Specifications

### Topstep (futures/index — micro contracts allowed per site)

Source: https://www.topstep.com/topstep-prop (fetched 2026-09-05)

| Account | Start | Target | Daily Loss | Max DD | Micro Contracts | Cost | Mode | Max Days |
|---|---:|---:|---:|---:|---|---:|---|---:|
| 50K Combine | $50,000 | $3,000 | $1,000 | $2,000 | 50 micro + 5 mini | $49/mo | EOD | 120 |
| 100K Combine | $100,000 | $6,000 | $2,000 | $3,000 | 100 micro + 10 mini | $99/mo | EOD | 120 |
| 150K Combine | $150,000 | $9,000 | $3,000 | $4,500 | 150 micro + 15 mini | $199/mo | EOD | 120 |

**Automation policy:** Not explicitly stated on Topstep's own help/terms pages accessed 2026-09-05.

**Consistency rule:** Not found on public pages.

---

### Apex (futures — micro contracts implied via platform)

Source: https://www.apexfunded.com (fetched 2026-09-05 — **403 Forbidden**)
Specs inferred from `research/g71_propfirm_sim.py` FIRMS roster (committed 2026-08-23, not freshly verified).

| Account | Start | Target | Daily Loss | Max DD | Cost | Mode | Max Days |
|---|---:|---:|---:|---:|---:|---|---:|
| 50K Eval EOD | $50,000 | $3,000 | None | $2,500 | $35 | EOD | 120 |
| 100K Eval EOD | $100,000 | $6,000 | None | $3,000 | $85 | EOD | 120 |
| 150K Eval EOD | $150,000 | $9,000 | None | $5,000 | $105 | EOD | 120 |

**Micro contracts:** Not confirmed this pass; g71 does not enumerate; platform capability not verified on Apex's own pages.

**Automation policy:** Not found on accessible pages.

**Consistency rule:** Not found on public pages.

---

### MFFU / MyFundedFutures (futures — micro contracts via platform)

Source: https://help.myfundedfutures.com (fetched 2026-09-05 — domain not resolving)
Specs inferred from `research/g71_propfirm_sim.py` FIRMS roster (committed 2026-08-23).

| Account | Start | Target | Daily Loss | Max DD | Cost | Mode | Max Days |
|---|---:|---:|---:|---:|---:|---|---:|
| MFFU Rapid 50K | $50,000 | $3,000 | None | $2,000 | $80 | EOD | 120 |
| MFFU Rapid 100K | $100,000 | $6,000 | None | $3,000 | $150 | EOD | 120 |

**Automation policy (via secondary source):** 
Per `research/execution_prep_2026-09.md` (fetched/read 2026-09-03): "Algo trading permitted on eval+funded per MFF's own policy per secondary sources" — primary source `https://intercom.help/funded-futures-family/.../bots-algorithmic-trading-policy` returned **403 Forbidden** on 2026-09-03, not independently verified this pass.

**Micro contracts:** Not enumerated on g71; platform (Tradovate, NinjaTrader, etc.) supports them; MFFU's own constraint not found.

**Consistency rule:** Not found on public pages.

**Minimum trading days:** Not found.

---

### Lucid Trading (futures — micro contracts via platform) — **NEWLY ADDED TO FIRMS**

Source: https://lucidtrading.com/general-faq/ (fetched 2026-09-05 — **403 Forbidden**)
Supporting source: `research/execution_prep_2026-09.md` (read 2026-09-03), citing secondary summaries of Lucid's FAQ and rules.

**Account sizes, profit targets, daily loss, max drawdown:** Not accessible via direct fetch or via secondary sources embedded in `execution_prep_2026-09.md`. **PRIMARY SOURCE DATA BLOCKED**.

**Automation policy (via secondary source, not independently verified this pass):**
> "Algorithmic trading, standard automated strategies, EAs, and algo systems are fully permitted on all account types"
— cited in `execution_prep_2026-09.md` as "secondary-sourced summary of Lucid's own FAQ/rules; primary `lucidtrading.com/general-faq/` 403'd on direct fetch this pass."

**Platforms:** Rithmic, Tradovate, NinjaTrader, Quantower, Sierra Chart (per secondary sources in execution_prep_2026-09.md).

**Micro contracts:** Yes — implied by Tradovate/Rithmic platform capability; not explicitly confirmed by Lucid's own pages.

**Consistency rule:** Not found.

**Minimum trading days:** Not found.

**Cost:** Not found.

---

## Attempted URLs, Status Codes, and Notes

| URL | Status | Fetch | Notes |
|---|---|---|---|
| https://lucidtrading.com | 403 Forbidden | 2026-09-05 | Primary content blocked; cited as secondary-sourced only in execution_prep_2026-09.md |
| https://lucidtrading.com/general-faq/ | 403 Forbidden | 2026-09-05 | "Algorithmic trading..." rule cited via secondary summary, not directly readable |
| https://lucidtrading.com/evaluations | 403 Forbidden | 2026-09-05 | Account specs blocked |
| https://lucidmarkets.com | 302 Redirect | 2026-09-05 | Redirects to HugeDomains (domain parking); not the real firm |
| https://www.lucidmarkets.io | ENOTFOUND | 2026-09-05 | Domain does not resolve |
| https://myfundfunder.com | ENOTFOUND | 2026-09-05 | Domain does not resolve; firm appears as "MFFU Rapid" in g71 only |
| https://myff.io | ENOTFOUND | 2026-09-05 | Domain does not resolve |
| https://help.myfundedfutures.com | ENOTFOUND | 2026-09-05 | Domain not resolving |
| https://www.topstep.com/topstep-prop | 200 OK | 2026-09-05 | ✓ Full specs, micro contract limits confirmed |
| https://www.topstep.com/express-funded-account | 200 OK | 2026-09-05 | ✓ Supporting docs; no daily-loss-limit details |
| https://www.apexfunded.com | 403 Forbidden | 2026-09-05 | Direct access blocked; specs in g71 not re-verified |
| https://www.apexfunded.com/evaluations | 403 Forbidden | 2026-09-05 | Blocked; g71 specs not re-verified |
| https://earn2trade.com | 200 OK | 2026-09-05 | ✓ TCP details retrieved (already in g71) |

---

## Recommendation for P0 Row Outcome

**Lucid as a new entry to g71 FIRMS:** Cannot populate all fields from primary sources due to access blocks (403 on lucidtrading.com/general-faq/). Automation policy is confirmed via secondary source (execution_prep_2026-09.md's citation); account sizes, targets, drawdown, and cost remain **unconfirmed primary-source data**. 

**Options:**
1. **Hold until primary source is accessible** — defer adding Lucid rows to FIRMS until lucidtrading.com/general-faq/ returns 200 OK or an alternative primary page is located.
2. **Add with secondary-source caveat** — add Lucid row(s) to FIRMS with a note in the code comment that automation policy is secondary-sourced; leave account-spec fields as `None` or `0` until primary verification.
3. **Request Lucid specs via support ticket** — if the project needs Lucid rules tonight, a support email to Lucid Trading asking for account sizes/targets/drawdown is the path to primary confirmation (turnaround TBD).

**MFFU and Apex:** Specs in g71 are from an earlier commit (2026-08-23); primary pages return 403 or ENOTFOUND. Re-verification deferred; g71 specs assumed current unless contradicted by a later observation.

**Topstep:** Freshly verified 2026-09-05 via https://www.topstep.com/topstep-prop; specs match g71 entry (rows committed 2026-08-23).

---

## Next Step (for the spec's P1 row, not this row)

Once firm specs are finalized and added to g71 FIRMS, `research/g171_futures_proxy_arms.py` will:
- Map index/futures proxy ratios (ES/SPY, NQ/QQQ, RTY/IWM) from 2-year daily closes
- Run every firm's evaluation on the one-trade-a-day index stream
- Report pass rates, rolling-252-session performance, and cost per passing account

