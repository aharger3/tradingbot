#!/usr/bin/env python3
"""G5: Mine top unmined (not-cited-in-batches) skipped YouTube transcripts for
(a) day-trade rule deltas vs existing rulebooks and (b) swing/long-term B&R content.
Same DeepSeek key/env mechanism as run_b1_extraction.py. Cached interim in _g5_interim."""
import os, sys, time, json, csv, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import requests
except ImportError:
    os.system(f'"{sys.executable}" -m pip install requests -q')
    import requests

BASE = Path(r"C:\Users\aharg\tradingbot\research")
YOUTUBE = Path(r"C:\Users\aharg\tradingbot\youtube_data")
INTERIM = BASE / "_g5_interim"
INTERIM.mkdir(exist_ok=True)

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-516a62fdf01b4c19af470990babd63d8")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """You are a trading-rule extraction engine mining YouTube transcripts that were SKIPPED by a prior pass (low day-trade-keyword score, so likely trade reviews / live sessions / swing-flavored). Extract ONLY genuinely new material vs the existing rulebooks.

Existing rulebooks already cover (do NOT restate — only flag DELTAS):
- Break-and-retest core (break validity, retest, entry candle, stop, targets, invalidation)
- "One candle rule" / opening candle retest (≡ order block)
- 84% rule (reclaim-based entry, thesis-not-broken gate, multiple-tries-allowed variant, "84 to the 84" chop diagnostic)
- Order blocks (up/down-close candles, body strength, weekly OB)
- Key levels (PDH/PDL, PMH/PML, opening range, HOD/LOD, gap fill)
- Time-of-day/day-of-week; news days (FOMC/Powell = low prob, reduce)
- Exits (scale 80-90% at key levels, scale on way UP for 0DTE, trailing, breakeven)
- HTF/swing baseline (from bonus_How_To_Swing_Trade_Q_A): swing = HTF consolidation after move expecting impulse; trend intact via higher lows; entry on 4H/1H, execute 10-15m; swing less about precision; scale in on retest; HTF thesis → 1m opening range, else 5m; choppy 50% off HOD / trending 10-25% off; market designed to go up
- 0DTE rules (new traders avoid 0DTE use next-week; 0DTE must work immediately; Fri avoid 0DTE after 11am; scale up not down; gamma tail)
- A/A+ grading, QQQ alignment, displacement/FVG, stop-after-win (informal not mandated), contract selection (weekly default)

HARD RULES:
1. Quote verbatim + filename + [Ns] timestamp. If topic never appears: "NOT COVERED".
2. NEVER fill gaps from general knowledge. Cardinal sin.
3. For (a) day-trade deltas: only NEW rules, refinements, or CONTRADICTIONS to the above. One line + citation. State which existing rule it deltas/contradicts.
4. For (b) swing/long-term: HTF B&R setups, 4H/1H context, weekly/daily levels, position management (sizing, scaling-in on drawdown, holding through catalyst, theta/expiry mgmt, swing stop = HTF level break), swing selection (consolidation-not-pullback = strength, sympathy/correlation plays). Be exhaustive here — this is the priority.
5. Flag trade-review JUDGMENT criteria ("this trade was bad because X") as deltas too.

Output two sections per source group:
## (a) DAY-TRADE DELTAS
## (b) SWING / LONG-TERM
Verbatim quotes + (file, [Ns])."""

def call_deepseek(messages, max_retries=3):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    data = {"model": MODEL, "messages": messages, "temperature": 0, "max_tokens": 8192}
    for attempt in range(max_retries):
        try:
            resp = requests.post(API_URL, headers=headers, json=data, timeout=300)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            elif resp.status_code == 429:
                wait = min(30 * (attempt + 1), 120); print(f"  429 wait {wait}s"); time.sleep(wait); continue
            else:
                print(f"  API {resp.status_code}: {resp.text[:200]}")
                if attempt < max_retries - 1: time.sleep(10)
                else: return f"[EXTRACTION FAILED: HTTP {resp.status_code}]"
        except Exception as e:
            print(f"  exc: {e}")
            if attempt < max_retries - 1: time.sleep(15)
            else: return f"[EXTRACTION FAILED: {e}]"
    return "[EXTRACTION FAILED: max retries]"

def build_prompt(filenames):
    parts = []
    for fn in filenames:
        fp = YOUTUBE / fn
        text = fp.read_text(encoding="utf-8", errors="replace") if fp.exists() else f"[MISSING {fn}]"
        if len(text) > 70000:
            text = text[:70000] + "\n\n[...TRUNCATED]"
        parts.append(f"=== FILE: {fn} ===\n{text}")
    combined = "\n\n".join(parts)
    if len(combined) > 110000:
        combined = combined[:110000] + "\n\n[...GROUP TRUNCATED]"
    return f"Mine these skipped YouTube transcripts. Follow the system-prompt rules exactly — (a) day-trade deltas only, (b) swing/long-term exhaustive.\n\nTranscripts:\n{combined}"

def process_group(i, files):
    gid = f"g5_{i:02d}"
    cf = INTERIM / f"{gid}.md"
    if cf.exists():
        print(f"  [{gid}] cached ({len(files)}f)"); return gid, files, cf.read_text(encoding="utf-8")
    print(f"  [{gid}] {len(files)}f: {', '.join(f[:18] for f in files)}")
    content = call_deepseek([{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":build_prompt(files)}])
    cf.write_text(content, encoding="utf-8")
    print(f"  [{gid}] saved {len(content)}c"); return gid, files, content

def main():
    targets = [l.split('\t')[0] for l in (BASE/"_g5_targets.tsv").read_text(encoding='utf-8').splitlines() if l.strip()]
    targets = targets[:12]  # top-12 not-cited
    # group 1 per group (large files) to minimize truncation loss
    groups = [[fn] for fn in targets]
    print(f"G5 extraction: {len(groups)} groups, {sum(len(g) for g in groups)} files")
    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(process_group, i, g): (i, g) for i, g in enumerate(groups)}
        for fut in as_completed(futs):
            i, g = futs[fut]
            try: results.append(fut.result())
            except Exception as e: print(f"  FAIL g{i}: {e}")
    results.sort(key=lambda x: int(x[0].split('_')[1]))
    out = ["# G5 DeepSeek raw extraction (top-12 unmined skipped transcripts)\n\n"
           "Cached interim. Mined for (a) day-trade deltas, (b) swing/long-term.\n\n---\n"]
    for gid, files, content in results:
        out.append(f"## Group {gid}: {', '.join(files)}\n\n{content}\n\n---\n")
    (BASE/"g5_deepseek_raw.md").write_text("\n".join(out), encoding="utf-8")
    print(f"WROTE research/g5_deepseek_raw.md")

if __name__ == "__main__":
    main()
