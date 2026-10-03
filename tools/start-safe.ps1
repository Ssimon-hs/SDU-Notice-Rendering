# =============================================================
#  一键山大 · 安全启动器（v0.5.1）
#  设计原则：只启动本程序，绝不强杀、绝不关闭任何其它进程。
#  - 自动探测空闲端口（8765 起），端口被占用就递增换一个；
#  - 只拉起本项目的 uvicorn 后端；
#  - 后端就绪后打开默认浏览器访问。
# =============================================================
param(
  [int]$BasePort = 8765
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Root          # yijian-sdu 目录
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"

# ---------- 1. 探测空闲端口（从 BasePort 起递增）----------
function Get-FreePort([int]$start) {
  for ($p = $start; $p -lt ($start + 50); $p++) {
    $inUse = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if (-not $inUse) { return $p }
  }
  throw "从 $start 起 50 个端口均被占用，无法启动。"
}

Write-Host ""
Write-Host "============================================"
Write-Host "    YIJIAN SDU Launcher (safe, v0.5.1)"
Write-Host "============================================"
Write-Host ""

# ---------- 2. 环境检查 ----------
if (-not (Test-Path -LiteralPath $Python)) {
  Write-Host "[ERROR] 未找到虚拟环境 .venv，请先运行一次安装流程。" -ForegroundColor Red
  exit 1
}
& $Python -c "import uvicorn, fastapi, bs4, requests" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "[ERROR] 依赖不完整，请先运行一次安装流程。" -ForegroundColor Red
  exit 1
}

# ---------- 3. 探测空闲端口（绝不强杀其它进程）----------
$ApiPort = Get-FreePort $BasePort
Write-Host "[1/3] 端口探测完成：API 端口 = $ApiPort（空闲，未改动任何其它程序）" -ForegroundColor Cyan

# ---------- 4. 后端静态托管 dist ----------
$Env:YIJIAN_API_PORT = "$ApiPort"

Write-Host "[2/3] 启动后端（uvicorn :$ApiPort）..."
$serverLog = Join-Path $Root "server.log"
if (Test-Path -LiteralPath $serverLog) { Remove-Item -LiteralPath $serverLog -Force }
Start-Process -FilePath $Python -ArgumentList @("-m","uvicorn","server.main:app","--host","127.0.0.1","--port","$ApiPort") -WorkingDirectory $Root -WindowStyle Minimized -RedirectStandardOutput $serverLog -RedirectStandardError "$serverLog.err"

# ---------- 5. 等待后端就绪 ----------
Write-Host "    等待后端就绪（最多 60 秒）..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 2
  try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/api/health" -TimeoutSec 3
    if ($h.status -eq "ok") { $ready = $true; break }
  } catch { }
}
if (-not $ready) {
  Write-Host "[FAIL] 后端未能启动。server.log 内容如下：" -ForegroundColor Red
  if (Test-Path -LiteralPath $serverLog) { Get-Content -LiteralPath $serverLog -Raw }
  exit 1
}

# ---------- 6. 打开浏览器 ----------
Write-Host "[3/3] 后端就绪，正在打开浏览器 ..." -ForegroundColor Green
Start-Process "http://127.0.0.1:$ApiPort"
Write-Host ""
Write-Host "============================================"
Write-Host "  一键山大正在运行：http://127.0.0.1:$ApiPort"
Write-Host "  本次未关闭、未强杀任何其它程序。"
Write-Host "  停止方法：关闭最小化的后端窗口，或运行 停止一键山大.bat"
Write-Host "============================================"
Write-Host ""