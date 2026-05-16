# Terminal Manager - Shell

> 🇻🇳 Phiên bản tiếng Việt: [README.vi.md](README.vi.md)

A **cross-platform** (Windows / macOS / Linux) application for managing multiple shell sessions in a single window, written in **Python + PyQt5**.

**Repository:** https://github.com/huthido/TerminalManager

| Platform | Shells supported | TTY backend |
|----------|------------------|-------------|
| Windows  | CMD, PowerShell, WSL, Git Bash | `pywinpty` (ConPTY) |
| macOS    | Bash, Zsh, Fish, sh, PowerShell Core (if installed) | `ptyprocess` |
| Linux    | Bash, Zsh, Fish, sh, PowerShell Core (if installed) | `ptyprocess` |

## Features

- **Multiple shell types** per platform (see [Shells](#shells)).
- **Two shell backends**:
  - **TTY** (`pywinpty` on Windows / `ptyprocess` on Unix) — real TTY, supports `ssh`, `vim`, Python REPL, `top`/`htop`, etc.
  - **QProcess** (Qt's default) — pipe stdin/stdout, simple but no TTY (shows *"Pseudo-terminal will not be allocated…"* for ssh).
  - Auto fallback if `pywinpty`/`ptyprocess` isn't installed.
- **Full TUI support** (via [`pyte`](https://pyte.readthedocs.io/)): runs `vim`, `htop`, `nano`, `less`, `mc` and other full-screen TUI applications natively. Includes alternate screen buffer, absolute cursor positioning, scrollback, and raw key forwarding (arrow keys, F-keys, Ctrl+letters). Click into a terminal to grab focus, then keys go directly to the running TUI.
- **Unicode IME input**: type Vietnamese (Telex/VNI/Unikey), Chinese (Pinyin), Japanese (IME), Korean, emoji, … directly into the terminal — the OS composition popup appears next to the cursor.
- **Auto-hide shared input bar in TUI mode**: when `pyte` is installed, the bottom input bar is hidden by default so the terminal grid uses the full height. Toggle it with **Ctrl+I** or the **⌨ Input bar** toolbar button when you need line-based input (broadcast, multi-line paste, etc.).
- **Full ANSI color rendering** (16 colors + 256-color + 24-bit truecolor), bold/italic/underline, carriage-return overwrite, backspace, erase-line/erase-display.
- **Flexible layouts** (toolbar **▦ Layout**): Tabs (one terminal at a time) or **R × C Grid** (1×N row, N×1 column, or arbitrary rectangle/square). When the number of windows exceeds R×C, they're grouped into multiple **Pages** in an inner QTabWidget. Drag splitters between cells to resize; **↔ Equalize cells** menu resets the proportions.
- **Tab renaming**: double-click the tab title (or right-click → Rename) — the process keeps running.
- **Session restore**: tab list + custom titles + layout are saved on close; restored on next launch (can be disabled in Settings).
- **Themes**: Light / Dark / System (via `darkdetect`, cross-platform).
- **Languages**: English / Vietnamese (restart required for full UI string update).
- **Drag-and-drop terminals**: drag a terminal's status bar onto another grid cell to **swap positions**, or onto a page tab to move it to that page.
- **Empty cells have a menu** to open a new terminal right at that position.
- **Favorites sidebar**: save / edit / delete / run, with a **search box** and shell filter. **🔍 Scan** auto-detects installed CLI tools (git, python, docker, ...) and adds them as favorites in bulk.
- **Click a favorite** → command loads into the input box for editing; **double-click** → run immediately.
- **Run script** (`Ctrl+R`): pick a `.bat` / `.cmd` / `.ps1` file → auto-selects the right shell, asks whether to run in current tab or open a new one. For `.ps1`, automatically sets `Set-ExecutionPolicy -Scope Process Bypass`.
- **Open folder** (`Ctrl+O`): pick a folder from the dialog → auto `cd` into the active terminal (builds the right command per shell).
- **Active terminal**: only one terminal is "active" at a time; all commands (favorites, run script, shared input) apply to the active one. Clicking on a terminal makes it active + moves focus back to the input box.
- **One shared input box** at the bottom (multi-line) — for line-based shells. All terminals show OUTPUT ONLY. The label `→ CMD #1` shows which terminal a command will be sent to. Shared history (`Ctrl+↑` / `Ctrl+↓`). Auto-hidden in TUI mode; toggle with **Ctrl+I**.
- **Password mode**: auto-detects `password:` / `passphrase:` / `[sudo] password for…` / `Mật khẩu:` prompts and switches the input to masked mode. (In TUI mode the TTY shell handles echo-off natively, so masking is delegated to the shell.)
- **Combined log**: bottom panel shows merged output from all sessions, can be saved to `.txt`. Filter by session + search content. **Buffers per-line** so TUI keystrokes don't spam the log — only complete lines are logged.
- **Opens maximized** on every launch.

## Project structure

```
TerminalManager/
├── main.py              # entry point
├── main_window.py       # main window (toolbar, tabs, sidebar, combined log, input)
├── terminal_tab.py      # terminal widget for one session (output only)
├── terminal_view.py     # full TUI emulator widget (pyte-based)
├── pty_backend.py       # QProcess + TTY backends (cross-platform), shell resolver
├── ansi_renderer.py     # legacy ANSI renderer (fallback when pyte not installed)
├── favorites.py         # read/write favorites.json
├── tool_scanner.py      # CLI tools registry + scanner
├── settings.py          # AppSettings (theme, language, session, backend, layout)
├── theme.py             # light/dark/system palette (darkdetect)
├── i18n.py              # UI translations (vi / en)
├── favorites.json       # auto-generated on first run
├── settings.json        # auto-generated on first close
├── TerminalManager.spec # PyInstaller build spec
├── requirements.txt
├── README.md            # English
└── README.vi.md         # Vietnamese
```

## Installation

Requires: **Python 3.9+** on Windows 10/11, macOS 11+, or any Linux distro with Python.

`requirements.txt` uses PEP 508 markers, so `pip install -r requirements.txt` automatically picks the right dependency per platform (`pywinpty` for Windows, `ptyprocess` for macOS/Linux).

### Clone the repository

```bash
git clone https://github.com/huthido/TerminalManager.git
cd TerminalManager
```

### Windows

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Linux (Debian/Ubuntu)

```bash
sudo apt-get install -y python3-pyqt5 python3-venv
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install ptyprocess darkdetect
python main.py
```

> **Note**: on Linux, `--system-site-packages` lets the venv reuse the system PyQt5; or use `pip install PyQt5` (requires Qt5 dev headers + build tools).

> **Note**: if `pywinpty` / `ptyprocess` cannot be installed, the app still runs in QProcess mode (no TTY, ssh will warn "Pseudo-terminal will not be allocated...").

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+T` | New CMD/Bash tab (default per platform) |
| `Ctrl+Shift+T` | New PowerShell/Zsh tab |
| `Ctrl+R` | Run a script file (.bat/.cmd/.ps1) |
| `Ctrl+O` | Pick a folder → `cd` into the active terminal |
| `Ctrl+I` | Toggle the shared input bar (auto-hidden in TUI mode) |
| `Ctrl+W` | Close current terminal |
| `Ctrl+L` | Clear combined log |
| `Ctrl+,` | Open Settings (theme / language / backend / layout) |
| `Ctrl+=` | Equalize grid cells |
| `Ctrl+Shift+P` | Toggle password mode |
| `Enter` | Send command in input box |
| `Shift+Enter` | New line (multi-line input) |
| `Ctrl+↑` / `Ctrl+↓` | Browse command history |
| Double-click tab | Rename tab |
| **×** button on status bar | Close current terminal |

## Building a standalone executable

All platforms use the same [PyInstaller](https://pyinstaller.org/) spec file (`TerminalManager.spec`), which:
- Bundles `pywinpty` DLLs (Windows) or `ptyprocess` data (Unix) so the TTY backend works
- Includes `darkdetect`, `pyte`, `PyQt5` and their data files
- Uses **onedir** mode (`--onedir`) — a folder containing the executable + dependencies. Onefile mode is **avoided** because `pywinpty`'s ConPTY agent fails (`STATUS_CONTROL_C_EXIT`) when DLLs are unpacked to a temp directory
- On macOS, additionally produces a `.app` bundle

**Build on the target platform.** PyInstaller can't cross-compile: `.exe` only builds on Windows, `.app` only on macOS, ELF binaries only on Linux.

### Prerequisites

```bash
pip install pyinstaller
```

### Windows

```bat
rem In an activated virtual env, from the project root:
pyinstaller --noconfirm TerminalManager.spec

rem Output: dist\TerminalManager\TerminalManager.exe (and required DLLs)
rem Run it:
dist\TerminalManager\TerminalManager.exe
```

**Distribute** the entire `dist\TerminalManager\` folder (zip it). For a single-file installer, wrap the folder with:
- [Inno Setup](https://jrsoftware.org/isinfo.php) — friendly installer wizard, recommended
- [NSIS](https://nsis.sourceforge.io/) — lightweight, scriptable

### macOS

```bash
# In an activated virtual env, from the project root:
pyinstaller --noconfirm TerminalManager.spec

# Output:
#   dist/TerminalManager/                  ← onedir folder (binary + libs)
#   dist/TerminalManager.app/              ← macOS .app bundle (recommended)
# Run the .app:
open dist/TerminalManager.app
```

**Distribute** the `.app` bundle. Options:
- **Zip** `TerminalManager.app` and ship as-is
- **DMG** disk image: `hdiutil create -volname TerminalManager -srcfolder dist/TerminalManager.app TerminalManager.dmg`
- For App Store / Gatekeeper: codesign + notarize the bundle (`codesign --sign "Developer ID Application: …" dist/TerminalManager.app`, then `xcrun notarytool submit`).

If you have an icon, set `icon="/path/to/icon.icns"` in `TerminalManager.spec` inside the `BUNDLE(...)` block.

### Linux

```bash
# In an activated virtual env, from the project root:
pyinstaller --noconfirm TerminalManager.spec

# Output: dist/TerminalManager/   (folder with `TerminalManager` ELF binary)
./dist/TerminalManager/TerminalManager
```

**Distribute** options:
- **Tar.gz**: `tar -czvf TerminalManager-linux.tar.gz -C dist TerminalManager`
- **AppImage**: use [linuxdeployqt](https://github.com/probonopd/linuxdeployqt) or [appimagetool](https://appimage.github.io/appimagetool/)
- **`.deb`**: use `dh_make` + `dpkg-buildpackage`, or [`fpm`](https://github.com/jordansissel/fpm): `fpm -s dir -t deb -n terminal-manager -v 1.0.0 dist/TerminalManager/=/opt/terminal-manager/`
- **`.rpm`**: similar with `fpm -t rpm …`
- **Snap / Flatpak**: write a `snapcraft.yaml` / Flatpak manifest pointing to the binary

> **Note**: PyQt5 binary wheels include Qt platform plugins (`libqxcb`). On minimal/headless Linux distros, ensure system libraries like `libxcb-cursor0`, `libxkbcommon-x11-0`, `libxcb-render-util0` are installed — otherwise the bundled app may fail to start with `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`.

### Why `onedir` instead of `onefile`?

`--onefile` extracts everything to a temp directory at runtime, which causes `pywinpty`'s ConPTY agent (`winpty-agent.exe`) to fail with `STATUS_CONTROL_C_EXIT (-1073741510)` because it can't find its sibling DLLs. The included spec uses `--onedir` so DLLs sit next to the executable. To still ship a single file, wrap the onedir folder with an installer (Inno Setup / DMG / AppImage).

## Shells

The app auto-detects available shells and shows matching buttons on the toolbar.

### Windows
| Shell | Requires | Toolbar button |
|-------|----------|----------------|
| CMD | Built-in | `+ CMD` |
| PowerShell | `powershell.exe` | `+ PowerShell` |
| WSL | `wsl --install` | `+ WSL` |
| Git Bash | Git for Windows | `+ Git Bash` |

### macOS / Linux
| Shell | Requires | Toolbar button |
|-------|----------|----------------|
| Bash | `/bin/bash` | `+ Bash` |
| Zsh | `which zsh` (built-in on macOS) | `+ Zsh` |
| Fish | `which fish` | `+ Fish` |
| sh | `/bin/sh` (POSIX) | `+ sh` |
| PowerShell Core | `pwsh` | `+ PowerShell` (if installed) |

Shell buttons are **disabled** if the corresponding binary isn't found.

## Known limitations

- Mouse reporting in TUI apps (e.g. `htop` mouse clicks) isn't forwarded yet — keyboard navigation only.
- Scrollback is 5000 lines per tab.
- If `pyte` isn't installed, the app falls back to the legacy ANSI renderer (scroll-mode only, no TUI).

## Customization tips

- Edit the default commands list: tweak `FavoritesStore.load()` in `favorites.py`.
- Change colors/background: edit `setStyleSheet(...)` in `terminal_tab.py` (output area) and `main_window.py`.
- Change font: `QFont("Consolas", 10)` in the UI files.
- Add a CLI tool to the scanner: edit `_TOOLS` in `tool_scanner.py`.

## Contributing

Issues and pull requests welcome at https://github.com/huthido/TerminalManager.

When reporting an issue, please include:
- OS + Python version
- Output of `pip list | grep -i -E "pyqt|winpty|ptyprocess|darkdetect"`
- Contents of `startup.log` (generated next to `main.py` on each launch)
