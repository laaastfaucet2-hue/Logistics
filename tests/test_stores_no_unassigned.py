# -*- coding: utf-8 -*-
"""مفيش «غير موزع» (قرار المستخدم ١٤/١٠): أي كمية من غير توزيع تدخل على «مخزن 1».

«مخزن 1» = أول مخزن في سجل المخازن. الإذن الجديد يتوزع عليه وقت الحفظ، والقديم
بيتنقل له في كل الشهور. واتشال تبويب «غير موزع» من صفحة المخازن ومجلده، ومن الإحصائيات
(التبويب ٨ بقى «التنبيهات»). كل البيانات في مجلد مؤقت (conftest).
"""
from datetime import date

from data_access import db_rations as dr
from data_access import db_stores
from data_access import db_warehouses as dw
from data_access import db_warehouses_stores as dws
from data_access import months

YEAR, MONTH = 2031, 9
TODAY = date(2031, 9, 15)


def _rice(month=MONTH):
    months.init_month(YEAR, month)
    dr.add_item(YEAR, month, "tamween", "summer", "أرز", "كجم", 0, 0, 0)
    dr.add_item(YEAR, month, "tamween", "summer", "عدس", "كجم", 0, 0, 0)


def test_receipt_and_opener_without_distribution_go_to_store_one(app):
    _rice()
    db_stores.add_store("مخزن 1")
    db_stores.add_store("ثلاجة 2")
    first = db_stores.list_stores()[0]
    dw.add_receipt(YEAR, MONTH, "supply", 1, "أرز", 40, "كجم", date_iso="2031-09-01")
    dw.add_receipt(YEAR, MONTH, "supply", 1, "أرز", 5, "كجم", date_iso="2031-09-01",
                   stores=[(0, "مخزن مش في السجل", 5)])
    dw.add_opener(YEAR, MONTH, "supply", "عدس", 12, 1, handle_unit_hint="كجم",
                  exp_iso="2032-01-01", date_iso="2031-09-01")
    for receipt in dw.list_receipts(YEAR, MONTH, "supply"):
        assert [(p["store_id"], p["qty"]) for p in receipt["stores"]] == \
            [(first["id"], receipt["qty_handle"])]
    openers = [p for parts in dw.opener_stores(YEAR, MONTH, "supply").values() for p in parts]
    assert [(p["store_id"], p["qty"]) for p in openers] == [(first["id"], 12.0)]
    report = dw.stores_report(YEAR, MONTH)
    assert not report["unassigned"]["inn"] and not report["unassigned"]["out"]
    one = next(t for t in report["stores"] if t["store"]["id"] == first["id"])
    assert one["balances"] == {"أرز": 45.0, "عدس": 12.0}


def test_old_unassigned_quantities_move_to_store_one_in_every_month(app, client):
    for month in (8, 9):
        _rice(month)
        dw.add_receipt(YEAR, month, "supply", 1, "أرز", 30, "كجم",
                       date_iso=f"{YEAR}-{month:02d}-01")
    assert dw.stores_report(YEAR, 8)["unassigned"]["inn"]          # السجل فاضي ⇒ مستنية
    assert client.post("/stores/save", data={"name": "مخزن الأرز"}).status_code == 302
    for month in (8, 9):
        report = dw.stores_report(YEAR, month)
        assert not report["unassigned"]["inn"], month
        assert report["stores"][0]["balances"] == {"أرز": 30.0}, month
    # توزيع على مخزن اتشال من السجل ⇒ «مخزن 1» برضه
    db_stores.add_store("مخزن مؤقت")
    temp = db_stores.list_stores()[1]
    dw.add_receipt(YEAR, MONTH, "supply", 2, "أرز", 7, "كجم", date_iso="2031-09-02",
                   receipt_no=2, stores=[(temp["id"], temp["name"], 7)])
    db_stores.delete_store(temp["id"])
    assert dws.assign_unassigned() == 1
    assert dw.stores_report(YEAR, MONTH)["stores"][0]["balances"] == {"أرز": 37.0}
    assert dws.assign_unassigned() == 0


def test_stores_page_and_files_have_no_unassigned_tab_or_folder(app, client):
    from services import stores_fs
    _rice()
    db_stores.add_store("مخزن 1")
    dw.add_receipt(YEAR, MONTH, "supply", 1, "أرز", 20, "كجم", date_iso="2031-09-01")
    legacy = stores_fs.base_dir(YEAR, MONTH) / dws.UNASSIGNED
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "قديم.xlsx").write_bytes(b"old")
    response = client.get("/stores/?tab=mains&store=0")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "غير موزع" not in page and "مخزن 1" in page and "أرز" in page
    assert not legacy.exists()
    folders = {p.name for p in stores_fs.base_dir(YEAR, MONTH).iterdir() if p.is_dir()}
    assert folders == {"سجل المخازن", "مخزن 1"}
    assert client.get("/stores/open-folder-store/0/movement").status_code == 404


def test_stats_have_no_unassigned_and_alerts_tab_is_renamed(app, client):
    from services import stats_stores as ss
    from services.stats_stores import files
    _rice()
    db_stores.add_store("مخزن 1")
    store = db_stores.list_stores()[0]
    dw.add_receipt(YEAR, MONTH, "supply", 1, "أرز", 20, "كجم", exp_iso="2031-12-01",
                   date_iso="2031-09-01")
    legacy = files.root(YEAR, MONTH) / "8. التنبيهات وغير الموزع"
    legacy.mkdir(parents=True, exist_ok=True)
    for sub in ("summary", "balances", "alerts", "compare"):
        for scope in ("month", "year"):
            page = client.get(f"/stats/?cycle=supply&tab=stores&sub={sub}&scope={scope}"
                              ).get_data(as_text=True)
            assert "غير موزع" not in page and "غير الموزع" not in page, (sub, scope)
    assert ss.folder_name("alerts") == "8. التنبيهات"
    assert files.tab_file("alerts", YEAR, MONTH).name == "التنبيهات — سبتمبر ٢٠٣١.xlsx"
    ss.refresh_now(YEAR, MONTH)
    assert not legacy.exists() and files.tab_file("alerts", YEAR, MONTH).exists()
    balances = ss.build_view("balances", YEAR, MONTH, "month", today=TODAY)
    assert [t["key"] for t in balances["tables"]] == ["total", f"store_{store['id']}"]
