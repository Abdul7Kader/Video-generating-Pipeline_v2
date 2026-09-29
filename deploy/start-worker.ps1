$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python-Umgebung fehlt: $python"
}
$env:PATH = "$(Join-Path $env:LOCALAPPDATA 'agy\bin');$env:PATH"
Set-Location -LiteralPath (Join-Path $repoRoot 'backend')
& $python -m app.worker
exit $LASTEXITCODE
