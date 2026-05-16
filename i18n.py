"""
i18n đơn giản dựa trên dict. Dùng hàm `t(key)` để lấy chuỗi theo ngôn ngữ
hiện tại. Mặc định là tiếng Việt.

Khi đổi ngôn ngữ giữa chừng, gọi `set_language(lang)`. Các string đã render
trên UI sẽ cần app khởi động lại để cập nhật triệt để.
"""

from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "vi": {
        # toolbar / menu
        "app_title": "Terminal Manager - Shell",
        "menu_new_cmd": "+ CMD",
        "menu_new_ps": "+ PowerShell",
        "menu_new_wsl": "+ WSL",
        "menu_new_bash": "+ Git Bash",
        "menu_new_unix_bash": "+ Bash",
        "menu_new_zsh": "+ Zsh",
        "menu_new_fish": "+ Fish",
        "menu_new_sh": "+ sh",
        "wsl_not_found": "Không tìm thấy wsl.exe. Cài đặt WSL bằng `wsl --install` trước.",
        "bash_not_found": "Không tìm thấy Git Bash. Cài Git for Windows từ https://git-scm.com/",
        "shell_not_found": "Không tìm thấy shell '{shell}' trên hệ thống.",
        "menu_run_script": "▶ Chạy script...",
        "menu_run_script_tip": "Chọn file .bat / .cmd / .ps1 để chạy",
        "menu_open_folder": "📁 Mở thư mục...",
        "menu_open_folder_tip": "Chọn 1 thư mục để cd terminal active vào đó",
        "open_folder_dialog_title": "Chọn thư mục",
        "menu_toggle_input": "⌨ Ô nhập",
        "menu_toggle_input_tip": "Ẩn / hiện ô nhập lệnh chung (Ctrl+I). TUI mode (vim/htop) gõ thẳng vào terminal.",
        "menu_broadcast_label": "Broadcast: ",
        "menu_broadcast_btn": "Broadcast →",
        "menu_broadcast_placeholder": "Gõ lệnh để gửi đến TẤT CẢ phiên đang mở...",
        "menu_settings": "⚙ Cài đặt",
        "menu_about": "?",
        "menu_layout": "▦ Bố cục",
        "layout_tabs": "Tabs (một terminal/lần)",
        "layout_grid_rc": "Lưới {r} × {c}",
        "layout_custom": "Tuỳ chỉnh...",
        "layout_equalize": "↔ Cân đều các ô",
        "layout_custom_title": "Bố cục tuỳ chỉnh",
        "layout_custom_rows": "Số hàng:",
        "layout_custom_cols": "Số cột:",
        "layout_page": "Trang {n}",
        "empty_cell_title": "(ô trống)",
        "empty_cell_open": "+ Mở terminal",

        # favorites sidebar
        "fav_title": "Lệnh yêu thích",
        "fav_title_filtered": "Lệnh yêu thích — {shell}",
        "fav_show_all": "Tất cả",
        "fav_filter_shell_label": "Lọc theo shell:",
        "fav_search_placeholder": "Tìm theo tên / lệnh / shell...",
        "fav_run": "▶ Chạy",
        "fav_add": "+ Thêm",
        "fav_edit": "Sửa",
        "fav_delete": "Xoá",
        "fav_dialog_title": "Lệnh yêu thích",
        "fav_field_name": "Tên:",
        "fav_field_command": "Lệnh:",
        "fav_field_shell": "Shell:",
        "fav_unnamed": "(không tên)",
        "fav_diff_shell_title": "Khác shell",
        "fav_diff_shell_msg": "Lệnh này được lưu cho '{saved}', nhưng tab hiện tại là '{current}'.\nVẫn chạy?",
        "fav_delete_confirm_title": "Xác nhận",
        "fav_delete_confirm_msg": "Xoá lệnh '{name}'?",
        "fav_scan_btn": "🔍 Quét",
        "fav_scan_btn_tip": "Quét các CLI tool đã cài (git, python, docker, ...) và thêm vào lệnh yêu thích",
        "fav_scan_title": "Quét CLI tools",
        "fav_scan_info": "Tìm được {n} lệnh từ các CLI tool có sẵn trên máy. Chọn các lệnh muốn thêm vào Lệnh yêu thích.",
        "fav_scan_none_found": "Không tìm thấy CLI tool nào trong PATH.\nThử cài git / python / docker / node ... rồi quét lại.",
        "fav_scan_search": "Tìm trong danh sách...",
        "fav_scan_select_all": "Chọn tất cả (hiện)",
        "fav_scan_select_none": "Bỏ chọn tất cả",
        "fav_scan_added": "Đã thêm {n} lệnh vào Lệnh yêu thích.",
        "fav_scan_skipped": "Bỏ qua {n} lệnh đã có sẵn.",

        # combined log
        "log_title": "Log gộp",
        "log_session": "Phiên:",
        "log_all": "Tất cả",
        "log_search_placeholder": "Lọc nội dung log...",
        "log_clear": "Clear",
        "log_save": "Lưu log...",
        "log_save_title": "Lưu log gộp",
        "log_save_filter": "Text files (*.txt);;Tất cả (*.*)",
        "log_save_err_title": "Lỗi",
        "log_save_err_msg": "Không lưu được file:\n{err}",

        # tab management
        "tab_rename_title": "Đổi tên tab",
        "tab_rename_prompt": "Nhập tên mới cho tab:",
        "tab_ctx_rename": "Đổi tên...",
        "tab_ctx_close": "Đóng tab",
        "tab_ctx_close_others": "Đóng các tab khác",

        # run script
        "script_dialog_title": "Chọn file script",
        "script_dialog_filter": "Script files (*.bat *.cmd *.ps1);;Batch (*.bat *.cmd);;PowerShell (*.ps1);;Tất cả (*.*)",
        "script_unsupported_title": "Định dạng không hỗ trợ",
        "script_unsupported_msg": "Đuôi file '{ext}' không phải .bat/.cmd/.ps1.",
        "script_choose_title": "Chạy script",
        "script_choose_msg": "Chạy <b>{name}</b> ở đâu?<br>Tab hiện tại: <i>{label}</i> ({shell})",
        "script_choose_current": "Tab hiện tại",
        "script_choose_new": "Tab mới",
        "script_choose_cancel": "Huỷ",

        # settings dialog
        "settings_title": "Cài đặt",
        "settings_theme": "Giao diện:",
        "settings_language": "Ngôn ngữ:",
        "settings_restore": "Khôi phục các tab đã mở khi khởi động",
        "settings_theme_system": "Theo hệ thống",
        "settings_theme_light": "Sáng",
        "settings_theme_dark": "Tối",
        "settings_lang_vi": "Tiếng Việt",
        "settings_lang_en": "English",
        "settings_lang_note": "Đổi ngôn ngữ sẽ áp dụng sau khi khởi động lại app.",
        "settings_backend": "Backend shell:",
        "settings_backend_auto": "Tự động (ưu tiên ConPTY)",
        "settings_backend_conpty": "ConPTY (TTY thật, hỗ trợ ssh / vim / REPL)",
        "settings_backend_qprocess": "QProcess (không TTY, đơn giản)",
        "settings_backend_note": "ConPTY cần cài pywinpty. Đổi backend chỉ áp dụng cho tab MỚI mở.",
        "settings_backend_missing": "(pywinpty chưa cài → ConPTY không khả dụng)",

        # about
        "about_title": "Về ứng dụng",
        "about_body": (
            "<b>Terminal Manager</b><br>"
            "Quản lý nhiều phiên CMD và PowerShell trong cùng cửa sổ.<br><br>"
            "Phím tắt:<br>"
            "• Ctrl+T: tab CMD mới<br>"
            "• Ctrl+Shift+T: tab PowerShell mới<br>"
            "• Ctrl+R: chạy file .bat/.cmd/.ps1<br>"
            "• Ctrl+W: đóng tab hiện tại<br>"
            "• Ctrl+L: xoá log gộp<br>"
            "• Ctrl+, : mở Cài đặt<br>"
            "• Ctrl+↑ / Ctrl+↓ trong ô lệnh: lịch sử<br>"
            "• Enter: gửi — Shift+Enter: xuống dòng<br>"
            "• Double-click tab để đổi tên<br><br>"
            "Build với PyQt5."
        ),

        # misc
        "input_hint": "Enter: gửi  •  Shift+Enter: xuống dòng  •  Ctrl+↑/↓: lịch sử",
        "input_placeholder": "Nhập lệnh (hỗ trợ nhiều dòng) — Enter để gửi, Shift+Enter để xuống dòng...",
        "input_password_placeholder": "🔒 Mật khẩu (Enter gửi, Esc huỷ) — ký tự được che",
        "input_password_hint": "🔒 Mode nhập mật khẩu — ký tự bị che. Esc để huỷ.",
        "input_btn_password_tip": "Bật/tắt mode nhập mật khẩu (Ctrl+Shift+P)",
    },

    "en": {
        # toolbar / menu
        "app_title": "Terminal Manager - Shell",
        "menu_new_cmd": "+ CMD",
        "menu_new_ps": "+ PowerShell",
        "menu_new_wsl": "+ WSL",
        "menu_new_bash": "+ Git Bash",
        "menu_new_unix_bash": "+ Bash",
        "menu_new_zsh": "+ Zsh",
        "menu_new_fish": "+ Fish",
        "menu_new_sh": "+ sh",
        "wsl_not_found": "wsl.exe not found. Install WSL with `wsl --install` first.",
        "bash_not_found": "Git Bash not found. Install Git for Windows from https://git-scm.com/",
        "shell_not_found": "Shell '{shell}' not found on this system.",
        "menu_run_script": "▶ Run script...",
        "menu_run_script_tip": "Pick a .bat / .cmd / .ps1 file to run",
        "menu_open_folder": "📁 Open folder...",
        "menu_open_folder_tip": "Pick a folder to cd the active terminal into",
        "open_folder_dialog_title": "Choose folder",
        "menu_toggle_input": "⌨ Input bar",
        "menu_toggle_input_tip": "Show / hide the shared input bar (Ctrl+I). TUI mode (vim/htop) types directly in the terminal.",
        "menu_broadcast_label": "Broadcast: ",
        "menu_broadcast_btn": "Broadcast →",
        "menu_broadcast_placeholder": "Type a command to send to ALL open sessions...",
        "menu_settings": "⚙ Settings",
        "menu_about": "?",
        "menu_layout": "▦ Layout",
        "layout_tabs": "Tabs (one terminal at a time)",
        "layout_grid_rc": "Grid {r} × {c}",
        "layout_custom": "Custom...",
        "layout_equalize": "↔ Equalize cells",
        "layout_custom_title": "Custom layout",
        "layout_custom_rows": "Rows:",
        "layout_custom_cols": "Columns:",
        "layout_page": "Page {n}",
        "empty_cell_title": "(empty cell)",
        "empty_cell_open": "+ Open terminal",

        # favorites sidebar
        "fav_title": "Favorites",
        "fav_title_filtered": "Favorites — {shell}",
        "fav_show_all": "All",
        "fav_filter_shell_label": "Filter shell:",
        "fav_search_placeholder": "Search by name / command / shell...",
        "fav_run": "▶ Run",
        "fav_add": "+ Add",
        "fav_edit": "Edit",
        "fav_delete": "Delete",
        "fav_dialog_title": "Favorite command",
        "fav_field_name": "Name:",
        "fav_field_command": "Command:",
        "fav_field_shell": "Shell:",
        "fav_unnamed": "(unnamed)",
        "fav_diff_shell_title": "Different shell",
        "fav_diff_shell_msg": "This command is saved for '{saved}', but current tab is '{current}'.\nRun anyway?",
        "fav_delete_confirm_title": "Confirm",
        "fav_delete_confirm_msg": "Delete '{name}'?",
        "fav_scan_btn": "🔍 Scan",
        "fav_scan_btn_tip": "Scan installed CLI tools (git, python, docker, ...) and add as favorites",
        "fav_scan_title": "Scan CLI tools",
        "fav_scan_info": "Found {n} commands from CLI tools available on this machine. Pick which ones to add to Favorites.",
        "fav_scan_none_found": "No CLI tools found in PATH.\nInstall git / python / docker / node ... then scan again.",
        "fav_scan_search": "Search list...",
        "fav_scan_select_all": "Select all (visible)",
        "fav_scan_select_none": "Deselect all",
        "fav_scan_added": "Added {n} commands to Favorites.",
        "fav_scan_skipped": "Skipped {n} commands already saved.",

        # combined log
        "log_title": "Combined log",
        "log_session": "Session:",
        "log_all": "All",
        "log_search_placeholder": "Filter log content...",
        "log_clear": "Clear",
        "log_save": "Save log...",
        "log_save_title": "Save combined log",
        "log_save_filter": "Text files (*.txt);;All files (*.*)",
        "log_save_err_title": "Error",
        "log_save_err_msg": "Cannot save file:\n{err}",

        # tab management
        "tab_rename_title": "Rename tab",
        "tab_rename_prompt": "New tab name:",
        "tab_ctx_rename": "Rename...",
        "tab_ctx_close": "Close tab",
        "tab_ctx_close_others": "Close other tabs",

        # run script
        "script_dialog_title": "Choose script file",
        "script_dialog_filter": "Script files (*.bat *.cmd *.ps1);;Batch (*.bat *.cmd);;PowerShell (*.ps1);;All files (*.*)",
        "script_unsupported_title": "Unsupported format",
        "script_unsupported_msg": "File extension '{ext}' is not .bat/.cmd/.ps1.",
        "script_choose_title": "Run script",
        "script_choose_msg": "Run <b>{name}</b> where?<br>Current tab: <i>{label}</i> ({shell})",
        "script_choose_current": "Current tab",
        "script_choose_new": "New tab",
        "script_choose_cancel": "Cancel",

        # settings dialog
        "settings_title": "Settings",
        "settings_theme": "Theme:",
        "settings_language": "Language:",
        "settings_restore": "Restore previously opened tabs on startup",
        "settings_theme_system": "System",
        "settings_theme_light": "Light",
        "settings_theme_dark": "Dark",
        "settings_lang_vi": "Tiếng Việt",
        "settings_lang_en": "English",
        "settings_lang_note": "Language change applies after restarting the app.",
        "settings_backend": "Shell backend:",
        "settings_backend_auto": "Auto (prefer ConPTY)",
        "settings_backend_conpty": "ConPTY (real TTY, supports ssh / vim / REPL)",
        "settings_backend_qprocess": "QProcess (no TTY, simpler)",
        "settings_backend_note": "ConPTY requires pywinpty. Backend change applies to NEW tabs only.",
        "settings_backend_missing": "(pywinpty not installed → ConPTY unavailable)",

        # about
        "about_title": "About",
        "about_body": (
            "<b>Terminal Manager</b><br>"
            "Manage multiple CMD and PowerShell sessions in one window.<br><br>"
            "Shortcuts:<br>"
            "• Ctrl+T: new CMD tab<br>"
            "• Ctrl+Shift+T: new PowerShell tab<br>"
            "• Ctrl+R: run .bat/.cmd/.ps1 file<br>"
            "• Ctrl+W: close current tab<br>"
            "• Ctrl+L: clear combined log<br>"
            "• Ctrl+, : open Settings<br>"
            "• Ctrl+↑ / Ctrl+↓ in input: command history<br>"
            "• Enter: send — Shift+Enter: newline<br>"
            "• Double-click a tab to rename<br><br>"
            "Built with PyQt5."
        ),

        # misc
        "input_hint": "Enter: send  •  Shift+Enter: newline  •  Ctrl+↑/↓: history",
        "input_placeholder": "Type a command (multi-line supported) — Enter to send, Shift+Enter for newline...",
        "input_password_placeholder": "🔒 Password (Enter to submit, Esc to cancel) — characters hidden",
        "input_password_hint": "🔒 Password input mode — characters hidden. Esc to cancel.",
        "input_btn_password_tip": "Toggle password input mode (Ctrl+Shift+P)",
    },
}

_current_lang: str = "vi"


def set_language(lang: str) -> None:
    """Đổi ngôn ngữ. Chỉ áp dụng cho các string render sau đó."""
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang


def get_language() -> str:
    return _current_lang


def t(key: str, **kwargs) -> str:
    """
    Trả về string theo ngôn ngữ hiện tại. Nếu thiếu key, fallback sang 'vi', rồi key.
    Hỗ trợ format(): t("foo", name="bar") → "...{name}..." được .format.
    """
    s = TRANSLATIONS.get(_current_lang, {}).get(key)
    if s is None:
        s = TRANSLATIONS["vi"].get(key, key)
    if kwargs:
        try:
            return s.format(**kwargs)
        except Exception:
            return s
    return s
