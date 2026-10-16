"""Windows 실행 패키지용 로컬 서버 시작점."""

from __future__ import annotations

import threading
import webbrowser

import uvicorn


def open_browser() -> None:
    webbrowser.open("http://127.0.0.1:8765/projects")


def main() -> None:
    threading.Timer(1.0, open_browser).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
