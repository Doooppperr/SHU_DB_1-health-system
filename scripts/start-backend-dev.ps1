$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $projectRoot "backend"
Set-Location $backendDir

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "backend/.venv not found. Please create virtualenv and install dependencies first."
}

& ".\.venv\Scripts\python.exe" run.py
