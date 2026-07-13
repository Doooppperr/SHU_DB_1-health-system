param(
    [string]$ListenHost = "127.0.0.1",
    [int]$Port = 5050,
    [int]$Threads = 8
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $projectRoot "backend"
Set-Location $backendDir

function New-RandomHexSecret {
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
}

function Ensure-ProductionJwtSecret {
    $currentProcessSecret = [string]$env:JWT_SECRET_KEY
    if ($currentProcessSecret.Trim().Trim('"').Trim("'").Length -ge 32) {
        return
    }

    $envPath = Join-Path $backendDir ".env"
    $content = if (Test-Path -LiteralPath $envPath) {
        [System.IO.File]::ReadAllText($envPath)
    }
    else {
        ""
    }
    $secretPattern = New-Object System.Text.RegularExpressions.Regex(
        "(?m)^\s*JWT_SECRET_KEY\s*=\s*(.*)\s*$"
    )
    $match = $secretPattern.Match($content)
    if ($match.Success) {
        $fileSecret = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
        if ($fileSecret.Length -ge 32) {
            $env:JWT_SECRET_KEY = $fileSecret
            return
        }
    }

    $generatedSecret = New-RandomHexSecret
    $replacement = "JWT_SECRET_KEY=$generatedSecret"
    if ($match.Success) {
        $content = $secretPattern.Replace($content, $replacement, 1)
    }
    else {
        if ($content.Length -gt 0 -and -not $content.EndsWith("`n")) {
            $content += [System.Environment]::NewLine
        }
        $content += $replacement + [System.Environment]::NewLine
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($envPath, $content, $utf8NoBom)
    $env:JWT_SECRET_KEY = $generatedSecret
    Write-Host "Generated a local production JWT secret in backend/.env."
}

$normalizedListenHost = $ListenHost.Trim().ToLowerInvariant()
$isLoopbackOnly = $normalizedListenHost -in @("127.0.0.1", "localhost", "::1")
if ($isLoopbackOnly) {
    $env:ALLOW_INSECURE_LOCAL_DEMO = "1"
}
else {
    Remove-Item Env:ALLOW_INSECURE_LOCAL_DEMO -ErrorAction SilentlyContinue
}

Ensure-ProductionJwtSecret

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "backend/.venv not found. Please create virtualenv and install dependencies first."
}

& ".\.venv\Scripts\python.exe" -m waitress --listen "$ListenHost`:$Port" --threads $Threads wsgi:app
