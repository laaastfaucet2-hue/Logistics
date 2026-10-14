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


# ==========================================================================
# «الخروج برا البرنامج» (١٥/١٠): المستخدم بيختار يوم (الورقة بتتبدل بالـ fetch)
# وبعدين «تطبيق الجرد» → كان الرمز بيضيع من الفورم البديل فيطرد لشاشة الدخول.
# ==========================================================================
from data_access import database as db  # noqa: E402


def _sid_only_get(app, token, url):
    """طلب بجلسة الرمز فقط — عميل نضيف بلا أي كوكيز (يحاكي متصفح بيحجب كوكي الجلسة)."""
    c = app.test_client()
    return c.get(f"{url}{'&' if '?' in url else '?'}sid={token}")


def test_day_paper_carries_session_token(client, app):
    """الورقة الجاية من /inv6/day لازم يكون جواها فورم التطبيق وبه الرمز."""
    _init()
    _seed()
    token = db.create_session(1)
    response = _sid_only_get(app, token, "/inv6/day?day=2")
    assert response.status_code == 200
    paper = response.get_json()["paper"]
    form = paper[paper.find('<form id="inv6ApplyForm"'):]
    form = form[:form.find("</form>")]
    assert f'name="sid" value="{token}"' in form


def test_apply_from_fetched_paper_never_bounces_to_login(app):
    """رحلة المستخدم الحقيقية: فتح التاب ← تغيير اليوم (جلب الورقة) ← تطبيق:
    لازم تنجح و**ما توصلش** لشاشة الدخول مهما كانت الكوكيز محجوبة."""
    _init()
    _seed()
    token = db.create_session(1)
    # ١) فتح التاب
    assert _sid_only_get(app, token, "/warehouses?cycle=supply&sub=inv6").status_code == 200
    # ٢) تغيير اليوم — الورقة البديلة من الجلب
    paper = _sid_only_get(app, token, "/inv6/day?day=4").get_json()["paper"]
    form = paper[paper.find('<form id="inv6ApplyForm"'):]
    form = form[:form.find("</form>")]
    fields = dict(__import__("re").findall(
        r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', form))
    fields["sid"] = token
    assert fields["sid"] == token                      # الفورم البديل شايل الرمز
    # ٣) الضغط على «تطبيق الجرد» بجلسة الرمز فقط
    anon = app.test_client()
    response = anon.post("/inv6/apply", data=fields)
    assert response.status_code == 302
    location = response.headers["Location"]
    assert "/login" not in location                    # ما خرجش برا البرنامج
    assert location.startswith("/inv6/") and f"sid={token}" in location
    # ٤) متابعة التحويل حتى صفحة القسم — الرمز بيفضل معاه
    follow = anon.get(location)
    assert follow.status_code == 302
    assert f"sid={token}" in follow.headers["Location"]
    final = anon.get(follow.headers["Location"])
    assert final.status_code == 200
    assert "تسجيل الدخول" not in final.data.decode("utf-8")


def test_inv6_page_redirect_keeps_token_and_context(app):
    _init()
    token = db.create_session(1)
    response = _sid_only_get(app, token, "/inv6/?day=1&ok=خالص")
    assert response.status_code == 302
    location = response.headers["Location"]
    assert f"sid={token}" in location and "day=1" in location and "sub=inv6" in location


def test_post_redirect_keeps_form_token_even_with_cookie(client, app):
    """حتى لو الكوكي شغالة، رمز الفورم بيفضل في التحويل بعد POST (إصلاح ١٥/١٠)."""
    _init()
    _seed()
    token = db.create_session(1)
    response = client.post("/inv6/apply", data={
        "day": "2", "sid": token,
        "row0_cycle": "supply", "row0_item_id": "1", "row0_name": "أرز",
        "row0_unit": "كجم", "row0_serial": "1", "row0_book": "100",
        "row0_counted": "100", "row0_price": "0",
        "row0_status_item": "جيدة", "row0_status_issue": "جيدة",
    })
    assert response.status_code == 302
    assert f"sid={token}" in response.headers["Location"]
