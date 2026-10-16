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
    & $pythonPath -m alembic upgrade head
    Start-Process "http://127.0.0.1:8765/projects"
    & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8765
}
finally {
    Pop-Location
}
