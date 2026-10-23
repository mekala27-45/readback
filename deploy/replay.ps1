# Preload the demo queue so the desk is never empty: every development question through the floor,
# from a separate client, over the chat stream. Writes what the server answered to
# results\deploy\replay.json.
#
#   powershell -ExecutionPolicy Bypass -File deploy\replay.ps1
$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "_env.ps1")
$questions = Get-Content (Join-Path $repo "deploy\demo_questions.json") -Raw | ConvertFrom-Json
$made = @()
foreach ($q in $questions) {
    $body = @{ question = $q.question; provider = "floor" } | ConvertTo-Json
    try {
        $raw = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$base/v1/chat" -ContentType "application/json" -Body $body -TimeoutSec 180
        $answer = $null
        foreach ($line in ($raw.Content -split "`n")) {
            if ($line.StartsWith("data:")) {
                $event = $line.Substring(5) | ConvertFrom-Json
                if ($event.event -eq "answer") { $answer = $event }
            }
        }
        $made += [ordered]@{ id = $q.id; answer_id = $answer.answer_id; verdict = $answer.answer.verdict; trace_id = $answer.trace_id }
        Write-Host "$($q.id): $($answer.answer.verdict) $($answer.answer_id)"
    } catch { Write-Host "$($q.id): failed, $($_.Exception.Message)" }
}
$result = [ordered]@{ base_url = $base; replayed_at = (Get-Date).ToUniversalTime().ToString("o"); questions = $questions.Count;
    answered = ($made | Where-Object { $_.answer_id }).Count; verified = ($made | Where-Object { $_.verdict -eq "verified" }).Count; answers = $made }
New-Item -ItemType Directory -Force -Path (Join-Path $repo "results\deploy") | Out-Null
$result | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $repo "results\deploy\replay.json")
Write-Host "replayed: $($result.answered) of $($questions.Count) answered, $($result.verified) verified"
