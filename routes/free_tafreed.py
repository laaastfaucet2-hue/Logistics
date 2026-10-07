# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحات «التفاريد الحرة وتفاريد الدول» — قسم مستقل تمامًا (توجيه ٠٦/١٠/٢٠٢٦).

أربع تابات كما في الشاشة المرجعية:
  ١) حسابة الصرف وطباعة الإذن (`calc`)  ٢) عمل التفريدة (`make`)
  ٣) تفريدات الدول (`intl`)              ٤) معدلات الأصناف (`rates`)
+ زر «فتح المجلد» وطباعات ثلاثة (إذن مجمع · بيان توزيع · ورقة نقطة).

**قاعدة ملزمة:** لا قراءة ولا كتابة لأي جدول أو ملف من المخازن/المقررات —
المعدلات لقطة تُسحب مرة ثم تُعدَّل بحرية، والملفات في فولدر مستقل (14-التفاريد الحرة).
"""
from flask import (Blueprint, render_template, request, redirect, url_for, g, send_file,
                   abort, current_app)
from core.auth_core import login_required, current_context, current_session
from core import arabic_numbers as arnum, dates, egtime
from core.config import MONTH_NAMES
from data_access import db_free_tafreed as db
from services import free_tafreed_calc as calc, free_tafreed_fs as fs

free_tafreed_bp = Blueprint("free_tafreed", __name__, url_prefix="/free-tafreed")

TABS = [("calc", "حسابة الصرف وطباعة الإذن", "🧮"),
        ("make", "عمل التفريدة", "🧾"),
        ("intl", "تفريدات الدول", "🌍"),
        ("rates", "معدلات الأصناف", "⚙️")]
TAB_KEYS = {key for key, _name, _icon in TABS}
OPENERS = [("أوراق وإيصالات الصرف", "📄"), ("إجمالي خطوط التوزيع", "🧮"),
           ("إدارة الخطوط والنقاط", "➕"), ("تعديل معدلات الأصناف", "⚙️")]


def _ctx():
    from data_access import months
    year, month = current_context(g.user["id"])
    months.init_month(year, month)
    return year, month


def _rb(tab="calc", ok=None, err=None, **extra):
    _, token = current_session()
    params = {"tab": tab}
    if token:
        params["sid"] = token
    if ok:
        params["ok"] = ok
    if err:
        params["err"] = err
    params.update({k: v for k, v in extra.items() if v not in (None, "")})
    return redirect(url_for("free_tafreed.page", **params))


def _int(raw, fallback=1):
    value = arnum.parse_int(raw)
    return fallback if value in (None, "") else int(value)


def _float(raw, fallback=0.0):
    value = arnum.parse_float(raw)
    return fallback if value is None else float(value)


def _day(year, month, raw, fallback=1):
    day = _int(raw, fallback)
    last = egtime.days_in_month(year, month)
    return min(max(int(day), 1), last)


def _lines_with_points(year, month, line_id=None):
    lines = db.list_lines(year, month) if not line_id else [db.get_line(year, month, line_id)]
    out = []
    for line in lines:
        if not line:
            continue
        line["points_list"] = db.list_points(year, month, line["id"])
        out.append(line)
    return out


def _rates_with_serial(year, month, kind=None):
    rates = db.list_rates(year, month, kind)
    for index, rate in enumerate(rates, start=1):
        rate["serial"] = index
        rate["days_count"] = len(rate.get("days") or [])
    return rates


def _sheet_context(year, month, tab):
    """متغيرات مشتركة لكل تابات القسم — بلا أي None في الواجهة."""
    return {
        "year": year, "month": month, "month_name": MONTH_NAMES[month - 1],
        "tab": tab, "tabs": TABS, "openers": OPENERS,
        "lines": _lines_with_points(year, month),
        "line_cards": calc.line_summary(_lines_with_points(year, month)),
        "rates": _rates_with_serial(year, month),
        "rates_tamween": _rates_with_serial(year, month, "tamween"),
        "rates_contractor": _rates_with_serial(year, month, "contractor"),
        "days_range": list(range(1, db.MAX_DAYS + 1)),
        "sheets_free": db.list_sheets(year, month, "free"),
        "sheets_intl": db.list_sheets(year, month, "intl"),
        "sheets_pending": db.list_sheets(year, month, pending=True),
        "sheets_done": db.list_sheets(year, month, pending=False),
        "query": (request.args.get("q") or "").strip(),
        "found_points": (db.find_points(year, month, request.args.get("q") or "")
                         if (request.args.get("q") or "").strip() else []),
        "day_from": _day(year, month, request.args.get("from"), _default_day(year, month)),
        "day_to": _day(year, month, request.args.get("to"), _default_day(year, month)),
        "ok": request.args.get("ok") or "", "err": request.args.get("err") or "",
    }


def _default_day(year, month):
    today = egtime.today()
    return today.day if (today.year, today.month) == (year, month) else 1


# ======================================================================
# الصفحة والتابات
# ======================================================================
@free_tafreed_bp.route("")
@free_tafreed_bp.route("/")
@login_required
def page():
    year, month = _ctx()
    tab = request.args.get("tab") or "calc"
    if tab not in TAB_KEYS:
        tab = "calc"
    ctx = _sheet_context(year, month, tab)
    if tab == "rates":
        ctx["rates"] = _rates_with_serial(year, month)
    return render_template("free_tafreed/main.html", **ctx)


# ======================================================================
# الحساب اللحظي (بلا تخزين)
# ======================================================================
@free_tafreed_bp.route("/compute")
@login_required
def compute():
    """حساب فوري بموجب القوة وعدد الأيام — للعرض في التابين (JSON، بلا كتابة)."""
    from flask import jsonify
    year, month = _ctx()
    force = _int(request.args.get("force"), 0)
    days = max(1, _int(request.args.get("days"), 1))
    kind = request.args.get("kind") or None
    rates = _rates_with_serial(year, month, kind)
    rows = calc.build_rows(rates, force, days)
    return jsonify({"rows": rows, "force": force, "days": days,
                    "totals": calc.totals_by_item([{"cells": rows}])})


# ======================================================================
# معدلات الأصناف
# ======================================================================
@free_tafreed_bp.route("/rates/save", methods=["POST"])
@login_required
def rates_save():
    year, month = _ctx()
    try:
        db.upsert_rate(
            year, month,
            request.form.get("name"), request.form.get("unit"),
            _float(request.form.get("rate"), 0),
            request.form.get("kind") or "tamween",
            active=bool(request.form.get("active")),
            days=[d for d in range(1, db.MAX_DAYS + 1)
                  if request.form.get(f"day_{d}")] or [1],
            sort=_int(request.form.get("sort"), 0))
    except ValueError as exc:
        return _rb("rates", err=str(exc))
    fs.write_rates(year, month, _rates_with_serial(year, month))
    return _rb("rates", ok="حُفظ معدّل الصنف في ملفات القسم المستقلة — "
                           "بلا أي مساس بمقررات التموين أو المتعهد")


@free_tafreed_bp.route("/rates/seed", methods=["POST"])
@login_required
def rates_seed():
    """«اسحب الأصناف من المقررات» — لقطة تُنسخ ثم تصبح حرة تمامًا."""
    year, month = _ctx()
    added = db.seed_rates_from_rations(year, month)
    fs.write_rates(year, month, _rates_with_serial(year, month))
    if not added:
        return _rb("rates", err="لا أصناف جديدة — المقررات مسحوبة بالفعل "
                                "(أو لا يوجد مقرر مفعّل هذا الشهر)")
    return _rb("rates", ok=f"تم سحب {arnum.to_arabic_indic(added)} صنفًا من المقررات "
                           "كلقطة حرة — عدّلها كما تريد فلن تمس المقررات")


@free_tafreed_bp.route("/rates/<int:rate_id>/<action>", methods=["POST"])
@login_required
def rates_action(rate_id, action):
    year, month = _ctx()
    if action == "delete":
        db.delete_rate(year, month, rate_id)
        message = "حُذف الصنف من معدلات التفاريد الحرة"
    elif action == "toggle":
        db.set_rate_active(year, month, rate_id, request.form.get("on") == "1")
        message = "تم تغيير تفعيل الصنف"
    elif action == "day":
        db.toggle_rate_day(year, month, rate_id, _int(request.form.get("day"), 1),
                           request.form.get("on") == "1")
        message = "تم تحديث أيام الصرف للصنف"
    else:
        abort(404)
    fs.write_rates(year, month, _rates_with_serial(year, month))
    return _rb("rates", ok=message)


# ======================================================================
# الخطوط والنقاط
# ======================================================================
@free_tafreed_bp.route("/lines/add", methods=["POST"])
@login_required
def lines_add():
    year, month = _ctx()
    try:
        db.add_line(year, month, request.form.get("name"), request.form.get("notes"),
                    default_points=_int(request.form.get("points"), 0))
    except ValueError as exc:
        return _rb("intl", err=str(exc))
    return _rb("intl", ok=f"أُضيف خط التوزيع «{request.form.get('name')}»")


@free_tafreed_bp.route("/lines/<int:line_id>/<action>", methods=["POST"])
@login_required
def lines_action(line_id, action):
    year, month = _ctx()
    if action == "delete":
        db.delete_line(year, month, line_id)
        return _rb("intl", ok="حُذف الخط بنقاطه")
    if action == "reset":
        db.reset_forces(year, month, line_id)
        return _rb("intl", ok="تم تصفير قوات نقاط الخط — أعد تعيينها كما تريد")
    if action == "rename":
        db.update_line(year, month, line_id, name=request.form.get("name"),
                       notes=request.form.get("notes"))
        return _rb("intl", ok="تم تعديل بيانات الخط")
    abort(404)


@free_tafreed_bp.route("/points/add", methods=["POST"])
@login_required
def points_add():
    year, month = _ctx()
    try:
        db.add_point(year, month, _int(request.form.get("line_id"), 0),
                     request.form.get("name"), _int(request.form.get("force"), 0))
    except ValueError as exc:
        return _rb("intl", err=str(exc))
    return _rb("intl", ok="أُضيفت النقطة ورُبطت بخطها")


@free_tafreed_bp.route("/points/<int:point_id>/<action>", methods=["POST"])
@login_required
def points_action(point_id, action):
    year, month = _ctx()
    if action == "force":
        db.set_point_force(year, month, point_id, _int(request.form.get("force"), 0))
        return _rb("intl", ok="حُدّثت قوة النقطة")
    if action == "toggle":
        db.set_point_active(year, month, point_id, request.form.get("on") == "1")
        return _rb("intl", ok="تم تغيير حالة النقطة")
    if action == "delete":
        db.delete_point(year, month, point_id)
        return _rb("intl", ok="حُذفت النقطة")
    abort(404)


@free_tafreed_bp.route("/points/search")
@login_required
def points_search():
    year, month = _ctx()
    query = (request.args.get("q") or "").strip()
    return {"query": query, "points": db.find_points(year, month, query)}


# ======================================================================
# حفظ الكشوف (تفريدة حرة · تفريدة دول) + طباعتها
# ======================================================================
@free_tafreed_bp.route("/save", methods=["POST"])
@login_required
def save_sheet():
    year, month = _ctx()
    tab = request.form.get("tab") or "make"
    kind = "intl" if tab == "intl" else "free"
    title = " ".join((request.form.get("title") or "").split())
    if not title:
        return _rb(tab, err="اكتب اسم الجهة أو عنوان التفريدة أولًا")
    force = _int(request.form.get("force"), 0)
    day_from = _day(year, month, request.form.get("date_from"), 1)
    day_to = _day(year, month, request.form.get("date_to"), day_from)
    if day_to < day_from:
        day_to = day_from
    days = max(1, _int(request.form.get("days"), day_to - day_from + 1))
    chosen = set(request.form.getlist("pick"))                 # الأنف المختارة في الحساب
    rates = [r for r in _rates_with_serial(year, month) if not chosen or r["name"] in chosen]
    rows = calc.build_rows(rates, force, days)
    payload = {"rows": rows, "totals": calc.totals_by_item([{"cells": rows}]),
               "lines": _lines_short(year, month)}
    sheet_id = db.save_sheet(year, month, kind, title, payload, day_from, day_to, days,
                             force, request.form.get("holder") or "",
                             request.form.get("writer") or "",
                             sheet_id=_int(request.form.get("sheet_id"), 0) or None)
    sheet = db.get_sheet(year, month, sheet_id)
    path = fs.write_free_sheet(year, month, sheet)
    return _rb(tab, ok=f"حُفظت التفريدة «{title}» في ملفات القسم المستقلة "
                       f"({path.name}) — ويمكن طباعتها الآن", sheet=sheet_id)


def _lines_short(year, month):
    """ملخص الخطوط داخل الحفظ — للطباعة لاحقًا بلا إعادة قراءة النقاط."""
    out = []
    for card in calc.line_summary(_lines_with_points(year, month)):
        out.append({"name": card["name"], "points": card["points"], "force": card["force"],
                    "active": card["active"],
                    "points_list": [{"name": p["name"], "force": p["force"],
                                     "active": p["active"]} for p in card["points_list"]]})
    return out


@free_tafreed_bp.route("/sheets/<int:sheet_id>/delete", methods=["POST"])
@login_required
def sheet_delete(sheet_id):
    year, month = _ctx()
    sheet = db.get_sheet(year, month, sheet_id)
    db.delete_sheet(year, month, sheet_id)
    if sheet:
        fs.remove_sheet_files(year, month, sheet)
    return _rb("intl" if (sheet or {}).get("kind") == "intl" else "make",
               ok="حُذفت التفريدة وملفاتها المحلية")


@free_tafreed_bp.route("/sheets/<int:sheet_id>/file/<fmt>")
@login_required
def sheet_file(sheet_id, fmt):
    """تنزيل ملف التفريدة المحلي (إكسل) — «الورق = الإكسل»."""
    year, month = _ctx()
    sheet = db.get_sheet(year, month, sheet_id)
    if not sheet:
        abort(404)
    path = fs.write_free_sheet(year, month, sheet)
    if fmt == "xlsx":
        title = " ".join(str(sheet.get("title") or "").split()) or f"تفريدة {sheet_id}"
        return send_file(str(path), as_attachment=True,
                         download_name=f"{title}.xlsx")
    abort(404)


@free_tafreed_bp.route("/print/<kind>")
@login_required
def print_sheet(kind):
    """الطباعات الثلاثة: permit (إذن مجمع) · dist (بيان توزيع) · point (ورقة نقطة)."""
    year, month = _ctx()
    ctx = _sheet_context(year, month, "make")
    sheet_id = _int(request.args.get("sheet"), 0)
    sheet = db.get_sheet(year, month, sheet_id) if sheet_id else None
    rows = (sheet or {}).get("payload", {}).get("rows") or []
    lines = _lines_with_points(year, month)
    point_id = _int(request.args.get("point"), 0)
    point = next((p for p in db.list_points(year, month) if p["id"] == point_id), None)
    if point:
        line = db.get_line(year, month, point["line_id"])
        point["line_name"] = (line or {}).get("name") or "—"
    # أيام الصرف للبيان: ما أُمر به صراحةً ← عدد أيام التفريدة ← المدة المختارة في الشاشة
    view_days = max(1, _int(request.args.get("days"), 0)
                    or int((sheet or {}).get("days") or 0)
                    or (ctx["day_to"] - ctx["day_from"] + 1))
    dist_rows = calc.distribution_rows(lines, ctx["rates"], view_days)
    from data_access import db_letterhead as lhdb
    ctx.update({
        "sheet": sheet, "rows": rows, "point": point,
        "dist_rows": dist_rows, "dist_totals": calc.totals_by_item(dist_rows),
        "kind": kind, "today_text": dates.format_date(egtime.today().isoformat()),
        "lh": [lhdb.get_setting(year, month, f"lh_{i}") for i in range(1, 5)],
        "sig_right": (lhdb.get_setting(year, month, "sig_right_rank"),
                      lhdb.get_setting(year, month, "sig_right_name")),
        "sig_left": (lhdb.get_setting(year, month, "sig_left_rank"),
                     lhdb.get_setting(year, month, "sig_left_name")),
        "has_logo": bool(lhdb.logo_path(year, month)),
        "title": (sheet or {}).get("title") or (point or {}).get("name") or "",
        "force": (sheet or {}).get("force") or (point or {}).get("force") or 0,
        "days": view_days,
    })
    if kind == "permit":
        if sheet:                                   # فتح الإذن = صرف فعلي ⇒ ينتقل للسجل
            db.mark_printed(year, month, sheet["id"])
            ctx["sheet"] = db.get_sheet(year, month, sheet["id"])
        return render_template("free_tafreed/print_permit.html", **ctx)
    if kind == "dist":
        return render_template("free_tafreed/print_dist.html", **ctx)
    if kind == "point":
        return render_template("free_tafreed/print_point.html", **ctx)
    abort(404)


@free_tafreed_bp.route("/dist/save", methods=["POST"])
@login_required
def dist_save():
    """حفظ «بيان توزيع وإجمالي تعيينات خطوط حراسة الدول» في ملف إكسل محلي.

    «الورق = الإكسل»: نفس الصفوف ونفس الأرقام المعروضة في ورقة الطباعة (مصدر واحد).
    """
    year, month = _ctx()
    sheet_id = _int(request.form.get("sheet"), 0)
    sheet = db.get_sheet(year, month, sheet_id) if sheet_id else None
    days = (sheet or {}).get("days") or max(1, _day(year, month, request.form.get("days"), 1))
    lines = _lines_with_points(year, month)
    rows = calc.distribution_rows(lines, _rates_with_serial(year, month), days)
    totals = calc.totals_by_item(rows)
    if not rows:
        return _rb("intl", err="لا نقاط توزيع بعد — أضف الخطوط والنقاط ثم احفظ البيان")
    record = sheet or {"title": "خطوط حراسة الدول"}      # الكتابة تضيف «بيان توزيع — »
    path = fs.write_distribution(year, month, record, rows, totals)
    return _rb("intl", ok=f"حُفظ بيان التوزيع في ملف الإكسل المحلي ({path.name}) "
                          f"— وورق الطباعة يطابقه بالحرف")


@free_tafreed_bp.route("/open-folder")
@login_required
def open_folder():
    """«فتح المجلد» — فتح فولدر القسم المستقل (وفي نسخة الويب: بيان المسار)."""
    year, month = _ctx()
    folder = fs.free_dir(year, month)
    import os, subprocess, sys
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(folder))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            raise OSError("no gui")
        return _rb("calc", ok="تم فتح مجلد «التفاريد الحرة» 📂")
    except Exception:
        return _rb("calc", err=f"فتح المجلدات متاح من نسخة سطح المكتب — "
                               f"المجلد جاهز على المسار: {folder}")
