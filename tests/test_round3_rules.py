# -*- coding: utf-8 -*-
"""قاعدة التقريب الموحدة (توجيه ١٠/١٠) — على كل أصناف المتعهد والإمداد:

1. الكميات: 3 خانات بعد العلامة، والرقم الرابع ٥ أو أكبر → يتقرب لأعلى
   (10.9685 → 10.969 · 10.9682 → 10.968 · زيت 12 لتر → 10.968 مش 10.970).
2. المقررات (للشخص): مش بتقرب خالص — القيمة المدخلة بالظبط (كمون 0.00025
   تظهر «٠٫٠٠٥» مش «٠٫٠٠») — الضرب عادي، والناتج (الكمية) هو اللي بيتقرب.
3. دفتر ٣ مخازن (والنفس تفاريد): اليوم ← التاريخ ← رقم الإذن ← البيان ←
   رصيد الافتتاح ← مضاف ← منصرف ← الرصيد ← ملاحظات — والملاحظة بتتعديل يدوي.
"""
import re

from core import arabic_numbers as arnum
from data_access import db_warehouses as dw
from data_access import db_rations as dr
from data_access import db_stores, months

YEAR, MONTH = 2031, 9


# ── round3: نصف-أعلى على 3 خانات ─────────────────────────────────────────
def test_round3_half_up_rule():
    assert arnum.round3(10.9685) == 10.969     # الرقم الرابع 5 → فوق
    assert arnum.round3(10.9682) == 10.968     # الرقم الرابع 2 → في مكانه
    assert arnum.round3(10.968) == 10.968
    assert arnum.round3(10.96899) == 10.969
    assert arnum.round3(12 * 0.914) == 10.968  # حالة الزيت الفعلية
    assert arnum.round3(0.0005) == 0.001
    assert arnum.round3(0.0004) == 0.0
    assert arnum.round3(1.23449) == 1.234
    assert arnum.round3(1.2345) == 1.235
    assert arnum.round3(75) == 75.0
    assert arnum.round3(None) == 0.0
    assert arnum.round3("2.5") == 2.5


def test_fmt_qty_uses_half_up():
    assert arnum.fmt_qty(10.9685) == "\u0661\u0660\u066b\u0669\u0666\u0669"   # ١٠٫٩٦
    assert arnum.fmt_qty(10.968) == "\u0661\u0660\u066b\u0669\u0666\u0668"    # ١٠٫٩٦
    assert arnum.fmt_qty(12 * 0.914) == "\u0661\u0660\u066b\u0669\u0666\u0668"
    assert arnum.fmt_qty(0.12) == "\u0660\u066b\u0661\u0662\u0660"
    assert arnum.fmt_qty(75) == "\u0667\u0665\u066b\u0660\u0660\u0660"
    assert arnum.fmt_qty(None) == ""


def test_fmt_qty_exact_no_rounding():
    assert arnum.fmt_qty_exact(0.00025) == "\u0660\u066b\u0660\u0660\u0660\u0662\u0665"  # ٠٫٠٠٥
    assert arnum.fmt_qty_exact(0.01) == "\u0660\u066b\u0660\u0661"
    assert arnum.fmt_qty_exact(0.012) == "\u0660\u066b\u0660\u0661\u0662"
    assert arnum.fmt_qty_exact(2) == "\u0662"
    assert arnum.fmt_qty_exact(0.914) == "\u0660\u066b\u0669\u0661\u0664"
    assert arnum.fmt_qty_exact(None) == ""
    assert arnum.fmt_qty_exact(0) == ""


# ── الزيت: 12 لتر على كارت الدفتر = ١٠٫٩٦٨ (مش ١٠٫٩٧) ──────────────────────
def test_oil_card_12_liters_shows_10968(client):
    db_stores.add_store("المخزن الرئيسي")
    r = client.post("/warehouses/wh1/add?cycle=supply", data={
        "receipt_no": "31", "day": "10", "supplier_name": "كوكو",
        "l0_item_name": "زيت الطعام", "l0_handle_unit": "لتر", "l0_qty": "12",
        "l0_pack_kind": "بدون تغليف"}, follow_redirects=True)
    assert r.status_code == 200
    oil = [i for i in dw.list_items(YEAR, MONTH, "supply")
           if i["name"] == "زيت الطعام"][0]
    card = dw.item_card(YEAR, MONTH, oil["id"])
    # الكمية المخزنة بالتر سليمة — واللي بيتعرض بكجم على 3 خانات
    assert card["total_added"] == 12.0
    assert card["total_added_d"] == 10.968
    assert card["balance_d"] == 10.968
    row = [r_ for r_ in card["rows"] if r_["kind"] == "add1"][0]
    assert row["added_d"] == 10.968
    # عمود اليوم: اسم اليوم موجود في كل سطر
    assert row["wday"] in ("الأحد", "الاثنين", "الثلاثاء", "الأربعاء",
                           "الخميس", "الجمعة", "السبت")
    page = r.data.decode("utf-8")
    assert "\u0661\u0660\u066b\u0669\u0666\u0668" in page     # ١٠٫٩٦
    assert "\u0661\u0660\u066b\u0669\u0667\u0660" not in page  # مش ١٠٫٩٧٠


def test_non_oil_item_stays_in_handle_unit_three_decimals(client):
    """الأصناف الأخرى تبقى بوحدة التعامل، مع التقريب إلى ثلاث خانات نصف-أعلى."""
    db_stores.add_store("المخزن الرئيسي")
    client.post("/warehouses/wh1/add?cycle=supply", data={
        "receipt_no": "32", "day": "10", "supplier_name": "مورد",
        "l0_item_name": "سكر", "l0_handle_unit": "كجم", "l0_qty": "10.9685",
        "l0_pack_kind": "بدون تغليف"}, follow_redirects=True)
    it = [i for i in dw.list_items(YEAR, MONTH, "supply")
          if i["name"] == "سكر"][0]
    card = dw.item_card(YEAR, MONTH, it["id"])
    # السكر: وحدة الدفتر كجم مثل وحدة التعامل، دون تحويل إلى جم
    assert card["total_added_d"] == 10.969


# ── الكمون: مقرر 0.00025 بيتخزن وبيعرض بالظبط ─────────────────────────────
def test_cumin_ration_stored_exact(client):
    months.init_month(YEAR, MONTH)
    client.post("/rations/tamween/items/add?year=2031&month=9", data={
        "name": "كمون", "kind": "summer", "unit": "كجم",
        "breakfast": "0.00025", "lunch": "", "dinner": ""},
        follow_redirects=True)
    items, _custom = dr.get_items(YEAR, MONTH, "tamween", "summer")
    cumin = [i for i in items if i["name"] == "كمون"][0]
    assert cumin["breakfast"] == 0.00025     # التخزين بالظبط
    page = client.get("/rations/tamween?year=2031&month=9&kind=summer")
    body = page.data.decode("utf-8")
    # العرض: ٠٫٠٠٢٥ (مش ٠٫٠٠)
    assert "\u0660\u066b\u0660\u0660\u0660\u0662\u0665" in body
    # والضرب: الناتج (الكمية) هو اللي بيتقرب — 40 شخص × 0.00025 = 0.01
    assert dr.issuance_map(cumin, None)  # الخريطة سليمة


def test_cumin_total_rounds_but_ration_exact(client):
    """2 أشخاص × 0.00025 × 3 أيام = 0.0015 → بيتقرب للناتج 0.002 (نصف-أعلى)."""
    assert arnum.round3(0.00025 * 2 * 3) == 0.002
    assert arnum.round3(0.00025 * 40) == 0.01


# ── ترتيب أعمدة دفتر ٣ مخازن + تفاريد ─────────────────────────────────────
def test_ledger_column_order_template():
    src = open("templates/warehouses/tab_wh3.html", encoding="utf-8").read()
    heads = re.findall(r"<thead><tr>(.*?)</tr></thead>", src, re.S)
    assert len(heads) >= 2, "فيها ترويسة واحدة فقط؟"
    for h in heads:
        order = re.findall(r"<th>([^<]+)</th>", h)
        assert order[:3] == ["اليوم", "يوم الشهر", "التاريخ"], order
        assert order[3:10] == ["رقم الإذن", "البيان", "رصيد الافتتاح",
                               "مضاف", "منصرف", "الرصيد", "ملاحظات"], order


def test_ledger_row_note_editable(client):
    """ملاحظة يدوية على سطر — تحفظ وتعلو على المحسوبة (والنفس دورة الترفيه)."""
    db_stores.add_store("المخزن الرئيسي")
    client.post("/warehouses/wh1/add?cycle=supply", data={
        "receipt_no": "33", "day": "10",
        "l0_item_name": "أرز", "l0_handle_unit": "كجم", "l0_qty": "5",
        "l0_pack_kind": "بدون تغليف"}, follow_redirects=True)
    it = [i for i in dw.list_items(YEAR, MONTH, "supply")
          if i["name"] == "أرز"][0]
    # حفظ ملاحظة
    r = client.post("/warehouses/wh3/row-note?cycle=supply", data={
        "item_id": str(it["id"]), "kind": "add1", "permit_no": "33",
        "day": "10", "notes": "ملاحظة من الورقة"}, follow_redirects=True)
    assert r.status_code == 200
    assert dw.row_notes_map(YEAR, MONTH, "supply", it["id"]) == {
        ("add1", 33, 10): "ملاحظة من الورقة"}
    card = dw.item_card(YEAR, MONTH, it["id"])
    row = [r_ for r_ in card["rows"] if r_["kind"] == "add1"][0]
    assert row["notes"] == "ملاحظة من الورقة"   # المعلّمة يدويًا تعلو
    # الترفيه: نفس الشغل بدورة tarfea
    client.post("/warehouses/wh1/add?cycle=tarfea", data={
        "receipt_no": "5", "day": "11",
        "l0_item_name": "تونة 185", "l0_handle_unit": "علبة", "l0_qty": "10",
        "l0_pack_kind": "بدون تغليف"}, follow_redirects=True)
    t = [i for i in dw.list_items(YEAR, MONTH, "tarfea")
         if i["name"] == "تونة 185"][0]
    r = client.post("/warehouses/wh3/row-note?cycle=tarfea", data={
        "item_id": str(t["id"]), "kind": "add1", "permit_no": "5",
        "day": "11", "notes": "دفتر الترفيه"}, follow_redirects=True)
    assert r.status_code == 200
    assert dw.row_notes_map(YEAR, MONTH, "tarfea", t["id"]) == {
        ("add1", 5, 11): "دفتر الترفيه"}
