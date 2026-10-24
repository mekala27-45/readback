# The three live checks in order, for one click in Git GUI: the probe (is the host up, which provider
# would answer), the separate client verification, and the load test with its first call timed on
# its own. Each writes its own file under results\; this script only runs them and stops on the first
# failure.
#
#   powershell -ExecutionPolicy Bypass -File deploy\live.ps1 [-IdleMinutes 20]
param([int]$IdleMinutes = 0)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $here "probe.ps1")
& (Join-Path $here "verify.ps1")
& (Join-Path $here "load-test.ps1") -IdleMinutes $IdleMinutes
Write-Host "live checks done: results\hosting_probe.json, results\deploy\verification.json, results\latency.json"
