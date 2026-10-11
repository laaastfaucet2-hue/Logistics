# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تفاريد الدولى — ورقة الإذن إكسل مطبوعة بالملى (توجيه الخطة ١٠/١٠).

نفس ورقة الإذن جوا البرنامج (templates/dowail/_paper_doc.html) حرفيًا:
ديباجة ٤ أسطر + لوجو + RTL + A4 (add_letterhead) → عنوان «إذن صرف بون
تأريضات» → كتلة المعلومات (القطاع الحرسى/المهلة/القوة/الفترة) → جدول ٧
أعمدة (م/اسم النصف والمادة الخانزية/الوحدة/المعدل اليومي/أيام الصرف/
إجمالي الخطط المخصصة/ملاحظات) → سطر الملاحظات → ٣ توقيعات.
شيت «مجمّع الخط» أولًا ثم شيت لكل نقطة — نفس ترتيب صفحة «طباعة الكل».
الأرقام = fmt_qty (٣ خانات عربية) والحقبة = format_date — بالظبط زي الشاشات.
"""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core import arabic_numbers as arnum
from core import dates
from data_access import db_letterhead as lhdb
from documents.official_xlsx import add_letterhead

NAVY = "132638"   # نص كحلي على أبيض
HEAD = "E9F1F9"   # ازرق فاتح خالص لرؤوس الجدوال (نص أسود عادي)
GRID = Side(style="thin", color="B8B8B8")
BORDER = Border(left=GRID, right=GRID, top=GRID, bottom=GRID)
NC = 7

HEADERS = ["م", "اسم النصف والمادة الخانزية", "الوحدة", "المعدل اليومي",
           "أيام الصرف", "إجمالي الخطط المخصصة", "ملاحظات"]
NOTES = ("هذا الكشف يبين إجمالي أذونات الصرف بين تأريضات المصروفات "
         "({count} نقاط) وورقة نقطة محددة للتحميل.")
def _sig_pairs():
    """التوقيعات الثلاثة — خانتا «أمين العهدة المعتمد» مرتبطتان بالتوقيعين
    الرسميين للدباجة (مستوى المنظومة — نفس صحة/تفاريد)، وخانة المندوب
    المستلم لخط التوقيع الفعلي وقت التسليم (توجيه ١٠/١٠)."""
    s = lhdb.get_signatures()
    return [
        ("أمين العهدة المعتمد",
         f"{s['sig_right_rank']} {s['sig_right_name']}".strip()),
        ("المندوب المستلم", "(..........................)"),
        ("أمين العهدة المعتمد",
         f"{s['sig_left_rank']} {s['sig_left_name']}".strip()),
    ]


def _navy(ws, row, col, value, merge_to=None):
    cell = ws.cell(row, col, value)
    cell.fill = PatternFill("solid", fgColor=HEAD)
    cell.font = Font(name="Arial", size=11, bold=True, color="000000")
    cell.alignment = Alignment(horizontal="center", vertical="center",
                               readingOrder=2, wrap_text=True)
    cell.border = BORDER
    if merge_to:
        ws.merge_cells(start_row=row, start_column=col,
                       end_row=row, end_column=merge_to)
        for c in range(col, merge_to + 1):
            ws.cell(row, c).border = BORDER
            ws.cell(row, c).fill = PatternFill("solid", fgColor=HEAD)
    return cell


def _cell(ws, row, col, value="", bold=False):
    cell = ws.cell(row, col, value)
    cell.font = Font(name="Arial", size=11, bold=bold)
    cell.alignment = Alignment(horizontal="center", vertical="center",
                               readingOrder=2)
    cell.border = BORDER
    return cell


def _q(value):
    """الكمية بثلاث خانات عربية — نفس فلتر qty3 جوا البرنامج."""
    return arnum.fmt_qty(value) if (value not in (None, "", 0)) else arnum.fmt_qty(0)


def _safe_sheet(name):
    return "".join(ch for ch in (name or "") if ch not in "[]:*?/\\")[:31] or "عنصر"


def _uniq_sheet(wb, name):
    name = _safe_sheet(name)
    if name not in wb.sheetnames:
        return name
    i = 2
    while True:
        cand = f"{name[:29]}-{i}"
        if cand not in wb.sheetnames:
            return cand
        i += 1


def _doc_rows(data, line, kind, point=None):
    """أسطر الجدول — نفس بنية line_papers (rate في المجمعة × قوة الخط)."""
    for lp in data.get("papers") or []:
        if lp["line"]["id"] != line["id"]:
            continue
        if kind == "line":
            return lp["line_paper"]["rows"]
        for pp in lp["points_papers"]:
            if point is not None and pp["point"]["id"] == point["id"]:
                return pp["rows"]
    return []


def _write_doc(ws, data, line, kind, point=None):
    """ورقة إذن واحدة: ديباجة → عنوان → معلومات → جدول → ملاحظات → توقيعات."""
    year, month = int(data["year"]), int(data["month"])
    add_letterhead(ws, year, month, NC)
    # العنوان (سطر 7)
    title = ("إذن صرف بون تأريضات مجمّع" if kind == "line"
             else f"إذن صرف بون تأريضات — نقطة «{point['name']}» — خط «{line['name']}»")
    t = ws.cell(7, 1, title)
    ws.merge_cells(start_row=7, start_column=1, end_row=7, end_column=NC)
    t.font = Font(name="Arial", size=16, bold=True, color=NAVY)
    t.alignment = Alignment(horizontal="center", vertical="center", readingOrder=2)
    ws.row_dimensions[7].height = 26
    # كتلة المعلومات (سطور 8-11)
    f, t_ = int(data["date_from"]), int(data["date_to"])
    n_days = len(data.get("dates") or [None]) or int(data.get("issue_days") or 0)
    force = line["total_force"] if kind == "line" else point["force"]
    count = line["count"] if kind == "line" else 1
    sector = line["name"] + " (مجمّع)" if kind == "line" else point["name"]
    meta = [
        f"اسم القطاع الحرسى: {sector}",
        f"القطاع بالمهلة بالضبط: عدد {arnum.to_arabic_indic(str(count))} قطاع",
        f"إجمالي القوة العسكرية: {arnum.to_arabic_indic(str(force))} فرد / يوم",
        (f"فترة بون الصرف والتحصيل: من "
         f"{dates.format_date(f'{year:04d}-{month:02d}-{f:02d}')} إلى "
         f"{dates.format_date(f'{year:04d}-{month:02d}-{t_:02d}')} "
         f"({arnum.to_arabic_indic(str(n_days))} أيام)"),
    ]
    # أسطر التخصيص (لو في) — رقم الإذن/نوع الخط/أرقام الهوية
    pm = data.get("paper_meta") or {}
    if pm.get("paper_no"):
        meta.append(f"رقم الإذن: {pm['paper_no']}")
    if pm.get("line_type"):
        meta.append(f"نوع خط الحراسة: {pm['line_type']}")
    ids = " · ".join(x for x in (pm.get("id_1"), pm.get("id_2"), pm.get("id_3")) if x)
    if ids:
        meta.append(f"أرقام الهوية: {ids}")
    r = 8
    for text in meta:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NC)
        c = ws.cell(r, 1, text)
        c.font = Font(name="Arial", size=11, bold=True)
        c.alignment = Alignment(horizontal="right", vertical="center", readingOrder=2)
        r += 1
    # الجدول (بعد أسطر المعلومات مباشرة)
    hr = r + 1
    for c, name in enumerate(HEADERS, start=1):
        _navy(ws, hr, c, name)
    ws.row_dimensions[hr].height = 22
    r = hr + 1
    for i, row in enumerate(_doc_rows(data, line, kind, point), start=1):
        _cell(ws, r, 1, arnum.to_arabic_indic(str(i)))
        _cell(ws, r, 2, row["name"], bold=True)
        _cell(ws, r, 3, row["unit"] or "—")
        _cell(ws, r, 4, _q(row["rate"]))
        _cell(ws, r, 5, arnum.to_arabic_indic(str(row["days"])))
        _cell(ws, r, 6, _q(row["total"]), bold=True)
        _cell(ws, r, 7, "")
        r += 1
    if r == hr + 1:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NC)
        _cell(ws, r, 1, "لا توجد أصناف مفعّلة — فعّل معدلات من «تعديل معدلات الأصناف».")
        r += 1
    # سطر الملاحظات
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NC)
    note = ws.cell(r, 1, NOTES.format(count=arnum.to_arabic_indic(str(line["count"]))))
    note.font = Font(name="Arial", size=10, bold=True)
    note.alignment = Alignment(horizontal="center", vertical="center", readingOrder=2)
    # التوقيعات الثلاثة (سطران: الاسم ثم التوقيع/الرتبة والاسم الرسمي)
    r += 2
    for (label, val), col in zip(_sig_pairs(), (1, 4, 7)):
        _cell(ws, r, col, label, bold=True)
        _cell(ws, r + 1, col, val)
    for i, w in enumerate([5, 30, 9, 12, 10, 15, 10], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def build_paper_wb(data, year, month):
    """ملف كامل: لكل خط شيت «مجمّع» ثم شيت لكل نقطة (نفس ترتيب الطباعة)."""
    book = Workbook()
    book.remove(book.active)
    for lp in data.get("papers") or []:
        line = lp["line"]
        ws = book.create_sheet(_uniq_sheet(book, f"مجمّع-{line['name']}"))
        _write_doc(ws, data, line, "line")
        for p in line["points"]:
            ws2 = book.create_sheet(_uniq_sheet(book, f"{line['name']}·{p['name']}"))
            _write_doc(ws2, data, line, "point", point=p)
    if not book.sheetnames:
        ws = book.create_sheet("الخطوط")
        add_letterhead(ws, year, month, NC)
        _cell(ws, 7, 1, "لا توجد خطوط — ابدأ من «إدارة الخطوط والنقاط»")
    return book


def build_line_paper_wb(data, line):
    """ورقة خط واحد: شيت «مجمّع» + شيتات نقاطه (للتنزيل من صفحة الورقة)."""
    book = Workbook()
    book.remove(book.active)
    lp = next((x for x in data.get("papers") or [] if x["line"]["id"] == line["id"]),
              None)
    if lp is None:
        return book
    ws = book.create_sheet(_uniq_sheet(book, f"مجمّع-{line['name']}"))
    _write_doc(ws, data, line, "line")
    for p in line["points"]:
        ws2 = book.create_sheet(_uniq_sheet(book, f"{line['name']}·{p['name']}"))
        _write_doc(ws2, data, line, "point", point=p)
    return book


def write_paper_file(path, data, line):
    """كتابة ورقة خط واحد على القرص (مستدعى من حفظ التوزيعة)."""
    build_line_paper_wb(data, line).save(str(path))
