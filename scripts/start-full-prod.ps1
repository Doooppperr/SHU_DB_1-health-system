param(
    [string]$BackendListenHost = "0.0.0.0",
    [int]$BackendPort = 5000,
    [string]$FrontendListenHost = "0.0.0.0",
    [int]$FrontendPort = 4173
)

$ErrorActionPreference = "Stop"

$backendScript = Join-Path $PSScriptRoot "start-backend-prod.ps1"
$frontendScript = Join-Path $PSScriptRoot "start-frontend-prod.ps1"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "`"$backendScript`"",
    "-ListenHost",
    $BackendListenHost,
    "-Port",
    $BackendPort
)

& $frontendScript -ListenHost $FrontendListenHost -Port $FrontendPort
