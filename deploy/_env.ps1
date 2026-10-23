# Shared by the deploy scripts: read KEY=VALUE lines from the .env beside the repository into this
# process only. Nothing read here is ever printed or written.
function Read-DotEnv($path) {
    if (Test-Path $path) {
        Get-Content $path | ForEach-Object {
            if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
                $name = $matches[1]; $value = $matches[2].Trim().Trim('"').Trim("'")
                if (-not [string]::IsNullOrEmpty($value)) { [Environment]::SetEnvironmentVariable($name, $value, "Process") }
            }
        }
    }
}
$script:repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Read-DotEnv (Join-Path (Split-Path -Parent $script:repo) ".env")
Read-DotEnv (Join-Path $script:repo ".env")
$script:base = (Get-Content (Join-Path $script:repo "deploy\live-url.txt") -Raw).Trim().TrimEnd("/")
