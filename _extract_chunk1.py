"""Extract chunk1 reviews from agent output file."""
import json, re

with open(r'C:\Users\aharg\AppData\Local\Temp\claude\C--Users-aharg\ca9ea715-5118-49ae-ae62-22d7311f2548\tasks\aa4bc40898e6f1b5d.output', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
if m:
    data = json.loads(m.group(1))
    with open('_chunk1_reviews.json', 'w', encoding='utf-8') as fout:
        json.dump(data, fout, indent=2)
    print(f'Chunk 1: {len(data["tradeReviews"])} reviews saved')
else:
    print('No JSON block found')
    # Try looking for JSON directly
    m2 = re.search(r'\{\s*\n\s*"tradeReviews":\s*\[', text, re.DOTALL)
    if m2:
        print('Found tradeReviews but need proper extraction')
    else:
        print('No tradeReviews found')
