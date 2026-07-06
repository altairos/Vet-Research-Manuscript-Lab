$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'

Push-Location $repoRoot
try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        python -m venv .venv
    }

    & $venvPython -m pip install 'setuptools>=81'
    & $venvPython -m pip install -e '.[dev]' --no-build-isolation
    & (Join-Path $PSScriptRoot 'check.ps1')
}
finally {
    Pop-Location
}

