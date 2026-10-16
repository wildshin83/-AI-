$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "개발용 .venv를 찾을 수 없습니다."
}

Push-Location $projectRoot
try {
    & $pythonPath -m pip install -e ".[package]"
    & $pythonPath -m PyInstaller --noconfirm --clean --onedir --name BOM관리서비스 --collect-all openpyxl --add-data "참고자료;참고자료" app\launcher.py
    Write-Host "빌드 완료: dist\BOM관리서비스"
}
finally {
    Pop-Location
}
