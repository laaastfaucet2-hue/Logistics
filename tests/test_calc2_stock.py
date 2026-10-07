# -*- coding: utf-8 -*-
"""ربط آلة حاسبة ٢ مخازن بالمخازن — «الرصيد المتوفر» و«الحالة الكلية للرصيد».

توجيه ٠٦/١٠/٢٠٢٦: العمودان كانا «قيد التطوير»؛ والاختبارات هنا تُثبت:
الرصيد يُقرأ من المخازن فعلًا · الحالة ثلاث حالات بحد من `core.config.STOCK_LOW_RATIO` ·
التغليف يظهر مع الوحدة · وإعادة الحفظ بنفس رقم الإذن = استبدال لا خصم مزدوج.
"""
from core import arabic_numbers as arnum
from core.config import STOCK_LOW_RATIO
from data_access import db_permits as dp, db_rations as dr
from data_access import db_warehouses as dw, months
from services import stock_link as sl

YEAR, MONTH = 2031, 9


def _init():
    months.init_month(YEAR, MONTH)


def _catalog_item(name, unit="كجم", section="tamween"):
    dr.add_item(YEAR, MONTH, section, "summer", name, unit, 0, 0.1, 0)
    dr.set_activation(YEAR, MONTH, section, "summer")
    return name


# ======================================================================
# ١) الحالة الكلية — الثلاث حالات والحد من الإعدادات
# ======================================================================
def test_status_three_states_and_threshold_from_config(app):
    _init()
    assert sl.status_of(0, 10) == sl.STATUS_NONE            # صفر ⇒ لا يوجد
    assert sl.status_of(100, 10) == sl.STATUS_SAFE          # فائض كبير ⇒ آمن
    low = 10 * (1 + STOCK_LOW_RATIO) - 0.001                # المتبقي أقل من الحد
    assert sl.status_of(low, 10) == sl.STATUS_LOW
    assert sl.status_of(10 * (1 + STOCK_LOW_RATIO), 10) == sl.STATUS_SAFE
    assert sl.STATUS_KEYS == {"آمن": "safe", "يوشك على النفاذ": "low", "لا يوجد": "none"}


def test_status_without_need_is_safe_when_stock_exists(app):
    _init()
    assert sl.status_of(5, 0) == sl.STATUS_SAFE             # رصيد بلا احتياج ⇒ آمن
    assert sl.status_of(0, 0) == sl.STATUS_NONE             # لا رصيد ولا احتياج ⇒ لا يوجد


# ======================================================================
# ٢) الرصيد يُقرأ من المخازن + التغليف + المتبقي بعد الإذن
# ======================================================================
def test_availability_reads_warehouse_balance_and_pack(app):
    _init()
    name = _catalog_item("أرز بلدي")
    dw.add_opener(YEAR, MONTH, "supply", name, 170, 1, handle_unit_hint="كجم", exp_iso="2027-06-30",
                  pack_kind="شكارة", pack_count=3, pack_capacity=50, pack_loose=20)
    info = sl.availability(YEAR, MONTH, "supply", name, needed=20)
    assert info["avail"] == 170 and info["unit"] == "كجم"
    assert info["remaining"] == 150 and info["status"] == sl.STATUS_SAFE
    assert "شكارة" in info["pack"]                          # الرصيد بالتغليف ظاهر
    assert info["remaining_text"] == arnum.fmt_qty_trim(150)


def test_availability_reflects_permits_deduction(app):
    """الرصيد المعلن هو رصيد المخزن نفسه (بعد خصم الأذون) — لا رقم محفوظ منفصل."""
    _init()
    name = _catalog_item("سكر")
    dw.add_opener(YEAR, MONTH, "supply", name, 100, 1, handle_unit_hint="كجم", exp_iso="2027-06-30")
    dp.save_permit(YEAR, MONTH, {
        "number": 7, "fiscal_year": 2026, "date_from": 1, "date_to": 1, "issue_days": 1,
        "mode": "box", "entity_label": "جهة", "officers": 0, "individuals": 0, "recruits": 0,
        "actuals": {"tamween_" + name: 40},
    })
    info = sl.availability(YEAR, MONTH, "supply", name, needed=10)
    assert info["avail"] == 60                              # ١٠٠ − ٤٠ (خصم الإذن)
    assert info["status"] == sl.STATUS_SAFE


def test_saving_same_permit_number_replaces_actuals_without_double_deduction(app):
    _init()
    name = _catalog_item("زيت")
    dw.add_opener(YEAR, MONTH, "supply", name, 100, 1, handle_unit_hint="كجم", exp_iso="2027-06-30")
    base = {"number": 9, "fiscal_year": 2026, "date_from": 1, "date_to": 1,
            "issue_days": 1, "mode": "box", "entity_label": "جهة",
            "officers": 0, "individuals": 0, "recruits": 0}
    dp.save_permit(YEAR, MONTH, {**base, "actuals": {"tamween_" + name: 30}})
    assert sl.availability(YEAR, MONTH, "supply", name)["avail"] == 70
    dp.save_permit(YEAR, MONTH, {**base, "actuals": {"tamween_" + name: 50}})   # «تحديث الإذن»
    assert sl.availability(YEAR, MONTH, "supply", name)["avail"] == 50         # ٥٠ لا ٢٠


def test_for_rows_maps_every_row_by_name(app):
    _init()
    a, b = _catalog_item("فول"), _catalog_item("مكرونة", unit="كيس")
    dw.add_opener(YEAR, MONTH, "supply", a, 30, 1, handle_unit_hint="كجم", exp_iso="2027-06-30")
    data = sl.for_rows(YEAR, MONTH, "tamween", [
        {"name": a, "auto": 100}, {"name": b, "auto": 5}, {"name": "صنف غير موجود", "auto": 1}])
    assert data[a]["status"] == sl.STATUS_LOW               # ٣٠ والمطلوب ١٠٠
    assert data[b]["status"] == sl.STATUS_NONE              # لا رصيد
    assert data["صنف غير موجود"]["avail"] == 0
    assert sl.totals(data)[sl.STATUS_NONE] == 2


# ======================================================================
# ٣) المسار: /calc2/stock وواجهة الصفحة
# ======================================================================
def test_stock_route_returns_items_and_totals(client):
    _init()
    name = _catalog_item("جبنة", unit="علبة")
    dw.add_opener(YEAR, MONTH, "supply", name, 40, 1, handle_unit_hint="علبة", exp_iso="2027-06-30")
    body = client.get(f"/calc2/stock?section=tamween&items={name}:10").get_json()
    assert body["section"] == "tamween"
    assert body["items"][name]["avail"] == 40 and body["items"][name]["status"] == sl.STATUS_SAFE
    assert body["totals"][sl.STATUS_SAFE] == 1


def test_stock_route_rejects_unknown_section(client):
    _init()
    response = client.get("/calc2/stock?section=unknown&items=أرز:1")
    assert response.status_code == 400 and response.get_json()["error"]


def test_calc2_page_shows_live_balance_columns(client):
    from data_access import db_tameedat as dt
    _init()
    name = _catalog_item("شاي")
    dw.add_opener(YEAR, MONTH, "supply", name, 25, 1, handle_unit_hint="كجم", exp_iso="2027-06-30")
    eid = dt.add_entity(YEAR, MONTH, "قطاع اختبار الربط", "شرطية")
    rid = dt.add_record(YEAR, MONTH, 1, dt.get_entity(YEAR, MONTH, eid), 10, 10, 0, "", [])
    page = client.get(f"/calc2?from=1&to=1&selected=main:{rid}").data.decode("utf-8")
    assert "الرصيد المتوفر بالمخازن" in page and "الحالة الكلية للرصيد" in page
    assert "قيد التطوير" not in page                        # شيلت من العمودين
    assert "بعد الإذن" in page and "c2-stock-legend" in page
    assert "/calc2/stock" in page                           # الجافاسكربت يعرف المسار
    assert "بدون خصم مزدوج" in page                         # زر تحديث الإذن
