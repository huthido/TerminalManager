"""
Quản lý danh sách lệnh yêu thích (favorites).

Dữ liệu được lưu ở favorites.json cạnh main.py, dạng:

[
  {"name": "List files", "command": "dir", "shell": "cmd"},
  {"name": "Get processes", "command": "Get-Process | sort CPU -desc | select -first 10", "shell": "powershell"}
]
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class Favorite:
    name: str
    command: str
    shell: str = "cmd"  # cmd | powershell | any


class FavoritesStore:
    def __init__(self, path: str):
        self.path = path
        self.items: List[Favorite] = []
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            # tạo sẵn vài lệnh mẫu cho lần chạy đầu
            self.items = [
                Favorite("Liệt kê file (CMD)", "dir", "cmd"),
                Favorite("Đường dẫn hiện tại (CMD)", "cd", "cmd"),
                Favorite("Liệt kê file (PS)", "Get-ChildItem", "powershell"),
                Favorite("Top 10 process theo CPU", "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10", "powershell"),
                Favorite("Ping Google", "ping -n 4 google.com", "any"),
                Favorite("IP config", "ipconfig", "cmd"),
            ]
            self.save()
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.items = [Favorite(**row) for row in raw]
        except Exception as e:
            print(f"[favorites] Lỗi đọc {self.path}: {e}")
            self.items = []

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump([asdict(it) for it in self.items], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[favorites] Lỗi ghi {self.path}: {e}")

    def add(self, fav: Favorite) -> None:
        self.items.append(fav)
        self.save()

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.items):
            del self.items[index]
            self.save()

    def update(self, index: int, fav: Favorite) -> None:
        if 0 <= index < len(self.items):
            self.items[index] = fav
            self.save()
