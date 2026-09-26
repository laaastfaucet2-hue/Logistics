# -*- coding: utf-8 -*-
"""الدورة المخزنية «مستودعات وسجلات» — دفعة ١ و٢ و٣ مخازن.

يُحصَّن: تابان «سجل الإمداد / سجل المتعهد» منفصلان تمامًا وبنفس الشاشات،
نموذج الشركات الموردة الشامل، تحويل ١ مخازن للوحدة القاعدة (١ طن = ١٠٠٠ كجم)،
فتح كارت الصنف تلقائيًا في دفتر ٣ مسازن، تسلسل أرقام الإذن، دفتر ٢ مخازن
بأصناف الدورة فقط، قاعدة القوائم المتمثّمة، الطباعة الرسمية، ومرايا Excel.
"""
from data_access import db_permits as dp
from data_access import db_rations as dr
from data_access import db_warehouses as dw
from data_access import months
from services import warehouses_fs as wf

YEAR, MONTH = 2031, 9


def _init():
    months.init_month(YEAR, MONTH)


def _page(client, url):
    response = client.get(url)
    assert response.status_code == 200, (url, response.status_code)
    return response.data.decode("utf-8")


def _post(client, url, data, follow=False):
    response = client.post(url, data=data, follow_redirects=follow)
    expected = 200 if follow else 302
    assert response.status_code == expected, (url, response.status_code, response.data[:200])
    return response


def _sidebar(page):
    start = page.index("<aside")
    end = page.index("</aside>")
    return page[start:end]


# ======================================================================
# الهيكل: تابان الدورتين + التويبات الأربعة + الشريط الجانبي كما هو
# ======================================================================
def test_page_shows_both_cycles_and_four_subtabs(client):
    _init()
    page = _page(client, "/warehouses")
    assert "سجل الإمداد" in page and "سجل المتعهد" in page
    assert "منفصلتان تمامًا" in page
    for name in ("الشركات الموردة", "١ مخازن", "٢ مخازن", "٣ مخازن"):
        assert name in page
    assert "/warehouses?cycle=contractor" in page or "cycle=contractor" in page


def test_sidebar_unchanged_no_new_top_level_entries(client):
    page = _page(client, "/dashboard")
    sidebar = _sidebar(page)
    assert "/sections/warehouses_records" in sidebar      # التاب الأم كما هو
    assert "سجل الإمداد" not in sidebar                    # التوابع الجديدة داخل الصفحة فقط
    assert "سجل المتعهد" not in sidebar


# ======================================================================
# الشركات الموردة — نموذج شامل + مرآة Excel
# ======================================================================
def test_supplier_full_form_saved_and_mirrored(client):
    _init()
    _post(client, "/warehouses/suppliers/add?cycle=supply", {
        "cycle": "supply", "name": "الشركة العامة للأغذية", "contact": "أ. محمود",
        "phone": "٠١٠٠٢٣٤٥٦٧٨", "address": "طنطا — شارع البحر", "activity": "أغذية",
        "notes": "توريد شهري"})
    page = _page(client, "/warehouses?cycle=supply&sub=suppliers")
    assert "الشركة العامة للأغذية" in page and "أ. محمود" in page
    assert "٠١٠٠٢٣٤٥٦٧٨" in page
    path = wf.file_path(YEAR, MONTH, "supply", "suppliers")
    assert path.exists() and path.name == "الشركات الموردة.xlsx"


def test_supplier_edit_and_delete(client):
    _init()
    dw.add_supplier(YEAR, MONTH, "supply", "مؤسسة النور")
    supplier = dw.list_suppliers(YEAR, MONTH, "supply")[0]
    _post(client, "/warehouses/suppliers/save?cycle=supply", {
        "cycle": "supply", "supplier_id": supplier["id"], "name": "مؤسسة النور للتوريدات",
        "contact": "", "phone": "", "address": "", "activity": "", "notes": ""})
    page = _page(client, "/warehouses?cycle=supply&sub=suppliers")
    assert "مؤسسة النور للتوريدات" in page
    _post(client, "/warehouses/suppliers/delete?cycle=supply",
          {"cycle": "supply", "supplier_id": supplier["id"]})
    assert dw.list_suppliers(YEAR, MONTH, "supply") == []


# ======================================================================
# ١ مخازن: التحويل التلقائي + التسلسل + فتح كارت ٣ مخازن
# ======================================================================
def _seed_ration_item():
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز بلدي", "طن", 0, 0, 0)


def test_wh1_add_converts_ton_to_kg_and_opens_card(client):
    _init()
    _seed_ration_item()
    response = _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١",
        "day": "٢", "producer": "مطاحن الدلتا",
        "prod_date": "٠١/٠٩/٢٠٢٦", "exp_date": "٠١/٠٩/٢٠٢٧",
        "pack_kind": "شكارة", "pack_count": "١٩", "pack_capacity": "٥٠",
        "pack_loose": "٥٠", "store_qty": ""}, follow=True)
    page = response.data.decode("utf-8")
    assert "إذن إضافة ١ مخازن رقم ١" in page
    assert "كارت الصنف" in page and "أرز بلدي" in page  # فُتح كارت ٣ مخازن
    assert "١٠٠٠٫٠٠٠" in page                           # الرصيد = ١٩×٥٠+٥٠ بوحدة التعامل
    item = dw.list_items(YEAR, MONTH, "supply")[0]
    assert item["handle_unit"] == "طن" and item["base_unit"] == "كجم"
    card = dw.item_card(YEAR, MONTH, item["id"])
    assert card["total_added"] == 1000.0 and card["balance"] == 1000.0  # ١٩×٥٠+٥٠ بوحدة التعامل (طن)
    receipt = dw.list_receipts(YEAR, MONTH, "supply")[0]
    assert receipt["serial"] == 1 and receipt["shelf_days"] == 365
    assert receipt["producer"] == "مطاحن الدلتا"
    assert receipt["qty_handle"] == 1000.0              # الكمية حُسبت من التغليف تلقائيًا
    assert receipt["pack_kind"] == "شكارة"


def test_wh1_serial_sequence_and_ledger_growth(client):
    _init()
    _seed_ration_item()
    for qty in ("٥٠٠", "٢٥٠"):
        _post(client, "/warehouses/wh1/add?cycle=supply", {
            "cycle": "supply", "item_name": "أرز بلدي", "qty": qty, "day": "٣"})
    receipts = sorted(dw.list_receipts(YEAR, MONTH, "supply"), key=lambda r: r["serial"])
    assert [r["serial"] for r in receipts] == [1, 2]
    item = dw.list_items(YEAR, MONTH, "supply")[0]
    card = dw.item_card(YEAR, MONTH, item["id"])
    assert card["balance"] == 750.0 and len(card["rows"]) == 2


def test_wh1_new_item_with_chosen_handle_unit(client):
    _init()
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "صلصة", "qty": "١٢", "handle_unit": "كرتونة",
        "day": "٤"})
    item = dw.list_items(YEAR, MONTH, "supply")[0]
    assert item["handle_unit"] == "كرتونة" and item["base_unit"] == "كرتونة"
    assert item["balance"] == 12.0


# ======================================================================
# عزل الدورتين — لا اختلاط إطلاقًا
# ======================================================================
def test_cycles_are_fully_isolated(client):
    _init()
    _seed_ration_item()
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "٧", "day": "٥"})
    _post(client, "/warehouses/suppliers/add?cycle=supply",
          {"cycle": "supply", "name": "مورد الإمداد"})
    supply_page = _page(client, "/warehouses?cycle=supply&sub=wh1")
    assert "أرز بلدي" in supply_page
    assert "إذن إضافة ١ مخازن رقم ١" not in supply_page   # نص الدفتر ليس في ١ مخازن
    contractor_page = _page(client, "/warehouses?cycle=contractor&sub=wh1")
    assert "أرز بلدي" not in contractor_page
    assert "لا إذون إضافة بعد هذا الشهر" in contractor_page
    contractor_suppliers = _page(client, "/warehouses?cycle=contractor&sub=suppliers")
    assert "مورد الإمداد" not in contractor_suppliers
    assert dw.list_items(YEAR, MONTH, "contractor") == []
    assert dw.list_suppliers(YEAR, MONTH, "contractor") == []
    # نفس الاسم في الدورتين = صنفان مستقلان
    _post(client, "/warehouses/wh1/add?cycle=contractor", {
        "cycle": "contractor", "item_name": "أرز بلدي", "qty": "٩", "day": "٥"})
    supply_items = dw.list_items(YEAR, MONTH, "supply")
    contractor_items = dw.list_items(YEAR, MONTH, "contractor")
    assert len(supply_items) == 1 and len(contractor_items) == 1
    assert supply_items[0]["balance"] == 7.0        # ٧ طن بوحدة التعامل
    assert contractor_items[0]["balance"] == 9.0


# ======================================================================
# دفتر ٢ مخازن — إذون الحاسبة بأصناف الدورة فقط (عرض)
# ======================================================================
def _save_permit(number, actuals):
    dp.save_permit(YEAR, MONTH, {
        "number": number, "fiscal_year": 2026, "date_from": 2, "date_to": 3,
        "issue_days": 2, "mode": "combined", "entity_label": "جهة الاختبار",
        "officers": 3, "individuals": 40, "recruits": 5,
        "meals": ["breakfast", "lunch"], "record_ids": [1], "actuals": actuals,
    })


def test_wh2_book_filters_items_per_cycle(client):
    _init()
    _save_permit(1, {"tamween_أرز": 15, "contractor_سكر": 7})
    supply_page = _page(client, "/warehouses?cycle=supply&sub=wh2")
    assert "إذن صرف ٢ مخازن رقم ١" in supply_page and "أرز" in supply_page
    assert "١٥٫٠٠٠" in supply_page
    assert "سكر" not in supply_page
    contractor_page = _page(client, "/warehouses?cycle=contractor&sub=wh2")
    assert "سكر" in contractor_page
    # عزل تام: الإذن مالوش أصناف تانية لدورة المتعهد فلا يُذكر فيه صنف التموين إطلاقًا
    assert "أرز" not in contractor_page
    _save_permit(2, {"tamween_سكر": 3})   # إذن بلا أصناف متعهد — لا يظهر في دفترها
    contractor_page2 = _page(client, "/warehouses?cycle=contractor&sub=wh2")
    assert "إذن صرف ٢ مخازن رقم ٢" not in contractor_page2


# ======================================================================
# توجيهات المستخدم ٢٥/٠٩/٢٠٢٦: رقم إذن يدوي + رصيد أول المدة بكل بياناته
# + المنصرف من إذون ٢ مخازن داخل الكارت + عمود اليوم باسم اليوم
# ======================================================================
def test_receipt_number_is_manual_with_sequence_rules(client):
    _init()
    _seed_ration_item()
    # رقم يدوي يقفز بالتسلسل
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١٠", "day": "٧",
        "receipt_no": "٥"})
    receipts = dw.list_receipts(YEAR, MONTH, "supply")
    assert receipts[0]["serial"] == 5
    # رقم مكرر يُرفض برسالة واضحة
    response = _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "٥", "day": "٧",
        "receipt_no": "٥"}, follow=True)
    assert "مستخدم من قبل" in response.data.decode("utf-8")
    # فارغ يكمّل بعد الأكبر (٦) — ويدوي أكبر يصبح أصل التسلسل
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١", "day": "٧"})
    assert dw.list_receipts(YEAR, MONTH, "supply")[0]["serial"] == 6
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١", "day": "٧",
        "receipt_no": "٩"})
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١", "day": "٧"})
    serials = sorted(r["serial"] for r in dw.list_receipts(YEAR, MONTH, "supply"))
    assert serials == [5, 6, 9, 10]


def test_opener_balance_entered_with_full_details_once(client):
    _init()
    _seed_ration_item()
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "٢٠", "day": "٨"})
    item = dw.list_items(YEAR, MONTH, "supply")[0]
    _post(client, "/warehouses/wh3/opener?cycle=supply", {
        "cycle": "supply", "item_id": item["id"], "qty": "٥٠", "day": "١",
        "producer": "مطاحن الافتتاح", "supplier_name": "مورد الافتتاح",
        "pack_kind": "شكارة", "pack_count": "١", "pack_capacity": "٥٠",
        "notes": "رصيد السنة الماضية"})
    card = dw.item_card(YEAR, MONTH, item["id"])
    assert card["has_opener"] and card["opener_row"]["added"] == 50.0
    assert card["balance"] == 70.0                     # ٥٠ افتتاح + ٢٠ إذن
    assert "مطاحن الافتتاح" in card["opener_row"]["notes"]
    assert "مورد الافتتاح" in card["opener_row"]["notes"]
    assert "تغليف" in card["opener_row"]["notes"]
    # مرة واحدة فقط لكل صنف
    response = _post(client, "/warehouses/wh3/opener?cycle=supply", {
        "cycle": "supply", "item_id": item["id"], "qty": "٩", "day": "٢"}, follow=True)
    assert "لا يُسجل مرتين" in response.data.decode("utf-8")
    page = _page(client, f"/warehouses?cycle=supply&sub=wh3&item={item['id']}")
    assert "رصيد أول المدة" in page and "رصيد السنة الماضية" in page
    assert "لم يُسجَّل بعد" not in page


def test_issued_from_calc2_permits_appears_in_card(client):
    _init()
    _seed_ration_item()
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١٠٠", "day": "٩"})
    dp.save_permit(YEAR, MONTH, {
        "number": 1, "fiscal_year": 2026, "date_from": 10, "date_to": 10,
        "issue_days": 1, "mode": "box", "entity_label": "جهة الصرف التجريبية",
        "officers": 2, "individuals": 30, "recruits": 0, "meals": ["lunch"],
        "record_ids": [1], "actuals": {"tamween_أرز بلدي": 2.4},
    })
    item = dw.list_items(YEAR, MONTH, "supply")[0]
    card = dw.item_card(YEAR, MONTH, item["id"])
    kinds = [r["kind"] for r in card["rows"]]
    assert "issue2" in kinds
    issue = next(r for r in card["rows"] if r["kind"] == "issue2")
    assert issue["issued"] == 2.4 and issue["permit_no"] == 1
    assert card["total_issued"] == 2.4
    assert card["balance"] == 97.6                     # ١٠٠ مضاف − ٢٫٤ منصرف
    assert dw.item_balances(YEAR, MONTH, "supply")[item["id"]] == 97.6
    page = _page(client, f"/warehouses?cycle=supply&sub=wh3&item={item['id']}")
    assert "إذن صرف ٢ مخازن رقم ١" in page and "٩٧٫٦٠٠" in page


def test_issued_converts_to_handle_unit(client):
    _init()
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز بلدي", "كجم", 0, 0, 0)
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١", "handle_unit": "طن",
        "day": "١١"})
    dp.save_permit(YEAR, MONTH, {
        "number": 1, "fiscal_year": 2026, "date_from": 12, "date_to": 12,
        "issue_days": 1, "mode": "box", "entity_label": "", "officers": 0,
        "individuals": 10, "recruits": 0, "meals": ["lunch"],
        "record_ids": [1], "actuals": {"tamween_أرز بلدي": 100},
    })
    item = dw.list_items(YEAR, MONTH, "supply")[0]
    card = dw.item_card(YEAR, MONTH, item["id"])
    issue = next(r for r in card["rows"] if r["kind"] == "issue2")
    assert abs(issue["issued"] - 0.1) < 1e-9           # ١٠٠ كجم = ٠٫١ طن
    assert card["balance"] == 0.9


def test_weekday_name_column_and_live_hint(client):
    _init()
    _seed_ration_item()
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "٣", "day": "٢٥"})
    from datetime import date
    from core import egtime
    expected = egtime.weekday_ar(date(YEAR, MONTH, 25))
    page = _page(client, "/warehouses?cycle=supply&sub=wh1")
    assert expected in page and ">٢٥<" not in page     # الاسم بدل الرقم
    assert "wh-day-hint" in page                       # التلميح الحي في النموذج
    item = dw.list_items(YEAR, MONTH, "supply")[0]
    page = _page(client, f"/warehouses?cycle=supply&sub=wh3&item={item['id']}")
    assert expected in page


# ======================================================================
# القواعد العامة: كومبو متمثّم + طباعة رسمية + مرايا Excel + التنزيل
# ======================================================================
def test_themed_combos_no_native_selects_and_print_rule(client):
    _init()
    for sub in ("suppliers", "wh1", "wh2", "wh3"):
        page = _page(client, f"/warehouses?cycle=supply&sub={sub}")
        assert "<select" not in page, sub
        assert "js-print-page" in page, sub                     # زر الطباعة الرسمية
        assert "مستودعات وسجلات" in page, sub                   # عنوان الطباعة
    page = _page(client, "/warehouses?cycle=supply&sub=wh1")
    assert 'data-combo="whItemsList"' in page
    assert 'data-combo="whUnitsList"' in page
    assert "١ طن = ١٠٠٠ كجم" in page                            # تلميح التحويل في النموذج


def test_excel_mirrors_for_all_subtabs_and_download(client):
    _init()
    _post(client, "/warehouses/suppliers/add?cycle=supply",
          {"cycle": "supply", "name": "شركة المرايا"})
    _page(client, "/warehouses?cycle=supply")                   # فتح القسم يكتب المرايا
    for sub in ("suppliers", "wh1", "wh2", "wh3"):
        path = wf.file_path(YEAR, MONTH, "supply", sub)
        assert path.exists(), sub
    response = client.get("/warehouses/download/supply/suppliers")
    assert response.status_code == 200
    assert b"PK" in response.data[:4]                            # ملف إكسل حقيقي


# ======================================================================
# التغليف «مستوى واحد + سائب» + توزيع المخازن + التفريدة التلقائية FEFO
# ======================================================================
def test_packaging_auto_total_and_capacity_memory(client):
    _init()
    _seed_ration_item()
    # شكارة ٥٠ + ٣٠ سائب = ٨٠ كجم — الكمية تُحسب من التغليف لا من الحقل
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "٩٩٩",
        "day": "١", "pack_kind": "شكارة", "pack_count": "١",
        "pack_capacity": "٥٠", "pack_loose": "٣٠"})
    receipt = dw.list_receipts(YEAR, MONTH, "supply")[0]
    assert receipt["qty_handle"] == 80.0
    assert receipt["pack_capacity"] == 50.0
    # السعة ات حفظت للصنف — تظهر في خريطة التعبئة التلقائية
    specs = dw.pack_specs_map(YEAR, MONTH, "supply")
    assert specs["أرز بلدي"]["شكارة"] == 50.0
    page = _page(client, "/warehouses?cycle=supply&sub=wh1")
    assert "شكارة" in page and "٨٠٫٠٠٠" in page


def test_store_split_in_receipt_and_validation(client):
    _init()
    _seed_ration_item()
    db_stores_add = __import__("data_access.db_stores", fromlist=["add_store"])
    db_stores_add.add_store("مخزن الأرز", capacity_m2=120, fans=4, extractors=2)
    db_stores_add.add_store("مخزن الثلاجة", capacity_m2=60, fans=2, extractors=6)
    stores = __import__("data_access.db_stores", fromlist=["list_stores"]).list_stores()
    a, b = stores[0], stores[1]
    # التوزيع لا يطابق الكمية → يُرفض
    response = _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١٠٠", "day": "٣",
        "store_id": [str(a["id"]), str(b["id"])],
        "store_qty": ["٦٠", "٣٠"]}, follow=True)
    assert "لا يساوي كمية الإذن" in response.data.decode("utf-8")
    # توزيع صحيح ٦٠ + ٤٠
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١٠٠", "day": "٣",
        "store_id": [str(a["id"]), str(b["id"])],
        "store_qty": ["٦٠", "٤٠"]})
    receipt = dw.list_receipts(YEAR, MONTH, "supply")[0]
    assert [(p["store_name"], p["qty"]) for p in receipt["stores"]] == \
        [("مخزن الأرز", 60.0), ("مخزن الثلاجة", 40.0)]
    page = _page(client, "/warehouses?cycle=supply&sub=wh1")
    assert "مخزن الأرز (٦٠٫٠٠٠)" in page and "مخزن الثلاجة (٤٠٫٠٠٠)" in page


def test_tafreeda_fefo_nearest_expiry_first_then_older(client):
    _init()
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز بلدي", "كجم", 0, 0, 0)  # كجم لسهولة الحساب
    db_stores_add = __import__("data_access.db_stores", fromlist=["add_store"])
    db_stores_add.add_store("المخزن الرئيسي")
    store = __import__("data_access.db_stores", fromlist=["list_stores"]).list_stores()[0]
    # دفعة قديمة صلاحيتها أبعد (إذن ١) ثم دفعة أقرب صلاحية (إذن ٢) — كلها مخزن رئيسي
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "٥٠", "day": "١",
        "exp_date": "٠١/١٢/٢٠٢٦", "receipt_no": "١",
        "store_id": [str(store["id"])], "store_qty": ["٥٠"]})
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "٥٠", "day": "٢",
        "exp_date": "٠١/١٠/٢٠٢٦", "receipt_no": "٢",
        "store_id": [str(store["id"])], "store_qty": ["٥٠"]})
    # إذن صرف ٥٥ كجم: الأقرب صلاحية (إذن ٢) ٥٠ ثم ٥ من الدفعة التالية أقرب صلاحية (إذن ٣)
    dp.save_permit(YEAR, MONTH, {
        "number": 1, "fiscal_year": 2026, "date_from": 5, "date_to": 5,
        "issue_days": 1, "mode": "box", "entity_label": "جهة", "officers": 0,
        "individuals": 11, "recruits": 0, "meals": ["lunch"],
        "record_ids": [1], "actuals": {"tamween_أرز بلدي": 55}})
    # دفعتان بنفس الصلاحية كلتاهما متاحة ⇒ الأقدم إضافةً (الأبعد في الإضافة) أولًا
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١٠", "day": "٣",
        "exp_date": "٠١/١٠/٢٠٢٦", "receipt_no": "٣",
        "store_id": [str(store["id"])], "store_qty": ["١٠"]})
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١٠", "day": "٤",
        "exp_date": "٠١/١٠/٢٠٢٦", "receipt_no": "٤",
        "store_id": [str(store["id"])], "store_qty": ["١٠"]})
    dp.save_permit(YEAR, MONTH, {
        "number": 2, "fiscal_year": 2026, "date_from": 6, "date_to": 6,
        "issue_days": 1, "mode": "box", "entity_label": "", "officers": 0,
        "individuals": 5, "recruits": 0, "meals": ["lunch"],
        "record_ids": [1], "actuals": {"tamween_أرز بلدي": 15}})
    rows = dw.tafreeda_rows(YEAR, MONTH, "supply")
    rows1 = [r for r in rows if r["permit_no"] == 1]
    assert len(rows1) == 2
    assert rows1[0]["receipt_serial"] == 2 and rows1[0]["qty"] == 50.0  # الأقرب صلاحية
    assert rows1[1]["receipt_serial"] == 3 and rows1[1]["qty"] == 5.0
    assert rows1[0]["store_name"] == "المخزن الرئيسي"
    rows2 = [r for r in rows if r["permit_no"] == 2]
    assert rows2[0]["receipt_serial"] == 3 and rows2[0]["qty"] == 5.0   # بقايا الأقدم إضافةً أولًا
    assert rows2[1]["receipt_serial"] == 4 and rows2[1]["qty"] == 10.0
    # التفريدة ظاهرة في دفتر ٢ مخازن
    page = _page(client, "/warehouses?cycle=supply&sub=wh2")
    assert "التفريدة التلقائية من المخازن" in page and "المخزن الرئيسي" in page


def test_stores_page_tabs_and_unified_cycles(client):
    _init()
    _seed_ration_item()
    db_stores_add = __import__("data_access.db_stores", fromlist=["add_store"])
    db_stores_add.add_store("مخزن موحد", capacity_m2=100, fans=2, extractors=1)
    store = __import__("data_access.db_stores", fromlist=["list_stores"]).list_stores()[0]
    # إضافة من دورة الإمداد + صنف من دورة المتعهد في نفس المخزن
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "٤٠", "day": "٤",
        "store_id": [str(store["id"])], "store_qty": ["٤٠"]})
    dr.add_item(YEAR, MONTH, "contractor", "summer", "سكر", "كجم", 0, 0, 0)
    _post(client, "/warehouses/wh1/add?cycle=contractor", {
        "cycle": "contractor", "item_name": "سكر", "qty": "٢٥", "day": "٤",
        "store_id": [str(store["id"])], "store_qty": ["٢٥"]})
    page = _page(client, "/stores?tab=movement")
    assert "مخزن موحد" in page and "أرز بلدي" in page and "سكر" in page
    assert "كشف أرصدة المخزن" in page
    assert "٤٠٫٠٠٠" in page and "٢٥٫٠٠٠" in page
    # تحويل القسم من الشريط
    response = client.get("/sections/cold_stores", follow_redirects=True)
    assert "المخازن والثلاجات" in response.data.decode("utf-8")
    # زر الطباعة وممنوع select
    assert "js-print-page" in page and "<select" not in page
    # مرايا الإكسل
    from services import stores_fs as sf
    assert sf.file_path(YEAR, MONTH, "mains").exists()
    assert sf.file_path(YEAR, MONTH, "movement").exists()


def test_store_registry_crud_rules(client):
    _init()
    _post(client, "/stores/save", {
        "name": "مخزن الشفاطات", "location": "الدور الثاني", "capacity_m2": "٩٠",
        "fans": "٦", "extractors": "٣", "equipment": "رفوف حديد، ميزان"})
    page = _page(client, "/stores?tab=mains")
    assert "مخزن الشفاطات" in page and "الدور الثاني" in page and "رفوف حديد" in page
    store = __import__("data_access.db_stores", fromlist=["list_stores"]).list_stores()[0]
    assert store["fans"] == 6 and store["extractors"] == 3 and store["capacity_m2"] == 90.0
    _post(client, "/stores/save", {
        "store_id": store["id"], "name": "مخزن الشفاطات المعدل", "location": "",
        "capacity_m2": "", "fans": "", "extractors": "", "equipment": "", "notes": ""})
    assert __import__("data_access.db_stores", fromlist=["list_stores"]).list_stores()[0]["name"] == "مخزن الشفاطات المعدل"
    _post(client, "/stores/delete", {"store_id": store["id"]})
    assert __import__("data_access.db_stores", fromlist=["list_stores"]).list_stores() == []

# ======================================================================
# قواعد جولة ٢٦/٠٩: أرقام التغليف المقصوصة + رصيد أول المدة الكامل + حذف المخازن
# ======================================================================
def test_pack_label_integers_stay_integers_fractions_show_fractions():
    from data_access.db_warehouses import pack_summary
    label, total = pack_summary("شكارة", 19, 50, 50, "كجم")
    assert label == "١٩ شكارة × ٥٠ كجم + ٥٠ كجم سائب = ١٠٠٠ كجم" and total == 1000.0
    label, total = pack_summary("بلاتة", 2, 12.5, 0, "كجم")
    assert "١٢٫٥ كجم" in label and "= ٢٥ كجم" in label and total == 25.0
    label, _ = pack_summary("كرتونة", 3, 0.66, 0, "لتر")
    assert "٠٫٦٦ لتر" in label


def test_opener_full_fields_splits_and_expiry_drive_fefo(client):
    _init()
    db_stores_add = __import__("data_access.db_stores", fromlist=["add_store"])
    db_stores_add.add_store("مخزن أ")
    db_stores_add.add_store("مخزن ب")
    stores = __import__("data_access.db_stores", fromlist=["list_stores"]).list_stores()
    a, b = stores[0], stores[1]
    dr.add_item(YEAR, MONTH, "tamween", "summer", "سكر أبيض", "كجم", 0, 0, 0)
    # رصيد أول المدة بتوزيع ٣٠/٢٠ وصلاحية قريبة — يُصرف أولًا رغم أنه أقدم إضافةً
    _post(client, "/warehouses/wh3/opener?cycle=supply", {
        "cycle": "supply", "item_name": "سكر أبيض", "qty": "٥٠", "day": "١",
        "producer": "حوانيت", "supplier_name": "مورد قديم",
        "prod_date": "٠١/٠١/٢٠٢٦", "exp_date": "٠١/١١/٢٠٢٦",
        "store_id": [str(a["id"]), str(b["id"])], "store_qty": ["٣٠", "٢٠"]})
    # إذن إضافة بلا صلاحية — أحدث خزينًا لكن صلاحيته أبعد
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "سكر أبيض", "qty": "٤٠", "day": "٢",
        "receipt_no": "١", "store_id": [str(a["id"])], "store_qty": ["٤٠"]})
    rows = dw.tafreeda_rows(YEAR, MONTH, "supply")
    dp.save_permit(YEAR, MONTH, {
        "number": 1, "fiscal_year": 2026, "date_from": 5, "date_to": 5,
        "issue_days": 1, "mode": "box", "entity_label": "جهة", "officers": 0,
        "individuals": 10, "recruits": 0, "meals": ["lunch"],
        "record_ids": [1], "actuals": {"tamween_سكر أبيض": 55}})
    rows = dw.tafreeda_rows(YEAR, MONTH, "supply")
    assert rows[0]["receipt_serial"] == 0 and rows[0]["qty"] == 30.0   # الرصيد أولًا: أقرب صلاحية
    assert rows[0]["store_name"] == "مخزن أ"
    assert rows[1]["receipt_serial"] == 0 and rows[1]["qty"] == 20.0 and rows[1]["store_name"] == "مخزن ب"
    assert rows[2]["receipt_serial"] == 1 and rows[2]["qty"] == 5.0    # ثم إذن الإضافة
    # مجموع لا يطابق → رفض
    response = _post(client, "/warehouses/wh3/opener?cycle=supply", {
        "cycle": "supply", "item_name": "شاي فتلة", "qty": "١٠", "day": "١",
        "store_id": [str(a["id"])], "store_qty": ["٧"]}, follow=True)
    assert "لا يساوي كمية رصيد أول المدة" in response.data.decode("utf-8")
    # صلاحية قبل إنتاج → رفض
    response = _post(client, "/warehouses/wh3/opener?cycle=supply", {
        "cycle": "supply", "item_name": "شاي فتلة", "qty": "١٠", "day": "١",
        "prod_date": "٠١/٠٦/٢٠٢٦", "exp_date": "٠١/٠١/٢٠٢٦"}, follow=True)
    assert "قبل تاريخ الإنتاج" in response.data.decode("utf-8")


def test_store_with_movement_cannot_delete_without_transfer(client):
    _init()
    db_stores_add = __import__("data_access.db_stores", fromlist=["add_store"])
    db_stores_add.add_store("مخزن الحذف")
    db_stores_add.add_store("مخزن الوجهة")
    stores = __import__("data_access.db_stores", fromlist=["list_stores"]).list_stores()
    victim, dest = stores[0], stores[1]
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز بلدي", "كجم", 0, 0, 0)
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "cycle": "supply", "item_name": "أرز بلدي", "qty": "١٠٠", "day": "٢",
        "receipt_no": "١", "store_id": [str(victim["id"])], "store_qty": ["١٠٠"]})
    # بلا نقل → مرفوض
    response = _post(client, "/stores/delete", {"store_id": str(victim["id"])}, follow=True)
    assert "ممنوع حذف" in response.data.decode("utf-8")
    # بالنقل → يُحذف وتنتقل التوزيعات (والاسم يُعاد تسميته في الحركة)
    response = _post(client, "/stores/delete",
                     {"store_id": str(victim["id"]), "transfer_to": str(dest["id"])},
                     follow=True)
    assert "ونُقلت أصنافه" in response.data.decode("utf-8")
    remaining = __import__("data_access.db_stores", fromlist=["list_stores"]).list_stores()
    assert [st["id"] for st in remaining] == [dest["id"]]
    splits = dw.list_receipts(YEAR, MONTH, "supply")[0]["stores"]
    assert splits[0]["store_id"] == dest["id"] and splits[0]["qty"] == 100.0
    # الوجهة ورثت الحركة → صارت هي الأخرى محمية من الحذف
    response = _post(client, "/stores/delete", {"store_id": str(dest["id"])}, follow=True)
    assert "ممنوع حذف" in response.data.decode("utf-8")
