# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الملف المحلي لقسم «المخازن والثلاجات» — موحد لكل الأصناف (بلا تموينية/متعهد).

المكان المعتمد: database/<السنة>/<الشهر>/10-المخازن والثلاجات/
    سجل المخازن/ (المواصفات) — حركة المخازن/ (داخل وخارج بالتغليف) — كشف الأرصدة/
الحركة والأرصدة محسوبة من دفاتر ١ و٢ و٣ مخازن للدورتين — تتجدد تلقائيًا مع أي ٢ مخازن.
"""
import logging

from core.config import MONTH_NAMES
from data_access import db_warehouses as dw
from data_access import db_stores
from services import warehouses_fs as wf
from services.tameedat_fs import _save_xlsx

TAB_FILES = {
    "mains": "سجل المخازن.xlsx",
    "movement": "حركة وكشف الأرصدة.xlsx",
}


def base_dir(year, month):
    from core.config import SECTIONS
    from data_access import storage
    index = next(i for i, s in enumerate(SECTIONS, start=1)
                 if s["key"] == "cold_stores")
    path = storage.section_files_path(year, month, index)
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_path(year, month, tab):
    sub = "سجل المخازن" if tab == "mains" else "حركة وكشف الأرصدة"
    path = base_dir(year, month) / sub
    path.mkdir(parents=True, exist_ok=True)
    return path / TAB_FILES[tab]


def _fmt_pack(row):
    bits = []
    if row.get("pack_label"):
        bits.append(row["pack_label"])
    return " — ".join(bits) or "—"


def snapshot(year, month):
    """مرايا القسم الثلاثة — تُستدعى عند الفتح وبعد كل حفظ في المخازن."""
    from core import egtime
    try:
        stores = db_stores.list_stores()
        _save_xlsx(file_path(year, month, "mains"), [(
            "سجل المخازن",
            ["م", "اسم المخزن", "الموقع", "السعة (متر)", "عدد المرواح",
             "عدد الشفاطات", "التجهيزات", "ملاحظات"],
            [(i, s["name"], s["location"] or "—", s["capacity_m2"] or "—",
              s["fans"] if s["fans"] is not None else "—",
              s["extractors"] if s["extractors"] is not None else "—",
              s["equipment"] or "—", s["notes"] or "—")
             for i, s in enumerate(stores, 1)])])

        rep = dw.stores_report(year, month)
        move_rows, balance_rows = [], []
        idx = 0
        for target in rep["stores"] + [rep["unassigned"]]:
            store_name = target["store"]["name"]
            for row in target["inn"]:
                idx += 1
                move_rows.append((idx, store_name, "إضافة", row["date_iso"],
                                  row["cycle"], row["item"], row["qty"], row["unit"],
                                  _fmt_pack(row), f"إذن إضافة رقم {row['serial']}"
                                  if row.get("serial") else "رصيد أول المدة"))
            for row in target["out"]:
                idx += 1
                move_rows.append((idx, store_name, "صرف", row["date_iso"],
                                  row["cycle"], row["item"], row["qty"], row["unit"],
                                  _fmt_pack(row),
                                  f"إذن صرف ٢ مخازن رقم {row['permit_no']}"))
        for target in rep["stores"] + [rep["unassigned"]]:
            store_name = target["store"]["name"]
            for item, qty in sorted(target["balances"].items()):
                balance_rows.append((store_name, item, qty))
        _save_xlsx(file_path(year, month, "movement"), [
            ("حركة المخازن",
             ["م", "المخزن", "النوع", "التاريخ", "الدورة", "الصنف",
              "الكمية", "الوحدة", "التغليف", "المستند"], move_rows),
            ("كشف الأرصدة",
             ["المخزن", "الصنف", "الرصيد"], balance_rows)])
    except Exception:
        logging.exception("stores snapshot failed")


def ensure_folders(year, month):
    file_path(year, month, "mains")
    file_path(year, month, "movement")
    return base_dir(year, month)
