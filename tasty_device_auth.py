"""One-time Tastytrade device verification.

Tastytrade now blocks new API sessions with a device challenge (403
device_challenge_required + emailed code). Run this ONCE interactively:

    python tasty_device_auth.py

It logs in, triggers the challenge, asks for the code Tastytrade emails you,
submits it, then saves a remember-me token to .env. tastytrade_feed uses that
token on future logins so the scanner never sees the challenge again.
"""
import os
import sys
from pathlib import Path

import requests

API_BASE = "https://api.tastyworks.com"
UA = {"User-Agent": "omen-trading-bot/1.0"}
ENV = Path(__file__).parent / ".env"


def _env(key):
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return os.getenv(key, "")


def _save_env(key, value):
    lines = [l for l in ENV.read_text().splitlines() if not l.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    ENV.write_text("\n".join(lines) + "\n")


def main():
    user = _env("TASTYTRADE_USERNAME") or _env("USERNAME")
    pw = _env("TASTYTRADE_PASSWORD") or _env("PASSWORD")
    if not user or not pw:
        sys.exit("TASTYTRADE_USERNAME/PASSWORD not in .env")

    body = {"login": user, "password": pw, "remember-me": True}
    r = requests.post(f"{API_BASE}/sessions", json=body, headers=UA, timeout=15)

    if r.status_code == 403 and "device_challenge_required" in r.text:
        challenge_token = r.headers.get("X-Tastyworks-Challenge-Token", "")
        # this POST makes Tastytrade text the one-time code to your phone
        cr = requests.post(
            f"{API_BASE}/device-challenge",
            json={"login": user},
            headers={**UA, "X-Tastyworks-Challenge-Token": challenge_token},
            timeout=15,
        )
        if cr.status_code >= 300:
            sys.exit(f"Challenge request failed: HTTP {cr.status_code} {cr.text[:300]}")
        phone = cr.json().get("data", {}).get("phone", "your phone")
        code = input(f"Tastytrade texted a code to {phone}. Enter it: ").strip()
        r = requests.post(
            f"{API_BASE}/sessions", json=body,
            headers={**UA, "X-Tastyworks-Challenge-Token": challenge_token,
                     "X-Tastyworks-OTP": code},
            timeout=15,
        )

    if r.status_code != 201:
        sys.exit(f"Login failed: HTTP {r.status_code} {r.text[:300]}")

    data = r.json().get("data", {})
    remember = data.get("remember-token")
    if remember:
        _save_env("TASTYTRADE_REMEMBER_TOKEN", remember)
        print("Saved TASTYTRADE_REMEMBER_TOKEN to .env — scanner will use it.")
    else:
        print("Login OK but no remember-token returned; session works for 24h.")
    print(f"session-token: ...{(data.get('session-token') or '')[-8:]}")


if __name__ == "__main__":
    main()
