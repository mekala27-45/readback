# The hosting probe, run from a separate machine before the deploy step is called done: the live
# health route (and through it Neon), and each provider whose key is in .env with a request that
# lists its models, which uses no generation quota. Writes results\hosting_probe.json and
# results\providers.json with the model ids and limits the APIs report, and never a key.
#
#   powershell -ExecutionPolicy Bypass -File deploy\probe.ps1
$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "_env.ps1")
$out = Join-Path $repo "results"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$sw = [Diagnostics.Stopwatch]::StartNew()
try {
    $health = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 120
    $first = $sw.Elapsed.TotalMilliseconds
    $sw.Restart(); $null = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 60; $warm = $sw.Elapsed.TotalMilliseconds
    $hosting = [ordered]@{ host = "vercel"; url = $base; reached = $true; status = $health.status; database = $health.database;
        protocol_revision = $health.protocol_revision; provider = $health.provider; first_ms = [Math]::Round($first, 0); warm_ms = [Math]::Round($warm, 0) }
} catch {
    $hosting = [ordered]@{ host = "vercel"; url = $base; reached = $false; error = $_.Exception.Message }
}
$hosting["probed_at"] = (Get-Date).ToUniversalTime().ToString("o")
$hosting["client"] = "$env:COMPUTERNAME, Windows, PowerShell $($PSVersionTable.PSVersion)"
$hosting | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $out "hosting_probe.json")

$providers = [ordered]@{}
function Probe($name, $url, $headers, $pick) {
    try {
        $r = Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec 60
        $providers[$name] = [ordered]@{ reached = $true; models = @(& $pick $r) }
    } catch { $providers[$name] = [ordered]@{ reached = $false; error = $_.Exception.Message.Split("`n")[0] } }
}
if ($env:GEMINI_API_KEY) {
    Probe "gemini" "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200" @{ "x-goog-api-key" = $env:GEMINI_API_KEY } {
        param($r) $r.models | Where-Object { $_.name -match "flash" -and $_.supportedGenerationMethods -contains "generateContent" } | ForEach-Object { $_.name -replace "^models/", "" } }
} else { $providers["gemini"] = [ordered]@{ reached = $false; error = "no GEMINI_API_KEY in .env" } }
if ($env:GROQ_API_KEY) {
    Probe "groq" "https://api.groq.com/openai/v1/models" @{ Authorization = "Bearer $env:GROQ_API_KEY" } { param($r) $r.data | ForEach-Object { $_.id } }
} else { $providers["groq"] = [ordered]@{ reached = $false; error = "no GROQ_API_KEY in .env" } }
if ($env:OPENROUTER_API_KEY) {
    Probe "openrouter" "https://openrouter.ai/api/v1/key" @{ Authorization = "Bearer $env:OPENROUTER_API_KEY" } { param($r) @("limit " + $r.data.limit, "free tier " + $r.data.is_free_tier) }
} else { $providers["openrouter"] = [ordered]@{ reached = $false; error = "no OPENROUTER_API_KEY in .env" } }
if ($env:SAMBANOVA_API_KEY) {
    Probe "sambanova" "https://api.sambanova.ai/v1/models" @{ Authorization = "Bearer $env:SAMBANOVA_API_KEY" } { param($r) $r.data | ForEach-Object { $_.id } }
} else { $providers["sambanova"] = [ordered]@{ reached = $false; error = "no SAMBANOVA_API_KEY in .env" } }
$providers["probed_at"] = (Get-Date).ToUniversalTime().ToString("o")
$providers | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $out "providers.json")
$hosting | ConvertTo-Json -Depth 5
$providers | ConvertTo-Json -Depth 5
if (-not $hosting.reached) { throw "the probe did not reach $base; the deploy step does not proceed" }
