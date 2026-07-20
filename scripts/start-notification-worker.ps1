param(
    [ValidateSet("development", "production")]
    [string]$Config = "development",
    [int]$IntervalSeconds = 5,
    [int]$Limit = 50
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $projectRoot "backend"
$python = Join-Path $backendDir ".venv\Scripts\python.exe"
$worker = Join-Path $backendDir "scripts\notification_worker.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "backend/.venv not found. Please create virtualenv and install dependencies first."
}

Set-Location $backendDir
& $python $worker --watch --config $Config --interval-seconds $IntervalSeconds --limit $Limit
