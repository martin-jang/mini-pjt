# Legacy2Next 실행 스크립트 (PowerShell 판, run.sh 와 같은 동작): 환경 확인 → API 서버 기동 (127.0.0.1:8000)
# 시연 전 체크리스트를 겸합니다. 하나라도 실패하면 이유를 보여주고 멈춥니다.
# 실행: powershell -ExecutionPolicy Bypass -File .\run.ps1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
[Console]::OutputEncoding = [Text.Encoding]::UTF8   # 한글 출력 깨짐 방지
$env:PYTHONIOENCODING = "utf-8"

function Stop-WithError([string]$msg) {
    Write-Host "❌ $msg" -ForegroundColor Red
    exit 1
}

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Stop-WithError "가상환경(.venv)이 없습니다. README 실행 방법 1) 참고" }
Write-Host "Python: $(& $py --version)"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Stop-WithError "Node.js 가 필요합니다 (20 이상)" }
Write-Host "Node:   $(node --version)"

if (-not (Test-Path ".env")) { Stop-WithError ".env 가 없습니다 (.env.example 참고)" }
if (-not (Test-Path "templates\tobe-app\node_modules")) {
    Stop-WithError "템플릿 의존성이 없습니다: cd templates\tobe-app; npm install"
}
if (-not (Test-Path "data\snapshots")) {
    Write-Host "⚠ 스냅샷이 없습니다. 분석 요청 시 실제 크롤링이 필요합니다." -ForegroundColor Yellow
}
if (Select-String -Path "config\settings.yaml" -Pattern "snapshot_mode: replay" -Quiet) {
    Write-Host "모드: 스냅샷 재생 (시연·평가 기본)"
} else {
    Write-Host "모드: 실제 크롤링"
}

Write-Host "UI: http://127.0.0.1:8000/   API: POST http://127.0.0.1:8000/query"
& $py app.py
exit $LASTEXITCODE
