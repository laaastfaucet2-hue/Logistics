# -*- coding: utf-8 -*-
"""تاب «٢ مخازن تفاريد» — تفريدة كل إذن بالدفعات FEFO ورصيد المخزن قبل/بعد.

توجيه ٠٦/١٠/٢٠٢٦ (الدفعة هـ): التاب الجديد يعرض نفس بيانات ملف
«٢ مخازن تفاريد مجمع.xlsx» وملفات أيامه — قاعدة «الورق = الإكسل».
"""
from data_access import db_permits as dp, db_rations as dr
from data_access import db_warehouses as dw, months
from services import warehouses_fs as wf

YEAR, MONTH = 2031, 9


def _init():
    months.init_month(YEAR, MONTH)


def _seed_stock_and_permit(number=3, qty=60):
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز", "كجم", 0, 0.1, 0)
    dr.set_activation(YEAR, MONTH, "tamween", "summer")
    dw.add_opener(YEAR, MONTH, "supply", "أرز", 200, 1, handle_unit_hint="كجم",
                  exp_iso="2027-06-30", pack_kind="شكارة", pack_count=4, pack_capacity=50)
    dp.save_permit(YEAR, MONTH, {
        "number": number, "fiscal_year": 2026, "date_from": 1, "date_to": 1,
        "issue_days": 1, "mode": "box", "entity_label": "جهة التفريدة",
        "officers": 5, "individuals": 10, "recruits": 0,
        "actuals": {"tamween_أرز": qty}})


def test_tab_is_registered_with_folder_and_file(app):
    _init()
    assert ("tafreeda", "٢ مخازن تفاريد", "🧾") in __import__("routes.warehouses",
                                                             fromlist=["TABS"]).TABS
    assert wf.SUB_FOLDERS["tafreeda"] == "٢ مخازن تفاريد"
    assert wf.TAB_XLSX["tafreeda"] == "٢ مخازن تفاريد مجمع.xlsx"


def test_tab_shows_fefo_lines_with_before_after(client):
    _init()
    _seed_stock_and_permit()
    page = client.get("/warehouses?cycle=supply&sub=tafreeda").data.decode("utf-8")
    for token in ("٢ مخازن تفاريد", "إذن صرف رقم", "الصلاحية المتبقية", "تغليف الدفعة",
                  "المخزن قبل", "المنصرف بالتغليف", "جهة التفريدة"):
        assert token in page, token
    assert "٦٠ كجم" in page                     # المنصرف بالوحدة (أرقام عربية)
    assert "٢٠٠ كجم" in page and "١٤٠ كجم" in page   # رصيد المخزن قبل/بعد


def test_tab_empty_state_is_explicit_and_never_crashes(client):
    _init()
    page = client.get("/warehouses?cycle=contractor&sub=tafreeda").data.decode("utf-8")
    assert "لا تفاريد في هذا الشهر بعد" in page
    assert "٢ مخازن تفاريد" in page             # التاب ظاهر رغم الفراغ


def test_tafreeda_tab_columns_match_its_local_file(client):
    """قاعدة «الورق = الإكسل»: أعمدة الشاشة هي أعمدة ملف «٢ مخازن تفاريد مجمع.xlsx»."""
    from openpyxl import load_workbook
    _init()
    _seed_stock_and_permit(number=9, qty=30)
    wf.snapshot_cycle(YEAR, MONTH, "supply")
    path = wf.file_path(YEAR, MONTH, "supply", "tafreeda")
    assert path.exists()
    ws = load_workbook(path).active
    headers = [c.value for c in ws[1] if c.value]
    page = client.get("/warehouses?cycle=supply&sub=tafreeda").data.decode("utf-8")
    # نفس أعمدة الملف بالحرف — «الورق = الإكسل» (توجيه ٠٦/١٠)
    for name in ("م", "الجهة", "الصنف", "الكمية المنصرفة", "الوحدة", "المنصرف بالتغليف",
                 "تغليف الدفعة", "مخزن", "تاريخ الانتهاء", "الصلاحية المتبقية",
                 "إذن رقم", "ملاحظات"):
        assert name in headers and name in page, name


def test_tab_counts_appear_in_tab_bar(client):
    _init()
    _seed_stock_and_permit(number=11, qty=25)
    page = client.get("/warehouses?cycle=supply&sub=wh2").data.decode("utf-8")
    assert "٢ مخازن تفاريد" in page             # تويب التاب ظاهر في شريط التويبات
    assert "/warehouses?cycle=supply&amp;sub=tafreeda" in page or "sub=tafreeda" in page
