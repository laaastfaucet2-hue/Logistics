# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الملفات المحلية المستقلة لصفحات التفاريد الحرة (توجيه ٠٦/١٠/٢٠٢٦).

قاعدة المستخدم: «لها ملفات مستقلة، وتعديلاتها لا تمس مقررات المتعهد/التموينيات».

الشجرة (مستقلة تمامًا عن فولدرات المخازن والمقررات):

    database/<سنة>/<شهر>/14-التفاريد الحرة/
        ├── معدلات الأصناف/معدلات الأصناف.json + .xlsx
        ├── التفاريد الحرة/<العنوان> — يوم <البداية> إلى <النهاية>.json + .xlsx
        └── تفريدات الدول/<العنوان>.json + .xlsx

كل ملف إكسل بدباجة + لوجو + توقيعين رسميين (القواعد الذهبية)، وكل كتابة ذرّية
عبر `dataguard.atomic_save` (live-sync لو الملف مفتوح في Excel).
"""
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from core import arabic_numbers as arnum
from core import egtime
from core.config import MONTH_NAMES, month_folder
from data_access import dataguard, storage
from documents.official_xlsx import add_letterhead
from services import free_tafreed_calc as calc, sheet_columns

FOLDER = "14-التفاريد الحرة"
# «الورق = الإكسل»: كل رؤوس هذا القسم من `services/sheet_columns.py` (مصدر واحد)
HEADERS_RATE = sheet_columns.FREE_RATE
HEADERS_FREE = sheet_columns.FREE_SHEET
HEADERS_POINT = sheet_columns.FREE_POINT
HEADERS_DIST = sheet_columns.FREE_DIST

CENTER = Alignment(horizontal="center", vertical="center", readingOrder=2)
BLUE = "132638"
ZEBRA = "F4F6FB"
SUBTOTAL = "E9EDF7"
KIND_LABEL = {"tamween": "التموينيات", "contractor": "المتعهد"}


def free_dir(year, month):
    """فولدر القسم المستقل داخل الشهر: 14-التفاريد الحرة (لا يتبع أي قسم آخر)."""
    path = storage.DATA_DIR / str(year) / month_folder(month) / FOLDER
    path.mkdir(parents=True, exist_ok=True)
    return path


def sub_dir(year, month, name):
    path = free_dir(year, month) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe(name):
    """اسم ملف آمن (بلا رموز المسار) — مع الحفاظ على العربية."""
    return " ".join(str(name or "").replace("/", "-").replace("\\", "-").split())[:90]


def _save_json(path, payload):
    """كتابة JSON ذرّية (بلا فحص ZIP — الملف نصي لا مضغوط)."""
    text = json.dumps(payload, ensure_ascii=False, indent=1)

    def _writer(target):
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text)

    dataguard.atomic_save(_writer, str(path), zip_check=False)
    return path


def _signatures(ws, row, year, month, ncols):
    from data_access import db_letterhead as lhdb
    right = (lhdb.get_setting(year, month, "sig_right_rank"),
             lhdb.get_setting(year, month, "sig_right_name"))
    left = (lhdb.get_setting(year, month, "sig_left_rank"),
            lhdb.get_setting(year, month, "sig_left_name"))
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=max(2, ncols // 2))
    ws.merge_cells(start_row=row, start_column=max(3, ncols // 2 + 1), end_row=row,
                   end_column=ncols)
    for col, block in ((1, right), (max(3, ncols // 2 + 1), left)):
        cell = ws.cell(row, col, f"{block[0] or ''} — {block[1] or ''}")
        cell.font = Font(name="Cairo", size=11, bold=True)
        cell.alignment = CENTER


def _sheet(ws, year, month, title, headers, rows, note=""):
    """ورقة رسمية موحّدة: دباجة + لوجو + عنوان بالشهر والسنة + رأس + صفوف + إجمالي + توقيعان."""
    add_letterhead(ws, year, month, len(headers))
    ws.merge_cells(start_row=6, start_column=1, end_row=6, end_column=len(headers))
    head = ws.cell(6, 1, f"{title} — {MONTH_NAMES[month - 1]} "
                         f"{arnum.to_arabic_indic(year)}")
    head.font = Font(name="Cairo", size=13, bold=True, color=BLUE)
    head.alignment = CENTER
    ws.row_dimensions[6].height = 22
    for col, name in enumerate(headers, start=1):
        cell = ws.cell(7, col, name)
        cell.font = Font(name="Cairo", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BLUE)
        cell.alignment = CENTER
        ws.column_dimensions[get_column_letter(col)].width = max(12, len(name) * 2 + 4)
    ws.row_dimensions[7].height = 20
    row = 8
    for index, values in enumerate(rows, start=1):
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row, col, value)
            cell.alignment = CENTER
            cell.font = Font(name="Cairo", size=11, bold=(col == 2))
            if index % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=ZEBRA)
        row += 1
    if note:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(headers))
        cell = ws.cell(row, 1, note)
        cell.font = Font(name="Cairo", size=11, bold=True)
        cell.alignment = CENTER
        row += 1
    _signatures(ws, row + 2, year, month, len(headers))


def rate_rows(rates):
    """صفوف معدلات الأصناف (مفتاح الحروف ض/أ/م غير لازم هنا — أسماء أصناف لا فئات)."""
    rows = []
    for rate in rates:
        rows.append((arnum.to_arabic_indic(str(rate["serial"])), rate["name"],
                     rate["unit"] or "—", calc.fmt(rate["rate"]),
                     "، ".join(arnum.to_arabic_indic(str(d)) for d in (rate.get("days") or []))
                     or "—",
                     KIND_LABEL.get(rate.get("kind"), rate.get("kind") or "—"),
                     "مفعّل" if rate.get("active") else "موقوف"))
    return rows


def write_rates(year, month, rates):
    """ملف معدلات الأصناف — JSON + إكسل، بلا أي مساس بالمقررات."""
    for index, rate in enumerate(rates, start=1):     # المسلسل للعرض إن لم يكن محسوبًا
        rate.setdefault("serial", index)
    folder = sub_dir(year, month, "معدلات الأصناف")
    payload = {"الجهة": "قسم التعيينات", "القسم": "التفاريد الحرة", "الشهر": month,
               "السنة": year, "آخر تحديث": egtime.now().isoformat(timespec="seconds"),
               "عدد الأصناف": len(rates), "مفتاح الأعمدة": HEADERS_RATE, "الأصناف": rates}
    _save_json(folder / "معدلات الأصناف.json", payload)
    book = Workbook()
    _sheet(book.active, year, month, "معدلات تفاريد حرة — الأصناف",
           sheet_columns.as_labels(HEADERS_RATE), rate_rows(rates),
           note="هذه المعدلات لقطة حرة من مقررات الشهر وقابلة للتعديل بحرية — "
                "تعديلها لا يمس مقررات التموين أو المتعهد ولا أرصدة المخازن.")
    path = folder / "معدلات الأصناف.xlsx"
    dataguard.atomic_save(book.save, str(path))
    return path


def sheet_base(sheet):
    """اسم ملف التفريدة: «العنوان — يوم البداية إلى النهاية» (مصدر واحد للكتابة والحذف)."""
    title = _safe(sheet.get("title")) or "تفريدة"
    first = int(sheet.get("date_from") or 1)
    last = int(sheet.get("date_to") or first)
    if last > first:
        stamp = "يوم {} إلى {}".format(arnum.to_arabic_indic(str(first)),
                                       arnum.to_arabic_indic(str(last)))
    else:
        stamp = "يوم {}".format(arnum.to_arabic_indic(str(first)))
    return "{0} — {1}".format(title, stamp)


def write_free_sheet(year, month, sheet):
    """ملف تفريدة حرة (أو تفريدة دول) محفوظة — JSON + إكسل بالدباجة والتوقيعين."""
    kind_folder = "تفريدات الدول" if sheet.get("kind") == "intl" else "التفاريد الحرة"
    folder = sub_dir(year, month, kind_folder)
    payload = {"الجهة": sheet.get("title") or "قسم التعيينات", "القسم": kind_folder,
               "الشهر": month, "السنة": year,
               "آخر تحديث": egtime.now().isoformat(timespec="seconds"),
               "أمين المخزن": sheet.get("holder") or "", "كاتب التعهدات": sheet.get("writer") or "",
               "من يوم": sheet.get("date_from"), "إلى يوم": sheet.get("date_to"),
               "عدد الأيام": sheet.get("days"), "القوة": sheet.get("force"),
               "الأصناف": sheet.get("payload", {}).get("rows", [])}
    base = sheet_base(sheet)
    _save_json(folder / f"{base}.json", payload)
    rows = []
    for row in sheet.get("payload", {}).get("rows", []):
        rows.append((arnum.to_arabic_indic(str(row.get("serial"))), row.get("name"),
                     row.get("unit") or "—", calc.fmt(row.get("rate")),
                     arnum.to_arabic_indic(str(row.get("days"))),
                     f"{calc.fmt(row.get('total'))} {row.get('unit') or ''}".strip(), ""))
    book = Workbook()
    _sheet(book.active, year, month, f"تفريدة — {sheet.get('title') or ''}",
           sheet_columns.as_labels(HEADERS_FREE), rows,
           note=f"القوة: {arnum.to_arabic_indic(str(sheet.get('force') or 0))} فرد · "
                f"عدد الأيام: {arnum.to_arabic_indic(str(sheet.get('days') or 0))} — "
                "تفريدة حرة مستقلة، لا تمس المقررات ولا أرصدة المخازن.")
    path = folder / f"{base}.xlsx"
    dataguard.atomic_save(book.save, str(path))
    return path


def write_distribution(year, month, sheet, rows, totals):
    """بيان توزيع وإجمالي تعيينات خطوط حراسة الدول (مطبوع + ملف)."""
    folder = sub_dir(year, month, "تفريدات الدول")
    title = _safe(sheet.get("title")) or "بيان توزيع"
    data = []
    serial = 0
    for row in rows:
        cells = [c for c in (row.get("cells") or []) if c.get("total")]
        for column, cell in enumerate(cells):
            if column == 0:
                serial += 1
            data.append((arnum.to_arabic_indic(str(serial)) if column == 0 else "",
                         row.get("point"), arnum.to_arabic_indic(str(row.get("force"))),
                         cell.get("name"), cell.get("unit") or "—",
                         calc.fmt(cell.get("total"))))
    total_row = [("", "إجمالي القطاعات والخطوط العامة", "", item.get("name"),
                  item.get("unit") or "—", calc.fmt(item.get("total"))) for item in totals]
    book = Workbook()
    _sheet(book.active, year, month, f"بيان توزيع — {title}",
           sheet_columns.as_labels(HEADERS_DIST), data + total_row,
           note="هذا الكشف يمثل إجمالي أذونات وحصص التعيينات المصروفة لكل نقطة (خط) دفعة واحدة مجمعة.")
    path = folder / f"بيان توزيع — {title}.xlsx"
    dataguard.atomic_save(book.save, str(path))
    return path


def remove_sheet_files(year, month, sheet):
    """حذف ملفات تفريدة محذوفة (JSON + إكسل) — بلا أي مساس بغيرها."""
    kind_folder = "تفريدات الدول" if sheet.get("kind") == "intl" else "التفاريد الحرة"
    folder = sub_dir(year, month, kind_folder)
    removed = 0
    for suffix in (".json", ".xlsx"):
        path = folder / f"{sheet_base(sheet)}{suffix}"
        if path.exists():
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def tree(year, month):
    """شجرة ملفات القسم — للحصر والفحص (قراءة فقط)."""
    root = free_dir(year, month)
    items = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items.append({"name": path.name, "folder": path.parent.name,
                          "size": path.stat().st_size})
    return {"folder": str(root), "files": items}
