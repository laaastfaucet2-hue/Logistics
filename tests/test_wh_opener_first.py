# -*- coding: utf-8 -*-
"""رصيد أول المدة زي ١ مخازن بالظبط (١٥/١٠): أول سطر في الحساب دايمًا مهما كان يومه —
رصيده = كميته والإضافات تتراكم فوقه، في الكارت والتفاريد والإكسل و٤ مخازن
ورصيد المخزن (بعد). كل البيانات في مجلد مؤقت (conftest)."""
import re

from data_access import db_pack, db_stores
from data_access import db_rations as dr
from data_access import db_warehouses as dw
from data_access import db_warehouses_stores as dws
from data_access import months
from routes.stores import _enrich
from services import warehouses_fs as wf
from services import wh4_build

YEAR, MONTH = 2031, 9


def _late_opener():
    """إضافتين يوم ٣ و١٠ — ورصيد أول المدة اتسجّل بعدهم بيوم ١٥."""
    months.init_month(YEAR, MONTH)
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز", "كجم", 0, 0, 0)
    db_stores.add_store("مخزن 1")
    dw.add_receipt(YEAR, MONTH, "supply", 3, "أرز", 100, "كجم", receipt_no=11,
                   date_iso="2031-09-03", exp_iso="2032-01-01")
    dw.add_receipt(YEAR, MONTH, "supply", 10, "أرز", 50, "كجم", receipt_no=12,
                   date_iso="2031-09-10", exp_iso="2032-02-01")
    dw.add_opener(YEAR, MONTH, "supply", "أرز", 200, 15, exp_iso="2032-03-01",
                  date_iso="2031-09-15", producer="الدلتا", supplier_name="النور")
    return dw.resolve_item(YEAR, MONTH, "supply", "أرز")[0]


def test_opener_first_in_every_running_balance(app):
    item = _late_opener()
    card = dw.item_card(YEAR, MONTH, item["id"])
    assert [(r["kind"], r["open"], r["balance"]) for r in card["rows"]] == [
        ("opener", 0.0, 200.0), ("add1", 200.0, 300.0), ("add1", 300.0, 350.0)]
    expected = [200.0, 300.0, 350.0]
    assert [r["balance"] for r in db_pack.card_pack_rows(YEAR, MONTH, "supply", card)] == expected
    taf = wf.taf3_pack_rows(YEAR, MONTH, "supply", item["id"])
    assert [r["balance"] for r in taf["rows"]] == expected
    assert taf["rows"][0]["open_pack"] == "—"
    wh4 = wh4_build.monthly_ledger(YEAR, MONTH, "supply", "أرز")
    assert [(r["kind"], r["balance"]) for r in wh4["rows"]] == [
        ("opener", 200.0), ("add1", 300.0), ("add1", 350.0), ("closing", 350.0)]
    store = dw.stores_report(YEAR, MONTH)["stores"][0]
    assert [(r["serial"], r["rem_qty"]) for r in store["inn"]] == [
        (0, 200.0), (11, 300.0), (12, 350.0)]
    assert (store["inn"][0]["producer"], store["inn"][0]["supplier"]) == ("الدلتا", "النور")
    days = dws.item_day_rows(store["inn"], store["out"], "أرز", "كجم")
    assert [(d["date"], d["balance"]) for d in days] == [
        ("2031-09-15", 200.0), ("2031-09-03", 300.0), ("2031-09-10", 350.0)]
    moves = _enrich(store)["items"]["أرز"]["moves"]
    assert [(m["doc"], m["rem_qty"]) for m in moves][0] == ("رصيد أول المدة", 200.0)
    assert [m["rem_qty"] for m in moves] == expected


def test_wh3_page_opener_row_and_forms_like_wh1(client):
    item = _late_opener()
    dr.add_item(YEAR, MONTH, "tamween", "summer", "زيت", "كجم", 0, 0, 0)   # صنف مقرر من غير كارت
    page = client.get(f"/warehouses/?cycle=supply&sub=wh3&item={item['id']}").data.decode()
    body = page[page.find("wh-ledger"):]
    body = body[:body.find("</table>")]
    rows = [[re.sub(r"<[^>]+>", "", c).strip()
             for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)][5:9]
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S)]
    rows = [r for r in rows if r]
    assert rows[0] == ["٠٫٠٠٠", "٢٠٠٫٠٠٠", "٠٫٠٠٠", "٢٠٠٫٠٠٠ كجم"]
    assert rows[1][0] == "٢٠٠٫٠٠٠" and rows[1][3] == "٣٠٠٫٠٠٠ كجم"
    # نموذج صنف جديد فيه وحدة التعامل — والصنف بيتولد بيها زي ١ مخازن
    assert 'class="js-unit" name="handle_unit"' in page
    client.post("/warehouses/wh3/opener?cycle=supply", data={
        "cycle": "supply", "item_name": "زيت", "handle_unit": "لتر", "qty": "٤٠",
        "day": "١", "exp_date": "2032/01/01"})
    oil = dw.resolve_item(YEAR, MONTH, "supply", "زيت")[0]
    assert oil["handle_unit"] == "لتر" and dw.has_opener(YEAR, MONTH, oil["id"])
    # نموذج كارت من غير رصيد أول المدة فيه وحدة المعيار زي ١ مخازن
    dw.add_receipt(YEAR, MONTH, "supply", 2, "عدس", 5, "كجم", receipt_no=13,
                   date_iso="2031-09-02", exp_iso="2032-01-01")
    lentil = dw.resolve_item(YEAR, MONTH, "supply", "عدس")[0]
    page = client.get(f"/warehouses/?cycle=supply&sub=wh3&item={lentil['id']}").data.decode()
    form = page[page.find('id="whOpenerForm"'):]
    form = form[:form.find("</form>")]
    assert 'name="pack_inner_unit"' in form
    # نفس التغليف ⇒ نفس التسمية في أول المدة و١ مخازن (زيت بالكيلو وزجاجات باللتر)
    pk = dict(pack_kind="كرتونة", pack_count=10, pack_capacity=12, pack_inner_count=12,
              pack_inner_capacity=1, pack_inner_kind="زجاجة", pack_inner_unit="لتر")
    oil = dw.resolve_item(YEAR, MONTH, "supply", "زيت طعام", "كجم")[0]
    dw.add_opener(YEAR, MONTH, "supply", "زيت طعام", 0, 1, exp_iso="2032-01-01",
                  date_iso="2031-09-01", **pk)
    dw.add_receipt(YEAR, MONTH, "supply", 2, "زيت طعام", 0, receipt_no=14,
                   date_iso="2031-09-02", exp_iso="2032-01-01", **pk)
    opener = dw.item_card(YEAR, MONTH, oil["id"])["opener_row"]
    receipt = [r for r in dw.list_receipts(YEAR, MONTH, "supply") if r["serial"] == 14][0]
    assert receipt["pack_label"] == opener["pack_label"] and opener["pack_label"].endswith("١٠٩٫٦٨ كجم")


def test_pack_in_other_unit_converts_to_item_unit(app):
    """تغليف بوحدة غير وحدة الصنف (١٥/١٠): زجاجة لتر وصنف بالكيلو ⇒ بالوزن النوعي
    (٩١٤ للزيت أو المحفوظ في الكارت) — نفس الكلام في ١ مخازن ورصيد أول المدة."""
    months.init_month(YEAR, MONTH)
    db_stores.add_store("مخزن 1")
    store = db_stores.list_stores()[0]
    for name in ("زيت طعام", "زيت ذرة", "خل"):
        dw.resolve_item(YEAR, MONTH, "supply", name, "كجم")
    pk = dict(pack_kind="كرتونة", pack_count=10, pack_capacity=12, pack_inner_count=12,
              pack_inner_capacity=1, pack_inner_kind="زجاجة", pack_inner_unit="لتر")
    rec = dw.add_receipt(YEAR, MONTH, "supply", 1, "زيت طعام", 0, receipt_no=1,
                         date_iso="2031-09-01", exp_iso="2032-01-01", **pk)
    assert round(rec["qty_handle"], 6) == 109.68 and rec["conv_note"] == "١٢٠ لتر = ١٠٩٫٦٨ كجم"
    op = dw.add_opener(YEAR, MONTH, "supply", "زيت ذرة", 0, 1, exp_iso="2032-01-01",
                       date_iso="2031-09-01", stores=[(store["id"], "مخزن 1", 120)], **pk)
    assert round(op["qty"], 6) == 109.68
    assert dw.opener_stores(YEAR, MONTH, "supply")[op["item"]["id"]][0]["qty"] == 109.68
    # تعديل أول المدة باللتر (لقطة المستخدم ١٥/١٠): نفس التحويل — مش ١٢٠ كجم
    dw.update_opener(YEAR, MONTH, "supply", op["item"]["id"], 120, 1, exp_iso="2032-01-01",
                     date_iso="2031-09-01", stores=[(store["id"], "مخزن 1", 120)], **pk)
    assert round(dw.item_card(YEAR, MONTH, op["item"]["id"])["opener_row"]["added"], 6) == 109.68
    assert dw.opener_stores(YEAR, MONTH, "supply")[op["item"]["id"]][0]["qty"] == 109.68
    try:
        dw.add_receipt(YEAR, MONTH, "supply", 1, "خل", 0, receipt_no=2, **pk)
        raise AssertionError("لازم يطلب الوزن النوعي")
    except ValueError as exc:
        assert "الوزن النوعي" in str(exc)
    vinegar = dw.resolve_item(YEAR, MONTH, "supply", "خل")[0]
    dw.set_specific_weight(YEAR, MONTH, vinegar["id"], 1010)
    rec = dw.add_receipt(YEAR, MONTH, "supply", 1, "خل", 0, receipt_no=2, **pk)
    assert round(rec["qty_handle"], 6) == 121.2
    juice = dict(pack_kind="كرتونة", pack_count=10, pack_inner_count=12,
                 pack_inner_capacity=500, pack_inner_kind="زجاجة", pack_inner_unit="مل")
    dw.resolve_item(YEAR, MONTH, "supply", "عصير", "لتر")
    rec = dw.add_receipt(YEAR, MONTH, "supply", 1, "عصير", 0, receipt_no=3, **juice)
    assert round(rec["qty_handle"], 6) == 60.0


def test_opener_pack_saved_like_wh1(app):
    """تغليف أول المدة بخانات ١ مخازن (١٥/١٠): كرتونة بداخلها علب + سائب بالعلب
    ⇒ نفس الدفعة ونفس رصيد المخزن بالتغليف ونفس الصرف — والسطر القديم اللي
    اتحفظ جملة بس بيطلع نفس النتيجة."""
    months.init_month(YEAR, MONTH)
    db_stores.add_store("مخزن 1")
    pk = dict(pack_kind="كرتونة", pack_count=5, pack_inner_kind="علبة", pack_inner_count=6,
              pack_inner_capacity=2, pack_inner_unit="كجم", pack_loose=3, pack_loose_unit="علب")
    for name in ("صنف أ", "صنف ب"):
        dw.resolve_item(YEAR, MONTH, "supply", name, "كجم")
    dw.add_receipt(YEAR, MONTH, "supply", 1, "صنف أ", 0, receipt_no=1,
                   date_iso="2031-09-01", exp_iso="2032-01-01", **pk)
    dw.add_opener(YEAR, MONTH, "supply", "صنف ب", 0, 1, date_iso="2031-09-01",
                  exp_iso="2032-01-01", **pk)
    keys = ("qty", "pack_kind", "pack_count", "pack_capacity", "pack_loose", "pack_inner_count",
            "pack_inner_capacity", "pack_inner_kind", "pack_loose_unit")

    def snap():
        pool = {b["item"]["name"]: b for b in dws._batch_pool(YEAR, MONTH, "supply")}
        rep = dw.stores_report(YEAR, MONTH)["stores"][0]
        after = {r["item"]: r.get("rem_after") for r in rep["inn"]}
        return [{k: pool[n][k] for k in keys} for n in ("صنف أ", "صنف ب")], after

    (a, b), after = snap()
    assert a == b and after["صنف أ"] == after["صنف ب"] == "٥ كرتونة + ٣ علبة"
    item_b = dw.resolve_item(YEAR, MONTH, "supply", "صنف ب")[0]
    edit = dw.item_card(YEAR, MONTH, item_b["id"])["opener_row"]
    assert dws.opener_pack_fields(edit)["pack_inner_count"] == 6
    conn = dw._conn(YEAR, MONTH)   # السطر القديم: الجملة بس من غير الخانات
    with conn:
        conn.execute("UPDATE wh_ledger SET pack_kind='', pack_count=0, pack_inner_count=0, "
                     "pack_inner_capacity=0, pack_loose=0, pack_loose_unit='' WHERE kind='opener'")
    conn.close()
    months.bust_cache()
    (a2, b2), after2 = snap()
    assert b2 == a and after2 == after
