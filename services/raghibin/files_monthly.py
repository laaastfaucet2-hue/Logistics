# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""ملفات «3. تجميع الكشف الشهري العام/» — كشف وجبات الشهر لكل جهة.

قرار المستخدم ٣٠/٠٩/٢٠٢٦: وجبة واحدة لليوم، والكشف بالإجمالي فقط
(م | الرتبة والاسم الكامل | عدد الوجبات) — زي صورة نظامه.
ملف واحد لكل جهة «<الجهة>.xlsx» شيتان: «الضباط» و«الأفراد والصف»،
كل شيت: كل الأسماء غير المستثناءة (حتى صفر وجبة) بالأقدمية +
صف «إجمالي X فرد — إجمالي الوجبات: Y وجبة» + الدباجة والتوقيعان.
يُبنى لحظيًا بعد كل علامة يومية (بناء مستهدف لملف الجهة).
"""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from core import arabic_numbers as arnum
from core.config import MONTH_NAMES
from data_access import dataguard
from data_access import db_raghibin as dr
from documents.official_xlsx import add_letterhead

from . import signatures_rows, tab_dir

CENTER = Alignment(horizontal="center", vertical="center", readingOrder=2)
HEADERS = ["م", "الرتبة والاسم الكامل", "عدد الوجبات"]
COLS = len(HEADERS)


def _sheet(ws, year, month, entity_name, category_label, persons, meals):
    add_letterhead(ws, year, month, COLS)
    ws.merge_cells(start_row=6, start_column=1, end_row=6, end_column=COLS)
    title = ws.cell(6, 1, f"تجميع الكشف الشهري العام — {category_label} — {entity_name} — "
                          f"{MONTH_NAMES[month - 1]} {arnum.to_arabic_indic(year)}")
    title.font = Font(name="Cairo", size=13, bold=True, color="132638")
    title.alignment = CENTER
    ws.row_dimensions[6].height = 22
    from core import labels
    legend = ws.cell(5, 1, labels.LEGEND_TWO)
    legend.font = Font(name="Cairo", size=10, color="6B7280")
    legend.alignment = CENTER
    for col, name in enumerate(HEADERS, start=1):
        cell = ws.cell(7, col, name)
        cell.font = Font(name="Cairo", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="132638")
        cell.alignment = CENTER
        ws.column_dimensions["A"].width = 8
        ws.column_dimensions["B"].width = 46
        ws.column_dimensions["C"].width = 16
    ws.row_dimensions[7].height = 20
    row = 8
    total_meals = 0
    for serial, person in enumerate(persons, start=1):
        count = meals.get(person["id"], 0)
        total_meals += count
        values = [arnum.to_arabic_indic(str(serial)),
                  f"{person['rank'] + ' / ' if person['rank'] else ''}{person['full_name']}",
                  arnum.to_arabic_indic(str(count))]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row, col, value)
            cell.alignment = CENTER
            cell.font = Font(size=11, name="Cairo", bold=(col == 2))
            if row % 2 == 0:
                cell.fill = PatternFill("solid", fgColor="F4F6FB")
        row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=COLS)
    total = ws.cell(row, 1, f"إجمالي {arnum.to_arabic_indic(str(len(persons)))} فرد | "
                            f"إجمالي الوجبات: {arnum.to_arabic_indic(str(total_meals))} وجبة")
    total.font = Font(size=12, name="Cairo", bold=True)
    total.alignment = CENTER
    signatures_rows(ws, row + 2, year, month, COLS)
    return total_meals


def write_monthly_file(year, month, entity_id, entity_name):
    """بناء/تحديث كشف التجميع الشهري لجهة واحدة (شيتا ضباط وأفراد)."""
    folder = tab_dir(year, month, "monthly")
    meals = dr.month_meals(year, month, entity_id)
    book = Workbook()
    book.remove(book.active)
    for category_key, category_label in (("officers", "ض — الضباط"),
                                         ("individuals", "أ — الأفراد والصف")):
        persons = dr.list_persons(year, month, entity_id=entity_id,
                                  category=category_key, excluded=False)
        ws = book.create_sheet(category_label)
        _sheet(ws, year, month, entity_name, category_label, persons, meals)
    path = folder / f"{entity_name}.xlsx"
    dataguard.atomic_save(book.save, str(path))
    return path
