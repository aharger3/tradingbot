# Usage: .\new_worktree.ps1 <name> [base-ref=origin/main]
# Makes ..\.worktrees\<name> on branch wt/<name> WITHOUT the ~2.4 GB of tracked data
# (data_archive/ + research/*.json). Code finds the archive via omen_paths.py.
param([Parameter(Mandatory)][string]$Name, [string]$Base = "origin/main")
$main = Split-Path (git rev-parse --path-format=absolute --git-common-dir) -Parent
$dest = Join-Path (Split-Path $main -Parent) ".worktrees\$Name"
git -C $main worktree add --no-checkout -b "wt/$Name" $dest $Base
git -C $dest sparse-checkout set --no-cone '/*' '!/data_archive/' '!/research/*.json'
git -C $dest checkout
Write-Host "worktree: $dest  (data: OMEN_DATA_DIR or $main\data_archive)"
