# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""قسم «الصحة» — أربعة تابات بتقارير وورد محلية قابلة للتعديل:

- الرش والتعقيم: محضر رش وتقفيم الشهر كاملًا.
- الكشف الدوري على المجندين: ثلاثة أيام بالشهر (قابلة للتعديل) — اختيار المكتوشين
  باقتراح «حاضرو اليوم» من اليومية، وتوليد كشف وورد لكل يوم.
- تطهير الخزانات: محضر بجدول مواصفات الخزانات.
- فحص مياة الشرب: تقرير نتيجة الفحص.

التعديل من الصفحة يحدّث ملف الفولدر المحلي فورًا (مصدر حقيقة واحد).
"""
from datetime import date as _date

from flask import g
from flask import (Blueprint, abort, redirect, render_template, request,
                   url_for, send_file)

from core.auth_core import login_required, current_session, current_context
from core.config import MONTH_NAMES
from core import egtime
from core import arabic_numbers as arnum
from data_access import db_health
from data_access import db_recruits
from data_access import db_letterhead as lhdb
from data_access import storage
from documents import docx_health
from services import health_fs
from services.images import save_logo

health_bp = Blueprint("health", __name__, url_prefix="/health")

TABS = [("spray", "الرش والتعقيم", "🧴"),
        ("checkups", "الكشف الدوري على المجندين", "🩺"),
        ("tanks", "تطهير الخزانات", "🚰"),
        ("water", "فحص مياة الشرب", "💧"),
        ("letter", "الدباجة والتوقيعات", "📜")]
TAB_KEYS = tuple(k for k, _n, _i in TABS)


def _ctx():
    return current_context(g.user["id"])


def _rb(tab, day=0, ok=None, err=None):
    _, token = current_session()
    year, month = _ctx()
    return redirect(url_for("health.page", year=year, month=month, tab=tab,
                            day=day or None, sid=token, ok=ok, err=err))


def _field_rows(year, month, report):
    """حقول التقرير جاهزة للعرض: (key, label, kind, value) — التوقيعات الفارغة
    ترجع للافتراضي من الدباجة."""
    stored = db_health.get_fields(year, month, report)
    hdr_defs = db_health.get_fields(year, month, "header")
    rows = []
    for key, label, kind, default in docx_health.FIELDS[report]:
        val = (stored.get(key) or "").strip()
        if not val and key.startswith("sig_"):
            val = (hdr_defs.get("def_" + key[4:]) or "").strip()
        if kind == "date":
            rows.append((key, label, kind, stored.get(key, "")))
        else:
            rows.append((key, label, kind, val or default))
    return rows


def _tank_rows(year, month):
    """مصفوفة الخزانات للتعديل: صف لكل خزان × 8 خلايا (العدد ديناميكي)."""
    stored = db_health.get_fields(year, month, "tanks")
    out = []
    for t in range(1, docx_health.tank_count(year, month) + 1):
        row = []
        for key, label in docx_health.TANK_COLS:
            row.append((f"t{t}_{key}", label,
                        (stored.get(f"t{t}_{key}") or "").strip()
                        or docx_health.TANK_DEFAULT[key]))
        out.append(row)
    return out


def _checkup_state(year, month, day):
    """حالة تاب الكشف: القائمة الكاملة بحالة كل مجند (مكتوش؟ مقترح؟ حالته اليوم؟)."""
    checked = set(db_health.get_day_recruits(year, month, day))
    day_map = db_health.day_map_full(year, month, day)
    suggested = {rid for rid, st in day_map.items() if st == "حضور"}
    if not day_map:
        suggested = {r["id"] for r in db_recruits.list_recruits(year, month)}
    real = egtime.today().replace(day=1) == _date(year, month, 1)
    items = []
    for r in sorted(db_recruits.list_recruits(year, month), key=lambda x: x["name"]):
        items.append({"id": r["id"], "name": r["name"],
                      "status": day_map.get(r["id"], ""),
                      "checked": r["id"] in checked,
                      "suggested": r["id"] in suggested})
    return items, real


@health_bp.route("/")
@login_required
def page():
    # ملاحظة: /health (بدون سلاش) محجوزة كـendpoint مراقبة JSON في app.py —
    # صفحة القسم على /health/ وتُفتح من القائمة عبر /sections/health.
    year, month = _ctx()
    tab = request.args.get("tab", "spray")
    if tab not in TAB_KEYS:
        tab = "spray"
    health_fs.ensure_month(year, month)
    hdr_vals = docx_health.header_values(year, month)
    logo = lhdb.logo_path(year, month)
    v = {"tab": tab, "tabs": TABS, "year": year, "month": month,
         "month_name": MONTH_NAMES[month - 1],
         "tab_title": dict((k, n) for k, n, _i in TABS).get(tab, ""),
         "tab_icon": dict((k, i) for k, _n, i in TABS).get(tab, ""),
         "folder_path": docx_health.folder_hint(year, month),
         "header_fields": [(k, l, (db_health.get_fields(year, month, "header").get(k, "") or "").strip() or d)
                           for k, l, d in docx_health.HEADER_FIELDS],
         "logo_exists": bool(logo),
         "pv": {"logo": url_for("letterhead.logo_view") if logo else "", "h": hdr_vals},
         "ok": request.args.get("ok"), "err": request.args.get("err")}
    if tab == "checkups":
        days = db_health.get_days(year, month)
        day = int(request.args.get("day") or (days[0] if days else 1))
        if day not in days:
            day = days[0]
        items, _real = _checkup_state(year, month, day)
        v.update(days=days, day=day, items=items,
                 checked_count=len(db_health.get_day_recruits(year, month, day)),
                 field_rows=_field_rows(year, month, "checkup"))
        v["pv"].update(f=docx_health.field_values(year, month, "checkup", day),
                       is_checkup=True,
                       names=[it["name"] for it in items if it["checked"]])
    elif tab == "tanks":
        v.update(field_rows=_field_rows(year, month, "tanks"),
                 tank_rows=_tank_rows(year, month))
        stored_t = db_health.get_fields(year, month, "tanks")
        count_t = docx_health.tank_count(year, month)
        v["tank_count"] = count_t
        tank_cells = [[("t%d_%s" % (t, key),
                        (stored_t.get("t%d_%s" % (t, key)) or "").strip()
                        or docx_health.TANK_DEFAULT[key])
                       for key, _l in docx_health.TANK_COLS]
                      for t in range(1, count_t + 1)]
        v["pv"].update(f=docx_health.field_values(year, month, "tanks"),
                       tanks=True,
                       tank_labels=[l for _k, l in docx_health.TANK_COLS],
                       tank_cells=tank_cells)
    elif tab == "letter":
        v["pv"]["sample"] = True  # معاينة الدباجة: ترويسة + توقيعات افتراضية
    else:
        v.update(field_rows=_field_rows(year, month, tab))
        v["pv"].update(f=docx_health.field_values(year, month, tab))
    return render_template("health.html", **v)


# ======================================================================
# اللوجو الرسمي (نفس لوجو الدباجة — يظهر أعلى يسار الورق الصحي)
# ======================================================================
@health_bp.route("/logo", methods=["POST"])
@login_required
def logo_upload():
    year, month = _ctx()
    f = request.files.get("logo")
    if f and f.filename:
        try:
            name = save_logo(f.stream, storage.letterhead_dir(year, month))
        except ValueError as exc:
            return _rb("letter", err=str(exc))
        lhdb.save(year, month, {"logo_file": name})
        return _rb("letter", ok="تم حفظ اللوجو الرسمي ✓")
    return _rb("letter", err="اختر صورة اللوجو أولًا")


@health_bp.route("/logo/delete", methods=["POST"])
@login_required
def logo_delete():
    year, month = _ctx()
    lhdb.save(year, month, {"logo_file": ""})
    return _rb("letter", ok="تم حذف اللوجو ✓")


# ======================================================================
# حفظ النصوص القابلة للتعديل + إعادة توليد الملف فورًا
# ======================================================================
@health_bp.route("/save/<report>", methods=["POST"])
@login_required
def save_fields(report):
    year, month = _ctx()
    if report == "header":
        db_health.set_fields(year, month, "header",
                             {k: request.form.get(k, "").strip()
                              for k, _l, _d in docx_health.HEADER_FIELDS})
        return _rb(request.form.get("back", "spray"), ok="تم حفظ الترويسة ✓")
    if report not in docx_health.FIELDS:
        abort(404)
    day = 0
    if report == "checkup":
        days = db_health.get_days(year, month)
        try:
            day = int(request.form.get("day") or days[0])
        except (ValueError, IndexError):
            day = days[0]
        if day not in days:
            day = days[0]
    mapping = {}
    for key, _label, _kind, _default in docx_health.FIELDS[report]:
        mapping[key] = request.form.get(key, "").strip()
    db_health.set_fields(year, month, report, mapping)
    if report == "tanks":
        stored_pairs = {}
        for t in range(1, docx_health.TANK_COUNT + 1):
            for key, _label in docx_health.TANK_COLS:
                stored_pairs[f"t{t}_{key}"] = request.form.get(f"t{t}_{key}", "").strip()
        db_health.set_fields(year, month, "tanks", stored_pairs)
    docx_health.rebuild(year, month, report, day or None)
    return _rb(report, day, ok="تم الحفظ وتحديث ملف الوورد ✓")


@health_bp.route("/reset/<report>", methods=["POST"])
@login_required
def reset_fields(report):
    year, month = _ctx()
    if report not in docx_health.FIELDS:
        abort(404)
    db_health.reset_report(year, month, report)
    docx_health.rebuild(year, month, report)
    return _rb(report, ok="أُعيدت نصوص النموذج الرسمي الافتراضية ✓")


# ======================================================================
# الخزانات: إضافة / حذف (العدد ديناميكي ١-١٢ ويُحفظ مع بيانات الشهر)
# ======================================================================
@health_bp.route("/tanks/add", methods=["POST"])
@login_required
def tanks_add():
    year, month = _ctx()
    n = docx_health.set_tank_count(year, month,
                                   docx_health.tank_count(year, month) + 1)
    docx_health.rebuild(year, month, "tanks")
    return _rb("tanks", ok="أُضيف خزان — صار العدد {} خزانًا ✓".format(
        arnum.to_arabic_indic(n)))


@health_bp.route("/tanks/delete", methods=["POST"])
@login_required
def tanks_delete():
    year, month = _ctx()
    cur = docx_health.tank_count(year, month)
    if cur <= 1:
        return _rb("tanks", err="لازم يفضل خزان واحد على الأقل في الجدول")
    last = cur
    db_health.set_fields(year, month, "tanks",
                         {f"t{last}_{k}": "" for k, _l in docx_health.TANK_COLS})
    n = docx_health.set_tank_count(year, month, cur - 1)
    docx_health.rebuild(year, month, "tanks")
    return _rb("tanks", ok="اتحذف الخزان رقم {} — صار العدد {} خزانًا ✓".format(
        arnum.to_arabic_indic(last), arnum.to_arabic_indic(n)))


# ======================================================================
# أيام الكشف الثلاثة + اختيار المكتوشين
# ======================================================================
@health_bp.route("/days", methods=["POST"])
@login_required
def save_days():
    year, month = _ctx()
    old = db_health.get_days(year, month)
    vals = []
    for i in (1, 2, 3):
        try:
            vals.append(int(request.form.get(f"day{i}", "")))
        except ValueError:
            pass
    days = db_health.set_days(year, month, vals)
    for d in old:
        if d not in days:
            health_fs.remove_day_dir(year, month, d)
    for d in days:
        docx_health.rebuild(year, month, "checkup", d)
    return _rb("checkups", days[0], ok="تم تحديث أيام الكشف الثلاثة ✓")


@health_bp.route("/checkup/select", methods=["POST"])
@login_required
def select_checkup():
    year, month = _ctx()
    days = db_health.get_days(year, month)
    try:
        day = int(request.form.get("day", ""))
    except ValueError:
        day = days[0]
    if day not in days:
        day = days[0]
    ids = [int(x) for x in request.form.getlist("recruits")]
    known = {r["id"] for r in db_recruits.list_recruits(year, month)}
    db_health.set_day_recruits(year, month, day, [i for i in ids if i in known])
    docx_health.rebuild(year, month, "checkup", day)
    return _rb("checkups", day, ok="تم تحديد المكتوشين وتحديث الكشف ✓")


# ======================================================================
# تنزيل ملفات الوورد (تُعاد بناءها لحظة الطلب فتطابق آخر تعديل)
# ======================================================================
@health_bp.route("/docx/<report>")
@login_required
def docx_download(report):
    year, month = _ctx()
    day = request.args.get("day", type=int) or 0
    if report == "checkup":
        days = db_health.get_days(year, month)
        if day not in days:
            day = days[0]
        path = docx_health.rebuild(year, month, "checkup", day)
    elif report in docx_health.FIELDS:
        path = docx_health.rebuild(year, month, report)
    else:
        abort(404)
    return send_file(str(path), as_attachment=True)
