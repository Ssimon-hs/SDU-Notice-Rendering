param(
  [switch]$Install
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if ($Install -or -not (Test-Path "node_modules")) {
  Write-Host "Installing web dependencies..."
  npm install
}

if ($Install -or -not (Test-Path ".venv")) {
  Write-Host "Creating Python environment..."
  python -m venv .venv
  & ".\.venv\Scripts\python.exe" -m pip install -r server\requirements.txt
}

$api = Start-Process `
  -FilePath ".\.venv\Scripts\python.exe" `
  -ArgumentList "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", "8765" `
  -PassThru

try {
  Write-Host "Starting 一键山大 at http://127.0.0.1:5173"
  Start-Process "http://127.0.0.1:5173"
  npm run dev
}
finally {
  if (-not $api.HasExited) {
    Stop-Process -Id $api.Id
  }
}