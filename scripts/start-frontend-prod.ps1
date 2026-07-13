param(
    [string]$ListenHost = "127.0.0.1",
    [int]$Port = 4173
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$frontendDir = Join-Path $projectRoot "frontend"
Set-Location $frontendDir

npm run build
npm run preview -- --host $ListenHost --port $Port
