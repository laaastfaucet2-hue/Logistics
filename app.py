"""Application factory and route wiring only. See CONTRIBUTING.md."""
import mimetypes
import os
import secrets
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from core.paths import RESOURCE_DIR, APP_VERSION

# صفحة رفض الرفعة الأكبر من الحد — عربية وواضحة بدل صفحة السيرفر الإنجليزية
# (بتوجيه المستخدم ٠٨/١٠/٢٠٢٦: الفيديوهات الكبيرة تُرفع عادي حتى ٢ جيجا).
UPLOAD_TOO_LARGE_HTML = """<!doctype html>
<html dir="rtl" lang="ar"><head><meta charset="utf-8">
<title>الملف أكبر من الحد المسموح</title>
<style>
  body{font-family:"Segoe UI",Tahoma,sans-serif;background:#0b1220;color:#e2e8f0;
       display:grid;place-items:center;min-height:100vh;margin:0}
  .box{background:#16213a;border:1px solid #d4a84a;border-radius:14px;
       padding:28px 30px;max-width:560px;text-align:center;line-height:2}
  h1{color:#f5c451;font-size:20px;margin:0 0 10px}
  a{display:inline-block;margin-top:14px;background:#d4a84a;color:#1a2337;
    padding:8px 22px;border-radius:9px;text-decoration:none;font-weight:700}
</style></head><body><div class="box">
<h1>الملف أكبر من الحد المسموح</h1>
<p>الحد الأقصى للرفعة الواحدة <b>٢ جيجابايت</b> (وحتى <b>٣٠ ملفًا</b> في الرفعة).</p>
<p>قلّل حجم الملف أو قسّم الرفعة على دفعات، ثم ارجع وحاول تاني.</p>
<a href="javascript:history.back()">↩ رجوع للصفحة</a>
</div></body></html>"""


def create_app():
    # Windows registry MIME associations can override Python's font/woff2 default.
    # Keep bundled font responses identical across preview and installed WebView2.
    mimetypes.add_type("font/woff2", ".woff2")
    from services.bootstrap import initialize
    from data_access import database as db
    initialize()
    app = Flask(__name__, template_folder=str(RESOURCE_DIR / "templates"),
                static_folder=str(RESOURCE_DIR / "static"))
    secret = db.get_setting("session_secret")
    if not secret:
        secret = secrets.token_hex(32)
        db.set_setting("session_secret", secret)
    preview = os.environ.get("LOGISTICS_PREVIEW") == "1"
    app.config.update(SECRET_KEY=secret, TEMPLATES_AUTO_RELOAD=True,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=preview,
                      SESSION_COOKIE_SAMESITE="None" if preview else "Lax",
                      MAX_CONTENT_LENGTH=2048 * 1024 * 1024,   # ٢ جيجا لصور وفيديو المناسبات
                      DESKTOP=os.environ.get("LOGISTICS_DESKTOP") == "1")
    if preview:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    @app.after_request
    def _no_cache_html(resp):
        """الصفحات ديناميكية دايمًا — ممنوع كاش المتصفح يعرض نسخة قديمة
        (المستخدم شاف شاشات قديمة مرتين بسبب كاش الموبايل)."""
        ct = resp.headers.get("Content-Type", "")
        if ct.startswith("text/html"):
            resp.headers["Cache-Control"] = "no-store, must-revalidate"
        return resp

    from core import web
    from routes import main
    from routes.rations import rations_bp
    from routes.letterhead import letterhead_bp
    from routes.backups import backups_bp
    from routes.recruits import recruits_bp
    from routes.tameedat import tameedat_bp
    from routes.calc2 import calc2_bp
    from routes.calc2_free import calc2_free_bp
    from routes.month_copy import copy_bp
    from routes.warehouses import warehouses_bp
    from routes.stores import stores_bp
    from routes.health import health_bp
    from routes.tarfea import tarfea_bp
    from routes.raghibin import raghibin_bp
    from routes.assistant import assistant_bp
    from routes.files_tree import files_tree_bp
    from routes.occasions import occasions_bp
    app.register_blueprint(copy_bp)
    web.register(app)
    main.register(app)
    for bp in (rations_bp, letterhead_bp, backups_bp, recruits_bp, tameedat_bp, calc2_bp,
               calc2_free_bp, warehouses_bp, stores_bp, health_bp, tarfea_bp,
               raghibin_bp, assistant_bp, files_tree_bp, occasions_bp):
        app.register_blueprint(bp)
    app.add_url_rule("/health", "health", lambda: {"status": "ready", "version": APP_VERSION})

    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0   # JS/CSS تتأكد من السيرفر دايمًا

    @app.after_request
    def _no_store_html(response):
        # صفحات المنظومة ديناميكية دايمًا — يمنع تصفح صفحة قديمة من كاش المتصفح
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(413)
    def _upload_too_large(_error):       # noqa: ANN001 — رفض الرفعة بلغة عربية واضحة
        return app.response_class(UPLOAD_TOO_LARGE_HTML, status=413, mimetype="text/html")

    try:  # فولدر الموديلات + ملف «اقرأني» — يُنشآن عند التشغيل (بلا أي شبكة)
        from services.assistant import model_store
        model_store.ensure_folder()
    except Exception:      # noqa: BLE001 — لا يعطّل التشغيل أبدًا
        pass

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
