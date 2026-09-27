$k=[Environment]::GetEnvironmentVariable('POLYGON_API_KEY','User')
if(-not $k){$k=[Environment]::GetEnvironmentVariable('POLYGON_API_KEY','Machine')}
if(-not $k){'NOKEY'; exit 1}
$env:POLYGON_API_KEY=$k
Set-Location $PSScriptRoot
python opt0.py fetch *> fetch.log
