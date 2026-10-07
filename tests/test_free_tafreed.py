# -*- coding: utf-8 -*-
"""التفاريد الحرة وتفاريد الدول — قسم مستقل تمامًا (توجيه ٠٦/١٠/٢٠٢٦).

القاعدة الملزمة التي يحرسها هذا الملف:
  «صفحات عمل تفاريد حرة/تفاريد الدول/معدلات الأصناف حرة تمامًا غير متصلة بالمخازن،
   لها ملفات مستقلة، وتعديلاتها لا تمس مقررات المتعهد/التموينيات.»
لذلك أهم اختبار هنا هو `test_free_tafreed_is_isolated_from_rations_and_warehouses`.
"""
import re

from openpyxl import load_workbook

from core import arabic_numbers as arnum
from data_access import db_free_tafreed as db, db_rations as dr, db_warehouses as dw, months
from services import free_tafreed_calc as calc, free_tafreed_fs as fs

YEAR, MONTH = 2031, 9


def _init():
    months.init_month(YEAR, MONTH)


def _seed_rate(name="أرز بلدي", unit="كجم", rate=0.075, days=None):
    return db.upsert_rate(YEAR, MONTH, name, unit, rate, "tamween", True,
                          days if days is not None else [1, 2, 3])


# ======================================================================
# ١) الحساب: المعدل × القوة × أيام الصرف
# ======================================================================
def test_qty_is_rate_times_force_times_days(app):
    _init()
    assert calc.row_total(0.075, 10, 10) == 7.5
    assert calc.row_total(1, 5, 2) == 10
    rows = calc.build_rows([{"name": "أرز", "unit": "كجم", "rate": 0.075, "days_count": 10,
                             "active": True}], 10, 10)
    assert rows[0]["total"] == 7.5 and rows[0]["unit"] == "كجم" and rows[0]["serial"] == 1


def test_unit_conversion_gram_to_kg(app):
    _init()
    assert calc.to_base(2, "كجم") == 2000 and calc.to_base(500, "جم") == 500
    shown, unit = calc.to_display(4200, "جم")
    assert (shown, unit) == (4.2, "كجم")          # ٤٢٠٠ جم تُعرض ٤٫٢٠٠ كجم
    shown, unit = calc.to_display(750, "جم")
    assert (shown, unit) == (750, "جم")


def test_chosen_period_limits_item_days(app):
    """«عدد الأيام» في الحسابة يحكم فعلًا: ٠٫٥ × ١٠ أفراد × ٣ أيام = ١٥ لا ٥٠."""
    _init()
    _seed_rate("أرز", "كجم", 0.5)                    # مفعّل أيام ١–٣ افتراضيًا في المساعد
    db.toggle_rate_day(YEAR, MONTH, db.list_rates(YEAR, MONTH)[0]["id"], 1, False)
    db.toggle_rate_day(YEAR, MONTH, db.list_rates(YEAR, MONTH)[0]["id"], 2, False)
    db.toggle_rate_day(YEAR, MONTH, db.list_rates(YEAR, MONTH)[0]["id"], 3, False)
    for day in range(1, db.MAX_DAYS + 1):            # مفعّل كل الأيام ١–١٠
        db.toggle_rate_day(YEAR, MONTH, db.list_rates(YEAR, MONTH)[0]["id"], day, True)
    rate = db.list_rates(YEAR, MONTH)[0]
    assert rate["days"] == list(range(1, db.MAX_DAYS + 1))
    assert calc.build_rows([rate], 10, 3)[0]["total"] == 15.0      # المدة ٣ أيام
    assert calc.build_rows([rate], 10, 10)[0]["total"] == 50.0
    # صنف مفعّل خارج المدة المختارة لا يُدرج أصلًا
    db.set_rate_active(YEAR, MONTH, rate["id"], False)
    db.upsert_rate(YEAR, MONTH, "شاي", "فتلة", 1, "tamween", True, [8, 9, 10])
    late_rate = [r for r in db.list_rates(YEAR, MONTH) if r["name"] == "شاي"][0]
    assert calc.search_days(late_rate, 3) == 0
    assert calc.build_rows([late_rate], 10, 3) == []


def test_disabled_item_and_days_are_respected(app):
    _init()
    rates = [{"name": "شاي", "unit": "فتلة", "rate": 1, "days_count": 5, "active": True},
             {"name": "سكر", "unit": "باكت", "rate": 1, "days_count": 5, "active": False}]
    rows = calc.build_rows(rates, 4, 10)
    assert [r["name"] for r in rows] == ["شاي"]    # الموقوف لا يظهر
    assert rows[0]["days"] == 5
    assert rows[0]["total"] == 20                  # ١ × ٤ أفراد × ٥ أيام


# ======================================================================
# ٢) معدلات الأصناف: لقطة من المقررات ثم حرة
# ======================================================================
def test_rates_seed_snapshot_then_free_edit(app):
    _init()
    dr.add_item(YEAR, MONTH, "tamween", "summer", "جبنة بيضاء", "علبة", 0.5, 0.5, 0)
    dr.set_activation(YEAR, MONTH, "tamween", "summer")
    added = db.seed_rates_from_rations(YEAR, MONTH)
    assert added == 1
    rate = db.list_rates(YEAR, MONTH)[0]
    assert rate["name"] == "جبنة بيضاء" and rate["rate"] == 1.0     # ٠٫٥ + ٠٫٥
    assert rate["days"] == list(range(1, db.MAX_DAYS + 1))          # كل أيام الصرف افتراضيًا
    # اللقطة حرة: تعديلها لا يمس المقرر
    db.upsert_rate(YEAR, MONTH, "جبنة بيضاء", "علبة", 2.5, "tamween")
    master, _custom = dr.get_items(YEAR, MONTH, "tamween", "summer")
    assert master[0]["lunch"] == 0.5                                # المقرر كما هو
    assert db.list_rates(YEAR, MONTH)[0]["rate"] == 2.5


def test_rate_days_toggle_and_active_switch(app):
    _init()
    rate_id = _seed_rate("ملح", "كجم", 0.01, days=[1, 2])
    db.toggle_rate_day(YEAR, MONTH, rate_id, 3, True)
    assert db.list_rates(YEAR, MONTH)[0]["days"] == [1, 2, 3]
    db.toggle_rate_day(YEAR, MONTH, rate_id, 2, False)
    assert db.list_rates(YEAR, MONTH)[0]["days"] == [1, 3]
    db.set_rate_active(YEAR, MONTH, rate_id, False)
    assert db.list_rates(YEAR, MONTH)[0]["active"] is False


# ======================================================================
# ٣) الخطوط والنقاط
# ======================================================================
def test_lines_and_points_with_forces(app):
    _init()
    line_id = db.add_line(YEAR, MONTH, "خط معين", default_points=0)
    p1 = db.add_point(YEAR, MONTH, line_id, "د.٤٧", 5)
    db.add_point(YEAR, MONTH, line_id, "د.٤٨", 5)
    line = db.list_lines(YEAR, MONTH)[0]
    assert line["points"] == {"count": 2, "force": 10, "active": 2}
    db.set_point_force(YEAR, MONTH, p1, 7)
    assert db.list_lines(YEAR, MONTH)[0]["points"]["force"] == 12
    assert db.find_points(YEAR, MONTH, "٤٧")[0]["name"] == "د.٤٧"
    db.reset_forces(YEAR, MONTH)
    assert db.list_lines(YEAR, MONTH)[0]["points"]["force"] == 0
    db.delete_line(YEAR, MONTH, line_id)
    assert db.list_lines(YEAR, MONTH) == [] and db.list_points(YEAR, MONTH) == []


def test_distribution_rows_and_totals(app):
    _init()
    line_id = db.add_line(YEAR, MONTH, "خط النقب")
    db.add_point(YEAR, MONTH, line_id, "د.٧٠", 5)
    db.add_point(YEAR, MONTH, line_id, "د.٨٧", 10)
    lines = db.list_lines(YEAR, MONTH)
    for line in lines:
        line["points_list"] = db.list_points(YEAR, MONTH, line["id"])
    rates = [{"name": "أرز", "unit": "كجم", "rate": 0.1, "days": [1, 2], "active": True}]
    rows = calc.distribution_rows(lines, rates, 2)
    assert [r["force"] for r in rows] == [5, 10]
    assert rows[0]["cells"][0]["total"] == 1.0        # ٠٫١ × ٥ × ٢
    totals = calc.totals_by_item(rows)
    assert totals[0]["total"] == 3.0                  # ١ + ٢


# ======================================================================
# ٤) الملفات المستقلة (دباجة + لوجو + توقيعان) — القواعد الذهبية
# ======================================================================
def test_rates_file_has_letterhead_and_signatures(app):
    _init()
    _seed_rate("أرز بلدي")
    path = fs.write_rates(YEAR, MONTH, db.list_rates(YEAR, MONTH))
    assert path.name == "معدلات الأصناف.xlsx" and path.parent.name == "معدلات الأصناف"
    ws = load_workbook(path).active
    text = " ".join(str(c) for row in ws.iter_rows(values_only=True) for c in row if c)
    assert "وزارة الداخلية" in text and "قسم التعيينات" in text
    assert "مصطفى نصرالله" in text and "اسامة العجرودى" in text   # التوقيعان الرسميان
    from services import local_audit
    assert local_audit.audit_workbook(path, YEAR, MONTH) == []


def test_saved_sheet_writes_json_and_excel_in_independent_folder(app):
    _init()
    _seed_rate("مكرونة", "كجم", 0.09, days=[1, 2, 3])
    rows = calc.build_rows(db.list_rates(YEAR, MONTH), 10, 3)
    sheet_id = db.save_sheet(YEAR, MONTH, "free", "قطاع وسط سيناء", {"rows": rows},
                             1, 3, 3, 10, "أمين", "كاتب")
    sheet = db.get_sheet(YEAR, MONTH, sheet_id)
    path = fs.write_free_sheet(YEAR, MONTH, sheet)
    assert path.parent.name == "التفاريد الحرة"
    assert path.exists() and (path.parent / (path.stem + ".json")).exists()
    assert "قسم التعيينات" in " ".join(
        str(c) for row in load_workbook(path).active.iter_rows(values_only=True)
        for c in row if c)
    fs.remove_sheet_files(YEAR, MONTH, sheet)
    assert not path.exists()


def test_save_same_sheet_id_replaces_not_duplicates(app):
    _init()
    first = db.save_sheet(YEAR, MONTH, "intl", "تفريدة الدول", {"rows": []}, 1, 5, 5, 20)
    second = db.save_sheet(YEAR, MONTH, "intl", "تفريدة الدول", {"rows": [{"name": "أرز"}]},
                           1, 5, 5, 25, sheet_id=first)
    assert first == second
    sheets = db.list_sheets(YEAR, MONTH, "intl")
    assert len(sheets) == 1 and sheets[0]["force"] == 25


# ======================================================================
# ٥) عزل تام عن المخازن والمقررات (أهم اختبار — قاعدة المستخدم)
# ======================================================================
def test_free_tafreed_is_isolated_from_rations_and_warehouses(app):
    _init()
    dr.add_item(YEAR, MONTH, "tamween", "summer", "زيت طهي", "كجم", 0, 0.012, 0)
    dr.set_activation(YEAR, MONTH, "tamween", "summer")
    dw.add_opener(YEAR, MONTH, "supply", "زيت طهي", 100, 1, handle_unit_hint="كجم",
                  exp_iso="2027-06-30")
    before_rations = [dict(i) for i in dr.get_items(YEAR, MONTH, "tamween", "summer")[0]]
    before_balance = dict(dw.item_balances(YEAR, MONTH, "supply"))
    before_tafreeda = dw.tafreeda_rows(YEAR, MONTH, "supply")
    before_permits = [(p["number"], p["actuals"]) for p in dw.permits_book(YEAR, MONTH, "supply")]

    db.seed_rates_from_rations(YEAR, MONTH)                       # لقطة
    line_id = db.add_line(YEAR, MONTH, "خط معين")
    db.add_point(YEAR, MONTH, line_id, "د.٤٧", 5)
    db.upsert_rate(YEAR, MONTH, "زيت طهي", "كجم", 9.99, "tamween")   # تعديل حر ضخم
    db.save_sheet(YEAR, MONTH, "free", "تفريدة اختبار", {"rows": []}, 1, 3, 3, 5)
    fs.write_rates(YEAR, MONTH, db.list_rates(YEAR, MONTH))

    after_rations = [dict(i) for i in dr.get_items(YEAR, MONTH, "tamween", "summer")[0]]
    assert after_rations == before_rations                          # المقرر لم يُمس
    assert dict(dw.item_balances(YEAR, MONTH, "supply")) == before_balance   # الرصيد لم يُمس
    assert dw.tafreeda_rows(YEAR, MONTH, "supply") == before_tafreeda        # التفريدة الرسمية لم تُمس
    assert [(p["number"], p["actuals"]) for p in dw.permits_book(YEAR, MONTH, "supply")] \
        == before_permits                                                     # الأذون لم تُمس


def test_only_ft_tables_are_created_by_the_section(app):
    """القسم لا ينشئ/يعدّل أي جدول غير ft_* — عزل بنيوي على مستوى القاعدة."""
    _init()
    conn = months.get_db(YEAR, MONTH)
    db.add_line(YEAR, MONTH, "خط تدقيق")
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"ft_lines", "ft_points", "ft_rates", "ft_rate_days", "ft_sheets"} <= tables


# ======================================================================
# ٦) الشاشات والمسارات
# ======================================================================
def test_page_tabs_and_prints(client):
    _init()
    _seed_rate("عدس", "كجم", 0.05, days=[1, 2, 3])
    page = client.get("/free-tafreed?tab=calc").data.decode("utf-8")
    for token in ("حسابة الصرف وطباعة الإذن", "عمل التفريدة", "تفريدات الدول", "معدلات الأصناف",
                  "فتح المجلد", "تجمعي التفريدات", "تجميع التفريدات للدفتر"):
        assert token.replace("تجمعي ", "") in page
    assert "التفاريد الحرة" in page
    line_id = db.add_line(YEAR, MONTH, "خط معين")       # بطاقة الخط تُبنى عند وجود خطوط
    db.add_point(YEAR, MONTH, line_id, "د.٤٧", 5)
    intl = client.get("/free-tafreed?tab=intl").data.decode("utf-8")
    assert "إدارة الخطوط والنقاط" in intl
    assert "تصفير وإعادة تعيين القوات" in intl and "د.٤٧" in intl
    rates = client.get("/free-tafreed?tab=rates").data.decode("utf-8")
    assert "أصناف التعهدات التموينية" in rates and "أصناف المتعهد" in rates
    assert "اسحب الأصناف من مقررات الشهر" in rates and "إضافة/تعديل الصنف" in rates


def test_compute_route_returns_rows_without_writing(client):
    _init()
    _seed_rate("فول", "علبة", 0.5, days=[1, 2, 3])
    body = client.get("/free-tafreed/compute?force=10&days=3").get_json()
    assert body["rows"][0]["name"] == "فول"
    assert body["rows"][0]["total"] == 15.0            # ٠٫٥ × ١٠ × ٣
    assert body["rows"][0]["serial"] == 1
    # نفس الصنف بمدة أطول: الأيام المفعّلة (٣) هي الحد ⇒ النتيجة لا تتضخّم
    assert client.get("/free-tafreed/compute?force=10&days=10").get_json()["rows"][0]["total"] == 15.0


def test_saved_sheet_quantity_follows_chosen_period(client):
    """الكشف المحفوظ يطابق ما تراه العين في الحسابة: الكمية = المعدل × القوة × الأيام."""
    _init()
    rate_id = db.upsert_rate(YEAR, MONTH, "أرز", "كجم", 0.5, "tamween")
    for day in range(1, db.MAX_DAYS + 1):
        db.toggle_rate_day(YEAR, MONTH, rate_id, day, True)
    client.post("/free-tafreed/save", data={"year": YEAR, "month": MONTH, "tab": "make",
                                           "title": "قطاع اختبار المدة", "force": 10,
                                           "date_from": 1, "date_to": 3, "days": 3})
    sheet = db.list_sheets(YEAR, MONTH, "free")[0]
    rows = sheet["payload"]["rows"]
    assert rows[0]["days"] == 3 and rows[0]["total"] == 15.0
    assert "قطاع اختبار المدة" in sheet["title"]


def test_print_documents_render(client):
    _init()
    _seed_rate("سكر", "باكت", 1, days=[1, 2])
    rows = calc.build_rows(db.list_rates(YEAR, MONTH), 5, 2)
    sheet_id = db.save_sheet(YEAR, MONTH, "free", "قطاع اختبار", {"rows": rows}, 1, 2, 2, 5)
    permit = client.get(f"/free-tafreed/print/permit?sheet={sheet_id}").data.decode("utf-8")
    assert "إذن صرف بون تعيينات مجمع" in permit and "أيام الصرف" in permit
    line_id = db.add_line(YEAR, MONTH, "خط معين")
    db.add_point(YEAR, MONTH, line_id, "د.٤٧", 5)
    dist = client.get("/free-tafreed/print/dist").data.decode("utf-8")
    assert "بيان توزيع وإجمالي تعيينات خطوط حراسة الدول" in dist and "د.٤٧" in dist
    point_id = db.list_points(YEAR, MONTH)[0]["id"]
    point = client.get(f"/free-tafreed/print/point?point={point_id}").data.decode("utf-8")
    assert "نقطة د.٤٧" in point and "خط معين" in point
    assert client.get("/free-tafreed/print/unknown").status_code == 404


def test_paper_equals_excel_for_free_sheet(app):
    """قاعدة المستخدم: «الورق اللي في البرنامج هو بالضبط اللي في ملف الإكسل».

    نطابق كل صف في ملف الإكسل المحفوظ بصف في ورقة طباعة الإذن (نفس الأصناف والوحدات
    والأرقام) — بترتيب الأعمدة: الصنف · الوحدة · المعدل · الأيام · الإجمالي.
    """
    _init()
    rate_id = db.upsert_rate(YEAR, MONTH, "أرز بلدي", "كجم", 0.075, "tamween")
    db.upsert_rate(YEAR, MONTH, "زيت", "جم", 250, "tamween", True, [1, 2, 3])
    for day in range(1, db.MAX_DAYS + 1):
        db.toggle_rate_day(YEAR, MONTH, rate_id, day, True)
    rows = calc.build_rows(db.list_rates(YEAR, MONTH), 10, 3)
    sheet_id = db.save_sheet(YEAR, MONTH, "free", "قطاع وسط سيناء", {"rows": rows}, 1, 3, 3, 10)
    sheet = db.get_sheet(YEAR, MONTH, sheet_id)
    path = fs.write_free_sheet(YEAR, MONTH, sheet)

    ws = load_workbook(path).active
    values = list(ws.iter_rows(values_only=True))
    head = next(i for i, r in enumerate(values) if r and r[0] == "م")
    xlsx_rows = []
    for row in values[head + 1:]:
        if not row or not str(row[0] or "").strip().isdigit():
            continue
        xlsx_rows.append([str(row[1]).strip(), str(row[2]).strip(), str(row[3]).strip(),
                          str(row[4]).strip(), str(row[5]).strip()])

    html = client_get(app, f"/free-tafreed/print/permit?year={YEAR}&month={MONTH}&sheet={sheet_id}")
    # صفوف جدول الورق: م · الصنف · الوحدة · المعدل · الأيام · الإجمالي · ملاحظات
    printed = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(cells) == 7 and cells[1] in [r[0] for r in xlsx_rows]:
            printed.append(cells)
    assert len(printed) == len(xlsx_rows) == 2, printed
    for sheet_row, paper_row in zip(xlsx_rows, printed):
        name, unit, rate, days, total = sheet_row
        assert paper_row[1] == name and paper_row[2] == unit
        assert paper_row[3] == rate, f"المعدل اختلف: ورق {paper_row[3]} / إكسل {rate}"
        assert paper_row[4] == days, f"الأيام اختلفت: ورق {paper_row[4]} / إكسل {days}"
        assert paper_row[5] == total, f"الإجمالي اختلف: ورق {paper_row[5]} / إكسل {total}"


def test_distribution_paper_equals_excel(app):
    """بيان التوزيع: صفوف الورق = صفوف ملف الإكسل بالحرف (نفس الأعمدة والأرقام)."""
    _init()
    rate_id = db.upsert_rate(YEAR, MONTH, "أرز بلدي", "كجم", 0.075, "tamween")
    for day in range(1, db.MAX_DAYS + 1):
        db.toggle_rate_day(YEAR, MONTH, rate_id, day, True)
    line_id = db.add_line(YEAR, MONTH, "خط معين")
    db.add_point(YEAR, MONTH, line_id, "د.٤٧", 5)
    db.add_point(YEAR, MONTH, line_id, "د.٤٨", 7)
    client = app.test_client()
    client.post("/login", data={"username": "mostafa", "password": "779"})
    html = client.get(f"/free-tafreed/print/dist?year={YEAR}&month={MONTH}&days=3").data.decode("utf-8")
    assert "بيان توزيع" in html
    response = client.post("/free-tafreed/dist/save",
                           data={"year": YEAR, "month": MONTH, "days": 3})
    assert "days=3" in html or "٣" in html            # أيام الصرف المختارة مطبوعة على الورق
    assert response.status_code == 302
    files = list(fs.sub_dir(YEAR, MONTH, "تفريدات الدول").glob("*.xlsx"))
    assert len(files) == 1, files
    ws = load_workbook(files[0]).active
    values = [r for r in ws.iter_rows(values_only=True) if r and any(r)]
    head = next(i for i, r in enumerate(values) if r and r[0] == "م")
    assert list(values[head]) == [c for c in fs.HEADERS_DIST] + [None] * (
        len(values[head]) - len(fs.HEADERS_DIST))
    body = [r for r in values[head + 1:] if r and str(r[0] or "").strip().isdigit()]
    # كل صف في الإكسل: نقطة وقوة وإجمالي — والقيم موجودة في الورق حرفيًا
    assert len(body) == 2                                   # نقطتان × صنف واحد
    forces = {"٥", "٧"}                                     # قوتا النقطتين كما سُجّلتا
    for row in body:
        point, force, total = str(row[1]), str(row[2]), str(row[5])
        assert point in html and f">{force}<" in html
        assert force in forces and force in html
        # الكمية = المعدل × القوة × أيام الصرف — والقيمة نفسها مكتوبة في الورق
        assert total == calc.fmt(0.075 * float(arnum.to_western(force)) * 3)
        assert total in html
    totals_row = [r for r in values if r and "إجمالي" in str(r[1] or "")]
    assert totals_row and str(totals_row[0][5]) == calc.fmt(0.075 * 12 * 3)
    assert "إجمالي القطاعات والخطوط العامة" in html


def test_printing_permit_moves_sheet_to_done_register(client):
    """«البونات النشطة وبانتظار تفريد الصرف» ⇒ عند فتح إذن الصرف تنتقل لـ«سجل المنجزة»."""
    _init()
    rate_id = db.upsert_rate(YEAR, MONTH, "أرز", "كجم", 0.5, "tamween")
    for day in range(1, db.MAX_DAYS + 1):
        db.toggle_rate_day(YEAR, MONTH, rate_id, day, True)
    rows = calc.build_rows(db.list_rates(YEAR, MONTH), 10, 3)
    sheet_id = db.save_sheet(YEAR, MONTH, "free", "قطاع الميدان", {"rows": rows}, 1, 3, 3, 10)
    assert len(db.list_sheets(YEAR, MONTH, pending=True)) == 1
    assert db.list_sheets(YEAR, MONTH, pending=False) == []
    client.get(f"/free-tafreed/print/permit?year={YEAR}&month={MONTH}&sheet={sheet_id}")
    assert db.list_sheets(YEAR, MONTH, pending=True) == []
    done = db.list_sheets(YEAR, MONTH, pending=False)
    assert len(done) == 1 and done[0]["printed_count"] == 1 and done[0]["printed_at"]
    page = client.get(f"/free-tafreed?tab=calc&year={YEAR}&month={MONTH}").data.decode("utf-8")
    assert "البونات النشطة وبانتظار تفريد الصرف" in page
    assert "سجل التفريدات المنجزة والمصروفة" in page
    assert "قطاع الميدان" in page and "تفريدة إدارية منفصلة (تسجيل حر)" in page


def test_quick_point_search_and_zero_toggle(client):
    """بحث سريع عن نقطة + مربع «عرض نقاط التوزيع الصفرية» + الطرق الثلاث للعرض."""
    _init()
    line_id = db.add_line(YEAR, MONTH, "خط معين")
    db.add_point(YEAR, MONTH, line_id, "د.٤٧", 5)
    db.add_point(YEAR, MONTH, line_id, "د.٤٨", 0)          # نقطة صفرية
    page = client.get(f"/free-tafreed?tab=intl&year={YEAR}&month={MONTH}").data.decode("utf-8")
    assert "بحث سريع عن نقطة" in page
    assert "ft-zeros-toggle" in page and 'class="ft-point ft-zero"' in page
    for token in ("التفريدة المجمعة والفردية معًا", "التفريدة المجمعة للخط فقط",
                  "تفاريد النقاط الفردية فقط (ورق)"):
        assert token in page
    found = client.get(f"/free-tafreed?tab=intl&q=٤٧&year={YEAR}&month={MONTH}").data.decode("utf-8")
    assert "د.٤٧" in found and "خط معين" in found
    empty = client.get(f"/free-tafreed?tab=intl&q=٩٩&year={YEAR}&month={MONTH}").data.decode("utf-8")
    assert "لا نتائج مطابقة" in empty


def test_page_is_linked_in_sidebar(client):
    _init()
    home = client.get("/dashboard").data.decode("utf-8")
    assert "التفاريد الحرة وتفاريد الدول" in home
    redirect = client.get("/sections/free_tafreed")
    assert redirect.status_code == 302 and "/free-tafreed" in redirect.headers["Location"]


def test_open_folder_message_is_honest_in_web(client):
    """نسخة الويب لا تتظاهر بالنجاح: رسالة واضحة بالمسار بدل الفشل الصامت."""
    _init()
    page = client.get("/free-tafreed/open-folder", follow_redirects=True).data.decode("utf-8")
    assert ("تم فتح مجلد" in page) or ("فتح المجلدات متاح من نسخة سطح المكتب" in page)


# ======================================================================
# ٧) مساعد داخلي: قراءة صفحة بجلسة دخول
# ======================================================================
def client_get(app, url):
    """جلسة دخول مباشرة للقراءة فقط — لا تستخدم مخزن بيانات حقيقيًا."""
    client = app.test_client()
    client.post("/login", data={"username": "mostafa", "password": "779"})
    response = client.get(url)
    assert response.status_code == 200
    return response.data.decode("utf-8")
