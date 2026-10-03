"""Constants and paths. Everything here is declared before any forward result exists (prereg-S2.md)."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# ---- prereg-S2 window and caps (row W9) -------------------------------------------------
WINDOW_FIRST = "09:35"        # first signal-bar start that may be carded
WINDOW_LAST = "10:58"         # last signal-bar start (decision at 10:59, card by 11:00 ET)
MAX_CARDS_PER_DAY = 6
MIN_GAP_MINUTES = 5           # a card only if its signal bar closed >= this long after the previous card's (one tap at a time)
REPEAT_MINUTES = 30           # no second card on the same symbol and side this soon after one (the engine re-fires the same level)
WEEKDAYS = (0, 1, 2, 3)       # Mon-Thu
STALE_SECONDS = 45            # a card is only sent if its decision bar closed this recently
TAP_WINDOW_SECONDS = 120      # prereg-S2: a tap counts only within 2 min after the signal bar closes

# Eligibility (declared before any forward data): the engine's own causal status and tag at the decision bar.
ELIGIBLE_TAG = "clean"
ELIGIBLE_STATUS = "fired"
ELIGIBILITY_NOTE = ("engine status 'fired' (the tape's fired + halted, since the loss halt is applied after the engine) and tag "
                    "[clean] (retest not [late]). Fit window: 14.6 candidates/day, 35.7% of his 143 S rows inside it, mean R "
                    "-0.094 vs -0.316 for all candidates (a +0.22R head start: the S2 null must be this same pool). Chosen "
                    "from the fit-window tape before any forward data; every candidate is logged with its status and tags")

# ---- paths ------------------------------------------------------------------------------
PROD = Path(os.environ.get("OMEN_DATA_DIR", r"C:\Users\aharg\Desktop\Projects\tradingbot"))
ARCHIVE = PROD / "data_archive"                                    # read-only 1-min archive (Polygon)
S_TRADES = PROD / "research" / "agent_runs" / "v3-s-dataset" / "s_trades.csv"
LABELS_CSV = Path(os.environ.get("EYE_LABELS_CSV", str(PROD / "eye_card" / "labels.csv")))   # tap server writes here
DATA_DIR = Path(os.environ.get("STOCK_CARDS_DATA", r"C:\Users\aharg\Desktop\AI-Outputs\stock-cards"))
LOG_DIR = Path(os.environ.get("STOCK_CARDS_LOGS", r"C:\Users\aharg\Desktop\logs\stock-cards"))
SEND_FLAG_NAME = "SEND_ENABLED"      # an empty file in DATA_DIR turns real sends on; absent = dry run only

# The 28 tickers in the S2 tape and in s_trades.csv (same set, checked). Used when s_trades.csv is unreadable.
FALLBACK_WATCHLIST = (
    "AAPL", "ACHR", "AMD", "AMZN", "AVGO", "BABA", "COIN", "CRM", "GOOGL", "HOOD", "INTC", "IREN", "IWM", "MARA",
    "META", "MSFT", "MU", "NFLX", "NVDA", "ORCL", "PLTR", "QQQ", "SOFI", "SPCX", "SPY", "TSLA", "TSM", "UBER",
)


def load_watchlist(path: Path | None = None) -> list[str]:
    """Tickers Austin marks, read from s_trades.csv; the committed 28-ticker list if the file is not readable."""
    p = Path(path) if path else S_TRADES
    try:
        with open(p, newline="", encoding="utf-8") as fh:
            syms = sorted({r["sym"].strip().upper() for r in csv.DictReader(fh) if r.get("sym")})
        if syms:
            return syms
    except (OSError, KeyError):
        pass
    return list(FALLBACK_WATCHLIST)


def send_enabled(data_dir: Path | None = None) -> bool:
    return ((Path(data_dir) if data_dir else DATA_DIR) / SEND_FLAG_NAME).exists()
