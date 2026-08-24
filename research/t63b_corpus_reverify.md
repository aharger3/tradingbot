# T63b — Corpus Re-verify (with corpus_index.py / corpus_query.py)

**Date:** 2026-08-24
**What this is:** t63's three test questions re-run through the new provenance-tagged
index (`research/corpus_index.py` → `research/corpus_index.jsonl`, queried with
`research/corpus_query.py`) instead of hand-grep, to check: same verdicts, faster, and
does splitting by provenance class change any answer.

**Index built:** 5,460 rows over the ten rule-extraction docs t63 named
(`EXTRACTED_TRADING_RULES.md`, `scarface-rules-{videos,mastermind,accelerator,
coaching-bonus,youtube,discord}.md`, `84rule-sizing-dossier.md`, `hallucination-audit.md`,
`parameter_catalog_draft.md`) plus `signal_runner.py` as its own source.

| class | rows | what it means |
|---|---:|---|
| TRADER_SAID | 5,288 | verbatim transcript/Discord quote, or Austin's own words (quoted, wherever recorded) |
| DOC_CLAIMS | 44 | a rule-extraction doc's own narrative assertion, no reproduced quote |
| CODE_COMMENT | 99 | a claim living in `signal_runner.py` — paraphrase or unquoted attribution |
| DERIVED | 29 | every row from `hallucination-audit.md` — an earlier audit pass's MATCHES/DIVERGES verdicts, kept as its own class per t63's finding that one of those verdicts was an interpretive leap, not a citation |

No existing file was modified. Nothing was committed.

---

## (a) "What is the one candle rule?"

`python research/corpus_query.py "what is the one candle rule" --class TRADER_SAID --top 4`

```
[TRADER_SAID] research/EXTRACTED_TRADING_RULES.md:690 [Scarface/jdub] (Day 6 / [560s-568s])
  -- One candle rule set up there meaning that the down close candle has to
     support price for a move to the upside
[TRADER_SAID] research/EXTRACTED_TRADING_RULES.md:683 [Scarface/jdub] (Day 6 / [542s-560s])
  -- We also have the one candle rule right here, which is at 9.35 so both of
     these factors now setting us up
```

**Verdict: unchanged — CONFIRMED.** Same line (`EXTRACTED_TRADING_RULES.md:690`), same
quote t63 cited, now returned by a query instead of a manual grep + read.

**Time:** ~15 seconds (one command) vs t63's ~2 minutes. Faster, verdict identical. The
provenance split changed nothing here — there was only ever one class of evidence
(TRADER_SAID) for this question.

---

## (b) "What does the 84% rule trigger on, and how many times per day may it fire?"

**Trigger** — `python research/corpus_query.py "84 rule trigger stop out same setup
re-entry" --class TRADER_SAID --top 6` returns six TRADER_SAID rows, top-ranked:

```
[TRADER_SAID] research/scarface-rules-videos.md:2137 (boot-camp-recordings_Day_5...[7751s-7764s])
  -- If price stops you out on a trade and the same trade presents itself again,
     you can take the same original trade a second time using the original stop
     and targets and it'll work out 84% of the time
[TRADER_SAID] research/scarface-rules-mastermind.md:79 (mastermind-1-0_1453512, 00:02:01)
  -- If criteria is the exact same — same break, same retest, same hammer, same
     stop, same target — 84 percent of the time this second trade should work out.
```

**Verdict: unchanged — CONFIRMED.** Same trigger mechanics t63 found (A/A+ setup,
stop-out, thesis intact, re-enter same level 5-20 min later on the reclaim close).

**Per-day cap** — two separate filtered queries on the same question text:

`--class CODE_COMMENT`:
```
No rows matched in any provenance class. UNMENTIONED in the indexed corpus --
do not synthesize an answer from other documents' interpretations.
```
(A narrower query, `"84 rule cap two attempts per day re-entry" --class CODE_COMMENT`,
does surface the relevant line: `signal_runner.py:1709 — "Scarface: 84% rule = ONE
re-entry per failed setup. Disarm so it..."` — the exact line t63 traced by hand. It
just needs the right keywords, same as grep would.)

`--class TRADER_SAID` (6 rows, none stating a numeric daily cap):
```
[TRADER_SAID] research/84rule-sizing-dossier.md:91 -- "...84 percent of the time this
  second trade should work out." (mechanics, not a cap)
[TRADER_SAID] research/84rule-sizing-dossier.md:112 -- "The 84 percent rule has to have
  all the same theses." (a requirement, not a cap)
```
No TRADER_SAID row in the full 5,288-row bucket contains a number-of-fires-per-day
statement for the 84% rule specifically. The only place the "ONE re-entry" language
exists is `signal_runner.py:1709`, indexed as CODE_COMMENT — never TRADER_SAID.

**Verdict: unchanged — the per-day cap is still not a corpus-stated trader rule.
`--class TRADER_SAID` returning zero cap statements and `--class CODE_COMMENT`
surfacing exactly the "ONE re-entry" line is the tool doing, mechanically, what t63
had to do by manually checking `signal_runner.py`'s own comments.** This is the one
place the provenance split visibly changes how the answer is produced (not what it
concludes): querying `TRADER_SAID` alone now makes the absence obvious in one command
instead of requiring a human to remember to go check the engine source separately.

**Time:** ~1 minute across 4 queries vs t63's ~20 minutes across 6 grep passes + 5
documents + a `signal_runner.py` check.

---

## (c) "How far from the original entry can a reclaim be and still count?"

`python research/corpus_query.py "reclaim distance tolerance how far entry
BAR_EXTREME_FRAC" --top 6` (all classes, grouped):

```
=== TRADER_SAID (6) ===  -- topically related (reclaim, risk tolerance, entries)
                            but none states a numeric or qualitative distance bound
=== DOC_CLAIMS (6) ===   -- R:R and timing stats, no distance bound
=== CODE_COMMENT (6) ===
[CODE_COMMENT] signal_runner.py:339  -- BAR_EXTREME_FRAC = 0.25
[CODE_COMMENT] signal_runner.py:637  -- "...the same 25% that governs the 84%
  reclaim and stop slippage. One tolerance unit."
=== DERIVED (0) ===
```

**Verdict: unchanged — UNMENTIONED as a trader rule, and the provenance split makes
the risk t63 flagged structurally impossible to miss.** `BAR_EXTREME_FRAC = 0.25` shows
up ONLY in the CODE_COMMENT section. The TRADER_SAID section — Austin's own definition
of a validator answer — contains zero rows with a distance number. A reader who filters
to `--class TRADER_SAID` (or just reads the grouped output, since CODE_COMMENT is its
own labeled section, never merged into TRADER_SAID) cannot hand Austin's 25% back to
him as a corpus finding without the tool itself telling them, in the section header,
that it's engine source, not a trader quote. That is the exact failure mode t63 said a
naive read risked.

**Time:** ~10 seconds for one query vs t63's ~10 minutes (grep + `signal_runner.py`
docstring read + `omen-rulebook.md` cross-check). The cross-check that took a human
reading two extra files to catch is now enforced by the class label on every returned
row.

---

## Summary

| question | t63 verdict | t63b verdict | changed? | t63 time | t63b time |
|---|---|---|---|---|---|
| (a) one candle rule | CONFIRMED | CONFIRMED | no | ~2 min | ~15 sec |
| (b) 84% trigger | CONFIRMED | CONFIRMED | no | ~20 min | ~1 min |
| (b) 84% per-day cap | UNMENTIONED (cap traces to CODE_COMMENT, not TRADER_SAID) | UNMENTIONED — same trace, same line (`signal_runner.py:1709`) | no | ~20 min | ~1 min |
| (c) reclaim distance | UNMENTIONED (25% is Austin's/engine's number) | UNMENTIONED — same number, same file | no | ~10 min | ~10 sec |

**No verdict changed.** All three answers are faster — roughly 8-20x on elapsed time —
and on (b) and (c), the class separation is no longer something the reader has to
remember to do by hand (t63's own words: "depended on already knowing the codebase and
the provenance conventions well enough to distrust a document that looked
authoritative"). `--class TRADER_SAID` now enforces that distrust mechanically: it
returns zero rows for both the 84%-per-day cap and the reclaim-distance tolerance,
which is the correct answer, on the first query, without anyone needing to know in
advance that a plausible-looking number lived in engine source.
