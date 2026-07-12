import json, re, os

SRC = r'C:\Users\aharg\tradingbot\research\discord_extracted\all_extracted.jsonl'
OUT = r'C:\Users\aharg\tradingbot\research\discord_curated'
os.makedirs(OUT, exist_ok=True)

print('Loading all_extracted...')
with open(SRC, 'r') as f:
    entries = [json.loads(l) for l in f]
print(f'Loaded {len(entries)} entries')

# Write top signal by match count
entries.sort(key=lambda e: -e['matches'])
path = os.path.join(OUT, 'top_by_signal.txt')
with open(path, 'w', encoding='utf-8', errors='replace') as f:
    for e in entries[:200]:
        if e['matches'] >= 4:
            f.write(f"[{e['matches']}m] {e['file']} | {e['author']} | {e['ts']}\n")
            content = e['content'][:1200].replace('\n', ' | ')
            f.write(f'  {content}\n\n---\n\n')

# Write all short-side relevant (keyword match)
short_kw = re.compile(r'\b(short|shorts|bear|put option|puts|elevator down|downside|shorting|bearish|put play|sell off|sell the rip|shorting into|failed breakout|breakdown)\b', re.IGNORECASE)
short = [e for e in entries if e['matches'] >= 3 and short_kw.search(e['content'])]
short.sort(key=lambda e: -e['matches'])
with open(os.path.join(OUT, 'short_side.txt'), 'w', encoding='utf-8', errors='replace') as f:
    for e in short[:80]:
        f.write(f"[{e['matches']}m] {e['file']} | {e['author']} | {e['ts']}\n")
        c = e['content'][:1000].replace('\n', '\n  ')
        f.write(f'  {c}\n\n---\n\n')

# Exit management
exit_kw = re.compile(r'\b(scale|exit|TP1|TP2|runner|trail|breakeven|HOD|LOD|partial|cut|take profit|lock in)\b', re.IGNORECASE)
exit_msgs = [e for e in entries if e['matches'] >= 3 and exit_kw.search(e['content'])]
exit_msgs.sort(key=lambda e: -e['matches'])
with open(os.path.join(OUT, 'exit_mgmt.txt'), 'w', encoding='utf-8', errors='replace') as f:
    for e in exit_msgs[:80]:
        f.write(f"[{e['matches']}m] {e['file']} | {e['author']} | {e['ts']}\n")
        c = e['content'][:1000].replace('\n', '\n  ')
        f.write(f'  {c}\n\n---\n\n')

# Trade reviews (bad/good + reasoning)
review_kw = re.compile(r'\b(bad|mistake|wrong|shouldn|good|great|perfect|textbook|reason|because|lesson|learn|never again|what I did|my mistake|cut early|should have)\b', re.IGNORECASE)
reviews = [e for e in entries if e['matches'] >= 3 and review_kw.search(e['content'])]
reviews.sort(key=lambda e: -e['matches'])
with open(os.path.join(OUT, 'trade_reviews.txt'), 'w', encoding='utf-8', errors='replace') as f:
    for e in reviews[:100]:
        f.write(f"[{e['matches']}m] {e['file']} | {e['author']} | {e['ts']}\n")
        c = e['content'][:1000].replace('\n', '\n  ')
        f.write(f'  {c}\n\n---\n\n')

# 84% rule
eightyfour = [e for e in entries if e['matches'] >= 2 and re.search(r'\b(84%|84 percent|re.entry|reentry|84%.rule|second entry)\b', e['content'], re.IGNORECASE)]
with open(os.path.join(OUT, '84rule.txt'), 'w', encoding='utf-8', errors='replace') as f:
    for e in eightyfour[:40]:
        f.write(f"[{e['matches']}m] {e['file']} | {e['author']} | {e['ts']}\n")
        c = e['content'][:1000].replace('\n', '\n  ')
        f.write(f'  {c}\n\n---\n\n')

# Rule statements
stmt_kw = re.compile(r"\b(rule|always |never |don't|must |only |require|criteria|system says|my system|rule of thumb|golden rule)\b", re.IGNORECASE)
stmts = [e for e in entries if e['matches'] >= 3 and stmt_kw.search(e['content'])]
stmts.sort(key=lambda e: -e['matches'])
with open(os.path.join(OUT, 'rule_statements.txt'), 'w', encoding='utf-8', errors='replace') as f:
    for e in stmts[:100]:
        f.write(f"[{e['matches']}m] {e['file']} | {e['author']} | {e['ts']}\n")
        c = e['content'][:800].replace('\n', '\n  ')
        f.write(f'  {c}\n\n---\n\n')

top = len([e for e in entries if e['matches'] >= 4])
print(f'top_signal: {top}')
print(f'short_side: {len(short)}')
print(f'exit_mgmt: {len(exit_msgs)}')
print(f'trade_reviews: {len(reviews)}')
print(f'84rule: {len(eightyfour)}')
print(f'rule_statements: {len(stmts)}')
print('Done')
