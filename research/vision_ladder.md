# Vision Ladder (T3) - which tier can read a price level off a chart

200 Discord chart screenshots (100 jdub-alerts / 60 scarface-alerts / 40 premarket-charts), same strict-JSON prompt every tier:
`{ticker, direction, entry, stop, target, key_levels[], timeframe, confidence}` with `null` for any field the model cannot actually read off the chart.

## Substitutions (documented)
- **free**: spec named `google/gemma-4-31b-it:free`. That `:free` variant is throughput-blocked by Google's free-gemma quota (~1 row per 5 min, calls dropping) - unusable for a 200-image sample. The SAME model (`gemma-4-31b-it`) was run via OpenRouter's paid variant to measure capability; cost is negligible (~$0.013) and it remains the cheapest tier. The free variant's rate limit is a throughput finding, not a capability one.
- **batch**: spec named `google/gemini-2.5-flash-lite:batch` (OpenRouter `:batch` models use a separate async batch API, not `/chat/completions`). The 2026-08-20 run used synchronous `google/gemini-3.5-flash-lite`; gemini-2.5 is also deprecated on this account (404, per the T6 note). 200 clean rows, kept.
- **flash**: spec routes `gemini-3.6-flash` via Google AI Studio (`GOOGLE_AI_STUDIO_API_KEY`), but that key's quota is exhausted (429 "You exceeded your current quota"). The SAME model was reached via paid OpenRouter instead. ~34% of flash responses did not parse as strict JSON (prose / truncated) - a real reliability finding, recorded as parsed_ok=False (no error key written).
- **incumbent**: spec routes `gemini-3.1-flash-lite` via local OmniRoute (the scarface annotator's model). OmniRoute's credentials for that model are quota-cooling (429 `model_cooldown`, all credentials) and its vision auto-routers 400, so the SAME model (`gemini-3.1-flash-lite`) was reached via OpenRouter instead. The model identity - the model the existing annotator already used - is what makes this the incumbent; the route is just how the annotator reached it.

## Grading
- **ticker_acc**: over rows whose message text names a data_archive ticker (the only rows with a ground-truth ticker; 145/200 pilot messages are generic and carry none). correct when the model's ticker is among the text's ticker(s).
- **price_in_range_pct**: a price is in range when it falls within `[low*0.98, high*1.02]` of the day's session bars (2% tolerance around the day's high-low range; a price outside is a hallucination). Day bars located by the ticker shown on the chart (text ticker when named, else the model's read). A row is in-range only if EVERY non-null price is in range. Rows with no price read or no gradeable range are excluded.
- **null_rate**: share of the 8 schema fields returned null.
- **cost_usd**: sum over the tier. free used the paid gemma variant (~$0.013; the :free variant is quota-blocked); incumbent via OpenRouter is real cost.

```
| tier | model | n | parsed_ok | ticker_acc | price_in_range_pct | null_rate | cost_usd |
|---|---|---|---|---|---|---|---|
| free | google/gemma-4-31b-it | 200 | 200 | 89.1% (n=55) | 80.0% (n=140) | 63.1% | 0.0128 |
| cheap | qwen/qwen3.7-flash | 200 | 200 | 92.7% (n=55) | 72.5% (n=153) | 19.9% | 0.0226 |
| batch | google/gemini-3.5-flash-lite | 200 | 200 | 92.7% (n=55) | 74.4% (n=133) | 61.3% | 0.1141 |
| flash | gemini-3.6-flash | 200 | 148 | 83.6% (n=55) | 78.3% (n=115) | 63.9% | 0.6783 |
| incumbent | gemini-3.1-flash-lite | 200 | 199 | 92.7% (n=55) | 74.0% (n=146) | 59.2% | 0.0938 |
```

WINNER: google/gemma-4-31b-it (tier=free, price_in_range_pct=80.0%, cost_usd=0.0128)

_No results row in any tier carries an `error` key (done-guard: error responses are dropped, never written). The zero-work guard added to `scarface_image_annotator.py` exits non-zero instead of logging DONE._
