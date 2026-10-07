# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تقرير المناسبة الرسمي (Excel + Word) — دباجة الشهر + اللوجو + التوقيعان.

يُبنى داخل فولدر المناسبة نفسه: `التقرير.xlsx` و`التقرير.docx` — والقاعدة الذهبية
(توجيه ٠٦/١٠/٢٠٢٦): لا ملف محلي بغير دباجة + لوجو + توقيعين.
"""
import io
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from core import arabic_numbers as arnum
from core import egtime
from data_access import dataguard
from data_access import db_letterhead as lh
from data_access import storage
from documents.official_xlsx import add_letterhead
from services import occasions_fs as ofs
from services.raghibin import signatures_rows

NAVY = RGBColor(0x0A, 0x12, 0x30)
GOLD = RGBColor(0xB8, 0x86, 0x0B)
CENTER = Alignment(horizontal="center", vertical="center", readingOrder=2)
RIGHT = Alignment(horizontal="right", vertical="center", readingOrder=2)
RIGHT_WRAP = Alignment(horizontal="right", vertical="center", readingOrder=2,
                       wrap_text=True)


def _logo_png(year, month, size=(300, 300)):
    """اللوجو الرسمي للشهر (أو الشعار الافتراضي) كـPNG — وإلا None بلا كسر."""
    from services.images import png_bytes
    sources = [lh.logo_path(year, month),
               Path(__file__).resolve().parents[1] / "static" / "img" / "app.ico"]
    for source in sources:
        if source and Path(source).is_file():
            try:
                return png_bytes(source, max_size=size)
            except ValueError:
                continue
    return None


def _month_of(item):
    """شهر/سنة المناسبة من تاريخها (الدباجة شهرية) — وإلا الشهر الحالي."""
    parts = (item.get("date_iso") or "").split("-")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1])
    today = egtime.today()
    return today.year, today.month


def _rows(item):
    """صفوف التقرير: (البند، القيمة) — بلا أي قيمة None في الورق."""
    return [
        ("المسمى", item["title"]), ("النوع", item["kind"]),
        ("التاريخ", item["date_iso"]), ("المكان", item["place"]),
        ("القوة / الوفد", item["force_text"]), ("إطار", item["frame"]),
        ("إخطار", item["alert"]),
    ]


def build_xlsx(item):
    """التقرير Excel — ورقة واحدة رسمية: الدباجة + بيانات المناسبة + الوصف + التوقيعان."""
    year, month = _month_of(item)
    folder = Path(item["folder"])
    book = Workbook()
    ws = book.active
    ws.title = "تقرير المناسبة"[:31]
    add_letterhead(ws, year, month, 4)
    ws.merge_cells(start_row=6, start_column=1, end_row=6, end_column=4)
    title = ws.cell(6, 1, f"تقرير مناسبة — {item['title']}")
    title.font = Font(name="Cairo", size=14, bold=True, color="132638")
    title.alignment = CENTER
    row = 8
    for label, value in _rows(item):
        head = ws.cell(row, 1, label)
        head.font = Font(name="Cairo", size=11, bold=True, color="FFFFFF")
        head.fill = PatternFill("solid", fgColor="132638")
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        body = ws.cell(row, 2, value or "—")
        body.font = Font(name="Cairo", size=11)
        body.alignment = RIGHT
        ws.column_dimensions["A"].width = 22
        row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
    header = ws.cell(row, 1, "الوصف / مجريات المناسبة")
    header.font = Font(name="Cairo", size=12, bold=True, color="996C27")
    header.alignment = CENTER
    row += 1
    for line in (item["notes"] or "—").splitlines() or ["—"]:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        cell = ws.cell(row, 1, line)
        cell.alignment = RIGHT_WRAP
        cell.font = Font(name="Cairo", size=11)
        row += 1
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
    media = ws.cell(row, 1, f"مرفقات المناسبة: "
                            f"{arnum.to_arabic_indic(str(len(item['photos'])))} صورة · "
                            f"{arnum.to_arabic_indic(str(len(item['videos'])))} فيديو")
    media.font = Font(name="Cairo", size=11, bold=True)
    media.alignment = CENTER
    signatures_rows(ws, row + 2, year, month, 4)
    path = folder / ofs.REPORT_XLSX
    dataguard.atomic_save(book.save, str(path))
    return path


def build_docx(item):
    """التقرير Word — نفس الورق بنفس الدباجة واللوجو والتوقيعين (للطباعة والتعديل)."""
    year, month = _month_of(item)
    folder = Path(item["folder"])
    doc = Document()
    # اللوجو: المرفوع للشهر، وإلا الشعار الافتراضي — ويُحوَّل PNG قبل الإدراج
    # (python-docx لا يقرأ ico) فلا يسقط التقرير أبدًا.
    logo_bytes = _logo_png(year, month)
    if logo_bytes:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.add_run().add_picture(io.BytesIO(logo_bytes), width=Cm(2.6))
    for index, size in ((1, 16), (2, 14), (3, 13), (4, 13)):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = p.add_run(lh.get_setting(year, month, f"lh_{index}") or "")
        run.font.size = Pt(size)
        run.font.bold = index == 1
        run.font.color.rgb = GOLD if index == 1 else NAVY
        run.font.name = "Cairo"
    head = doc.add_paragraph()
    head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = head.add_run(f"تقرير مناسبة — {item['title']}")
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.color.rgb = NAVY
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in _rows(item):
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = value or "—"
    body = doc.add_paragraph()
    body.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = body.add_run(item["notes"] or "—")
    run.font.size = Pt(12)
    sig = doc.add_table(rows=1, cols=2)
    for cell, side in zip(sig.rows[0].cells, ("right", "left")):
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        for key in (f"sig_{side}_rank", f"sig_{side}_name"):
            p = cell.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(lh.get_setting(year, month, key) or "........................")
            r.font.bold = True
            r.font.size = Pt(12)
            r.font.name = "Cairo"
    path = folder / ofs.REPORT_DOCX
    dataguard.atomic_save(doc.save, str(path))
    return path


def build_all(item):
    """إعادة بناء التقريرين داخل فولدر المناسبة — يُستدعى بعد الحفظ أو التعديل."""
    return {"xlsx": build_xlsx(item), "docx": build_docx(item)}
