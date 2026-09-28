# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحة «الترفية» — دورة مستقلة على محرك المخازن (cycle='tarfea') بخمسة تابات:

📦 الأصناف (اسم + معيار) · 📥 ١ مخازن (إذون إضافة بالتغليف) · 📤 ٢ مخازن (صرف
يدوي من الصنف) · 📒 ٣ مخازن (رصيد أول المدة + كارت صنف + جرد + تفريد) ·
📋 ٥ مخازن (السجل اليومي المشتق: التاريخ/رقم الإذن/وارد من-منصرف إلى/قيمة
مضافة-منصرفة بالمعيار/البيان/المسؤول عن الصرف/إجراءات — توجيه ٢٩/٠٩).
كل حفظ يحدّث مرايا Excel في 11-الترفية/ ذرّيًا.
"""
from flask import g
from flask import (Blueprint, abort, redirect, render_template, request,
                   url_for)

from core.auth_core import login_required, current_session, current_context
from core import arabic_numbers as arnum, egtime
from core.config import MONTH_NAMES
from data_access import db_tarfea as dt
from data_access import db_warehouses as dw
from services import tarfea_fs as tf

tarfea_bp = Blueprint("tarfea", __name__, url_prefix="/tarfea")

TABS = [("items", "الأصناف", "📦"),
        ("wh1", "١ مخازن", "📥"),
        ("wh2", "٢ مخازن", "📤"),
        ("wh3", "٣ مخازن", "📒"),
        ("wh5", "٥ مخازن", "📋")]
SUB_KEYS = tuple(k for k, _n, _i in TABS)


def _ctx():
    return current_context(g.user["id"])


def _rb(sub, **params):
    _, token = current_session()
    year, month = _ctx()
    return redirect(url_for("tarfea.page", sub=sub, year=year, month=month,
                            sid=token, **params))


def _day(raw, fallback=None):
    """يوم صالح داخل الشهر النشط — الافتراضي: اليوم الحقيقي لو نفس الشهر وإلا ١."""
    year, month = _ctx()
    day = arnum.parse_int(raw)
    if day and 1 <= day <= egtime.days_in_month(year, month):
        return day
    if fallback:
        return min(fallback, egtime.days_in_month(year, month))
    today = egtime.today()
    return today.day if (today.year == year and today.month == month) else 1


# ======================================================================
# الصفحة
# ======================================================================
@tarfea_bp.route("")
@tarfea_bp.route("/")
@login_required
def page():
    year, month = _ctx()
    sub = request.args.get("sub", "items")
    if sub not in SUB_KEYS:
        sub = "items"
    tf.ensure_folders(year, month)
    v = {"sub": sub, "tabs": TABS, "year": year, "month": month,
         "month_name": MONTH_NAMES[month - 1],
         "items": dt.list_items(year, month),
         "has_move": {it["id"]: dw.item_has_movement(year, month, dt.CYCLE, it["id"])
                      for it in dt.list_items(year, month)},
         "folder_path": tf.folder_hint(year, month),
         "ok": request.args.get("ok"), "err": request.args.get("err")}
    if sub == "wh1":
        v.update(groups=dt.receipt_groups(year, month),
                 edit_serial=arnum.parse_int(request.args.get("edit")),
                 edit_group=None)
        if v["edit_serial"]:
            for grp in v["groups"]:
                if grp["serial"] == v["edit_serial"]:
                    v["edit_group"] = grp
                    break
    elif sub == "wh2":
        v.update(issues=dt.list_issues(year, month),
                 next_serial=dt.next_issue_serial(year, month))
    elif sub == "wh3":
        sel = arnum.parse_int(request.args.get("item"))
        v.update(sel_item=dt.item_card(year, month, sel) if sel else None,
                 stock=dt.stock_report(year, month),
                 tafreeda=dt.tafreeda_rows(year, month))
    elif sub == "wh5":
        v.update(t5=dt.t5_rows(year, month))
    return render_template("tarfea.html", **v)


# ======================================================================
# ملفات Excel المحلية: تنزيل (الفتح المباشر على ويندوز فقط زي باقي النظام)
# ======================================================================
@tarfea_bp.route("/file/<sub>")
@login_required
def file(sub):
    from flask import send_file
    year, month = _ctx()
    if sub not in SUB_KEYS:
        abort(404)
    tf.snapshot(year, month)
    return send_file(str(tf.file_path(year, month, sub)), as_attachment=True)


# ======================================================================
# تاب الأصناف
# ======================================================================
@tarfea_bp.route("/items/save", methods=["POST"])
@login_required
def items_save():
    name = " ".join((request.form.get("name") or "").split())
    unit = (request.form.get("handle_unit") or "").strip()
    item_id = arnum.parse_int(request.form.get("id"))
    try:
        if not name or not unit:
            raise ValueError("اسم الصنف ووحدة التعامل إلزاميان")
        if item_id:
            old_unit = (request.form.get("old_unit") or "").strip()
            if unit != old_unit:
                dt.update_item_unit(*_ctx(), item_id, unit)
            dt.rename_item(*_ctx(), item_id, name)
            ok = "عُدّل الصنف «{}» ✓".format(name)
        else:
            item, created = dt.add_item(*_ctx(), name, unit)
            ok = ("أُضيف الصنف «{}» بمعيار «{}» ✓".format(name, unit)
                  if created else "الصنف «{}» موجود بالفعل بنفس المعيار".format(name))
    except ValueError as exc:
        return _rb("items", err=str(exc))
    tf.snapshot(*_ctx())
    return _rb("items", ok=ok)


@tarfea_bp.route("/items/delete", methods=["POST"])
@login_required
def items_delete():
    item_id = arnum.parse_int(request.form.get("id"))
    try:
        dt.delete_item(*_ctx(), item_id)
    except ValueError as exc:
        return _rb("items", err=str(exc))
    tf.snapshot(*_ctx())
    return _rb("items", ok="اتحذف الصنف من كتالوج الترفية ✓")


# ======================================================================
# تاب ١ مخازن — إذون إضافة (بالتغليف زي المخازن بالظبط)
# ======================================================================
def _receipt_form():
    form = {"day": _day(request.form.get("day")),
            "producer": (request.form.get("producer") or "").strip(),
            "supplier_name": (request.form.get("supplier_name") or "").strip(),
            "notes": (request.form.get("notes") or "").strip(),
            "receipt_no": arnum.parse_int(request.form.get("receipt_no"))}
    lines = []
    for i in range(20):
        if "l{}_item_name".format(i) not in request.form:
            break
        name = (request.form.get("l{}_item_name".format(i)) or "").strip()
        if not name:
            continue
        def _f(key, default=0.0, _i=i):
            return arnum.parse_float(request.form.get("l{}_{}".format(_i, key))) or default
        lines.append(dict(
            item_name=name,
            qty=arnum.parse_float(request.form.get("l{}_qty".format(i))),
            handle_unit_hint=(request.form.get("l{}_handle_unit".format(i)) or "").strip(),
            pack_kind=(request.form.get("l{}_pack_kind".format(i)) or "").strip(),
            pack_count=_f("pack_count"), pack_capacity=_f("pack_capacity"),
            pack_loose=_f("pack_loose"),
            pack_inner_kind=(request.form.get("l{}_pack_inner_kind".format(i)) or "").strip(),
            pack_inner_count=_f("pack_inner_count"),
            pack_inner_capacity=_f("pack_inner_capacity"),
            pack_loose_unit=(request.form.get("l{}_pack_loose_unit".format(i)) or "").strip(),
            prod_iso=_opt_date(request.form.get("l{}_prod_date".format(i))),
            exp_iso=_opt_date(request.form.get("l{}_exp_date".format(i)))))
    return form, lines


def _opt_date(raw):
    from core import dates
    return dates.to_iso((raw or "").strip()) or ""


@tarfea_bp.route("/wh1/add", methods=["POST"])
@login_required
def wh1_add():
    try:
        form, lines = _receipt_form()
        if not lines:
            raise ValueError("ضيف صنفًا واحدًا على الأقل في الإذن")
        saved = []
        for order, ln in enumerate(lines):
            saved.append(dt.add_receipt(
                *_ctx(), day=form["day"], item_name=ln["item_name"],
                qty_handle=ln["qty"], handle_unit_hint=ln["handle_unit_hint"],
                producer=form["producer"], supplier_name=form["supplier_name"],
                notes=form["notes"], receipt_no=form["receipt_no"],
                allow_same_serial=order > 0, pack_kind=ln["pack_kind"],
                pack_count=ln["pack_count"], pack_capacity=ln["pack_capacity"],
                pack_loose=ln["pack_loose"], pack_inner_kind=ln["pack_inner_kind"],
                pack_inner_count=ln["pack_inner_count"],
                pack_inner_capacity=ln["pack_inner_capacity"],
                pack_loose_unit=ln["pack_loose_unit"],
                prod_iso=ln["prod_iso"], exp_iso=ln["exp_iso"]))
        first = saved[0]
        ok = "حُفظ إذن إضافة ترفية رقم {} — {} أصناف ✓".format(
            arnum.to_arabic_indic(first["serial"]), arnum.to_arabic_indic(len(saved)))
    except ValueError as exc:
        return _rb("wh1", err=str(exc))
    tf.snapshot(*_ctx())
    return _rb("wh1", ok=ok)


@tarfea_bp.route("/wh1/delete/<int:serial>", methods=["POST"])
@login_required
def wh1_delete(serial):
    try:
        dt.delete_receipt(*_ctx(), serial)
    except (ValueError, KeyError) as exc:
        return _rb("wh1", err=str(exc) or "الإذن غير موجود")
    tf.snapshot(*_ctx())
    return _rb("wh1", ok="اتحذف إذن إضافة رقم {} وأُعيد احتساب الأرصدة ✓".format(
        arnum.to_arabic_indic(serial)))


# ======================================================================
# تاب ٢ مخازن — إذون صرف يدوية من الصنف
# ======================================================================
@tarfea_bp.route("/wh2/add", methods=["POST"])
@login_required
def wh2_add():
    try:
        serial = dt.add_issue(
            *_ctx(), day=_day(request.form.get("day")),
            item_id=arnum.parse_int(request.form.get("item_id")) or 0,
            qty=arnum.parse_float(request.form.get("qty")) or 0,
            receiver=request.form.get("receiver"),
            responsible=request.form.get("responsible"),
            notes=request.form.get("notes"),
            serial=arnum.parse_int(request.form.get("serial")))
    except ValueError as exc:
        return _rb("wh2", err=str(exc))
    tf.snapshot(*_ctx())
    return _rb("wh2", ok="حُفظ إذن صرف ٢ مخازن ترفية رقم {} ✓".format(
        arnum.to_arabic_indic(serial)))


@tarfea_bp.route("/wh2/delete/<int:issue_id>", methods=["POST"])
@login_required
def wh2_delete(issue_id):
    try:
        row = dt.delete_issue(*_ctx(), issue_id)
    except ValueError as exc:
        return _rb("wh2", err=str(exc))
    tf.snapshot(*_ctx())
    return _rb("wh2", ok="اتحذف إذن صرف رقم {} وأُعيد الرصيد ✓".format(
        arnum.to_arabic_indic(row["serial"])))


# ======================================================================
# تاب ٣ مخازن — رصيد أول المدة + الكارت + الجرد
# ======================================================================
@tarfea_bp.route("/wh3/opener", methods=["POST"])
@login_required
def wh3_opener():
    try:
        item_name = (request.form.get("item_name") or "").strip()
        qty = arnum.parse_float(request.form.get("qty")) or 0
        if not item_name or qty <= 0:
            raise ValueError("اختر الصنف واكتب كمية رصيد أول المدة")
        unit = (request.form.get("handle_unit") or "").strip()
        if not unit:
            known = {it["name"]: it for it in dt.list_items(*_ctx())}
            unit = known.get(item_name, {}).get("handle_unit", "")
        dt.add_opener(*_ctx(), item_name=item_name, qty=qty,
                      day=_day(request.form.get("day"), 1), handle_unit_hint=unit)
    except ValueError as exc:
        return _rb("wh3", err=str(exc))
    tf.snapshot(*_ctx())
    return _rb("wh3", ok="تسجل رصيد أول المدة ✓ — الكارت اتفتح في ٣ مخازن")
