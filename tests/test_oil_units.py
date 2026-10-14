# -*- coding: utf-8 -*-
"""الزيت بالكيلو + التغليف المتداخل (كرتونة + زجاجة/علبة) + FEFO والعجز — توجيه ١٠/١٠.

- الزيت: الكمية المادية بالتر، والدفتر/الحاسبة/العجز بكجم (الوزن النوعي ٠٫٩١٤).
- كل الأصناف الأخرى: وحدة الدفتر = وحدة التعامل التي أُضيف بها الصنف.
- رقم إذن ١ مخازن خارجي — **مطلوب** عند الإضافة.
- الشركة المنتجة: لكل كارت صنف (فاضي = شركة منتج الإذن).
"""
import re

import pytest

from data_access import db_warehouses as dw
from data_access import db_warehouses_stores as dws
from data_access import db_permits as dp
from data_access import db_rations as dr
from data_access import db_stores
from data_access import oil_units as ou

YEAR, MONTH = 2031, 9


def _page(client, url):
    r = client.get(url)
    assert r.status_code == 200, (url, r.status_code)
    return r.data.decode("utf-8")


def _post(client, url, data):
    r = client.post(url, data=data, follow_redirects=True)
    assert r.status_code == 200, (url, r.status_code)
    return r.data.decode("utf-8")


def _init(client):
    db_stores.add_store("المخزن الرئيسي")
    return db_stores.list_stores()[0]


# ── التحويلات وثوابت المقررات (مستوى الوحدة) ─────────────────────────────
def test_oil_conversions_and_constants():
    assert ou.is_oil("زيت الطعام") and ou.is_oil("زيت طعام")
    assert not ou.is_oil("صلصة") and not ou.is_oil("سكر")
    assert ou.liter_to_kg(12) == 10.968          # ١٢ لتر × ٠٫٩١٤
    assert ou.kg_to_liter(1.2) == pytest.approx(1.2 / 0.914, abs=1e-6)
    assert ou.ration_kg("summer") == 0.012
    assert ou.ration_kg("winter") == 0.015
    assert ou.day_total_kg("summer", 100) == 1.2
    assert ou.day_total_kg("winter", 100) == 1.5
    # وحدة الدفتر: الزيت كجم (بالوزن النوعي) · الباقي وحدة التعامل
    assert ou.ledger_unit("زيت طعام", "كجم", "لتر", 914) == ("كجم", 0.914)
    assert ou.ledger_unit("زيت طعام", "كجم", "لتر", None) == ("كجم", 0.914)  # افتراضي
    assert ou.ledger_unit("زيت طعام", "كجم", "كجم", None) == ("كجم", 1.0)    # التعامل كجم = جسر ١
    # باقي الأصناف: وحدة الدفتر هي وحدة التعامل نفسها دون تحويل إلى جم/مل
    assert ou.ledger_unit("صلصة", "كجم", "كجم", None) == ("كجم", 1.0)
    assert ou.ledger_unit("حليب", "مل", "مل", None) == ("مل", 1.0)
    assert ou.calc_unit("زيت طعام", "كجم") == ("كجم", 1.0)   # الزيت: الكجم زي ما هو
    assert ou.calc_unit("زيت طعام", "لتر") == ("كجم", 0.914)  # اللتر يتحول بكثافة الزيت
    assert ou.calc_unit("حليب", "مل") == ("مل", 1.0)


def test_warehouse_item_name_starting_with_oil_uses_oil_rule(client):
    """كل اسم يبدأ بكلمة «زيت» يخضع لقاعدة الزيت، حتى إن لم يكن في القائمة الثابتة."""
    store = _init(client)
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "receipt_no": "1", "day": "1", "l0_item_name": "زيت شوفان",
        "l0_handle_unit": "كجم", "l0_qty": "5", "l0_pack_kind": "بدون تغليف"})
    items = {i["name"]: i for i in dw.list_items(YEAR, MONTH, "supply")}
    f_unit, factor = dw.ou.ledger_unit(
        items["زيت شوفان"]["name"], items["زيت شوفان"]["ration_unit"],
        items["زيت شوفان"]["handle_unit"], items["زيت شوفان"].get("specific_weight"))
    assert (f_unit, factor) == ("كجم", 1.0)      # وحدة التعامل كجم والجسر ١


# ── رقم الإذن المطلوب + المنتج لكل صنف ────────────────────────────────────
def test_wh1_receipt_no_required(client):
    store = _init(client)
    page = _post(client, "/warehouses/wh1/add?cycle=supply", {
        "day": "1", "supplier_name": "مورد",
        "l0_item_name": "أرز", "l0_handle_unit": "كجم", "l0_qty": "10"})
    assert "أدخل رقم الإذن" in page
    assert dw.list_receipts(YEAR, MONTH, "supply") == []   # مفيش حفظ بدونه


def test_wh1_per_line_producer_and_fallback(client):
    store = _init(client)
    page = _post(client, "/warehouses/wh1/add?cycle=supply", {
        "receipt_no": "7", "day": "1", "supplier_name": "مورد", "producer": "شركة الإذن",
        "l0_item_name": "أرز", "l0_handle_unit": "كجم", "l0_qty": "10",
        "l0_pack_kind": "بدون تغليف", "l0_producer": "",          # فاضي = شركة الإذن
        "l1_item_name": "سكر", "l1_handle_unit": "كجم", "l1_qty": "5",
        "l1_pack_kind": "بدون تغليف", "l1_producer": "شركة السكر"})
    assert "7" in page or "٧" in page
    recs = dw.list_receipts(YEAR, MONTH, "supply")
    by_item = {r["item_name"] if "item_name" in r else None: r for r in recs}
    lines = dw.receipt_groups(YEAR, MONTH, "supply")
    prods = {ln["item_name"]: ln.get("producer") for g in lines for ln in g["lines"]}
    assert prods["أرز"] == "شركة الإذن"        # الفولباك شغل
    assert prods["سكر"] == "شركة السكر"


# ── التغليف العام: كرتونة + نوع عبوة (زجاجة/علبة) ────────────────────────
def test_pack_carton_with_bottle_inner(client):
    store = _init(client)
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "receipt_no": "1", "day": "1", "supplier_name": "مورد", "producer": "منتج",
        "l0_item_name": "زيت طعام", "l0_handle_unit": "لتر", "l0_qty": "12",
        "l0_pack_kind": "كرتونة", "l0_pack_count": "1",
        "l0_pack_inner_kind": "زجاجة", "l0_pack_inner_count": "12",
        "l0_pack_inner_capacity": "1"})
    r = dw.list_receipts(YEAR, MONTH, "supply")[0]
    assert r["qty_handle"] == 12.0
    assert "١ كرتونة" in r["pack_label"] and "١٢ زجاجة" in r["pack_label"]
    assert r["pack_inner_kind"] == "زجاجة"
    # الكارت: ١٢ لتر × ٠٫٩١٤ = ١٠٫٩٦٨ كجم (بيعرض على قريبن = ١٠٫٩٧٠)
    page = _page(client, "/warehouses?cycle=supply&sub=wh3&item=1")
    assert "١٠٫٩٦٨" in page and "كجم" in page   # ١٢ لتر × ٠٫٩١٤ = ١٠٫٩٦٨ (قاعدة ١٠/١٠: 3 خانات)
    assert "وحدة الدفتر: كجم" in re.sub(r"<[^>]+>", "", page)


def test_pack_carton_plain_capacity(client):
    store = _init(client)
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "receipt_no": "2", "day": "1",
        "l0_item_name": "صلصة", "l0_handle_unit": "كجم", "l0_qty": "12",
        "l0_pack_kind": "كرتونة", "l0_pack_count": "1", "l0_pack_capacity": "12"})
    r = [x for x in dw.list_receipts(YEAR, MONTH, "supply")
         if x.get("item_name") or x["qty_handle"] == 12.0]
    rec = dw.list_receipts(YEAR, MONTH, "supply")[-1]
    assert "١٢ كجم" in rec["pack_label"]
    # صنف غير زيت: وحدة الدفتر هي وحدة التعامل نفسها
    card = dw.item_card(YEAR, MONTH, [i for i in dw.list_items(YEAR, MONTH, "supply")
                                      if i["name"] == "صلصة"][0]["id"])
    assert card["unit_disp"] == "كجم"
    assert card["total_added_d"] == 12.0


# ── FEFO + العجز: الزيت كجم في الحاسبة، لتر في التفريد المادي ─────────────
def _oil_setup(client):
    store = _init(client)
    dr.add_item(YEAR, MONTH, "tamween", "summer", "زيت طعام", "كجم", 0, 0.012, 0)
    dr.add_item(YEAR, MONTH, "tamween", "summer", "صلصة", "كجم", 0, 0.02, 0)
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "receipt_no": "1", "day": "1", "supplier_name": "مورد",
        "l0_item_name": "زيت طعام", "l0_handle_unit": "لتر", "l0_qty": "12",
        "l0_pack_kind": "كرتونة", "l0_pack_count": "1",
        "l0_pack_inner_kind": "زجاجة", "l0_pack_inner_count": "12",
        "l0_pack_inner_capacity": "1"})
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "receipt_no": "2", "day": "1",
        "l0_item_name": "صلصة", "l0_handle_unit": "كجم", "l0_qty": "12",
        "l0_pack_kind": "كرتونة", "l0_pack_count": "1", "l0_pack_capacity": "12"})
    return store


def test_fefo_oil_kg_to_liters_no_shortfall(client):
    store = _oil_setup(client)
    # ١٠٠ مجند × ٠٫٠١٢ = ١٫٢ كجم ⇒ المادي: ١٫٢ ÷ ٠٫٩١٤ = ١٫٣١٩١٠ لتر
    dp.save_permit(YEAR, MONTH, {
        "number": 1, "fiscal_year": 2031, "date_from": 5, "date_to": 5,
        "issue_days": 1, "mode": "box", "entity_label": "الوحدة", "officers": 0,
        "individuals": 0, "recruits": 100, "meals": ["lunch"],
        # الزيت والصلصة في الحاسبة بوحدة الإضافة (كجم)
        "record_ids": [], "actuals": {"tamween_زيت طعام": 1.2, "tamween_صلصة": 2}})
    rows = dws.tafreeda_rows(YEAR, MONTH, "supply")
    oil = [r for r in rows if r["item"] == "زيت طعام"]
    sauce = [r for r in rows if r["item"] == "صلصة"]
    assert len(oil) == 1 and oil[0]["unit"] == "لتر"
    assert oil[0]["qty"] == pytest.approx(1.2 / 0.914, abs=1e-5)
    assert sauce[0]["qty"] == 2.0 and sauce[0]["unit"] == "كجم"
    # الدفتر: المنصرف بالكجم — مفيش عجز
    oil_item = [i for i in dw.list_items(YEAR, MONTH, "supply") if i["name"] == "زيت طعام"][0]
    card = dw.item_card(YEAR, MONTH, oil_item["id"])
    issued_rows = [r for r in card["rows"] if r["kind"] == "issue2"]
    assert issued_rows[0]["issued_d"] == 1.2
    assert "عجز" not in issued_rows[0]["notes"]
    # الرصيد بعد الصرف: ١٢ − ١٫٣١٢٩١٠ = ١٠٫٦٨٧٠٩ لتر = ٩٫٧٦٣٦ كجم
    assert card["balance_d"] == pytest.approx((12 - 1.2 / 0.914) * 0.914, abs=0.01)  # قريبن على ٢


def test_fefo_oil_shortfall_when_need_exceeds_stock(client):
    store = _oil_setup(client)
    # إذن أكبر من الرصيد (١٢٠ كجم) — المادي كله ١٢ لتر ⇒ عجز واضح
    dp.save_permit(YEAR, MONTH, {
        "number": 1, "fiscal_year": 2031, "date_from": 5, "date_to": 5,
        "issue_days": 1, "mode": "box", "entity_label": "الوحدة", "officers": 0,
        "individuals": 0, "recruits": 13000, "meals": ["lunch"],
        "record_ids": [], "actuals": {"tamween_زيت طعام": 120}})
    rows = dws.tafreeda_rows(YEAR, MONTH, "supply")
    oil = [r for r in rows if r["item"] == "زيت طعام"]
    assert oil[0]["qty"] == 12.0                    # كل اللي في المخزن
    oil_item = [i for i in dw.list_items(YEAR, MONTH, "supply") if i["name"] == "زيت طعام"][0]
    card = dw.item_card(YEAR, MONTH, oil_item["id"])
    issued = [r for r in card["rows"] if r["kind"] == "issue2"][0]
    # عجز = ١٢ − ١٢×٠٫٩١ = ١٠٫٠٣٢ كجم
    assert "عجز: ١٠٩٫٠٣٢" in issued["notes"]
    assert "اتصرف ١٠٫٩٦٨ من ١٢٠٫٠٠٠" in issued["notes"]
