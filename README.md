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
- **One shared input box** at the bottom (multi-line). All terminals show OUTPUT ONLY. The label `→ CMD #1` shows which terminal a command will be sent to. Shared history (`Ctrl+↑` / `Ctrl+↓`).
- **Password mode**: auto-detects `password:` / `passphrase:` / `[sudo] password for…` / `Mật khẩu:` prompts and switches the input to masked mode.
- **Combined log**: bottom panel shows merged output from all sessions, can be saved to `.txt`. Filter by session + search content.
- **Opens maximized** on every launch.

## Project structure

```
TerminalManager/
├── main.py              # entry point
├── main_window.py       # main window (toolbar, tabs, sidebar, combined log, input)
├── terminal_tab.py      # terminal widget for one session (output only)
├── pty_backend.py       # QProcess + TTY backends (cross-platform), shell resolver
├── ansi_renderer.py     # ANSI parser + color rendering into QPlainTextEdit
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

Use [PyInstaller](https://pyinstaller.org/) with the included `TerminalManager.spec` (which bundles `pywinpty`'s DLLs properly so the ConPTY agent can find them):

```bash
pip install pyinstaller
pyinstaller --noconfirm TerminalManager.spec
```

Output: `dist/TerminalManager/TerminalManager.exe` (Windows) or equivalent on macOS/Linux — distribute the **entire `TerminalManager/` folder**, not just the executable, because the DLLs need to sit next to it.

> Build on the target platform: `.exe` only builds on Windows, `.app` only on macOS, AppImage/binary only on Linux.

> **Why not `--onefile`?** `--onefile` extracts DLLs to a temp directory, which causes `pywinpty`'s ConPTY agent to fail with `STATUS_CONTROL_C_EXIT (-1073741510)`. The included `.spec` uses `--onedir` mode to keep DLLs alongside the executable. If you want a single-file distribution, wrap the folder with [Inno Setup](https://jrsoftware.org/isinfo.php) or [NSIS](https://nsis.sourceforge.io/) afterwards.

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

- **Not a full terminal emulator**: no alternate screen buffer, no absolute cursor positioning (CSI H/f). Full-screen TUI apps like `vim`, `htop`, `nano` **still work** (keys are forwarded), but the layout may render incorrectly / flicker. REPLs / ssh / colored output work well.
- Mouse reporting isn't supported.
- Scrollback is capped at 5000 lines per tab.

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
