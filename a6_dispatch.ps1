# A6 paper-week logger dispatch — schtask OmenA6PaperLog, weekdays 16:20 ET.
# Runs a headless Claude Code session on GLM 5.2 via OpenRouter (queue model
# mapping: Sonnet tasks -> GLM). Prompt: a6-prompt.txt. Logs: journal\a6-*.log.
$ErrorActionPreference = 'Continue'
Set-Location C:\Users\aharg\tradingbot
$env:ANTHROPIC_API_KEY = (python C:\Users\aharg\.claude\sync-setup\keys.py get OPENROUTER)
$env:ANTHROPIC_BASE_URL = 'https://openrouter.ai/api'
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1'
$prompt = Get-Content C:\Users\aharg\tradingbot\a6-prompt.txt -Raw
$log = "C:\Users\aharg\tradingbot\journal\a6-$(Get-Date -Format yyyy-MM-dd).log"
claude -p $prompt --model z-ai/glm-5.2 --dangerously-skip-permissions *> $log
