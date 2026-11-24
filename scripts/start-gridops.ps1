param(
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$SkipDemoInit,
    [switch]$NoBuild
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$runDir = Join-Path $root ".run"
New-Item -ItemType Directory -Force $runDir | Out-Null
$pidFile = Join-Path $runDir "vite.pid"
$logFile = Join-Path $runDir "vite.log"
$errFile = Join-Path $runDir "vite.err.log"
$python = Join-Path $root ".venv\Scripts\python.exe"
$frontendLauncher = Join-Path $root "scripts\start-frontend.py"

function Wait-Http([string]$Url, [int]$Attempts = 30, [int]$DelaySeconds = 2) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return $true }
        } catch {
            # The service is still starting.
        }
        Start-Sleep -Seconds $DelaySeconds
    }
    return $false
}

Write-Host "=== GridOps Intelligence startup ===" -ForegroundColor Cyan

# 1. Docker availability
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not on PATH."
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker daemon is not running." }
Write-Host "[OK] Docker available"

# 2. PostgreSQL
cmd /c "docker compose up -d db 2>&1"
if ($LASTEXITCODE -ne 0) { throw "Failed to start the PostgreSQL container." }
$status = ""
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    $status = (docker inspect -f '{{.State.Health.Status}}' gridops-postgres 2>$null)
    if ($status -eq "healthy") { break }
}
if ($status -ne "healthy") { throw "PostgreSQL did not become healthy." }
Write-Host "[OK] PostgreSQL healthy on host port 55432"

# 3. Migrations (host virtualenv, same database)
if (-not (Test-Path $python)) {
    throw "Python virtualenv not found at .venv. Create it and install requirements.txt first."
}
& $python -m alembic upgrade head 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Alembic migration failed." }
Write-Host "[OK] Migrations at head"

# 4. API container (rebuild so backend code changes are actually served)
$buildFlag = ""
if (-not $NoBuild) { $buildFlag = "--build " }
cmd /c "docker compose up -d ${buildFlag}api 2>&1"
if ($LASTEXITCODE -ne 0) { throw "Failed to start the API container." }

if (-not (Wait-Http "http://localhost:$ApiPort/health" -Attempts 45 -DelaySeconds 2)) {
    throw "API health check failed on port $ApiPort. Inspect: docker logs gridops-api"
}
Write-Host "[OK] API healthy at http://localhost:$ApiPort"

if (-not (Wait-Http "http://localhost:$ApiPort/health/db" -Attempts 15 -DelaySeconds 2)) {
    throw "API cannot reach PostgreSQL. Inspect: docker logs gridops-api"
}
Write-Host "[OK] API can reach PostgreSQL"

# 5. Demo data: only initialize when the asset dimension is empty.
$summary = $null
try {
    $summary = Invoke-RestMethod -Uri "http://localhost:$ApiPort/api/v1/assets/summary" -TimeoutSec 10
} catch {
    Write-Warning "Asset summary endpoint not reachable: $($_.Exception.Message)"
}
if (-not $SkipDemoInit -and ($null -eq $summary -or [int]$summary.total -eq 0)) {
    Write-Host "[..] Asset database is empty; running one-time demo initialization"
    & $python -m data_engineering.cli initialize-demo
    if ($LASTEXITCODE -ne 0) { Write-Warning "Demo initialization reported errors; review output above." }
} else {
    Write-Host "[OK] Existing data preserved (assets: $($summary.total))"
}

# 6. Frontend (persistent background process with PID and logs)
$frontendHealthy = $false
try {
    $probe = Invoke-WebRequest -Uri "http://localhost:$FrontendPort" -UseBasicParsing -TimeoutSec 3
    $frontendHealthy = $probe.StatusCode -eq 200
} catch {
    $frontendHealthy = $false
}

if (-not $frontendHealthy) {
    if (Test-Path $pidFile) {
        $oldPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
            Write-Host "[..] Stopping stale frontend process $oldPid"
            taskkill /PID $oldPid /T /F *> $null
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw "npm.cmd was not found on PATH."
    }
    & $python $frontendLauncher $logFile $errFile "127.0.0.1" "$FrontendPort" $pidFile
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to launch the Vite dev server. Inspect .run\vite.err.log."
    }
    $vitePid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    Write-Host "[..] Frontend process started (PID $vitePid, detached)"
}

if (-not (Wait-Http "http://localhost:$FrontendPort" -Attempts 30 -DelaySeconds 2)) {
    Write-Warning "Frontend did not answer on port $FrontendPort. Inspect .run\vite.log and .run\vite.err.log."
} else {
    Write-Host "[OK] Frontend healthy at http://localhost:$FrontendPort"
}

# 7. End-to-end smoke checks through the Vite proxy
foreach ($path in @("/api/v1/overview", "/api/v1/risk/summary", "/api/v1/predictive", "/api/v1/governance")) {
    try {
        $null = Invoke-RestMethod -Uri "http://localhost:$FrontendPort$path" -TimeoutSec 20
        Write-Host "[OK] proxy $path"
    } catch {
        Write-Warning "Proxy check failed for $path : $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "=== GridOps Intelligence is running ===" -ForegroundColor Green
Write-Host "Frontend: http://localhost:$FrontendPort"
Write-Host "API:      http://localhost:$ApiPort"
Write-Host "Docs:     http://localhost:$ApiPort/docs"
Write-Host ""
Write-Host "Stop:  .\scripts\stop-gridops.ps1"
Write-Host "Logs:  .run\vite.log, .run\vite.err.log, docker logs gridops-api"
exit 0
