param(
    [string]$ListenHost = "0.0.0.0",
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $projectRoot "backend"
Set-Location $backendDir

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "backend/.venv not found. Please create virtualenv and install dependencies first."
}

& ".\.venv\Scripts\python.exe" -m waitress --listen "$ListenHost`:$Port" wsgi:app
