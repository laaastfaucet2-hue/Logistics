"""Offline font delivery, readable approved colors, and desktop/web parity."""
import base64
import re
from pathlib import Path
import pytest
from core.paths import APP_VERSION
from desktop.appearance import welcome_html

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "static" / "fonts"


@pytest.mark.parametrize("weight", ["Regular", "Medium", "SemiBold", "Bold"])
def test_complete_offline_font_files(weight):
    font = FONT_DIR / f"IBMPlexSansArabic-{weight}.woff2"
    assert font.read_bytes().startswith(b"wOF2")
    assert font.stat().st_size > 60_000  # Full Arabic/Latin family, not a Latin-only subset.
    assert font.name in (ROOT / "static/css/fonts.css").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in (FONT_DIR / "IBM-Plex-OFL.txt").read_text(encoding="utf-8")


def test_welcome_uses_same_fonts_and_palette_without_network():
    html = welcome_html(False)
    assert APP_VERSION in html and "if (false) begin()" in html
    assert "IBM Plex Sans Arabic" in html and "#ffc72c" in html and "#da291c" in html
    assert not re.search(r'\b(?:src|href)=["\']https?://', html)
    assert "../fonts/" not in html
    assert not any(marker in html for marker in ("__STYLES__", "__MARK__", "__VERSION__", "__EXISTING__"))
    fonts = re.findall(r"data:font/woff2;base64,([A-Za-z0-9+/=]+)", html)
    assert len(fonts) == 4
    assert all(base64.b64decode(font).startswith(b"wOF2") for font in fonts)
    assert "if (true) begin()" in welcome_html(True)


def test_palette_has_accessible_black_on_yellow_and_white_on_red():
    css = (ROOT / "static/css/theme.css").read_text(encoding="utf-8")
    def token(name):
        return re.search(r"--" + name + r":\s*(#[0-9a-f]{6});", css).group(1)
    def luminance(hex_color):
        rgb = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
        return sum(v * factor for v, factor in zip(linear, [.2126, .7152, .0722]))
    def contrast(a, b):
        bright, dark = sorted([luminance(a), luminance(b)], reverse=True)
        return (bright + .05) / (dark + .05)
    assert token("brand-red") == "#da291c"
    assert token("brand-yellow") == "#ffc72c"
    assert token("on-yellow") == "#000000"
    assert contrast(token("on-yellow"), token("brand-yellow")) >= 7
    assert contrast(token("on-red"), token("brand-red")) >= 4.5
    assert contrast(token("text"), token("bg1")) >= 7
    assert contrast(token("muted"), token("bg1")) >= 4.5


def test_font_and_theme_assets_are_served_locally(client):
    for page in ("/login", "/dashboard", "/recruits/", "/letterhead/"):
        browser = client.application.test_client() if page == "/login" else client
        response = browser.get(page)
        assert response.status_code == 200
        assert "css/theme.css?v=" in response.text
        assert "css/fonts.css?v=" in response.text
    for weight in ("Regular", "Medium", "SemiBold", "Bold"):
        response = client.get(f"/static/fonts/IBMPlexSansArabic-{weight}.woff2")
        assert response.status_code == 200 and response.data.startswith(b"wOF2")
        assert response.mimetype == "font/woff2"
    assert client.get("/static/css/theme.css").status_code == 200


def test_ui_no_longer_requests_old_typefaces():
    for folder, pattern in [("static/css", "*.css"), ("templates", "*.html"), ("desktop", "*.html")]:
        for file in (ROOT / folder).rglob(pattern):
            source = file.read_text(encoding="utf-8")
            assert "Cairo" not in source and "Changa" not in source, file
    assert "theme.fontFamily" in (ROOT / "static/js/app.js").read_text(encoding="utf-8")
    assert not (FONT_DIR / "cairo.ttf").exists()
    assert not (FONT_DIR / "changa.ttf").exists()


def test_installer_versions_match_application():
    for name in ("scripts/installer/Logistics.iss", "scripts/installer/version_info.txt",
                 "scripts/build-installer.ps1", "scripts/test-installer.ps1",
                 ".github/workflows/windows-installer.yml"):
        assert APP_VERSION in (ROOT / name).read_text(encoding="utf-8"), name


def test_windows_registry_cannot_mislabel_bundled_fonts(app, monkeypatch):
    import mimetypes
    from app import create_app
    mimetypes.init()
    monkeypatch.setitem(mimetypes.types_map, ".woff2", "application/octet-stream")
    # app fixture already redirects every data module to its temporary directory.
    fresh = create_app()
    response = fresh.test_client().get("/static/fonts/IBMPlexSansArabic-Regular.woff2")
    assert response.status_code == 200
    assert response.mimetype == "font/woff2"
    assert response.data.startswith(b"wOF2")


def test_native_font_callback_never_blocks_the_gui_thread(tmp_path):
    import threading
    from types import SimpleNamespace
    from desktop.ui_smoke import attach
    caller = threading.current_thread()
    recorded = []
    closed = threading.Event()

    class Event:
        def __iadd__(self, callback):
            self.callback = callback
            return self

    class Window:
        events = SimpleNamespace(loaded=Event())
        def evaluate_js(self, script, callback=None):
            # Mimic WebView2 invoking the promise callback on its GUI thread.
            callback({"family": "IBM Plex Sans Arabic", "fonts": True,
                      "red": "rgb(218, 41, 28)", "yellow": "rgb(255, 199, 44)",
                      "text": "rgb(0, 0, 0)"})
        def destroy(self):
            closed.set()

    def begin():
        recorded.append(threading.current_thread())
        # Finish this isolated stub test and cancel the real smoke watchdog.
        raise RuntimeError("end isolated threading check")

    window = Window()
    report = tmp_path / "native-check.txt"
    attach(SimpleNamespace(window=window), SimpleNamespace(_origin=None, begin_new=begin), report)
    window.events.loaded.callback()
    assert closed.wait(5), "Native callback blocked its caller"
    assert recorded and recorded[0] is not caller
    assert "end isolated threading check" in report.read_text(encoding="utf-8")
