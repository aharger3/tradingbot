# D5 Discord data mining — keyword extraction
# Extracts high-signal Discord messages for trading rules review
# Output: discord_extracted.jsonl + categorized files

import json, os, re, sys
from collections import defaultdict

BASE = r'C:\Users\aharg\tradingbot\discord_data'
OUT = r'C:\Users\aharg\tradingbot\research\discord_extracted'

os.makedirs(OUT, exist_ok=True)

# Files to scan
FILES = {
    'trade-reviews': ['trade-feedback.json', 'scarface-trade-reviews.json', 'jdub-trade-reviews.json', 'options-trade-reviews.json', 'futures-trade-reviews.json'],
    'discussion': ['trading-floor.json'],
    'tips': ['scarface-tips.json'],
    'alerts': ['scarface-alerts.json', 'jdub-alerts.json', 'futures-alerts.json'],
}
MIN_MATCH_THRESHOLD = 2  # alerts need 2+ keyword hits to extract

# Files where even 1 match is enough
HIGH_SIGNAL_FILES = {'trade-feedback.json', 'scarface-trade-reviews.json', 'jdub-trade-reviews.json', 'options-trade-reviews.json', 'futures-trade-reviews.json', 'scarface-tips.json'}

# Keywords by category — matches = extract
PATTERNS = {
    'bad_trade': r'\b(bad|mistake|wrong|shouldn.t|should not|failed|loss|stopped out|blew|cut early|sold too)\b',
    'good_trade': r'\b(good|great|perfect|beautiful|best|textbook|nicely|excellent|worked out)\b',
    'why_reason': r'\b(because|reason|why I|why we|due to|since)\b',
    'rule_stmt': r"\b(rule|always|never|don't|dont|must|only|require|criteria|system says|my system)\b",
    'short_side': r'\b(short|shorts|bear|put option|puts|elevator down|downside|shorting)\b',
    'exit': r'\b(scale|exit|target|TP1|TP2|take profit|runner|trail|bar.by.bar|breakeven|HOD|LOD|high of day|low of day)\b',
    '84rule': r'\b(84%|84 percent|re.entry|reentry|second trade|twice)\b',
    'aplus': r'\b(A\+|A plus|A.plus|high quality setup)\b',
    'time': r'\b(10[.:]?[03]0|after 11|before 10|morning trade|opening drive|first hour|9:30|9 30)\b',
    'relative_strength': r'\b(relative strength|relative weakness|RS|RW|QQQ.*strength|QQQ.*weak|leading|lagging)\b',
    'level': r'\b(PDH|PDL|PMH|PML|gap fill|psychological|whole number|key level|order block|one candle)\b',
    'theta': r'\b(theta|DTE|expiry|expiration|weekly|0DTE|0 DTE|zero day)\b',
    'volume': r'\b(volume|open interest|OI|options flow|unusual|big blocks|size)\b',
}

def has_pattern(text, pattern):
    return bool(re.search(pattern, text, re.IGNORECASE)) if text else False

def count_matches(text):
    return sum(1 for p in PATTERNS.values() if has_pattern(text, p))

def should_extract(fn, match_count):
    if fn in HIGH_SIGNAL_FILES:
        return match_count >= 1
    return match_count >= MIN_MATCH_THRESHOLD

results = {k: [] for k in PATTERNS}
all_extracted = []

for category, file_list in FILES.items():
    for fn in file_list:
        path = os.path.join(BASE, fn)
        with open(path, 'r', encoding='utf-8') as f:
            msgs = json.load(f)

        print(f'Scanning {fn} ({len(msgs)} msgs)...')
        for m in msgs:
            content = m.get('content', '') or ''
            if not content:
                continue
            match_count = count_matches(content)
            if not should_extract(fn, match_count):
                continue

            entry = {
                'file': fn,
                'ts': m.get('ts', ''),
                'author': m.get('author', ''),
                'content': content[:2000],
                'matches': match_count,
            }
            all_extracted.append(entry)

            # Tag all matching categories
            for cat, pat in PATTERNS.items():
                if has_pattern(content, pat):
                    results[cat].append(entry)

# Save all extracted
with open(os.path.join(OUT, 'all_extracted.jsonl'), 'w', encoding='utf-8') as f:
    for e in all_extracted:
        f.write(json.dumps(e) + '\n')

print(f'\nTotal extracted: {len(all_extracted)} messages with >=1 keyword match')

for cat, items in sorted(results.items()):
    print(f'  [{cat}]: {len(items)} messages')

# Save categorized extracts
for cat, items in results.items():
    outpath = os.path.join(OUT, f'{cat}.jsonl')
    with open(outpath, 'w', encoding='utf-8') as f:
        for e in items:
            f.write(json.dumps(e) + '\n')
    # Print a sample
    if items:
        sample = items[0]
        print(f'\n[{cat}] sample from {sample["file"]} by {sample["author"]}:')
        print(f'  {sample["content"][:200]}')
