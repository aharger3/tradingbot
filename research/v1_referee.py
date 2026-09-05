"""V1 referee checks -- run by the referee for row V1 (omen-10.0).

Re-derives, without trusting the builder's report:
  1. the premarket list dry-run prints all 11 core symbols with PDH/PDL/PMH/PML
  2. the API-key scrubber in research/premarket_list.py actually removes the key
  3. the OmenPremarketList scheduled task fires weekdays at 09:25 local (= ET here)
  4. its command path exists and is tracked by git
  5. c59abe88's live_scanner.py diff touches ntfy text only, never the Alpaca
     order path

    python research/v1_referee.py

Exit 0 = every check passed. Prints one line per check.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

BUILDER_COMMIT = "c59abe88"      # the commit that actually carries V1's code
REPORTED_COMMIT = "3c8e586d"     # what the builder's report named (an auto-commit)

CORE = ["TSLA", "NVDA", "AAPL", "AMD", "META", "GOOGL",
        "AMZN", "MSFT", "PLTR", "QQQ", "SPY"]

fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'ok  ' if ok else 'FAIL'}] {name}{(' -- ' + detail) if detail else ''}")
    if not ok:
        fails.append(name)


# 1 -- dry-run output ---------------------------------------------------------
out = subprocess.run([sys.executable, "research/premarket_list.py", "--dry-run"],
                     cwd=ROOT, capture_output=True, text=True, timeout=300)
text = out.stdout + out.stderr
lines = {}
for ln in text.splitlines():
    m = re.match(r"^(\w+)\s+PDH ([\d.]+)\s+PDL ([\d.]+)\s+PMH ([\d.]+)\s+PML ([\d.]+)$",
                 ln.strip())
    if m:
        lines[m.group(1)] = ln.strip()
missing = [s for s in CORE if s not in lines]
check("dry-run lists all 11 core symbols with PDH/PDL/PMH/PML",
      not missing and len(lines) == 11,
      f"{len(lines)} rows, missing={missing}")
check("dry-run raised no traceback", "Traceback" not in text)
check("dry-run exited 0", out.returncode == 0, f"rc={out.returncode}")
check("no raw apiKey value in dry-run output",
      not re.search(r"apiKey=(?!\*)", text))

# 2 -- the scrubber -----------------------------------------------------------
import premarket_list as pl  # noqa: E402

probe = ("403 Forbidden for url: https://api.polygon.io/v2/aggs/ticker/TSLA/"
         "range/1/minute/2026-09-05/2026-09-05?adjusted=true&limit=50000"
         "&apiKey=SENTINELKEY&x=1")
check("_scrub removes the api key from a polygon error URL",
      "SENTINELKEY" not in pl._scrub(probe))

# 3 -- the scheduled task -----------------------------------------------------
ps = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "$t=Get-ScheduledTask -TaskName OmenPremarketList -ErrorAction SilentlyContinue;"
     "if(-not $t){'MISSING';exit};"
     "$tr=$t.Triggers[0];"
     "'START=' + $tr.StartBoundary; 'DOW=' + $tr.DaysOfWeek;"
     "'ENABLED=' + $tr.Enabled; 'EXEC=' + $t.Actions[0].Execute"],
    capture_output=True, text=True, timeout=120)
info = dict(l.split("=", 1) for l in ps.stdout.splitlines() if "=" in l)
start = info.get("START", "")
dow = info.get("DOW", "")
check("OmenPremarketList exists", "MISSING" not in ps.stdout)
check("trigger time is 09:25 local", "T09:25:00" in start, start)
# DaysOfWeek bitmask: Sun=1 Mon=2 Tue=4 Wed=8 Thu=16 Fri=32 Sat=64 -> Mon-Fri = 62
check("trigger days are Mon-Fri (mask 62)", dow.strip() == "62", f"mask={dow}")
exec_path = Path(info.get("EXEC", "").strip())
check("task command path exists on disk", exec_path.is_file(), str(exec_path))

tracked = subprocess.run(["git", "ls-files", "research/premarket_list_run.cmd",
                          "research/premarket_list.py"],
                         cwd=ROOT, capture_output=True, text=True, timeout=60)
check("both V1 files are tracked by git",
      "research/premarket_list_run.cmd" in tracked.stdout
      and "research/premarket_list.py" in tracked.stdout)

# 4 -- the live_scanner diff --------------------------------------------------
diff = subprocess.run(["git", "show", BUILDER_COMMIT, "--", "live_scanner.py"],
                      cwd=ROOT, capture_output=True, text=True, timeout=60).stdout
added = [l[1:] for l in diff.splitlines()
         if l.startswith("+") and not l.startswith("+++")]
removed = [l[1:] for l in diff.splitlines()
           if l.startswith("-") and not l.startswith("---")]
check(f"{BUILDER_COMMIT} removes no live_scanner line", not removed,
      f"{len(removed)} removals")
banned = ("place_order", "submit_order", "alpaca_submit", "broker.")
hits = [l for l in added if any(b in l for b in banned)]
check("added lines never touch the Alpaca order path", not hits, str(hits))
check("added lines are the ntfy tag only",
      any("PUSH_TAG_PRERECONCILE" in l for l in added)
      and any("pre-reconcile" in l for l in added),
      f"{len(added)} added lines")

# 5 -- the reported hash ------------------------------------------------------
check("builder's reported commit carries V1's code", False,
      f"report named {REPORTED_COMMIT} (an unrelated wip auto-commit); "
      f"V1's code is in {BUILDER_COMMIT}")

print()
print(f"{len(fails)} failed check(s): {fails}" if fails else "all checks passed")
sys.exit(1 if fails else 0)
