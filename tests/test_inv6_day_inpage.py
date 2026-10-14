# -*- coding: utf-8 -*-
"""يوم الجرد في «6 مخازن» (توجيه ١٤/١٠): تغيير اليوم يجيب رصيد ٣ مخازن
من غير خروج من الصفحة (fetch على /inv6/day)، وعلامة ✓ على الأيام المجردة،
وإعادة ربط صفوف الحسبة بعد كل تحديث."""
from core import arabic_numbers as arnum


D = lambda w: "".join(chr(0x0660 + int(c)) for c in w)
from data_access import db_permits as dp
from data_access import db_rations as dr
from data_access import db_warehouses as dw
from data_access import months

YEAR, MONTH = 2031, 9


def _init():
    months.init_month(YEAR, MONTH)


def _seed():
    """صنف + إذن إضافة يوم ٢ + إذن صرف يوم ٤ → رصيد ١٠٠ − ٢٠ = ٨٠ من يوم ٤."""
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز", "كجم", 0, 0, 0)
    dw.add_receipt(YEAR, MONTH, "supply", 2, "أرز", 100, "كجم",
                   date_iso="2031-09-02", receipt_no=1)
    dp.save_permit(YEAR, MONTH, {
        "number": 1, "fiscal_year": 2026, "date_from": 4, "date_to": 4,
        "issue_days": 1, "mode": "combined", "entity_label": "جهة الاختبار",
        "officers": 3, "individuals": 40, "recruits": 5,
        "meals": ["breakfast", "lunch"], "record_ids": [1],
        "actuals": {"tamween_أرز": 20},
    })


def _page(client, day=None):
    url = "/warehouses?cycle=supply&sub=inv6"
    if day:
        url += f"&day={day}"
    response = client.get(url)
    assert response.status_code == 200
    return response.data.decode("utf-8")


def test_day_bar_loads_in_page_without_full_navigation(client):
    _init()
    _seed()
    page = _page(client)
    # القائمة بقت fetch — مفيش submit للصفحة
    assert 'id="inv6DaySel"' in page
    assert 'onchange="this.form.submit()"' not in page
    assert 'id="inv6DayForm"' in page and 'data-day-url="/inv6/day?' in page
    # الورقة في partial ويتحدث مكانه
    assert 'id="inv6PaperWrap"' in page and "inv6Paper" in page
    # زر الحذف وفورم الحذف موجودين دايمًا (بيتخفوا لما اليوم مش محفوظ)
    assert 'id="inv6DelBtn"' in page and 'id="inv6DelForm"' in page
    assert "✓" not in page.split('id="inv6DaySel"')[1].split("</select>")[0]


def test_saved_day_gets_check_mark_and_can_be_deleted(client):
    _init()
    _seed()
    response = client.post("/inv6/apply", data={
        "day": "3", "sector": "الجهة", "warehouse": "المخزن",
        "row0_cycle": "supply", "row0_item_id": "1", "row0_name": "أرز",
        "row0_unit": "كجم", "row0_serial": "1", "row0_book": "100",
        "row0_counted": "100", "row0_price": "0",
        "row0_status_item": "جيدة", "row0_status_issue": "جيدة",
    })
    assert response.status_code == 302
    page = _page(client)
    options = page.split('id="inv6DaySel"')[1].split("</select>")[0]
    assert "يوم ٣ ✓" in options                      # ✓ على اليوم المجرد
    assert "يوم ٢" in options and "يوم ٢ ✓" not in options
    # زر الحذف ظاهر لليوم المحفوظ
    seg = page.split('id="inv6DelBtn"')[1][:120]
    assert "hidden" not in seg.split(">")[0]


def test_day_endpoint_returns_paper_for_any_day(client):
    _init()
    _seed()
    # يوم ٢: الرصيد الدفتري ١٠٠ (الإضافة) — يوم ٤: ٨٠ بعد الصرف
    early = client.get("/inv6/day?day=2")
    late = client.get("/inv6/day?day=4")
    assert early.status_code == 200 and late.status_code == 200
    e, l = early.get_json(), late.get_json()
    assert e["ok"] and l["ok"]
    assert e["day"] == 2 and l["day"] == 4
    assert e["day_label"] == arnum.to_arabic_indic("2")
    assert "inv6ApplyForm" in e["paper"] and "inv6-paper" in e["paper"]
    assert e["saved_days"] == [] and e["has_saved"] is False
    # الرصيد الدفتري بيتغير من يوم ليوم (١٠٠ ثم ٨٠)
    def book_of(payload):
        seg = payload["paper"].split('iv-book">')[1]
        return seg.split("<")[0].strip()
    assert book_of(e).startswith(D("100"))     # يوم ٢: الإضافة لسه ما اتصرف منها
    assert book_of(l).startswith(D("80"))      # يوم ٤: ١٠٠ − ٢٠ منصرف
    # يوم خارج الشهر → رسالة خطأ واضحة
    bad = client.get("/inv6/day?day=99")
    assert bad.status_code == 400 and bad.get_json()["ok"] is False
