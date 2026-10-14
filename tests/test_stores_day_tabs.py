# -*- coding: utf-8 -*-
"""تابات فرعية لكل صنف في سجل حركة المخزن (١٤/١٠): الإجماليات تبقى أول، وتحت
تاب لكل صنف بسطر لكل يوم نشط — اليوم / الشركة الموردة / الشركة المنتجة /
داخل (تغليف) / خارج (تغليف) / الرصيد التراكمي في نهاية اليوم — أرقام عربية."""
from data_access import db_permits as dp
from data_access import db_rations as dr
from data_access import db_stores
from data_access import db_warehouses as dw
from data_access import months
from data_access.db_warehouses_stores import item_day_rows

YEAR, MONTH = 2031, 9


def _init():
    months.init_month(YEAR, MONTH)


def _aggregate(moves, unit):
    """يحوّل شكل الحركات (اللي بتستخدمه الوحدة) لصفوف المخزن ثم يجمعها بنفس الدالة."""
    inn = [{"item": "أرز", "date_iso": m["date"], "qty": m["qty"],
            "supplier": m.get("supplier", ""), "producer": m.get("producer", ""),
            "pack_short": m.get("pack_short") or m.get("pack", ""),
            "pack_label": m.get("pack", ""), "rem_qty": m.get("rem_qty")}
           for m in moves if m["dir"] == "in"]
    out = [{"item": "أرز", "date_iso": m["date"], "qty": m["qty"],
            "pack_label": m.get("pack", ""),
            "pack_short": m.get("pack_short", ""), "rem_qty": m.get("rem_qty")}
           for m in moves if m["dir"] == "out"]
    return item_day_rows(inn, out, "أرز", unit)


def test_item_days_aggregates_by_day_with_running_balance():
    moves = [
        {"dir": "in", "date": "2031-09-01", "qty": 100.0, "supplier": "النور",
         "producer": "الدلتا", "pack_short": "شكارتان (٥٠ كجم)", "rem_qty": 100.0},
        {"dir": "out", "date": "2031-09-01", "qty": 10.0,
         "pack_short": "١٠ كجم سائب", "rem_qty": 90.0},
        {"dir": "in", "date": "2031-09-02", "qty": 60.0, "supplier": "النور",
         "producer": "الدلتا", "pack_short": "شكارة (٦٠ كجم)", "rem_qty": 150.0},
        {"dir": "out", "date": "2031-09-02", "qty": 20.0,
         "pack_short": "٢٠ كجم سائب", "rem_qty": 130.0},
    ]
    days = _aggregate(moves, "كجم")
    assert [d["date"] for d in days] == ["2031-09-01", "2031-09-02"]
    assert days[0]["in"] == 100.0 and days[0]["out"] == 10.0
    assert days[0]["balance"] == 90.0                     # رصيد نهاية اليوم الأول
    assert days[1]["balance"] == 130.0                    # تراكمي (٩٠ + ٦٠ − ٢٠)
    assert days[0]["supplier"] == "النور" and days[0]["producer"] == "الدلتا"
    assert "شكارتان" in days[0]["in_pack"]
    assert "١٠ كجم سائب" in days[0]["out_pack"]


def test_item_days_plain_item_has_no_pack_label():
    days = _aggregate([{"dir": "out", "date": "2031-09-01", "qty": 4.0,
                        "pack": "٤ كجم", "rem_qty": -4.0}], "كجم")
    assert days[0]["out"] == 4.0 and days[0]["out_pack"] == ""


def _seed(client):
    _init()
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز", "كجم", 0, 0, 0)
    db_stores.add_store("مخزن الاختبار")
    sid = db_stores.list_stores()[0]["id"]
    dw.add_receipt(YEAR, MONTH, "supply", 1, "أرز", 100, "كجم",
                   producer="مطاحن الدلتا", supplier_name="شركة النور",
                   exp_iso="2032-09-01", date_iso="2031-09-01",
                   pack_kind="شكارة", pack_count=2, pack_capacity=50,
                   stores=[(sid, "مخزن الاختبار", 100)])
    dw.add_receipt(YEAR, MONTH, "supply", 2, "أرز", 60, "كجم",
                   producer="مطاحن الدلتا", supplier_name="شركة النور",
                   exp_iso="2032-09-01", date_iso="2031-09-02", receipt_no=2,
                   pack_kind="شكارة", pack_count=1, pack_capacity=60,
                   stores=[(sid, "مخزن الاختبار", 60)])
    dp.save_permit(YEAR, MONTH, {
        "number": 1, "fiscal_year": 2026, "date_from": 2, "date_to": 2,
        "issue_days": 1, "mode": "combined", "entity_label": "جهة الاختبار",
        "officers": 3, "individuals": 40, "recruits": 5,
        "meals": ["breakfast", "lunch"], "record_ids": [1],
        "actuals": {"tamween_أرز": 20},
    })
    return sid


def test_store_page_renders_per_item_day_tabs(client):
    sid = _seed(client)
    page = client.get(f"/stores/?year={YEAR}&month={MONTH}&tab=mains&store={sid}")
    assert page.status_code == 200
    html = page.data.decode("utf-8")
    assert 'data-st-sub="mv:أرز"' in html
    assert 'data-st-panel="mv:أرز"' in html
    # الإجماليات تبقا أول — التابات الفرعية جوه نفس السجل تحتها
    assert html.index("الإجماليات لكل صنف") < html.index('data-st-sub="mv:أرز"')
    # جدول الأيام داخل تاب الصنف: سطر لكل يوم نشط
    start = html.index('data-st-panel="mv:أرز"')
    panel = html[start:html.index("</table>", start)]
    assert "٢٠٣١/٠٩/٠١" in panel and "٢٠٣١/٠٩/٠٢" in panel        # يوم ١ ويوم ٢
    assert panel.index("٢٠٣١/٠٩/٠١") < panel.index("٢٠٣١/٠٩/٠٢")  # الترتيب الزمني
    assert "شركة النور" in panel and "مطاحن الدلتا" in panel
    assert "١٠٠٫٠٠٠" in panel                          # رصيد نهاية اليوم الأول
    assert "١٤٠٫٠٠٠" in panel                          # رصيد نهاية اليوم الثاني (١٠٠+٦٠−٢٠)
    # داخل وخارج اليوم الثاني (٦٠ داخل / ٢٠ خارج) — الأرقام عربية
    assert "+" + "٦٠٫٠٠٠" in panel and "−" + "٢٠٫٠٠٠" in panel
