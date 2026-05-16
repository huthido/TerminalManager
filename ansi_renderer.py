"""
Bộ render ANSI escape sequences cho QTextEdit/QPlainTextEdit.

Hỗ trợ:
- SGR (Select Graphic Rendition): 16 màu cơ bản (30-37, 40-47, 90-97, 100-107),
  256-color (38;5;N / 48;5;N), truecolor (38;2;R;G;B / 48;2;R;G;B),
  bold (1), dim (2), underline (4), reset (0/22/24/39/49).
- CR (\\r): cursor về đầu dòng → ký tự tiếp theo overwrite (giống terminal thật).
- BS (\\b): cursor lùi 1.
- CSI K: erase line (0=to end, 1=to start, 2=whole line).
- CSI J: erase display (2=clear all).
- Sequences khác (cursor positioning, mode set/reset, ...): bỏ qua an toàn.

Renderer giữ buffer escape chưa hoàn chỉnh giữa các lần feed() để xử lý
trường hợp PTY gửi data bị cắt ngang escape sequence.

Không phải terminal emulator đầy đủ: không có alternate screen buffer, không
xử lý cursor positioning tuyệt đối (CSI H), nên TUI full-screen như vim/htop
sẽ vẽ ngược nhưng các app dùng SGR + line editing vẫn hoạt động tốt.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import (
    QColor,
    QFont,
    QTextCharFormat,
    QTextCursor,
)


# 16 màu cơ bản (xterm-like)
_BASIC_COLORS = {
    0: QColor(0, 0, 0),
    1: QColor(205, 49, 49),
    2: QColor(13, 188, 121),
    3: QColor(229, 229, 16),
    4: QColor(36, 114, 200),
    5: QColor(188, 63, 188),
    6: QColor(17, 168, 205),
    7: QColor(229, 229, 229),
    # bright
    8: QColor(102, 102, 102),
    9: QColor(241, 76, 76),
    10: QColor(35, 209, 139),
    11: QColor(245, 245, 67),
    12: QColor(59, 142, 234),
    13: QColor(214, 112, 214),
    14: QColor(41, 184, 219),
    15: QColor(229, 229, 229),
}


def _xterm_256(n: int) -> QColor:
    """Map 256-color index → RGB. n: 0..255."""
    if n < 16:
        return _BASIC_COLORS.get(n, QColor(200, 200, 200))
    if n < 232:
        n -= 16
        r = (n // 36) % 6
        g = (n // 6) % 6
        b = n % 6
        steps = (0, 95, 135, 175, 215, 255)
        return QColor(steps[r], steps[g], steps[b])
    # 232..255: grayscale
    g = 8 + (n - 232) * 10
    return QColor(g, g, g)


class AnsiRenderer:
    """Apply ANSI-formatted text stream to a QTextEdit (hoặc QPlainTextEdit)."""

    def __init__(self, edit, default_fg: QColor | None = None, default_bg: QColor | None = None):
        self.edit = edit
        self.default_fg = default_fg or QColor("#d4d4d4")
        self.default_bg = default_bg  # None = không set background → trong suốt
        self._reset_attrs()
        # incomplete escape between feeds
        self._buffer = ""

    # --------------- attribute state ---------------
    def _reset_attrs(self) -> None:
        self.fg = QColor(self.default_fg)
        self.bg = QColor(self.default_bg) if self.default_bg else None
        self.bold = False
        self.dim = False
        self.underline = False
        self.italic = False
        self.inverse = False

    def _current_format(self) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fg, bg = (self.bg, self.fg) if self.inverse and self.bg else (self.fg, self.bg)
        if fg:
            fmt.setForeground(fg)
        if bg:
            fmt.setBackground(bg)
        font = QFont(self.edit.font())
        font.setBold(self.bold)
        font.setItalic(self.italic)
        font.setUnderline(self.underline)
        fmt.setFont(font)
        return fmt

    # --------------- main entry ---------------
    def feed(self, text: str) -> None:
        text = self._buffer + text
        self._buffer = ""
        i = 0
        plain_start = 0
        n = len(text)

        def flush_plain(upto: int):
            nonlocal plain_start
            if upto > plain_start:
                self._insert_text(text[plain_start:upto])
            plain_start = upto + 1  # caller sẽ +1 sau khi gọi (mặc định)

        while i < n:
            ch = text[i]
            if ch == "\x1b":
                # flush text trước escape
                if i > plain_start:
                    self._insert_text(text[plain_start:i])
                consumed = self._parse_escape(text, i)
                if consumed is None:
                    # incomplete sequence — giữ phần còn lại cho lần sau
                    self._buffer = text[i:]
                    return
                i += consumed
                plain_start = i
                continue
            if ch == "\r":
                if i > plain_start:
                    self._insert_text(text[plain_start:i])
                self._cr()
                i += 1
                plain_start = i
                continue
            if ch == "\b":
                if i > plain_start:
                    self._insert_text(text[plain_start:i])
                self._backspace()
                i += 1
                plain_start = i
                continue
            if ch == "\x07":  # BEL: bỏ qua
                if i > plain_start:
                    self._insert_text(text[plain_start:i])
                i += 1
                plain_start = i
                continue
            i += 1

        if n > plain_start:
            self._insert_text(text[plain_start:n])

    # --------------- text insertion with overwrite ---------------
    def _insert_text(self, s: str) -> None:
        if not s:
            return
        cursor = self.edit.textCursor()
        # nếu cursor không ở cuối → overwrite (replace) characters trên dòng đó
        # nếu ở cuối → append bình thường
        doc_end = self.edit.document().characterCount() - 1
        fmt = self._current_format()
        # Tách s theo newline để xử lý overwrite per-line
        parts = s.split("\n")
        for idx, part in enumerate(parts):
            if part:
                if cursor.position() < doc_end:
                    # overwrite: xoá đúng len(part) ký tự (hoặc đến cuối block)
                    # tránh overwrite qua line break
                    remaining_in_block = cursor.block().length() - 1 - cursor.positionInBlock()
                    overwrite_len = min(len(part), remaining_in_block)
                    if overwrite_len > 0:
                        cursor.movePosition(
                            QTextCursor.Right,
                            QTextCursor.KeepAnchor,
                            overwrite_len,
                        )
                        cursor.removeSelectedText()
                    cursor.insertText(part, fmt)
                else:
                    cursor.insertText(part, fmt)
                # cập nhật doc_end vì document có thể đã dài thêm
                doc_end = self.edit.document().characterCount() - 1
            if idx < len(parts) - 1:
                # giữa các part có "\n" → newline
                cursor.movePosition(QTextCursor.EndOfBlock)
                cursor.insertText("\n")
                doc_end = self.edit.document().characterCount() - 1
        self.edit.setTextCursor(cursor)
        self.edit.ensureCursorVisible()

    # --------------- cursor control ---------------
    def _cr(self) -> None:
        cursor = self.edit.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock)
        self.edit.setTextCursor(cursor)

    def _backspace(self) -> None:
        cursor = self.edit.textCursor()
        if cursor.positionInBlock() > 0:
            cursor.movePosition(QTextCursor.Left)
        self.edit.setTextCursor(cursor)

    # --------------- escape parsing ---------------
    def _parse_escape(self, text: str, i: int) -> int | None:
        """
        Parse 1 escape bắt đầu tại text[i]=='\x1b'.
        Trả về số ký tự đã consume hoặc None nếu chưa đủ data.
        """
        n = len(text)
        if i + 1 >= n:
            return None
        ch1 = text[i + 1]

        if ch1 == "[":
            # CSI: ESC [ params final
            j = i + 2
            params = []
            while j < n:
                c = text[j]
                if "0" <= c <= "9" or c in ";?:":
                    params.append(c)
                    j += 1
                elif 0x20 <= ord(c) <= 0x2F:
                    # intermediate bytes
                    params.append(c)
                    j += 1
                elif 0x40 <= ord(c) <= 0x7E:
                    # final byte
                    self._handle_csi(c, "".join(params))
                    return j - i + 1
                else:
                    # invalid
                    return j - i + 1
            return None

        if ch1 == "]":
            # OSC: kết thúc bằng BEL (0x07) hoặc ST (ESC \)
            j = i + 2
            while j < n:
                c = text[j]
                if c == "\x07":
                    return j - i + 1
                if c == "\x1b" and j + 1 < n and text[j + 1] == "\\":
                    return j - i + 2
                j += 1
            return None

        if ch1 in "()":
            # charset switch: ESC ( B  hoặc  ESC ) 0
            if i + 2 >= n:
                return None
            return 3

        # short escapes (ESC =, ESC >, ESC c, ...)
        if ch1 == "c":
            # full reset
            self._reset_attrs()
            self.edit.clear()
        return 2

    # --------------- CSI handlers ---------------
    def _handle_csi(self, final: str, params: str) -> None:
        if final == "m":
            self._sgr(params)
            return
        if final == "K":
            self._erase_line(params)
            return
        if final == "J":
            self._erase_display(params)
            return
        # các sequence khác — bỏ qua an toàn (cursor positioning, modes, ...)

    # --------------- SGR ---------------
    def _sgr(self, params: str) -> None:
        if not params or params == "":
            codes = [0]
        else:
            try:
                codes = [int(p) if p else 0 for p in params.split(";")]
            except ValueError:
                return

        i = 0
        while i < len(codes):
            c = codes[i]
            if c == 0:
                self._reset_attrs()
            elif c == 1:
                self.bold = True
            elif c == 2:
                self.dim = True
            elif c == 3:
                self.italic = True
            elif c == 4:
                self.underline = True
            elif c == 7:
                self.inverse = True
            elif c == 22:
                self.bold = False
                self.dim = False
            elif c == 23:
                self.italic = False
            elif c == 24:
                self.underline = False
            elif c == 27:
                self.inverse = False
            elif 30 <= c <= 37:
                self.fg = _BASIC_COLORS[c - 30]
            elif c == 38 and i + 1 < len(codes):
                # extended fg
                mode = codes[i + 1]
                if mode == 5 and i + 2 < len(codes):
                    self.fg = _xterm_256(codes[i + 2])
                    i += 2
                elif mode == 2 and i + 4 < len(codes):
                    self.fg = QColor(codes[i + 2], codes[i + 3], codes[i + 4])
                    i += 4
                else:
                    i += 1
            elif c == 39:
                self.fg = QColor(self.default_fg)
            elif 40 <= c <= 47:
                self.bg = _BASIC_COLORS[c - 40]
            elif c == 48 and i + 1 < len(codes):
                mode = codes[i + 1]
                if mode == 5 and i + 2 < len(codes):
                    self.bg = _xterm_256(codes[i + 2])
                    i += 2
                elif mode == 2 and i + 4 < len(codes):
                    self.bg = QColor(codes[i + 2], codes[i + 3], codes[i + 4])
                    i += 4
                else:
                    i += 1
            elif c == 49:
                self.bg = QColor(self.default_bg) if self.default_bg else None
            elif 90 <= c <= 97:
                self.fg = _BASIC_COLORS[8 + (c - 90)]
            elif 100 <= c <= 107:
                self.bg = _BASIC_COLORS[8 + (c - 100)]
            i += 1

    # --------------- erase ---------------
    def _erase_line(self, params: str) -> None:
        mode = int(params or "0")
        cursor = self.edit.textCursor()
        if mode == 0:
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
        elif mode == 1:
            cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
        elif mode == 2:
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
        self.edit.setTextCursor(cursor)

    def _erase_display(self, params: str) -> None:
        mode = int(params or "0")
        if mode == 2 or mode == 3:
            self.edit.clear()
        elif mode == 0:
            # from cursor to end of doc
            cursor = self.edit.textCursor()
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            self.edit.setTextCursor(cursor)
        elif mode == 1:
            cursor = self.edit.textCursor()
            cursor.movePosition(QTextCursor.Start, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            self.edit.setTextCursor(cursor)
