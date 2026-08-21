"""Delta scraper runner that stubs out the missing playwright import.
Reads the captured user token from .disc_token_tmp and runs
discord_scraper.main() — the scraper's own break condition stops at each
channel's stored newest, so only the delta is pulled.
"""
import sys, types, pathlib

# Stub playwright so discord_scraper.py can import without the package
pw_mod = types.ModuleType("playwright")
pw_sync = types.ModuleType("playwright.sync_api")
pw_sync.sync_playwright = lambda: None
pw_mod.sync_api = pw_sync
sys.modules["playwright"] = pw_mod
sys.modules["playwright.sync_api"] = pw_sync

# Now import and run
import discord_scraper

tok = pathlib.Path(".disc_token_tmp").read_text(encoding="utf-8").strip()
discord_scraper.sniff_token = lambda: tok
discord_scraper.main()
