"""Market-open health check: runs before 9:30 ET, verifies everything,
posts PASS/FAIL to Discord."""

import os
import sys
import json
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).parent.resolve()
RESULTS = {"pass": [], "fail": []}

def check(label: str, ok: bool, detail: str = ""):
    if ok:
        RESULTS["pass"].append(label)
    else:
        RESULTS["fail"].append(f"{label}: {detail}")
    return ok

def post_to_discord(payload: dict) -> bool:
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        webhook_env = BASE / ".env"
        if webhook_env.exists():
            for line in webhook_env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("DISCORD_WEBHOOK_URL="):
                    webhook = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not webhook:
        print("No DISCORD_WEBHOOK_URL found — can't post to Discord")
        return False
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "market-open-healthcheck/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"Discord post failed: {e}")
        return False


# ── 1. Python 3.13 ──────────────────────────────────────────────
PY313 = Path(r"C:\Users\aharg\AppData\Local\Programs\Python\Python313\python.exe")
pv_ok = False
if PY313.exists():
    try:
        out = subprocess.run([str(PY313), "--version"], capture_output=True, text=True, timeout=10)
        pv_ok = "3.13" in out.stdout
        check("python313-exists", pv_ok, out.stdout.strip() or out.stderr.strip())
    except Exception as e:
        check("python313-exists", False, str(e))
else:
    check("python313-exists", False, f"Not found at {PY313}")

# ── 2. yfinance (fallback) ──────────────────────────────────────
if pv_ok:
    try:
        out = subprocess.run(
            [str(PY313), "-c", "import yfinance; print(yfinance.__version__)"],
            capture_output=True, text=True, timeout=15,
        )
        check("yfinance-works", out.returncode == 0, out.stderr.strip() or out.stdout.strip())
    except Exception as e:
        check("yfinance-works", False, str(e))
else:
    check("yfinance-works", False, "Python313 not available")

# ── 3. Core trading deps ────────────────────────────────────────
if pv_ok:
    deps = ["requests", "websocket", "yfinance"]
    missing = []
    for d in deps:
        r = subprocess.run(
            [str(PY313), "-c", f"import {d.split('.')[0]}"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            missing.append(d)
    check("trading-deps", len(missing) == 0, f"Missing: {', '.join(missing)}" if missing else "")
else:
    check("trading-deps", False, "Python313 not available")

# ── 4. Tastytrade credentials ───────────────────────────────────
CRED_FILES = [
    ("main .env", BASE / ".env"),
    ("projects .env.tastytrade",
     Path(r"C:\Users\aharg\projects\tradingbot\.env.tastytrade")),
    ("project .env", Path(r"C:\Users\aharg\projects\tradingbot\.env")),
]
tt_ok = False
for label, path in CRED_FILES:
    if path.exists():
        content = path.read_text(encoding="utf-8")
        has_id = "CLIENT_ID" in content or "TASTYTRADE_USERNAME" in content
        has_secret = "CLIENT_SECRET" in content or "TASTYTRADE_PASSWORD" in content
        has_token = "REFRESH_TOKEN" in content or "TASTYTRADE_REMEMBER_TOKEN" in content
        has_acct = "ACCOUNT_NUMBER" in content
        if has_id and has_secret and (has_token or has_acct):
            tt_ok = True
check("tastytrade-creds-exist", tt_ok, f"No valid cred file found")

# Check refresh token format (JWT should start with eyJ)
if tt_ok:
    tt_env = Path(r"C:\Users\aharg\projects\tradingbot\.env.tastytrade")
    refresh_token = None
    if tt_env.exists():
        for line in tt_env.read_text().splitlines():
            if line.startswith("REFRESH_TOKEN="):
                refresh_token = line.split("=", 1)[1].strip()
                break
    if refresh_token:
        check("tastytrade-refresh-token-format",
              refresh_token.startswith("eyJ"),
              f"Token starts with {refresh_token[:10]}...")
    else:
        env_main = BASE / ".env"
        remember_token = None
        if env_main.exists():
            for line in env_main.read_text().splitlines():
                if line.startswith("TASTYTRADE_REMEMBER_TOKEN="):
                    remember_token = line.split("=", 1)[1].strip()
                    break
        check("tastytrade-remember-token-exists",
              bool(remember_token),
              "No TASTYTRADE_REMEMBER_TOKEN or REFRESH_TOKEN found")

# ── 5. Task Scheduler task exists and enabled ───────────────────
try:
    out = subprocess.run(
        ["schtasks", "/query", "/tn", "run_daily", "/fo", "LIST", "/v"],
        capture_output=True, text=True, timeout=10,
    )
    if out.returncode == 0 and "run_daily" in out.stdout:
        enabled = "Enabled" in out.stdout
        check("scheduler-task-exists", enabled,
              "Task found but status may not be Enabled" if not enabled else "Enabled")
    else:
        # Broader search
        out2 = subprocess.run(
            ["schtasks", "/query", "/fo", "LIST", "/v"],
            capture_output=True, text=True, timeout=10,
        )
        if "run_daily" in out2.stdout.lower():
            check("scheduler-task-exists", True, "Found in task list via broad search")
        else:
            check("scheduler-task-exists", False, "No 'run_daily' task found")
except Exception as e:
    check("scheduler-task-exists", False, str(e))


# ── Results ─────────────────────────────────────────────────────
pass_count = len(RESULTS["pass"])
fail_count = len(RESULTS["fail"])
total = pass_count + fail_count

timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %I:%M:%S %p ET")
overall = "PASS" if fail_count == 0 else "FAIL"

summary_parts = [f"**{overall}** — {pass_count}/{total} checks passed"]
for p in RESULTS["pass"]:
    summary_parts.append(f"✓ {p}")
for f in RESULTS["fail"]:
    summary_parts.append(f"✗ {f}")

description = "\n".join(summary_parts)

color = 3066993  # green
if fail_count > 0:
    color = 15158332  # red

payload = {
    "embeds": [{
        "title": f"📊 Pre-Market Health Check — {overall}",
        "description": description,
        "color": color,
        "footer": {"text": f"Market Open Health Check · {timestamp}"},
    }]
}

# Also print to stdout for logs
print(f"\n{'='*50}")
print(f"  MARKET OPEN HEALTH CHECK  —  {overall}")
print(f"{'='*50}")
print(f"  Time:     {timestamp}")
print(f"  Passed:   {pass_count}/{total}")
print()
for p in RESULTS["pass"]:
    print(f"  ✓  {p}")
for f in RESULTS["fail"]:
    print(f"  ✗  {f}")
print(f"{'='*50}\n")

post_ok = post_to_discord(payload)
print(f"Discord post: {'✓ sent' if post_ok else '✗ failed'}")

sys.exit(0 if fail_count == 0 else 1)
