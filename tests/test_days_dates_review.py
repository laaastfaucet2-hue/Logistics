# -*- coding: utf-8 -*-
"""مراجعة شاملة (توجيه المستخدم ٠٦/١٠/٢٠٢٦): أيام الشهر عربي وربطها بالتواريخ
الصحيحة، ضبط الحسابات، وتصيّد الأخطاء البرمجية في كل مسارات المنظومة.

كل الاختبارات على قواعد مؤقتة معزولة (conftest) — لا تمس بيانات المستخدم أبدًا.
"""
from datetime import date

import pytest

from core import dates, egtime
from data_access import db_raghibin as rp
from data_access import db_rations as dr
from data_access import db_tameedat as dt
from services import tameed_alerts

# أسبوع مرجعي معروف: ٢٠٢٦/١٠/٠٣ السبت … ٢٠٢٦/١٠/٠٩ الجمعة
REFERENCE_WEEK = [
    (date(2026, 10, 3), "السبت"),
    (date(2026, 10, 4), "الأحد"),
    (date(2026, 10, 5), "الاثنين"),
    (date(2026, 10, 6), "الثلاثاء"),
    (date(2026, 10, 7), "الأربعاء"),
    (date(2026, 10, 8), "الخميس"),
    (date(2026, 10, 9), "الجمعة"),
]

# أشهر بأطوال وأول أيام مختلفة (شهر عادي / كبيس / أول الشهر سبت / نهاية الشهر جمعة)
CALENDAR_MONTHS = [(2026, 1), (2026, 2), (2024, 2), (2026, 10), (2026, 12), (2027, 5)]


def test_weekday_names_are_correct_for_the_full_week():
    """أسماء الأيام العربي مربوطة بالتاريخ الصحيح (لا إزاحة يوم)."""
    for day, name in REFERENCE_WEEK:
        assert egtime.weekday_ar(day) == name, day
    # ترتيب قائمة العرض المعتمدة: السبت = ٠ … الجمعة = ٦
    from core.config import DAYS
    for index, (day, name) in enumerate(REFERENCE_WEEK):
        assert egtime.weekday_sat0(day) == index
        assert DAYS[index] == name


def _grid_columns(grid):
    """يحوّل شبكة أسابيع إلى {رقم اليوم: رقم عمود الأسبوع} (٠ = السبت)."""
    columns = {}
    for week in grid:
        for index, cell in enumerate(week):
            if not cell.get("empty"):
                columns[cell["day"]] = index
    return columns


@pytest.mark.parametrize("year,month", CALENDAR_MONTHS)
def test_calendar_grids_pin_every_day_to_its_real_weekday(app, year, month):
    """تقويم التاميدات وتقويم الراغبين: كل يوم في عمود يومه الحقيقي، ومرة واحدة."""
    from routes.raghibin.context import _day_grid
    from routes.tameedat.context import _calendar

    total = egtime.days_in_month(year, month)
    with app.test_request_context("/"):
        columns = _grid_columns(_calendar(year, month, 1))
    assert sorted(columns) == list(range(1, total + 1))

    ragh_columns = _grid_columns(_day_grid(year, month, 1, {}))
    assert sorted(ragh_columns) == list(range(1, total + 1))

    for day in range(1, total + 1):
        expected = egtime.weekday_sat0(date(year, month, day))
        assert columns[day] == expected, (year, month, day)
        assert ragh_columns[day] == expected, (year, month, day)


def test_dates_render_day_first_in_arabic_digits():
    """كل تاريخ ظاهر = يوم/شهر/سنة بصفر بادئ وأرقام عربية مشرقية."""
    assert dates.format_date("2026-09-22") == "٢٢/٠٩/٢٠٢٦"
    assert dates.format_date(date(2026, 10, 1)) == "٠١/١٠/٢٠٢٦"
    assert dates.format_date("22/09/2026") == "٢٢/٠٩/٢٠٢٦"
    assert dates.input_date("2026-10-06") == "٠٦/١٠/٢٠٢٦"
    assert egtime.fmt_ar("2026-10-06") == "٠٦/١٠/٢٠٢٦ — الثلاثاء"
    assert dates.period_date(2026, 2, 29) == "—"          # يوم مستحيل في شهر غير كبيس
    assert dates.period_date(2026, 10, 5) == "٠٥/١٠/٢٠٢٦"


def test_days_in_month_and_leap_years():
    assert egtime.days_in_month(2026, 2) == 28
    assert egtime.days_in_month(2024, 2) == 29
    assert egtime.days_in_month(2026, 10) == 31
    assert egtime.days_in_month(2026, 11) == 30
    assert (2026, 12, 31) == (egtime.eom(2026, 12).year, egtime.eom(2026, 12).month,
                              egtime.eom(2026, 12).day)


def test_illegal_dates_are_rejected_before_any_write(app):
    """التواريخ المستحيلة والمقلوبة تُرفض قبل الحفظ (لا تخمين ولا تبديل يوم/شهر)."""
    for bad in ("31/02/2026", "2026-02-30", "00/10/2026", "13/13/2026"):
        with pytest.raises(ValueError):
            dates.parse_date(bad)
    assert dates.parse_date("") is None
    assert dates.parse_date("01/10/2026") == date(2026, 10, 1)


def test_duration_and_month_end_clipping_are_correct(app):
    """المدة الزمنية: الأيام المحسوبة صحيحة، واللصق لا يعبر نهاية الشهر."""
    from data_access import months

    year, month = 2031, 9          # الشهر الذي يجهزه conftest
    months.init_month(year, month)
    entity_id = dt.add_entity(year, month, "جهة اختبار المدة", "شرطية")
    entity = dt.get_entity(year, month, entity_id)
    total_days = egtime.days_in_month(year, month)

    # من ٢٨ إلى ٣٠ = ٣ أيام سريان، ومجموع الأعداد يُضرب في أيام السريان
    record_id = dt.add_record(year, month, 28, entity, 2, 5, 1, day_to=30)
    record = dt.get_record(year, month, record_id)
    assert record["range_days"] == 3
    summary, totals = dt.month_summary(year, month)
    row = next(r for r in summary if r["entity_id"] == entity_id)
    assert row["active_days"] == 3
    assert row["total_officers"] == 2 * 3 and row["total_individuals"] == 5 * 3
    assert totals["active_days"] == 3

    # اللصق يوم ٣٠ بمدة ٣ أيام ==> يُقصّ عند آخر يوم في الشهر (لا انتقال للشهر التالي)
    pasted = dt.copy_record(year, month, record_id, 30)
    cloned = dt.get_record(year, month, pasted)
    assert cloned["day"] == 30 and cloned["day_to"] == min(30 + 2, total_days)
    assert cloned["day_to"] <= total_days


def test_month_totals_match_record_by_record(app):
    """الحساب الإجمالي = مجموع السجلات × أيام سريانها، والملحق محسوب مرة واحدة."""
    from data_access import months

    year, month = 2031, 9
    months.init_month(year, month)
    entity_id = dt.add_entity(year, month, "جهة حساب", "شرطية")
    entity = dt.get_entity(year, month, entity_id)
    dt.add_record(year, month, 1, entity, 10, 20, 5,
                  attachments=[{"name": "جهة ملحقة حساب", "entity_type": "شرطية",
                                "officers": 3, "individuals": 7, "recruits": 0}])
    dt.add_record(year, month, 2, entity, 1, 2, 3, day_to=4)
    summary, totals = dt.month_summary(year, month)
    main = next(r for r in summary if r["entity_id"] == entity_id)
    attached = next(r for r in summary if r["name"] == "جهة ملحقة حساب")
    assert main["records"] == 2
    assert main["total_officers"] == 10 + 1 * 3
    assert main["total_individuals"] == 20 + 2 * 3
    assert main["total_recruits"] == 5 + 3 * 3
    assert attached["total_officers"] == 3          # مرة واحدة، لا مضاعفة
    assert totals["officers"] == main["total_officers"] + 3
    assert totals["grand"] == totals["officers"] + totals["individuals"] + totals["recruits"]
    # عدد التأميدات في الإجمالي يُحسب للجهات الأصلية فقط (الملحقة مشاركة لا تأميدة)
    assert totals["records"] == 2


def test_alert_rows_cover_every_day_of_every_record(app):
    """جدول التنبيهات يبني صفًا لكل يوم داخل كل تأميدة (المفروض: كل الأيام)."""
    from data_access import months

    year, month = 2031, 9
    months.init_month(year, month)
    entity_id = dt.add_entity(year, month, "جهة تنبيهات", "شرطية")
    entity = dt.get_entity(year, month, entity_id)
    dt.add_record(year, month, 3, entity, 4, 8, 0, day_to=5)     # ٣ أيام
    dt.add_record(year, month, 10, entity, 2, 3, 0)              # يوم واحد
    rows = tameed_alerts.month_rows(year, month, only_issues=False)
    assert sorted(row["day"] for row in rows) == [3, 4, 5, 10]
    # الجهة غير مسجلة في الكوادر ==> تنبيه «غير مسجلة» على كل يوم
    assert all(any("غير مسجلة" in issue["text"] for issue in row["issues"]) for row in rows)

    # تسجيل قوة + راغبين ليوم واحد ==> يبقى تنبيه النقص على الأيام الأخرى فقط
    ids = [rp.add_person(year, month, entity_id, "officers", f"ضابط تنبيه {i}",
                         rank="ملازم")[0] for i in range(4)]
    ids += [rp.add_person(year, month, entity_id, "individuals", f"فرد تنبيه {i}",
                          rank="جندي")[0] for i in range(8)]
    for person_id in ids:
        rp.set_daily(year, month, person_id, 3, 1)          # يوم ٣ مطابق تمامًا
    for person_id in ids[4:6]:                               # يوم ٤: نقص ضباط فقط
        rp.set_daily(year, month, person_id, 4, 1)
    rows = tameed_alerts.month_rows(year, month, only_issues=True)
    by_day = {row["day"]: row for row in rows}
    assert 3 not in by_day, "اليوم المطابق تمامًا يجب ألا يظهر تنبيهًا"
    assert set(by_day) == {4, 5, 10}
    day4 = " ".join(issue["text"] for issue in by_day[4]["issues"])
    assert "أقل من التأميدة" in day4 and "الناقص" in day4
    day5 = " ".join(issue["text"] for issue in by_day[5]["issues"])
    assert "مفيش راغب واحد مسجل" in day5

    summary = tameed_alerts.summary(year, month)
    assert summary["rows"] == 4 and summary["problem_rows"] == 3


def test_rations_entities_are_pulled_from_their_own_section_only(app):
    """قاعدة الجهات: أصناف الجهة تُسحب من المقرر النشط في قسمها نفسه فقط."""
    from data_access import db_entities as de
    from data_access import months

    year, month = 2031, 9
    months.init_month(year, month)
    dr.set_activation(year, month, "tamween", "summer")
    dr.add_item(year, month, "tamween", "summer", "صنف التموين", "كجم", 1, 2, 3)
    dr.set_activation(year, month, "contractor", "winter")
    dr.add_item(year, month, "contractor", "winter", "صنف المتعهد", "كجم", 4, 5, 6)
    de.add_entity(year, month, "tamween", "جهة التموين")
    de.add_entity(year, month, "contractor", "جهة المتعهد")
    tamween = de.list_entities(year, month, "tamween")[0]
    contractor = de.list_entities(year, month, "contractor")[0]
    assert [item["name"] for item in tamween["items"]] == ["صنف التموين"]
    assert [item["name"] for item in contractor["items"]] == ["صنف المتعهد"]


def test_every_get_page_answers_without_server_error(client, app):
    """تصيّد الأخطاء البرمجية: كل مسارات GET كاملة المعاملات لا تُسقط البرنامج (بلا 5xx).

    التحويلات (302) مقبولة لأن بعض المسارات أفعال (فتح مجلد/ملف، تغيير سياق)،
    و404 الوحيد المتوقع هو شعار الدباجة قبل رفعه — والمهم: لا خطأ خادم داخلي أبدًا.
    """
    checked, bad = 0, []
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: str(r)):
        if "GET" not in (rule.methods - {"HEAD", "OPTIONS"}) or rule.endpoint == "static":
            continue
        if rule.arguments - {"year", "month", "sid"}:
            continue                      # مسارات تحتاج معرّفات كيانات تُختبر منفصلة
        url = str(rule)
        for argument in rule.arguments:
            url = url.replace(f"<{argument}>", "2031" if argument == "year" else "9")
        checked += 1
        response = client.get(url)
        if response.status_code >= 400 and response.status_code != 404:
            bad.append((url, response.status_code))
        elif response.status_code == 404 and url != "/letterhead/logo":
            bad.append((url, response.status_code))
    assert checked > 30, "عدد المسارات المفحوصة أقل من المتوقع"
    assert not bad, bad


def test_new_alerts_and_assistant_surfaces_exist(client):
    """الأسطح الجديدة موجودة فعلًا على الصفحات: جدول التنبيهات + المساعد + مفتاح الألوان."""
    tameedat = client.get("/tameedat?tab=day").get_data(as_text=True)
    assert "al-zone" in tameedat and "تنبيهات التاميدات والراغبين" in tameedat
    raghibin = client.get("/raghibin?tab=daily&d=1").get_data(as_text=True)
    assert "al-zone" in raghibin
    assert "فتح مجلد الراغبين" in raghibin and "فتح إكسل راغبين" in raghibin
    dashboard = client.get("/dashboard").get_data(as_text=True)
    assert "asst-wrap" in dashboard and "themeSwitch" in dashboard
    assert "رئيس قسم التعيينات" in dashboard and "مقدم/ اسامة العجرودى" in dashboard
    assert "رائد/ مصطفى نصرالله" in dashboard
    assert "بيئة المعاينة" not in dashboard and "معاينة ويب" not in dashboard


def test_assistant_answers_greeting_navigation_and_real_numbers(client):
    greeting = client.post("/assistant/ask", data={"q": "السلام عليكم"}).get_json()
    assert greeting["kind"] == "greeting" and "وعليكم السلام" in greeting["reply"]

    navigation = client.post("/assistant/ask", data={"q": "افتح الراغبين"}).get_json()
    assert navigation["kind"] == "nav"
    assert navigation["navigate"].startswith("/raghibin")

    numbers = client.post("/assistant/ask", data={"q": "عدد التأميدات"}).get_json()
    assert numbers["kind"] == "data" and numbers["links"]

    unknown = client.post("/assistant/ask", data={"q": "زلابية بالعسل"}).get_json()
    assert unknown["kind"] == "unknown" and "مساعدة" in unknown["reply"]

    prompts = client.get("/assistant/prompts").get_json()
    assert prompts["ok"] and "مساعدة" in prompts["prompts"]


def test_theme_modes_exist_and_never_touch_printing(client):
    """أوضاع الألوان (كحلي/أبيض/أزرق) موجودة، ومحصورة على الشاشة، والمساعد مخفي في الطباعة."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    css = (root / "static/css/theme-modes.css").read_text(encoding="utf-8")
    assert '@media screen' in css
    for mode in ('[data-theme="white"]', '[data-theme="blue"]'):
        assert mode in css
    assert "--brand-gold" in css and "--bg0" in css
    assistant = (root / "static/css/assistant.css").read_text(encoding="utf-8")
    assert "@media print" in assistant and ".asst-wrap" in assistant
    js = (root / "static/js/theme-mode.js").read_text(encoding="utf-8")
    for mode in ("'slate'", "'white'", "'blue'"):
        assert mode in js
    page = client.get("/dashboard").get_data(as_text=True)
    for mode in ('data-theme-mode="slate"', 'data-theme-mode="white"', 'data-theme-mode="blue"'):
        assert mode in page


def test_raghibin_file_buttons_follow_the_open_day(client):
    """«فتح مجلد الراغبين» يفتح يوم اليوم المفتوح، وزر الإكسل يبني ملف الجهة في يومها."""
    from data_access import db_tameedat as dt
    from data_access import months
    from services.raghibin import files_daily

    # في معاينة الويب: إعلان صريح بالتعذر بدل التظاهر بالنجاح
    folder = client.get("/raghibin/open-folder?d=7", follow_redirects=True)
    body = folder.get_data(as_text=True)
    assert folder.status_code == 200 and "يوم ٧" in body

    # تنزيل ملف اليوم/الجهة يعمل دائمًا (بديل الفتح في المعاينة)
    with client.session_transaction() as session:
        assert session.get("user")
    entity = dt.list_entities(2031, 9) or [None]
    if entity[0]:
        months.init_month(2031, 9)
        response = client.get(f"/raghibin/day-excel?d=7&e={entity[0]['id']}")
        assert response.status_code == 200
        assert response.headers["Content-Disposition"].endswith("raghibin-day7.xlsx\"") or \
            "raghibin-day7.xlsx" in response.headers["Content-Disposition"]
        path = files_daily.day_dir(2031, 9, 7) / f"{entity[0]['name']}.xlsx"
        assert path.is_file()
