$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'

# Kill any stale Streamlit/Python processes that may hold cached modules.
Write-Host "Stopping any existing Python processes..." -ForegroundColor Cyan
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

# Clear __pycache__ directories to prevent stale .pyc loads.
Write-Host "Clearing __pycache__ directories..." -ForegroundColor Cyan
Get-ChildItem -Path (Join-Path $repoRoot 'src') -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path (Join-Path $repoRoot 'tests') -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Push-Location $repoRoot
try {
    Write-Host "Starting Streamlit..." -ForegroundColor Green
    & $python -m streamlit run src/vet_manuscript_lab/ui/app.py
}
finally {
    Pop-Location
}
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'

Push-Location $repoRoot
try {
    & $python -m streamlit run src/vet_manuscript_lab/ui/app.py
}
finally {
    Pop-Location
}

