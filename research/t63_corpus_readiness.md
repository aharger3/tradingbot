# T63 — Corpus Readiness Probe

**Date:** 2026-08-23
**Question:** not "is the corpus right" — **can it answer a specific question at all, and how would we know to trust the answer?**
**Scope:** `research/` in `tradingbot` only (the raw scrape/extraction corpus). Did not touch `omen-corpus` (separate repo) or the OMEN engine's own settled rules (`omen-rulebook.md`) except to identify what Austin has already decided himself vs. what the corpus says.
**Rule honored throughout:** corpus is a validator only. Nothing below proposes a new rule; every answer is CONFIRMED / CONTRADICTED / UNMENTIONED against a rule Austin already stated (or an open question he already logged).

---

## 1. Inventory — what's actually in `research/`

`research/` is **497 top-level files, 13 GB total**, plus deep subdirectories. It is one flat bucket: raw transcripts, extracted-rule docs, backtest reports, jsonl data dumps, one-off Python probes, and logs, all living side by side with no separation between "source," "derived," and "scratch."

### The rule-extraction documents (what answered the 3 questions below)

| file | lines | what it is | gitignored? |
|---|---:|---|---|
| `research/EXTRACTED_TRADING_RULES.md` | 1,002 | Verbatim rule extraction from Day 5/6 boot-camp transcripts, timestamped | No |
| `research/scarface-rules-videos.md` | 12,535 | Rule extraction across 89 Whisper-transcribed videos, 36 groups | No |
| `research/scarface-rules-mastermind.md` | 284 | Mastermind-call rule extraction | No |
| `research/scarface-rules-accelerator.md` | 113 | Accelerator-course rule extraction | No |
| `research/scarface-rules-coaching-bonus.md` | 243 | Coaching/bonus-file rule extraction | No |
| `research/scarface-rules-youtube.md` | 527 | Standalone YouTube rule extraction | No |
| `research/scarface-rules-discord.md` | 194 | Discord trade-feedback rule extraction | No |
| `research/84rule-sizing-dossier.md` | 344 | Every quote across all sources on 84%-rule **sizing** specifically, contradiction called out explicitly, no conclusion drawn | No |
| `research/hallucination-audit.md` | 254 | Line-by-line diff of every coded engine rule vs. the rulebooks above — MATCHES / DIVERGES / SOURCE-SAYS-MORE verdicts | No |
| `research/parameter_catalog_draft.md` | 86 | Every tunable in `signal_runner.py`, cited back to its A/B evidence and/or source quote | No |

### The raw material behind those extractions

| source | files | what |
|---|---:|---|
| `research/video_transcripts/` | 93 | Raw + checkpointed video transcripts |
| `research/videos_extract/` | 37 | Extraction working files |
| `research/youtube_batches/` | 19 | Batch extraction outputs |
| `discord_data/`, `circle_data/`, `youtube_data/` | 45 GB total | Raw scrape (per `CORPUS.md`), outside `research/`, all gitignored |

### The corpus's own bulk jsonl artifacts (the "mine it for new detectors" corpus, separate from the rule-extraction docs above)

| file | rows | gitignored? |
|---|---:|---|
| `research/corpus_instances.jsonl` | 10,379 | **Yes** (`research/*.jsonl`, no un-ignore rule matches `corpus_*`) |
| `research/corpus_entries.jsonl` | 2,882 | **Yes** |
| `research/corpus_normalized.jsonl` | 2,876 | **Yes** |
| `research/corpus_frames.jsonl` | 1,830 | **Yes** |
| `research/corpus_setup_rules.jsonl` | 712 | **Yes** |
| `research/corpus_rule_candidates.jsonl` | 185 | **Yes** |
| `research/corpus_backtest_manifest.jsonl` | 701 | **Yes** |

**At risk:** all seven of these are covered by `research/*.jsonl` in `.gitignore` and none matches an un-ignore exception (`!research/*marks*.jsonl`, `!research/mark_batch_*.jsonl`, `!research/*verdicts*.jsonl`, `!research/*reviews*.jsonl`, `!research/rule_ballot_*.jsonl`, `!research/probe_*.jsonl`, `!research/t60_silent_days.jsonl`). Per `tradingbot/CLAUDE.md`'s own warning, this is the exact trap that already ate the T6 decks once. These are **not human judgement files** (they're bulk extraction/backtest artifacts, in principle regenerable) — but "regenerable" here means re-running paid/rate-limited API calls and days of pipeline work per `CORPUS.md`'s own stage-by-stage account, so losing one uncommitted is expensive even if not irreplaceable. Not fixing this now (out of scope, read-only), flagging it.

### A real index was attempted once and no longer exists

`research/embed_rules.log` records a semantic-embedding build on 2026-08-03: **"ledger -> 32951 distinct rule texts"**, completing at 23:30:59 with **"DONE 32951 embeddings, 0 failures."** The script that built it, `build_embed_index.py`, is gone from the repo (only its compiled `__pycache__/build_embed_index.cpython-313.pyc` survives), and no embedding output file (`.npy`, `.pkl`, or similar) exists anywhere in `research/` or the rest of the repo. **The one attempt at a real index was built, finished clean, and then discarded or never persisted.** There is no query script referencing it either. Today's retrieval tool is `grep`, full stop.

---

## 2. Three test questions

### (a) "What is the one candle rule?" — control question

**CONFIRMED.**

`research/EXTRACTED_TRADING_RULES.md:679-716` ("ONE CANDLE RULE" section, Day 6):

> "One candle rule set up there meaning that the down close candle has to support price for a move to the upside." — `research/EXTRACTED_TRADING_RULES.md:690`

Additional confirming context in the same block: it can be traded on QQQ as well as the individual ticker (`:696-700`), it can act as consolidation support while the ticker itself lags (`:703-707`), and it was applied live to a Tesla earnings-reversal entry (`:710-714`). This matches OMEN's own coded understanding — `hallucination-audit.md` #21 independently re-confirms "the order block and the one candle rule is I consider the exact same thing" across four separate sources (Day 4, Day 6, Hayden's coaching, Building Your Profitable System).

**Time to answer: ~2 minutes.** One grep for "one candle rule", one read of the surrounding 40 lines. This is what "ready" retrieval looks like when it works — a single well-organized extraction doc already had it verbatim with a timestamp.

### (b) "What does the 84% rule trigger on, and how many times per day may it fire?"

**SPLIT — trigger CONFIRMED, per-day cap UNMENTIONED as a stated trader rule.**

**Trigger — CONFIRMED.** Consistent across every source in the corpus (mastermind, accelerator, coaching, YouTube, Discord):

> "The 84% rule is only valid if the first trade would have stopped you out." — YouTube `7kajZjCStT8` [1351s], quoted in `research/84rule-sizing-dossier.md:154`

> "If criteria is the exact same — same break, same retest, same hammer, same stop, same target — 84 percent of the time this second trade should work out." — mastermind `1453512` [00:02:01], `research/84rule-sizing-dossier.md:52`

> "Wait 5, 10, 15, 20 minutes. Come back to same area, same key level, same setup." — mastermind `1453512` [00:01:28], `research/84rule-sizing-dossier.md:60`

So: it arms on a stop-out of an A/A+ setup whose thesis is still intact (not merely any stopped-out trade — `research/84rule-sizing-dossier.md:220`, "The 84% rule is invalidated only if it doesn't break your thesis the first time"), and fires as a re-entry at the same level, 5-20 minutes later, same stop/target, entered on the reclaim candle's **close** (`research/scarface-rules-videos.md:2339`). This matches `omen-rulebook.md`'s already-settled q15 ("what arms it: a stop-out, and the candle must match the trend").

**Per-day cap — UNMENTIONED.** No Scarface or jdub statement in the corpus gives a numeric cap on 84%-rule fires per day. What exists instead:

- The engine's own code comment attributes a cap to the source: `signal_runner.py:1715` — *"Scarface: 84% rule = ONE re-entry per failed setup."* Traced this back through `hallucination-audit.md` #35, which justifies it against: *"84 to 84% roll... whenever you see like you know two or three of the same setups kind of occur that just means it's going to be more of a choppy day"* (`research/84rule-sizing-dossier.md:158`, YouTube `Se_P4N3u48o` [3095s-3116s]). **That source quote is about recognizing a choppy-day regime, not a stated cap on attempts** — the audit's "MATCHES" verdict is an interpretive leap, not a verbatim rule. I would not certify it as CONFIRMED.
- Community (non-canonical) evidence actually runs the other way: a Discord user describes taking the 84% rule a **third** time on the same idea (*"I didn't take it a third time because 84% of 84% is 71%. But it ended up exceeding my profit target the third time"* — `research/84rule-sizing-dossier.md:245`), and a different user states a personal, self-imposed limit of two trades a day (`:251`) — explicitly personal, not attributed to Scarface/jdub as a rule.
- `omen-rulebook.md` already has this settled independently as **"attempts per day: two"** (q14) and `signal_runner.py:434` encodes it as *"2 attempts on one idea TOTAL (the original entry plus a single [re-entry])."* But that is **Austin's own settled answer**, not something the corpus states as a trader rule — it happens to agree with the engine's number, but the corpus does not independently confirm it.

**Verdict on (b): the trigger is genuinely well-documented and citable. The specific "how many times per day" phrasing has no canonical corpus answer — treating the loose choppy-day quote as a confirmation would be exactly the confident-wrong-answer failure mode this probe exists to catch.**

**Time to answer: ~20 minutes**, across 6 grep passes over 5 different documents plus a full read of the sizing dossier and the relevant `hallucination-audit.md` rows, plus a check of `signal_runner.py` to see whether "ONE re-entry" was corpus-attributed or engine-invented.

### (c) "How far from the original entry can a reclaim be and still count?"

**UNMENTIONED.**

Exhaustive search (`reclaim` cross-referenced against `tick`, `point`, `percent`, `%`, `cent`, `distance`, `within`, `too far`, `close`) across every rule-extraction doc in `research/` turns up **zero** statements of a numeric or qualitative tolerance for how far a reclaim candle's close may sit from the original entry price. What the corpus does say about reclaim mechanics is mechanism, not tolerance: it's a candle-close event (`research/scarface-rules-videos.md:2337`), entered on the close rather than waiting for a retest (`:2339`), and — per one divergence the audit already flags — the source wants "strong buying action," not just any close (`research/scarface-rules-videos.md:3418`, audit #32, marked **DIVERGES** because the coded engine variant skips that PA gate).

The number that actually governs this in the live engine — **`BAR_EXTREME_FRAC = 0.25`, 25% of the previous candle's range** — is explicitly Austin's own decision, not the corpus's. `signal_runner.py:622-626`:

> "Distance is BAR_EXTREME_FRAC (0.25) of the PREVIOUS bar's range... Austin settled it as ONE tolerance unit governing the entry trigger, the 84% reclaim and stop slippage alike."

And `omen-rulebook.md:126` already logs this precisely as an open item: **"how far is too far: unspecified → Q&A queue."** The corpus does not resolve it — it was never asked the question by the traders in the source material at all.

**Verdict on (c): UNMENTIONED, cleanly.** No hedging — this is not "the corpus is vague," it's that the concept of a reclaim-distance tolerance does not appear in the source material. Austin's 25% number is an engineering decision made in its absence, correctly logged in his own rulebook as unsourced.

**Time to answer: ~10 minutes** — the grep itself was fast (a few seconds), but confirming the 25% figure wasn't secretly corpus-derived required reading the `signal_runner.py` docstring and cross-checking `omen-rulebook.md`'s own open-question log.

---

## 3. Retrieval assessment

**It is grep-over-flat-files today, not an index**, despite one real attempt:

- **No working index exists.** `embed_rules.log` shows 32,951 rule texts were embedded successfully on 2026-08-03, and then the index and the script that built it both vanished. Nothing queries it. Whatever it would have answered, it isn't available now.
- **The `corpus_*.jsonl` bulk files** (instances/entries/normalized/frames/setup_rules/rule_candidates — 10k+ to a few hundred rows each) are a different corpus from the rule-extraction docs used above, aimed at mining *new* detector candidates rather than answering "what did the trader say." They were not needed for any of the 3 questions above; the hand-curated `.md` extraction docs answered all three. That's a meaningful signal: **the highest-value corpus artifacts for validator questions are the small, human-curated rule docs, not the large raw jsonl dumps** — and those small docs are the ones NOT gitignored.
- **Retrieval quality was inconsistent across the three questions**, not because of tooling but because of source coverage: (a) had one document with the exact answer, fast; (b) required synthesizing across 5+ documents and catching a loose interpretive leap already baked into `hallucination-audit.md`; (c) required knowing to check the *engine code's own comments* to determine that a plausible-looking number wasn't corpus-derived at all. A naive grep-and-answer pass, without that last cross-check, would have risked reporting Austin's own 25% figure back to him as if the corpus had said it — which is precisely the leak this whole probe exists to prevent.
- **What would make this repeatable rather than artisanal:** a single indexed, queryable table over the rule-extraction docs (the ~15,600 lines across `EXTRACTED_TRADING_RULES.md` + `scarface-rules-*.md` + the two audit docs) with each row carrying `{quote, source_file, line/timestamp, trader, topic_tags}`, distinct from and clearly separated from the bulk `corpus_*.jsonl` mining corpus. The dead 2026-08-03 embedding run is the closest existing attempt and is a reasonable starting point if its build script can be recovered — but even a flat CSV/sqlite table with topic tags would turn "20 minutes of grep across 5 files, second-guessing an audit's interpretive leap" into a single query.

---

## Verdict

**Not ready to be a validator.** It answered the control question cleanly, but on both of Austin's real open questions it either required catching another document's own overreach (the 84%-per-day "MATCHES" verdict) or required knowing to check the *engine's* code comments to rule out a false-positive CONFIRMED (the reclaim-distance tolerance, which is Austin's number, not the corpus's). Both of those catches depended on already knowing the codebase and the provenance conventions well enough to distrust a document that looked authoritative. That is not a repeatable process — it is exactly the "front man" problem Austin named on 2026-08-19 (*"we dont know what rules/ideas it decides to save and how to structure and organize them"*), still open.

**What has to be built first:** a single provenance-tagged index over the rule-extraction docs — quote + source file + line/timestamp + trader + topic — that keeps a hard boundary between "trader said this" (citable) and "OMEN's code says the trader said this" (a claim to re-verify, not a citation). Until that boundary is enforced by the retrieval layer instead of by the reader's judgment call each time, every corpus answer needs the same manual second pass this probe just did — which does not scale past three questions, let alone a cross-reference pass over the whole rulebook.
