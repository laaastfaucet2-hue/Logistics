# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""ملفات دورة «الترفية» المحلية — database/<سنة>/<شهر>/11-الترفية/:

الأصناف/ · ١ مخازن إذون الإضافة/ · ٢ مخازن إذون الصرف/ · ٣ مخازن دفتر الأصناف/
· ٥ مخازن السجل اليومي/ — كل تاب ملف Excel مرآة يتحدث ذرّيًا بعد كل حفظ
(نفس نمط مستودعات وسجلات — توجيه ٢٩/٠٩).
"""
from core import arabic_numbers as arnum
from core import egtime
from data_access import storage
from data_access import db_warehouses as dw
from data_access import db_tarfea as dt
from services.tameedat_fs import _save_xlsx
from services import warehouses_fs as wf  # HEADER_1/2 + مساعدات التاريخ

SUB_FOLDERS = {
    "items": "الأصناف",
    "wh1": "١ مخازن إذون الإضافة",
    "wh2": "٢ مخازن إذون الصرف",
    "wh3": "٣ مخازن دفتر الأصناف",
    "wh5": "٥ مخازن السجل اليومي",
}
TAB_XLSX = {
    "items": "كشف الأصناف.xlsx",
    "wh1": "إذون إضافة ١ مخازن ترفية.xlsx",
    "wh2": "دفتر صرف ٢ مخازن ترفية.xlsx",
    "wh3": "دفتر ٣ مخازن ترفية.xlsx",
    "wh5": "سجل ٥ مخازن.xlsx",
}


def _section_index():
    for index, section in enumerate(SECTIONS_IDX, start=1):
        if section == "tarfea":
            return index
    raise KeyError("tarfea")


SECTIONS_IDX = [s["key"] for s in __import__("core.config", fromlist=["SECTIONS"]).SECTIONS]


def base_dir(year, month):
    path = storage.section_files_path(year, month, _section_index())
    path.mkdir(parents=True, exist_ok=True)
    return path


def sub_dir(year, month, sub):
    path = base_dir(year, month) / SUB_FOLDERS[sub]
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_path(year, month, sub):
    return sub_dir(year, month, sub) / TAB_XLSX[sub]


def ensure_folders(year, month):
    for sub in SUB_FOLDERS:
        sub_dir(year, month, sub)
    return base_dir(year, month)


def folder_hint(year, month):
    from core.config import month_folder
    return "database/{}/{}/11-الترفية/".format(year, month_folder(month))


def _meta(title):
    return {"الجهة": wf.HEADER_1, "القسم": wf.HEADER_2, "الدورة": "الترفية",
            "آخر تحديث": egtime.now().isoformat(timespec="seconds"),
            "الورقة": title}


def _d(day, year, month):
    return wf._d(day, year, month)


def _wday(day, year, month):
    return wf._wday(day, year, month)


def snapshot(year, month):
    """يعيد كتابة مرايا الترفية الخمسة بعد أي حفظ — محليًا وذرّيًا."""
    ensure_folders(year, month)
    items = dt.list_items(year, month)
    receipts = dt.list_receipts(year, month)
    issues = dt.list_issues(year, month)
    names = {it["id"]: it["name"] for it in items}

    # ---------- الأصناف ----------
    _save_xlsx(file_path(year, month, "items"), [(
        "كشف أصناف الترفية",
        ["م", "اسم الصنف", "وحدة التعامل", "وحدة القاعدة", "عليه حركة"],
        [(idx, it["name"], it["handle_unit"], it["base_unit"],
          "نعم" if dw.item_has_movement(year, month, dt.CYCLE, it["id"]) else "لا")
         for idx, it in enumerate(items, 1)])])

    # ---------- ١ مخازن ----------
    def _pack_cell(r):
        return r.get("pack_label") or "—"

    _save_xlsx(file_path(year, month, "wh1"), [(
        "إذون إضافة ١ مخازن ترفية",
        ["رقم الإذن", "اليوم", "التاريخ", "الصنف", "الكمية", "وحدة التعامل",
         "يعادل (قاعدة)", "وحدة القاعدة", "التغليف", "الشركة المنتجة", "المورد",
         "تاريخ الإنتاج", "تاريخ الصلاحية", "ملاحظات"],
        [(r["serial"], _wday(r["day"], year, month), _d(r["day"], year, month),
          names.get(r["item_id"], "—"), r["qty_handle"], r["unit"],
          r["qty_base"], r["base_unit"], _pack_cell(r),
          r["producer"] or "—", r["supplier_name"] or "—",
          wf._date_or_dash(r["prod_date"]), wf._date_or_dash(r["exp_date"]),
          dw.user_notes(r["notes"]) or "—")
         for r in sorted(receipts, key=lambda x: x["serial"])])])

    # ---------- ٢ مخازن ----------
    _save_xlsx(file_path(year, month, "wh2"), [(
        "دفتر صرف ٢ مخازن ترفية",
        ["رقم الإذن", "اليوم", "التاريخ", "الصنف", "الكمية المنصرفة", "الوحدة",
         "منصرف إلى", "المسؤول عن الصرف", "ملاحظات"],
        [(i["serial"], _wday(i["day"], year, month), _d(i["day"], year, month),
          i["item_name"] or "—", i["qty"], i["unit"] or "—",
          i["receiver"] or "—", i["responsible"] or "—",
          i["notes"] or "—") for i in issues])])

    # ---------- ٣ مخازن ----------
    wh3_rows = []
    for it in items:
        card = dt.item_card(year, month, it["id"]) or {}
        for r in card.get("rows") or []:
            wh3_rows.append((
                it["name"], _wday(r["day"], year, month), _d(r["day"], year, month),
                r.get("permit_no") or "—",
                {"opener": "رصيد أول المدة", "add1": "إذن إضافة",
                 "issue2": "إذن صرف ٢ مخازن"}.get(r.get("kind"), r.get("kind")),
                r.get("added") or 0, r.get("issued") or 0, r.get("balance") or 0,
                r.get("pack_label") or "—", r.get("notes") or "—"))
    _save_xlsx(file_path(year, month, "wh3"), [(
        "دفتر ٣ مخازن ترفية",
        ["الصنف", "اليوم", "التاريخ", "رقم الإذن", "البيان", "مضاف",
         "منصرف", "الرصيد", "التغليف", "ملاحظات"],
        wh3_rows)])

    # ---------- ٥ مخازن ----------
    t5 = dt.t5_rows(year, month)
    _save_xlsx(file_path(year, month, "wh5"), [(
        "سجل ٥ مخازن اليومي",
        ["م", "التاريخ", "رقم الإذن", "وارد من / منصرف إلى",
         "قيمة الأصناف المضافة", "قيمة الأصناف المنصرفة",
         "البيان والملحوظات والتفاصيل", "المسؤول عن الصرف"],
        [(idx, _d(r["day"], year, month),
          r["permit_no"] or "رصيد", r["party"],
          "{} {}".format(arnum.fmt_qty(r["added"]), r["unit"] or "").strip()
          if r["added"] else "—",
          "{} {}".format(arnum.fmt_qty(r["issued"]), r["unit"] or "").strip()
          if r["issued"] else "—",
          r["details"], r["responsible"] or "—")
         for idx, r in enumerate(t5, 1)])])

    return base_dir(year, month)
