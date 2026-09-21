"""Windows desktop lifecycle: private server, native window, persistent user data."""
import ctypes
import json
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from core.paths import DATA_DIR, RUNTIME_DIR, LOG_DIR, RESOURCE_DIR, APP_VERSION


class DesktopApplication:
    def __init__(self):
        self.server = None
        self.thread = None
        self.window = None

    def start_server(self, api):
        try:
            from app import create_app
            from waitress import create_server
            app = create_app()
            # Desktop only: inaccessible from the LAN. Web previews use app.py on 0.0.0.0.
            self.server = create_server(app, host="127.0.0.1", port=0, threads=4)
            self.thread = threading.Thread(target=self.server.run, name="Logistics-server", daemon=True)
            self.thread.start()
            api._origin = f"http://127.0.0.1:{self.server.effective_port}"
            self.window.load_url(api._origin + "/login")
        except Exception:
            logging.exception("Desktop startup failed")
            self.window.evaluate_js("showError(" + json.dumps(
                "تعذّر تشغيل البرنامج. بياناتك لم تُحذف. تفاصيل الخطأ في: " + str(LOG_DIR / "desktop.log")) + ")")

    def stop(self):
        if self.server:
            self.server.close()
            self.server.task_dispatcher.shutdown(timeout=8)
        if self.thread:
            self.thread.join(timeout=2)


def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_DIR / "desktop.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", force=True)
    # pythonnet and GUI initialization occasionally write directly to stdout/stderr.
    if sys.stdout is None:
        sys.stdout = open(LOG_DIR / "native.log", "a", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout


def run(ui_smoke=None):
    os.environ["LOGISTICS_DESKTOP"] = "1"
    os.environ.pop("LOGISTICS_PREVIEW", None)
    configure_logging()
    from ctypes import wintypes
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    mutex = kernel.CreateMutexW(None, False, "LogisticsDesktopV2")
    if kernel.GetLastError() == 183:
        ctypes.windll.user32.MessageBoxW(None, "البرنامج مفتوح بالفعل. انتقل لنافذته الحالية.", "مخازن التعيينات", 64)
        return
    application = DesktopApplication()
    try:
        import webview
        from desktop.native import NativeApi
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
        width = min(1440, max(980, int(ctypes.windll.user32.GetSystemMetrics(0) * .94)))
        height = min(950, max(650, int(ctypes.windll.user32.GetSystemMetrics(1) * .90)))
        existing = (DATA_DIR / "system.db").is_file()
        from desktop.appearance import welcome_html
        html = welcome_html(existing)
        application.window = webview.create_window("مخازن التعيينات", html=html,
            width=width, height=height, min_size=(980, 640), frameless=True, easy_drag=False,
            resizable=True, shadow=True, background_color="#f5f5f1", text_select=True,
            confirm_close=not bool(ui_smoke), localization={"global.quitConfirmation": "إغلاق منظومة مخازن التعيينات؟"})
        api = NativeApi(application.window, DATA_DIR, application.start_server)
        application.window.expose(api.window_action, api.begin_new, api.choose_old_data)
        if ui_smoke:
            from desktop.ui_smoke import attach
            attach(application, api, ui_smoke)
        profile = DATA_DIR.parent / "ui-profile" if ui_smoke else RUNTIME_DIR / "webview"
        profile.mkdir(parents=True, exist_ok=True)
        webview.start(gui="edgechromium", private_mode=bool(ui_smoke), storage_path=str(profile),
                      icon=str(RESOURCE_DIR / "static" / "img" / "app.ico"))
    except Exception:
        logging.exception("Native window failed")
        if ui_smoke:
            from pathlib import Path
            Path(ui_smoke).write_text("UI_SMOKE_FAILED: see desktop.log", encoding="utf-8")
            raise
        ctypes.windll.user32.MessageBoxW(None,
            "تعذّر فتح النافذة. أعد تشغيل المثبّت لإصلاح WebView2.\nسجل الخطأ: " + str(LOG_DIR / "desktop.log"),
            "مخازن التعيينات", 16)
        raise
    finally:
        application.stop()
        if mutex:
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(mutex)
