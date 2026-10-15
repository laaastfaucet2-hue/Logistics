"""Application factory and route wiring only. See CONTRIBUTING.md."""
import logging
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
<p>الحد الأقصى للرفع الواحد <b>٢ جيجابايت</b> (حتى <b>٣٠ ملفًا</b> في الرفع).</p>
<p>قلّل حجم الملف أو قسّم الرفع على دفعات، ثم ارجع وحاول مرة أخرى.</p>
<a href="javascript:history.back()">↩ رجوع للصفحة</a>
</div></body></html>"""


def _section_target(section, sub, token):
    """رابط أول تويب مسموح جوه قسم (تحويلة لطيفة بدل 403 على رابط القسم العاري)."""
    if not section or not sub:
        return None
    from flask import url_for
    sid = {"sid": token} if token else {}
    try:
        if section == "settings":
            return url_for("settings.page", sub=sub, **sid)
        if section == "warehouses_records":
            return url_for("warehouses.page", sub=sub, **sid)
        if section == "tarfea":
            return url_for("tarfea.page", sub=sub, **sid)
        if section == "tameedat":
            return url_for("tameedat.page", tab=sub, **sid)
        if section == "calc2":
            if sub == "main":
                return url_for("calc2.page", **sid)
            if sub == "free":
                return url_for("calc2_free.free_page", **sid)
            if sub == "dowail":
                return url_for("dowail.page", **sid)
    except Exception:      # noqa: BLE001 — اسم endpoint غير متوقع → 403 العادي
        return None
    return None


def _action_verb(path):
    """اسم عملي للإجراء من شكل الرابط (للسجل)."""
    p = path
    if "delete" in p:
        return "حذف"
    if "download" in p:
        return "تنزيل ملف"
    if "restore" in p:
        return "استعادة نسخة"
    if "open" in p:
        return "فتح ملف/فولدر"
    if any(k in p for k in ("add", "save", "apply", "create", "update", "edit",
                            "strike", "price", "meta", "set", "copy")):
        return "حفظ/تعديل"
    return "إجراء"


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

    # ==================================================================
    # «الإعدادات»: صلاحيات التابات + سجل الحركة (مركزي — بلا تعديل الروات)
    # ==================================================================
    @app.before_request
    def _perms_and_pages():
        from flask import g, request, render_template, redirect, url_for
        from core.auth_core import current_session
        from core import tabs_registry as tr
        user, token = current_session()
        if not user:
            return None
        g.user, g.sid = user, token
        path = request.path
        if path.startswith(("/static/", "/assistant/", "/api/")):
            return None
        tab = tr.tab_key_for_request(path, request.args,
                                     request.form if request.method == "POST" else None)
        if tab is None:
            return None
        if not tr.has_permission(user, tab):
            # القسم كله محجوب لكن فيه تويب مسموح → نقذف لأول تويب مسموح (GET فقط)
            if ":" not in tab and request.method == "GET":
                sub = tr.first_allowed_sub(user, tab)
                target = _section_target(tab, sub, token)
                if target:
                    return redirect(target)
            return render_template("forbidden.html", tab=tab), 403
        if request.method == "GET":
            from data_access import db_users
            db_users.log_activity(user["id"], "page", tab)
        return None

    @app.after_request
    def _log_actions(resp):
        """كل POST ناجح/فاشل على تاب = حركة «إجراء» في سجل المستخدم."""
        from flask import g, request
        user = getattr(g, "user", None)
        if not user or request.method != "POST":
            return resp
        path = request.path
        if path.startswith(("/static/", "/assistant/", "/api/")):
            return resp
        from core import tabs_registry as tr
        from core import action_names
        # حركات الملاحظات بتتسجل بمفردها بالتفاصيل (من/إلى/رقم) — مفيش تكرار
        if not request.endpoint or request.endpoint.startswith("settings.notes_"):
            return resp
        tab = tr.tab_key_for_request(path, request.args, request.form)
        if tab is None:
            return resp
        from data_access import db_users
        loc = resp.headers.get("Location", "")
        failed = resp.status_code >= 400 or "err=" in loc
        obj = action_names.form_name(request.form)
        detail = f"{'فشل: ' if failed else ''}{_action_verb(path)} ({request.endpoint})"
        if obj:
            detail += f" — {obj}"
        db_users.log_activity(user["id"], "action", tab, detail)
        return resp

    @app.after_request
    def _stats_stores_refresh(resp):
        """بعد أي حفظ ناجح يأثر على المخازن: تحديث ملفات إحصائيات المخازن في الخلفية
        (نقطة واحدة بدل تعديل كل الروات — الحفظات المتتالية تتجمع في تحديث واحد)."""
        from flask import g, request
        user = getattr(g, "user", None)
        if not user or request.method != "POST":
            return resp
        if resp.status_code >= 400 or "err=" in resp.headers.get("Location", ""):
            return resp
        try:
            from core.auth_core import current_context
            from services import stats_stores
            if request.path.startswith(stats_stores.REFRESH_PREFIXES):
                year, month = current_context(user["id"])
                stats_stores.after_save(request.path, request.form, year, month,
                                        background=not app.config.get("TESTING"))
        except Exception:  # noqa: BLE001 — طلب التحديث لا يُسقط الحفظ نفسه أبدًا
            logging.getLogger(__name__).exception("stats stores refresh request failed")
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
    from routes.dowail import dowail_bp
    from routes.month_copy import copy_bp
    from routes.warehouses import warehouses_bp
    from routes.wh4 import wh4_bp
    from routes.inv6 import inv6_bp
    from routes.stores import stores_bp
    from routes.health import health_bp
    from routes.tarfea import tarfea_bp
    from routes.raghibin import raghibin_bp
    from routes.stats import stats_bp
    from routes.stats_stores import stats_stores_bp
    from routes.assistant import assistant_bp
    from routes.files_tree import files_tree_bp
    from routes.occasions import occasions_bp
    from routes.settings import settings_bp
    app.register_blueprint(copy_bp)
    web.register(app)
    main.register(app)
    for bp in (rations_bp, letterhead_bp, backups_bp, recruits_bp, tameedat_bp, calc2_bp,
               calc2_free_bp, dowail_bp, warehouses_bp, wh4_bp, stores_bp, health_bp,
               tarfea_bp, raghibin_bp, stats_bp, stats_stores_bp, assistant_bp, files_tree_bp,
               occasions_bp, inv6_bp, settings_bp):
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
