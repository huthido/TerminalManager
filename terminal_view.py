"""
TerminalView — widget terminal emulator full TUI dùng `pyte`.

Thay thế cho QPlainTextEdit + AnsiRenderer cũ. Hỗ trợ:
- Alternate screen buffer (vim, htop, nano, less)
- Cursor positioning tuyệt đối + tương đối
- Scrollback (pyte.HistoryScreen)
- Raw keyboard input forwarding (arrow keys, F-keys, ...)
- ANSI colors đầy đủ (16 + 256 + truecolor) qua pyte

Phát signal:
- key_pressed(bytes): user gõ phím → bytes để gửi xuống PTY
- resized(cols, rows): widget đổi size → backend cần resize PTY
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QRect, QSize, QTimer
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import QAbstractScrollArea, QWidget

try:
    import pyte
except ImportError as _e:
    pyte = None
    _PYTE_ERR = str(_e)
else:
    _PYTE_ERR = None


# ============================================================
# Color palette — map pyte color → QColor
# ============================================================

# 16 colors xterm-like
_BASE_COLORS = {
    "black":   QColor(0, 0, 0),
    "red":     QColor(205, 49, 49),
    "green":   QColor(13, 188, 121),
    "brown":   QColor(229, 229, 16),  # yellow
    "blue":    QColor(36, 114, 200),
    "magenta": QColor(188, 63, 188),
    "cyan":    QColor(17, 168, 205),
    "white":   QColor(229, 229, 229),
    "brightblack":   QColor(102, 102, 102),
    "brightred":     QColor(241, 76, 76),
    "brightgreen":   QColor(35, 209, 139),
    "brightbrown":   QColor(245, 245, 67),
    "brightblue":    QColor(59, 142, 234),
    "brightmagenta": QColor(214, 112, 214),
    "brightcyan":    QColor(41, 184, 219),
    "brightwhite":   QColor(255, 255, 255),
}

_DEFAULT_FG = QColor("#d4d4d4")
_DEFAULT_BG = QColor("#1e1e1e")


def _resolve_color(name: str, default: QColor) -> QColor:
    """Convert pyte color name → QColor. Hỗ trợ named, 256-color số, hex."""
    if not name or name == "default":
        return default
    # Hex (truecolor, vd "ff0000")
    if len(name) == 6:
        try:
            r = int(name[0:2], 16)
            g = int(name[2:4], 16)
            b = int(name[4:6], 16)
            return QColor(r, g, b)
        except ValueError:
            pass
    # Named color
    if name in _BASE_COLORS:
        return _BASE_COLORS[name]
    # 256-color index (pyte có thể trả về số dạng string)
    try:
        idx = int(name)
        return _xterm_256(idx)
    except ValueError:
        pass
    return default


def _xterm_256(n: int) -> QColor:
    if n < 16:
        names = list(_BASE_COLORS.keys())
        return _BASE_COLORS.get(names[n], _DEFAULT_FG)
    if n < 232:
        n -= 16
        r = (n // 36) % 6
        g = (n // 6) % 6
        b = n % 6
        steps = (0, 95, 135, 175, 215, 255)
        return QColor(steps[r], steps[g], steps[b])
    # grayscale 232..255
    g = 8 + (n - 232) * 10
    return QColor(g, g, g)


# ============================================================
# Key mapping Qt → ANSI
# ============================================================

_KEY_MAP = {
    Qt.Key_Up:        b"\x1b[A",
    Qt.Key_Down:      b"\x1b[B",
    Qt.Key_Right:     b"\x1b[C",
    Qt.Key_Left:      b"\x1b[D",
    Qt.Key_Home:      b"\x1b[H",
    Qt.Key_End:       b"\x1b[F",
    Qt.Key_PageUp:    b"\x1b[5~",
    Qt.Key_PageDown:  b"\x1b[6~",
    Qt.Key_Insert:    b"\x1b[2~",
    Qt.Key_Delete:    b"\x1b[3~",
    Qt.Key_F1:        b"\x1bOP",
    Qt.Key_F2:        b"\x1bOQ",
    Qt.Key_F3:        b"\x1bOR",
    Qt.Key_F4:        b"\x1bOS",
    Qt.Key_F5:        b"\x1b[15~",
    Qt.Key_F6:        b"\x1b[17~",
    Qt.Key_F7:        b"\x1b[18~",
    Qt.Key_F8:        b"\x1b[19~",
    Qt.Key_F9:        b"\x1b[20~",
    Qt.Key_F10:       b"\x1b[21~",
    Qt.Key_F11:       b"\x1b[23~",
    Qt.Key_F12:       b"\x1b[24~",
    Qt.Key_Tab:       b"\t",
    Qt.Key_Backtab:   b"\x1b[Z",
    Qt.Key_Backspace: b"\x7f",
    Qt.Key_Escape:    b"\x1b",
    Qt.Key_Return:    b"\r",
    Qt.Key_Enter:     b"\r",
}


# ============================================================
# TerminalView widget
# ============================================================

class TerminalView(QAbstractScrollArea):
    """Terminal emulator widget dùng pyte."""

    # User gõ phím → bytes cần gửi xuống PTY
    key_pressed = pyqtSignal(bytes)
    # Widget đổi size (cells) → backend cần resize PTY (cols, rows)
    resized = pyqtSignal(int, int)

    def __init__(self, parent=None, cols: int = 80, rows: int = 24, history: int = 5000):
        super().__init__(parent)
        if pyte is None:
            raise ImportError(f"pyte is required: {_PYTE_ERR}")

        self.setFocusPolicy(Qt.StrongFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Bật input method (IME) để gõ Unicode: tiếng Việt (Telex/VNI/Unikey),
        # tiếng Trung, tiếng Nhật, emoji, ... Qt sẽ route IME events vào
        # inputMethodEvent() của widget.
        self.setAttribute(Qt.WA_InputMethodEnabled, True)

        # Font monospace
        self._font = QFont("Consolas", 10)
        self._font.setStyleHint(QFont.Monospace)
        self._fm = QFontMetrics(self._font)
        self._char_width = max(1, self._fm.horizontalAdvance("M"))
        self._char_height = max(1, self._fm.height())

        self._cols = cols
        self._rows = rows

        # pyte screen with scrollback
        self.screen = pyte.HistoryScreen(cols, rows, history=history, ratio=0.5)
        self.stream = pyte.ByteStream(self.screen)

        # Viewport background
        self.viewport().setStyleSheet(
            f"background-color: {_DEFAULT_BG.name()};"
        )

        # Cursor blink
        self._cursor_visible = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start()

        # Scroll position (0 = ở cuối/live; >0 = đã scroll lên scrollback)
        self.verticalScrollBar().valueChanged.connect(lambda _: self.viewport().update())

    # ---------- API ----------
    def feed(self, data) -> None:
        """Feed bytes/str từ PTY vào emulator."""
        if isinstance(data, str):
            data = data.encode("utf-8", errors="replace")
        try:
            self.stream.feed(data)
        except Exception:
            # pyte đôi khi raise với sequence hiếm — bỏ qua để app không crash
            pass
        self._update_scrollbar()
        self.viewport().update()

    def clear(self) -> None:
        self.screen.reset()
        self.viewport().update()

    def grid_size(self) -> tuple[int, int]:
        return self._cols, self._rows

    def set_font(self, font: QFont) -> None:
        self._font = font
        self._fm = QFontMetrics(font)
        self._char_width = max(1, self._fm.horizontalAdvance("M"))
        self._char_height = max(1, self._fm.height())
        self._recompute_size()

    # ---------- size / scroll ----------
    def _recompute_size(self) -> None:
        cols = max(1, self.viewport().width() // self._char_width)
        rows = max(1, self.viewport().height() // self._char_height)
        if (cols, rows) != (self._cols, self._rows):
            self._cols, self._rows = cols, rows
            self.screen.resize(rows, cols)
            self.resized.emit(cols, rows)
        self._update_scrollbar()

    def _update_scrollbar(self) -> None:
        history_lines = len(self.screen.history.top)
        bar = self.verticalScrollBar()
        bar.setRange(0, history_lines)
        bar.setPageStep(self._rows)
        bar.setSingleStep(1)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._recompute_size()

    def sizeHint(self) -> QSize:
        return QSize(
            80 * self._char_width + 4,
            24 * self._char_height + 4,
        )

    # ---------- input ----------
    def _scroll_to_live(self) -> None:
        """Đưa view về bottom (live screen) — gọi mỗi khi user gõ phím để con trỏ luôn visible."""
        bar = self.verticalScrollBar()
        if bar.value() != 0:
            bar.setValue(0)

    def _emit_key(self, data: bytes) -> None:
        """Helper: scroll về live trước khi forward phím xuống PTY."""
        self._scroll_to_live()
        self.key_pressed.emit(data)

    def keyPressEvent(self, e):
        key = e.key()
        mods = e.modifiers()
        text = e.text()

        # Đặc biệt: Ctrl+letter → control codes (Ctrl+C = \x03, Ctrl+D = \x04, ...)
        if mods & Qt.ControlModifier and not (mods & Qt.AltModifier):
            if Qt.Key_A <= key <= Qt.Key_Z:
                ctrl_byte = key - Qt.Key_A + 1
                self._emit_key(bytes([ctrl_byte]))
                e.accept()
                return
            # Ctrl+[ = ESC; Ctrl+\ = FS; Ctrl+] = GS; Ctrl+^ = RS; Ctrl+_ = US
            if key == Qt.Key_BracketLeft:
                self._emit_key(b"\x1b")
                e.accept()
                return

        # Map key đặc biệt qua bảng tra
        if key in _KEY_MAP:
            self._emit_key(_KEY_MAP[key])
            e.accept()
            return

        # Alt+key → ESC + key (meta key)
        if mods & Qt.AltModifier and text:
            self._emit_key(b"\x1b" + text.encode("utf-8", errors="replace"))
            e.accept()
            return

        # Ký tự thường — gửi text raw
        if text:
            self._emit_key(text.encode("utf-8", errors="replace"))
            e.accept()
            return

        super().keyPressEvent(e)

    # ---------- paint ----------
    def _blink(self) -> None:
        self._cursor_visible = not self._cursor_visible
        self.viewport().update()

    def paintEvent(self, e):
        painter = QPainter(self.viewport())
        painter.setFont(self._font)

        # Background
        painter.fillRect(self.viewport().rect(), _DEFAULT_BG)

        cw = self._char_width
        ch = self._char_height

        # Lấy nội dung hiển thị: nếu user scroll lên thì hiển thị history + screen
        scroll_pos = self.verticalScrollBar().value()
        history_top = list(self.screen.history.top)

        # Visible lines = một slice history + buffer hiện tại
        # screen.buffer là dict {y: {x: Char}}, y trong [0..rows-1]
        visible_lines: list[dict] = []
        if scroll_pos > 0:
            # Đang scroll lên — show lines từ history
            history_lines_to_show = min(scroll_pos, len(history_top))
            for hist_line in history_top[-history_lines_to_show:]:
                # hist_line là dict {x: Char}
                visible_lines.append(hist_line)

        # Còn lại lấy từ screen.buffer (current display)
        remaining = self._rows - len(visible_lines)
        for y in range(remaining):
            line = self.screen.buffer.get(y, {})
            visible_lines.append(line)

        # Vẽ từng dòng
        baseline_offset = self._fm.ascent()
        for row_idx, line in enumerate(visible_lines[: self._rows]):
            y_px = row_idx * ch
            # Group ô liên tiếp có cùng format → vẽ nhanh hơn
            x = 0
            while x < self._cols:
                cell = line.get(x) if line else None
                if cell is None:
                    x += 1
                    continue
                # Bắt đầu run với format này
                run_start = x
                run_chars = [cell.data or " "]
                run_fg = cell.fg
                run_bg = cell.bg
                run_bold = bool(cell.bold)
                run_italic = bool(cell.italics)
                run_under = bool(cell.underscore)
                run_reverse = bool(cell.reverse)
                x += 1
                while x < self._cols:
                    next_cell = line.get(x)
                    if (
                        next_cell is None
                        or next_cell.fg != run_fg
                        or next_cell.bg != run_bg
                        or bool(next_cell.bold) != run_bold
                        or bool(next_cell.italics) != run_italic
                        or bool(next_cell.underscore) != run_under
                        or bool(next_cell.reverse) != run_reverse
                    ):
                        break
                    run_chars.append(next_cell.data or " ")
                    x += 1

                # Render run
                fg = _resolve_color(run_fg, _DEFAULT_FG)
                bg = _resolve_color(run_bg, _DEFAULT_BG)
                if run_reverse:
                    fg, bg = bg, fg

                run_w = (x - run_start) * cw
                rect = QRect(run_start * cw, y_px, run_w, ch)
                if bg != _DEFAULT_BG or run_reverse:
                    painter.fillRect(rect, bg)

                # Font weight/italic per run
                f = QFont(self._font)
                f.setBold(run_bold)
                f.setItalic(run_italic)
                f.setUnderline(run_under)
                painter.setFont(f)
                painter.setPen(fg)
                painter.drawText(
                    run_start * cw, y_px + baseline_offset, "".join(run_chars)
                )

        # Cursor (chỉ vẽ nếu KHÔNG đang scroll lên history)
        if scroll_pos == 0 and not self.screen.cursor.hidden and self._cursor_visible:
            cx_px = self.screen.cursor.x * cw
            cy_px = self.screen.cursor.y * ch
            cursor_rect = QRect(cx_px, cy_px, cw, ch)
            painter.fillRect(cursor_rect, _DEFAULT_FG)
            # Vẽ ký tự ở vị trí cursor với màu invert
            cell = self.screen.buffer.get(self.screen.cursor.y, {}).get(self.screen.cursor.x)
            if cell and cell.data:
                painter.setPen(_DEFAULT_BG)
                f = QFont(self._font)
                f.setBold(bool(cell.bold))
                painter.setFont(f)
                painter.drawText(cx_px, cy_px + baseline_offset, cell.data)

        painter.end()

    # ---------- IME / Unicode composition input ----------
    def inputMethodEvent(self, e):
        """Gõ Unicode qua IME (Telex/VNI/Pinyin/Hiragana/...).

        Khi user gõ phím qua IME, Qt route đến đây thay vì keyPressEvent.
        Ta gửi commitString xuống PTY ngay khi user "commit" ký tự đã ghép.
        """
        commit = e.commitString()
        if commit:
            # Cùng nguyên tắc với keyPressEvent: scroll về live + forward
            self._emit_key(commit.encode("utf-8", errors="replace"))
            e.accept()
            return
        super().inputMethodEvent(e)

    def inputMethodQuery(self, query):
        """Báo cho IME biết vị trí cursor để hiển thị popup composition đúng chỗ."""
        if query == Qt.ImCursorRectangle:
            cx_px = self.screen.cursor.x * self._char_width
            cy_px = self.screen.cursor.y * self._char_height
            return QRect(cx_px, cy_px, self._char_width, self._char_height)
        if query == Qt.ImFont:
            return self._font
        return super().inputMethodQuery(query)

    # ---------- mouse — focus on click ----------
    def mousePressEvent(self, e):
        self.setFocus(Qt.MouseFocusReason)
        super().mousePressEvent(e)


PYTE_AVAILABLE = pyte is not None
