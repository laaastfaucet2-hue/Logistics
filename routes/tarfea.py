# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحة «الترفية» — دورة ثالثة (cycle='tarfea') على محرك المستودعات نفسه:

- تابا ١ مخازن و٣ مخازن **بنفس قوالب المستودعات الحقيقية بالظبط** (كروت أصناف
  بمعادلة التغليف، تعديل الإذن بنفس الفورم، كارت الصنف والتفاريد) — والتوجيه
  يذهب لمسارات المستودعات بـcycle=tarfea فيعزل البيانات تلقائيًا.
- تاب الأصناف: اسم + معيار، والحذف يمسح **دورة الصنف كاملة** (توجيه ٢٩/٠٩).
- تاب ٢ مخازن: صرف يدوي من الصنف (db_tarfea) بخصم من الكارت بلا رصيد سالب.
- تاب ٥ مخازن: السجل اليومي المشتق بالكميات المعيارية.
كل حفظ يحدّث مرايا Excel في 11-الترفية/ ذرّيًا.
"""
from flask import g
from flask import (Blueprint, abort, redirect, render_template, request,
                   url_for)

from core.auth_core import login_required, current_session, current_context
from core import arabic_numbers as arnum, egtime
from core.config import MONTH_NAMES, UNIT_BASE
from data_access import db_tarfea as dt
from data_access import db_warehouses as dw
from data_access import db_stores
from services import tarfea_fs as tf
from services import warehouses_fs as wf

tarfea_bp = Blueprint("tarfea", __name__, url_prefix="/tarfea")

TABS = [("items", "الأصناف", "📦"),
        ("wh1", "١ مخازن", "📥"),
        ("wh2", "٢ مخازن", "📤"),
        ("wh3", "٣ مخازن", "📒"),
        ("wh5", "٥ مخازن", "📋")]
SUB_KEYS = tuple(k for k, _n, _i in TABS)
CYCLE = "tarfea"
CYCLE_NAME = "سجل الترفية"


def _ctx():
    return current_context(g.user["id"])


def _rb(sub, **params):
    _, token = current_session()
    year, month = _ctx()
    return redirect(url_for("tarfea.page", sub=sub, year=year, month=month,
                            sid=token, **params))


def _default_day(year, month):
    today = egtime.today()
    return today.day if (today.year == year and today.month == month) else 1


def _wday(year, month, day):
    from datetime import date as _d
    try:
        return egtime.weekday_ar(_d(year, month, int(day)))
    except (ValueError, TypeError):
        return "—"


# ======================================================================
# الصفحة — بناء نفس سياق قوالب المستودعات لتابي ١ و٣ مخازن
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
    items = dt.list_items(year, month)
    receipts = dt.list_receipts(year, month)
    names = {it["id"]: it["name"] for it in items}
    for r in receipts:
        r["item_name"] = names.get(r["item_id"], "—")
        r["wday"] = _wday(year, month, r["day"])
        r["notes"] = dw.user_notes(r["notes"])
    groups = dw.receipt_groups(year, month, CYCLE)

    v = {"sub": sub, "tabs": TABS, "year": year, "month": month,
         "month_name": MONTH_NAMES[month - 1],
         "items": items, "receipts": receipts, "groups": groups,
         "cycle_key": CYCLE, "cycle_name": CYCLE_NAME,
         "days_in_month": egtime.days_in_month(year, month),
         "default_day": _default_day(year, month),
         "has_move": {it["id"]: dw.item_has_movement(year, month, CYCLE, it["id"])
                      for it in items},
         "folder_path": tf.folder_hint(year, month),
         "ok": request.args.get("ok"), "err": request.args.get("err")}

    if sub == "wh1":
        wh1_edit = None
        if request.args.get("wh1edit"):
            _ed = arnum.parse_int(request.args.get("wh1edit")) or 0
            wh1_edit = next((gr for gr in groups if gr["serial"] == _ed), None)
        v["wh1_edit"] = wh1_edit
        v["prefill"] = request.args.get("item_name") or ""
    elif sub == "wh2":
        v.update(issues=dt.list_issues(year, month),
                 next_serial=dt.next_issue_serial(year, month))
    elif sub == "wh3":
        card = None
        if request.args.get("item"):
            card = dw.item_card(year, month, arnum.parse_int(request.args.get("item")) or 0)
            if card and card["item"]["cycle"] != CYCLE:
                card = None
        if card:
            for row in card["rows"]:
                row["wday"] = _wday(year, month, row["day"])
            card["moved"] = dw.item_has_movement(year, month, CYCLE, card["item"]["id"])
            _specs = dw.pack_specs_map(year, month, CYCLE).get(card["item"]["name"], {})
            card["pack_note"] = ""
            if _specs and card["balance"] > 0:
                _pk = list(_specs)[-1]
                _sp = _specs[_pk]
                card["pack_note"] = dw.pack_breakdown(
                    _pk, _sp.get("capacity"), _sp.get("inner_count"),
                    _sp.get("inner_capacity"), card["balance"],
                    card["item"]["handle_unit"], inner_kind=_sp.get("inner_kind"))
            taf3 = wf.taf3_pack_rows(year, month, CYCLE, card["item"]["id"])
            if taf3:
                for row in taf3["rows"]:
                    row["wday"] = _wday(year, month, row["day"])
            v["taf3"] = taf3
        v["card"] = card
        v["stock"] = dt.stock_report(year, month)
        v["catalog_missing"] = []
    elif sub == "wh5":
        v.update(t5=dt.t5_rows(year, month))

    # سياق قوائم الكومبو وبيانات JS (نفس معرفات المستودعات)
    packs_map = dw.pack_specs_map(year, month, CYCLE)
    items_data = {}
    for it in items:
        base, factor = __import__("core.config", fromlist=["unit_base"]).unit_base(it["handle_unit"])
        items_data[it["name"]] = {"unit": it["handle_unit"], "base": base,
                                  "factor": factor, "id": it["id"],
                                  "packs": packs_map.get(it["name"], {})}
    v.update(units=__import__("data_access.db_rations", fromlist=["collect_units"])
             .collect_units(year, month),
             producers=sorted({r["producer"] for r in receipts if r["producer"]}),
             supplier_names=[],
             items_data=items_data, unit_base_data=UNIT_BASE,
             stores_registry=db_stores.list_stores(),
             pack_kinds=dw.collect_pack_kinds())
    return render_template("tarfea.html", **v)


# ======================================================================
# ملفات Excel المحلية: تنزيل (بتتعاد كتابتها لحظة الطلب)
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
# تاب الأصناف — الاسم + المعيار، والحذف يمسح الدورة كاملة
# ======================================================================
@tarfea_bp.route("/items/save", methods=["POST"])
@login_required
def items_save():
    name = " ".join((request.form.get("name") or "").split())
    unit = (request.form.get("handle_unit") or "").strip()
    item_id = arnum.parse_int(request.form.get("id"))
    try:
        if not name or not unit:
            raise ValueError("اسم الصنف ووحدة التعامل (المعيار) إلزاميان")
        if item_id:
            old_unit = (request.form.get("old_unit") or "").strip()
            if unit != old_unit:
                dt.update_item_unit(*_ctx(), item_id, unit)
            dt.rename_item(*_ctx(), item_id, name)
            ok = "عُدّل الصنف «{}» ✓".format(name)
        else:
            item, created = dt.add_item(*_ctx(), name, unit)
            ok = ("أُضيف الصنف «{}» بمعيار «{}» ✓ — وكارته اتفتح في ٣ مخازن".format(name, unit)
                  if created else "الصنف «{}» موجود بالفعل".format(name))
    except ValueError as exc:
        return _rb("items", err=str(exc))
    tf.snapshot(*_ctx())
    return _rb("items", ok=ok)


@tarfea_bp.route("/items/delete", methods=["POST"])
@login_required
def items_delete():
    item_id = arnum.parse_int(request.form.get("id"))
    try:
        name = dt.delete_item(*_ctx(), item_id)
    except ValueError as exc:
        return _rb("items", err=str(exc))
    tf.snapshot(*_ctx())
    return _rb("items", ok="اتمسح «{}» ودورته كاملة: الإيذانات والحركات والافتتاحي وإذون الصرف ✓".format(name))


# ======================================================================
# تاب ٢ مخازن — إذون صرف يدوية من الصنف (توجيه ٢٩/٠٩)
# ======================================================================
@tarfea_bp.route("/wh2/add", methods=["POST"])
@login_required
def wh2_add():
    try:
        serial = dt.add_issue(
            *_ctx(), day=arnum.parse_int(request.form.get("day"))
            or _default_day(*_ctx()),
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
