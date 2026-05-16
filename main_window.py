"""Cửa sổ chính của Terminal Manager - Shell."""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime

IS_WINDOWS = sys.platform == "win32"

from PyQt5.QtCore import Qt, QEvent, QTimer
from PyQt5.QtGui import QFont, QIcon, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QPlainTextEdit,
    QToolBar,
    QAction,
    QInputDialog,
    QMessageBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QFormLayout,
    QShortcut,
    QCheckBox,
    QMenu,
    QToolButton,
    QStackedWidget,
    QSpinBox,
)

from favorites import Favorite, FavoritesStore
from terminal_tab import (
    TerminalTab,
    CommandEdit,
    PasswordEdit,
    looks_like_password_prompt,
    TERMINAL_MIME,
)
try:
    from terminal_view import TerminalView
except ImportError:
    TerminalView = None  # type: ignore
from settings import AppSettings, TabState, Geometry
from i18n import t, set_language, get_language
import theme as app_theme
from pty_backend import ConPtyBackend, find_wsl, find_git_bash
from tool_scanner import ToolInfo, detect_tools


APP_DIR = os.path.dirname(os.path.abspath(__file__))
FAVORITES_PATH = os.path.join(APP_DIR, "favorites.json")
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")


# ---------------- Dialog thêm/sửa favorite ----------------
class FavoriteDialog(QDialog):
    def __init__(self, parent=None, fav: Favorite | None = None):
        super().__init__(parent)
        self.setWindowTitle(t("fav_dialog_title"))
        self.setMinimumWidth(480)

        layout = QFormLayout(self)
        self.ed_name = QLineEdit(fav.name if fav else "")
        self.ed_cmd = QLineEdit(fav.command if fav else "")
        self.cb_shell = QComboBox()
        self.cb_shell.addItems(["cmd", "powershell", "wsl", "bash", "zsh", "fish", "sh", "any"])
        if fav:
            idx = self.cb_shell.findText(fav.shell)
            if idx >= 0:
                self.cb_shell.setCurrentIndex(idx)

        layout.addRow(t("fav_field_name"), self.ed_name)
        layout.addRow(t("fav_field_command"), self.ed_cmd)
        layout.addRow(t("fav_field_shell"), self.cb_shell)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def to_favorite(self) -> Favorite:
        return Favorite(
            name=self.ed_name.text().strip() or t("fav_unnamed"),
            command=self.ed_cmd.text(),
            shell=self.cb_shell.currentText(),
        )


# ---------------- Settings dialog ----------------
class SettingsDialog(QDialog):
    """Dialog cho phép đổi theme, ngôn ngữ, bật/tắt khôi phục session."""

    def __init__(self, parent=None, current: AppSettings | None = None):
        super().__init__(parent)
        self.setWindowTitle(t("settings_title"))
        self.setMinimumWidth(420)
        current = current or AppSettings()

        form = QFormLayout(self)

        # theme
        self.cb_theme = QComboBox()
        self._theme_keys = ["system", "light", "dark"]
        self._theme_labels = [
            t("settings_theme_system"),
            t("settings_theme_light"),
            t("settings_theme_dark"),
        ]
        for k, lbl in zip(self._theme_keys, self._theme_labels):
            self.cb_theme.addItem(lbl, k)
        if current.theme in self._theme_keys:
            self.cb_theme.setCurrentIndex(self._theme_keys.index(current.theme))
        form.addRow(t("settings_theme"), self.cb_theme)

        # language
        self.cb_lang = QComboBox()
        self._lang_keys = ["vi", "en"]
        self.cb_lang.addItem(t("settings_lang_vi"), "vi")
        self.cb_lang.addItem(t("settings_lang_en"), "en")
        if current.language in self._lang_keys:
            self.cb_lang.setCurrentIndex(self._lang_keys.index(current.language))
        form.addRow(t("settings_language"), self.cb_lang)

        lang_note = QLabel(t("settings_lang_note"))
        lang_note.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", lang_note)

        # backend
        self.cb_backend = QComboBox()
        self._backend_keys = ["auto", "conpty", "qprocess"]
        self.cb_backend.addItem(t("settings_backend_auto"), "auto")
        self.cb_backend.addItem(t("settings_backend_conpty"), "conpty")
        self.cb_backend.addItem(t("settings_backend_qprocess"), "qprocess")
        if current.backend in self._backend_keys:
            self.cb_backend.setCurrentIndex(self._backend_keys.index(current.backend))
        form.addRow(t("settings_backend"), self.cb_backend)

        backend_note_text = t("settings_backend_note")
        if not ConPtyBackend.is_available():
            backend_note_text += "\n" + t("settings_backend_missing")
        backend_note = QLabel(backend_note_text)
        backend_note.setStyleSheet("color: #888; font-size: 11px;")
        backend_note.setWordWrap(True)
        form.addRow("", backend_note)

        # restore session
        self.chk_restore = QCheckBox(t("settings_restore"))
        self.chk_restore.setChecked(current.restore_session)
        form.addRow("", self.chk_restore)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def apply_to(self, settings: AppSettings) -> None:
        settings.theme = self.cb_theme.currentData() or "system"
        settings.language = self.cb_lang.currentData() or "vi"
        settings.backend = self.cb_backend.currentData() or "auto"
        settings.restore_session = self.chk_restore.isChecked()


# ---------------- Page tab widget với drop support ----------------
class PageTabWidget(QTabWidget):
    """QTabWidget cho pagination grid — chấp nhận drop terminal để chuyển page."""

    def __init__(self, main_window: "MainWindow", page_capacity: int, parent=None):
        super().__init__(parent)
        self._mw = main_window
        self._page_cap = max(1, page_capacity)
        self.setTabsClosable(False)
        self.setMovable(False)
        self.setDocumentMode(True)
        bar = self.tabBar()
        bar.setAcceptDrops(True)
        bar.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.tabBar():
            etype = event.type()
            if etype == QEvent.DragEnter:
                if event.mimeData().hasFormat(TERMINAL_MIME):
                    event.acceptProposedAction()
                    return True
            elif etype == QEvent.DragMove:
                if event.mimeData().hasFormat(TERMINAL_MIME):
                    event.acceptProposedAction()
                    return True
            elif etype == QEvent.Drop:
                if event.mimeData().hasFormat(TERMINAL_MIME):
                    page = self.tabBar().tabAt(event.pos())
                    if page >= 0:
                        src_id = int(
                            bytes(event.mimeData().data(TERMINAL_MIME)).decode("utf-8")
                        )
                        target_idx = page * self._page_cap
                        self._mw.handle_terminal_drop_on_cell(src_id, target_idx)
                    event.acceptProposedAction()
                    return True
        return super().eventFilter(obj, event)


# ---------------- Empty cell placeholder ----------------
class EmptyCellPlaceholder(QWidget):
    """Ô trống trong grid mode — có nút mở terminal mới, nhận drop terminal."""

    def __init__(self, main_window: "MainWindow", target_index: int = -1, parent=None):
        super().__init__(parent)
        self._mw = main_window
        self.target_index = target_index  # vị trí trong _terminals nếu nhận drop
        self.setAcceptDrops(True)
        self.setMinimumSize(120, 80)
        # background sáng hơn để phân biệt rõ với terminal output
        self.setAutoFillBackground(False)
        self.setStyleSheet(
            "EmptyCellPlaceholder { background-color: #2a2a2a; "
            "border: 1px dashed #555; }"
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel(t("empty_cell_title"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "color: #888; font-style: italic; background: transparent; border: none;"
        )
        layout.addWidget(title)

        # Nút mở terminal với menu popup chọn shell
        btn = QToolButton()
        btn.setText(t("empty_cell_open"))
        btn.setPopupMode(QToolButton.InstantPopup)
        btn.setStyleSheet(
            "QToolButton { background-color: #3a3a3a; color: #ddd; "
            "padding: 6px 12px; border: 1px solid #555; border-radius: 3px; }"
            "QToolButton:hover { background-color: #4a4a4a; }"
            "QToolButton::menu-indicator { image: none; }"
        )

        menu = QMenu(btn)
        if IS_WINDOWS:
            a_cmd = menu.addAction(t("menu_new_cmd"))
            a_cmd.triggered.connect(main_window.add_cmd_tab)
            a_ps = menu.addAction(t("menu_new_ps"))
            a_ps.triggered.connect(main_window.add_ps_tab)
            a_wsl = menu.addAction(t("menu_new_wsl"))
            a_wsl.triggered.connect(main_window.add_wsl_tab)
            a_wsl.setEnabled(find_wsl() is not None)
            a_bash = menu.addAction(t("menu_new_bash"))
            a_bash.triggered.connect(main_window.add_bash_tab)
            a_bash.setEnabled(find_git_bash() is not None)
        else:
            a_bash = menu.addAction(t("menu_new_unix_bash"))
            a_bash.triggered.connect(main_window.add_bash_tab)
            a_bash.setEnabled(shutil.which("bash") is not None)
            a_zsh = menu.addAction(t("menu_new_zsh"))
            a_zsh.triggered.connect(main_window.add_zsh_tab)
            a_zsh.setEnabled(shutil.which("zsh") is not None)
            a_fish = menu.addAction(t("menu_new_fish"))
            a_fish.triggered.connect(main_window.add_fish_tab)
            a_fish.setEnabled(shutil.which("fish") is not None)
            a_sh = menu.addAction(t("menu_new_sh"))
            a_sh.triggered.connect(main_window.add_sh_tab)
            a_sh.setEnabled(shutil.which("sh") is not None)
            if shutil.which("pwsh"):
                a_ps = menu.addAction(t("menu_new_ps"))
                a_ps.triggered.connect(main_window.add_ps_tab)
        btn.setMenu(menu)

        layout.addWidget(btn, 0, Qt.AlignCenter)

        # Right-click anywhere in the cell → cùng menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self._context_menu = menu
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos) -> None:
        self._context_menu.exec_(self.mapToGlobal(pos))

    # ---------- Drag-and-drop drop target ----------
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(TERMINAL_MIME):
            event.acceptProposedAction()
            self.setStyleSheet(
                "EmptyCellPlaceholder { background-color: #2e4a3a; "
                "border: 2px solid #4ec9b0; }"
            )
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            "EmptyCellPlaceholder { background-color: #2a2a2a; "
            "border: 1px dashed #555; }"
        )

    def dropEvent(self, event):
        self.setStyleSheet(
            "EmptyCellPlaceholder { background-color: #2a2a2a; "
            "border: 1px dashed #555; }"
        )
        if not event.mimeData().hasFormat(TERMINAL_MIME):
            event.ignore()
            return
        src_id = int(bytes(event.mimeData().data(TERMINAL_MIME)).decode("utf-8"))
        if hasattr(self._mw, "handle_terminal_drop_on_cell"):
            self._mw.handle_terminal_drop_on_cell(src_id, self.target_index)
        event.acceptProposedAction()


# ---------------- Scan CLI tools dialog ----------------
class ScanToolsDialog(QDialog):
    """Dialog hiện danh sách CLI tools tìm được, cho user chọn để add vào favorites."""

    def __init__(self, parent, tools: list[ToolInfo]):
        super().__init__(parent)
        self.setWindowTitle(t("fav_scan_title"))
        self.setMinimumSize(720, 520)

        layout = QVBoxLayout(self)
        info = QLabel(t("fav_scan_info", n=len(tools)))
        info.setWordWrap(True)
        layout.addWidget(info)

        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText(t("fav_scan_search"))
        self.ed_search.setClearButtonEnabled(True)
        self.ed_search.textChanged.connect(self._filter)
        layout.addWidget(self.ed_search)

        self.list_w = QListWidget()
        self._tools = tools
        for tool in tools:
            text = (
                f"[{tool.category}] {tool.display_name}\n"
                f"    → {tool.command}    ({tool.path})"
            )
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, tool)
            self.list_w.addItem(item)
        layout.addWidget(self.list_w, 1)

        row = QHBoxLayout()
        btn_all = QPushButton(t("fav_scan_select_all"))
        btn_all.clicked.connect(self._select_all)
        row.addWidget(btn_all)
        btn_none = QPushButton(t("fav_scan_select_none"))
        btn_none.clicked.connect(self._select_none)
        row.addWidget(btn_none)
        row.addStretch(1)
        layout.addLayout(row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.list_w.count()):
            item = self.list_w.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _select_all(self) -> None:
        for i in range(self.list_w.count()):
            item = self.list_w.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)

    def _select_none(self) -> None:
        for i in range(self.list_w.count()):
            item = self.list_w.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Unchecked)

    def selected_tools(self) -> list[ToolInfo]:
        result: list[ToolInfo] = []
        for i in range(self.list_w.count()):
            item = self.list_w.item(i)
            if item.checkState() == Qt.Checked:
                result.append(item.data(Qt.UserRole))
        return result


# ---------------- Cửa sổ chính ----------------
class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings | None = None):
        super().__init__()
        self.settings = settings or AppSettings()
        self.setWindowTitle(t("app_title"))
        self.resize(self.settings.geometry.w, self.settings.geometry.h)

        self.favorites = FavoritesStore(FAVORITES_PATH)
        self._cmd_counter = 0
        self._ps_counter = 0
        self._wsl_counter = 0
        self._bash_counter = 0
        self._zsh_counter = 0
        self._fish_counter = 0
        self._sh_counter = 0
        self._unix_bash_counter = 0

        # Authoritative list of terminals — đảm bảo nhất quán giữa các mode bố cục.
        self._terminals: list[TerminalTab] = []
        # Terminal đang active — TẤT CẢ command (favorites, run script, ...) đều
        # áp dụng cho terminal này. Trong tab mode = tab đang chọn. Trong grid mode
        # = terminal được click/focus gần nhất.
        self._active_terminal: TerminalTab | None = None

        # Bố cục hiện tại: "tabs" | "grid:RxC".
        # Migrate cols:N / rows:N (format cũ) → grid:1xN / grid:Nx1.
        _saved_layout = self.settings.layout_mode or "tabs"
        if _saved_layout.startswith("cols:"):
            try:
                _n = max(1, int(_saved_layout.split(":", 1)[1]))
                _saved_layout = f"grid:1x{_n}"
            except Exception:
                _saved_layout = "tabs"
        elif _saved_layout.startswith("rows:"):
            try:
                _n = max(1, int(_saved_layout.split(":", 1)[1]))
                _saved_layout = f"grid:{_n}x1"
            except Exception:
                _saved_layout = "tabs"
        self._layout_mode: str = _saved_layout

        # log lưu dạng (timestamp, source_label, line) để có thể lọc lại
        self._log_entries: list[tuple[str, str, str]] = []
        # bộ nhớ các label phiên đã từng xuất hiện để build dropdown lọc
        self._known_sources: list[str] = []
        # Buffer per-label: gom các chunk output thành line hoàn chỉnh trước khi
        # log. Tránh log từng ký tự khi TUI mode echo từng phím gõ.
        self._log_buffers: dict[str, str] = {}

        # Lịch sử lệnh dùng chung cho ô input
        self._history: list[str] = []
        self._history_idx: int = -1
        # Trạng thái password mode của ô input chung
        self._password_mode: bool = False

        self._build_ui()
        self._build_toolbar()
        self._build_shortcuts()

        # Theo dõi focus toàn app để cập nhật active terminal
        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._on_focus_changed)

        # Mở tab khi khởi động: ưu tiên khôi phục session nếu có
        saved_layout = self._layout_mode
        self._layout_mode = "tabs"
        if self.settings.restore_session and self.settings.last_tabs:
            for ts in self.settings.last_tabs:
                self._restore_tab(ts)
        else:
            # Default shell theo platform
            if IS_WINDOWS:
                self.add_cmd_tab()
            else:
                self.add_bash_tab()
        if saved_layout != "tabs":
            self._set_layout(saved_layout)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # splitter dọc: phần trên (sidebar + tabs), phần dưới (combined log)
        v_split = QSplitter(Qt.Vertical)
        root.addWidget(v_split, 1)

        # splitter ngang trên: sidebar | tabs
        h_split = QSplitter(Qt.Horizontal)
        v_split.addWidget(h_split)

        # ----- sidebar favorites -----
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_fav_title = QLabel(f"<b>{t('fav_title')}</b>")
        side_layout.addWidget(self.lbl_fav_title)

        # ô tìm kiếm favorites
        self.ed_fav_search = QLineEdit()
        self.ed_fav_search.setPlaceholderText(t("fav_search_placeholder"))
        self.ed_fav_search.setClearButtonEnabled(True)
        self.ed_fav_search.textChanged.connect(self._refresh_favorites_list)
        side_layout.addWidget(self.ed_fav_search)

        # filter theo shell (mặc định "auto" = theo tab hiện tại)
        shell_filter_row = QHBoxLayout()
        shell_filter_row.setContentsMargins(0, 0, 0, 0)
        shell_filter_row.addWidget(QLabel(t("fav_filter_shell_label")))
        self.cb_fav_shell = QComboBox()
        # (label_visible, value)
        self.cb_fav_shell.addItem("Auto", "auto")
        self.cb_fav_shell.addItem(t("fav_show_all"), "all")
        self.cb_fav_shell.addItem("cmd", "cmd")
        self.cb_fav_shell.addItem("powershell", "powershell")
        self.cb_fav_shell.addItem("wsl", "wsl")
        self.cb_fav_shell.addItem("bash", "bash")
        self.cb_fav_shell.currentIndexChanged.connect(self._refresh_favorites_list)
        shell_filter_row.addWidget(self.cb_fav_shell, 1)
        side_layout.addLayout(shell_filter_row)

        self.list_fav = QListWidget()
        self.list_fav.itemDoubleClicked.connect(self._run_selected_favorite)
        # Khi user select 1 favorite → load command vào ô nhập để edit/gửi
        self.list_fav.currentItemChanged.connect(self._on_favorite_item_selected)
        side_layout.addWidget(self.list_fav, 1)

        row = QHBoxLayout()
        btn_run = QPushButton(t("fav_run"))
        btn_run.clicked.connect(self._run_selected_favorite)
        row.addWidget(btn_run)
        btn_add = QPushButton(t("fav_add"))
        btn_add.clicked.connect(self._add_favorite)
        row.addWidget(btn_add)
        side_layout.addLayout(row)

        row2 = QHBoxLayout()
        btn_edit = QPushButton(t("fav_edit"))
        btn_edit.clicked.connect(self._edit_favorite)
        row2.addWidget(btn_edit)
        btn_del = QPushButton(t("fav_delete"))
        btn_del.clicked.connect(self._delete_favorite)
        row2.addWidget(btn_del)
        side_layout.addLayout(row2)

        # Nút quét CLI tools để add hàng loạt
        btn_scan = QPushButton(t("fav_scan_btn"))
        btn_scan.setToolTip(t("fav_scan_btn_tip"))
        btn_scan.clicked.connect(self._scan_and_add_tools)
        side_layout.addWidget(btn_scan)

        h_split.addWidget(side)

        # ----- tab widget (cho tab mode) -----
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        # đổi tab → tự lọc favorites theo shell của tab mới
        self.tabs.currentChanged.connect(self._on_current_tab_changed)
        # double-click vào header tab để đổi tên
        self.tabs.tabBarDoubleClicked.connect(self._rename_tab)
        # right-click trên tab → context menu
        tab_bar = self.tabs.tabBar()
        tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._show_tab_context_menu)

        # ----- grid container (cho mọi bố cục dạng lưới) -----
        self._grid_container = QWidget()
        self._grid_layout = QVBoxLayout(self._grid_container)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)

        # ----- stacked widget chuyển giữa tab mode <-> grid mode -----
        self._tabs_stack = QStackedWidget()
        self._tabs_stack.addWidget(self.tabs)            # index 0 = tabs
        self._tabs_stack.addWidget(self._grid_container) # index 1 = grid

        # ----- ô nhập lệnh CHUNG (1 cho tất cả terminal) -----
        self._input_panel = self._build_input_panel()
        # cố định height cho input panel — không dùng max + size policy
        # combo có thể gây Qt layout bug
        self._input_panel.setFixedHeight(120)

        # Cột bên phải: dùng QVBoxLayout, terminals stretch=1, input cố định
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        right_layout.addWidget(self._tabs_stack, 1)
        right_layout.addWidget(self._input_panel, 0)
        h_split.addWidget(right_col)
        # đảm bảo right_col và children visible
        right_col.show()
        self._tabs_stack.show()
        self._input_panel.show()

        h_split.setStretchFactor(0, 0)
        h_split.setStretchFactor(1, 1)
        h_split.setSizes([240, 1000])

        # ----- combined log -----
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)

        log_header = QHBoxLayout()
        log_header.addWidget(QLabel(f"<b>{t('log_title')}</b>"))

        log_header.addWidget(QLabel(t("log_session")))
        self.cb_log_filter = QComboBox()
        self.cb_log_filter.addItem(t("log_all"))
        self.cb_log_filter.setMinimumWidth(140)
        self.cb_log_filter.currentTextChanged.connect(self._rerender_log)
        log_header.addWidget(self.cb_log_filter)

        self.ed_log_search = QLineEdit()
        self.ed_log_search.setPlaceholderText(t("log_search_placeholder"))
        self.ed_log_search.setClearButtonEnabled(True)
        self.ed_log_search.textChanged.connect(self._rerender_log)
        log_header.addWidget(self.ed_log_search, 1)

        btn_clear_log = QPushButton(t("log_clear"))
        btn_clear_log.clicked.connect(self._clear_log)
        log_header.addWidget(btn_clear_log)
        btn_save_log = QPushButton(t("log_save"))
        btn_save_log.clicked.connect(self._save_combined_log)
        log_header.addWidget(btn_save_log)
        log_layout.addLayout(log_header)

        self.combined_log = QPlainTextEdit()
        self.combined_log.setReadOnly(True)
        mono = QFont("Consolas", 9)
        mono.setStyleHint(QFont.Monospace)
        self.combined_log.setFont(mono)
        # không gán stylesheet cứng — để combined_log follow theme của app
        log_layout.addWidget(self.combined_log, 1)

        v_split.addWidget(log_container)
        v_split.setStretchFactor(0, 3)
        v_split.setStretchFactor(1, 1)
        v_split.setSizes([600, 200])

        self._refresh_favorites_list()

    # ---------- Shared input panel ----------
    def _build_input_panel(self) -> QWidget:
        """Tạo panel chứa ô nhập lệnh dùng chung cho mọi terminal."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        mono = QFont("Consolas", 10)
        mono.setStyleHint(QFont.Monospace)

        bar = QHBoxLayout()
        self._input_prompt_label = QLabel("›")
        self._input_prompt_label.setStyleSheet("color: #4ec9b0; font-family: Consolas;")
        bar.addWidget(self._input_prompt_label)

        # Label cho biết command sẽ đi đến terminal nào
        self._input_target_label = QLabel("(no active terminal)")
        self._input_target_label.setStyleSheet("color: #888; font-size: 11px;")
        bar.addWidget(self._input_target_label, 1)

        self._input_hint_label = QLabel(t("input_hint"))
        self._input_hint_label.setStyleSheet("color: #888; font-size: 11px;")
        bar.addWidget(self._input_hint_label)

        self._input_default_hint = self._input_hint_label.text()

        self.btn_input_password = QPushButton("🔒")
        self.btn_input_password.setFixedWidth(36)
        self.btn_input_password.setCheckable(True)
        self.btn_input_password.setToolTip(t("input_btn_password_tip"))
        self.btn_input_password.toggled.connect(self._on_password_button_toggled)
        bar.addWidget(self.btn_input_password)

        self.btn_input_ctrlc = QPushButton("Ctrl+C")
        self.btn_input_ctrlc.setFixedWidth(70)
        self.btn_input_ctrlc.setToolTip("Send Ctrl+C to the active terminal")
        self.btn_input_ctrlc.clicked.connect(self._send_ctrl_c_to_active)
        bar.addWidget(self.btn_input_ctrlc)

        # Nút xoá hết nội dung ô nhập
        self.btn_input_clear = QPushButton("✕")
        self.btn_input_clear.setFixedWidth(36)
        self.btn_input_clear.setToolTip("Xoá hết nội dung trong ô nhập (Ctrl+Backspace)")
        self.btn_input_clear.clicked.connect(self._clear_input)
        bar.addWidget(self.btn_input_clear)

        self.btn_input_send = QPushButton("Send")
        self.btn_input_send.setFixedWidth(70)
        self.btn_input_send.clicked.connect(self._send_current_input)
        bar.addWidget(self.btn_input_send)

        layout.addLayout(bar)

        # CommandEdit (đa dòng)
        self.input = CommandEdit()
        self.input.setFont(mono)
        self.input.setPlaceholderText(t("input_placeholder"))
        self.input.setStyleSheet(
            "background-color: #252526; color: #d4d4d4; border: 1px solid #333;"
        )
        self.input.submitted.connect(self._send_current_input)
        self.input.history_prev.connect(lambda: self._cycle_history(-1))
        self.input.history_next.connect(lambda: self._cycle_history(1))
        layout.addWidget(self.input, 1)

        # PasswordEdit (hidden by default)
        self.input_password = PasswordEdit()
        self.input_password.setFont(mono)
        self.input_password.setPlaceholderText(t("input_password_placeholder"))
        self.input_password.setStyleSheet(
            "background-color: #2d2d30; color: #d4d4d4; border: 1px solid #5a8a5a;"
        )
        self.input_password.submitted.connect(self._submit_password)
        self.input_password.cancelled.connect(self._cancel_password)
        self.input_password.hide()
        layout.addWidget(self.input_password)

        # initial state: chưa có active terminal → disable
        self._update_input_target_label()
        return panel

    def _send_current_input(self) -> None:
        cmd = self.input.toPlainText()
        if not cmd.strip():
            return
        term = self._current_terminal()
        if term is None:
            return
        # ghi nhận vào history dùng chung
        if cmd and (not self._history or self._history[-1] != cmd):
            self._history.append(cmd)
        self._history_idx = len(self._history)
        term.send_command(cmd)
        self.input.clear()

    def _send_ctrl_c_to_active(self) -> None:
        term = self._current_terminal()
        if term is not None:
            term.send_ctrl_c()

    def _clear_input(self) -> None:
        """Xoá hết nội dung ô nhập (CommandEdit hoặc PasswordEdit tuỳ mode)."""
        if self._password_mode:
            self.input_password.clear()
            self.input_password.setFocus()
        else:
            self.input.clear()
            self.input.setFocus()

    def _cycle_history(self, direction: int) -> None:
        if not self._history:
            return
        self._history_idx = max(
            0, min(len(self._history) - 1, self._history_idx + direction)
        )
        self.input.setPlainText(self._history[self._history_idx])
        cursor = self.input.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.input.setTextCursor(cursor)

    # ---------- Password mode (shared input) ----------
    def _on_password_button_toggled(self, checked: bool) -> None:
        # nút toggle do user nhấn — chuyển mode tương ứng
        self._set_password_mode(checked)

    def _set_password_mode(self, active: bool) -> None:
        if active == self._password_mode:
            # đồng bộ button state nếu khác
            if self.btn_input_password.isChecked() != active:
                self.btn_input_password.blockSignals(True)
                self.btn_input_password.setChecked(active)
                self.btn_input_password.blockSignals(False)
            return
        self._password_mode = active
        if self.btn_input_password.isChecked() != active:
            self.btn_input_password.blockSignals(True)
            self.btn_input_password.setChecked(active)
            self.btn_input_password.blockSignals(False)

        if active:
            self.input.hide()
            self.input_password.clear()
            self.input_password.show()
            self.input_password.setFocus()
            self._input_hint_label.setText(t("input_password_hint"))
            self._input_hint_label.setStyleSheet("color: #5a8a5a; font-size: 11px;")
        else:
            self.input_password.hide()
            self.input_password.clear()
            self.input.show()
            self.input.setFocus()
            self._input_hint_label.setText(self._input_default_hint)
            self._input_hint_label.setStyleSheet("color: #888; font-size: 11px;")

    def _submit_password(self) -> None:
        term = self._current_terminal()
        if term is None:
            self._set_password_mode(False)
            return
        secret = self.input_password.text()
        term.send_password(secret)
        # reset detection buffer nên không re-trigger ngay
        term.clear_recent_output()
        self.input_password.clear()
        self._set_password_mode(False)

    def _cancel_password(self) -> None:
        # Cũng reset detection buffer để không re-trigger
        term = self._current_terminal()
        if term is not None:
            term.clear_recent_output()
        self._set_password_mode(False)

    def _update_input_target_label(self) -> None:
        active = self._active_terminal is not None
        if active:
            self._input_target_label.setText(f"→ {self._active_terminal.label}")
            self._input_target_label.setStyleSheet("color: #4ec9b0; font-size: 11px;")
        else:
            self._input_target_label.setText("(no active terminal)")
            self._input_target_label.setStyleSheet("color: #888; font-size: 11px;")
        self.input.setEnabled(active)
        self.input_password.setEnabled(active)
        self.btn_input_send.setEnabled(active)
        self.btn_input_ctrlc.setEnabled(active)
        self.btn_input_password.setEnabled(active)
        if hasattr(self, "btn_input_clear"):
            self.btn_input_clear.setEnabled(active)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        # Toolbar shells khác nhau theo platform
        if IS_WINDOWS:
            a_cmd = QAction(t("menu_new_cmd"), self)
            a_cmd.setShortcut("Ctrl+T")
            a_cmd.triggered.connect(self.add_cmd_tab)
            tb.addAction(a_cmd)

            a_ps = QAction(t("menu_new_ps"), self)
            a_ps.setShortcut("Ctrl+Shift+T")
            a_ps.triggered.connect(self.add_ps_tab)
            tb.addAction(a_ps)

            a_wsl = QAction(t("menu_new_wsl"), self)
            a_wsl.triggered.connect(self.add_wsl_tab)
            a_wsl.setEnabled(find_wsl() is not None)
            tb.addAction(a_wsl)

            a_bash = QAction(t("menu_new_bash"), self)
            a_bash.triggered.connect(self.add_bash_tab)
            a_bash.setEnabled(find_git_bash() is not None)
            tb.addAction(a_bash)
        else:
            # Unix (Linux/macOS)
            a_bash = QAction(t("menu_new_unix_bash"), self)
            a_bash.setShortcut("Ctrl+T")
            a_bash.triggered.connect(self.add_bash_tab)
            a_bash.setEnabled(shutil.which("bash") is not None)
            tb.addAction(a_bash)

            a_zsh = QAction(t("menu_new_zsh"), self)
            a_zsh.setShortcut("Ctrl+Shift+T")
            a_zsh.triggered.connect(self.add_zsh_tab)
            a_zsh.setEnabled(shutil.which("zsh") is not None)
            tb.addAction(a_zsh)

            a_fish = QAction(t("menu_new_fish"), self)
            a_fish.triggered.connect(self.add_fish_tab)
            a_fish.setEnabled(shutil.which("fish") is not None)
            tb.addAction(a_fish)

            a_sh = QAction(t("menu_new_sh"), self)
            a_sh.triggered.connect(self.add_sh_tab)
            a_sh.setEnabled(shutil.which("sh") is not None)
            tb.addAction(a_sh)

            # PowerShell Core (pwsh) nếu có
            if shutil.which("pwsh"):
                a_ps = QAction(t("menu_new_ps"), self)
                a_ps.triggered.connect(self.add_ps_tab)
                tb.addAction(a_ps)

        tb.addSeparator()

        a_run = QAction(t("menu_run_script"), self)
        a_run.setShortcut("Ctrl+R")
        a_run.setToolTip(t("menu_run_script_tip"))
        a_run.triggered.connect(self._run_script_file)
        tb.addAction(a_run)

        a_open_folder = QAction(t("menu_open_folder"), self)
        a_open_folder.setShortcut("Ctrl+O")
        a_open_folder.setToolTip(t("menu_open_folder_tip"))
        a_open_folder.triggered.connect(self._open_folder_in_shell)
        tb.addAction(a_open_folder)

        a_toggle_input = QAction(t("menu_toggle_input"), self)
        a_toggle_input.setShortcut("Ctrl+I")
        a_toggle_input.setToolTip(t("menu_toggle_input_tip"))
        a_toggle_input.setCheckable(True)
        a_toggle_input.triggered.connect(self._toggle_input_panel)
        # Mặc định: ẩn nếu TUI mode (pyte có sẵn), hiện nếu fallback
        a_toggle_input.setChecked(TerminalView is None)
        tb.addAction(a_toggle_input)
        self._action_toggle_input = a_toggle_input

        tb.addSeparator()

        # Layout menu
        btn_layout = QToolButton()
        btn_layout.setText(t("menu_layout"))
        btn_layout.setPopupMode(QToolButton.InstantPopup)
        layout_menu = QMenu(self)

        a_tabs = layout_menu.addAction(t("layout_tabs"))
        a_tabs.triggered.connect(lambda: self._set_layout("tabs"))

        # Mọi bố cục đa cửa sổ đều là grid (1×N = một hàng nhiều cột, N×1 = một
        # cột nhiều hàng, RxC = lưới chữ nhật). Loại bỏ cols/rows trùng lặp.
        layout_menu.addSeparator()
        for r, c in [
            (1, 2), (1, 3), (1, 4),       # 1 hàng × N cột
            (2, 1), (3, 1), (4, 1),       # N hàng × 1 cột
            (2, 2), (2, 3), (3, 2), (3, 3),  # lưới chữ nhật / vuông
        ]:
            a = layout_menu.addAction(t("layout_grid_rc", r=r, c=c))
            a.triggered.connect(lambda _checked=False, r=r, c=c: self._set_layout(f"grid:{r}x{c}"))

        layout_menu.addSeparator()
        a_custom = layout_menu.addAction(t("layout_custom"))
        a_custom.triggered.connect(self._open_custom_layout_dialog)

        layout_menu.addSeparator()
        a_equalize = layout_menu.addAction(t("layout_equalize"))
        a_equalize.setShortcut("Ctrl+=")
        a_equalize.triggered.connect(self._equalize_grid_cells)

        btn_layout.setMenu(layout_menu)
        tb.addWidget(btn_layout)

        tb.addSeparator()

        a_settings = QAction(t("menu_settings"), self)
        a_settings.setShortcut("Ctrl+,")
        a_settings.triggered.connect(self._open_settings_dialog)
        tb.addAction(a_settings)

        a_about = QAction(t("menu_about"), self)
        a_about.triggered.connect(self._show_about)
        tb.addAction(a_about)

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+W"), self, activated=self._close_current_tab)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self._clear_log)
        QShortcut(
            QKeySequence("Ctrl+Shift+P"), self,
            activated=lambda: self._set_password_mode(not self._password_mode),
        )
        # Áp dụng trạng thái mặc định cho input panel (ẩn nếu TUI mode)
        self._apply_input_panel_visibility(visible=TerminalView is None)

    def _toggle_input_panel(self, checked: bool) -> None:
        """Bật/tắt hiển thị ô nhập chung. Phím tắt Ctrl+I."""
        self._apply_input_panel_visibility(visible=checked)

    def _apply_input_panel_visibility(self, visible: bool) -> None:
        if not hasattr(self, "_input_panel"):
            return
        self._input_panel.setVisible(visible)
        if hasattr(self, "_action_toggle_input"):
            if self._action_toggle_input.isChecked() != visible:
                self._action_toggle_input.blockSignals(True)
                self._action_toggle_input.setChecked(visible)
                self._action_toggle_input.blockSignals(False)
        # Khi ẩn: clear text, exit password mode để không kẹt
        if not visible:
            if hasattr(self, "input"):
                self.input.clear()
            if self._password_mode:
                self._set_password_mode(False)

    # ---------- Tab management ----------
    def add_cmd_tab(self) -> TerminalTab:
        self._cmd_counter += 1
        label = f"CMD #{self._cmd_counter}"
        return self._add_terminal("cmd", label)

    def add_ps_tab(self) -> TerminalTab:
        self._ps_counter += 1
        label = f"PS #{self._ps_counter}"
        return self._add_terminal("powershell", label)

    def add_wsl_tab(self) -> TerminalTab | None:
        if find_wsl() is None:
            QMessageBox.warning(self, t("app_title"), t("wsl_not_found"))
            return None
        self._wsl_counter += 1
        label = f"WSL #{self._wsl_counter}"
        return self._add_terminal("wsl", label)

    def add_bash_tab(self) -> TerminalTab | None:
        # Trên Windows: Git Bash. Trên Unix: /bin/bash hệ thống.
        if IS_WINDOWS:
            if find_git_bash() is None:
                QMessageBox.warning(self, t("app_title"), t("bash_not_found"))
                return None
            self._bash_counter += 1
            label = f"Bash #{self._bash_counter}"
        else:
            if shutil.which("bash") is None:
                QMessageBox.warning(self, t("app_title"), t("shell_not_found", shell="bash"))
                return None
            self._unix_bash_counter += 1
            label = f"Bash #{self._unix_bash_counter}"
        return self._add_terminal("bash", label)

    def add_zsh_tab(self) -> TerminalTab | None:
        if shutil.which("zsh") is None:
            QMessageBox.warning(self, t("app_title"), t("shell_not_found", shell="zsh"))
            return None
        self._zsh_counter += 1
        label = f"Zsh #{self._zsh_counter}"
        return self._add_terminal("zsh", label)

    def add_fish_tab(self) -> TerminalTab | None:
        if shutil.which("fish") is None:
            QMessageBox.warning(self, t("app_title"), t("shell_not_found", shell="fish"))
            return None
        self._fish_counter += 1
        label = f"Fish #{self._fish_counter}"
        return self._add_terminal("fish", label)

    def add_sh_tab(self) -> TerminalTab | None:
        if shutil.which("sh") is None:
            QMessageBox.warning(self, t("app_title"), t("shell_not_found", shell="sh"))
            return None
        self._sh_counter += 1
        label = f"sh #{self._sh_counter}"
        return self._add_terminal("sh", label)

    def _add_terminal(self, shell: str, label: str) -> TerminalTab:
        term = TerminalTab(shell=shell, label=label, backend_pref=self.settings.backend)
        term.output_received.connect(self._on_terminal_output)
        term.close_requested.connect(lambda _t=term: self._close_terminal(_t))
        self._terminals.append(term)
        if self._layout_mode == "tabs":
            idx = self.tabs.addTab(term, label)
            self.tabs.setCurrentIndex(idx)
        else:
            self._rebuild_grid()
        # terminal mới luôn thành active
        self._set_active_terminal(term)
        self._log_system(f"[+] Mở tab {label}")
        return term

    # ---------- Drag-and-drop terminal reorder ----------
    def _find_terminal_by_id(self, term_id: int) -> TerminalTab | None:
        for t in self._terminals:
            if id(t) == term_id:
                return t
        return None

    def handle_terminal_drop(self, src_id: int, target_term: TerminalTab) -> None:
        """User kéo terminal có id=src_id, thả lên target_term → swap vị trí."""
        src = self._find_terminal_by_id(src_id)
        if src is None or src is target_term:
            return
        try:
            i = self._terminals.index(src)
            j = self._terminals.index(target_term)
        except ValueError:
            return
        # Defer thật sự rebuild để drop event complete trước, tránh race với reparent
        from PyQt5.QtCore import QTimer as _QTimer
        _QTimer.singleShot(0, lambda: self._swap_terminals(i, j))

    def handle_terminal_drop_on_cell(self, src_id: int, target_index: int) -> None:
        """User kéo terminal lên ô trống (target_index = vị trí đích)."""
        src = self._find_terminal_by_id(src_id)
        if src is None:
            return
        try:
            i = self._terminals.index(src)
        except ValueError:
            return
        from PyQt5.QtCore import QTimer as _QTimer
        _QTimer.singleShot(0, lambda: self._move_terminal(i, target_index))

    def _swap_terminals(self, i: int, j: int) -> None:
        if i == j:
            return
        if not (0 <= i < len(self._terminals) and 0 <= j < len(self._terminals)):
            return
        self._terminals[i], self._terminals[j] = self._terminals[j], self._terminals[i]
        self._log_system(f"[*] Swap terminal #{i} ↔ #{j}")
        self._rebuild_current_layout()

    def _move_terminal(self, src_idx: int, dst_idx: int) -> None:
        if not (0 <= src_idx < len(self._terminals)):
            return
        # cap dst_idx vào range hợp lệ — empty cell có thể nằm ngoài len(_terminals)
        target = min(max(0, dst_idx), len(self._terminals) - 1)
        if src_idx == target:
            return
        term = self._terminals.pop(src_idx)
        self._terminals.insert(target, term)
        self._log_system(f"[*] Move terminal #{src_idx} → #{target}")
        self._rebuild_current_layout()

    def _rebuild_current_layout(self) -> None:
        """Rebuild bố cục hiện tại sau khi _terminals đã đổi thứ tự."""
        if self._layout_mode == "tabs":
            # Xóa tabs hiện tại và thêm lại theo thứ tự mới.
            # KHÔNG gọi term.show() — QTabWidget tự quản visibility (chỉ tab
            # current mới visible). show() thủ công sẽ làm tất cả terminal cùng
            # hiện ra → status bars chồng nhau.
            self._detach_all_terminals()
            while self.tabs.count() > 0:
                self.tabs.removeTab(0)
            for term in self._terminals:
                self.tabs.addTab(term, term.label)
            # Khôi phục active tab nếu còn
            target = self._active_terminal if self._active_terminal in self._terminals else None
            if target is not None:
                idx = self.tabs.indexOf(target)
                if idx >= 0:
                    self.tabs.setCurrentIndex(idx)
        else:
            self._rebuild_grid()
        self._refresh_active_state()

    def _close_terminal(self, term: TerminalTab) -> None:
        """Đóng 1 terminal cụ thể — hoạt động ở cả tab mode và grid mode."""
        if term not in self._terminals:
            return
        try:
            term.stop_process()
        except Exception:
            pass
        # Flush phần buffer log còn lại của terminal này
        leftover = self._log_buffers.pop(term.label, "").rstrip("\r")
        if leftover:
            ts = datetime.now().strftime("%H:%M:%S")
            self._append_log_entry(ts, term.label, leftover)
        self._log_system(f"[-] Đóng tab {term.label}")
        self._terminals.remove(term)
        # nếu vừa đóng đúng terminal active → chọn cái đầu còn lại
        if term is self._active_terminal:
            self._active_terminal = self._terminals[0] if self._terminals else None
        # Detach khỏi bố cục hiện tại
        if self._layout_mode == "tabs":
            idx = self.tabs.indexOf(term)
            if idx >= 0:
                self.tabs.removeTab(idx)
        term.setParent(None)
        term.deleteLater()
        if self._layout_mode != "tabs":
            self._rebuild_grid()
        self._refresh_active_state()

    def _close_tab(self, index: int) -> None:
        """Slot cho tabCloseRequested của QTabWidget (chỉ áp dụng tab mode)."""
        widget = self.tabs.widget(index)
        if isinstance(widget, TerminalTab):
            self._close_terminal(widget)

    def _close_current_tab(self) -> None:
        term = self._current_terminal()
        if term is not None:
            self._close_terminal(term)

    def _current_terminal(self) -> TerminalTab | None:
        """Terminal đang ACTIVE — tất cả command đi vào đây."""
        if self._active_terminal is not None and self._active_terminal in self._terminals:
            return self._active_terminal
        # fallback: tab hiện tại (tab mode) hoặc terminal đầu (grid mode)
        if self._layout_mode == "tabs":
            w = self.tabs.currentWidget()
            if isinstance(w, TerminalTab):
                return w
        return self._terminals[0] if self._terminals else None

    def _set_active_terminal(self, term: TerminalTab | None) -> None:
        """Đặt terminal active + cập nhật highlight visual + ô nhập chung."""
        if term is not None and term not in self._terminals:
            return
        if term is self._active_terminal:
            return
        self._active_terminal = term
        self._refresh_active_state()

    def _refresh_active_state(self) -> None:
        """Cập nhật visual highlight + input panel cho terminal active hiện tại."""
        self._update_active_visual()
        self._sync_input_to_active()

    def _sync_input_to_active(self) -> None:
        """Cập nhật label đích + chuyển password mode theo trạng thái active terminal."""
        if not hasattr(self, "input"):
            return  # input panel chưa build xong
        self._update_input_target_label()
        # đồng bộ password mode với active terminal
        should_pw = (
            self._active_terminal is not None
            and self._active_terminal.is_at_password_prompt()
        )
        if should_pw != self._password_mode:
            self._set_password_mode(should_pw)

    def _update_active_visual(self) -> None:
        """
        Cập nhật highlight cho terminal đang active.
        Chỉ thay đổi status_label — tránh setStyleSheet trên QWidget cha vì có
        thể tương tác kỳ lạ với QSplitter sizing.
        """
        is_grid = self._layout_mode != "tabs"
        for term in self._terminals:
            if is_grid and term is self._active_terminal:
                term.status_label.setStyleSheet(
                    "color: #ffffff; background-color: #2a7c5f; padding: 2px 6px;"
                )
            else:
                term.status_label.setStyleSheet("color: #888;")

    def _on_focus_changed(self, _old, new) -> None:
        """
        Khi focus đổi → cập nhật active terminal.
        - Click QPushButton trong status bar: chỉ set active, không steal focus.
        - Click TerminalView (TUI mode): chỉ set active, KHÔNG steal focus → user
          có thể gõ phím trực tiếp vào vim/htop/nano qua TerminalView.
        - Click output (fallback mode): set active + steal focus về ô nhập chung.
        """
        if new is getattr(self, "input", None) or new is getattr(self, "input_password", None):
            return
        # Click vào button → giữ focus button để click cycle hoàn thành
        if isinstance(new, QPushButton):
            w = new
            while w is not None:
                if isinstance(w, TerminalTab) and w in self._terminals:
                    self._set_active_terminal(w)
                    return
                w = w.parentWidget()
            return
        # Click vào TerminalView (TUI) → giữ focus để raw keys đi xuống PTY
        if TerminalView is not None and isinstance(new, TerminalView):
            w = new
            while w is not None:
                if isinstance(w, TerminalTab) and w in self._terminals:
                    self._set_active_terminal(w)
                    return
                w = w.parentWidget()
            return
        # Trường hợp khác: set active + steal focus về input chung
        w = new
        while w is not None:
            if isinstance(w, TerminalTab):
                if w in self._terminals:
                    self._set_active_terminal(w)
                    target = self.input_password if self._password_mode else self.input
                    QTimer.singleShot(0, target.setFocus)
                return
            w = w.parentWidget()

    # ---------- Combined log ----------
    def _on_terminal_output(self, label: str, text: str) -> None:
        # Gom chunk vào buffer per-label. Chỉ log những line ĐÃ KẾT THÚC (có
        # \n). Trong từng line, \r ĐÈ DÒNG (như spinner) — chỉ giữ phần sau
        # \r cuối cùng. Tránh log spam khi TUI mode echo từng ký tự / spinner.
        ts = datetime.now().strftime("%H:%M:%S")
        buf = self._log_buffers.get(label, "") + text
        parts = buf.split("\n")
        # parts[-1] là phần dở dang (sau \n cuối cùng); chỉ giữ text sau \r cuối
        # — nếu user/shell sau đó in nữa sẽ tiếp tục ghép vào dòng đang xây.
        self._log_buffers[label] = parts[-1].rsplit("\r", 1)[-1]
        for line in parts[:-1]:
            # \r trong line = overwrite. Chỉ log content cuối cùng (sau \r cuối).
            line = line.rsplit("\r", 1)[-1].rstrip()
            if line:
                self._append_log_entry(ts, label, line)

        # Password detection — apply nếu output đến từ active terminal.
        # Bỏ qua khi input panel đang ẩn (TUI mode) vì TTY shell tự xử lý
        # echo off khi đọc password rồi.
        input_visible = hasattr(self, "_input_panel") and self._input_panel.isVisible()
        if (
            input_visible
            and self._active_terminal is not None
            and label == self._active_terminal.label
            and not self._password_mode
            and self._active_terminal.is_at_password_prompt()
        ):
            self._set_password_mode(True)
            self._active_terminal.clear_recent_output()

    def _log_system(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._append_log_entry(ts, "system", msg)

    def _append_log_entry(self, ts: str, source: str, line: str) -> None:
        # Dedup: bỏ qua nếu (source, line) trùng với entry cuối — tránh spam log
        # khi shell vẽ lại prompt nhiều lần (vd sau resize, sau Ctrl+C, ...).
        if self._log_entries:
            _, prev_src, prev_line = self._log_entries[-1]
            if prev_src == source and prev_line == line:
                return
        self._log_entries.append((ts, source, line))
        self._ensure_source_in_filter(source)
        # chỉ append vào view nếu khớp filter hiện tại — đỡ phải re-render toàn bộ
        if self._entry_matches_filter(ts, source, line):
            self.combined_log.appendPlainText(self._format_entry(ts, source, line))

    def _format_entry(self, ts: str, source: str, line: str) -> str:
        return f"[{ts}] [{source}] {line}"

    def _ensure_source_in_filter(self, source: str) -> None:
        if source in self._known_sources:
            return
        self._known_sources.append(source)
        # tránh emit signal khi thêm item, vì nó sẽ trigger _rerender_log không cần thiết
        self.cb_log_filter.blockSignals(True)
        self.cb_log_filter.addItem(source)
        self.cb_log_filter.blockSignals(False)

    def _entry_matches_filter(self, ts: str, source: str, line: str) -> bool:
        # index 0 luôn là "All / Tất cả"
        if self.cb_log_filter.currentIndex() > 0:
            if self.cb_log_filter.currentText() != source:
                return False
        needle = self.ed_log_search.text().strip().lower()
        if needle and needle not in line.lower() and needle not in source.lower():
            return False
        return True

    def _rerender_log(self, *_) -> None:
        """Vẽ lại toàn bộ log dựa trên filter + search hiện tại."""
        self.combined_log.clear()
        # nối các dòng thành 1 lần setPlainText để nhanh hơn khi log dài
        lines = [
            self._format_entry(ts, src, line)
            for ts, src, line in self._log_entries
            if self._entry_matches_filter(ts, src, line)
        ]
        if lines:
            self.combined_log.setPlainText("\n".join(lines))
            # cuộn xuống cuối
            sb = self.combined_log.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _clear_log(self) -> None:
        self._log_entries.clear()
        self.combined_log.clear()

    def _save_combined_log(self) -> None:
        from PyQt5.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self,
            t("log_save_title"),
            os.path.join(APP_DIR, f"terminal-log-{datetime.now():%Y%m%d-%H%M%S}.txt"),
            t("log_save_filter"),
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.combined_log.toPlainText())
            self._log_system(f"[*] Saved log → {path}")
        except Exception as e:
            QMessageBox.warning(self, t("log_save_err_title"), t("log_save_err_msg", err=e))

    # ---------- Open folder in shell ----------
    def _open_folder_in_shell(self) -> None:
        from PyQt5.QtWidgets import QFileDialog
        term = self._current_terminal()
        if term is None:
            return
        start_dir = getattr(self, "_last_folder_dir", APP_DIR)
        path = QFileDialog.getExistingDirectory(
            self, t("open_folder_dialog_title"), start_dir
        )
        if not path:
            return
        self._last_folder_dir = path
        cmd = self._build_cd_command(term.shell, path)
        term.send_command(cmd)
        self._log_system(f"[*] cd {path} ({term.label})")

    @staticmethod
    def _build_cd_command(shell: str, path: str) -> str:
        """Build cd command phù hợp với từng shell + platform."""
        sh = (shell or "").lower()
        # Windows shells (chỉ relevant trên Windows)
        if sh == "cmd":
            return f'cd /D "{path}"'
        if sh in ("powershell", "pwsh"):
            safe = path.replace("'", "''")
            return f"Set-Location -LiteralPath '{safe}'"
        if sh == "wsl":
            # Convert Windows path → WSL path
            if len(path) >= 2 and path[1] == ":":
                drive = path[0].lower()
                rest = path[2:].replace("\\", "/")
                return f"cd '/mnt/{drive}{rest}'"
            return f"cd '{path}'"
        # Unix shells (bash trên Unix, hoặc Git Bash trên Windows, hoặc zsh/fish/sh)
        if sh in ("bash", "zsh", "fish", "sh"):
            if not IS_WINDOWS:
                # Native Unix: dùng path như-là, escape single quote
                safe = path.replace("'", "'\\''")
                return f"cd '{safe}'"
            # Git Bash trên Windows: convert C:\foo → /c/foo
            if len(path) >= 2 and path[1] == ":":
                drive = path[0].lower()
                rest = path[2:].replace("\\", "/")
                return f"cd '/{drive}{rest}'"
            return f"cd '{path}'"
        return f'cd "{path}"'

    # ---------- Run script ----------
    def _run_script_file(self) -> None:
        from PyQt5.QtWidgets import QFileDialog

        # nhớ thư mục mở file gần nhất
        start_dir = getattr(self, "_last_script_dir", APP_DIR)

        path, _ = QFileDialog.getOpenFileName(
            self,
            t("script_dialog_title"),
            start_dir,
            t("script_dialog_filter"),
        )
        if not path:
            return

        self._last_script_dir = os.path.dirname(path)

        ext = os.path.splitext(path)[1].lower()
        if ext in (".bat", ".cmd"):
            target_shell = "cmd"
            # `call` để khi script xong vẫn trở lại prompt, không thoát phiên
            command = f'call "{path}"'
        elif ext == ".ps1":
            target_shell = "powershell"
            # & với single-quote, escape single quote bằng cách double nó
            safe = path.replace("'", "''")
            # set execution policy scope=Process để tránh lỗi "running scripts is disabled"
            command = f"Set-ExecutionPolicy -Scope Process Bypass -Force; & '{safe}'"
        else:
            QMessageBox.warning(
                self,
                t("script_unsupported_title"),
                t("script_unsupported_msg", ext=ext),
            )
            return

        term = self._choose_target_tab_for_shell(target_shell, script_name=os.path.basename(path))
        if term is None:
            return  # user huỷ

        term.send_command(command)
        self._log_system(f"[*] Chạy '{path}' trên {term.label}")

    def _choose_target_tab_for_shell(
        self, target_shell: str, script_name: str = ""
    ) -> TerminalTab | None:
        """
        Quyết định tab để chạy script:
        - Nếu tab hiện tại trùng shell → hỏi: dùng tab hiện tại hay mở tab mới.
        - Nếu không → tự mở tab mới.
        """
        current = self._current_terminal()
        if current is not None and current.shell == target_shell:
            box = QMessageBox(self)
            box.setWindowTitle(t("script_choose_title"))
            box.setIcon(QMessageBox.Question)
            box.setText(
                t(
                    "script_choose_msg",
                    name=script_name or "script",
                    label=current.label,
                    shell=current.shell,
                )
            )
            btn_current = box.addButton(t("script_choose_current"), QMessageBox.AcceptRole)
            btn_new = box.addButton(t("script_choose_new"), QMessageBox.ActionRole)
            box.addButton(t("script_choose_cancel"), QMessageBox.RejectRole)
            box.exec_()
            clicked = box.clickedButton()
            if clicked is btn_current:
                return current
            if clicked is btn_new:
                return self.add_cmd_tab() if target_shell == "cmd" else self.add_ps_tab()
            return None

        # tab hiện tại không khớp shell → mở tab mới
        return self.add_cmd_tab() if target_shell == "cmd" else self.add_ps_tab()

    # ---------- Favorites ----------
    def _active_shell_filter(self) -> str | None:
        """
        Trả về shell mà danh sách favorites đang lọc theo, hoặc None nếu không lọc.
        - "auto" → shell của tab hiện tại (nếu có), không thì không lọc
        - "all"  → không lọc
        - khác   → lọc theo tên đó
        """
        mode = "auto"
        if hasattr(self, "cb_fav_shell"):
            mode = self.cb_fav_shell.currentData() or "auto"
        if mode == "all":
            return None
        if mode == "auto":
            term = self._current_terminal()
            return term.shell if term is not None else None
        return mode

    def _refresh_favorites_list(self, *_) -> None:
        # lưu lệnh đang được chọn (theo command + name) để khôi phục selection sau khi lọc
        prev_idx = self.list_fav.currentRow()
        prev_real = (
            self._visible_to_real_index(prev_idx) if prev_idx >= 0 else -1
        )

        needle = self.ed_fav_search.text().strip().lower() if hasattr(self, "ed_fav_search") else ""
        shell_filter = self._active_shell_filter()

        # cập nhật title cho rõ ràng
        if hasattr(self, "lbl_fav_title"):
            if shell_filter:
                self.lbl_fav_title.setText(
                    f"<b>{t('fav_title_filtered', shell=shell_filter)}</b>"
                )
            else:
                self.lbl_fav_title.setText(f"<b>{t('fav_title')}</b>")

        self.list_fav.clear()
        # map từ row hiển thị → index thật trong self.favorites.items
        self._fav_index_map: list[int] = []
        for i, fav in enumerate(self.favorites.items):
            # filter theo shell
            if shell_filter is not None and fav.shell != "any" and fav.shell != shell_filter:
                continue
            # filter theo search text
            if needle and not self._fav_matches(fav, needle):
                continue
            item = QListWidgetItem(f"[{fav.shell}] {fav.name}")
            item.setToolTip(fav.command)
            self.list_fav.addItem(item)
            self._fav_index_map.append(i)

        # khôi phục selection nếu lệnh cũ còn xuất hiện
        if prev_real in self._fav_index_map:
            self.list_fav.setCurrentRow(self._fav_index_map.index(prev_real))

    def _on_current_tab_changed(self, _index: int) -> None:
        """Khi đổi tab → cập nhật active terminal + refresh favorites."""
        w = self.tabs.currentWidget()
        if isinstance(w, TerminalTab):
            self._set_active_terminal(w)
        # chỉ refresh khi đang ở chế độ auto (theo tab)
        if hasattr(self, "cb_fav_shell") and self.cb_fav_shell.currentData() == "auto":
            self._refresh_favorites_list()

    @staticmethod
    def _fav_matches(fav: Favorite, needle: str) -> bool:
        return (
            needle in fav.name.lower()
            or needle in fav.command.lower()
            or needle in fav.shell.lower()
        )

    def _visible_to_real_index(self, visible_row: int) -> int:
        """Đổi row trong list (đã lọc) → index thật trong self.favorites.items."""
        if not hasattr(self, "_fav_index_map"):
            return visible_row
        if 0 <= visible_row < len(self._fav_index_map):
            return self._fav_index_map[visible_row]
        return -1

    def _selected_favorite_index(self) -> int:
        return self._visible_to_real_index(self.list_fav.currentRow())

    def _on_favorite_item_selected(self, current, _previous) -> None:
        """Khi user click chọn 1 lệnh yêu thích → load command vào ô nhập.

        Nếu input panel đang ẩn (TUI mode), không load (user sẽ dùng
        double-click để chạy lệnh trực tiếp).
        """
        if current is None or not hasattr(self, "input"):
            return
        # Bỏ qua nếu ô nhập đang ẩn — load sẽ không thấy
        if hasattr(self, "_input_panel") and not self._input_panel.isVisible():
            return
        idx = self._visible_to_real_index(self.list_fav.row(current))
        if not (0 <= idx < len(self.favorites.items)):
            return
        if self._password_mode:
            return
        fav = self.favorites.items[idx]
        self.input.setPlainText(fav.command)
        cursor = self.input.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.input.setTextCursor(cursor)
        self.input.setFocus()

    def _run_selected_favorite(self, *_) -> None:
        idx = self._selected_favorite_index()
        if idx < 0:
            return
        fav = self.favorites.items[idx]
        term = self._current_terminal()
        if term is None:
            # tự động mở tab phù hợp
            term = self.add_ps_tab() if fav.shell == "powershell" else self.add_cmd_tab()

        # nếu shell yêu cầu cụ thể mà tab hiện tại không khớp → cảnh báo nhẹ
        if fav.shell != "any" and term.shell != fav.shell:
            ret = QMessageBox.question(
                self,
                t("fav_diff_shell_title"),
                t("fav_diff_shell_msg", saved=fav.shell, current=term.shell),
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return

        term.send_command(fav.command)

    def _add_favorite(self) -> None:
        dlg = FavoriteDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self.favorites.add(dlg.to_favorite())
            self._refresh_favorites_list()

    def _scan_and_add_tools(self) -> None:
        """Quét các CLI tool đã cài + hộp thoại chọn → add vào favorites."""
        tools = detect_tools()
        if not tools:
            QMessageBox.information(self, t("fav_scan_title"), t("fav_scan_none_found"))
            return
        dlg = ScanToolsDialog(self, tools)
        if dlg.exec_() != QDialog.Accepted:
            return
        selected = dlg.selected_tools()
        # Bỏ qua những lệnh đã có sẵn (so theo command + shell)
        existing = {(f.command, f.shell) for f in self.favorites.items}
        added = 0
        skipped = 0
        for tool in selected:
            key = (tool.command, tool.shell)
            if key in existing:
                skipped += 1
                continue
            self.favorites.add(
                Favorite(name=tool.display_name, command=tool.command, shell=tool.shell)
            )
            existing.add(key)
            added += 1
        self._refresh_favorites_list()
        # Log + thông báo
        self._log_system(f"[*] Scan tools: thêm {added}, bỏ qua {skipped}")
        msg = t("fav_scan_added", n=added)
        if skipped:
            msg += "\n" + t("fav_scan_skipped", n=skipped)
        QMessageBox.information(self, t("fav_scan_title"), msg)

    def _edit_favorite(self) -> None:
        idx = self._selected_favorite_index()
        if idx < 0:
            return
        dlg = FavoriteDialog(self, fav=self.favorites.items[idx])
        if dlg.exec_() == QDialog.Accepted:
            self.favorites.update(idx, dlg.to_favorite())
            self._refresh_favorites_list()

    def _delete_favorite(self) -> None:
        idx = self._selected_favorite_index()
        if idx < 0:
            return
        ret = QMessageBox.question(
            self,
            t("fav_delete_confirm_title"),
            t("fav_delete_confirm_msg", name=self.favorites.items[idx].name),
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self.favorites.remove(idx)
            self._refresh_favorites_list()

    # ---------- Layout switching ----------
    def _set_layout(self, mode: str) -> None:
        """
        Đổi bố cục terminals. mode:
        - "tabs"      : hiển thị 1 terminal/lần qua QTabWidget
        - "cols:N"    : N cột, tự suy ra số hàng theo số terminal
        - "rows:N"    : N hàng, tự suy ra số cột
        - "grid:RxC"  : lưới cố định R hàng × C cột
        """
        if not mode:
            mode = "tabs"
        # Nếu đang ở mode đó rồi và mode == "tabs" → không cần làm gì
        if mode == self._layout_mode and mode == "tabs":
            return

        old_mode = self._layout_mode
        self._layout_mode = mode
        self.settings.layout_mode = mode

        # CRITICAL: detach mọi terminal khỏi parent hiện tại TRƯỚC khi xoá splitter cũ
        # (nếu để terminal nằm trong splitter rồi xoá splitter, terminal sẽ bị xoá luôn)
        self._detach_all_terminals()
        # Xoá hết tabs (terminals đã được detach an toàn)
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        # Xoá hết widget trong grid_layout (chủ yếu là splitter cũ)
        self._clear_grid_container()

        if mode == "tabs":
            # Re-add terminals vào QTabWidget.
            # KHÔNG gọi term.show() ở đây — QTabWidget tự quản visibility:
            # chỉ widget của tab CURRENT mới hiển thị, các tab khác bị ẩn.
            # Gọi show() thủ công sẽ buộc tất cả terminal cùng visible →
            # status bars chồng lên nhau khó phân biệt.
            for term in self._terminals:
                self.tabs.addTab(term, term.label)
            target = self._active_terminal if self._active_terminal in self._terminals else None
            if target is not None:
                idx = self.tabs.indexOf(target)
                if idx >= 0:
                    self.tabs.setCurrentIndex(idx)
            elif self._terminals:
                self.tabs.setCurrentIndex(0)
            # setCurrentIndex tự gọi show() trên widget của tab đang chọn
            self._tabs_stack.setCurrentIndex(0)
        else:
            self._build_grid_into_layout()
            self._tabs_stack.setCurrentIndex(1)

        # đảm bảo active terminal hợp lệ + cập nhật highlight + input panel
        if self._active_terminal not in self._terminals:
            self._active_terminal = self._terminals[0] if self._terminals else None
        self._refresh_active_state()

        self._log_system(f"[*] Đổi bố cục: {old_mode} → {mode}")

    def _detach_all_terminals(self) -> None:
        """Detach mọi terminal khỏi parent hiện tại để giữ alive khi xoá container."""
        for term in self._terminals:
            term.setParent(None)
            # ẩn tạm để khỏi flash window khi widget thành top-level
            term.hide()

    def _clear_grid_container(self) -> None:
        """Xoá widgets trong grid_layout (chỉ chứa splitter wrapper, KHÔNG có terminal)."""
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _build_grid_into_layout(self) -> None:
        """
        Build vào grid_layout cho mode "grid:RxC":
        - Mỗi page R×C cố định
        - Nếu n > R×C → chia thành nhiều page, gom trong QTabWidget
        """
        if not self._terminals:
            return

        n = len(self._terminals)
        rows, cols = self._parse_layout(self._layout_mode)
        capacity = max(1, rows * cols)
        num_pages = max(1, (n + capacity - 1) // capacity)

        if num_pages == 1:
            page = self._build_grid_page(rows, cols, start=0, end=n)
            self._grid_layout.addWidget(page)
            page.show()
            # cân đều ngay sau khi splitter đã visible
            QTimer.singleShot(0, lambda p=page: self._equalize_splitter_recursive(p))
            return

        # Nhiều page → QTabWidget bao quanh (custom: chấp nhận drop terminal)
        page_tabs = PageTabWidget(self, page_capacity=capacity)
        pages_built: list[QSplitter] = []
        for p in range(num_pages):
            start = p * capacity
            end = min(start + capacity, n)
            page = self._build_grid_page(rows, cols, start=start, end=end)
            pages_built.append(page)
            page_tabs.addTab(page, t("layout_page", n=p + 1))
        self._grid_layout.addWidget(page_tabs)
        page_tabs.show()

        def _equalize_all():
            for p in pages_built:
                self._equalize_splitter_recursive(p)
        QTimer.singleShot(0, _equalize_all)

    def _build_grid_page(self, rows: int, cols: int, start: int, end: int) -> QSplitter:
        """Build 1 trang QSplitter lưới rows×cols chứa terminals[start:end]."""
        outer = QSplitter(Qt.Vertical)
        outer.setChildrenCollapsible(False)
        outer.setHandleWidth(4)

        idx = start
        for r in range(rows):
            row_split = QSplitter(Qt.Horizontal)
            row_split.setChildrenCollapsible(False)
            row_split.setHandleWidth(4)
            for c in range(cols):
                if idx < end:
                    term = self._terminals[idx]
                    row_split.addWidget(term)
                    term.show()
                    idx += 1
                else:
                    # target_index = vị trí trong _terminals nếu user drop terminal vào đây
                    placeholder = EmptyCellPlaceholder(self, target_index=idx)
                    row_split.addWidget(placeholder)
                    idx += 1
            outer.addWidget(row_split)
        return outer

    # Giữ tên cũ để các caller khác (vd _add_terminal khi đang ở grid) còn dùng
    def _rebuild_grid(self) -> None:
        self._detach_all_terminals()
        self._clear_grid_container()
        self._build_grid_into_layout()

    # ---------- Cân đều grid splitters ----------
    def _equalize_grid_cells(self) -> None:
        """Reset mọi QSplitter trong grid về kích thước đều nhau."""
        if self._layout_mode == "tabs":
            return
        if not self._grid_layout.count():
            return
        root = self._grid_layout.itemAt(0).widget()
        if root is None:
            return
        if isinstance(root, QTabWidget):
            # paginated → cân đều từng page
            for i in range(root.count()):
                page = root.widget(i)
                if isinstance(page, QSplitter):
                    self._equalize_splitter_recursive(page)
        elif isinstance(root, QSplitter):
            self._equalize_splitter_recursive(root)
        self._log_system("[*] Cân đều các ô lưới")

    def _equalize_splitter_recursive(self, splitter: QSplitter) -> None:
        """Set sizes đều cho splitter, rồi recurse vào child splitters."""
        n = splitter.count()
        if n == 0:
            return
        if splitter.orientation() == Qt.Vertical:
            total = splitter.height()
        else:
            total = splitter.width()
        # fallback nếu chưa visible (size = 0)
        each = max(100, total // n if total > 0 else 200)
        splitter.setSizes([each] * n)
        for i in range(n):
            child = splitter.widget(i)
            if isinstance(child, QSplitter):
                self._equalize_splitter_recursive(child)

    def _parse_layout(self, mode: str, _n_terms: int = 0) -> tuple[int, int]:
        """
        Trả về (rows, cols) cho bố cục.
        - "grid:RxC" → R hàng × C cột mỗi page (1×N = 1 hàng nhiều cột,
          N×1 = 1 cột nhiều hàng, RxC tổng quát).
        - khác (vd "tabs") → (1, 1) — không dùng grid.
        """
        if mode.startswith("grid:"):
            try:
                spec = mode.split(":", 1)[1]
                r, c = spec.split("x")
                return max(1, int(r)), max(1, int(c))
            except Exception:
                return 2, 2
        return 1, 1

    def _open_custom_layout_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(t("layout_custom_title"))
        form = QFormLayout(dlg)
        sp_rows = QSpinBox()
        sp_rows.setRange(1, 10)
        sp_rows.setValue(2)
        sp_cols = QSpinBox()
        sp_cols.setRange(1, 10)
        sp_cols.setValue(2)
        # nếu mode hiện tại là grid → set giá trị mặc định
        try:
            if self._layout_mode.startswith("grid:"):
                r, c = self._layout_mode.split(":", 1)[1].split("x")
                sp_rows.setValue(int(r))
                sp_cols.setValue(int(c))
        except Exception:
            pass
        form.addRow(t("layout_custom_rows"), sp_rows)
        form.addRow(t("layout_custom_cols"), sp_cols)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec_() == QDialog.Accepted:
            self._set_layout(f"grid:{sp_rows.value()}x{sp_cols.value()}")

    # ---------- Tab rename / context menu ----------
    def _rename_tab(self, index: int) -> None:
        if index < 0 or index >= self.tabs.count():
            return
        term = self.tabs.widget(index)
        if not isinstance(term, TerminalTab):
            return
        current_name = self.tabs.tabText(index)
        new_name, ok = QInputDialog.getText(
            self,
            t("tab_rename_title"),
            t("tab_rename_prompt"),
            text=current_name,
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == current_name:
            return
        self.tabs.setTabText(index, new_name)
        term.set_label(new_name)
        self._log_system(f"[*] Rename: {current_name} → {new_name}")

    def _show_tab_context_menu(self, pos) -> None:
        bar = self.tabs.tabBar()
        index = bar.tabAt(pos)
        if index < 0:
            return
        menu = QMenu(self)
        a_rename = menu.addAction(t("tab_ctx_rename"))
        a_close = menu.addAction(t("tab_ctx_close"))
        a_close_others = menu.addAction(t("tab_ctx_close_others"))
        chosen = menu.exec_(bar.mapToGlobal(pos))
        if chosen is a_rename:
            self._rename_tab(index)
        elif chosen is a_close:
            self._close_tab(index)
        elif chosen is a_close_others:
            # đóng từ cuối về đầu, bỏ qua index đang chọn
            for i in range(self.tabs.count() - 1, -1, -1):
                if i != index:
                    self._close_tab(i)

    # ---------- Session restore ----------
    def _restore_tab(self, state: TabState) -> None:
        """Mở 1 tab dựa trên TabState đã lưu (cross-platform)."""
        valid_shells = ("cmd", "powershell", "wsl", "bash", "zsh", "fish", "sh")
        shell = state.shell if state.shell in valid_shells else ("cmd" if IS_WINDOWS else "bash")

        # Migrate cross-platform: shell không tồn tại trên platform hiện tại → fallback
        if IS_WINDOWS:
            if shell == "wsl" and find_wsl() is None:
                shell = "cmd"
            if shell == "bash" and find_git_bash() is None:
                shell = "cmd"
            if shell in ("zsh", "fish", "sh"):
                shell = "cmd"  # các shell này không có trên Windows
        else:
            # Unix
            if shell in ("cmd", "wsl"):
                shell = "bash"
            if not shutil.which(shell):
                shell = "bash"

        if shell == "powershell":
            self._ps_counter += 1
            default_label = f"PS #{self._ps_counter}"
        elif shell == "wsl":
            self._wsl_counter += 1
            default_label = f"WSL #{self._wsl_counter}"
        elif shell == "bash":
            if IS_WINDOWS:
                self._bash_counter += 1
                default_label = f"Bash #{self._bash_counter}"
            else:
                self._unix_bash_counter += 1
                default_label = f"Bash #{self._unix_bash_counter}"
        elif shell == "zsh":
            self._zsh_counter += 1
            default_label = f"Zsh #{self._zsh_counter}"
        elif shell == "fish":
            self._fish_counter += 1
            default_label = f"Fish #{self._fish_counter}"
        elif shell == "sh":
            self._sh_counter += 1
            default_label = f"sh #{self._sh_counter}"
        else:
            self._cmd_counter += 1
            default_label = f"CMD #{self._cmd_counter}"
        label = state.title.strip() or default_label
        term = TerminalTab(shell=shell, label=label, backend_pref=self.settings.backend)
        term.output_received.connect(self._on_terminal_output)
        term.close_requested.connect(lambda _t=term: self._close_terminal(_t))
        self._terminals.append(term)
        # khi restore, ta tạm thời thêm vào QTabWidget (sẽ chuyển sang grid sau nếu cần)
        idx = self.tabs.addTab(term, label)
        self.tabs.setCurrentIndex(idx)
        self._log_system(f"[+] Restored tab {label}")

    # ---------- Settings dialog ----------
    def _open_settings_dialog(self) -> None:
        dlg = SettingsDialog(self, current=self.settings)
        if dlg.exec_() != QDialog.Accepted:
            return
        old_lang = self.settings.language
        old_theme = self.settings.theme
        dlg.apply_to(self.settings)
        # áp dụng theme ngay
        if self.settings.theme != old_theme:
            app = QApplication.instance()
            if app is not None:
                app_theme.apply_theme(app, self.settings.theme)
        # ngôn ngữ chỉ apply sau restart, nhưng cập nhật biến để lần lưu sau đúng
        if self.settings.language != old_lang:
            set_language(self.settings.language)
            QMessageBox.information(
                self,
                t("settings_title"),
                t("settings_lang_note"),
            )
        # lưu ngay để không mất nếu app crash
        self.settings.save(SETTINGS_PATH)

    # ---------- Misc ----------
    def _show_about(self) -> None:
        QMessageBox.information(self, t("about_title"), t("about_body"))

    def _collect_session(self) -> list[TabState]:
        # Dùng authoritative list để hoạt động ở cả tab mode và grid mode.
        # title: nếu đang ở tab mode thì lấy tabText cho chính xác (sau rename).
        out: list[TabState] = []
        for term in self._terminals:
            title = term.label
            if self._layout_mode == "tabs":
                idx = self.tabs.indexOf(term)
                if idx >= 0:
                    title = self.tabs.tabText(idx)
            out.append(TabState(shell=term.shell, title=title))
        return out

    def closeEvent(self, event):
        # lưu session + geometry + layout
        try:
            self.settings.last_tabs = self._collect_session()
            self.settings.geometry = Geometry(w=self.width(), h=self.height())
            self.settings.layout_mode = self._layout_mode
            self.settings.save(SETTINGS_PATH)
        except Exception as e:
            print(f"[settings] Lỗi lưu khi đóng: {e}")
        # đóng tất cả tiến trình con
        for term in list(self._terminals):
            try:
                term.stop_process()
            except Exception:
                pass
        super().closeEvent(event)
