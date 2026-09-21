"""Windows-runner acceptance check: real WebView2 window, login and native controls."""
import logging
import threading
from pathlib import Path
from urllib.parse import urlsplit


def attach(application, api, output):
    report = Path(output)
    window = application.window
    complete = threading.Event()
    login_started = threading.Event()

    def finish(error=None):
        if complete.is_set():
            return
        complete.set()
        watchdog.cancel()
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("UI_SMOKE_FAILED: " + str(error) if error else "UI_SMOKE_OK", encoding="utf-8")
        window.destroy()

    def loaded():
        if complete.is_set():
            return
        try:
            if not api._origin:
                api.begin_new()
                return
            path = urlsplit(window.get_current_url() or "").path
            if path == "/login" and not login_started.is_set():
                login_started.set()
                window.evaluate_js("document.querySelector('[name=username]').value='mostafa';"
                                   "document.querySelector('[name=password]').value='779';"
                                   "document.querySelector('form').requestSubmit();")
            elif path == "/dashboard":
                result = window.evaluate_js("({desktop:document.body.dataset.desktop,"
                    "controls:document.querySelectorAll('[data-window]').length,"
                    "bridge:typeof window.pywebview.api.window_action,"
                    "title:document.title})")
                assert result["desktop"] == "1", result
                assert result["controls"] == 4 and result["bridge"] == "function", result
                api.window_action("maximize")
                api.window_action("maximize")
                try:
                    from PIL import ImageGrab
                    ImageGrab.grab(all_screens=True).save(report.with_suffix(".png"))
                except OSError:
                    logging.exception("Screenshot unavailable; DOM/native checks succeeded")
                finish()
        except Exception as exc:
            logging.exception("Real WebView2 smoke test failed")
            finish(exc)

    watchdog = threading.Timer(90, lambda: finish("Window did not complete login within 90 seconds"))
    watchdog.daemon = True
    window.events.loaded += loaded
    watchdog.start()
