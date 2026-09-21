"""Template context and central Arabic formatting filters."""
from flask import g, session, request, current_app
from core.paths import APP_VERSION
from data_access import storage
from core import arabic_numbers as arnum
from core.auth_core import current_context
from core.config import MONTH_NAMES, SECTIONS, EXTRA_PAGES, STATIC_VER

def register(app):
    @app.context_processor
    def inject_bell():
        """🔔 مجموعات إشعارات الجرس لكل الصفحات — بتاريخ القاهرة الحقيقي دائمًا."""
        user = getattr(g, "user", None) or session.get("user")
        if not user:
            return {}
        try:
            from services import notifications
            sid = getattr(g, "sid", None) or request.args.get("sid") or ""
            groups, count = notifications.summarize(user["id"], sid)
            return {"bell_groups": groups, "bell_count": count}
        except Exception:  # noqa: BLE001 — الجرس لا يسقط أي صفحة
            return {"bell_groups": [], "bell_count": 0}


    @app.context_processor
    def inject_auth():
        user = getattr(g, "user", None) or session.get("user")
        sid = getattr(g, "sid", None) or request.args.get("sid") or ""
        ctx = {"current_user": user, "sid": sid, "static_ver": STATIC_VER,
               "app_version": APP_VERSION, "desktop_mode": current_app.config["DESKTOP"]}
        if user:
            year, month = current_context(user["id"])
            ctx.update(
                sections=SECTIONS,
                extra_pages=EXTRA_PAGES,
                static_ver=STATIC_VER,
                years=storage.list_years(),
                months=list(enumerate(MONTH_NAMES, start=1)),
                ctx_year=year,
                ctx_month=month,
            )
        return ctx


    @app.template_filter("fmt")
    def fmt_number(value):
        try:
            n = float(value)
            return arnum.to_arabic_indic(f"{int(n):,}" if n == int(n) else f"{n:,.1f}")
        except (TypeError, ValueError):
            return value


    @app.template_filter("aindic")
    def aindic_number(value):
        """عرض الرقم بالأرقام العربية المشرقية: 2026 → ٢٠٢٦"""
        return arnum.to_arabic_indic(value)


    @app.template_filter("qty3")
    def qty3_number(value):
        """كمية بثلاثة أرقام عشرية عربية دائمًا: 0.12 → ٠٫١٢٠ و75 → ٧٥٫٠٠٠"""
        return arnum.fmt_qty(value if value != "" else None)


    @app.template_filter("oval")
    def oval_value(value):
        """قيمة داخل حقل إدخال: اللاشيء = ٠ (بدل طباعة كلمة None)، وغيره بثلاث خانات عربية."""
        if value is None or value == "":
            return "٠"
        return arnum.fmt_qty(value)



    @app.url_defaults
    def scoped_urls(endpoint, values):
        if not endpoint.startswith(("recruits.", "letterhead.", "rations.")):
            return
        user = getattr(g, "user", None) or session.get("user")
        if user:
            year, month = current_context(user["id"])
            values.setdefault("year", year)
            values.setdefault("month", month)
            sid = getattr(g, "sid", None) or request.args.get("sid")
            if sid:
                values.setdefault("sid", sid)
