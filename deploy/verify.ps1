# Verify the live MCP server from a separate client in a separate process: not the Python SDK, but
# plain JSON-RPC over HTTP from PowerShell on another machine, the way a host from another vendor
# would speak the 2026-07-28 revision. Discovery, the tool list (twice, compared byte for byte),
# one run_sql, and one readback of its result in the same trace. Prints what the server answered and
# writes results\deploy\verification.json. Refuses to run against a host the probe did not reach.
#
#   powershell -ExecutionPolicy Bypass -File deploy\verify.ps1
$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "_env.ps1")
$probe = Get-Content (Join-Path $repo "results\hosting_probe.json") -Raw | ConvertFrom-Json
if (-not $probe.reached) { throw "results\hosting_probe.json says the host was not reached; run deploy\probe.ps1 first" }
Start-Transcript -Path (Join-Path $repo "deploy\verify-log.txt") -Force | Out-Null

$traceId = -join ((1..32) | ForEach-Object { "{0:x}" -f (Get-Random -Maximum 16) })
$spanId = -join ((1..16) | ForEach-Object { "{0:x}" -f (Get-Random -Maximum 16) })
$meta = [ordered]@{
    "io.modelcontextprotocol/protocolVersion" = "2026-07-28"
    "io.modelcontextprotocol/clientInfo" = @{ name = "readback-verify-powershell"; version = "1" }
    "io.modelcontextprotocol/clientCapabilities" = @{}
    traceparent = "00-$traceId-$spanId-01"
}
$script:id = 0
function Rpc($method, $params, $name) {
    $script:id += 1
    $p = [ordered]@{}; if ($params) { $params.GetEnumerator() | ForEach-Object { $p[$_.Key] = $_.Value } }
    $p["_meta"] = $meta
    $body = [ordered]@{ jsonrpc = "2.0"; id = $script:id; method = $method; params = $p } | ConvertTo-Json -Depth 12 -Compress
    $headers = @{ Accept = "application/json, text/event-stream"; "mcp-protocol-version" = "2026-07-28"; "mcp-method" = $method }
    if ($name) { $headers["mcp-name"] = $name }
    $raw = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$base/mcp" -ContentType "application/json" -Headers $headers -Body $body -TimeoutSec 120
    return @{ text = $raw.Content; json = ($raw.Content | ConvertFrom-Json) }
}

Write-Host "client: $env:COMPUTERNAME, PowerShell $($PSVersionTable.PSVersion), plain JSON-RPC (not the MCP SDK)"
Write-Host "server: $base/mcp"
$discover = Rpc "server/discover" $null $null
Write-Host "discover: versions $($discover.json.result.supportedVersions -join ', '), tools capability $([bool]$discover.json.result.capabilities.tools), ttl $($discover.json.result.ttlMs) $($discover.json.result.cacheScope)"
$list1 = Rpc "tools/list" $null $null
$list2 = Rpc "tools/list" $null $null
$names = $list1.json.result.tools | ForEach-Object { $_.name }
$identical = ($list1.json.result | ConvertTo-Json -Depth 20 -Compress) -eq ($list2.json.result | ConvertTo-Json -Depth 20 -Compress)
$withSchemas = ($list1.json.result.tools | Where-Object { $_.outputSchema }).Count
Write-Host "tools: $($names -join ', '); output schemas on $withSchemas of $($names.Count); two lists identical: $identical"
$sql = "select period, nim from metrics_bank_quarter where period = '2024Q4'"
$run = Rpc "tools/call" ([ordered]@{ name = "run_sql"; arguments = @{ warehouse = "ledger"; sql = $sql } }) "run_sql"
$rows = $run.json.result.structuredContent.rows
$rid = $run.json.result.structuredContent.result_id
$nim = [double]$rows[0][1]
Write-Host "run_sql: $($run.json.result.structuredContent.sql) returned $($rows.Count) row: $($rows[0] -join ', ')"
$display = "{0:N2}%" -f ($nim * 100)
$claim = [ordered]@{ value = [Math]::Round($nim * 100, 2); unit = "percent"; display = $display; result_id = $rid; column = "nim" }
$rb = Rpc "tools/call" ([ordered]@{ name = "readback"; arguments = @{ claim = $claim } }) "readback"
$verdict = $rb.json.result.structuredContent.verdict
Write-Host "readback: $display against the warehouse: $verdict ($($rb.json.result.structuredContent.reason))"
$statement = $run.json.result.structuredContent.statement.Length -gt 100
$ok = ($discover.json.result.supportedVersions -contains "2026-07-28") -and $identical -and ($names.Count -eq 7) -and ($withSchemas -eq 7) -and ($verdict -eq "agree") -and $statement
$result = [ordered]@{
    base_url = $base; client = "$env:COMPUTERNAME, Windows, PowerShell $($PSVersionTable.PSVersion), plain JSON-RPC"
    checked_at = (Get-Date).ToUniversalTime().ToString("o"); transport = "streamable HTTP"
    supported_versions = @($discover.json.result.supportedVersions); tools = @($names); output_schemas = $withSchemas
    lists_identical = $identical; run_sql_rows = $rows.Count; readback_display = $display; readback_verdict = $verdict
    statement_present = $statement; passed = $ok
}
New-Item -ItemType Directory -Force -Path (Join-Path $repo "results\deploy") | Out-Null
$result | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $repo "results\deploy\verification.json")
$result | ConvertTo-Json -Depth 6
Stop-Transcript | Out-Null
if (-not $ok) { throw "verification failed" }
Write-Host "verified: discovery, the tool list, a query and its readback, from a client that is not the SDK"
