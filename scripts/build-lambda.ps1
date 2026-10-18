# Stage the backend for `sam build` (no venv, tests, local DB or demo files in the bundle).
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$src = Join-Path $root 'backend'
$out = Join-Path $root 'infra\build\lambda'

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force $out | Out-Null
Copy-Item "$src\app" "$out\app" -Recurse
Get-ChildItem "$out\app" -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
Copy-Item "$src\lambda_handler.py", "$src\requirements.txt" $out
Write-Host "Lambda bundle staged at $out"
Write-Host "Next:  cd infra ; sam build --use-container ; sam deploy --guided"
