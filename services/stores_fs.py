# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الملف المحلي لقسم «المخازن والثلاجات» — موحد لكل الأصناف (بلا تموينية/متعهد).

المكان المعتمد: database/<السنة>/<الشهر>/10-المخازن والثلاجات/
    سجل المخازن/ (المواصفات) — حركة المخازن/ (داخل وخارج بالتغليف) — كشف الأرصدة/
الحركة والأرصدة محسوبة من دفاتر ١ و٢ و٣ مخازن للدورتين — تتجدد تلقائيًا مع أي ٢ مخازن.
"""
import logging

from core import dates
from core.config import MONTH_NAMES
from data_access import db_warehouses as dw
from data_access import db_stores
from services import warehouses_fs as wf
from services.tameedat_fs import _save_xlsx

TAB_FILES = {
    "mains": "سجل المخازن.xlsx",
    "movement": "حركة وكشف أرصدة المخازن.xlsx",   # 🆕 الملف الموحد (٤ شيتات + شيتات الأصناف)
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
    path = base_dir(year, month)
    if tab == "mains":
        path = path / "سجل المخازن"
        path.mkdir(parents=True, exist_ok=True)
    return path / TAB_FILES[tab]


def _fmt_pack(row):
    bits = []
    if row.get("pack_label"):
        bits.append(row["pack_label"])
    return " — ".join(bits) or "—"


def snapshot(year, month):
    """مرايا القسم الثلاثة — تُستدعى عند الفتح وبعد كل حفظ في المخازن."""
    from core import arabic_numbers as arnum, egtime
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

        # 🆕 فولدر لكل مخزن (ملف واحد ٤ شيتات) + الملف الجذري الموحد
        # «حركة وكشف أرصدة المخازن.xlsx» — توجيه المستخدم
        from services import cycle_xlsx
        units = {}
        for _c in ("supply", "contractor", "tarfea"):
            try:
                for _it in dw.list_items(year, month, _c):
                    units[_it["name"]] = _it["handle_unit"]
            except Exception:
                continue
        cycle_xlsx.build_store_folders(base_dir(year, month), rep, units,
                                       year, month)
    except Exception:
        logging.exception("stores snapshot failed")


def ensure_folders(year, month):
    base = base_dir(year, month)
    file_path(year, month, "mains")
    file_path(year, month, "movement")
    # 🧹 ترحيل الهيكل القديم (توجيه المستخدم — ملف موحد + ملف واحد لكل مخزن)
    import shutil
    old_sub = base / "حركة وكشف الأرصدة"
    if old_sub.is_dir():
        shutil.rmtree(old_sub, ignore_errors=True)
    for old in ("حركة المخازن.xlsx", "حركة المخازن تغليف.xlsx"):
        oldp = base / old
        if oldp.exists():
            try:
                oldp.unlink()
            except OSError:
                pass
    return base
