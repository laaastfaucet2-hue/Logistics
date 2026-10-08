# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""«تفاريد خط الحدود الدولى» — النقط الحدودية.

أربع أقسام:
- أوراق وإيصالات الصرف: البوابة + الحفظ اليدوي + الارشيف + البحث
- إجمالي خطوط التوزيع: مصفوفة + اختيار خط + اختيار التوزيعة (الحالية/ارشيف)
- إدارة الخطوط والنقاط: CRUD + بيان إكسل مع كل تغيير (ارشيف)
- تعديل معدلات الأصناف: معدلات الدولى (منفصلة) + بيان مع كل تغيير (ارشيف)

الحفظ على القرص = أربع فولدرات محلية جوا بيانات الشهر (services/dowail_fs.py).
"""
from flask import (Blueprint, redirect, render_template, request,
                   send_file, url_for)
from core import arabic_numbers as arnum
from core.auth_core import current_session, login_required
from core.config import DAYS, MEALS, MONTH_NAMES
from data_access import db_dowail as dw
from data_access import db_rations as dr
from data_access import months
from documents import xlsx_rations
from services import dowail_build as db
from services import dowail_fs
from services import free_build as fb
from routes.calc2 import _ctx, _day

dowail_bp = Blueprint("dowail", __name__, url_prefix="/calc2/dowail")

TABS = ("papers", "totals", "lines", "rates")


def _range(year, month):
    from core import egtime
    last = egtime.days_in_month(year, month)
    f = _day(year, month, request.args.get("from") or request.form.get("date_from"), 1)
    t = _day(year, month, request.args.get("to") or request.form.get("date_to"), last)
    if t < f:
        t = f
    days = arnum.parse_int(request.args.get("days") or request.form.get("issue_days")) \
        or (t - f + 1)
    days = max(1, min(days, t - f + 1))
    return last, f, t, days


def _tab():
    return request.args.get("tab") if request.args.get("tab") in TABS else "papers"


def _base(year, month, last, f, t, days, tab):
    _, token = current_session()
    return {
        "year": year, "month": month, "month_name": MONTH_NAMES[month - 1],
        "days_in_month": last, "day_from": f, "day_to": t, "issue_days": days,
        "tab": tab, "sid": token or "", "cur_tab": "dowail",
    }


def _rates_view(year, month):
    """أصناف الدولى: المقررات (تموين/متعهد) + الإضافات — بالمعدلات والمفعّل."""
    saved = {(r["section"], r["name"]): r for r in dw.list_rates(year, month)}
    out = {}
    for section in ("tamween", "contractor"):
        kind = dr.get_activation(year, month, section) or "summer"
        rows, custom = dr.get_items(year, month, section, kind)
        items = []
        for i, item in enumerate(rows):
            name = " ".join((item.get("name") or "").split())
            if not name:
                continue
            item = dict(item)
            item["custom"] = custom.get(item.get("id"), [])
            item["is_custom"] = bool(item["custom"])
            s = saved.get((section, name))
            items.append({
                "serial": i + 1, "name": name, "unit": item.get("unit") or "",
                "base": fb.seed_rate(item),
                "custom": fb.custom_chips(item),
                "rate": float(s["rate"]) if s else 0.0,
                "enabled": int(s["enabled"]) if s else 0,
                "rate_id": s["id"] if s else None,
                "is_extra": bool(s and s.get("is_extra")),
                "item_id": item.get("id"),
                "custom_entries": custom.get(item.get("id"), []),
            })
        for s in dw.list_rates(year, month):
            if s["section"] == section and s.get("is_extra") \
                    and s["name"] not in {it["name"] for it in items}:
                items.append({
                    "serial": len(items) + 1, "name": s["name"],
                    "unit": s.get("unit") or "", "base": 0.0, "custom": [],
                    "rate": float(s["rate"]), "enabled": int(s["enabled"]),
                    "rate_id": s["id"], "is_extra": True, "item_id": None})
        out[section] = items
    return out


# ======================================================================
# الصفحة الرئيسية (4 تابات)
# ======================================================================
@dowail_bp.route("")
@dowail_bp.route("/")
@login_required
def page():
    year, month = _ctx()
    months.init_month(year, month)
    last, f, t, days = _range(year, month)
    tab = _tab()
    ctx = _base(year, month, last, f, t, days, tab)
    if tab == "papers":
        ctx["saves"] = dw.list_saves(year, month)
        line_id = arnum.parse_int(request.args.get("line"))
        ctx["lines"] = dw.list_lines(year, month)
        ctx["sel_line_id"] = line_id
        ctx["current_papers"] = [
            lp for lp in db.line_papers(year, month, f, t, days)
            if line_id is None or lp["line"]["id"] == line_id]
        dist_id = arnum.parse_int(request.args.get("dist"))
        ctx["dist_save"] = dw.get_save(year, month, dist_id) if dist_id else None
        found = db.search_point(year, month, request.args.get("q"))
        ctx["search_q"] = request.args.get("q") or ""
        ctx["search_hit"] = (
            {"line": found[0], "point": found[1],
             "rows": list(enumerate(
                 [db.item_row(r, found[1]["force"],
                              db.issue_dates(year, month, f, t, days))
                  for r in db.active_rates(year, month)]))}
            if found else None)
    elif tab == "totals":
        line_id = arnum.parse_int(request.args.get("line"))
        ctx["lines"] = dw.list_lines(year, month)
        ctx["sel_line_id"] = line_id
        ctx["saves"] = dw.list_saves(year, month)
        archive = dw.get_save(year, month, arnum.parse_int(request.args.get("dist"))) \
            if request.args.get("dist") else None
        if archive and archive.get("data"):
            ctx["matrix"] = archive["data"].get("matrix") or \
                db.totals_matrix(year, month, f, t, days)
            ctx["archive_save"] = archive
        else:
            ctx["matrix"] = db.totals_matrix(year, month, f, t, days, line_id)
            ctx["archive_save"] = None
    elif tab == "lines":
        ctx["lines"] = dw.list_lines(year, month)
        ctx["sel_line_id"] = arnum.parse_int(request.args.get("line"))
        ctx["line_statements"] = dowail_fs.list_line_statements(year, month)
    elif tab == "rates":
        ctx["rates_view"] = _rates_view(year, month)
        ctx["rate_statements"] = dowail_fs.list_rates_statements(year, month)
        ctx["days"], ctx["meals"] = DAYS, MEALS
    return render_template(f"dowail/tab_{tab}.html", **ctx)


# ======================================================================
# إدارة الخطوط والنقاط (بيان إكسل مع كل تغيير)
# ======================================================================
def _statement_after(year, month, line_id):
    line = dw.get_line(year, month, line_id)
    if line:
        dowail_fs.write_line_statement(year, month, line)


@dowail_bp.route("/lines", methods=["POST"])
@login_required
def add_line():
    year, month = _ctx()
    new_id = dw.add_line(year, month, request.form.get("name"))
    if new_id:
        _statement_after(year, month, new_id)
    return _back("lines")


@dowail_bp.route("/lines/<int:line_id>/delete", methods=["POST"])
@login_required
def delete_line(line_id):
    year, month = _ctx()
    dw.delete_line(year, month, line_id)
    return _back("lines")


@dowail_bp.route("/points", methods=["POST"])
@login_required
def add_point():
    year, month = _ctx()
    line_id = arnum.parse_int(request.form.get("line_id")) or 0
    if dw.add_point(year, month, line_id, request.form.get("name"),
                    request.form.get("force")):
        _statement_after(year, month, line_id)
    return _back(request.form.get("from_tab") or "lines")


@dowail_bp.route("/points/<int:point_id>/update", methods=["POST"])
@login_required
def update_point(point_id):
    year, month = _ctx()
    line, _p = dw.find_point(year, month, point_id)
    force = arnum.parse_int(request.form.get("force"))
    responsible = request.form.get("responsible")
    if request.form.get("responsible_only"):
        dw.update_point(year, month, point_id, responsible=responsible)
    else:
        dw.update_point(year, month, point_id, force=force)
    if line:
        _statement_after(year, month, line["id"])
    return _back(request.form.get("from_tab") or "lines")


@dowail_bp.route("/points/<int:point_id>/delete", methods=["POST"])
@login_required
def delete_point(point_id):
    year, month = _ctx()
    line, _p = dw.find_point(year, month, point_id)
    dw.delete_point(year, month, point_id)
    if line:
        _statement_after(year, month, line["id"])
    return _back("lines")


# ======================================================================
# معدلات الدولى (بيان إكسل مع كل تغيير)
# ======================================================================
def _rates_statement(year, month):
    dowail_fs.write_rates_statement(year, month, db.rates_with_custom(year, month))


# ======================================================================
# مخصص الأيام (يُعدّل من تاب المعدلات — نفس مقررات ٢ مخازن المشتركة)
# ======================================================================
@dowail_bp.route("/custom/<int:item_id>", methods=["POST"])
@login_required
def custom_save(item_id):
    year, month = _ctx()
    item = dr.get_item(year, month, item_id)
    if not item:
        return redirect(url_for("dowail.page", tab="rates",
                                err="الصنف غير موجود — عدّل المخصص من صفّه في الجدول"))
    entries = []
    for d in range(7):
        for meal, _label in MEALS:
            qty = arnum.parse_float(request.form.get(f"c_{d}_{meal}", ""))
            if qty is not None and qty > 0:   # الفاضي/صفر = لا يُضاف ذلك اليوم
                entries.append((d, meal, qty))
    dr.save_custom(year, month, item_id, entries)
    xlsx_rations.rebuild(year, month, item["section"])
    _rates_statement(year, month)
    if entries:
        ok = f"تخصص «{item['name']}» اتحفظ ({arnum.to_arabic_indic(len(entries))} خانة) — بيُضاف فوق المعدل في حصائل التوزيعات"
    else:
        ok = f"«{item['name']}» خلاص من غير مخصص — الحصيلة = المعدل × القوة × الأيام بس"
    return redirect(url_for("dowail.page", tab="rates", ok=ok))


@dowail_bp.route("/rates/add", methods=["POST"])
@login_required
def rates_add():
    year, month = _ctx()
    section = request.form.get("section") if request.form.get("section") \
        in ("tamween", "contractor") else "tamween"
    name = " ".join((request.form.get("name") or "").split())
    if name:
        dw.save_rate(year, month, section, name,
                     arnum.parse_float(request.form.get("rate")) or 0,
                     request.form.get("unit") or "", is_extra=True)
        _rates_statement(year, month)
    return _back("rates")


@dowail_bp.route("/rates/<int:rate_id>/update", methods=["POST"])
@login_required
def rates_update(rate_id):
    year, month = _ctx()
    row = next((r for r in dw.list_rates(year, month) if r["id"] == rate_id), None)
    if row:
        dw.save_rate(year, month, row["section"], row["name"],
                     arnum.parse_float(request.form.get("rate")) or 0,
                     request.form.get("unit") or row.get("unit") or "",
                     is_extra=bool(row.get("is_extra")))
        _rates_statement(year, month)
    return _back("rates")


@dowail_bp.route("/rates/<int:rate_id>/toggle", methods=["POST"])
@login_required
def rates_toggle(rate_id):
    year, month = _ctx()
    dw.toggle_rate(year, month, rate_id)
    _rates_statement(year, month)
    return _back("rates")


@dowail_bp.route("/rates/<int:rate_id>/delete", methods=["POST"])
@login_required
def rates_delete(rate_id):
    year, month = _ctx()
    dw.delete_rate(year, month, rate_id)
    _rates_statement(year, month)
    return _back("rates")


# ======================================================================
# حفظ على القرص (يدوي) + الارشيف + الملفات
# ======================================================================
@dowail_bp.route("/save", methods=["POST"])
@login_required
def save_tafreeda():
    year, month = _ctx()
    last, f, t, days = _range(year, month)
    data = db.snapshot(year, month, f, t, days, request.form.get("store_keeper"))
    n_same = dw.count_saves_from(year, month, f) + 1
    rel = dowail_fs.save_to_disk(year, month, data, n_same)
    dw.save_tafreeda(year, month, data, rel)
    return redirect(url_for("dowail.page", tab="papers", ok="اتحفظت التوزيعة على القرص"))


@dowail_bp.route("/saves/<int:save_id>/delete", methods=["POST"])
@login_required
def save_delete(save_id):
    year, month = _ctx()
    save = dw.get_save(year, month, save_id)
    if save:
        dowail_fs.delete_files(year, month, save.get("files") or [])
        dw.delete_save(year, month, save_id)
    return _back("papers")


@dowail_bp.route("/file/<int:save_id>/<path:filename>")
@login_required
def save_file(save_id, filename):
    year, month = _ctx()
    save = dw.get_save(year, month, save_id)
    if not save:
        return "الملف مش موجود", 404
    base = months.month_db_path(year, month).parent.resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        return "الملف مش موجود", 404
    return send_file(str(target), as_attachment=True, download_name=target.name)


@dowail_bp.route("/statement/<path:filename>")
@login_required
def statement_file(filename):
    """ملفات البيان (ارشيف الخطوط والمعدلات) — جوا فولدر القسم بس."""
    year, month = _ctx()
    section = dowail_fs.section_dir(year, month).resolve()
    target = (section / filename).resolve()
    if not str(target).startswith(str(section)) or not target.is_file():
        return "الملف مش موجود", 404
    return send_file(str(target), as_attachment=True, download_name=target.name)


def _back(tab):
    return redirect(url_for("dowail.page", tab=tab))
