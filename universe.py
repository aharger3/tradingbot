"""Single source of truth for symbol pools.

Three tracked pools (2026-08-11):
  MAJOR_15   – the 15 core equities (incl. ACHR/NFLX/ORCL, excl. MSTR)
  INDEX_POOL – QQQ, SPY, IWM
  OTHER_POOL – everything else live_scanner tracks (DEFAULT_SYMBOLS minus the above)

Usage:
  from universe import MAJOR_15, INDEX_POOL, OTHER_POOL, ALL_SYMS, POOL_OF
"""

MAJOR_15 = [
    "NVDA","TSLA","AAPL","SPCX","MSFT","MU","INTC","PLTR",
    "AMZN","META","AMD","GOOGL","ACHR","NFLX","ORCL",
]

INDEX_POOL = ["QQQ","SPY","IWM"]

# Everything in live_scanner DEFAULT_SYMBOLS minus MAJOR_15 and INDEX_POOL.
OTHER_POOL = [
    "GOOG","SOFI","COIN","HOOD","IREN","AVGO","UBER","BABA","CRM","TSM","MARA",
]

ALL_SYMS = MAJOR_15 + INDEX_POOL + OTHER_POOL  # 15 + 3 + 11 = 29 symbols

# Reverse lookup: symbol -> pool name (used for per-pool reporting).
POOL_OF = {}
for _name, _pool in [
    ("MAJOR_15", MAJOR_15),
    ("INDEX_POOL", INDEX_POOL),
    ("OTHER_POOL", OTHER_POOL),
]:
    for _sym in _pool:
        POOL_OF[_sym] = _name