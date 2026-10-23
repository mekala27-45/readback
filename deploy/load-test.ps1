# Latency through the live API from a separate client: the cold start (the first call after the
# function has been idle for the stated minutes) measured on its own, then N sequential chat turns of
# test split questions through the floor, then N MCP tool calls. Writes results\latency.json.
#
#   powershell -ExecutionPolicy Bypass -File deploy\load-test.ps1 [-IdleMinutes 20] [-Turns 20]
param([int]$IdleMinutes = 0, [int]$Turns = 20)
$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "_env.ps1")
function Summary($samples) {
    $s = $samples | Sort-Object; $n = $s.Count
    $p50 = if ($n % 2) { $s[[int](($n - 1) / 2)] } else { ($s[[int]($n / 2) - 1] + $s[[int]($n / 2)]) / 2 }
    $p99 = $s[[Math]::Min($n - 1, [int][Math]::Round(0.99 * ($n - 1)))]
    return [ordered]@{ n = $n; p50_ms = [Math]::Round($p50, 1); p99_ms = [Math]::Round($p99, 1); max_ms = [Math]::Round($s[$n - 1], 1) }
}
if ($IdleMinutes -gt 0) { Write-Host "waiting $IdleMinutes minutes for the function to go idle"; Start-Sleep -Seconds ($IdleMinutes * 60) }
$sw = [Diagnostics.Stopwatch]::StartNew()
$null = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 180
$cold = $sw.Elapsed.TotalMilliseconds
$questions = (Get-Content (Join-Path $repo "deploy\load_questions.json") -Raw | ConvertFrom-Json) | Select-Object -First $Turns
$chat = @()
foreach ($q in $questions) {
    $sw.Restart()
    $null = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$base/v1/chat" -ContentType "application/json" -Body (@{ question = $q; provider = "floor" } | ConvertTo-Json) -TimeoutSec 180
    $chat += $sw.Elapsed.TotalMilliseconds
}
$meta = @{ "io.modelcontextprotocol/protocolVersion" = "2026-07-28"; "io.modelcontextprotocol/clientCapabilities" = @{} }
$body = @{ jsonrpc = "2.0"; id = 1; method = "tools/call"; params = @{ name = "run_sql"; arguments = @{ warehouse = "turnaround"; sql = "select carrier, sum(flown) as flown from mart_carrier_month where year = 2025 group by carrier order by flown desc limit 5" }; _meta = $meta } } | ConvertTo-Json -Depth 8 -Compress
$headers = @{ Accept = "application/json, text/event-stream"; "mcp-protocol-version" = "2026-07-28"; "mcp-method" = "tools/call"; "mcp-name" = "run_sql" }
$tool = @()
for ($i = 0; $i -lt $Turns; $i++) {
    $sw.Restart()
    $null = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$base/mcp" -ContentType "application/json" -Headers $headers -Body $body -TimeoutSec 60
    $tool += $sw.Elapsed.TotalMilliseconds
}
$result = [ordered]@{ base_url = $base; measured_at = (Get-Date).ToUniversalTime().ToString("o"); idle_minutes_before_first = $IdleMinutes
    cold_start_ms = [Math]::Round($cold, 1); chat = Summary $chat; run_sql = Summary $tool; provider = "floor"
    client = "$env:COMPUTERNAME, Windows, PowerShell $($PSVersionTable.PSVersion)"
    note = "sequential, after the first call; the first call is the cold start when the function was idle" }
$result | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $repo "results\latency.json")
$result | ConvertTo-Json -Depth 5
