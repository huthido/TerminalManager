"""
Backend chạy shell con cho TerminalTab. Có 2 implementation:

- QProcessBackend  : dùng QProcess (pipe stdin/stdout). Không có TTY thực,
  nên các chương trình kiểm tra `isatty()` (ssh, REPL Python, vim, top...) sẽ
  cảnh báo hoặc disable tính năng tương tác.
- ConPtyBackend    : dùng pywinpty (Windows ConPTY) — có TTY thật, chạy được
  ssh / vim / REPL... nhưng phải dispose ANSI escape codes trên đường về.

Cả 2 cùng implement interface `PtyBackendBase` với signals:
- output(str)      : có dữ liệu mới (đã decode UTF-8)
- finished(int)    : process kết thúc, mang exit code
- error(str)       : lỗi
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import threading

from PyQt5.QtCore import QObject, QProcess, QThread, pyqtSignal


# ============================================================
# Shell resolution
# ============================================================

# Các vị trí mặc định của Git Bash trên Windows
_GIT_BASH_PATHS = [
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
    r"C:\Program Files\Git\usr\bin\bash.exe",
]


def find_git_bash() -> str | None:
    for p in _GIT_BASH_PATHS:
        if os.path.exists(p):
            return p
    # last resort: which bash
    try:
        path = shutil.which("bash.exe") or shutil.which("bash")
        if path and "WindowsApps" not in path:
            return path
    except Exception:
        pass
    return None


def find_wsl() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        return shutil.which("wsl.exe") or shutil.which("wsl")
    except Exception:
        return None


IS_WINDOWS = sys.platform == "win32"


def shell_command(shell: str, tty: bool = False) -> tuple[str, list[str]]:
    """
    Trả về (program, args) phù hợp cho từng loại shell trên platform hiện tại.

    Windows shells: cmd, powershell, pwsh, wsl, bash (Git Bash).
    Unix shells (Linux/macOS): bash, zsh, fish, sh, pwsh (PowerShell Core nếu có).
    """
    sh = shell.lower()

    # ---------- Windows ----------
    if IS_WINDOWS:
        if sh == "powershell":
            if tty:
                return "powershell.exe", ["-NoLogo"]
            return "powershell.exe", ["-NoLogo", "-NoExit", "-Command", "-"]
        if sh == "pwsh":
            if tty:
                return "pwsh.exe", ["-NoLogo"]
            return "pwsh.exe", ["-NoLogo", "-NoExit", "-Command", "-"]
        if sh == "wsl":
            wsl = find_wsl() or "wsl.exe"
            return wsl, []
        if sh == "bash":
            bash = find_git_bash()
            if bash is None:
                return "bash.exe", ["--login", "-i"]
            return bash, ["--login", "-i"]
        # default Windows: cmd
        return os.environ.get("COMSPEC", "cmd.exe"), ["/Q", "/K", "chcp 65001 >nul"]

    # ---------- Unix (Linux / macOS / BSD) ----------
    if sh == "bash":
        return shutil.which("bash") or "/bin/bash", ["-i"]
    if sh == "zsh":
        return shutil.which("zsh") or "/bin/zsh", ["-i"]
    if sh == "fish":
        return shutil.which("fish") or "/usr/bin/fish", ["-i"]
    if sh == "sh":
        return shutil.which("sh") or "/bin/sh", ["-i"]
    if sh == "pwsh":
        return shutil.which("pwsh") or "pwsh", ["-NoLogo"] if tty else ["-NoLogo", "-Command", "-"]
    # default Unix: $SHELL hoặc bash
    default = os.environ.get("SHELL") or shutil.which("bash") or "/bin/sh"
    return default, ["-i"]


# ============================================================
# ANSI escape stripping
# ============================================================

# CSI: ESC [ ... letter  (vd colors, cursor movement)
_ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
# OSC: ESC ] ... BEL or ST  (vd set title)
_ANSI_OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
# SS3 / single char escapes
_ANSI_SHORT = re.compile(r"\x1b[=>NOP\\)(/]")
# Charset switches: ESC ( B, ESC ) 0 ...
_ANSI_CHARSET = re.compile(r"\x1b[()][\w@]")
# DEC private: ESC [ ? ... letter — đã cover bởi CSI
# Ký tự control hiếm (giữ \r \n \t \b)
_ANSI_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1a\x1c-\x1f]")


def strip_ansi(text: str) -> str:
    """Loại bỏ tất cả ANSI escape sequences. Giữ \\r, \\n, \\t, \\b."""
    text = _ANSI_OSC.sub("", text)
    text = _ANSI_CSI.sub("", text)
    text = _ANSI_CHARSET.sub("", text)
    text = _ANSI_SHORT.sub("", text)
    text = _ANSI_CTRL.sub("", text)
    return text


# ============================================================
# Base interface
# ============================================================

class PtyBackendBase(QObject):
    """Interface chung cho mọi backend shell."""

    output = pyqtSignal(str)        # text đã decode (chưa strip ANSI)
    finished = pyqtSignal(int)      # exit code
    error = pyqtSignal(str)

    backend_name: str = "base"
    supports_tty: bool = False

    def __init__(self, shell: str = "cmd", parent=None):
        super().__init__(parent)
        self.shell = shell.lower()
        self._pid: int = 0
        self._program: str = ""

    def program_name(self) -> str:
        return self._program

    def pid(self) -> int:
        return self._pid

    def start(self) -> bool:
        raise NotImplementedError

    def write(self, data: str) -> None:
        raise NotImplementedError

    def kill(self) -> None:
        raise NotImplementedError

    def is_running(self) -> bool:
        raise NotImplementedError

    def resize(self, cols: int, rows: int) -> None:
        """Đổi kích thước PTY (tính theo ký tự). Backend nào không hỗ trợ thì bỏ qua."""
        return


# ============================================================
# QProcess backend (no TTY)
# ============================================================

class QProcessBackend(PtyBackendBase):
    backend_name = "qprocess"
    supports_tty = False

    def __init__(self, shell: str = "cmd", parent=None):
        super().__init__(shell, parent)
        self.process: QProcess | None = None

    def start(self) -> bool:
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._on_data)
        self.process.finished.connect(lambda code, _s: self.finished.emit(int(code)))
        self.process.errorOccurred.connect(lambda err: self.error.emit(str(err)))

        program, args = shell_command(self.shell)
        self._program = program
        self.process.start(program, args)
        ok = self.process.waitForStarted(3000)
        if ok:
            self._pid = self.process.processId()
        return ok

    def _on_data(self) -> None:
        if not self.process:
            return
        raw = self.process.readAllStandardOutput().data()
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = raw.decode("cp1258", errors="replace")
        self.output.emit(text)

    def write(self, data: str) -> None:
        if self.process and self.process.state() == QProcess.Running:
            self.process.write(data.encode("utf-8"))

    def kill(self) -> None:
        if self.process and self.process.state() == QProcess.Running:
            self.process.kill()

    def is_running(self) -> bool:
        return self.process is not None and self.process.state() == QProcess.Running


# ============================================================
# ConPTY backend (real TTY via pywinpty)
# ============================================================

class _PtyReaderThread(QThread):
    """Đọc PTY trong thread riêng (pywinpty.read là blocking)."""

    data_received = pyqtSignal(bytes)
    finished_signal = pyqtSignal(int)

    def __init__(self, proc):
        super().__init__()
        self.proc = proc
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                data = self.proc.read(4096)
            except EOFError:
                break
            except Exception as e:
                print(f"[pty reader] {e}")
                break
            if not data:
                # process có thể đã đóng
                try:
                    if not self.proc.isalive():
                        break
                except Exception:
                    break
                continue
            if isinstance(data, str):
                data = data.encode("utf-8", errors="replace")
            self.data_received.emit(data)

        try:
            code = self.proc.exitstatus
            if code is None:
                code = 0
        except Exception:
            code = -1
        self.finished_signal.emit(int(code))

    def stop(self) -> None:
        self._stop.set()


class ConPtyBackend(PtyBackendBase):
    """
    TTY backend cross-platform.
    - Windows: dùng pywinpty (ConPTY)
    - Linux/macOS: dùng ptyprocess (native pty via os.openpty)

    Tên class giữ là "ConPtyBackend" để tương thích settings cũ, nhưng thực tế
    là TTY backend tổng quát.
    """

    backend_name = "tty"
    supports_tty = True

    _availability_checked = False
    _is_available = False
    _import_error: str | None = None

    def __init__(self, shell: str = "cmd", parent=None):
        super().__init__(shell, parent)
        self.proc = None
        self.reader: _PtyReaderThread | None = None
        self._cols = 120
        self._rows = 30

    @staticmethod
    def _pty_module():
        """Trả về module pty phù hợp với platform, hoặc raise nếu không cài."""
        if IS_WINDOWS:
            import winpty
            return winpty
        else:
            import ptyprocess
            return ptyprocess

    @classmethod
    def is_available(cls) -> bool:
        if cls._availability_checked:
            return cls._is_available
        try:
            cls._pty_module()
            cls._is_available = True
        except Exception as e:
            cls._import_error = str(e)
            cls._is_available = False
        cls._availability_checked = True
        return cls._is_available

    @classmethod
    def import_error(cls) -> str | None:
        return cls._import_error

    def start(self) -> bool:
        try:
            pty_mod = self._pty_module()
        except Exception as e:
            self.error.emit(f"PTY library không cài được: {e}")
            return False

        program, args = shell_command(self.shell, tty=True)
        self._program = program

        # Pass argv dạng list để tránh shlex parsing quote (đặc biệt cần thiết
        # cho Windows pywinpty với path có space như "C:\Program Files\...").
        argv = [program] + list(args)
        try:
            # Cả winpty.PtyProcess và ptyprocess.PtyProcess có API spawn() tương tự
            self.proc = pty_mod.PtyProcess.spawn(
                argv,
                dimensions=(self._rows, self._cols),
            )
        except Exception as e:
            self.error.emit(f"PtyProcess.spawn lỗi: {e}")
            return False

        self._pid = getattr(self.proc, "pid", 0) or 0

        self.reader = _PtyReaderThread(self.proc)
        self.reader.data_received.connect(self._on_data)
        self.reader.finished_signal.connect(self._on_finished)
        self.reader.start()
        return True

    def _on_data(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        self.output.emit(text)

    def _on_finished(self, code: int) -> None:
        self.finished.emit(code)

    def write(self, data: str) -> None:
        if not self.proc:
            return
        try:
            if not self.proc.isalive():
                return
        except Exception:
            return
        try:
            self.proc.write(data)
        except Exception as e:
            self.error.emit(f"write err: {e}")

    def kill(self) -> None:
        if self.reader:
            self.reader.stop()
        if self.proc:
            try:
                self.proc.terminate(force=True)
            except Exception:
                try:
                    self.proc.close()
                except Exception:
                    pass

    def is_running(self) -> bool:
        if not self.proc:
            return False
        try:
            return bool(self.proc.isalive())
        except Exception:
            return False

    def resize(self, cols: int, rows: int) -> None:
        cols = max(20, min(500, int(cols)))
        rows = max(5, min(200, int(rows)))
        self._cols, self._rows = cols, rows
        if self.proc:
            try:
                if self.proc.isalive():
                    self.proc.setwinsize(rows, cols)
            except Exception:
                pass


# ============================================================
# Factory
# ============================================================

def create_backend(
    shell: str,
    preference: str = "auto",
    parent=None,
) -> PtyBackendBase:
    """
    Trả về backend phù hợp.

    preference: "auto" | "conpty" | "qprocess"
    - auto: ưu tiên conpty nếu pywinpty có sẵn, không thì fallback qprocess.
    """
    if preference == "conpty":
        if ConPtyBackend.is_available():
            return ConPtyBackend(shell, parent)
        return QProcessBackend(shell, parent)
    if preference == "qprocess":
        return QProcessBackend(shell, parent)
    # auto
    if ConPtyBackend.is_available():
        return ConPtyBackend(shell, parent)
    return QProcessBackend(shell, parent)
