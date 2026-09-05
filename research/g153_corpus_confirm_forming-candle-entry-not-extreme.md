# F4: Corpus Confirmation — forming-candle-entry-not-extreme

## Candidate Claim
"He takes the entry while the candle is still forming, not after it closes at the low/high of day -- a close at the extreme kills the risk:reward."

## Corpus Verdict
**CONFIRMED**

## Quote & Source (Scarface/Jdub)
> "I ended up entering in this position which was your conservative entry as this candle was forming"

**Source:** `research/corpus_entries.jsonl`, YouTube corpus from Scarface/Jdub trading commentary (captured via yt-dlp captions).

**Second Direct Quote:**
> "once we rejected off this level as this candle was forming I end up getting in off this candle right with a stop just to break above where I was looking for was essentially your previous high of day"

**Source:** `research/corpus_entries.jsonl`, confirms the mechanic: entry taken WHILE candle forming, stop placed at previous high of day (not entering AT the extreme).

## Supporting Pattern
Multiple corpus entries show the same pattern:
- "Got in as this candle was forming."
- "We're looking for this reclaimed setup with an entry as this candle is forming stops just a break below."
- "as this candle was forming I end up getting in off this candle"

All indicate the traders enter during candle formation, with stops set away from the day's extreme.

## Fill & Script
Entry = candle-formation-time observation from YouTube transcripts; source: research/corpus_entries.jsonl extracted via yt-dlp captions + qwen3.5:4b; script: research/corpus_*normalized.py pipeline.
