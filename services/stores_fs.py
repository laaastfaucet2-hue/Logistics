# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الملف المحلي لقسم «المخازن والثلاجات» — موحد لكل الأصناف (بلا تموينية/متعهد).

المكان المعتمد (توجيه ٠٨/١٠):
    database/<السنة>/<الشهر>/10-المخازن والثلاجات/
        سجل المخازن/سجل المخازن.xlsx                 (المواصفات)
        <المخزن>/                                   ← يتعمل لحظيًا عند إنشاء المخزن
            حركة المخزن/حركة المخزن.xlsx             (كل حركات المخزن — داخل وخارج)
            الأصناف/<صنف>.xlsx                      (حركة كل صنف جوا المخزن)
            كشف أرصدة المخازن/كشف جرد أرصدة المخزن.xlsx (الرصيد بالتغليف)
الحركة والأرصدة محسوبة من دفاتر ١ و٢ مخازن للدورتين (إمداد + متعهد — الترفية خارجة)
وتتجدد تلقائيًا مع أي حفظ.
"""
import logging

from services.tameedat_fs import _save_xlsx

# الفولدرات داخل كل مخزن — مطابقة للـ 3 تابات في الواجهة 1:1
SUB_MOVEMENT = "حركة المخزن"
SUB_ITEMS = "الأصناف"
SUB_BALANCE = "كشف أرصدة المخازن"
STORE_SUBS = (SUB_MOVEMENT, SUB_ITEMS, SUB_BALANCE)

MOVE_FILE = "حركة المخزن.xlsx"
BALANCE_FILE = "كشف جرد أرصدة المخزن.xlsx"
MAIN_FOLDER = "سجل المخازن"
MAIN_FILE = "سجل المخازن.xlsx"

STATS_FILE = "إحصائيات المخازن.xlsx"
TAB_FILES = {"mains": MAIN_FILE, "stats": STATS_FILE}


def _safe_name(title):
    return "".join(ch for ch in str(title) if ch not in "\\/:*?\"<>|").strip() or "ملف"


def base_dir(year, month):
    from core.config import SECTIONS
    from data_access import storage
    index = next(i for i, s in enumerate(SECTIONS, start=1)
                 if s["key"] == "cold_stores")
    path = storage.section_files_path(year, month, index)
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_dir(year, month, store_name, create=True):
    """فولدر المخزن — نفس اسم المخزن بالظبط (يبتمس معاه عند أي تغيير)."""
    path = base_dir(year, month) / _safe_name(store_name)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def store_sub(year, month, store_name, sub, create=True):
    """فولدر فرعي جوا المخزن (حركة المخزن / الأصناف / كشف أرصدة المخازن)."""
    if sub not in STORE_SUBS:
        raise ValueError(sub)
    path = store_dir(year, month, store_name) / sub
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def create_store_folder(year, month, store_name):
    """إنشاء فولدر المخزن + فولدراته الثلاثة لحظيًا (توجيه ٠٨/١٠: أول ما المخزن
    يتعمل فولدره يتعمل)."""
    store_dir(year, month, store_name)
    for sub in STORE_SUBS:
        store_sub(year, month, store_name, sub)
    return store_dir(year, month, store_name, create=False)


def store_file_path(year, month, store_name, sub, item=None):
    """مسار إكسل جوا المخزن — sub بمفتاحه الثابت (movement/items/balance):
    movement → حركة المخزن/حركة المخزن.xlsx
    items    → الأصناف/ (فولدر) أو الأصناف/<صنف>.xlsx لو جه اسم صنف
    balance  → كشف أرصدة المخازن/كشف جرد أرصدة المخزن.xlsx"""
    from services import cycle_xlsx
    key = {"movement": SUB_MOVEMENT, "items": SUB_ITEMS,
           "balance": SUB_BALANCE}.get(sub, sub)
    root = store_dir(year, month, store_name, create=False)
    if key == SUB_MOVEMENT:
        return root / SUB_MOVEMENT / MOVE_FILE
    if key == SUB_ITEMS:
        items_dir = root / SUB_ITEMS
        if item:
            return items_dir / cycle_xlsx._file_name(item)
        return items_dir
    if key == SUB_BALANCE:
        return root / SUB_BALANCE / BALANCE_FILE
    raise ValueError(sub)


def file_path(year, month, tab):
    path = base_dir(year, month)
    if tab == "mains":
        path = path / MAIN_FOLDER
        path.mkdir(parents=True, exist_ok=True)
    return path / TAB_FILES[tab]


def snapshot(year, month):
    """مرايا القسم — تُستدعى عند الفتح وبعد كل حفظ في المخازن."""
    from data_access import db_stores
    from data_access import db_warehouses as dw
    try:
        stores = db_stores.list_stores()
        _save_xlsx(file_path(year, month, "mains"), [(
            MAIN_FOLDER,
            ["م", "اسم المخزن", "الموقع", "السعة (متر)", "عدد المرواح",
             "عدد الشفاطات", "التجهيزات", "ملاحظات"],
            [(i, s["name"], s["location"] or "—", s["capacity_m2"] or "—",
              s["fans"] if s["fans"] is not None else "—",
              s["extractors"] if s["extractors"] is not None else "—",
              s["equipment"] or "—", s["notes"] or "—")
             for i, s in enumerate(stores, 1)])])

        rep = dw.stores_report(year, month)
        units = {}
        for _c in ("supply", "contractor"):
            try:
                for _it in dw.list_items(year, month, _c):
                    units[_it["name"]] = _it["handle_unit"]
            except Exception:
                continue
        # فولدر لكل مخزن (3 فولدرات + الإكسلس) + ترحيل أي هيكل قديم/متبسم
        from services import cycle_xlsx
        cycle_xlsx.build_store_folders(base_dir(year, month), rep, units,
                                       year, month)
        stats_snapshot(year, month)
    except Exception:
        logging.exception("stores snapshot failed")


def stats_snapshot(year, month):
    """مرايا تاب الإحصائيات — بالمخزن + شهادات الصلاحية + توب ٥ (بلا جداول جديدة)."""
    from services import stats_sections as ssec
    try:
        st = ssec.stores_stats(year, month)
        path = file_path(year, month, "stats")
        path.parent.mkdir(parents=True, exist_ok=True)
        _save_xlsx(path, [
            ("بالمخزن", ["المخزن", "الأصناف", "الداخل", "الخارج", "إجمالي الرصيد"],
             [(r["name"], r["items"], r["inn"], r["out"], r["total"]) for r in st["rows"]]
             + [(st["unassigned"]["name"], st["unassigned"]["items"],
                 st["unassigned"]["inn"], st["unassigned"]["out"], st["unassigned"]["total"])]),
            ("شهادات الصلاحية", ["الحالة", "عدد الدفعات المضافة"],
             [("سليم (أكثر من ٩٠ يوم)", st["expiring"]["ok"]),
              ("قرب الصلاحية (٣٠–٩٠ يوم)", st["expiring"]["warn"]),
              ("خطر (أقل من ٣٠ يوم)", st["expiring"]["bad"])]),
            ("توب ٥ استهلاك", ["الصنف", "المنصرف (FEFO)"],
             [(k, v) for k, v in st["top5"]]),
        ], year, month)
    except Exception:
        logging.exception("stores stats snapshot failed")


def ensure_folders(year, month):
    """فولدرات القسم + ترحيل الهياكل القديمة (توجيه ٠٨/١٠)."""
    import shutil
    base = base_dir(year, month)
    file_path(year, month, "mains")
    # 🧹 هيكل ١٠/٠٧ القديم: الملف الجذري الموحد + فولدر «حركة وكشف الأرصدة»
    for old in ("حركة وكشف أرصدة المخازن.xlsx",
                "حركة المخازن.xlsx", "حركة المخازن تغليف.xlsx"):
        oldp = base / old
        if oldp.exists():
            try:
                oldp.unlink()
            except OSError:
                pass
    old_sub = base / "حركة وكشف الأرصدة"
    if old_sub.is_dir():
        shutil.rmtree(old_sub, ignore_errors=True)
    return base
