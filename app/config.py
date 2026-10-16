"""로컬 실행 환경의 경로와 기본 설정을 한곳에서 관리한다."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "BomManagementService"


@dataclass(frozen=True)
class AppPaths:
    """앱 데이터와 사용자 파일을 저장하는 로컬 경로 모음."""

    root: Path
    database: Path
    files: Path
    exports: Path
    backups: Path
    logs: Path

    @classmethod
    def from_environment(cls) -> AppPaths:
        configured_root = os.getenv("BOM_APP_DATA_DIR")
        if configured_root:
            root = Path(configured_root).expanduser()
        else:
            local_app_data = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            root = local_app_data / APP_NAME

        return cls(
            root=root,
            database=root / "data" / "bom_service.sqlite3",
            files=root / "files",
            exports=root / "exports",
            backups=root / "backups",
            logs=root / "logs",
        )

    def ensure_directories(self) -> None:
        """데이터 저장에 필요한 디렉터리를 생성한다."""

        for directory in (
            self.database.parent,
            self.files,
            self.exports,
            self.backups,
            self.logs,
        ):
            directory.mkdir(parents=True, exist_ok=True)


paths = AppPaths.from_environment()


def reference_material_path(file_name: str) -> Path:
    """소스 실행·Windows 패키지 모두에서 번들 참고자료 경로를 반환한다."""

    application_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return application_root / "참고자료" / file_name
