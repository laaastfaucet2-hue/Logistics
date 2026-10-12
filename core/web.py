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
            "alert_ignored_names": tameed_alerts.ignored_names(year, month),
            "alert_day_href": href_for_day}


def _letterhead_print_vars(year, month):
    """دباجة وتوقيعات الشهر النشط — لأي window.print() في المنظومة."""
    try:
        from data_access.db_letterhead import template_vars
        return template_vars(year, month)
    except Exception:  # noqa: BLE001 — الطباعة لا تسقط الصفحة
        try:  # التوقيعان يظلان يُطبعان حتى لو تعذّرت قراءة قاعدة الشهر (محفوظان في system.db)
            from data_access.db_letterhead import get_signatures
            signatures = get_signatures()
            right = (signatures["sig_right_rank"], signatures["sig_right_name"])
            left = (signatures["sig_left_rank"], signatures["sig_left_name"])
        except Exception:  # noqa: BLE001
            right = left = ("", "")
        return {"lh": ["", "", "", ""], "sig_right": right, "sig_left": left,
                "has_logo": False}


def register(app):
    app.add_template_filter(dates.format_date, "datefmt")
    app.add_template_filter(dates.input_date, "dateinput")
    app.add_template_global(dates.period_date, "period_date")
    # تسميات فئات القوة (ضابط/فرد/مجندين) — مصدر واحد لكل عرض في التاميدات والراغبين (توجيه ٠٨/١٠/٢٠٢ — الحروف اتشالت)
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

    def visible_subtabs(section, subs):
        """فلترة تنقل التابات الداخلية حسب صلاحية المستخدم (توجيه ١٠/١٠).
        الـ admin يشوف الكل. لو التاب مش موجود في السجل → يبان (أقسام بلا توابت)."""
        user = getattr(g, "user", None) or session.get("user")
        if not user or not subs or user.get("role") == "admin":
            return subs
        from core import tabs_registry as tr
        known = [k for k, _n in tr.SUBTABS.get(section, [])]
        if not known:
            return subs
        allowed = tr.allowed_subtabs(user, section)
        return [s for s in subs if s[0] in allowed]

    app.add_template_global(visible_subtabs, "visible_subtabs")
    # وسم الجهة المجمّع (رئيسية + ملحقات) → كل جهة في شيبها الملوّن الخاص
    from data_access import db_permits as dp
    app.add_template_global(dp.split_entity_label, "split_entities")
    # «الورق = الإكسل»: أعمدة كل كشف من مصدر واحد (services/sheet_columns.py)
    from services import sheet_columns as sc
    app.add_template_global(sc.TAMEEDAT_DAY, "cols_day")
    app.add_template_global(sc.TAMEEDAT_MOMODA, "cols_momoda")
    app.add_template_global(sc.TAMEEDAT_DICT, "cols_dict")
    # أسماء ملفات التاميدات المحلية — مصدر واحد يقرأ منه زر «فتح ملف» (يوم يتب بيومه)
    from services import tameedat_fs
    app.add_template_global(tameedat_fs.day_file_name, "day_file_name")

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
        except Exception:  # noqa: BLE001 — الجرس لا يسقط أي صفحة
            groups, count = [], 0
        # 🗒️ مجموعة «الملاحظات» — تفضل على كل المجموعات (توجيه ١٠/١٠)
        try:
            from data_access import db_users
            un = db_users.unread_counts(user["id"])
            entries = []
            if un["to_me"]:
                entries.append({"text": f"📥 {un['to_me']} ملحوظة جديدة — يفتح عليها ويرد",
                                "href": f"/settings?sub=notes{'&sid=' + sid if sid else ''}"})
            if un["for_me"]:
                entries.append({"text": f"✅ اترد عليك في {un['for_me']} ملحوظة",
                                "href": f"/settings?sub=notes{'&sid=' + sid if sid else ''}"})
            if entries:
                groups.insert(0, {"key": "notes", "icon": "🗒️", "title": "الملاحظات",
                                  "level": "warn", "entries": entries})
                count += len(entries)
        except Exception:  # noqa: BLE001
            pass
        return {"bell_groups": groups, "bell_count": count}


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
        # لوجو المنظومة المرفوع (تاب «الهوية للمنظمة») — أو None ليعود الشعار الأصلي.
        # يظهر على كل الصفحات بما فيها تسجيل الدخول (السياق متاح بلا مستخدم).
        try:
            from data_access import db_identity
            _lname = db_identity.get_logo()
            _lp = storage.identity_dir() / _lname if _lname else None
            ctx["app_logo"] = ({"name": _lname, "v": int(_lp.stat().st_mtime)}
                               if _lp and _lp.exists() else None)
        except Exception:      # noqa: BLE001 — فشل اللوجو لا يسقط أي صفحة
            ctx["app_logo"] = None
        if user:
            year, month = current_context(user["id"])
            nav_items = nav_monthly()
            extra = [p for p in EXTRA_PAGES if p["key"] != "calc2"]
            notes_unread = {"to_me": 0, "for_me": 0}
            if user.get("role") != "admin":
                # الشريط الجانبي بيخفي الأقسام اللي مش مسموحة — القسم يظهر لو
                # مسموح كله أو تويب واحد على الأقل جواه (توجيه ١٠/١٠)
                from core import tabs_registry as tr
                nav_items = [s for s in nav_items if tr.section_visible(user, s["key"])]
                extra = [p for p in extra if tr.section_visible(user, p["key"])]
            try:
                from data_access import db_users
                notes_unread = db_users.unread_counts(user["id"])
            except Exception:  # noqa: BLE001
                pass
            ctx.update(
                sections=SECTIONS,
                extra_pages=extra,
                nav_monthly=nav_items,
                notes_unread=notes_unread,
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


    @app.template_filter("andjoin")
    def andjoin_names(names):
        """دمج أسماء بالعربي: «أحمد» / «محمد وأحمد» / «محمد، أحمد، وعلي»."""
        from services.notifications import and_join
        return and_join(names)

    @app.template_filter("qty")
    def qty_number(value):
        """كمية بلا أصفار زائدة: 2.25 → «٢٫٢٥» و7500 → «٧٥٠٠» — نفس ما يُكتب في الإكسل."""
        return arnum.fmt_qty_trim(value)


    @app.template_filter("qty3")
    def qty3_number(value):
        """كمية بثلاثة أرقام عشرية عربية دائمًا: 0.12 → ٠٫١٢٠ و75 → ٧٥٫٠٠٠"""
        return arnum.fmt_qty(value if value != "" else None)

    @app.template_filter("ivnum")
    def ivnum_number(value):
        """«6 مخازن» — أرقام لاتينية صيغ 0.### زي ملف التصميم المعتمد (1.250 → 1.25)."""
        if value in (None, ""):
            return ""
        try:
            n = round(float(value), 3)
        except (TypeError, ValueError):
            return value
        if n == int(n):
            return str(int(n))
        return f"{n:.3f}".rstrip("0").rstrip(".")


    @app.template_filter("oval")
    def oval_value(value):
        """قيمة داخل حقل إدخال: اللاشيء = ٠ (بدل طباعة كلمة None)، وغيره بثلاث خانات عربية."""
        if value is None or value == "":
            return "٠"
        return arnum.fmt_qty(value)


    @app.template_filter("qtyx")
    def qtyx_number(value):
        """مقرر بالشخص بالقيمة المدخلة — بلا تقريب (توجيه ١٠/١٠: كمون ٠٫٠٠٢٥)."""
        return arnum.fmt_qty_exact(value)


    @app.template_filter("ovalx")
    def ovalx_value(value):
        """مقرر داخل حقل إدخال — بالظبط (٠٫٠٠٢٥ يرجع زي ما دخله المستخدم)."""
        if value is None or value == "":
            return "٠"
        return arnum.fmt_qty_exact(value)


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
            "pack_inner_unit": (row.get("pack_inner_unit") or "").strip(),
            "pack_loose_unit": (row.get("pack_loose_unit") or "").strip(),
            "producer": (row.get("producer") or "").strip(),
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
        if endpoint.startswith("settings."):
            # «الإعدادات» مش تاب شهري — يتحمل sid بس (بلا سنة/شهر)
            sid = getattr(g, "sid", None) or request.args.get("sid")
            if sid:
                values.setdefault("sid", sid)
            return
        if not endpoint.startswith(("recruits.", "letterhead.", "rations.", "tameedat.",
                                    "calc2.", "calc2_free.", "warehouses.", "stores.",
                                    "dowail.", "tarfea.", "occasions.", "backups.",
                                    "health.", "stats.", "raghibin.", "month_copy.")):
            return
        user = getattr(g, "user", None) or session.get("user")
        if user:
            year, month = current_context(user["id"])
            values.setdefault("year", year)
            values.setdefault("month", month)
            sid = getattr(g, "sid", None) or request.args.get("sid")
            if sid:
                values.setdefault("sid", sid)
