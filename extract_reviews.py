"""Extract structured trades from trade-review transcript bodies via DeepSeek
(cheap, off the Opus budget). Body is authoritative over title (title tickers
are sometimes wrong). Whisper strips decimals ('24792' = 247.92) — the model
restores them from context. Run: python extract_reviews.py [N]  (N=limit)
"""
import os, re, glob, json, sys
from pathlib import Path
from openai import OpenAI

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                base_url="https://api.deepseek.com")

SCHEMA = """Return ONLY a JSON object with these keys:
- ticker: the actual traded symbol from the BODY (ignore the title; body wins)
- direction: "long" or "short"
- date_str: the date stated in the body (e.g. "October 4"), or null
- setup: short phrase (e.g. "break and retest of premarket high", "order block retest")
- entry_level: the price he entered near, as a realistic decimal number, or null
- target_level: profit target price as decimal, or null
- stop_level: stop price as decimal, or null
- outcome: "win" or "loss" per the body
- confidence: 0-1, your confidence the fields are right
Whisper dropped decimals: "24792" for a ~$248 stock means 247.92. Restore the
decimal to a realistic price for that ticker. Numbers with no sensible price =
null. No prose, JSON only."""


def extract(title: str, body: str) -> dict:
    msg = f"Trade review title: {title}\n\nTranscript (first part):\n{body[:3500]}\n\n{SCHEMA}"
    r = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": msg}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(r.choices[0].message.content)


def run(limit=None):
    files = []
    for f in glob.glob("youtube_data/*_transcript.txt") + glob.glob("circle_data/transcripts_text/*_transcript.txt"):
        head = Path(f).read_text(encoding="utf-8", errors="ignore")
        title = head.splitlines()[0].lstrip("# ").strip()
        if "trade review" in title.lower():
            files.append((f, title, head))
    if limit:
        files = files[:limit]
    out = []
    for i, (f, title, body) in enumerate(files, 1):
        try:
            rec = extract(title, body)
            rec["file"] = Path(f).name
            rec["title"] = title
            out.append(rec)
            g = lambda k: str(rec.get(k))
            print(f"[{i}/{len(files)}] {g('ticker'):>5} {g('direction'):>5} "
                  f"entry {g('entry_level')} tgt {g('target_level')} "
                  f"stop {g('stop_level')} {g('outcome'):>4} "
                  f"conf {g('confidence')} :: {(rec.get('setup') or '')[:40]}")
        except Exception as e:
            print(f"[{i}/{len(files)}] ERR {Path(f).name}: {e}")
    Path("reviews_extracted.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote reviews_extracted.json ({len(out)} records)")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else None)
