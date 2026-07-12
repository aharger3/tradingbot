#!/usr/bin/env python3
"""Trading bot dashboard server - serves HTML + JSON API on port 9121."""

import json
import os
import re
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from zoneinfo import ZoneInfo

REPO = "C:/Users/aharg/tradingbot"
PORT = 9122
HTML_PATH = os.path.join(REPO, "dashboard", "dashboard.html")


def load_today_data():
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    log_path = os.path.join(REPO, "journal", f"scanner-{today}.log")
    trades_path = os.path.join(REPO, "journal", "paper-trades.jsonl")
    signal_path = os.path.join(REPO, "journal", f"signal_log_{today}.jsonl")

    watchlist = {}
    signals = []
    trades = []
    total_pnl = 0.0
    wins = 0
    losses = 0
    last_scan_time = ""
    scan_cycles = 0
    log_size_kb = 0
    open_positions = []

    if os.path.exists(log_path):
        with open(log_path, "rb") as f:
            raw = f.read()
        log_size_kb = round(len(raw) / 1024, 1)
        text = raw.decode("utf-16-le")
        lines = text.split("\n")

        for line in lines:
            ls = line.strip()

            m = re.search(r"=== (\d+:\d+:\d+) ET scan ===", ls)
            if m:
                last_scan_time = m.group(1)
                scan_cycles += 1

            m = re.search(r"\[(\w+)\] PDH ([\d.]+) / PDL ([\d.]+) / HTF (\w+)", ls)
            if m:
                watchlist[m.group(1)] = {
                    "pdh": float(m.group(2)),
                    "pdl": float(m.group(3)),
                    "htf": m.group(4).lower(),
                }

            if "PAPER CLOSE" in ls:
                m = re.search(r"PAPER CLOSE (\w+) (\w+)", ls)
                if m:
                    pnl_match = re.search(r"P&L \$?(-?[\d,]+(?:\.[\d]+)?)", ls)
                    pnl = 0.0
                    if pnl_match:
                        pnl = float(pnl_match.group(1).replace(",", ""))
                    total_pnl += pnl
                    if pnl > 0:
                        wins += 1
                    elif pnl < 0:
                        losses += 1
                    trades.append({
                        "symbol": m.group(1),
                        "direction": m.group(2),
                        "pnl": pnl,
                    })

    if os.path.exists(trades_path):
        closes = set()
        all_lines = []
        with open(trades_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        pt = json.loads(line)
                        all_lines.append(pt)
                        if pt.get("event") == "CLOSE":
                            closes.add((pt.get("symbol"), pt.get("opened_at")))
                    except:
                        pass

        for pt in all_lines:
            if pt.get("event") == "OPEN":
                key = (pt.get("symbol"), pt.get("opened_at"))
                if key not in closes:
                    open_positions.append(pt)
            elif pt.get("event") == "CLOSE":
                pnl = pt.get("pnl", 0) or 0
                total_pnl += pnl
                if pnl > 0: wins += 1
                elif pnl < 0: losses += 1
                trades.append({
                    "symbol": pt.get("symbol", "?"),
                    "direction": pt.get("direction", "?"),
                    "pnl": pnl,
                    "outcome": pt.get("outcome", "?"),
                })

    if os.path.exists(signal_path):
        with open(signal_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        signals.append(json.loads(line))
                    except:
                        pass

    return {
        "pnl": {
            "total_pnl": total_pnl,
            "trade_count": len(trades),
            "wins": wins,
            "losses": losses,
            "trades": trades,
        },
        "positions": open_positions,
        "signals": signals,
        "watchlist": watchlist,
        "heartbeat": {
            "date": today,
            "last_scan_time": last_scan_time,
            "log_size_kb": log_size_kb,
            "scan_cycles": scan_cycles,
        },
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]  # strip query params

        if path == "/api/data":
            data = load_today_data()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())
            return

        if path in ("/", "/index.html", "/dashboard.html"):
            if os.path.exists(HTML_PATH):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                with open(HTML_PATH, "rb") as f:
                    self.wfile.write(f.read())
                return

        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not found")

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]} {args[1]} {args[2]}")


def main():
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"Dashboard: http://localhost:{PORT}")
    print(f"API:       http://localhost:{PORT}/api/data")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
