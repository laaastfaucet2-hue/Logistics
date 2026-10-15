# -*- coding: utf-8 -*-
"""إحصائيات المخازن والثلاجات: الحساب الصحيح + الصفحة بالهيدر والتبويبات الفرعية.

* الدفعتان ١٠٠ + ١٠٠ وصرف ١٢٠ ⇒ الباقي ٨٠ في الثانية وأقرب صلاحية لها (خطأ ٢ القديم).
* أول المدة + الوارد − المنصرف = الرصيد · لا إجمالي يجمع وحدتين.
* السنوي: أول المدة لا يُحسب مرتين · آخر الفترة = آخر شهر · فرق الترحيل يظهر.
* كل تبويب: زر الطباعة الرسمي + الدباجة + التوقيعان · أزرار الملفات بأسمائها · بلا None.
كل البيانات في مجلد مؤقت (conftest) — لا يلمس database/ الحقيقي.
"""
import re
from datetime import date

from core import arabic_numbers as arnum
from data_access import db_permits as dp
from data_access import db_rations as dr
from data_access import db_stores
from data_access import db_warehouses as dw
from data_access import db_warehouses_stores as dws
from data_access import months
from services import stats_stores as ss

YEAR, MONTH = 2031, 9
TODAY = date(2031, 9, 15)
STORE = "مخزن الاختبار"


def _permit(month, number, day, qty, entity="جهة الاختبار", item="أرز"):
    dp.save_permit(YEAR, month, {
        "number": number, "fiscal_year": 2031, "date_from": day, "date_to": day,
        "issue_days": 1, "mode": "combined", "entity_label": entity,
        "officers": 3, "individuals": 40, "recruits": 5, "meals": ["lunch"],
        "record_ids": [], "actuals": {f"tamween_{item}": qty}})


def seed_basic(month=MONTH):
    """مخزن واحد + دفعتان أرز (١٠٠ + ١٠٠) بصلاحيتين + إذن صرف ١٢٠."""
    months.init_month(YEAR, month)
    dr.add_item(YEAR, month, "tamween", "summer", "أرز", "كجم", 0, 0, 0)
    if not db_stores.list_stores():
        db_stores.add_store(STORE)
    sid = db_stores.list_stores()[0]["id"]
    dw.add_receipt(YEAR, month, "supply", 1, "أرز", 100, "كجم", producer="مطاحن الدلتا",
                   supplier_name="شركة النور", exp_iso="2031-10-01",
                   date_iso=f"{YEAR}-{month:02d}-01", stores=[(sid, STORE, 100)])
    dw.add_receipt(YEAR, month, "supply", 2, "أرز", 100, "كجم", exp_iso="2031-12-01",
                   date_iso=f"{YEAR}-{month:02d}-02", receipt_no=2, stores=[(sid, STORE, 100)])
    _permit(month, 1, 3, 120)
    return sid


def _num(text):
    if not text:
        return 0.0
    return arnum.parse_float(text) or 0.0


def _col(table, row, name):
    return row[table["head"].index(name)]["t"]


def test_remaining_batches_follow_fefo_two_batches(app):
    sid = seed_basic()
    remaining = {b["serial"]: b["remaining"] for b in dws.remaining_batches(YEAR, MONTH, "supply")}
    assert remaining == {1: 0.0, 2: 80.0}
    view = ss.build_view("balances", YEAR, MONTH, "month", today=TODAY)
    store = next(t for t in view["tables"] if t["key"] == f"store_{sid}")
    row = store["rows"][0]
    assert _col(store, row, "أقرب صلاحية") == "٢٠٣١/١٢/٠١"
    assert _col(store, row, "الرصيد") == "٨٠٫٠٠٠"


def test_inventory_equation_and_separate_unit_totals(app):
    sid = seed_basic()
    dr.add_item(YEAR, MONTH, "tamween", "summer", "صلصة", "علبة", 0, 0, 0)
    dw.add_receipt(YEAR, MONTH, "supply", 3, "صلصة", 50, "علبة", exp_iso="2032-03-01",
                   date_iso="2031-09-04", receipt_no=3, stores=[(sid, STORE, 50)])
    view = ss.build_view("balances", YEAR, MONTH, "month", today=TODAY)
    for table in view["tables"]:
        for row in table["rows"]:
            opening = _num(_col(table, row, "رصيد أول المدة"))
            balance = opening + _num(_col(table, row, "الوارد")) - _num(_col(table, row, "المنصرف"))
            assert abs(balance - _num(_col(table, row, "الرصيد"))) < 1e-6
    total = next(t for t in view["tables"] if t["key"] == "total")
    units = [row[2]["t"] for row in total["foot"]]
    assert units == sorted(["كجم", "علبة"])          # إجمالي منفصل لكل وحدة
    summary = ss.build_view("summary", YEAR, MONTH, "month", today=TODAY)
    labels = [row[0]["t"] for row in summary["tables"][0]["rows"]]
    assert "الرصيد (كجم)" in labels and "الرصيد (علبة)" in labels


def test_yearly_opening_once_closing_last_month_and_carry_difference(app):
    db_stores.add_store(STORE)
    sid = db_stores.list_stores()[0]["id"]
    # أغسطس: وارد ١٠٠ ومنصرف ٣٠ ⇒ آخره ٧٠
    dr.add_item(YEAR, 8, "tamween", "summer", "أرز", "كجم", 0, 0, 0)
    dw.add_receipt(YEAR, 8, "supply", 1, "أرز", 100, "كجم", exp_iso="2032-01-01",
                   date_iso="2031-08-01", stores=[(sid, STORE, 100)])
    _permit(8, 1, 2, 30)
    # سبتمبر: أول المدة ٦٠ (فرق ترحيل −١٠) + وارد ٥٠ − منصرف ٢٠ ⇒ آخره ٩٠
    dr.add_item(YEAR, 9, "tamween", "summer", "أرز", "كجم", 0, 0, 0)
    dw.add_opener(YEAR, 9, "supply", "أرز", 60, 1, handle_unit_hint="كجم",
                  exp_iso="2032-01-01", date_iso="2031-09-01", stores=[(sid, STORE, 60)])
    dw.add_receipt(YEAR, 9, "supply", 5, "أرز", 50, "كجم", exp_iso="2032-02-01",
                   date_iso="2031-09-03", stores=[(sid, STORE, 50)])
    _permit(9, 1, 4, 20)
    view = ss.build_view("balances", YEAR, 9, "year", today=TODAY)
    store = next(t for t in view["tables"] if t["key"] == f"store_{sid}")
    row = store["rows"][0]
    assert _col(store, row, "رصيد أول السنة") == ""            # أول المدة في أغسطس = ٠
    assert _col(store, row, "وارد السنة") == "١٥٠٫٠٠٠"         # أول مدة سبتمبر خارج المجموع
    assert _col(store, row, "منصرف السنة") == "٥٠٫٠٠٠"
    assert _num(_col(store, row, "فرق الترحيل")) == -10.0
    assert _col(store, row, "رصيد آخر الفترة") == "٩٠٫٠٠٠"      # = رصيد آخر شهر
    month_end = next(t for t in view["tables"] if t["key"] == "month_end")
    end_row = month_end["rows"][0]
    assert _col(month_end, end_row, "أغسطس") == "٧٠٫٠٠٠"
    assert _col(month_end, end_row, "سبتمبر") == "٩٠٫٠٠٠"
    cards = {c["label"]: c["value"] for c in view["cards"]}
    assert cards["فروق الترحيل"] == "١"


def test_summary_cards_split_expired_from_danger(app):
    sid = seed_basic()
    for serial, item, qty, expiry in ((3, "عدس", 10, "2031-09-10"), (4, "فول", 5, "2031-10-01")):
        dr.add_item(YEAR, MONTH, "tamween", "summer", item, "كجم", 0, 0, 0)
        dw.add_receipt(YEAR, MONTH, "supply", 5, item, qty, "كجم", exp_iso=expiry,
                       date_iso="2031-09-05", receipt_no=serial, stores=[(sid, STORE, qty)])
    view = ss.build_view("summary", YEAR, MONTH, "month", today=TODAY)
    cards = {c["label"]: (c["value"], c["sub"]) for c in view["cards"]}
    # عدس منتهية · فول خطر (١٦ يوم) · دفعة الأرز الأولى المستهلكة كلها لا تُعد أصلًا
    assert cards["منتهية / خطر"] == ("٢", "منتهية: ١")
    assert cards["إذون الإضافة"][0] == "٤" and cards["إذون الصرف"][0] == "١"
    # الشهر الفائت يُحسب لآخر يومه: ملف سبتمبر لا يتغير كل يوم
    later = ss.build_view("summary", YEAR, MONTH, "month", today=date(2031, 11, 20))
    assert later["cards"] == ss.build_view("summary", YEAR, MONTH, "month",
                                           today=date(2031, 12, 25))["cards"]


def _visible(html):
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    return re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)


def test_every_subtab_page_has_header_files_print_and_no_none(client):
    seed_basic()
    for tab in ss.visible_subtabs():
        for scope in ("month", "year"):
            response = client.get(f"/stats/?cycle=supply&tab=stores&sub={tab['key']}&scope={scope}")
            assert response.status_code == 200, (tab["key"], scope)
            page = response.get_data(as_text=True)
            assert "None" not in _visible(page), (tab["key"], scope)
            assert "js-print-page" in page and "window.print()" in page
            assert "app-print-head" in page and "app-print-foot" in page
            for other in ss.visible_subtabs():
                assert other["name"] in page
            name = ss.file_name(tab["key"], YEAR, MONTH if scope == "month" else None)
            assert f"📂 فتح مجلد «{ss.folder_name(tab['key'])}»" in page
            assert f"📗 فتح ملف «{name}»" in page
            assert f"إحصائيات المخازن والثلاجات — {tab['name']} — " in page


def test_scope_switch_keeps_the_same_subtab(client):
    seed_basic()
    page = client.get("/stats/?cycle=supply&tab=stores&sub=balances").get_data(as_text=True)
    hrefs = [h.replace("&amp;", "&") for h in re.findall(r'href="([^"]+)"', page)]
    yearly = [h for h in hrefs if "scope=year" in h and "tab=stores" in h]
    assert yearly and all("sub=balances" in h for h in yearly)


def test_header_stays_at_the_top_of_the_page_while_scrolling():
    """طلب المستخدم ١٤/١٠: الهيدر ميفضلش نازل معاه وهو بينزل في الصفحة."""
    from pathlib import Path
    css = (Path(__file__).resolve().parents[1] / "static" / "css" / "stats_stores.css"
           ).read_text(encoding="utf-8")
    rules = re.findall(r"\.ss-head\s*\{([^}]*)\}", css)
    assert rules and not any("sticky" in r or "fixed" in r for r in rules)


def test_wide_tab_prints_landscape_with_letterhead_and_signatures_together(client):
    """جدول أكثر من ١٠ أعمدة ⇒ الورق كله بالعرض (صفحة مسماة على body فلا ينفصل التوقيعان)."""
    seed_basic()
    body = re.compile(r'<body class="([^"]*)"')
    for sub, scope, wide in (("registry", "month", True), ("consumption", "year", True),
                             ("summary", "month", False), ("consumption", "month", False)):
        page = client.get(f"/stats/?cycle=supply&tab=stores&sub={sub}&scope={scope}"
                          ).get_data(as_text=True)
        assert ("ss-print-wide" in body.search(page).group(1)) is wide, (sub, scope)
        assert "ss-wide" not in page.replace("ss-print-wide", ""), (sub, scope)


def test_filters_change_screen_only_and_are_marked(client):
    sid = seed_basic()
    db_stores.add_store("ثلاجة فارغة")
    page = client.get("/stats/?cycle=supply&tab=stores&sub=balances&f_store=ثلاجة فارغة"
                      ).get_data(as_text=True)
    assert "معروض بفلتر: المخزن: ثلاجة فارغة" in page
    assert "مطبوع بفلتر: المخزن: ثلاجة فارغة" in page
    full = ss.build_view("balances", YEAR, MONTH, "month", today=TODAY)
    assert any(t["key"] == f"store_{sid}" and t["rows"] for t in full["tables"])


def test_statistics_permission_still_guards_the_new_endpoints(app, client):
    from data_access import db_users
    uid, err = db_users.create_user("مستخدم محدود", "limited.user", "secret1")
    assert uid and not err
    other = app.test_client()
    assert other.post("/login", data={"username": "limited.user", "password": "secret1"}
                      ).status_code == 302
    assert other.get("/stats/stores/status?sub=summary").status_code == 403
    db_users.set_user_tabs(uid, ["statistics"])
    assert other.get("/stats/stores/status?sub=summary").status_code == 200
