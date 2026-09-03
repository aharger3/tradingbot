"""Discord chat-mining vocabulary. NOT the traded universe.

`universe.py` answers "what does OMEN trade or backtest." The parsers in this
directory (research/corpus_sf/*.py) answer a different question: "what does
this raw chat message say," which requires recognizing two kinds of thing
universe.py has no reason to model:

  * real tickers mentors and members name that OMEN never trades (futures
    contracts, indices, other people's plays) -- so a mention can be read
    without pretending it is part of the tradeable universe.
  * uppercase tokens that LOOK like tickers but are jargon or ordinary prose
    ("ALL", "OR", "BE", "PDH") -- a stop-word list, the inverse of a universe.

Both are read-only text-recognition dictionaries feathered into `research/
corpus_sf`'s mining output. Nothing here is fed into a backtest, the signal
engine, or a symbol pool; `research/test_universe_single_source.py` exempts
this file for that reason.

Each constant stays named for the one parser that uses it and is NOT merged
across parsers: the channels differ (Scarface calls index futures Jdub never
mentions; post-your-gains prose collides with a much longer stop-word set
than the premarket call-outs do), so a shared list would silently change what
each parser recognizes. This file is a shared HOME, not a shared VALUE.
"""

# --- research/corpus_sf/bar_availability.py ---------------------------------
# Symbols the Polygon STOCKS aggregates endpoint cannot serve.
BAR_AVAILABILITY_FUTURES_SYMS = {
    "NQ", "ES", "YM", "RTY", "MNQ", "MES", "MYM", "M2K", "GC", "CL", "SPX",
    "NDX", "VIX",
}

# --- research/corpus_sf/grade_levels.py -------------------------------------
# Tickers that appear in this Discord beyond the engine universe. Kept explicit
# so a false ticker hit is a listed decision, not a regex accident.
GRADE_LEVELS_EXTRA_TICKERS = [
    "ES", "NQ", "MES", "MNQ", "RTY", "YM", "CL", "GC",      # futures
    "DIA", "SMCI", "RIVN", "MSTR", "ARM", "QCOM", "SPCE",
    "GME", "AMC", "SNAP", "SHOP", "DIS", "BA", "JPM", "XOM",
    "LULU", "COST", "WMT", "CRWD", "PANW", "SNOW", "DDOG",
    "ABNB", "RBLX", "U", "PYPL", "SQ", "ROKU", "ZM", "DKNG",
]

# --- research/corpus_sf/parse_pre_market_live.py ----------------------------
# Whitelist = universe.py + index/futures tickers Jdub names in premarket that
# the engine does not trade but does reference for bias.
PRE_MARKET_LIVE_EXTRA_SYMS = ["ES", "NQ", "SPX", "NDX", "DIA", "VIX", "SMH", "GOOG"]

# Tokens that look like tickers but are vocabulary. Belt and braces: the
# whitelist already excludes them, this documents the collision set.
PRE_MARKET_LIVE_NOT_TICKERS = {
    "PDH", "PDL", "PMH", "PML", "HOD", "LOD", "ATH", "ATHS", "OR",
    "EST", "AM", "PM", "PCE", "CPI", "AS", "IF",
}

# --- research/corpus_sf/parse_scarface_alerts.py ----------------------------
# Tickers that actually appear in this channel and are not in the engine
# universe. Ambiguous English words that are also real tickers (NOW, U, V,
# AI, SHOP, COST, ARM) are deliberately excluded.
SCARFACE_EXTRA_SYMS = ["SNDK", "GME", "DELL", "SMCI", "RIVN", "CRWD", "LLY", "MSTR"]

# --- research/corpus_sf/parse_gains.py --------------------------------------
# Uppercase tokens that look like tickers but are level names, jargon or words.
GAINS_NOT_TICKERS = {
    "HOD", "LOD", "PDH", "PDL", "PMH", "PML", "PDC", "PWH", "PWL", "ORH",
    "ORL", "ORB", "OR", "OB", "SL", "TP", "PT", "PA", "HTF", "LTF", "TF",
    "BE", "RR", "IV", "ITM", "OTM", "ATH", "ATL", "EMA", "SMA", "VWAP",
    "FVG", "FOMO", "FOMC", "CPI", "PPI", "PNL", "PL", "EOD", "EST", "ET",
    "AM", "PM", "DTE", "ODTE", "IBKR", "TOS", "TV", "YT", "DM", "LOL", "LFG",
    "IMO", "ROI", "USD", "KL", "BNR", "BR", "OCR", "IRA", "TWS", "BRB",
    "GJ", "GG", "WTF", "AF", "IDK", "TBH", "ATM", "MM", "MA", "RSI", "MACD",
    "US", "UK", "EU", "AI", "CEO", "PC", "APP", "TA", "PS", "NFA", "YOLO",
    "THE", "AND", "FOR", "NOT", "BUT", "YOU", "ALL", "OUT", "WIN", "LOSS",
    "RED", "GREEN", "BIG", "DAY", "NO", "SO", "OK", "ON", "TO", "MY", "IN",
    "IS", "IT", "AT", "BY", "UP", "IF", "AS", "AN", "AC", "PYA", "PMHR",
    "PDHR", "JDUB", "LIVE", "TRADE", "THAT", "VERY", "RS", "GO", "SPXW",
    "NA", "OG", "EOW", "WK", "MOC", "SPCX",
}
