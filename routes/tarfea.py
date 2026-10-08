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
from routes.warehouses import prepare_card

tarfea_bp = Blueprint("tarfea", __name__, url_prefix="/tarfea")

TABS = [("items", "الأصناف", "📦"),
        ("wh1", "١ مخازن", "📥"),
        ("wh2", "٢ مخازن", "📤"),
        ("wh3", "٣ مخازن", "📒"),
        ("wh5", "٥ مخازن", "📋"),
        ("store", "مخزن الترفية", "🏠")]
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

    # معدلات الأصناف تتبع المقررات التموينية (توجيه ٠٨/١٠/٢٠٢٦): لكل صنف ترفية
    # يطابق اسمًا في المقرر التموني النشط نعرض معدله حيًّا — يتجدد مع كل تغيير
    # في المقرر من غير أي كتابة يدوية هنا.
    rate_map = tf._tw_rate_map(year, month)
    for it in items:
        it["tw_rate"] = rate_map.get(" ".join(it["name"].split()))

    v = {"sub": sub, "tabs": TABS, "year": year, "month": month,
         "month_name": MONTH_NAMES[month - 1],
         "items": items, "rate_map": rate_map,
         "receipts": receipts, "groups": groups,
         "cycle_key": CYCLE, "cycle_name": CYCLE_NAME,
         "days_in_month": egtime.days_in_month(year, month),
         "default_day": _default_day(year, month),
         "has_move": {it["id"]: dw.item_has_movement(year, month, CYCLE, it["id"])
                      for it in items},
         "folder_path": tf.folder_hint(year, month),
         "sub_name": dict((k, n) for k, n, _i in TABS).get(sub, ""),
         "tab_file": tf.TAB_XLSX.get(sub, ""),
         "ok": request.args.get("ok"), "err": request.args.get("err")}

    if sub == "wh1":
        wh1_edit = None
        if request.args.get("wh1edit"):
            _ed = arnum.parse_int(request.args.get("wh1edit")) or 0
            wh1_edit = next((gr for gr in groups if gr["serial"] == _ed), None)
        v["wh1_edit"] = wh1_edit
        v["prefill"] = request.args.get("item_name") or ""
    elif sub == "wh2":
        issues = dt.list_issues(year, month)
        specs = dw.pack_specs_map(year, month, CYCLE)
        by_name = {it["name"]: it for it in items}

        def _spec_of(name):
            entry = specs.get(name) or {}
            if not entry:
                return "", {}
            kind = list(entry)[-1]
            return kind, (entry[kind] or {})

        def _issued_pack(i):
            it = by_name.get(i["item_name"])
            if not it:
                return "—"
            kind, sp = _spec_of(it["name"])
            fallback = "{} {}".format(arnum.fmt_qty(i["qty"]), it["handle_unit"])
            if not kind:
                return fallback
            return dw.pack_breakdown(kind, sp.get("capacity"),
                                     sp.get("inner_count"), sp.get("inner_capacity"),
                                     i["qty"], it["handle_unit"], "",
                                     inner_kind=sp.get("inner_kind")) or fallback
        v.update(issues=issues, next_serial=dt.next_issue_serial(year, month),
                 issues_pack=[{"i": i, "pack": _issued_pack(i),
                               "kind": (_spec_of(i["item_name"])[0] or "بدون تغليف")}
                              for i in issues])
    elif sub == "store":
        rep = dt.store_report(year, month)
        specs = dw.pack_specs_map(year, month, CYCLE)
        units = {it["name"]: it["handle_unit"] for it in items}
        per_item = {}
        for row in rep["inn"]:
            per_item.setdefault(row["item"], {"inn": [], "out": []})["inn"].append(row)
        for row in rep["out"]:
            per_item.setdefault(row["item"], {"inn": [], "out": []})["out"].append(row)
        for name, g in per_item.items():
            entry = specs.get(name) or {}
            g["kind"] = (list(entry)[-1] if entry else "بدون تغليف")
        balance_rows = [(name, qty, rep["pack_notes"].get(name) or "—",
                         units.get(name, "—"))
                        for name, qty in sorted(rep["balances"].items())]
        v.update(store=rep, store_per_item=per_item,
                 store_balances=balance_rows)
    elif sub == "wh3":
        # دفتر ٣ مخازن الترفيهي = دفتر ٣ مخازن المستودعات بالظبط (توجيه ٠٨/١٠):
        # نفس السياق — كارت + تفاريد المقسم + فورم رصيد أول المدة (جديد/تعديل).
        packs_map_wh3 = dw.pack_specs_map(year, month, CYCLE)
        card = None
        if request.args.get("item"):
            card = dw.item_card(year, month, arnum.parse_int(request.args.get("item")) or 0)
            if card and card["item"]["cycle"] != CYCLE:
                card = None
        opener_edit = prepare_card(card, year, month, CYCLE, packs_map_wh3)
        taf3_all = wf.taf3_all(year, month, CYCLE, items)
        taf3_active_id = (card["item"]["id"] if card else
                          (items[0]["id"] if items else None))
        v.update(card=card, opener_edit=opener_edit, taf3_all=taf3_all,
                 taf3_active_id=taf3_active_id,
                 stock=dt.stock_report(year, month),
                 catalog_missing=[])
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
    from data_access import db_tameedat as dtm
    v.update(units=__import__("data_access.db_rations", fromlist=["collect_units"])
             .collect_units(year, month),
             producers=sorted({r["producer"] for r in receipts if r["producer"]}),
             supplier_names=[],
             items_data=items_data, unit_base_data=UNIT_BASE,
             stores_registry=db_stores.list_stores(),
             pack_kinds=dw.collect_pack_kinds(),
             entity_names=dtm.entity_names(year, month))
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
# فتح مجلد/ملف التاب محليًا (نفس سلوك المستودعات — على مجلدات الترفية فقط)
# ======================================================================
@tarfea_bp.route("/open-folder/<sub>")
@login_required
def open_folder(sub):
    from routes.warehouses import _open_path
    year, month = _ctx()
    if sub not in SUB_KEYS:
        abort(404)
    if _open_path(tf.sub_dir(year, month, sub)):
        return _rb(sub, ok="تم فتح مجلد «{}» 📂".format(tf.SUB_FOLDERS[sub]))
    return _rb(sub, err="فتح المجلد متاح عند تشغيل البرنامج على جهازك — استخدم زر التنزيل هنا")


@tarfea_bp.route("/open-file/<sub>")
@login_required
def open_file(sub):
    from routes.warehouses import _open_path
    year, month = _ctx()
    if sub not in SUB_KEYS:
        abort(404)
    tf.snapshot(year, month)
    if tf.file_path(year, month, sub).exists() and _open_path(tf.file_path(year, month, sub)):
        return _rb(sub, ok="تم فتح ملف «{}» 📗".format(tf.TAB_XLSX[sub]))
    return redirect(url_for("tarfea.file", sub=sub))


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
    from data_access import db_tameedat as dtm
    try:
        year, month = _ctx()
        serial = dt.add_issue(
            year, month, day=arnum.parse_int(request.form.get("day"))
            or _default_day(year, month),
            item_id=arnum.parse_int(request.form.get("item_id")) or 0,
            qty=arnum.parse_float(request.form.get("qty")) or 0,
            # اسم الجهة يتبع قاموس جهات البرنامج (توجيه ٠٨/١٠)
            receiver=dtm.normalize_entity_name(year, month,
                                               request.form.get("receiver")),
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
