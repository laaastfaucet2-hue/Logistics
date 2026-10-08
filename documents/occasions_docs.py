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
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from core import arabic_numbers as arnum
from core import dates, egtime
from core.config import MONTH_NAMES
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


def _arabic_date(value):
    """تاريخ نصي عربي «٨ أكتوبر ٢٠٢٦» — يُقرأ من اليمين لليسار بلا التباس داخل Word/Excel."""
    parsed = dates.parse_date(value)
    if not parsed:
        return value or "—"
    return " ".join((arnum.to_arabic_indic(str(parsed.day)),
                     MONTH_NAMES[parsed.month - 1],
                     arnum.to_arabic_indic(str(parsed.year))))


def _month_of(item):
    """شهر/سنة المناسبة من تاريخها (الدباجة شهرية) — وإلا الشهر الحالي."""
    parts = (item.get("date_iso") or "").split("-")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1])
    today = egtime.today()
    return today.year, today.month


def _photo_png(path, size=(1200, 1200)):
    """صورة جاهزة للإدراج في التقرير (PNG) — تُرجع None لو الملف تالف (فلا يسقط التقرير)."""
    from services.images import png_bytes
    try:
        return png_bytes(path, max_size=size)
    except (ValueError, OSError):
        return None


def _add_photos_docx(doc, item):
    """يدمج صور المناسبة داخل تقرير Word: عنوان + شبكة عمودين بعرض ٧٫٦ سم لكل صورة."""
    photos = item.get("photos") or []
    if not photos:
        return
    _say(doc, f"صور المناسبة ({arnum.to_arabic_indic(str(len(photos)))}) — مدمجة في التقرير",
         size=13, bold=True, color=GOLD, space_after=6)
    rows = (len(photos) + 1) // 2
    table = _rtl_table(doc.add_table(rows=rows, cols=2))   # الصورة الأولى تبدأ من اليمين
    table.autofit = False
    for index, photo in enumerate(photos):
        cell = table.cell(index // 2, index % 2)
        data = _photo_png(Path(item["folder"]) / photo["sub"] / photo["name"])
        para = cell.paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if data:
            para.add_run().add_picture(io.BytesIO(data), width=Cm(7.6))
        caption = cell.add_paragraph()
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        text = caption.add_run(f"{photo['name']} — {photo.get('size_text') or ''}")
        text.font.size = Pt(8.5)
        text.font.name = "Cairo"
        _rtl_para(caption, WD_ALIGN_PARAGRAPH.CENTER)
        _rtl_runs(caption)


def _add_photos_xlsx(book, item, year, month):
    """ورقة «صور المناسبة» في تقرير Excel بمصغّرات مدمجة — وبلا كسر لو صورة تالفة."""
    photos = item.get("photos") or []
    if not photos:
        return
    from openpyxl.drawing.image import Image as XLImage
    ws = book.create_sheet("صور المناسبة"[:31])
    add_letterhead(ws, year, month, 4)
    ws.merge_cells(start_row=6, start_column=1, end_row=6, end_column=4)
    title = ws.cell(6, 1, f"صور مناسبة — {item['title']}")
    title.font = Font(name="Cairo", size=14, bold=True, color="132638")
    title.alignment = CENTER
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 34
    row = 8
    for index, photo in enumerate(photos):
        data = _photo_png(Path(item["folder"]) / photo["sub"] / photo["name"], size=(620, 620))
        label = ws.cell(row, 1, f"{arnum.to_arabic_indic(str(index + 1))}- {photo['name']}")
        label.font = Font(name="Cairo", size=10, bold=True)
        label.alignment = RIGHT
        ws.row_dimensions[row].height = 118
        if data:
            try:
                image = XLImage(io.BytesIO(data))     # الصورة تحت عنوانها في نفس العمود
                image.width, image.height = 150, 110
                ws.add_image(image, f"A{row + 1}")
                row += 2
                continue
            except (ValueError, OSError):                # pragma: no cover — صورة تالفة
                pass
        row += 1


def _rows(item):
    """صفوف التقرير: (البند، القيمة) — بلا أي قيمة None في الورق."""
    return [
        ("المسمى", item["title"]), ("النوع", item["kind"]),
        ("التاريخ", _arabic_date(item["date_iso"])), ("المكان", item["place"]),
        ("القوة / الوفد", item["force_text"]), ("إطار", item["frame"]),
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
    _add_photos_xlsx(book, item, year, month)     # الصور مدمجة في ورقة مستقلة داخل التقرير
    signatures_rows(ws, row + 2, year, month, 4)
    path = folder / ofs.REPORT_XLSX
    dataguard.atomic_save(book.save, str(path))
    return path


def _rtl_para(paragraph, align=WD_ALIGN_PARAGRAPH.RIGHT):
    """يجعل الفقرة عربية من اليمين لليسار (w:bidi) — قاعدة تقارير Word ٠٨/١٠/٢٠٢٦."""
    pPr = paragraph._p.get_or_add_pPr()
    if pPr.find(qn("w:bidi")) is None:
        pPr.insert_element_before(OxmlElement("w:bidi"), "w:adjustRightInd", "w:snapToGrid",
                                  "w:spacing", "w:ind", "w:jc", "w:textAlignment",
                                  "w:outlineLvl", "w:rPr", "w:sectPr", "w:pPrChange")
    paragraph.alignment = align
    return paragraph


def _rtl_runs(paragraph):
    """يعيد نص الفقرة لوضع العربية: خط Cairo للـComplex Script + حجم cs + علامة rtl."""
    for run in paragraph.runs:
        rPr = run._element.get_or_add_rPr()
        rPr.get_or_add_rFonts().set(qn("w:cs"), "Cairo")
        if run.font.size is not None:
            size_cs = OxmlElement("w:szCs")
            size_cs.set(qn("w:val"), str(int(run.font.size.pt * 2)))
            sized = rPr.find(qn("w:sz"))
            if sized is not None:
                sized.addnext(size_cs)
            else:
                rPr.append(size_cs)
        rPr.get_or_add_rtl().set(qn("w:val"), "1")


def _rtl_doc(doc):
    """اتجاه الورقة نفسها من اليمين لليسار (w:bidi في sectPr) — مثل ورقة Excel RTL."""
    sectPr = doc.sections[0]._sectPr
    if sectPr.find(qn("w:bidi")) is None:
        sectPr.insert_element_before(OxmlElement("w:bidi"), "w:rtlGutter", "w:docGrid",
                                     "w:printerSettings", "w:sectPrChange")


def _rtl_table(table):
    """الجدول يُقرأ من اليمين لليسار: العمود الأول على اليمين (مثل Excel)."""
    table._tbl.tblPr.get_or_add_bidiVisual()
    return table


def _say(doc, text, size=12, bold=False, color=None, align=WD_ALIGN_PARAGRAPH.RIGHT,
         space_after=6):
    """فقرة عربية رسمية جاهزة (RTL + Cairo) — تُستخدم لكل نصوص التقرير."""
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(space_after)
    run = para.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = "Cairo"
    if color is not None:
        run.font.color.rgb = color
    _rtl_para(para, align)
    _rtl_runs(para)
    return para


def _fill(cell, text, size=12, bold=False, color=None, align=WD_ALIGN_PARAGRAPH.RIGHT,
          dash=True):
    """تكتب داخل خلية جدول بأسلوب عربي RTL — بلا None (والفراغ شرطة إلا إن طُلب خلافه)."""
    para = cell.paragraphs[0]
    for extra in cell.paragraphs[1:]:
        extra._element.getparent().remove(extra._element)
    run = para.add_run(text if text not in (None, "") else ("—" if dash else ""))
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = "Cairo"
    if color is not None:
        run.font.color.rgb = color
    _rtl_para(para, align)
    _rtl_runs(para)
    return para


def _gold_rule(doc):
    """خط ذهبي فاصل تحت الدباجة — نفس شكل صفحة الورق (oc-paper-rule)."""
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(10)
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "18")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "B8860B")
    borders.append(bottom)
    para._p.get_or_add_pPr().append(borders)
    return para


def _letterhead_block(doc, year, month, logo_bytes):
    """بلوك الترويسة بنفس ترتيب Excel: الدباجة يمين الورقة واللوجو شمالها في نفس السطر."""
    table = _rtl_table(doc.add_table(rows=1, cols=2))
    table.autofit = False
    head, logo_cell = table.rows[0].cells
    head.width, logo_cell.width = Cm(12.6), Cm(4.4)
    first = True
    for index, size in ((1, 16), (2, 14), (3, 13), (4, 13)):
        text = lh.get_setting(year, month, f"lh_{index}") or ""
        if first:
            _fill(head, text, size=size, bold=index == 1,
                  color=GOLD if index == 1 else NAVY, dash=False)
            first = False
        else:
            para = head.add_paragraph()
            run = para.add_run(text)
            run.font.size = Pt(size)
            run.font.bold = False
            run.font.name = "Cairo"
            run.font.color.rgb = NAVY
            _rtl_para(para)
            _rtl_runs(para)
    if logo_bytes:
        para = logo_cell.paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        para.add_run().add_picture(io.BytesIO(logo_bytes), width=Cm(2.6))
    else:
        _fill(logo_cell, "", align=WD_ALIGN_PARAGRAPH.LEFT, dash=False)
    _gold_rule(doc)


def _signatures_block(doc, year, month):
    """التوقيعان الرسميان بنفس أماكن Excel: اليميني يمين الورقة واليساري شمالها."""
    _say(doc, "يعتمد،،", size=12, space_after=10)
    table = _rtl_table(doc.add_table(rows=1, cols=2))
    table.autofit = False
    right_cell, left_cell = table.rows[0].cells
    right_cell.width, left_cell.width = Cm(8.5), Cm(8.5)
    for cell, side in ((right_cell, "right"), (left_cell, "left")):
        rank = lh.get_setting(year, month, f"sig_{side}_rank") or "........................"
        name = lh.get_setting(year, month, f"sig_{side}_name") or "........................"
        _fill(cell, rank, size=12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        para = cell.add_paragraph()
        run = para.add_run(name)
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.name = "Cairo"
        _rtl_para(para, WD_ALIGN_PARAGRAPH.CENTER)
        _rtl_runs(para)


def build_docx(item):
    """التقرير Word — ورق عربي RTL بنفس ترتيب Excel: دباجة يمين + لوجو شمال (
    في نفس السطر)، ثم البيانات والوصف والصور، ثم «يعتمد،،» والتوقيعان في مكانهما."""
    year, month = _month_of(item)
    folder = Path(item["folder"])
    doc = Document()
    section = doc.sections[0]
    section.left_margin = section.right_margin = Cm(1.9)   # تتسع لصفّ الدباجة واللوجو (١٧ سم)
    section.top_margin = section.bottom_margin = Cm(1.7)
    _rtl_doc(doc)                                  # اتجاه الورقة من اليمين لليسار
    _letterhead_block(doc, year, month, _logo_png(year, month))

    _say(doc, f"تقرير مناسبة — {item['title']}", size=16, bold=True, color=NAVY,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10)

    rows = _rows(item)
    table = _rtl_table(doc.add_table(rows=len(rows), cols=2))
    table.style = "Table Grid"
    table.autofit = False
    for index, (label, value) in enumerate(rows):
        head_cell, body_cell = table.rows[index].cells
        head_cell.width, body_cell.width = Cm(4.0), Cm(13.0)
        _fill(head_cell, label, size=11, bold=True)
        _fill(body_cell, value, size=11)

    _say(doc, "الوصف / مجريات المناسبة", size=13, bold=True, color=GOLD, space_after=4)
    _say(doc, item["notes"] or "—", size=12, space_after=8)

    _add_photos_docx(doc, item)                    # الصور مدمجة في التقرير نفسه

    _say(doc, f"مرفقات المناسبة: {arnum.to_arabic_indic(str(len(item['photos'])))} صورة · "
              f"{arnum.to_arabic_indic(str(len(item['videos'])))} فيديو — محفوظة داخل فولدر المناسبة.",
         size=11, color=RGBColor(0x3F, 0x4A, 0x63), space_after=10)

    _signatures_block(doc, year, month)
    path = folder / ofs.REPORT_DOCX
    dataguard.atomic_save(doc.save, str(path))
    return path


def build_all(item):
    """إعادة بناء التقريرين داخل فولدر المناسبة — يُستدعى بعد الحفظ أو التعديل."""
    return {"xlsx": build_xlsx(item), "docx": build_docx(item)}
