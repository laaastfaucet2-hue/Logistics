# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""ملفات «1. (يومي) الراغبين/يوم N/<الجهة>.xlsx» — القوة كلها بعلامات اليوم.

قرار المستخدم ٣٠/٠٩/٢٠٢٦: ملف اليوم يعرض القوة كلها (ضباط ثم أفراد) بالترتيب
مع علامة راغب ✓ / لا ✗ والمستثنى ⊘ بلون مميز، وصف الإجمالي في الآخر.
بناء مستهدف: كل علامة تُحدّث ملف يوم+جهة واحد فقط عبر atomic_save (<١ ثانية)،
ولو الملف مفتوح عند المستخدم يتحدث أول ما يتقفل (live-sync الموجود).
"""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from core import arabic_numbers as arnum
from core import egtime
from core.config import MONTH_NAMES
from data_access import dataguard
from data_access import db_raghibin as dr
from documents.official_xlsx import add_letterhead

from . import FILL_EXCLUDED, signatures_rows, tab_dir

FILL_WILLING = "E8F5EE"
CENTER = Alignment(horizontal="center", vertical="center", readingOrder=2)
HEADERS = ["م", "الرتبة", "الاسم الرتبعي الكامل", "الفئة", "حالة اليوم", "ملاحظات"]
COLS = len(HEADERS)


def day_dir(year, month, day):
    """فولدر «يوم N» بأرقام عربية (نفس تسمية فولدرات التأميدات)."""
    path = tab_dir(year, month, "daily") / "يوم {}".format(arnum.to_arabic_indic(str(day)))
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_day_folders(year, month):
    """فولدرات «يوم ١..آخر الشهر» تتولد من أول الشهر (بلا ملفات — تُبنى عند التسجيل)."""
    root = tab_dir(year, month, "daily")
    for day in range(1, egtime.days_in_month(year, month) + 1):
        (root / "يوم {}".format(arnum.to_arabic_indic(str(day)))).mkdir(exist_ok=True)
    return root


def _signatures(ws, row, year, month):
    """التوقيعان الرسميان — ديليجيت للمشترك في الحزمة."""
    signatures_rows(ws, row, year, month, COLS)


def write_day_file(year, month, day, entity_id, entity_name):
    """بناء/تحديث ملف جهة واحد داخل يومه — يُستدعى بعد كل علامة (بناء مستهدف)."""
    folder = day_dir(year, month, day)
    persons = dr.list_persons(year, month, entity_id=entity_id)   # ضباط ثم أفراد
    state = dr.day_state(year, month, day, entity_id)
    book = Workbook()
    ws = book.active
    ws.title = "يوم {}".format(arnum.to_arabic_indic(str(day)))
    add_letterhead(ws, year, month, COLS)
    ws.merge_cells(start_row=6, start_column=1, end_row=6, end_column=COLS)
    title = ws.cell(6, 1, f"الراغبين في وجبة الطعام — يوم "
                          f"{arnum.to_arabic_indic(str(day))} — {entity_name} — "
                          f"{MONTH_NAMES[month - 1]} {arnum.to_arabic_indic(year)}")
    title.font = Font(name="Cairo", size=13, bold=True, color="132638")
    title.alignment = CENTER
    ws.row_dimensions[6].height = 22
    for col, name in enumerate(HEADERS, start=1):
        cell = ws.cell(7, col, name)
        cell.font = Font(name="Cairo", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="132638")
        cell.alignment = CENTER
        ws.column_dimensions[chr(64 + col)].width = max(12, len(name) * 2 + 6)
    ws.row_dimensions[7].height = 20
    row = 8
    serial = 0
    counts = {"officers": [0, 0], "individuals": [0, 0]}   # [راغبين, إجمالي الفئة]
    for person in persons:
        key = person["category"] if person["category"] in counts else "individuals"
        counts[key][1] += 1
        serial += 1
        if person["excluded"]:
            mark, fill = "⊘ غير راغب", FILL_EXCLUDED
        elif state.get(person["id"]):
            mark, fill = "✓ راغب بالوجبة", FILL_WILLING
            counts[key][0] += 1
        else:
            mark, fill = "✗ لا", None
        category_label = "ضابط" if person["category"] == "officers" else "فرد"
        values = [arnum.to_arabic_indic(str(serial)), person["rank"] or "—",
                  person["full_name"], category_label, mark,
                  person["exclude_note"] if person["excluded"] else ""]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row, col, value)
            cell.alignment = CENTER
            cell.font = Font(size=11, name="Cairo", bold=(col == 3))
            if fill:
                cell.fill = PatternFill("solid", fgColor=fill)
        row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=COLS)
    total = ws.cell(row, 1,
                    f"الإجمالي: {arnum.to_arabic_indic(str(counts['officers'][0] + counts['individuals'][0]))} "
                    f"راغبون من أصل {arnum.to_arabic_indic(str(len(persons)))} "
                    f"(ضباط {arnum.to_arabic_indic(str(counts['officers'][0]))} من "
                    f"{arnum.to_arabic_indic(str(counts['officers'][1]))} — أفراد "
                    f"{arnum.to_arabic_indic(str(counts['individuals'][0]))} من "
                    f"{arnum.to_arabic_indic(str(counts['individuals'][1]))})")
    total.font = Font(size=12, name="Cairo", bold=True)
    total.alignment = CENTER
    _signatures(ws, row + 2, year, month)
    path = folder / f"{entity_name}.xlsx"
    dataguard.atomic_save(book.save, str(path))   # ذرّي + لحظي لو الملف مفتوح
    return path
