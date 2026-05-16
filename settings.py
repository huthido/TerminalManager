"""
Cài đặt app + session (danh sách tab đang mở).

Tất cả lưu vào settings.json cạnh main.py, ví dụ:

{
  "theme": "system",           // system | light | dark
  "language": "vi",            // vi | en
  "restore_session": true,
  "geometry": {"w": 1280, "h": 800},
  "last_tabs": [
    {"shell": "cmd", "title": "CMD #1"},
    {"shell": "powershell", "title": "Build server"}
  ]
}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from typing import List


@dataclass
class TabState:
    shell: str = "cmd"        # cmd | powershell
    title: str = ""           # tên hiển thị (có thể đã được người dùng đổi)


@dataclass
class Geometry:
    w: int = 1280
    h: int = 800


@dataclass
class AppSettings:
    theme: str = "system"               # system | light | dark
    language: str = "vi"                # vi | en
    restore_session: bool = True
    backend: str = "auto"               # auto | conpty | qprocess
    layout_mode: str = "tabs"           # tabs | cols:N | rows:N | grid:RxC
    geometry: Geometry = field(default_factory=Geometry)
    last_tabs: List[TabState] = field(default_factory=list)

    # ---------- IO ----------
    @classmethod
    def load(cls, path: str) -> "AppSettings":
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[settings] Lỗi đọc {path}: {e}")
            return cls()

        tabs_raw = data.pop("last_tabs", []) or []
        geo_raw = data.pop("geometry", None)
        try:
            tabs = [TabState(**row) for row in tabs_raw if isinstance(row, dict)]
        except Exception:
            tabs = []
        try:
            geo = Geometry(**(geo_raw or {}))
        except Exception:
            geo = Geometry()
        # lọc các key chưa biết để không vỡ
        known = {f.name for f in cls.__dataclass_fields__.values()}
        data = {k: v for k, v in data.items() if k in known and k not in ("last_tabs", "geometry")}
        try:
            return cls(last_tabs=tabs, geometry=geo, **data)
        except TypeError as e:
            print(f"[settings] {e}")
            return cls()

    def save(self, path: str) -> None:
        try:
            payload = {
                "theme": self.theme,
                "language": self.language,
                "restore_session": self.restore_session,
                "backend": self.backend,
                "layout_mode": self.layout_mode,
                "geometry": asdict(self.geometry),
                "last_tabs": [asdict(t) for t in self.last_tabs],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[settings] Lỗi ghi {path}: {e}")
