# Windows Setup — Vanquish Signal Bot

Run the scanner on a Windows machine 24/7. Hermes edits the rules via GitHub; this machine runs the bot.

## 1. Install Python

1. Download Python 3.12+ from https://www.python.org/downloads/windows/
2. **Important:** during install, check **"Add python.exe to PATH"**
3. Verify in PowerShell:
   ```powershell
   python --version
   ```

## 2. Install Git

1. Download from https://git-scm.com/download/win
2. Install with defaults
3. Verify:
   ```powershell
   git --version
   ```

## 3. Clone the repo

```powershell
cd $HOME\Documents
git clone https://github.com/aharger3/tradingbot.git
cd tradingbot
```

## 4. Install dependencies

```powershell
pip install -r requirements.txt
```

## 5. Create the .env files

Copy the example and fill in your real keys (both files are gitignored — never committed):

```powershell
copy .env.example .env
notepad .env
```

Fill in:
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

Tastytrade is the data/broker integration — create `.env.tastytrade` with:
```
CLIENT_ID=...
CLIENT_SECRET=...
REFRESH_TOKEN=...
ACCOUNT_NUMBER=...
```
See `tastytrade_feed.py` for details on obtaining these.

## 6. Test it

```powershell
python live_scanner.py --once --no-discord
```

Should print signals (or "no new signals") without errors.

Then test Discord posting:
```powershell
python live_scanner.py --once
```
Check your Discord channel for a post.

## 7. Run the live loop

```powershell
python live_scanner.py
```

Loops 9:30-11:00 ET, posts on signals. Ctrl+C to stop.

## 8. Auto-start daily (Task Scheduler)

So you never forget to run it:

1. Open **Task Scheduler**
2. **Create Basic Task** → name "Signal Bot"
3. Trigger: **Daily** at **9:25 AM ET** (adjust if your PC clock is a different timezone)
4. Action: **Start a program**
   - Program: `python`
   - Arguments: `live_scanner.py`
   - Start in: `C:\Users\YOU\Documents\tradingbot`
5. Finish.

Optional: add a second daily task at 9:24 AM that runs `git pull` first, so you always get Hermes's latest rule changes before the scan:
   - Program: `git`
   - Arguments: `pull`
   - Start in: `C:\Users\YOU\Documents\tradingbot`

## Daily flow once set up

1. 9:24 ET — Task Scheduler runs `git pull` (gets Hermes's latest rules)
2. 9:25 ET — Task Scheduler runs `live_scanner.py`
3. 9:30-11:00 ET — signals post to Discord, you trade in Vanquish
4. 11:05 ET — Hermes asks how it went, logs journal
5. Anytime — talk to Hermes about improvements; it commits to GitHub; next morning's `git pull` picks them up

## Notes

- Keep the PC awake during 9:30-11 ET (Settings → Power → never sleep, or sleep after the window).
- The repo's `journal/` folder also lives here; if you want the journal on this PC too, it's already cloned.
- Only `requests` is an external dependency; everything else is Python stdlib.
