$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }

Push-Location $repoRoot
try {
    & $python -m compileall -q src tests migrations
    & $python -m ruff check src tests migrations
    & $python -m ruff format --check src tests migrations
    & $python -m mypy src
    & $python -m pytest
}
finally {
    Pop-Location
}

