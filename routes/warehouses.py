# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""قسم «مستودعات وسجلات» — الدورة المخزنية لدورتين منفصلتين تمامًا.

تابان رئيسيان: سجل الإمداد وسجل المتعهد — ولكل منهما بنفس الترتيب:
الشركات الموردة / ١ مخازن (إذون إضافة الأصناف) / دفتر ٢ مخازن (إذون الحاسبة — عرض) /
دفتر ٣ مخازن (كارت صنف: مسلسل، يوم، تاريخ، رقم إذن، مضاف، منصرف، رصيد).
١ مخازن هو الإدخال اليدوي الوحيد؛ حفظ الإذن يفتح كارت الصنف في ٣ مخازن تلقائيًا.
"""
import logging
from datetime import date

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from core.auth_core import current_context, current_session, login_required
from core.config import (MONTH_NAMES, UNIT_BASE, WAREHOUSE_CYCLES, WAREHOUSE_MAP,
                         unit_base)
from data_access import db_stores
from core import arabic_numbers as arnum, dates, egtime
from data_access import months
from data_access import db_rations as dr
from data_access import db_warehouses as dw
from services import warehouses_fs as wf

warehouses_bp = Blueprint("warehouses", __name__, url_prefix="/warehouses")

TABS = [
    ("suppliers", "الشركات الموردة", "🏢"),
    ("wh1", "١ مخازن — إذون الإضافة", "📥"),
    ("wh2", "٢ مخازن — إذون الصرف", "📤"),
    ("wh3", "٣ مخازن — دفتر الأصناف", "📒"),
]
SUB_KEYS = {t[0] for t in TABS}


# ======================================================================
# أدوات مشتركة
# ======================================================================
def _ctx():
    year, month = current_context(g.user["id"])
    months.init_month(year, month)
    return year, month


def _snapshot(cycle):
    try:
        year, month = _ctx()
        wf.snapshot_cycle(year, month, cycle)
    except Exception:
        logging.exception("warehouses mirror failed (cycle=%s)", cycle)


def _rb(cycle="supply", sub="wh1", ok=None, err=None, warn=None, item=None, **extra):
    """يرجع لصفحة القسم مع الحفاظ على الدورة والتبويب وكارت الصنف والتوكن."""
    params = {"cycle": cycle, "sub": sub}
    if item:
        params["item"] = item
    if ok:
        params["ok"] = ok
    if err:
        params["err"] = err
    if warn:
        params["warn"] = warn
    params.update({k: str(v) for k, v in extra.items() if v not in (None, "")})
    _, token = current_session()
    if token:
        params["sid"] = token
    return redirect(url_for("warehouses.page", **params))


def _cycle():
    raw = request.args.get("cycle") or request.form.get("cycle") or "supply"
    return raw if raw in WAREHOUSE_MAP else "supply"


def _sub():
    raw = request.values.get("sub") or "wh1"
    return raw if raw in SUB_KEYS else "wh1"


def _day(year, month, raw, fallback):
    n = arnum.parse_int(raw)
    last = egtime.days_in_month(year, month)
    if n is None or n < 1 or n > last:
        return fallback
    return n


def _default_day(year, month):
    today = egtime.today()
    return today.day if today.year == year and today.month == month else 1


def _wday(year, month, day):
    """اسم اليوم بالعربية (السبت/الأحد…) لتاريخ داخل الشهر — قاعدة عمود «اليوم»."""
    try:
        return egtime.weekday_ar(date(int(year), int(month), int(day)))
    except (TypeError, ValueError):
        return ""


def _opt_date(raw):
    """تاريخ اختياري نصي dd/mm/yyyy → ISO، أو ('' ) فارغ؛ يرفع ValueError للتاريخ المستحيل."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    parsed = dates.parse_date(raw)
    return parsed.isoformat() if parsed else ""


def _open_path(path):
    """يفتح مسارًا محليًا بنظام التشغيل؛ False في معاينة الويب (قاعدة البرمجة المحلية)."""
    import os
    import subprocess
    import sys
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


# ======================================================================
# الصفحة الرئيسية للقسم
# ======================================================================
@warehouses_bp.route("")
@warehouses_bp.route("/")
@login_required
def page():
    year, month = _ctx()
    cycle, sub = _cycle(), _sub()
    try:
        wf.ensure_folders(year, month)
        wf.snapshot_all(year, month)      # الإذون قد تُحفظ من آلة الحاسبة — نبقي المرايا صادقة
    except Exception:
        logging.exception("warehouses snapshots on open failed")

    suppliers = dw.list_suppliers(year, month, cycle)
    items = dw.list_items(year, month, cycle)
    receipts = dw.list_receipts(year, month, cycle)
    names = {it["id"]: it["name"] for it in items}
    for r in receipts:
        r["item_name"] = names.get(r["item_id"], "—")
        r["wday"] = _wday(year, month, r["day"])

    item_name_set = {it["name"].lower() for it in items}
    catalog_missing = [c for c in dw.ration_catalog(year, month, cycle)
                       if c["name"].lower() not in item_name_set]

    permits = dw.permits_book(year, month, cycle) if sub == "wh2" else []
    tafreeda = dw.tafreeda_rows(year, month, cycle) if sub == "wh2" else []
    tafreeda_by_permit = {}
    for row in tafreeda:
        tafreeda_by_permit.setdefault(row["permit_no"], []).append(row)
    stores_registry = db_stores.list_stores()
    pack_kinds = dw.collect_pack_kinds()
    packs_map = dw.pack_specs_map(year, month, cycle)
    editing = None
    if sub == "suppliers" and request.args.get("edit"):
        editing = dw.get_supplier(year, month, arnum.parse_int(request.args.get("edit")) or 0,
                                  cycle)

    card = None
    if sub == "wh3" and request.args.get("item"):
        card = dw.item_card(year, month, arnum.parse_int(request.args.get("item")) or 0)
        if card and card["item"]["cycle"] != cycle:
            card = None
    if card:
        for row in card["rows"]:
            row["wday"] = _wday(year, month, row["day"])

    cycle_cfg = WAREHOUSE_MAP[cycle]
    tab_file = wf.TAB_XLSX[sub]
    counts = {"suppliers": len(suppliers), "wh1": len(receipts),
              "wh2": len(dw.permits_book(year, month, cycle)), "wh3": len(items)}
    items_data = {}
    for it in items:
        base, factor = unit_base(it["handle_unit"])
        items_data[it["name"]] = {"unit": it["handle_unit"], "base": base,
                                  "factor": factor, "id": it["id"],
                                  "packs": packs_map.get(it["name"], {})}
    for c in catalog_missing:
        items_data.setdefault(c["name"], {"unit": c["unit"], "base": "", "factor": None,
                                          "id": None, "packs": {}})
    return render_template(
        "warehouses/main.html",
        year=year, month=month, month_name=MONTH_NAMES[month - 1],
        days_in_month=egtime.days_in_month(year, month),
        default_day=_default_day(year, month),
        cycles=WAREHOUSE_CYCLES, cycle_key=cycle, cycle_name=cycle_cfg["name"],
        cycle_icon=cycle_cfg["icon"], cycle_section=cycle_cfg["section"],
        subs=TABS, sub=sub, sub_name=dict((t[0], t[1]) for t in TABS)[sub],
        tab_file=tab_file, tab_folder=wf.SUB_FOLDERS[sub],
        counts=counts,
        suppliers=suppliers, editing=editing,
        items=items, catalog_missing=catalog_missing,
        receipts=receipts, permits=permits, card=card,
        units=__import__("data_access.db_rations", fromlist=["collect_units"])
              .collect_units(year, month),
        producers=sorted({r["producer"] for r in receipts if r["producer"]}),
        supplier_names=[s["name"] for s in suppliers],
        prefill=request.args.get("item_name") or "",
        items_data=items_data, unit_base_data=UNIT_BASE,
        stores_registry=stores_registry, pack_kinds=pack_kinds,
        tafreeda_by_permit=tafreeda_by_permit,
    )


# ======================================================================
# الشركات الموردة
# ======================================================================
def _supplier_fields():
    return (request.form.get("name"), request.form.get("contact"),
            request.form.get("phone"), request.form.get("address"),
            request.form.get("activity"), request.form.get("notes"))


@warehouses_bp.route("/suppliers/add", methods=["POST"])
@login_required
def suppliers_add():
    year, month = _ctx()
    cycle = _cycle()
    name, contact, phone, address, activity, notes = _supplier_fields()
    if not (name or "").strip():
        return _rb(cycle, "suppliers", err="اكتب اسم الشركة الموردة أولًا")
    dw.add_supplier(year, month, cycle, name, contact, phone, address, activity, notes)
    _snapshot(cycle)
    return _rb(cycle, "suppliers",
               ok=f"حُفظت شركة «{name.strip()}» في سجل الشركات الموردة — وتسجيلها في البيانات المحلية")


@warehouses_bp.route("/suppliers/save", methods=["POST"])
@login_required
def suppliers_save():
    year, month = _ctx()
    cycle = _cycle()
    supplier_id = arnum.parse_int(request.form.get("supplier_id"))
    name, contact, phone, address, activity, notes = _supplier_fields()
    if not supplier_id or not dw.get_supplier(year, month, supplier_id, cycle):
        return _rb(cycle, "suppliers", err="الشركة المطلوب تعديلها غير موجودة في هذه الدورة")
    if not (name or "").strip():
        return _rb(cycle, "suppliers", err="اسم الشركة مطلوب", item=None)
    dw.update_supplier(year, month, supplier_id, name, contact, phone, address, activity, notes)
    _snapshot(cycle)
    return _rb(cycle, "suppliers",
               ok=f"عُدّلت بيانات شركة «{name.strip()}» — وتسجيلها في البيانات المحلية")


@warehouses_bp.route("/suppliers/delete", methods=["POST"])
@login_required
def suppliers_delete():
    year, month = _ctx()
    cycle = _cycle()
    supplier_id = arnum.parse_int(request.form.get("supplier_id"))
    supplier = dw.get_supplier(year, month, supplier_id or 0, cycle)
    if not supplier:
        return _rb(cycle, "suppliers", err="الشركة المطلوب حذفها غير موجودة في هذه الدورة")
    dw.delete_supplier(year, month, supplier_id)
    _snapshot(cycle)
    return _rb(cycle, "suppliers",
               ok=f"حُذفت شركة «{supplier['name']}» من سجل الموردين — وتسجيلها في البيانات المحلية")


# ======================================================================
# ١ مخازن — إذن إضافة صنف
# ======================================================================
@warehouses_bp.route("/wh1/add", methods=["POST"])
@login_required
def wh1_add():
    year, month = _ctx()
    cycle = _cycle()
    name = (request.form.get("item_name") or "").strip()
    qty = arnum.parse_float(request.form.get("qty"))
    if not name:
        return _rb(cycle, "wh1", err="اكتب اسم الصنف أولًا — من أصناف المقرر أو صنف جديد")
    if qty is None or qty <= 0:
        return _rb(cycle, "wh1", err="اكتب كمية الإضافة بالوحدة التعاملية للصنف")
    receipt_no = arnum.parse_int(request.form.get("receipt_no"))
    if receipt_no is not None and receipt_no < 1:
        receipt_no = None
    day = _day(year, month, request.form.get("day"), _default_day(year, month))
    try:
        prod_iso = _opt_date(request.form.get("prod_date"))
        exp_iso = _opt_date(request.form.get("exp_date"))
    except ValueError:
        return _rb(cycle, "wh1", err="تاريخ مستحيل — اكتب التاريخ يوم/شهر/سنة صحيحًا")
    if prod_iso and exp_iso and exp_iso < prod_iso:
        return _rb(cycle, "wh1", err="تاريخ الصلاحية قبل تاريخ الإنتاج")
    pack_kind = (request.form.get("pack_kind") or "").strip()
    pack_count = arnum.parse_float(request.form.get("pack_count")) or 0
    pack_capacity = arnum.parse_float(request.form.get("pack_capacity")) or 0
    pack_loose = arnum.parse_float(request.form.get("pack_loose")) or 0
    stores_parts = []
    for sid_raw, qty_raw in zip(request.form.getlist("store_id"),
                                request.form.getlist("store_qty")):
        sid = arnum.parse_int(sid_raw)
        sqty = arnum.parse_float(qty_raw)
        store = db_stores.get_store(sid) if sid else None
        if store and sqty and sqty > 0:
            stores_parts.append((store["id"], store["name"], sqty))
    supplier_id = None
    supplier_name = (request.form.get("supplier_name") or "").strip()
    for sup in dw.list_suppliers(year, month, cycle):
        if sup["name"] == supplier_name:
            supplier_id = sup["id"]
            break
    try:
        result = dw.add_receipt(
            year, month, cycle, day, name, qty,
            handle_unit_hint=request.form.get("handle_unit"),
            producer=request.form.get("producer"),
            supplier_id=supplier_id, supplier_name=supplier_name,
            prod_iso=prod_iso, exp_iso=exp_iso,
            notes=request.form.get("notes"),
            date_iso=f"{year:04d}-{month:02d}-{day:02d}",
            receipt_no=receipt_no,
            pack_kind=pack_kind, pack_count=pack_count,
            pack_capacity=pack_capacity, pack_loose=pack_loose,
            stores=stores_parts)
    except ValueError as exc:
        return _rb(cycle, "wh1", err=str(exc))
    _snapshot(cycle)
    conv = ""
    if result["factor"] and result["factor"] != 1:
        conv = (f" — {arnum.fmt_qty(result['qty_handle'])} {result['item']['handle_unit']}"
                f" = {arnum.fmt_qty(result['qty_base'])} {result['base_unit']}")
    ok = (f"حُفظ إذن إضافة ١ مخازن رقم {arnum.to_arabic_indic(result['serial'])}{conv}"
          f" وفتح كارت «{result['item']['name']}» في دفتر ٣ مخازن تلقائيًا"
          " — وتسجيلها في البيانات المحلية")
    return _rb(cycle, "wh3", item=result["item"]["id"], ok=ok)


# ======================================================================
# ٣ مخازن — رصيد أول المدة: إدخال حقيقي بكل بياناته (مرة واحدة لكل صنف)
# ======================================================================
@warehouses_bp.route("/wh3/opener", methods=["POST"])
@login_required
def wh3_opener():
    year, month = _ctx()
    cycle = _cycle()
    item_id = arnum.parse_int(request.form.get("item_id"))
    item = dw.get_item(year, month, item_id or 0, cycle) if item_id else None
    name_fallback = (request.form.get("item_name") or "").strip()
    if not item:
        # صنف لم يُفتح كارته بعد — «رصيد أول المدة» يفتح الكارت تلقائيًا
        if not name_fallback:
            return _rb(cycle, "wh3", err="اختر الصنف أولًا أو اكتب اسمه لتسجيل رصيد أول المدة")
        item = {"name": name_fallback}
    qty = arnum.parse_float(request.form.get("qty"))
    if qty is None or qty <= 0:
        return _rb(cycle, "wh3", err="اكتب كمية رصيد أول المدة", item=item_id)
    day = _day(year, month, request.form.get("day"), _default_day(year, month))
    pack_kind = (request.form.get("pack_kind") or "").strip()
    pack_count = arnum.parse_float(request.form.get("pack_count")) or 0
    pack_capacity = arnum.parse_float(request.form.get("pack_capacity")) or 0
    pack_loose = arnum.parse_float(request.form.get("pack_loose")) or 0
    supplier_id = None
    supplier_name = (request.form.get("supplier_name") or "").strip()
    for sup in dw.list_suppliers(year, month, cycle):
        if sup["name"] == supplier_name:
            supplier_id = sup["id"]
            break
    try:
        dw.add_opener(year, month, cycle, item["name"], qty, day,
                      producer=request.form.get("producer"),
                      supplier_id=supplier_id, supplier_name=supplier_name,
                      notes=request.form.get("notes"),
                      date_iso=f"{year:04d}-{month:02d}-{day:02d}",
                      pack_kind=pack_kind, pack_count=pack_count,
                      pack_capacity=pack_capacity, pack_loose=pack_loose)
    except ValueError as exc:
        return _rb(cycle, "wh3", err=str(exc), item=item_id)
    _snapshot(cycle)
    return _rb(cycle, "wh3", item=item_id,
               ok=(f"سُجّل رصيد أول المدة لصنف «{item['name']}» بكل بياناته"
                   " — وتسجيلها في البيانات المحلية"))


# ======================================================================
# ٣ مخازن — وحدة تعامل الصنف
# ======================================================================
@warehouses_bp.route("/wh3/unit", methods=["POST"])
@login_required
def wh3_unit():
    year, month = _ctx()
    cycle = _cycle()
    item_id = arnum.parse_int(request.form.get("item_id"))
    item = dw.get_item(year, month, item_id or 0, cycle)
    unit = (request.form.get("handle_unit") or "").strip()
    if not item:
        return _rb(cycle, "wh3", err="الصنف غير موجود في هذه الدورة")
    if not unit:
        return _rb(cycle, "wh3", err="اكتب وحدة التعامل", item=item_id)
    dw.set_handle_unit(year, month, item_id, unit)
    _snapshot(cycle)
    return _rb(cycle, "wh3", item=item_id,
               ok=(f"صارت وحدة تعامل «{item['name']}» هي «{unit}» — تُطبق على الحركات الجديدة"
                   " — وتسجيلها في البيانات المحلية"))


# ======================================================================
# ملفات التويبات المحلية: فتح المجلد / فتح الملف / التنزيل (قاعدة أزرار الملفات)
# ======================================================================
def _tab_or_404(cycle, sub):
    if cycle not in WAREHOUSE_MAP or sub not in SUB_KEYS:
        abort(404)


@warehouses_bp.route("/open-folder/<cycle>/<sub>")
@login_required
def open_folder(cycle, sub):
    _tab_or_404(cycle, sub)
    year, month = _ctx()
    path = wf.cycle_dir(year, month, cycle, sub)
    if _open_path(path):
        return _rb(cycle, sub, ok=f"تم فتح مجلد «{wf.SUB_FOLDERS[sub]}» 📂")
    return _rb(cycle, sub,
               err="فتح المجلد متاح عند تشغيل البرنامج على جهازك — استخدم زر التنزيل هنا")


@warehouses_bp.route("/open-file/<cycle>/<sub>")
@login_required
def open_file(cycle, sub):
    _tab_or_404(cycle, sub)
    year, month = _ctx()
    _snapshot(cycle)
    path = wf.file_path(year, month, cycle, sub)
    if path.exists() and _open_path(path):
        return _rb(cycle, sub, ok=f"تم فتح ملف «{wf.TAB_XLSX[sub]}» 📗")
    return redirect(url_for("warehouses.download", cycle=cycle, sub=sub))


@warehouses_bp.route("/download/<cycle>/<sub>")
@login_required
def download(cycle, sub):
    from core.downloads import attachment
    _tab_or_404(cycle, sub)
    year, month = _ctx()
    _snapshot(cycle)
    path = wf.file_path(year, month, cycle, sub)
    if not path.exists():
        return _rb(cycle, sub, err="الملف لم يُنشأ بعد — أضف بيانات أولًا")
    return attachment(path, f"warehouses-{cycle}-{sub}-{year}-{month:02d}.xlsx")
