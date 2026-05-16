# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec cho Terminal Manager - Shell.

Build:
    pyinstaller --noconfirm TerminalManager.spec

QUAN TRỌNG: Nếu chỉ dùng --onefile thường, pywinpty sẽ spawn cmd.exe nhưng
ConPTY agent (winpty-agent.exe) không tìm được DLL của nó → child process
chết ngay với STATUS_CONTROL_C_EXIT (-1073741510).

Spec này:
- collect_all('winpty')   → đóng gói đầy đủ DLLs + winpty-agent.exe
- Build dưới dạng ONEDIR (folder) — DLL nằm cạnh exe để OS load được
"""

import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

hidden_imports = ["darkdetect"]
datas = []
binaries = []

# QUAN TRỌNG: collect_all() trả về tuple THEO THỨ TỰ (datas, binaries, hiddenimports)
# — KHÔNG phải (hiddenimports, datas, binaries). Đặt sai sẽ raise TypeError.
if sys.platform == "win32":
    # pywinpty: Cython extension + winpty.dll + winpty-agent.exe
    d, b, h = collect_all("winpty")
    datas += d
    binaries += b
    hidden_imports += h
else:
    hidden_imports.append("ptyprocess")
    try:
        d, b, h = collect_all("ptyprocess")
        datas += d
        binaries += b
        hidden_imports += h
    except Exception:
        pass

# darkdetect: là module (không phải package) → bỏ qua nếu collect_data_files fail
try:
    datas += collect_data_files("darkdetect")
except Exception:
    pass


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# ONEDIR build (recommended) — folder dist/TerminalManager/ chứa exe + DLLs.
# DLLs của winpty cần nằm cạnh exe để conhost/winpty-agent load được.
# Nếu MUỐN onefile: đổi `exclude_binaries=True` thành False trong EXE() bên dưới
# và xoá block COLLECT phía dưới. Tuy nhiên onefile dễ bị STATUS_CONTROL_C_EXIT
# với pywinpty trừ khi cài thêm runtime hook để set DLL path.

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # ONEDIR mode
    name='TerminalManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # winpty DLL không nên UPX compress
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TerminalManager',
)

# Trên macOS, đóng gói folder dist thành .app bundle để launcher Finder hiểu được.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="TerminalManager.app",
        icon=None,  # đường dẫn .icns nếu có icon
        bundle_identifier="com.huthido.terminalmanager",
        info_plist={
            "CFBundleName": "Terminal Manager - Shell",
            "CFBundleDisplayName": "Terminal Manager - Shell",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
