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

