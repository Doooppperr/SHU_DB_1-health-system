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
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $projectRoot "backend"
$workerPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$workerEntry = Join-Path $backendDir "scripts\notification_worker.py"

function Wait-BackendReady {
    param([int]$Port)
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 1
            if ($response.StatusCode -eq 200) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "Backend did not become ready on port $Port; notification worker was not started."
}

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

if (-not (Test-Path -LiteralPath $workerPython)) {
    throw "backend/.venv not found. Please create virtualenv and install dependencies first."
}

Wait-BackendReady -Port $BackendPort

$workerProcess = Start-Process -FilePath $workerPython -ArgumentList @(
    "`"$workerEntry`"",
    "--watch",
    "--config",
    "development",
    "--interval-seconds",
    "5"
) -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru

try {
    $env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
    & $frontendScript -ListenHost $FrontendListenHost -Port $FrontendPort
}
finally {
    if ($workerProcess -and -not $workerProcess.HasExited) {
        Stop-Process -Id $workerProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
