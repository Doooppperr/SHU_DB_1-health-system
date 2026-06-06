param(
    [int]$BackendPort = 5050
)

$ErrorActionPreference = "Stop"

$backendScript = Join-Path $PSScriptRoot "start-backend-dev.ps1"
$frontendScript = Join-Path $PSScriptRoot "start-frontend-dev.ps1"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "`"$backendScript`"",
    "-Port",
    $BackendPort
)

$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
& $frontendScript
