# -*- coding: utf-8 -*-
"""إصلاحا «٦ مخازن» (توجيه ١٥/١٠):

١) فولدر «يوم …» ما يتعملش غير عند الحفظ — فتح التاب أو تغيير يوم الجرد
   ما يسيبش فولدر فاضي يوهم إن الجرد اتحفظ.
٢) لو الشهر مفيهوش أصناف: زر «تطبيق الجرد» مقفول ورسالة واضحة **جوه الورقة
   نفسها** (مش توست مؤقت) — ومن غير أي خروج من الصفحة.
"""
from pathlib import Path

from data_access import db_permits as dp
from data_access import db_rations as dr
from data_access import db_warehouses as dw
from data_access import months
from services import inv6_fs as if6

YEAR, MONTH = 2031, 9
ROOT = Path(__file__).resolve().parents[1]


def _init():
    months.init_month(YEAR, MONTH)


def _seed():
    """صنف أرز + إذن إضافة يوم ٢ (نفس بذر اختبارات ٦ مخازن القائمة)."""
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز", "كجم", 0, 0, 0)
    dw.add_receipt(YEAR, MONTH, "supply", 2, "أرز", 100, "كجم",
                   date_iso="2031-09-02", receipt_no=1)


def _page(client, day=None):
    url = "/warehouses?cycle=supply&sub=inv6"
    if day:
        url += f"&day={day}"
    response = client.get(url)
    assert response.status_code == 200
    return response.data.decode("utf-8")


def _day_folder(day):
    return if6.day_file(YEAR, MONTH, day).parent


def test_opening_tab_never_creates_day_folder(client, app):
    _init()                                   # شهر فاضي تمامًا
    _page(client)
    _page(client, day=5)
    assert not _day_folder(1).exists()        # «يوم ١» ما اتعملش
    assert not _day_folder(5).exists()        # ولا «يوم ٥»
    assert not _day_folder(1).parent.exists()  # ولا «6-مخازن» نفسها


def test_day_fetch_never_creates_day_folder(client, app):
    _init()
    _seed()
    response = client.get("/inv6/day?day=3")
    assert response.status_code == 200 and response.get_json()["ok"]
    assert not _day_folder(3).exists()


def test_apply_creates_folder_and_file_only_on_save(client, app):
    _init()
    _seed()
    assert not _day_folder(3).exists()        # قبل الحفظ مفيش حاجة
    response = client.post("/inv6/apply", data={
        "day": "3", "sector": "الجهة", "warehouse": "المخزن",
        "row0_cycle": "supply", "row0_item_id": "1", "row0_name": "أرز",
        "row0_unit": "كجم", "row0_serial": "1", "row0_book": "100",
        "row0_counted": "100", "row0_price": "0",
        "row0_status_item": "جيدة", "row0_status_issue": "جيدة",
    })
    assert response.status_code == 302
    fpath = if6.day_file(YEAR, MONTH, 3)
    assert fpath.parent.is_dir() and fpath.is_file()   # الحفظ عمل الفولدر والملف


def test_empty_month_disables_apply_and_shows_note_in_paper(client, app):
    _init()
    page = _page(client)
    seg = page.split('id="inv6ApplyBtn"')[1][:220]
    assert "disabled" in seg                                # الزر مقفول
    paper = page.split('id="inv6PaperWrap"')[1]
    assert 'id="inv6NoItems"' in paper                      # الرسالة جوه الورقة
    assert "لا توجد أصناف في دفتر ٣ مخازن لهذا الشهر" in paper
    assert page.count('class="iv-row"') == 0


def test_month_with_items_enables_button_and_hides_note(client, app):
    _init()
    _seed()
    page = _page(client)
    seg = page.split('id="inv6ApplyBtn"')[1][:220]
    assert "disabled" not in seg                            # الزر شغال
    assert 'id="inv6NoItems"' not in page                   # مفيش رسالة
    assert page.count('class="iv-row"') > 0


def test_day_json_reports_rows_state_and_never_creates_folders(client, app):
    _init()
    empty = client.get("/inv6/day?day=4").get_json()
    assert empty["ok"] and empty["has_rows"] is False
    assert 'id="inv6NoItems"' in empty["paper"]             # الرسالة جوه ورقة اليوم
    assert not _day_folder(4).exists()
    _seed()
    full = client.get("/inv6/day?day=4").get_json()
    assert full["has_rows"] is True
    assert 'id="inv6NoItems"' not in full["paper"]
    assert not _day_folder(4).exists()                      # الكشف ما يعملش فولدر


def test_guard_js_and_css_contract():
    """قفل الزر محتاج: id + دالة مزامنة + حماية submit على اللفافة + ستايل الرسالة."""
    tpl = (ROOT / "templates" / "warehouses" / "tab_inv6.html").read_text(encoding="utf-8")
    assert 'id="inv6ApplyBtn"' in tpl and "syncApply" in tpl
    assert 'wrap.addEventListener("submit"' in tpl          # حماية Enter
    css = (ROOT / "static" / "css" / "inv6.css").read_text(encoding="utf-8")
    assert ".iv6-note" in css
