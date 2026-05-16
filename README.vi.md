# Terminal Manager - Shell

> 🇬🇧 English version: [README.md](README.md)

Ứng dụng **cross-platform** (Windows / macOS / Linux) quản lý nhiều phiên shell trong một cửa sổ duy nhất, viết bằng **Python + PyQt5**.

**Repository:** https://github.com/huthido/TerminalManager

| Platform | Shells hỗ trợ | TTY backend |
|----------|----------------|-------------|
| Windows  | CMD, PowerShell, WSL, Git Bash | `pywinpty` (ConPTY) |
| macOS    | Bash, Zsh, Fish, sh, PowerShell Core (nếu cài) | `ptyprocess` |
| Linux    | Bash, Zsh, Fish, sh, PowerShell Core (nếu cài) | `ptyprocess` |

## Tính năng chính

- **Nhiều loại shell** theo platform (xem mục [Shells](#shells)).
- **2 backend** chạy shell con:
  - **TTY** (`pywinpty` trên Windows / `ptyprocess` trên Unix) — TTY thật, chạy được `ssh`, `vim`, REPL Python, `top`/`htop`…
  - **QProcess** (mặc định của Qt) — pipe stdin/stdout, đơn giản nhưng không có TTY (sẽ hiện cảnh báo *"Pseudo-terminal will not be allocated…"*).
  - Auto fallback nếu pywinpty/ptyprocess chưa cài.
- **Hỗ trợ TUI đầy đủ** (qua [`pyte`](https://pyte.readthedocs.io/)): chạy được `vim`, `htop`, `nano`, `less`, `mc` và mọi TUI full-screen khác. Có alternate screen buffer, cursor positioning tuyệt đối, scrollback, raw key forwarding (arrow keys, F-keys, Ctrl+letters). Click vào terminal để focus → phím gõ đi thẳng tới TUI đang chạy.
- **Gõ Unicode qua IME**: gõ tiếng Việt (Telex/VNI/Unikey), tiếng Trung (Pinyin), tiếng Nhật, tiếng Hàn, emoji… trực tiếp vào terminal — popup composition của OS hiện sát con trỏ.
- **Tự ẩn ô nhập khi TUI mode**: nếu `pyte` đã cài, ô nhập dưới đáy app ẩn mặc định để khu vực terminal chiếm hết chiều cao. Toggle bằng **Ctrl+I** hoặc nút **⌨ Ô nhập** trên toolbar khi cần gõ lệnh line-based (multi-line paste, ...).
- **Render màu ANSI** đầy đủ (16 màu + 256-color + truecolor 24-bit), bold/italic/underline, carriage-return overwrite, backspace, erase-line/erase-display.
- **Bố cục linh hoạt** (toolbar **▦ Bố cục**): Tabs (1 terminal/lần) hoặc **Lưới R × C** (1×N một hàng, N×1 một cột, hoặc lưới chữ nhật/vuông tuỳ ý). Khi số cửa sổ vượt R×C → tự gom thành nhiều **Trang** trong QTabWidget bên trong. Kéo splitter giữa các cell để chỉnh tỉ lệ; menu **↔ Cân đều** để reset.
- **Đổi tên tab**: double-click tiêu đề tab (hoặc chuột phải → Đổi tên) — process vẫn chạy.
- **Khôi phục session**: tự lưu danh sách tab + tên tuỳ chỉnh + bố cục khi đóng app; mở lại sẽ phục hồi (có thể tắt trong Cài đặt).
- **Theme** sáng / tối / theo hệ thống (qua `darkdetect`, cross-platform).
- **Ngôn ngữ**: Tiếng Việt / English (đổi xong khởi động lại app để áp dụng cho mọi UI string).
- **Drag-and-drop terminal**: kéo status bar của terminal sang ô khác trong lưới để **đổi vị trí** (swap), hoặc kéo lên page tab để chuyển trang.
- **Cell trống có menu** mở terminal mới ngay tại vị trí đó.
- Sidebar **Lệnh yêu thích**: lưu / sửa / xoá / chạy, có ô **tìm kiếm** và lọc theo shell. **🔍 Quét** tự phát hiện CLI tools đã cài (git, python, docker, ...) và thêm hàng loạt làm favorites.
- **Click favorite** → command tự load vào ô nhập để edit; **double-click** → chạy ngay.
- **Chạy script** (`Ctrl+R`): chọn file `.bat` / `.cmd` / `.ps1` → tự chọn shell phù hợp, hỏi chạy ở tab hiện tại hay mở tab mới. Với `.ps1` tự bật `Set-ExecutionPolicy -Scope Process Bypass`.
- **Mở thư mục** (`Ctrl+O`): chọn folder từ dialog → tự `cd` vào terminal active (build command đúng theo shell).
- **Active terminal**: chỉ 1 terminal active tại 1 thời điểm; tất cả lệnh (favorites, run script, ô input chung) đều áp dụng cho terminal active. Click vào terminal → tự thành active + focus chuyển về ô nhập.
- **Một ô nhập lệnh dùng chung** ở dưới đáy app (đa dòng) — dùng cho shell line-based. Tất cả terminal CHỈ hiển thị output, không có ô nhập riêng. Label `→ CMD #1` cho biết command sẽ đi tới terminal nào. Lịch sử lệnh dùng chung (`Ctrl+↑` / `Ctrl+↓`). Tự ẩn khi TUI mode; toggle bằng **Ctrl+I**.
- **Password mode**: tự detect prompt `password:` / `passphrase:` / `[sudo] password for…` / `Mật khẩu:` và chuyển ô nhập sang masked input. (Khi TUI mode, TTY shell tự xử lý echo-off khi đọc password nên app uỷ thác việc che ký tự cho shell.)
- **Log gộp**: panel dưới hiển thị output gộp từ mọi phiên, có thể lưu ra `.txt`. Lọc theo phiên + tìm kiếm nội dung. **Gom theo dòng** nên gõ phím trong TUI không spam log — chỉ log line hoàn chỉnh.
- **Mở maximized** mỗi lần khởi động.

## Cấu trúc thư mục

```
TerminalManager/
├── main.py              # entry point
├── main_window.py       # cửa sổ chính (toolbar, tabs, sidebar, log gộp, input)
├── terminal_tab.py      # widget terminal cho 1 phiên (output only)
├── terminal_view.py     # widget TUI emulator đầy đủ (pyte-based)
├── pty_backend.py       # QProcess + TTY backends (cross-platform), shell resolver
├── ansi_renderer.py     # ANSI renderer cũ (fallback khi pyte chưa cài)
├── favorites.py         # đọc/ghi favorites.json
├── tool_scanner.py      # registry + scan CLI tools
├── settings.py          # AppSettings (theme, language, session, backend, layout)
├── theme.py             # light/dark/system palette (darkdetect)
├── i18n.py              # bộ dịch UI (vi / en)
├── favorites.json       # tự sinh khi chạy lần đầu
├── settings.json        # tự sinh khi đóng app lần đầu
├── TerminalManager.spec # PyInstaller build spec
├── requirements.txt
├── README.md            # English
└── README.vi.md         # Tiếng Việt
```

## Cài đặt

Yêu cầu: **Python 3.9+** trên Windows 10/11, macOS 11+, hoặc Linux (bất kỳ distro nào có Python).

`requirements.txt` dùng PEP 508 markers nên `pip install -r requirements.txt` tự chọn đúng dependency cho platform (`pywinpty` cho Windows, `ptyprocess` cho macOS/Linux).

### Clone repository

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

> **Note**: trên Linux, dùng `--system-site-packages` để tận dụng PyQt5 từ system; hoặc dùng `pip install PyQt5` (cần Qt5 dev headers + build tools).

> **Note**: nếu `pywinpty` / `ptyprocess` không cài được, app vẫn chạy ở chế độ QProcess (không có TTY).

## Phím tắt

| Phím tắt | Hành động |
|----------|-----------|
| `Ctrl+T` | Mở tab CMD/Bash mới (mặc định theo platform) |
| `Ctrl+Shift+T` | Mở tab PowerShell/Zsh mới |
| `Ctrl+R` | Chạy file script (.bat/.cmd/.ps1) |
| `Ctrl+O` | Mở dialog chọn thư mục → `cd` vào terminal active |
| `Ctrl+I` | Bật/tắt ô nhập chung (mặc định ẩn khi TUI mode) |
| `Ctrl+W` | Đóng terminal hiện tại |
| `Ctrl+L` | Xoá log gộp |
| `Ctrl+,` | Mở Cài đặt (theme / ngôn ngữ / backend / layout) |
| `Ctrl+=` | Cân đều các ô lưới |
| `Ctrl+Shift+P` | Toggle password mode trong ô nhập |
| `Enter` | Gửi lệnh trong ô nhập |
| `Shift+Enter` | Xuống dòng (nhập lệnh nhiều dòng) |
| `Ctrl+↑` / `Ctrl+↓` | Duyệt lịch sử lệnh trong ô input |
| Double-click tab | Đổi tên tab |
| Nút **×** trên status bar | Đóng terminal hiện tại |

## Build thành app thực thi

Tất cả platform dùng chung 1 file spec [`TerminalManager.spec`](TerminalManager.spec) cho [PyInstaller](https://pyinstaller.org/):
- Đóng gói đầy đủ DLLs của `pywinpty` (Windows) hoặc data của `ptyprocess` (Unix) để TTY backend hoạt động
- Bao gồm `darkdetect`, `pyte`, `PyQt5` và data files
- Dùng **onedir** mode (`--onedir`) — output là folder chứa executable + dependencies. **Không dùng onefile** vì pywinpty ConPTY agent sẽ fail (`STATUS_CONTROL_C_EXIT`) khi DLLs bị extract ra temp dir
- Trên macOS, còn tạo thêm `.app` bundle

**Phải build trên đúng platform target.** PyInstaller không cross-compile được: `.exe` chỉ build trên Windows, `.app` chỉ trên macOS, ELF binary chỉ trên Linux.

### Chuẩn bị

```bash
pip install pyinstaller
```

### Windows

```bat
rem Trong venv đang activate, từ thư mục project:
pyinstaller --noconfirm TerminalManager.spec

rem Output: dist\TerminalManager\TerminalManager.exe (+ các DLL cần thiết)
rem Chạy:
dist\TerminalManager\TerminalManager.exe
```

**Distribute** cả folder `dist\TerminalManager\` (zip lại). Nếu muốn 1 file installer:
- [Inno Setup](https://jrsoftware.org/isinfo.php) — wizard cài đặt thân thiện, khuyến nghị
- [NSIS](https://nsis.sourceforge.io/) — nhẹ, scriptable

### macOS

```bash
# Trong venv, từ thư mục project:
pyinstaller --noconfirm TerminalManager.spec

# Output:
#   dist/TerminalManager/                  ← folder onedir (binary + libs)
#   dist/TerminalManager.app/              ← .app bundle macOS (khuyến nghị)
# Chạy .app:
open dist/TerminalManager.app
```

**Distribute** dạng `.app` bundle. Lựa chọn:
- **Zip** `TerminalManager.app` rồi gửi
- **DMG**: `hdiutil create -volname TerminalManager -srcfolder dist/TerminalManager.app TerminalManager.dmg`
- Cho App Store / Gatekeeper: codesign + notarize (`codesign --sign "Developer ID Application: …" dist/TerminalManager.app`, rồi `xcrun notarytool submit`).

Nếu có icon, sửa `icon="/path/to/icon.icns"` trong khối `BUNDLE(...)` của `TerminalManager.spec`.

### Linux

```bash
# Trong venv, từ thư mục project:
pyinstaller --noconfirm TerminalManager.spec

# Output: dist/TerminalManager/   (folder chứa ELF binary `TerminalManager`)
./dist/TerminalManager/TerminalManager
```

**Distribute** lựa chọn:
- **Tar.gz**: `tar -czvf TerminalManager-linux.tar.gz -C dist TerminalManager`
- **AppImage**: dùng [linuxdeployqt](https://github.com/probonopd/linuxdeployqt) hoặc [appimagetool](https://appimage.github.io/appimagetool/)
- **`.deb`**: dùng `dh_make` + `dpkg-buildpackage`, hoặc [`fpm`](https://github.com/jordansissel/fpm): `fpm -s dir -t deb -n terminal-manager -v 1.0.0 dist/TerminalManager/=/opt/terminal-manager/`
- **`.rpm`**: tương tự `fpm -t rpm …`
- **Snap / Flatpak**: viết `snapcraft.yaml` / Flatpak manifest trỏ đến binary

> **Note**: PyQt5 wheel có sẵn Qt plugins (`libqxcb`). Trên distro tối giản/headless, cần cài thêm system libs như `libxcb-cursor0`, `libxkbcommon-x11-0`, `libxcb-render-util0` — không sẽ bị `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`.

### Vì sao dùng onedir thay vì onefile?

`--onefile` extract mọi thứ ra temp directory lúc runtime, khiến ConPTY agent của `pywinpty` (`winpty-agent.exe`) fail với `STATUS_CONTROL_C_EXIT (-1073741510)` vì không tìm được các DLL anh em. Spec dùng `--onedir` để DLLs nằm cạnh executable. Muốn ship 1 file thì wrap onedir folder bằng installer (Inno Setup / DMG / AppImage).

## Shells

App tự động phát hiện shells có sẵn và hiển thị nút phù hợp trên toolbar.

### Windows
| Shell | Yêu cầu | Nút toolbar |
|-------|---------|-------------|
| CMD | Có sẵn | `+ CMD` |
| PowerShell | `powershell.exe` | `+ PowerShell` |
| WSL | `wsl --install` | `+ WSL` |
| Git Bash | Git for Windows | `+ Git Bash` |

### macOS / Linux
| Shell | Yêu cầu | Nút toolbar |
|-------|---------|-------------|
| Bash | `/bin/bash` | `+ Bash` |
| Zsh | `which zsh` (macOS có sẵn) | `+ Zsh` |
| Fish | `which fish` | `+ Fish` |
| sh | `/bin/sh` (POSIX) | `+ sh` |
| PowerShell Core | `pwsh` | `+ PowerShell` (nếu có) |

Nút shell **disable** nếu app không tìm thấy binary tương ứng.

## Giới hạn đã biết

- Mouse reporting trong TUI apps (vd click chuột trong `htop`) chưa forward — chỉ keyboard.
- Scrollback giới hạn 5000 dòng/tab.
- Nếu `pyte` chưa cài, app fallback về ANSI renderer cũ (scroll-mode, không TUI).

## Tuỳ biến nhanh

- Sửa danh sách lệnh mặc định: chỉnh `FavoritesStore.load()` trong `favorites.py`.
- Đổi giao diện màu/nền: chỉnh `setStyleSheet(...)` trong `terminal_tab.py` (vùng output) và `main_window.py`.
- Đổi font: `QFont("Consolas", 10)` trong các file UI.
- Thêm CLI tool vào scanner: chỉnh `_TOOLS` trong `tool_scanner.py`.

## Đóng góp

Mọi issue và pull request được chào đón tại https://github.com/huthido/TerminalManager.

Khi báo lỗi, vui lòng kèm:
- OS + phiên bản Python
- Output của `pip list | grep -i -E "pyqt|winpty|ptyprocess|darkdetect"`
- Nội dung file `startup.log` (tự sinh cạnh `main.py` mỗi lần chạy)
