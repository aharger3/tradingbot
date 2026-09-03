"""Thin runner: reuse discord_scraper.main() exactly, but supply the user token
captured from the logged-in Chrome session (playwright CDP connect is broken on
Chrome 151, so sniff_token cannot run). Delta-only by the scraper's own logic."""
import sys, pathlib
import discord_scraper
tok = pathlib.Path(".disc_token_tmp").read_text(encoding="utf-8").strip()
discord_scraper.sniff_token = lambda: tok
discord_scraper.main()
