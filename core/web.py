"""Template context and central Arabic formatting filters."""
from flask import g, session, request, current_app
from core.paths import APP_VERSION
from data_access import storage
from core import arabic_numbers as arnum, dates, egtime
from core.auth_core import current_context
from core.config import MONTH_NAMES, DAYS, SECTIONS, EXTRA_PAGES, STATIC_VER, nav_monthly


def alerts_context(year, month, href_for_day):
    """متغيرات جدول تنبيهات التاميدات↔الراغبين لكل أيام الشهر (توجيه ٠٦/١٠/٢٠٢٦).

    href_for_day(day) يبني رابط الانتقال ليوم محدد في القسم الذي يعرض الجدول،
    فيُستخدم الجدول نفسه في «التاميدات» و«الراغبين» بلا تكرار.
    """
    from services import tameed_alerts
    return {"alert_rows": tameed_alerts.month_rows(year, month),
            "alert_summary": tameed_alerts.summary(year, month),
            "alert_day_href": href_for_day}


def _letterhead_print_vars(year, month):
    """دباجة وتوقيعات الشهر النشط — لأي window.print() في المنظومة."""
    try:
        from data_access.db_letterhead import template_vars
        return template_vars(year, month)
    except Exception:  # noqa: BLE001 — الطباعة لا تسقط الصفحة
        try:  # التوقيعات المثبّتة تظل تُطبع حتى لو تعذّرت قراءة قاعدة الشهر
            from data_access.db_letterhead import PINNED
            right = (PINNED["sig_right_rank"], PINNED["sig_right_name"])
            left = (PINNED["sig_left_rank"], PINNED["sig_left_name"])
        except Exception:  # noqa: BLE001
            right = left = ("", "")
        return {"lh": ["", "", "", ""], "sig_right": right, "sig_left": left,
                "has_logo": False}


def register(app):
    app.add_template_filter(dates.format_date, "datefmt")
    app.add_template_filter(dates.input_date, "dateinput")
    app.add_template_global(dates.period_date, "period_date")
    # مفتاح الحروف ض/أ/م — مصدر واحد لكل عرض في التاميدات والراغبين (توجيه ٠٦/١٠/٢٠٢٦)
    from core import labels
    app.add_template_global(labels.pair3, "pair3")
    app.add_template_global(labels.pair2, "pair2")
    app.add_template_global(labels.triple_slash, "slash3")
    app.add_template_global(labels.slash2, "slash2")
    app.add_template_global(labels.LEGEND, "tri_legend")
    app.add_template_global(labels.LEGEND_TWO, "pair_legend")
    # الألوان الثابتة للأصناف/الجهات/الأشخاص (توجيه ٠٦/١٠/٢٠٢٦)
    from core import colors
    app.add_template_global(colors.color_for, "color")
    app.add_template_global(colors.ring_style, "color_ring")
    # «الورق = الإكسل»: أعمدة كل كشف من مصدر واحد (services/sheet_columns.py)
    from services import sheet_columns as sc
    app.add_template_global(sc.TAMEEDAT_DAY, "cols_day")
    app.add_template_global(sc.TAMEEDAT_MOMODA, "cols_momoda")
    app.add_template_global(sc.TAMEEDAT_DICT, "cols_dict")
    app.add_template_global(sc.FREE_RATE, "cols_ft_rate")
    app.add_template_global(sc.FREE_SHEET, "cols_ft_sheet")
    app.add_template_global(sc.FREE_POINT, "cols_ft_point")
    app.add_template_global(sc.FREE_DIST, "cols_ft_dist")

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
        today = egtime.today()
        ctx = {"current_user": user, "sid": sid, "static_ver": STATIC_VER,
               "app_version": APP_VERSION, "desktop_mode": current_app.config["DESKTOP"],
               "today_date": today, "today_weekday": egtime.weekday_ar(today),
               "date_config": {"format": dates.DISPLAY_FORMAT, "months": MONTH_NAMES,
                               "weekdays": DAYS, "today": today.isoformat(),
                               "timeZone": "Africa/Cairo", "digits": arnum.digit_sets()}}
        if user:
            year, month = current_context(user["id"])
            ctx.update(
                sections=SECTIONS,
                extra_pages=[p for p in EXTRA_PAGES if p["key"] != "calc2"],
                nav_monthly=nav_monthly(),
                static_ver=STATIC_VER,
                years=storage.list_years(),
                months=list(enumerate(MONTH_NAMES, start=1)),
                ctx_year=year,
                ctx_month=month,
                **_letterhead_print_vars(year, month),
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


    @app.template_filter("qty")
    def qty_number(value):
        """كمية بلا أصفار زائدة: 2.25 → «٢٫٢٥» و7500 → «٧٥٠٠» — نفس ما يُكتب في الإكسل."""
        return arnum.fmt_qty_trim(value)


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


    def _wh1line_payload(row):
        """سطر إذن ١ مخازن → قاموس تعبئة فورم التعديل (توجيه ٢٧/٠٩)."""
        return {
            "item_name": row.get("item_name") or "",
            "handle_unit": row.get("unit") or "",
            "qty": float(row.get("qty_handle") or 0),
            "pack_kind": (row.get("pack_kind") or "").strip(),
            "pack_count": row.get("pack_count") or None,
            "pack_capacity": row.get("pack_capacity") or None,
            "pack_loose": row.get("pack_loose") or None,
            "pack_inner_kind": (row.get("pack_inner_kind") or "").strip(),
            "pack_inner_count": row.get("pack_inner_count") or None,
            "pack_inner_capacity": row.get("pack_inner_capacity") or None,
            "pack_loose_unit": (row.get("pack_loose_unit") or "").strip(),
            "prod_date": row.get("prod_date") or "",
            "exp_date": row.get("exp_date") or "",
            "stores": [{"store_id": st.get("store_id") or "",
                        "store_name": st.get("store_name") or "",
                        "qty": float(st.get("qty") or 0)}
                       for st in (row.get("stores") or [])],
        }


    @app.template_filter("wh1edit_json")
    def wh1edit_json(lines):
        """سطور إذن التعديل → JSON سليم للتاج <script> (v82).

        كان العيب: json.dumps بيرجّع نص عادي فالقالب بيتشفّله (&#34;)
        والمتصفح مش بيفك التشفير جوّه script فكان JSON.parse بيفشل والفورم بيرجع فاضي.
        """
        import json as _json
        from markupsafe import Markup
        payload = [_wh1line_payload(row) for row in (lines or [])]
        raw = _json.dumps(payload, ensure_ascii=False)
        # نفس حيَل tojson: المحارف اللي ممكن تكسر التاج تتحول لتهريب يونيكود
        raw = (raw.replace("<", "\\u003c").replace(">", "\\u003e")
                  .replace("&", "\\u0026").replace("\u2028", "\\u2028")
                  .replace("\u2029", "\\u2029"))
        return Markup(raw)




    @app.url_defaults
    def scoped_urls(endpoint, values):
        if not endpoint.startswith(("recruits.", "letterhead.", "rations.", "tameedat.", "calc2.", "warehouses.", "stores.")):
            return
        user = getattr(g, "user", None) or session.get("user")
        if user:
            year, month = current_context(user["id"])
            values.setdefault("year", year)
            values.setdefault("month", month)
            sid = getattr(g, "sid", None) or request.args.get("sid")
            if sid:
                values.setdefault("sid", sid)
