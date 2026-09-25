"""Self-contained welcome page: the same local fonts/theme, before HTTP startup."""
import base64
import re
from core.paths import RESOURCE_DIR, APP_VERSION


def welcome_html(existing):
    static = RESOURCE_DIR / "static"
    fonts_all = (static / "css" / "fonts.css").read_text(encoding="utf-8")
    # خط واجهة النظام المعتمد Tajawal (أوزانه الأربعة فقط) — نضمّنها وحدها في الترحيب
    # ليبقى الملف خفيفًا؛ باقي الخطوط المتوافقة تُحمَّل من static عبر HTTP عند الحاجة.
    fonts = "\n".join(block for block in
                      re.findall(r"@font-face\s*\{[^}]*\}", fonts_all)
                      if "Tajawal" in block)

    def embedded_font(match):
        path = static / "fonts" / match.group(1)
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'url("data:font/woff2;base64,{encoded}")'

    # No network/file-origin requests from the bootstrap window, even on first install.
    fonts = re.sub(r'url\("\.\./fonts/([A-Za-z0-9-]+\.woff2)"\)', embedded_font, fonts)
    styles = [fonts]
    for name in ("theme", "style", "welcome"):
        styles.append((static / "css" / f"{name}.css").read_text(encoding="utf-8"))
    html = (RESOURCE_DIR / "desktop" / "welcome.html").read_text(encoding="utf-8")
    return (html.replace("__STYLES__", "\n".join(styles))
            .replace("__MARK__", (static / "img" / "mark.svg").read_text(encoding="utf-8"))
            .replace("__VERSION__", APP_VERSION)
            .replace("__EXISTING__", "true" if existing else "false"))
