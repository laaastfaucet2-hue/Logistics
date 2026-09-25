"""Offline Changa font delivery, approved purple/orange palette, and desktop/web parity."""
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
    font = FONT_DIR / f"Changa-{weight}.woff2"
    assert font.read_bytes().startswith(b"wOF2")
    assert font.stat().st_size > 15_000  # Complete Arabic/Latin faces, not tiny subsets.
    assert font.name in (ROOT / "static/css/fonts.css").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in (FONT_DIR / "Changa-OFL.txt").read_text(encoding="utf-8")


def test_arabic_glyph_coverage_is_complete():
    tt_lib = pytest.importorskip("fontTools.ttLib")  # أداة بناء الخط — اختيارية في بيئة التشغيل
    font = tt_lib.TTFont(str(FONT_DIR / "Changa-Regular.woff2"))
    cmap = font.getBestCmap()
    arabic = [c for c in cmap if 0x0600 <= c <= 0x06FF]
    latin = [c for c in cmap if 0x0041 <= c <= 0x007A]
    assert len(arabic) >= 90 and len(latin) >= 50
    for char in ("ا", "ل", "م", "٠", "٩"):  # letters + Eastern digits
        assert ord(char) in cmap


def test_welcome_uses_same_fonts_and_palette_without_network():
    """الترحيب يضمّن خط الواجهة المعتمد Tajawal (٤ أوزان) + الألوان المرجعية، بلا أي شبكة."""
    html = welcome_html(False)
    assert APP_VERSION in html and "if (false) begin()" in html
    assert "Tajawal" in html and "#f59e0b" in html and "#020617" in html
    assert not re.search(r'\b(?:src|href)=["\']https?://', html)
    assert "../fonts/" not in html
    assert not any(marker in html for marker in ("__STYLES__", "__MARK__", "__VERSION__", "__EXISTING__"))
    fonts = re.findall(r"data:font/woff2;base64,([A-Za-z0-9+/=]+)", html)
    assert len(fonts) == 4
    assert all(base64.b64decode(font).startswith(b"wOF2") for font in fonts)
    assert "if (true) begin()" in welcome_html(True)


def test_slate_amber_palette_retains_accessible_text():
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
    assert token("brand-purple") == "#0f172a"
    assert token("brand-orange") == "#f59e0b"
    assert token("bg0") == "#020617"
    assert token("on-orange") == "#020617"
    assert contrast(token("on-orange"), token("brand-orange")) >= 7
    assert contrast(token("text"), token("brand-purple")) >= 7
    assert contrast(token("gold-light"), token("bg1")) >= 7
    assert contrast(token("muted"), token("bg1")) >= 4.5
    assert "#ffc72c" not in css and "#da291c" not in css


def test_font_and_theme_assets_are_served_locally(client):
    for page in ("/login", "/dashboard", "/recruits/", "/letterhead/", "/tameedat/"):
        browser = client.application.test_client() if page == "/login" else client
        response = browser.get(page)
        assert response.status_code == 200
        assert "css/theme.css?v=" in response.text
        assert "css/fonts.css?v=" in response.text
    for weight in ("Regular", "Medium", "SemiBold", "Bold"):
        response = client.get(f"/static/fonts/Changa-{weight}.woff2")
        assert response.status_code == 200 and response.data.startswith(b"wOF2")
        assert response.mimetype == "font/woff2"
    assert client.get("/static/css/theme.css").status_code == 200


def test_ui_no_longer_requests_old_typefaces():
    for folder, pattern in [("static/css", "*.css"), ("templates", "*.html"), ("desktop", "*.html")]:
        for file in (ROOT / folder).rglob(pattern):
            source = file.read_text(encoding="utf-8")
            assert "Cairo" not in source and "IBM Plex" not in source, file
    assert "theme.fontFamily" in (ROOT / "static/js/app.js").read_text(encoding="utf-8")
    assert not list(FONT_DIR.glob("IBMPlexSansArabic-*.woff2"))
    assert not (FONT_DIR / "cairo.ttf").exists()


def test_installer_versions_match_application():
    for name in ("scripts/installer/Logistics.iss", "scripts/installer/version_info.txt",
                 "scripts/build-installer.ps1", "scripts/test-installer.ps1",
                 ".github/workflows/windows-installer.yml"):
        assert APP_VERSION in (ROOT / name).read_text(encoding="utf-8"), name


def test_windows_registry_cannot_mislabel_bundled_fonts(app, monkeypatch):
    # سجل ويندوز قد يسيء تسمية woff2 — app.py يعيد تثبيت النوع الصحيح عند الإنشاء.
    import mimetypes
    monkeypatch.setitem(mimetypes.types_map, ".woff2", "application/x-font-woff")
    monkeypatch.setitem(mimetypes.common_types, ".woff2", "application/x-font-woff")
    mimetypes.add_type("font/woff2", ".woff2")  # نفس سطر create_app يتغلب على السجل
    client = app.test_client()
    response = client.get("/static/fonts/Changa-Regular.woff2")
    assert response.mimetype == "font/woff2"
