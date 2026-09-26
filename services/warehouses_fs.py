# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الملف المحلي للدورة المخزنية «مستودعات وسجلات» — داخل فولدر الشهر.

المكان المعتمد (توجيه المستخدم ٢٥/٠٩/٢٠٢٦):
    database/<السنة>/<الشهر>/06-مستودعات وسجلات/
        سجل الإمداد/ و سجل المتعهد/          ← الدورتان منفصلتان تمامًا
            الشركات الموردة/ ١ مخازن إذون الإضافة/ ٢ مخازن إذون الصرف/ ٣ مخازن دفتر الأصناف/

قاعدة البيانات الحية month.db (WAL ونسخ احتياطي)، وهنا مرايا مقروءة تتحدث بعد كل
حفظ ناجح فقط: JSON داخلي + **Excel RTL هو الملف الذي يفتحه المستخدم** (قاعدة ٢٣/٠٩).
"""
import json
import logging
from datetime import date

from core import arabic_numbers as arnum, dates, egtime
from core.config import SECTIONS, MONTH_NAMES
from data_access import dataguard, storage
from data_access import db_warehouses as dw

CYCLE_FOLDERS = {"supply": "سجل الإمداد", "contractor": "سجل المتعهد"}
SUB_FOLDERS = {
    "suppliers": "الشركات الموردة",
    "wh1": "١ مخازن إذون الإضافة",
    "wh2": "٢ مخازن إذون الصرف",
    "wh3": "٣ مخازن دفتر الأصناف",
}
# ملفات Excel التي يفتحها المستخدم بزر «فتح ملف» — كلها Excel (توجيه ٢٣/٠٩)
TAB_XLSX = {
    "suppliers": "الشركات الموردة.xlsx",
    "wh1": "إذون إضافة ١ مخازن.xlsx",
    "wh2": "دفتر إذون صرف ٢ مخازن.xlsx",
    "wh3": "دفتر ٣ مخازن.xlsx",
}

HEADER_1 = "منطقة وسط وجنوب للأمن المركزي"
HEADER_2 = "قطاع وسط سيناء - قسم التعيينات"


def _section_index():
    for index, section in enumerate(SECTIONS, start=1):
        if section["key"] == "warehouses_records":
            return index
    raise KeyError("warehouses_records")


def base_dir(year, month, cycle):
    """فولدر الدورة: database/<سنة>/<شهر>/06-مستودعات وسجلات/<سجل الدورة>"""
    path = storage.section_files_path(year, month, _section_index()) / CYCLE_FOLDERS[cycle]
    path.mkdir(parents=True, exist_ok=True)
    return path


def cycle_dir(year, month, cycle, sub):
    """فولدر التبويب الفرعي داخل الدورة — يُنشأ إن لم يوجد."""
    path = base_dir(year, month, cycle) / SUB_FOLDERS[sub]
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_path(year, month, cycle, sub):
    """مسار ملف Excel للتبويب — بلا إنشاء."""
    return base_dir(year, month, cycle) / SUB_FOLDERS[sub] / TAB_XLSX[sub]


def ensure_folders(year, month):
    """ينشئ فولدرات الدورتين كلها (يُستدعى عند فتح القسم وكل حفظ)."""
    for cycle in CYCLE_FOLDERS:
        for sub in SUB_FOLDERS:
            cycle_dir(year, month, cycle, sub)
    return base_dir(year, month, "supply").parent


def _save_json(path, payload):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    data = text.encode("utf-8")
    dataguard.atomic_save(
        lambda tmp: __import__("pathlib").Path(tmp).write_bytes(data),
        path, zip_check=False)


def _d(day, year, month):
    """تاريخ اليوم داخل الشهر بصيغة العرض dd/mm/yyyy."""
    try:
        return dates.format_date(f"{year:04d}-{month:02d}-{int(day):02d}")
    except (TypeError, ValueError):
        return "—"


def _date_or_dash(iso):
    return dates.format_date(iso) if iso else "—"


def _wday(day, year, month):
    """اسم اليوم بالعربية (السبت/الأحد…) — قاعدة عمود «اليوم» في كل الدفاتر."""
    try:
        return egtime.weekday_ar(date(int(year), int(month), int(day)))
    except (TypeError, ValueError):
        return "—"


# كاتب Excel RTL الموحد في المنظومة (نفس كاتب مرايا التأميدات) — مصدر واحد للشكل
from services.tameedat_fs import _save_xlsx  # noqa: E402


def snapshot_cycle(year, month, cycle):
    """يعيد كتابة مرايا دورة واحدة بعد أي حفظ/تعديل/حذف ناجح — محليًا وذرّيًا."""
    cycle_name = CYCLE_FOLDERS[cycle]
    ensure_folders(year, month)
    suppliers = dw.list_suppliers(year, month, cycle)
    items = dw.list_items(year, month, cycle)
    receipts = dw.list_receipts(year, month, cycle, limit=10000)
    permits = dw.permits_book(year, month, cycle)

    # ---------- الشركات الموردة ----------
    _save_json(cycle_dir(year, month, cycle, "suppliers") / "الشركات الموردة.json", {
        "الجهة": HEADER_1, "القسم": HEADER_2, "الدورة": cycle_name,
        "الشهر": MONTH_NAMES[month - 1], "السنة": year,
        "آخر تحديث": egtime.now().isoformat(timespec="seconds"),
        "عدد الشركات": len(suppliers),
        "الشركات": [{
            "اسم الشركة": s["name"], "اسم المورد": s["contact"], "تليفون المورد": s["phone"],
            "العنوان": s["address"], "النشاط": s["activity"], "ملاحظات": s["notes"],
        } for s in suppliers]})
    _save_xlsx(cycle_dir(year, month, cycle, "suppliers") / TAB_XLSX["suppliers"], [(
        "الشركات الموردة",
        ["م", "اسم الشركة", "اسم المورد", "تليفون المورد", "العنوان", "النشاط", "ملاحظات"],
        [(idx, s["name"], s["contact"] or "—", s["phone"] or "—",
          s["address"] or "—", s["activity"] or "—", s["notes"] or "—")
         for idx, s in enumerate(suppliers, 1)])])

    # ---------- ١ مخازن ----------
    _save_json(cycle_dir(year, month, cycle, "wh1") / "إذون الإضافة.json", {
        "الجهة": HEADER_1, "القسم": HEADER_2, "الدورة": cycle_name,
        "الشهر": MONTH_NAMES[month - 1], "السنة": year,
        "آخر تحديث": egtime.now().isoformat(timespec="seconds"),
        "عدد الإذون": len(receipts),
        "الإذون": [{
            "رقم الإذن": r["serial"], "اليوم": _wday(r["day"], year, month),
            "يوم الشهر": r["day"], "التاريخ": _d(r["day"], year, month),
            "الصنف": _item_name(items, r["item_id"]),
            "الكمية": r["qty_handle"], "وحدة التعامل": r["unit"],
            "يعادل بوحدة القاعدة": r["qty_base"], "وحدة القاعدة": r["base_unit"],
            "التغليف": {"النوع": r.get("pack_kind") or "—",
                        "عدد العبوات": r.get("pack_count") or 0,
                        "سعة العبوة": r.get("pack_capacity") or 0,
                        "كمية سائبة": r.get("pack_loose") or 0},
            "المخازن": [{"المخزن": p["store_name"], "الكمية": p["qty"]}
                        for p in r["stores"]],
            "الشركة المنتجة": r["producer"] or "—",
            "المورد": r["supplier_name"] or "—",
            "تاريخ الإنتاج": _date_or_dash(r["prod_date"]),
            "تاريخ الصلاحية": _date_or_dash(r["exp_date"]),
            "مدة الصلاحية (يوم)": r["shelf_days"] if r["shelf_days"] is not None else "—",
            "ملاحظات": r["notes"] or "—",
        } for r in receipts]})
    def _pack_cell(r):
        if r.get("pack_label"):
            return r["pack_label"]          # التسمية العربية الموحدة
        if not r.get("pack_kind") or r["pack_kind"] == "بدون تغليف":
            return "—"
        bits = []
        if r.get("pack_count"):
            cell = "{} {}".format(arnum.fmt_qty(r["pack_count"]).rstrip("0").rstrip("٫") or "٠", r["pack_kind"])
            if r.get("pack_capacity"):
                cell += " × {}".format(arnum.fmt_qty(r["pack_capacity"]).rstrip("0").rstrip("٫") or "٠")
            bits.append(cell)
        if r.get("pack_loose"):
            bits.append("{} سائب".format(arnum.fmt_qty(r["pack_loose"]).rstrip("0").rstrip("٫") or "٠"))
        return " + ".join(bits) or "—"

    def _stores_cell(r):
        cells = []
        for p in r["stores"]:
            cells.append("{} ({})".format(p["store_name"], arnum.fmt_qty(p["qty"])))
        return "، ".join(cells) or "—"

    _save_xlsx(cycle_dir(year, month, cycle, "wh1") / TAB_XLSX["wh1"], [(
        "إذون إضافة ١ مخازن",
        ["رقم الإذن", "اليوم", "يوم الشهر", "التاريخ", "الصنف", "الكمية", "وحدة التعامل",
         "يعادل (قاعدة)", "وحدة القاعدة", "التغليف", "المخازن", "الشركة المنتجة", "المورد",
         "تاريخ الإنتاج", "تاريخ الصلاحية", "مدة الصلاحية (يوم)", "ملاحظات"],
        [(r["serial"], _wday(r["day"], year, month), r["day"], _d(r["day"], year, month), _item_name(items, r["item_id"]),
          r["qty_handle"], r["unit"], r["qty_base"], r["base_unit"], _pack_cell(r),
          _stores_cell(r), r["producer"] or "—", r["supplier_name"] or "—",
          _date_or_dash(r["prod_date"]), _date_or_dash(r["exp_date"]),
          r["shelf_days"] if r["shelf_days"] is not None else "—", r["notes"] or "—")
         for r in sorted(receipts, key=lambda x: x["serial"])])])

    # ---------- ٣ مخازن ----------
    cards = {it["id"]: dw.item_card(year, month, it["id"]) for it in items}
    moves = []
    for it in items:
        card = cards[it["id"]] or {"rows": []}
        for row in card["rows"]:
            moves.append((it["name"], it["handle_unit"], row))
    _save_json(cycle_dir(year, month, cycle, "wh3") / "دفتر الأصناف.json", {
        "الجهة": HEADER_1, "القسم": HEADER_2, "الدورة": cycle_name,
        "الشهر": MONTH_NAMES[month - 1], "السنة": year,
        "آخر تحديث": egtime.now().isoformat(timespec="seconds"),
        "الأصناف": [{
            "الصنف": it["name"], "وحدة التعامل": it["handle_unit"],
            "وحدة المقرر": it["ration_unit"] or "—", "الرصيد": it["balance"],
        } for it in items],
        "الحركات": [{
            "الصنف": name, "اليوم": _wday(row["day"], year, month),
            "يوم الشهر": row["day"], "التاريخ": _d(row["day"], year, month),
            "رقم الإذن": row["permit_no"] or "—", "البيان": row["label"],
            "مضاف": row["added"], "منصرف": row["issued"], "الرصيد": row["balance"],
        } for name, _unit, row in moves]})
    balance_rows = [(idx, it["name"], it["handle_unit"], it["ration_unit"] or "—",
                     it["balance"]) for idx, it in enumerate(items, 1)]
    move_rows = [(idx, name, _wday(row["day"], year, month), row["day"], _d(row["day"], year, month),
                  row["permit_no"] or "—", row["label"], row["added"], row["issued"],
                  row["balance"], row["notes"] or "—")
                 for idx, (name, _unit, row) in enumerate(moves, 1)]
    _save_xlsx(cycle_dir(year, month, cycle, "wh3") / TAB_XLSX["wh3"], [
        ("أرصدة الأصناف",
         ["م", "الصنف", "وحدة التعامل", "وحدة المقرر", "الرصيد"], balance_rows),
        ("حركات الدفتر",
         ["م", "الصنف", "اليوم", "يوم الشهر", "التاريخ", "رقم الإذن", "البيان",
          "مضاف", "منصرف", "الرصيد", "ملاحظات"], move_rows)])

    # ---------- ٢ مخازن (عرض) ----------
    _save_json(cycle_dir(year, month, cycle, "wh2") / "إذون الصرف.json", {
        "الجهة": HEADER_1, "القسم": HEADER_2, "الدورة": cycle_name,
        "الشهر": MONTH_NAMES[month - 1], "السنة": year,
        "آخر تحديث": egtime.now().isoformat(timespec="seconds"),
        "ملاحظة": "الخصم التلقائي لدفاتر ٣ مخازن يُبنى مع مراحل ٤–٧ مخازن",
        "الإذون": [{
            "رقم الإذن": p["number"], "السنة المالية": p["fiscal_year"],
            "من يوم": p["date_from"], "إلى يوم": p["date_to"],
            "أيام الصرف": p["issue_days"], "الجهات": p["entity_label"],
            "ضباط": p["officers"], "أفراد": p["individuals"], "مجندين": p["recruits"],
            "أصناف الدورة": [{"الصنف": it["name"], "الكمية": it["qty"],
                              "الوحدة": it["unit"] or "—"} for it in p["cycle_items"]],
        } for p in permits]})
    permit_rows = []
    for p in permits:
        for it in p["cycle_items"]:
            permit_rows.append((p["number"], p["fiscal_year"], p["date_from"],
                                p["date_to"], p["issue_days"], p["entity_label"] or "—",
                                it["name"], it["qty"], it["unit"] or "—"))
    tafreeda = dw.tafreeda_rows(year, month, cycle)
    taf_rows = [(t["permit_no"], t["item"], t["store_name"],
                 t["receipt_serial"] or "رصيد أول المدة",
                 _date_or_dash(t["expiry"]), t["qty"], t["unit"],
                 t["pack_label"] or "—") for t in tafreeda]
    _save_xlsx(cycle_dir(year, month, cycle, "wh2") / TAB_XLSX["wh2"], [
        ("دفتر إذون صرف ٢ مخازن",
         ["رقم الإذن", "السنة المالية", "من يوم", "إلى يوم", "أيام الصرف",
          "الجهات", "الصنف", "الكمية الفعلية", "الوحدة"], permit_rows),
        ("التفريدة التلقائية",
         ["رقم الإذن", "الصنف", "المخزن", "الدفعة (إذن إضافة)", "الصلاحية",
          "الكمية المنصرفة", "الوحدة", "تغليف الدفعة"], taf_rows)])

    dataguard.auto_backup("write", min_minutes=20)
    return True


def _item_name(items, item_id):
    for it in items:
        if it["id"] == item_id:
            return it["name"]
    return "—"


def snapshot_all(year, month):
    """مرايا الدورتين معًا (تُستدعى عند فتح القسم)."""
    for cycle in CYCLE_FOLDERS:
        try:
            snapshot_cycle(year, month, cycle)
        except Exception:
            logging.exception("warehouses snapshot failed for cycle %s", cycle)
    return True
