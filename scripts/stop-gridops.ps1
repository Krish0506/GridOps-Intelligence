param(
    [switch]$StopDatabase
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$pidFile = Join-Path $root ".run\vite.pid"

Write-Host "=== Stopping GridOps Intelligence ===" -ForegroundColor Cyan

# Stop only the frontend process this repository started. Never kill every
# Node process on the machine: other projects may be running.
if (Test-Path $pidFile) {
    $vitePid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($vitePid) {
        taskkill /PID $vitePid /T /F *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Frontend process tree $vitePid stopped"
        } else {
            Write-Host "[..] Frontend process $vitePid was not running"
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "[..] No frontend PID file; nothing to stop"
}

$listener = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Warning "Port 5173 is still listening (PID $($listener.OwningProcess)). It was not started by this PID file; close it manually if it is stale."
}

# Stop the API container but keep the PostgreSQL container and named volume.
docker compose stop api *> $null
Write-Host "[OK] API container stopped (database preserved)"

if ($StopDatabase) {
    docker compose stop db *> $null
    Write-Host "[OK] PostgreSQL container stopped (named volume preserved)"
} else {
    Write-Host "[..] PostgreSQL left running. Use -StopDatabase to stop it too."
}

Write-Host ""
Write-Host "Destructive volume removal is intentionally not automated: 'docker compose down -v' would delete the database."
exit 0
