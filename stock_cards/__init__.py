"""W9 stock cards: the forward S2 feed.

Scans Austin's watchlist on live-ish 1-minute bars (Alpaca IEX, read-only market data), runs the same engine that
built the S2 tape, and sends one ntfy card per eligible candidate at the decision bar, with S / Not S / Skip buttons.
Paper research only. No orders. Not investment advice.
"""
