# G71 · agentteam — the standing team, the tier each role runs on, and the bill

Diagnosis pass, 2026-08-29. Nothing here is applied. Prices fetched live today;
the monthly figure is reproduced by `research/g71_agentteam_cost.py`.

**Answer in one line:** eight standing roles, five of which run on a cheap or free
tier, one of which genuinely needs a frontier model — **$165/mo recommended, $110/mo
lean**, against **$195/mo that the current `router.json` would already be spending**
if the loop ran at that volume, all of it on the Anthropic key.

**Safety bound, stated once:** the "cowork agents create their own emails / unlimited
cloud keys" idea is out. That is multi-accounting to evade rate limits, it breaks
every provider's terms, and one ban takes the whole team down mid-session. Everything
below is a paid plan, a metered API, a published free tier, or a model running on this
box. Nothing else is designed for.

---

## 0. What already exists (build on it, don't reinvent it)

| piece | where | what it already does |
|---|---|---|
| per-row provider routing | `Desktop\loop-local\dispatch.py` | one `claude -p` per spec row, **per-process env**, own git worktree per row. This is the multi-agent runner. It is the thing "one Agent SDK session cannot do" (its own docstring). |
| tier table | `Desktop\loop-local\router.json` | four named tiers — `bulk` / `cheap` / `think` / `edge` — already the right shape. |
| verify gate | `~\.claude\hooks\verify-before-done.py` | Stop hook, reads `verify:` from the nearest `CLAUDE.md`, blocks the turn on non-zero, 3 tries. Already runs `research/regression_gate.py` on every edit in this repo. |
| cheap subagents | `~\.claude\agents\glm.md`, `deepseek.md` | GLM 5.2 and DeepSeek via OpenRouter's Anthropic-compatible endpoint. |
| local bulk tier | ollama on `localhost:11434` | `qwen3.5:4b`, `qwen3.5:2b`, `qwen2.5vl:3b`, `nomic-embed-text` — alive, $0/token. |
| the lanes | `DIRECTION.md:117-145` | green / amber / red. Section 4 below **extends** it; it contradicts nothing there. |

The team is not new infrastructure. It is eight named roles, eight prompt files, eight
schedule entries, and a corrected `router.json`.

---

## 1. The roles

Each role owns **one question**. A role that owns two questions is two roles.
Hire order is the left column: 1–3 first, the rest as they earn it.

### 1 · QUARTERMASTER — "is every judgement still on disk, and is it staged?"

- **Trigger:** post-commit hook + nightly 23:00.
- **Does:** counts `research/build_deck.py::marked_card_ids()`, diffs against yesterday's
  count, asserts no corpus file shrank in bytes or rows, asserts every `*.jsonl` under
  `research/marks/` and every judgement file named in `CLAUDE.md` is either tracked or
  covered by an un-ignore rule, runs `git check-ignore -v` on each. Writes one line to a
  ledger. **Read-only. It never touches a mark file.**
- **Unattended: all of it.** It is arithmetic over file metadata.
- **Needs Austin:** nothing. It pages him only when a count goes *down*.
- **Why it is hire #1:** the `.gitignore` trap has fired twice (`CLAUDE.md`, "The trap,
  and it has already fired twice"), the no-repeat guarantee has failed three ways
  (memory: *the no-repeat guarantee*), and 1,057 judged symbol-days is the only
  unrecoverable asset in the project. This role costs $0.35/mo and insures all of it.
- **Tier: `bulk` (local qwen3.5:4b).** No judgement required — the check is `len()`.

### 2 · GATEKEEPER — "did anything that used to fire go silent?"

- **Trigger:** on-edit (the Stop hook, already live) + nightly full sweep.
- **Does:** `research/regression_gate.py`, `research/test_runner_stop.py`,
  `research/test_universe_single_source.py`. On RED it escalates to a model **once**, to
  classify stale-baseline vs real-regression, and stops.
- **Unattended:** running it, and diagnosing a RED into a one-paragraph classification.
- **Needs Austin:** **re-locking `research/baseline_3.8.json`. Never unattended.**
  `CLAUDE.md` is explicit — the gate was RED for 16 days with nobody noticing.
- **Tier: none, then `cheap`.** The gate is a Python script; it burns zero model tokens
  until it fails. Budgeted at 6 model escalations/month.

### 3 · SCEPTIC — "is the branch you are about to write reachable at all?"

- **Trigger:** pre-flight, mandatory, before any ticket that adds a variable to
  `downgrade.py` or a gate to `signal_runner.py` / `backtest_week.py`; plus on-commit
  for diffs touching those three files.
- **Does:** counts the population the proposed rule targets *before* anyone codes it,
  and reports two numbers: how many of 45,175 detections it would trip, and how many of
  ~1,016 traded. Then reads the result against the two known failure shapes.
- **Unattended: all of it.** It writes a count and a paragraph, never a rule.
- **Needs Austin:** nothing — but its output is what stops a red-lane ticket from being
  built on a fourth guess (`PHASES.md` P25).
- **Why it is hire #3 and the only frontier seat:** this repo has a *named recurring bug
  class* with four confirmed instances. `PHASES.md` P15 says it outright: *"This is the
  fourth instance of the unreachable-rule class."* P15 shipped three faithful readings of
  `level_not_respected`, all dead — the last trips **13 of 45,175, 0 of 1,016 traded**.
  The mirror failure is P18's large counter body: trips **57.2% of the book**, delta
  **+0.029R**, wrong-signed. Both are the same disease — a variable whose target
  population is degenerate or universal. Catching one instance pays for the seat for a
  year. **Cheap models do not catch this**; they confirm the code compiles.
- **Tier: `edge` (Claude Opus 5).** This is the seat Austin's money should buy.

### 4 · LIBRARIAN — "has Austin already answered this?"

- **Trigger:** on-demand, and **mandatory before any red-lane ticket reaches him**.
- **Does:** `research/corpus_query.py` over the 5,460 provenance-tagged rows in
  `corpus_index.jsonl`. Answers CONFIRMED / CONTRADICTED / UNMENTIONED against a rule he
  already stated, never a new rule, classes never blended (`corpus_query.py:5-11`).
- **Unattended: all of it.** `DIRECTION.md:122-126` calls this *"the most productive
  unattended lane in the project"* and this design does not touch that.
- **Needs Austin:** resolving a CONTRADICTED — two things he said that disagree. Red.
- **Tier: `plan` (GLM).** Retrieval and classification over a fixed index. The hard part
  (never blending TRADER_SAID with DERIVED) is enforced by the script, not the model.

### 5 · METRICIAN — "what does the number actually say?"

- **Trigger:** on-demand per ticket + weekly re-baseline Sunday 06:00.
- **Does:** runs the existing rigs — `t60_baseline`, `t61_onwatch_ab`, `backtest_2y` +
  `build_bt2y_report`, the `g71_*` A/B style. Reports **held-out S recall and false fires
  BEFORE the in-sample numbers**, both grade ladders side by side, every time.
- **Unattended:** running a rig that exists; sweeps; writing the finding next to the
  script (`DIRECTION.md:126-128`).
- **Amber, flag it:** any run that moves a published figure — say which and by how much.
- **Needs Austin:** nothing, but it is **forbidden from concluding on mean R.** Standing
  finding: every A/B this project has run moves less than its own **±1.5799R** error bar
  (memory: *error bar exceeds the arms*). A cheap model will happily report a +0.25R
  "win". The rule is in the role prompt, not in the model's judgement.
- **Tier: `plan` (GLM)** to run an existing rig. **`edge`** to *design a new* rig or to
  interpret a result that moves a gate. That split is the whole cost story.

### 6 · BRIDGE — "would the live path have taken the trade the backtest booked?"

- **Trigger:** nightly, weekdays, 20:00.
- **Does:** replays one session through `live_scanner._tier()` and through
  `backtest_week`'s gate and diffs the two trade sets. Reports trades the book took that
  the live path would have left as WATCH, and vice versa.
- **Unattended:** the measurement, entirely. Read-only on both paths.
- **Needs Austin:** changing live routing, `GOVERNOR_S_CAP`, or the halt rule. Red.
- **Why it exists:** `DIRECTION.md:34-38` calls the live/backtest divergence *"the real-
  money blocker and it outranks every gate"* — and **nobody owns it**. It is also the
  paragraph that has already gone stale (finding F1 below). A standing role would have
  caught that the day T25 landed.
- **Tier: `plan` (GLM).** Two code paths, one diff, no new judgement.

### 7 · SCRIBE — "does the board still match the repo?"

- **Trigger:** post-commit + nightly.
- **Does:** every claim in `DIRECTION.md` / `PHASES.md` / `TASKS.md` that names a
  `file:line`, a commit hash, or a number — re-resolve it. Line moved? Number changed?
  Flag it. Appends to `TASKS.md` Done with the commit hash and the number that moved
  (`DIRECTION.md:150-157`, step 4).
- **Unattended:** flagging drift, appending Done rows with a hash and a number.
- **Needs Austin:** nothing. It never rewrites a conclusion, only reports that a
  conclusion's anchor moved.
- **Tier: `cheap` (DeepSeek V4-Flash).** Grep, resolve, compare. Mechanical.

### 8 · CONCIERGE — "what is the smallest thing Austin can answer next?"

- **Trigger:** on-demand, and automatically when the red queue holds ≥3 open questions.
- **Does:** builds the deck / probe / Q&A page against the delivery contract — saves as
  he works, exports without a round trip, works on a phone, **static SVG charts rendered
  in Python** (`CLAUDE.md`, Homework instruments). Drafts the question list ranked by how
  many red tickets each answer unblocks.
- **Unattended:** building the instrument. Green (`DIRECTION.md:129-131`).
- **Needs Austin:** grading, and **serving him a card** — being *served* a card counts as
  consuming it (memory: *the no-repeat guarantee*), so the deck is built unattended and
  served only when he sits down.
- **Tier: `plan` (GLM)** to build the page. The *ranking* of what to ask is where a
  frontier read helps and it is cheap — it is one paragraph.

---

## 2. Model tier per role

| role | tier | model | genuinely needs frontier? |
|---|---|---|---|
| QUARTERMASTER | `bulk` | ollama `qwen3.5:4b`, local | no — it is `len()` and `git check-ignore` |
| GATEKEEPER | none → `cheap` | script; DeepSeek V4-Flash on RED | no — pass/fail, then one classification |
| SCRIBE | `cheap` | DeepSeek V4-Flash | no — resolve an anchor, compare a number |
| LIBRARIAN | `plan` | GLM 5.3 via the coding plan | no — the script enforces the hard rule |
| BRIDGE | `plan` | GLM 5.3 | no — two paths, one diff |
| CONCIERGE | `plan` | GLM 5.3 | no for the build; the ranking is one paragraph |
| METRICIAN | `plan` → `edge` | GLM 5.3, escalating to Opus 5 | **only** to design a new rig or read a gate-moving result |
| SCEPTIC | `edge` | Claude Opus 5 | **yes** — this is the seat that catches the unreachable-rule class |

**The honest test for "does this need frontier?"** — if the role's failure mode is
*producing a plausible wrong conclusion nobody checks*, it needs frontier. If the failure
mode is *crashing*, it does not. QUARTERMASTER, GATEKEEPER and SCRIBE cannot produce a
plausible wrong conclusion; their output is a number that either matches or does not.
METRICIAN and SCEPTIC can, and P15 and P18 are what that looks like in this repo.

**Existing subagent defs need three edits** (`~\.claude\agents\`) — see findings F3/F4:
`glm.md` pins `z-ai/glm-5.2` (z.ai now routes 5.2 → 5.3), `deepseek.md` pins
`deepseek/deepseek-chat` (current ids are `deepseek-v4-flash` / `deepseek-v4-pro`), and
both carry the same OpenRouter key in cleartext.

---

## 3. What it costs — live prices, 2026-08-29

### The published numbers

| provider | product | price |
|---|---|---|
| **Z.ai GLM Coding Plan** | Lite / Pro / Max | **$18 / $72 / $160 per month**, 30% off annual ($12.60 / $50.40 / $112 effective). Quota is credits, marketed as ~400 / 2,000 / 8,000 prompts per **week**. Coding-tool use only (Claude Code, Cline, Roo) — **not** general API. |
| **DeepSeek API** | V4-Flash | **$0.22 in / $0.66 out** per MTok off-peak; $0.44 / $1.32 peak. Cache hit **$0.007**. |
| | V4-Pro | **$0.66 / $1.98** off-peak; $1.32 / $3.96 peak. |
| | peak window | 01:00–04:00 and 06:00–10:00 UTC, **Mon–Fri only**. Everything else, weekends included, is off-peak. |
| **Google Gemini** | free tier | **$0** — 3.7/3.6/3.5 Flash and Flash-Lite, rate-limited, **and content is used to improve Google's products.** |
| | paid | 3.7 Flash **$0.75 / $3.75**; 3.5 Flash $1.50 / $9.00; 2.5 Flash $0.30 / $2.50; 3.1 Pro $2–4 / $12–18. |
| **OpenAI** | gpt-5.6-luna | **$0.20 / $1.20** (batch $0.10 / $0.60) |
| | gpt-5-nano | **$0.05 / $0.40** |
| | gpt-5.5-pro | $30 / $180 · o1-pro $150 / $600 |
| | ChatGPT | Plus **$20**, Pro **$100** (5× Plus incl. Codex) or **$200** (20×), Business $25/seat |
| **Anthropic** | Opus 5 | **$5 / $25**, cache hit $0.50, batch $2.50 / $12.50 |
| | Sonnet 5 | **$2 / $10**, cache hit $0.20 (the $2/$10 launch price is now permanent) |
| | Haiku 4.5 | **$1 / $5**, cache hit $0.10 |
| | Fable 5 | $10 / $50 |
| | consumer | Pro **$20/mo** ($17 annual), Max from **$100/mo** (5×) / **$200** (20×) |

### The team's bill

Modelled in `research/g71_agentteam_cost.py` — 164 runs/month, **47M input / 3.0M output
tokens**, 80% prompt-cache hit rate (the repo docs are byte-identical every run).

| scenario | plan | edge seat | **$/month** |
|---|---|---|---:|
| **A · status quo** — `router.json` as committed, every tier on `api.anthropic.com` | Sonnet 5 | Opus 5 | **$195.45** |
| **B · RECOMMENDED** — local bulk, DeepSeek cheap, GLM Pro, frontier sceptic | GLM Pro $72 | Opus 5 $91.80 | **$165.05** |
| **C1 · Lite probe** | GLM Lite $18 | Sonnet 5 | $55.97 — **but 2,820 / 1,600 prompts, over quota** |
| **C2 · lean** — same shape, Sonnet sceptic | GLM Pro $72 | Sonnet 5 $36.72 | **$109.97** |
| **D · floor** — everything on DeepSeek V4 off-peak, capability aside | Flash | V4-Pro | **$18.78** |

**Recommendation: B, $165/mo.** Three things fall out of that table:

1. **DeepSeek is a rounding error.** The entire cheap lane is **$1.25/month**. The reason
   not to run everything on it is capability, not price — scenario D costs $18.78 and
   would put the unreachable-rule class on a model that will not catch it.
2. **GLM Lite does not fit.** At 2,820 model turns/month the plan lane needs Pro. Start on
   Lite for two weeks anyway — the prompt→credit conversion above is z.ai's marketing
   number, not a measurement, and F7 says nothing in this repo meters agent turns yet.
3. **The Opus seat is 56% of the bill and it is the right 56%.** Scenario C2 saves $55/mo
   by downgrading the SCEPTIC to Sonnet. That is the one saving to refuse: P15 burned
   three build cycles on a variable that trips 13 rows in 45,175.

**On "American GPT": skip it.** gpt-5.6-luna at $0.20/$1.20 versus DeepSeek V4-Flash at
$0.22/$0.66 off-peak is a wash at this team's ~16:1 input:output ratio ($4.40 vs $4.18 per
16M+1M). ChatGPT Plus/Pro adds a fourth vendor and a second agent harness with no lane
here that GLM + Claude Code does not already cover. Buy it if he wants ChatGPT for reasons
outside this repo; do not buy it for the team.

**Gemini's role is free-tier only, with one hard rule: the free tier never sees a mark
file.** Google states free-tier content is used to improve their products. That is fine
for public-doc summarisation and web research; it is not fine for 1,057 judged symbol-days.
Paid Gemini 3.7 Flash at $0.75/$3.75 is 3.4× DeepSeek's input price for the same lane, so
there is no reason to pay for it here.

**Austin's Claude Max plan is not in any of these figures and stays reserved for him** —
that was the requirement. The team runs on its own metered Anthropic key
(`ANTHROPIC_BACKUP_API_KEY`, already what `router.json` uses) plus the GLM subscription.

---

## 4. Unattended vs attended — the one page

This **extends** `DIRECTION.md:117-145`. Its green/amber/red lanes are unchanged; the
rows in **bold** are new and the "owner" column is new throughout.

| lane | thing | owner | why here |
|---|---|---|---|
| 🟢 green | corpus validation via `corpus_query.py` | LIBRARIAN | unchanged — the most productive unattended lane |
| 🟢 green | re-running an existing measurement rig, sweeps | METRICIAN | unchanged — free and reproducible |
| 🟢 green | bug fixes with a failing test first | METRICIAN | unchanged |
| 🟢 green | building homework instruments | CONCIERGE | unchanged; delivery contract is hard |
| 🟢 green | repo hygiene touching no mark file, no published number | SCRIBE | unchanged |
| 🟢 green | **mark-file custody audit — counts, byte sizes, `git check-ignore`, read-only** | QUARTERMASTER | **new.** The trap has fired twice; the audit touches nothing |
| 🟢 green | **doc-vs-code drift — re-resolving every `file:line`, hash and number in the three board docs** | SCRIBE | **new.** F1 below is a live instance |
| 🟢 green | **live-vs-backtest parity measurement, read-only on both paths** | BRIDGE | **new.** `DIRECTION.md` calls this the top blocker and assigns it to nobody |
| 🟢 green | **reachability pre-flight: count the population a proposed rule targets, before coding it** | SCEPTIC | **new, and mandatory.** Four instances of the unreachable-rule class |
| 🟡 amber | threshold tuning inside `downgrade.py` | METRICIAN | unchanged — every constant there is a commented guess |
| 🟡 amber | anything that moves a published figure — name it and the delta | METRICIAN | unchanged |
| 🟡 amber | **changing a default to match something Austin has already said on the record** | METRICIAN | **new.** P24: the shipped 50% runner vs his stated 10%, worth 0.002R. Config drift, not a finding |
| 🔴 red | grading cards | Austin | unchanged — the only unrecoverable input |
| 🔴 red | any new rule, or resolving a contradiction between two things he said | Austin | unchanged |
| 🔴 red | `INCLUDE_SPY_IN_BACKTEST`, retiring a symbol, changing the money gate | Austin | unchanged |
| 🔴 red | wiring `downgrade.py` into detection | Austin | unchanged |
| 🔴 red | **re-locking `research/baseline_3.8.json`** | Austin | **new, and it is the sharpest one.** `CLAUDE.md` already forbids silent re-locking; this names the owner |
| 🔴 red | **serving Austin a card** — being served counts as consuming it | Austin | **new.** Build the deck unattended; hand it over only when he sits down |
| 🔴 red | **changing live routing** — `_tier()`, `GOVERNOR_S_CAP`, the loss halt | Austin | **new.** It is the only path that spends real money |
| 🔴 red | **re-freezing or voiding the forward book** | Austin | **new.** *"no freezing, version snapshots for rollback"* (`CLAUDE.md`) |

**The rule underneath the table:** a task is unattended when its worst outcome is a wrong
paragraph in a report, and attended when its worst outcome is a lost judgement, a
re-locked baseline, or a real order. Everything green above is read-only or reproducible;
everything red destroys something that cannot be rebuilt.

---

## 5. Findings

### F1 — HIGH · `DIRECTION.md`'s number-one blocker describes a live path that no longer exists

`DIRECTION.md:34-38` says the live scanner promotes to TRADE only on legacy `A+`, that
`A+` fires twice in 45,193 signals, and that this "outranks every gate." Since T25
(2026-08-28) `live_scanner.py` forces `ENABLE_SAC_LADDER=1` and maps Austin's ladder
through `SAC_TIER` — `live_scanner.py:528-531`: *"so `A+` here already means his S, not
the legacy A+/A pool."* The gate at `live_scanner.py:579` reads `if grade != "A+"`, but
`grade` is now `downgrade.py::score` output. The cited line number is also stale:
`_tier` is at **:567**, not **:546**.

The blocker may still be real in a different form — nobody has measured how many S-graded
live signals actually reach TRADE past `GOVERNOR_S_CAP` and the account-wide loss halt.
That measurement is the BRIDGE role's first job. What is *not* true is the paragraph as
written, and it is currently steering the whole board.

```diff
--- a/DIRECTION.md
+++ b/DIRECTION.md
@@ -34,4 +34,10 @@
-1. **The live scanner does not run this book.** `live_scanner._tier():546` promotes to TRADE
-   only on `grade == "A+"`, and `A+` fires **twice in 45,193 signals over two years**. The
-   1,017-trade book comes from `backtest_week`, a different gate. **Every number in this table
-   describes a system the live path would not trade.** This is the real-money blocker and it
-   outranks every gate.
+1. **The live scanner runs a different gate from the book — but no longer the legacy one.**
+   Superseded 2026-08-28 by T25: `live_scanner.py` forces `ENABLE_SAC_LADDER=1`, so the
+   `grade != "A+"` test at `live_scanner.py:579` is reading Austin's S off
+   `research/downgrade.py::score` through `SAC_TIER` (`live_scanner.py:528-531`), not
+   `_grade_pa`'s candle-shape verdict. The "A+ fires twice in two years" figure describes
+   the pre-T25 path and no longer applies. **What is still unmeasured, and still the
+   real-money blocker, is how many S signals survive `GOVERNOR_S_CAP` and the account-wide
+   two-loss halt (`live_scanner.py:571-583`) to reach TRADE, versus what `backtest_week`
+   books on the same days.** Nobody owns that diff; see G71's BRIDGE role.
```

### F2 — HIGH · `router.json` has no cheap tier; every lane bills the Anthropic key

`Desktop\loop-local\router.json` — `cheap`, `think` and `edge` all point at
`https://api.anthropic.com` with `ANTHROPIC_BACKUP_API_KEY`. Both `_why` fields say the
same thing: *"2026-08-22: no OpenRouter credits. Repointed off google/gemini-3.7-flash to
Claude direct."* That was a one-week workaround that is now the standing config. It is the
direct cause of Austin's "I need to save my max plan for me" — scenario A, **$195/mo**, is
what this file does at team volume. Only `bulk` (ollama `qwen3.5:4b`, present and running)
is actually cheap.

```diff
--- a/router.json
+++ b/router.json
@@
   "cheap": {
-    "_why": "2026-08-22: no OpenRouter credits. Repointed off google/gemini-3.7-flash to Claude direct. Haiku 4.5 is the cheap tool-capable tier.",
-    "base_url": "https://api.anthropic.com",
-    "model": "claude-haiku-4-5-20251001",
-    "api_key_env": "ANTHROPIC_BACKUP_API_KEY",
+    "_why": "2026-08-29 G71: DeepSeek V4-Flash off-peak is $0.22/$0.66 vs Haiku 4.5's $1/$5 -- 4.5x cheaper in, 7.6x cheaper out, for SCRIBE/GATEKEEPER-class work that cannot produce a plausible wrong conclusion.",
+    "base_url": "https://api.deepseek.com",
+    "model": "deepseek-v4-flash",
+    "api_key_env": "DEEPSEEK_API_KEY",
     "thinking_tokens": 0
   },
   "think": {
-    "_why": "2026-08-22: no OpenRouter credits. Repointed off google/gemini-3.7-flash to Claude direct. Sonnet 5 + 16k thinking is the code-editing tier.",
-    "base_url": "https://api.anthropic.com",
-    "model": "claude-sonnet-5",
-    "api_key_env": "ANTHROPIC_BACKUP_API_KEY",
+    "_why": "2026-08-29 G71: the plan lane (LIBRARIAN/METRICIAN/BRIDGE/CONCIERGE, ~2,820 turns/mo) runs on the GLM Coding Plan, a flat $72 rather than ~$94/mo metered on Sonnet 5.",
+    "base_url": "https://api.z.ai/api/anthropic",
+    "model": "glm-5.3",
+    "api_key_env": "ZAI_API_KEY",
     "thinking_tokens": 16000
   },
```

`edge` stays on Opus 5 — that is the SCEPTIC seat and it is the one worth paying for.
Verify z.ai's Anthropic-compatible base URL against their current docs before applying;
the GLM Coding Plan is licensed for coding tools, and the OpenRouter path in
`~\.claude\agents\glm.md` is the fallback if the direct endpoint is not covered.

### F3 — MEDIUM · an OpenRouter API key sits in cleartext in two agent definition files

`~\.claude\agents\glm.md` and `~\.claude\agents\deepseek.md` both carry the **same**
`sk-or-v1-…` key inline in their YAML front matter. Not quoted here. Two problems: it is
plaintext on disk in the directory that `~\.claude\hooks\sync-settings.py` operates over,
and one key serves both agents, so rotating for one rotates for both. Fix: rotate the key,
move it into the `env` block that `hydrate-env.py` fills (the mechanism `CLAUDE.md` says is
already local-only and self-syncing), and reference it as `${OPENROUTER_API_KEY}`.

### F4 — MEDIUM · both subagent defs pin retired model ids

`glm.md` pins `z-ai/glm-5.2`; z.ai's own devpack now auto-routes 5.2/5.1 → GLM-5.3 and
4.7 → GLM-5.3-Flash, so the pin is silently resolving to something else. `deepseek.md`
pins `deepseek/deepseek-chat`; DeepSeek's current ids are `deepseek-v4-flash` (updated to
`-0731`) and `deepseek-v4-pro` (`-0813`). A team whose cost model assumes V4-Flash pricing
should name V4-Flash.

### F5 — MEDIUM · there is no `.claude/agents/` in this repo

`C:\Users\aharg\Desktop\Projects\tradingbot\.claude\` holds only `scheduled_tasks.lock`
and `worktrees\`. Both subagent defs are global (`~\.claude\agents\`), so a role scoped to
*this* repo — one that knows about `marked_card_ids()`, the ±1.5799R error bar, the two
ladders — has nowhere to live and gets re-explained in every prompt. The eight roles above
should be eight files in `tradingbot\.claude\agents\`, committed, so they version with the
repo they describe. Sketch of the first:

```markdown
---
name: quartermaster
description: Mark-file custody audit. Read-only. Runs nightly and post-commit.
model: qwen3.5:4b
---
ONE QUESTION: is every judgement still on disk, and is it staged?
NEVER open a mark file for writing. NEVER run git clean. NEVER git add -f without
also adding an un-ignore rule in the same breath.
DO: python -c "import sys; sys.path.insert(0,'research'); import build_deck;
    print(len(build_deck.marked_card_ids()))"  -> compare to yesterday's ledger line.
DO: git check-ignore -v on every file named under CLAUDE.md "Where they live".
DO: assert no corpus file lost rows or bytes since the last run.
PAGE AUSTIN only if a count went DOWN. Otherwise append one line and exit 0.
```

### F6 — LOW · `.disc_token_tmp` is untracked and unignored in the repo root

`git check-ignore -v .disc_token_tmp` returns nothing — it is one `git add -A` away from
being committed. Given the filename, treat it as a credential. Either add it to
`.gitignore` or delete it. (Named, not read.)

### F7 — INFO · nothing meters agent token use, so the cost model above is an estimate

The per-role volumes in `g71_agentteam_cost.py::ROLES` are calibrated off session shapes
in this repo, not measured. Before committing to GLM Pro over Lite, log actual turns and
tokens per role for two weeks — `dispatch.py` already runs one process per row, so a
per-row usage line is a small addition and it turns section 3 from a projection into a
measurement. This is the same standard the repo applies to trading numbers.

### F8 — INFO · 308 scripts in `research/`, no index, no owner

`ls research/*.py | wc -l` → **308**. METRICIAN's first job is a one-page index: which rig
answers which question, which are superseded, which are `_`-prefixed scratch. Cheap, and
it is what makes the other seven roles able to find the rig instead of writing a ninth one.

---

## 6. First three hires, in order

1. **QUARTERMASTER** — $0.35/mo, local model, insures the only unrecoverable asset.
2. **SCRIBE** — $1/mo, DeepSeek. F1 is what a missing SCRIBE looks like: the board's
   top-priority paragraph went stale on 2026-08-28 and is still steering work today.
3. **SCEPTIC** — $92/mo, Opus 5. Four instances of the unreachable-rule class. It pays for
   itself the first time it stops a P15.

The other five come with the GLM Pro subscription and cost nothing marginal.

---

**Sources (fetched 2026-08-29):**
[Z.AI devpack overview](https://docs.z.ai/devpack/overview) ·
[GLM Coding Plan tier prices](https://www.aipricing.guru/z-ai-subscription-pricing/) ·
[DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/) ·
[Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) ·
[OpenAI API pricing](https://developers.openai.com/api/docs/pricing) ·
[ChatGPT plan pricing](https://www.aipricing.guru/chatgpt-subscription-pricing/) ·
[Claude API pricing](https://platform.claude.com/docs/en/about-claude/pricing) ·
[Claude plan pricing](https://claude.com/pricing)

Script behind every dollar figure: `research/g71_agentteam_cost.py`.
