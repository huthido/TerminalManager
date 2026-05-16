"""
Theme handling: light / dark / system.

`apply_theme(app, name)` đổi QPalette + style cho QApplication.
Với name="system", trên Windows sẽ đọc registry để xem app sáng hay tối,
và áp dụng theme tương ứng. Trên platform khác mặc định là light.
"""

from __future__ import annotations

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication


THEMES = ("system", "light", "dark")


def _windows_uses_dark_mode() -> bool:
    """Đọc HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        # AppsUseLightTheme = 0 → dark mode
        return val == 0
    except Exception:
        return False


def _system_uses_dark_mode() -> bool:
    """
    Detect dark mode cross-platform.
    Ưu tiên `darkdetect` (cross-platform), fallback từng platform nếu thiếu lib.
    """
    try:
        import darkdetect
        result = darkdetect.isDark()
        if result is not None:
            return bool(result)
    except Exception:
        pass
    # Fallback per-platform
    if sys.platform == "win32":
        return _windows_uses_dark_mode()
    # Linux/macOS without darkdetect → default light
    return False


def _build_dark_palette() -> QPalette:
    p = QPalette()
    bg = QColor(45, 45, 48)
    base = QColor(30, 30, 30)
    alt = QColor(53, 53, 55)
    text = QColor(220, 220, 220)
    disabled_text = QColor(127, 127, 127)
    highlight = QColor(38, 110, 184)

    p.setColor(QPalette.Window, bg)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, alt)
    p.setColor(QPalette.ToolTipBase, base)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, bg)
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.BrightText, Qt.red)
    p.setColor(QPalette.Link, QColor(68, 158, 244))
    p.setColor(QPalette.Highlight, highlight)
    p.setColor(QPalette.HighlightedText, Qt.white)

    p.setColor(QPalette.Disabled, QPalette.Text, disabled_text)
    p.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)
    p.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)
    return p


def resolve_theme(name: str) -> str:
    """Đổi 'system' thành 'light' hoặc 'dark' theo OS (cross-platform)."""
    if name == "system":
        return "dark" if _system_uses_dark_mode() else "light"
    return name if name in ("light", "dark") else "light"


def apply_theme(app: QApplication, name: str) -> None:
    """Áp dụng theme vào QApplication. Có thể gọi bất kỳ lúc nào."""
    app.setStyle("Fusion")
    effective = resolve_theme(name)
    if effective == "dark":
        app.setPalette(_build_dark_palette())
    else:
        # light: dùng palette mặc định của Fusion (light)
        app.setPalette(app.style().standardPalette())
