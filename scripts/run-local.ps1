# One-command local run: creates the venv, builds the UI, seeds demo data on first run, starts the server.
# Usage: .\scripts\run-local.ps1            (start; seeds only if the DB is empty)
#        .\scripts\run-local.ps1 -Reset     (wipe demo data and re-seed)
param([switch]$Reset, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$be = "$root\backend"; $fe = "$root\frontend"
$py = "$be\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
  python -m venv "$be\.venv"
  & $py -m pip install -q -r "$be\requirements-local.txt"
}
if (-not (Test-Path "$fe\node_modules")) { Push-Location $fe; npm install --no-audit --no-fund; Pop-Location }
if (-not (Test-Path "$fe\dist\index.html")) { Push-Location $fe; npm run build; Pop-Location }

Push-Location $be
if ($Reset) { & $py seed.py --reset }
elseif (-not (Test-Path "$be\data\cad.db")) { & $py seed.py }
Write-Host "`nOpen http://127.0.0.1:$Port  (API docs: /api/docs)`n" -ForegroundColor Cyan
& $py -m uvicorn app.main:app --host 127.0.0.1 --port $Port
Pop-Location
