param(
    [string]$BackendListenHost = "127.0.0.1",
    [int]$BackendPort = 5050,
    [int]$BackendThreads = 8,
    [string]$FrontendListenHost = "127.0.0.1",
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
    $BackendPort,
    "-Threads",
    $BackendThreads
)

$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
& $frontendScript -ListenHost $FrontendListenHost -Port $FrontendPort
