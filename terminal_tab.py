"""
TerminalTab — widget hiển thị 1 phiên shell.

Sau refactor "1 ô nhập chung": TerminalTab CHỈ chứa
- Status bar (Clear / Stop / Restart / Close)
- Vùng output (QPlainTextEdit) có AnsiRenderer để hiển thị màu

Ô nhập lệnh dùng chung đặt ở MainWindow. MainWindow điều phối input vào terminal
đang ACTIVE.

Module này vẫn export các class/helpers liên quan đến input panel để MainWindow
tái sử dụng:
- CommandEdit                : QPlainTextEdit cho lệnh đa dòng + history hooks
- PasswordEdit               : QLineEdit echo=Password + Esc handler
- looks_like_password_prompt : detect prompt password ở dòng cuối
"""

from __future__ import annotations

import os
import re
import sys
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QEvent, QMimeData
from PyQt5.QtGui import QFont, QTextCursor, QColor, QDrag
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QApplication,
)


# MIME type cho drag-and-drop terminal trong grid
TERMINAL_MIME = "application/x-tmgr-terminal"

from i18n import t
from pty_backend import PtyBackendBase, create_backend, strip_ansi
from terminal_view import TerminalView, PYTE_AVAILABLE


# ============================================================
# Password prompt detection
# ============================================================

_PASSWORD_PATTERNS = [
    re.compile(r"(^|\W)password\s*[:：]\s*$", re.IGNORECASE),
    re.compile(r"(^|\W)passphrase[^\n]{0,80}[:：]\s*$", re.IGNORECASE),
    re.compile(r"\[sudo\]\s+password\s+for\s+\S+\s*[:：]\s*$", re.IGNORECASE),
    re.compile(r"(^|\W)enter\s+password\s*[:：]?\s*$", re.IGNORECASE),
    re.compile(r"(^|\W)mật\s*khẩu\s*[:：]?\s*$", re.IGNORECASE),
    re.compile(r"\bpassword\s+for\s+user\s+\S+\s*[:：]\s*$", re.IGNORECASE),
]


def looks_like_password_prompt(text: str) -> bool:
    text = text.replace("\r", "")
    last_line = ""
    for ln in reversed(text.split("\n")):
        if ln.strip():
            last_line = ln.rstrip()
            break
    if not last_line:
        return False
    for pat in _PASSWORD_PATTERNS:
        if pat.search(last_line):
            return True
    return False


# ============================================================
# Input widgets (dùng ở MainWindow, không dùng trong TerminalTab nữa)
# ============================================================

class CommandEdit(QPlainTextEdit):
    """Ô nhập lệnh đa dòng:
    - Enter        : submitted
    - Shift+Enter  : xuống dòng
    - Ctrl+↑ / ↓   : history_prev / history_next
    """

    submitted = pyqtSignal()
    history_prev = pyqtSignal()
    history_next = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabChangesFocus(False)
        self.setMinimumHeight(28)
        sp = self.sizePolicy()
        sp.setVerticalPolicy(QSizePolicy.Expanding)
        self.setSizePolicy(sp)

    def keyPressEvent(self, e):
        key = e.key()
        mods = e.modifiers()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if mods & Qt.ShiftModifier:
                super().keyPressEvent(e)
                return
            self.submitted.emit()
            return
        if mods & Qt.ControlModifier:
            if key == Qt.Key_Up:
                self.history_prev.emit()
                return
            if key == Qt.Key_Down:
                self.history_next.emit()
                return
        super().keyPressEvent(e)


class PasswordEdit(QLineEdit):
    """QLineEdit echo=Password + Esc → cancelled."""

    submitted = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEchoMode(QLineEdit.Password)
        self.setMinimumHeight(28)
        self.returnPressed.connect(self.submitted)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(e)


# ============================================================
# TerminalTab — chỉ output, không có input
# ============================================================

class TerminalTab(QWidget):
    """Widget hiển thị 1 phiên shell. KHÔNG còn ô nhập riêng."""

    output_received = pyqtSignal(str, str)  # (label, clean_text)
    process_finished = pyqtSignal(str)
    close_requested = pyqtSignal()

    def __init__(
        self,
        shell: str = "cmd",
        label: str | None = None,
        backend_pref: str = "auto",
        parent=None,
    ):
        super().__init__(parent)
        self.shell = shell.lower()
        self.label = label or self.shell.upper()
        self.backend_pref = backend_pref
        self.backend: PtyBackendBase | None = None
        # buffer output gần nhất để MainWindow detect password prompt
        self._recent_output: str = ""

        # Timer debounce cho resize PTY — tránh resize liên tục khi kéo splitter
        # (mỗi resize làm shell vẽ lại prompt → spam combined log)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)  # 150ms sau lần resize cuối
        self._resize_timer.timeout.connect(self._apply_resize)

        self._build_ui()
        self._start_process()

        # Drag-and-drop: cho phép drop terminal khác lên đây để swap
        self.setAcceptDrops(True)
        # Drag-from: kéo trên status_label → bắt đầu drag terminal này
        self.status_label.installEventFilter(self)
        self.status_label.setCursor(Qt.OpenHandCursor)
        self.status_label.setToolTip(
            "Kéo (drag) status bar này để di chuyển terminal sang ô khác"
        )
        self._drag_start_pos = None

    # ---------- Drag-and-drop ----------
    def eventFilter(self, obj, event):
        if obj is self.status_label:
            etype = event.type()
            if etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_start_pos = event.pos()
            elif etype == QEvent.MouseMove and (event.buttons() & Qt.LeftButton):
                if self._drag_start_pos is not None:
                    dist = (event.pos() - self._drag_start_pos).manhattanLength()
                    if dist >= QApplication.startDragDistance():
                        self._start_terminal_drag()
                        self._drag_start_pos = None
            elif etype == QEvent.MouseButtonRelease:
                self._drag_start_pos = None
        return super().eventFilter(obj, event)

    def _start_terminal_drag(self) -> None:
        drag = QDrag(self)
        mime = QMimeData()
        # Dùng id() để định danh terminal — MainWindow sẽ tìm trong _terminals
        mime.setData(TERMINAL_MIME, str(id(self)).encode("utf-8"))
        drag.setMimeData(mime)
        # Hiển thị status bar làm preview khi kéo
        pixmap = self.status_label.grab()
        drag.setPixmap(pixmap)
        drag.exec_(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(TERMINAL_MIME):
            # Không cho drop lên chính mình
            src_id = int(bytes(event.mimeData().data(TERMINAL_MIME)).decode("utf-8"))
            if src_id != id(self):
                event.acceptProposedAction()
                # Highlight border khi hover
                self.setStyleSheet("TerminalTab { border: 2px solid #4ec9b0; }")
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event):
        self.setStyleSheet("")
        if not event.mimeData().hasFormat(TERMINAL_MIME):
            event.ignore()
            return
        src_id = int(bytes(event.mimeData().data(TERMINAL_MIME)).decode("utf-8"))
        # Tìm MainWindow để xử lý swap
        mw = self._find_main_window()
        if mw is not None and hasattr(mw, "handle_terminal_drop"):
            mw.handle_terminal_drop(src_id, self)
        event.acceptProposedAction()

    def _find_main_window(self):
        w = self.parentWidget()
        while w is not None:
            if hasattr(w, "_terminals") and hasattr(w, "handle_terminal_drop"):
                return w
            w = w.parentWidget()
        # fallback: QApplication.activeWindow
        aw = QApplication.activeWindow()
        if aw is not None and hasattr(aw, "_terminals"):
            return aw
        return None

    # ---------- UI ----------
    def _build_ui(self) -> None:
        # Đặt min size nhỏ để grid nhiều cột không ép cửa sổ to vượt monitor
        self.setMinimumSize(160, 120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Thanh trạng thái phía trên.
        # status_label phải có size policy Ignored (horizontal) để splitter có
        # thể thu hẹp terminal nhỏ hơn chiều dài text — nếu không, 4-6 cell
        # ngang sẽ ép cửa sổ rộng vượt monitor.
        top = QHBoxLayout()
        self.status_label = QLabel(f"[{self.label}] đang khởi động...")
        self.status_label.setStyleSheet("color: #888;")
        self.status_label.setMinimumWidth(50)
        self.status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        top.addWidget(self.status_label, 1)

        # Dùng lambda để chắc chắn drop arg `bool checked` của clicked signal
        # — tránh issue auto-trim arg ở một số build PyQt5/Python 3.13.
        # Tô màu nền + viền để debug visibility — bạn sẽ thấy các nút rõ ràng
        btn_style = (
            "QPushButton { background: #444; color: #fff; "
            "border: 1px solid #777; padding: 3px; }"
            "QPushButton:hover { background: #555; }"
            "QPushButton:pressed { background: #666; }"
        )

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFixedWidth(70)
        self.btn_clear.setStyleSheet(btn_style)
        self.btn_clear.setToolTip("Clear terminal output")
        self.btn_clear.clicked.connect(lambda _checked=False: self.clear_output())
        top.addWidget(self.btn_clear)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFixedWidth(70)
        self.btn_stop.setStyleSheet(btn_style)
        self.btn_stop.setToolTip("Kill the shell process")
        self.btn_stop.clicked.connect(lambda _checked=False: self.stop_process())
        top.addWidget(self.btn_stop)

        self.btn_restart = QPushButton("Restart")
        self.btn_restart.setFixedWidth(80)
        self.btn_restart.setStyleSheet(btn_style)
        self.btn_restart.setToolTip("Restart the shell process")
        self.btn_restart.clicked.connect(lambda _checked=False: self.restart_process())
        top.addWidget(self.btn_restart)

        self.btn_close = QPushButton("×")
        self.btn_close.setFixedWidth(32)
        self.btn_close.setStyleSheet(btn_style)
        self.btn_close.setToolTip("Close this terminal")
        self.btn_close.clicked.connect(lambda _checked=False: self.close_requested.emit())
        top.addWidget(self.btn_close)

        layout.addLayout(top)

        # Vùng output — chiếm hết phần còn lại
        mono = QFont("Consolas", 10)
        mono.setStyleHint(QFont.Monospace)
        # TerminalView (pyte-based full TUI emulator) thay cho QPlainTextEdit cũ.
        # Nếu pyte chưa cài → fallback về QPlainTextEdit (giới hạn ở scroll mode).
        if PYTE_AVAILABLE:
            self.output = TerminalView()
            self.output.setFont(mono)
            # User gõ phím khi focus TerminalView → forward xuống PTY
            self.output.key_pressed.connect(self._on_view_key_pressed)
            # Widget resize → cập nhật PTY size (debounced)
            self.output.resized.connect(self._on_view_resized)
            self._uses_tui = True
        else:
            # Fallback: QPlainTextEdit + AnsiRenderer cũ
            from ansi_renderer import AnsiRenderer
            self.output = QPlainTextEdit()
            self.output.setReadOnly(True)
            self.output.setFont(mono)
            self.output.setStyleSheet(
                "background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #333;"
            )
            self.output.setMaximumBlockCount(5000)
            self._renderer = AnsiRenderer(
                self.output,
                default_fg=QColor("#d4d4d4"),
                default_bg=None,
            )
            self._uses_tui = False
        layout.addWidget(self.output, 1)

    # ---------- Process / backend ----------
    def _start_process(self) -> None:
        self.backend = create_backend(self.shell, preference=self.backend_pref, parent=self)
        self.backend.output.connect(self._on_output)
        self.backend.finished.connect(self._on_finished)
        self.backend.error.connect(self._on_error)

        if self.backend.supports_tty:
            cols, rows = self._estimate_pty_size()
            self.backend.resize(cols, rows)

        ok = self.backend.start()
        if not ok:
            self._append_output(
                f"[!] Không khởi động được {self.backend.backend_name} / {self.backend.program_name() or self.shell}\n",
                error=True,
            )
            self.status_label.setText(f"[{self.label}] LỖI khởi động")
            return

        prog = self.backend.program_name() or self.shell
        pid = self.backend.pid()
        tag = "TTY" if self.backend.supports_tty else "no-TTY"
        self.status_label.setText(
            f"[{self.label}] {self.backend.backend_name} ({tag}) PID={pid} - {prog}"
        )
        self._append_output(
            f"[+] Đã mở {prog} qua backend '{self.backend.backend_name}' (PID={pid}, {tag})\n",
            system=True,
        )
        if not self.backend.supports_tty:
            self._append_output(
                "[!] Backend không có TTY: ssh / vim / REPL tương tác có thể không chạy đúng.\n",
                error=True,
            )

    def _estimate_pty_size(self) -> tuple[int, int]:
        try:
            fm = self.output.fontMetrics()
            char_w = max(1, fm.horizontalAdvance("M"))
            char_h = max(1, fm.height())
            w = max(40, self.output.viewport().width())
            h = max(20, self.output.viewport().height())
            cols = max(40, min(300, w // char_w))
            rows = max(10, min(120, h // char_h))
            return int(cols), int(rows)
        except Exception:
            return 120, 30

    def _on_output(self, text: str) -> None:
        # Render: TerminalView (pyte) hoặc AnsiRenderer (fallback)
        if self._uses_tui:
            self.output.feed(text)
        else:
            self._renderer.feed(text)
        # Combined log + password detection nhận bản plain
        clean = strip_ansi(text).replace("\r\n", "\n").replace("\r", "\n")
        self._recent_output = (self._recent_output + clean)[-512:]
        self.output_received.emit(self.label, clean)

    def _on_view_key_pressed(self, data: bytes) -> None:
        """User gõ phím khi focus TerminalView → forward bytes xuống PTY."""
        if self.backend and self.backend.is_running():
            try:
                # pty_backend.write expect str → decode bytes
                self.backend.write(data.decode("utf-8", errors="replace"))
            except Exception:
                pass

    def _on_view_resized(self, cols: int, rows: int) -> None:
        """TerminalView grid resize → cập nhật PTY size."""
        if self.backend and self.backend.supports_tty:
            try:
                self.backend.resize(cols, rows)
            except Exception:
                pass

    def _on_finished(self, exit_code: int) -> None:
        self._append_output(
            f"\n[*] Tiến trình đã kết thúc (exit code = {exit_code})\n",
            system=True,
        )
        self.status_label.setText(f"[{self.label}] đã kết thúc (exit={exit_code})")
        self.process_finished.emit(self.label)

    def _on_error(self, msg: str) -> None:
        self._append_output(f"[!] {msg}\n", error=True)

    # ---------- public API ----------
    def set_label(self, label: str) -> None:
        if not label or label == self.label:
            return
        self.label = label
        current = self.status_label.text()
        new_text = re.sub(r"^\[[^\]]*\]", f"[{label}]", current)
        self.status_label.setText(new_text)

    def send_command(self, command: str) -> None:
        if not self.backend or not self.backend.is_running():
            self._append_output("[!] Tiến trình không còn chạy. Bấm Restart.\n", error=True)
            return
        if not self.backend.supports_tty:
            # Echo manual cho QProcess vì pipe không tự echo
            for i, line in enumerate(command.splitlines() or [command]):
                prefix = "> " if i == 0 else ". "
                self._append_output(f"{prefix}{line}\n", echo=True)
        ending = "\r" if self.backend.supports_tty else "\r\n"
        normalized = ending.join(command.splitlines())
        payload = normalized + ending
        self.backend.write(payload)

    def send_password(self, secret: str) -> None:
        """Gửi password (không echo, không log) tới shell."""
        if not self.backend or not self.backend.is_running():
            return
        ending = "\r" if self.backend.supports_tty else "\r\n"
        self.backend.write(secret + ending)

    def send_ctrl_c(self) -> None:
        if self.backend and self.backend.is_running():
            self.backend.write("\x03")
            self._append_output("[*] Sent Ctrl+C\n", system=True)

    def stop_process(self) -> None:
        if self.backend and self.backend.is_running():
            self.backend.kill()
            self._append_output("[*] Đã kill tiến trình.\n", system=True)

    def restart_process(self) -> None:
        self.stop_process()
        if self._uses_tui:
            self.output.clear()
        else:
            self.output.clear()
        self._recent_output = ""
        self._start_process()

    def clear_output(self) -> None:
        # Cả TerminalView và QPlainTextEdit đều có method clear()
        self.output.clear()
        self._recent_output = ""

    def is_at_password_prompt(self) -> bool:
        """Đọc buffer gần nhất xem dòng cuối có giống prompt password không."""
        return looks_like_password_prompt(self._recent_output)

    def clear_recent_output(self) -> None:
        """Reset buffer detection — gọi sau khi đã chuyển input sang password mode."""
        self._recent_output = ""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # TUI mode: TerminalView tự handle resize + emit signal.
        # Fallback mode: debounce + estimate từ output widget.
        if self._uses_tui:
            return
        if self.backend and self.backend.supports_tty:
            self._resize_timer.start()

    def _apply_resize(self) -> None:
        if self.backend and self.backend.supports_tty:
            cols, rows = self._estimate_pty_size()
            self.backend.resize(cols, rows)

    # ---------- helpers ----------
    def _append_output(
        self, text: str, *, echo: bool = False, system: bool = False, error: bool = False
    ) -> None:
        """
        Hiển thị 1 message do APP (không phải shell) tạo ra.

        TUI mode: KHÔNG vẽ vào TerminalView — vì pyte coi text là dữ liệu của
        shell, sẽ làm cursor lệch khỏi vị trí thực của shell. Thay vào đó, gửi
        message vào combined log để user vẫn xem được. Status bar của terminal
        cũng đã hiển thị tên shell + PID + backend nên không thiếu info.

        Fallback (QPlainTextEdit): vẽ trực tiếp như cũ.
        """
        if self._uses_tui:
            clean = text.rstrip("\n").rstrip("\r")
            if clean:
                self.output_received.emit(self.label, clean)
            return
        # Fallback path: QPlainTextEdit + cursor
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = cursor.charFormat()
        if echo:
            color = QColor("#569cd6")
        elif system:
            color = QColor("#b5cea8")
        elif error:
            color = QColor("#f48771")
        else:
            color = QColor("#d4d4d4")
        fmt.setForeground(color)
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def closeEvent(self, event):
        self.stop_process()
        super().closeEvent(event)
