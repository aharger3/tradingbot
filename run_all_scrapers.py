"""Run all scrapers sequentially. For cron/task scheduler.
Usage: python run_all_scrapers.py
"""
import subprocess, sys
from pathlib import Path

SCRAPERS = [
    ("youtube_scraper.py", "youtube"),
    ("discord_scraper.py", "discord"),
    ("circle_scraper.py", "circle"),
]

for script, name in SCRAPERS:
    if not Path(script).exists():
        print(f"[SKIP] {script} not found")
        continue
    print(f"\n{'='*40}")
    print(f"Running {name} scraper...")
    print(f"{'='*40}")
    result = subprocess.run([sys.executable, script], capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        print(f"[FAIL] {name} scraper exited code {result.returncode}")
