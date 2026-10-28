"""Desktop entry point used by the Windows PyInstaller package."""

from __future__ import annotations

import os
import threading
import webbrowser

import uvicorn

from app.main import app


def open_browser() -> None:
    webbrowser.open(f"http://127.0.0.1:{PORT}")


PORT = int(os.getenv("DAILY_MANAGER_PORT", "8000"))


if __name__ == "__main__":
    if os.getenv("DAILY_MANAGER_NO_BROWSER") != "1":
        threading.Timer(1.5, open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
