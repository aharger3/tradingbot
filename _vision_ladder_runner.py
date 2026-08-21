"""
vision_ladder_runner.py - run the T3 vision ladder tiers over the 200-image pilot manifest.

Three of the five tiers are served here (cheap + batch already ran 2026-08-20 and are kept):
  free       google/gemma-4-31b-it:free   OpenRouter
  flash      gemini-3.6-flash             Google AI Studio (GOOGLE_AI_STUDIO_API_KEY)
  incumbent  gemini/gemini-3.1-flash-lite local OmniRoute gateway (localhost:20128)

Same strict-JSON prompt every tier. The model must return null for any field it cannot
actually read off the chart - guessing is the failure mode being tested for.

Done-guard applies (spec T3): an error response is NEVER written to the results file. It is
dropped and counted as a failure for that tier. That is the exact bug that put 685 fake 429
rows into stage C. Resumable by `path`: rerun skips rows already present in the output file.

Sibling in spirit to scarface_image_annotator.py / frame_annotator.py (urllib, no SDK deps).
"""

import base64
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MANIFEST = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\vision_pilot_manifest.jsonl")
OUTDIR = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GOOGLE_URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
OMNIROUTE_URL = "http://localhost:20128/v1/chat/completions"

# gemini-3.6-flash pricing, reverse-engineered from the existing flash rows
# (1166 in + 90 out -> $0.000572 => $0.30/M in, $2.50/M out).
GFLASH_IN = 0.30 / 1_000_000
GFLASH_OUT = 2.50 / 1_000_000

SCHEMA_KEYS = ["ticker", "direction", "entry", "stop", "target",
               "key_levels", "timeframe", "confidence"]

PROMPT = (
    "You are reading a trading chart screenshot. Return STRICT JSON only - no markdown, no "
    "prose - with exactly these keys:\n"
    '{"ticker": string|null, "direction": "long"|"short"|null, "entry": number|null, '
    '"stop": number|null, "target": number|null, "key_levels": [number]|null, '
    '"timeframe": string|null, "confidence": number(0..1)|null}\n'
    "Rules:\n"
    "- Read ONLY what is actually visible on the chart. Quote the ticker symbol exactly as printed.\n"
    "- For ANY field you cannot clearly read off the chart, return null. Do NOT guess or infer.\n"
    "- entry/stop/target/key_levels must be actual price numbers visible on the chart.\n"
    "- If the image is not a trading chart, return all nulls.\n"
    "Output JSON only."
)

_write_lock = threading.Lock()


def log(msg):
    line = "%s  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)


def session_date_et(ts_utc):
    """naive UTC ts -> America/New_York calendar date (the session day bars live under)."""
    try:
        dt = datetime.fromisoformat(ts_utc.replace("Z", ""))
        dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/New_York"))
        return dt.date().isoformat()
    except Exception:
        return None


def mime_for(path):
    return {".png": "image/png", ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(Path(path).suffix.lower(),
                                                              "image/png")


def _post(url, payload, headers, timeout):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def call_openrouter(model, b64, mime):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (mime, b64)}},
        ]}],
        "temperature": 0,
        "max_tokens": 1000,
        "response_format": {"type": "json_object"},
        # provider pinning per the OpenRouter rules already in use: prefer first-party Google.
        # (allow_fallback is not a valid OpenRouter provider key and 400s; order alone pins
        #  preference while still letting a :free variant find a serving provider.)
        "provider": {"order": ["Google"]},
    }
    body = _post(OPENROUTER_URL, payload, headers, 120)
    content = body["choices"][0]["message"]["content"]
    u = body.get("usage", {})
    # OpenRouter reports the real cost (0.0 for :free models); trust it.
    cost = float(u.get("cost", 0.0) or 0.0)
    return content, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), cost


def call_google(model, b64, mime):
    url = GOOGLE_URL % model + "?key=" + os.environ["GOOGLE_AI_STUDIO_API_KEY"]
    payload = {
        "contents": [{"role": "user", "parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": mime, "data": b64}},
        ]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1000,
                             "responseMimeType": "application/json"},
    }
    body = _post(url, payload, {"Content-Type": "application/json"}, 120)
    parts = body["candidates"][0]["content"]["parts"]
    content = "".join(p.get("text", "") for p in parts)
    u = body.get("usageMetadata", {})
    pt = u.get("promptTokenCount", 0)
    ct = u.get("candidatesTokenCount", 0)
    return content, pt, ct, pt * GFLASH_IN + ct * GFLASH_OUT


def call_omniroute(model, b64, mime):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (mime, b64)}},
        ]}],
        "stream": False,
        "max_tokens": 1000,
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json",
               "Authorization": "Bearer " + os.environ.get("OMNIROUTE_API_KEY", "")}
    body = _post(OMNIROUTE_URL, payload, headers, 120)
    msg = body["choices"][0]["message"]
    # auto/best-vision (a reasoning router) puts output in reasoning_content; fall back to it.
    content = msg.get("content") or msg.get("reasoning_content")
    u = body.get("usage", {})
    # local gateway; incumbent path, reserved credits - log 0 cost
    return content, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), 0.0


def _to_num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("$", "").replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_chart_json(content):
    """Extract strict-JSON dict from a model response. None if unparseable."""
    if not content:
        return None
    text = content.strip()
    # strip markdown code fences
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
    if fence:
        text = fence.group(1).strip()
    try:
        d = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            d = json.loads(m.group(0))
        except Exception:
            return None
    if not isinstance(d, dict):
        return None
    # coerce to schema; null anything missing
    out = {}
    for k in SCHEMA_KEYS:
        out[k] = d.get(k, None)
    # normalize types
    out["ticker"] = (str(out["ticker"]).strip().upper()
                     if out["ticker"] not in (None, "") else None)
    d_raw = out["direction"]
    out["direction"] = (str(d_raw).strip().lower()
                        if str(d_raw).strip().lower() in ("long", "short") else None)
    for k in ("entry", "stop", "target", "confidence"):
        out[k] = _to_num(out[k])
    kl = out["key_levels"]
    if isinstance(kl, list):
        out["key_levels"] = [x for x in (_to_num(v) for v in kl) if x is not None]
    elif kl is None:
        out["key_levels"] = None
    else:
        n = _to_num(kl)
        out["key_levels"] = [n] if n is not None else None
    out["timeframe"] = (str(out["timeframe"]).strip()
                        if out["timeframe"] not in (None, "") else None)
    return out


def load_manifest():
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def already_done(out_path):
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["path"])
            except Exception:
                continue
    return done


def run_one(tier, model, route, row):
    """Call the provider, return a result dict (never carries an 'error' key)."""
    path = row["path"]
    try:
        raw = Path(path).read_bytes()
    except Exception as e:
        log("  [skip] unreadable %s: %s" % (Path(path).name, e))
        return None
    b64 = base64.b64encode(raw).decode("ascii")
    mime = mime_for(path)

    last = None
    for attempt in range(8):
        try:
            if route == "openrouter":
                content, pt, ct, cost = call_openrouter(model, b64, mime)
            elif route == "google":
                content, pt, ct, cost = call_google(model, b64, mime)
            else:  # omniroute
                content, pt, ct, cost = call_omniroute(model, b64, mime)
            break
        except urllib.error.HTTPError as e:
            last = e
            body_txt = ""
            try:
                body_txt = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            # 429 / 5xx -> backoff and retry; 4xx otherwise -> drop
            if e.code == 429 or e.code >= 500:
                wait = min(2 ** attempt, 60)
                log("  [%s] %s HTTP %d, retry %ds (%s)"
                    % (tier, Path(path).name, e.code, wait, body_txt[:80]))
                time.sleep(wait)
                continue
            log("  [%s] %s HTTP %d, dropping: %s"
                % (tier, Path(path).name, e.code, body_txt[:120]))
            return None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = e
            wait = min(2 ** attempt, 20)
            log("  [%s] %s net err %s, retry %ds" % (tier, Path(path).name, e, wait))
            time.sleep(wait)
            continue
    else:
        log("  [%s] %s exhausted retries: %s" % (tier, Path(path).name, last))
        return None

    parsed = parse_chart_json(content)
    rec = {
        "tier": tier,
        "model": model,
        "path": path,
        "channel": row.get("channel"),
        "msg_id": row.get("msg_id"),
        "ts_utc": row.get("ts_utc"),
        "session_date_et": session_date_et(row.get("ts_utc")),
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "cost_usd": round(cost, 6),
        "parsed_ok": parsed is not None,
    }
    if parsed is not None:
        rec.update(parsed)
    else:
        # unparseable: keep the schema shape, all nulls. parsed_ok=False already set.
        for k in SCHEMA_KEYS:
            rec[k] = None
    # never write an error key - the done-guard. parsed_ok=False is the honest signal.
    return rec


def run_tier(tier, model, route, workers, limit):
    out_path = OUTDIR / ("vision_ladder_results_%s.jsonl" % tier)
    done = already_done(out_path)
    manifest = load_manifest()
    todo = [r for r in manifest if r["path"] not in done]
    if limit:
        todo = todo[:limit]

    log("START %s  model=%s route=%s  done=%d todo=%d workers=%d"
        % (tier, model, route, len(done), len(todo), workers))
    if not todo:
        log("  %s: nothing to do" % tier)
        return 0

    written = len(done)
    started = time.time()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def task(r):
        return run_one(tier, model, route, r)

    with open(out_path, "a", encoding="utf-8") as fout:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(task, r): r for r in todo}
            for i, fut in enumerate(as_completed(futs), 1):
                rec = fut.result()
                if rec is not None:
                    with _write_lock:
                        fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fout.flush()
                    written += 1
                if i % 25 == 0 or i == len(todo):
                    rate = i / max(time.time() - started, 1) * 60
                    log("  [%s] %d/%d done, %d written (%.0f/min)"
                        % (tier, i, len(todo), written, rate))

    log("DONE %s  %d total rows in %s" % (tier, written, out_path.name))
    return 0


TIERS = {
    # spec names google/gemma-4-31b-it:free, but that :free variant is throughput-blocked by
    # Google's free-gemma quota (~1 row/5min, unusable for a 200-image sample). FREE_MODEL lets
    # us run the SAME model (gemma-4-31b-it) via OpenRouter's paid variant to measure capability.
    # See vision_ladder.md.
    "free": (os.environ.get("FREE_MODEL", "google/gemma-4-31b-it:free"), "openrouter"),
    # spec routes flash via Google AI Studio (GOOGLE_AI_STUDIO_API_KEY), but that key's quota
    # is exhausted (429 "You exceeded your current quota"). FLASH_ROUTE/FLASH_MODEL let us
    # reach the SAME model (gemini-3.6-flash) via paid OpenRouter instead. See vision_ladder.md.
    "flash": (os.environ.get("FLASH_MODEL", "gemini-3.6-flash"),
              os.environ.get("FLASH_ROUTE", "google")),
    # spec routes incumbent via local OmniRoute on gemini/gemini-3.1-flash-lite (the scarface
    # annotator's model). OmniRoute is quota-cooling on that model (429 model_cooldown, all
    # credentials) and its vision auto-routers 400, so INCUMBENT_ROUTE/INCUMBENT_MODEL let us
    # reach the SAME model (gemini-3.1-flash-lite) via OpenRouter instead. The model identity
    # - "the model the existing annotator already used" - is what makes this the incumbent;
    # the route is just how the annotator reached it. See vision_ladder.md.
    "incumbent": (os.environ.get("INCUMBENT_MODEL", "google/gemini-3.1-flash-lite"),
                  os.environ.get("INCUMBENT_ROUTE", "openrouter")),
}


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("usage: vision_ladder_runner.py <free|flash|incumbent> [--workers N] [--limit N]")
        return 2
    tier = args[0]
    if tier not in TIERS:
        print("unknown tier: %s" % tier)
        return 2
    model, route = TIERS[tier]
    workers = 1
    limit = 0
    if "--workers" in args:
        workers = int(args[args.index("--workers") + 1])
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    return run_tier(tier, model, route, workers, limit)


if __name__ == "__main__":
    sys.exit(main())
