param(
    [string]$DataDirectory = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "개발용 .venv를 찾을 수 없습니다. README의 설치 절차를 먼저 실행하세요."
}

if ($DataDirectory) {
    $env:BOM_APP_DATA_DIR = $DataDirectory
}

Push-Location $projectRoot
try {
    & $pythonPath -m app.migrate
    if ($LASTEXITCODE -ne 0) {
        throw "데이터베이스 마이그레이션에 실패했습니다. 오류를 확인하고 앱을 시작하지 않았습니다."
    }
    Start-Process "http://127.0.0.1:8765/projects"
    & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8765
}
finally {
    Pop-Location
}
