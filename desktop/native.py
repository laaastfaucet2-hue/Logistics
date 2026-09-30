"""Narrow native bridge. Only trusted local UI can invoke window actions."""
import os
from pathlib import Path
from urllib.parse import urlparse


class NativeApi:
    def __init__(self, window, data_dir, on_start):
        self._window = window
        self._data_dir = Path(data_dir)
        self._on_start = on_start
        self._origin = None
        self._starting = False
        self._maximized = False

    def _trusted(self):
        url = self._window.get_current_url()
        if self._origin:
            parsed, expected = urlparse(url or ""), urlparse(self._origin)
            return (parsed.scheme, parsed.hostname, parsed.port) == (expected.scheme, expected.hostname, expected.port)
        return url in (None, "", "about:blank")

    def window_action(self, action):
        if not self._trusted():
            raise PermissionError("Untrusted window origin")
        if action == "minimize":
            self._window.minimize()
        elif action == "maximize":
            self._window.restore() if self._maximized else self._window.maximize()
            self._maximized = not self._maximized
        elif action == "close":
            self._window.destroy()
        elif action == "data_folder" and os.name == "nt":
            os.startfile(str(self._data_dir))
        else:
            raise ValueError("Unknown window action")
        return True

    def begin_new(self):
        if self._origin or self._starting or not self._trusted():
            return False
        self._starting = True
        self._on_start(self)
        return True

    def choose_old_data(self):
        if self._origin or self._starting or not self._trusted():
            raise PermissionError("Import is available only before the first launch")
        import webview
        from services.data_import import import_database
        selected = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if not selected:
            return {"cancelled": True}
        if not self._window.create_confirmation_dialog("استيراد البيانات",
                "أغلق النسخة القديمة أولًا. سننسخ مجلد البيانات المختار دون حذفه. متابعة؟"):
            return {"cancelled": True}
        try:
            count = import_database(selected[0], self._data_dir)
            self.begin_new()
            return {"ok": True, "files": count}
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}
