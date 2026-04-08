$ErrorActionPreference = "Stop"

$backendScript = Join-Path $PSScriptRoot "start-backend-dev.ps1"
$frontendScript = Join-Path $PSScriptRoot "start-frontend-dev.ps1"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "`"$backendScript`""
)

& $frontendScript
