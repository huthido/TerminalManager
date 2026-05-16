"""
Terminal Manager - entry point.

Chạy:
    python main.py

Yêu cầu: Windows + Python 3.9+ + PyQt5 (xem requirements.txt).

Khi gặp lỗi không hiện ra, kiểm tra file `startup.log` cạnh main.py
— mọi bước khởi động + exception đều được ghi vào đó.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime


HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "startup.log")


def log(msg: str) -> None:
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def main() -> int:
    # Reset log mỗi lần chạy
    try:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write(f"=== Terminal Manager startup {datetime.now()} ===\n")
    except Exception:
        pass

    log("Importing PyQt5...")
    from PyQt5.QtWidgets import QApplication, QMessageBox

    log("Creating QApplication...")
    app = QApplication(sys.argv)
    app.setApplicationName("Terminal Manager")

    try:
        log("Importing app modules...")
        from settings import AppSettings
        from i18n import set_language
        import theme as app_theme
        from main_window import MainWindow, SETTINGS_PATH

        log(f"Loading settings from {SETTINGS_PATH}...")
        settings = AppSettings.load(SETTINGS_PATH)
        log(f"Settings: theme={settings.theme}, language={settings.language}, "
            f"backend={settings.backend}, layout_mode={settings.layout_mode}, "
            f"last_tabs={len(settings.last_tabs)} items")

        log("Applying language...")
        set_language(settings.language)

        log("Applying theme...")
        app_theme.apply_theme(app, settings.theme)

        log("Creating MainWindow...")
        win = MainWindow(settings=settings)

        log("Showing window (maximized)...")
        win.showMaximized()
        log("Window shown — entering event loop")
    except Exception:
        tb = traceback.format_exc()
        log("STARTUP ERROR:\n" + tb)
        try:
            QMessageBox.critical(
                None,
                "Lỗi khởi động Terminal Manager",
                f"App không khởi động được:\n\n{tb}\n\nXem chi tiết: {LOG_PATH}",
            )
        except Exception:
            pass
        return 1

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
