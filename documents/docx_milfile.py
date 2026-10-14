# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تقرير تتبُّع المجند الرسمى (Word) — يلتزم الدباجة واللوجو والتوقيعين الرسميين.

الفولدر المحلى: database/ملفات المجند/<الرقم_العسكرى>_<الاسم>/
الملف:           تتبّع-<الاسم>-<الرقم_العسكرى>.docx

الدباجة (٤ أسطر) + اللوجو: من إعدادات الشهر الحالي (تبويب الدباجة والتوقيعات)
التوقيعان: من مستوى المنظومة كله — نفس التوقيعين في كل الملفات الرسمية.
"""
import re
from datetime import date

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt, RGBColor

from core import arabic_numbers as arnum, dates, egtime
from data_access import dataguard, db_letterhead as lh, storage
from services import recruit_file

NAVY = RGBColor(0x0A, 0x12, 0x30)
GOLD = RGBColor(0xB8, 0x86, 0x0B)
SOFT = RGBColor(0x47, 0x55, 0x69)
FILL_HEADER = "F3EEDF"     # خلفية رأس الجدول (كرمي فاتح — لون الورق الرسمي)
FILL_MONTH = "FBF7EA"      # خلفية سطر الشهر
FILL_TODAY = "FFF6DC"      # اليوم الحالي

MILFILES_ROOT = "ملفات المجند"


def _safe(text):
    """اسم مجلد/مل آمن على أنظمة الملفات (يبقي العربي كما هو)."""
    text = (text or "بدون-اسم").strip()
    return re.sub(r'[\\/:*?"<>|\s]+', "-", text)[:80] or "بدون-اسم"


def folder(year, month, r):
    """الفولدر المحلى للمجند — واحد لكل مجند على مستوى المنظومة."""
    d = (storage.DATA_DIR / MILFILES_ROOT
         / "{}-{}".format(_safe(r["mil_no"]), _safe(r["name"])))
    d.mkdir(parents=True, exist_ok=True)
    return d


def docx_path(year, month, r):
    return folder(year, month, r) / "تتبّع-{}-{}.docx".format(
        _safe(r["name"]), _safe(r["mil_no"]))


# ==================== أدوات تنسيق ====================
def _run(p, text, size=11, bold=False, color=None):
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = "Cairo"
    if color is not None:
        run.font.color.rgb = color
    return run


def _line(doc, text, size=11, bold=False, color=None, align=WD_ALIGN_PARAGRAPH.RIGHT):
    p = doc.add_paragraph()
    p.alignment = align
    _run(p, text, size, bold, color)
    return p


def _fill(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def _cell(cell, text, size=10.5, bold=False, color=None,
          align=WD_ALIGN_PARAGRAPH.RIGHT, fill=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    _run(p, text or "—", size, bold, color)
    if fill:
        _fill(cell, fill)
    return cell


def _table(doc, cols):
    t = doc.add_table(rows=0, cols=cols)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    return t


# ==================== البناء ====================
def _header(doc, year, month):
    """الدباجة: اللوجو شمال أعلى الصفحة + الأسطر الأربعة يمينًا — نفس شكل الدباجة الرسمى."""
    settings = lh.get_all(year, month)
    logo = settings.get("logo_file")
    if logo:
        logo_path = storage.letterhead_dir(year, month) / logo
        if logo_path.exists():
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.add_run().add_picture(str(logo_path), width=Cm(3))
    for i, size in ((1, 16), (2, 14), (3, 13), (4, 13)):
        text = settings.get("lh_{}".format(i), "")
        if text:
            _line(doc, text, size, color=(GOLD if i == 1 else NAVY))
    # فاصل ذهبي
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "B8860B")
    pBdr.append(bottom)
    pPr.append(pBdr)
    return settings


def _meta_table(doc, r, issued):
    t = _table(doc, 4)
    rows = [
        ("اسم المجند", r["name"], "الرقم العسكري", r["mil_no"] or "—"),
        ("دخول الخدمة", dates.format_date(r.get("service_start") or ""),
         "انتهاء الخدمة", dates.format_date(r.get("service_end") or "")),
        ("المحافظة", r.get("governorate") or "—", "المدينة", r.get("city") or "—"),
        ("العنوان", r.get("address") or "—",
         "الشهادة الصحية", "موجودة ({}-{})".format(
             dates.format_date(r.get("cert_date") or ""),
             dates.format_date(r.get("cert_expiry") or "")) if r.get("has_cert") else "غير مسجلة"),
    ]
    for l1, v1, l2, v2 in rows:
        row = t.add_row()
        _cell(row.cells[0], l1, 10, True, NAVY, fill=FILL_HEADER)
        _cell(row.cells[1], v1, 10.5)
        _cell(row.cells[2], l2, 10, True, NAVY, fill=FILL_HEADER)
        _cell(row.cells[3], v2, 10.5)
    _line(doc, "تاريخ إصدار التقرير: {}".format(
        dates.format_date(issued)), 9.5, color=SOFT,
        align=WD_ALIGN_PARAGRAPH.CENTER)


def _section(doc, title):
    _line(doc, "", 4)
    p = _line(doc, title, 13, True, NAVY)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "B8860B")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _milestones(doc, milestones):
    t = _table(doc, 2)
    row = t.add_row()
    _cell(row.cells[0], "المحطة", 10, True, NAVY, fill=FILL_HEADER)
    _cell(row.cells[1], "التاريخ", 10, True, NAVY, align=WD_ALIGN_PARAGRAPH.CENTER,
          fill=FILL_HEADER)
    for ms in milestones:
        row = t.add_row()
        text = ms["text"]
        if " — " in text:
            label, when = text.split(" — ", 1)
        else:
            label, when = text, ""
        _cell(row.cells[0], "{}  {}".format(ms["icon"], label), 10.5)
        _cell(row.cells[1], when, 10.5, align=WD_ALIGN_PARAGRAPH.CENTER)


def _daily(doc, groups, today):
    """الجدول اليومي الشامل: كل يوم من أول يوم في الخدمة لآخر يوم — مجمّع على الشهور."""
    t = _table(doc, 4)
    row = t.add_row()
    _cell(row.cells[0], "التاريخ", 10, True, NAVY, align=WD_ALIGN_PARAGRAPH.CENTER,
          fill=FILL_HEADER)
    _cell(row.cells[1], "اليوم", 10, True, NAVY, align=WD_ALIGN_PARAGRAPH.CENTER,
          fill=FILL_HEADER)
    _cell(row.cells[2], "الحالة", 10, True, NAVY, align=WD_ALIGN_PARAGRAPH.CENTER,
          fill=FILL_HEADER)
    _cell(row.cells[3], "ملاحظات", 10, True, NAVY, fill=FILL_HEADER)
    for g in groups:
        row = t.add_row()
        merged = row.cells[0].merge(row.cells[1]).merge(row.cells[2]).merge(row.cells[3])
        _cell(merged, g["label"], 11, True, GOLD, fill=FILL_MONTH)
        for dd in g["days"]:
            row = t.add_row()
            fill = FILL_TODAY if dd["today"] else None
            _cell(row.cells[0], dd["ymd"], 9.5, dd["today"],
                  align=WD_ALIGN_PARAGRAPH.CENTER, fill=fill)
            _cell(row.cells[1], dd["weekday"], 9.5, dd["today"],
                  align=WD_ALIGN_PARAGRAPH.CENTER, fill=fill)
            if dd["status"]:
                _cell(row.cells[2], dd["status"], 9.5, True,
                      align=WD_ALIGN_PARAGRAPH.CENTER, fill=fill)
            else:
                _cell(row.cells[2], "لم يُسجَّل", 9.5, False, SOFT,
                      align=WD_ALIGN_PARAGRAPH.CENTER, fill=fill)
            _cell(row.cells[3], dd["note"], 9.5, fill=fill)


def _totals(doc, totals):
    parts = ["{}: {}".format(st, arnum.to_arabic_indic(n))
             for st, n in totals.items() if n]
    _line(doc, "إجماليات الخدمة: " + "  ·  ".join(parts), 10.5, True, NAVY,
          align=WD_ALIGN_PARAGRAPH.CENTER)


def _signatures(doc, settings):
    _line(doc, "", 10)
    t = doc.add_table(rows=0, cols=2)   # بلا حدود — جدول توقيع عادي
    row = t.add_row()
    # يمين: مسؤول الملف — شمال: جهة الاعتماد
    for cell, rank_key, name_key, label in (
            (row.cells[1], "sig_right_rank", "sig_right_name", "مسؤول الملف"),
            (row.cells[0], "sig_left_rank", "sig_left_name", "جهة الاعتماد")):
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p, label, 10.5, True, NAVY)
        for key in (rank_key, name_key):
            p = cell.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _run(p, settings.get(key) or "........................", 12, True)


def build(year, month, rid):
    """ينشئ تقرير التتبع في الفولدر المحلى للمجند ويرجع مساره."""
    data = recruit_file.build(year, month, rid)
    if not data:
        return None
    r = data["recruit"]
    issued = egtime.today()
    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(1.5)
        section.bottom_margin = Cm(1.5)
        section.left_margin = Cm(1.8)
        section.right_margin = Cm(1.8)
    settings = _header(doc, year, month)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "تقرير تتبُّع المجند — {}  {}".format(r["name"], r["mil_no"]), 16, True, NAVY)
    _meta_table(doc, r, issued)
    _section(doc, "أولًا: محطات التتبع (كل خطوة في الخدمة)")
    if data["milestones"]:
        _milestones(doc, data["milestones"])
    else:
        _line(doc, "لا توجد محطات مسجلة بعد.", 10.5, color=SOFT)
    _section(doc, "ثانيًا: التتبع اليومي — كل يوم من دخول الخدمة لنهايتها")
    _daily(doc, data["daily"], issued)
    _section(doc, "ثالثًا: إجماليات فترة الخدمة")
    _totals(doc, data["totals"])
    _signatures(doc, settings)
    _line(doc, "صدر هذا التقرير آليًا من منظومة التعيينات — منظومة محلية سريّة على جهاز الوحدة.",
          8.5, False, SOFT, align=WD_ALIGN_PARAGRAPH.CENTER)
    path = docx_path(year, month, r)
    dataguard.atomic_save(doc.save, path)
    return path
