# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""حفظ «تفاريد خط الحدود الدولى» على القرص — أربع فولدرات محلية:

14-تفاريد خط الحدود الدولى
├─ أوراق وإيصالات الصرف/يوم F/خط X/  (مجمع + نقاط + ورقة الإذن + data.json)
├─ إجمالي خطوط التوزيع/خط X/يوم F/  (نفس الـ 2 ملفات إكسل)
├─ إدارة الخطوط والنقاط/خط X/يوم T/  (بيان.xlsx — كل تغيير في الخط/نقاطه)
└─ تعديل معدلات الأصناف/يوم T/       (بيان-المعدلات.xlsx — كل تغيير في المعدلات)

فولدر اليوم في الحفظ = أول يوم التوزيعة (ولو تكرر: «يوم F (2)»).
"""
import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from core import arabic_numbers as arnum, egtime
from core.config import DAYS, MEAL_MAP
from data_access import months
from services import dowail_paper_xlsx as paper_xlsx

SECTION_FOLDER = "14-تفاريد خط الحدود الدولى"
FOLDER_PAPERS = "أوراق وإيصالات الصرف"
FOLDER_TOTALS = "إجمالي خطوط التوزيع"
FOLDER_LINES = "إدارة الخطوط والنقاط"
FOLDER_RATES = "تعديل معدلات الأصناف"


def section_dir(year, month):
    """فولدر القسم داخل الشهر."""
    base = months.month_db_path(year, month).parent
    d = base / SECTION_FOLDER
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sheet(ws, title, header, rows, year=None, month=None):
    """شيت رسمي (١٠/١٠): لو فيه سياق شهر — ديباجة + لوجو + اسم الشهر +
    التوقيعان الرسميان (نفس القاعدة الذهبية لكل الملفات المحلية) + RTL."""
    ncols = max(len(header), 3)
    r0 = 1
    if year and month:
        from openpyxl.styles import Alignment
        from core.config import MONTH_NAMES
        from documents.official_xlsx import add_letterhead
        from services.raghibin import signatures_rows
        add_letterhead(ws, year, month, ncols)      # صفوف ١–٤ (لوجو + الوزارة)
        ws.merge_cells(start_row=5, start_column=1, end_row=5, end_column=ncols)
        c = ws.cell(5, 1, f"{MONTH_NAMES[int(month) - 1]} {arnum.to_arabic_indic(year)}")
        c.font = Font(bold=True, color="132638")
        c.alignment = Alignment(horizontal="center", vertical="center", readingOrder=2)
        r0 = 6
    ws.cell(r0, 1, title)
    for i, h in enumerate(header, start=1):
        ws.cell(r0 + 1, i, h)
    r = r0 + 2
    for row in rows:
        for i, v in enumerate(row, start=1):
            ws.cell(r, i, v)
        r += 1
    ws.cell(r0, 1).font = Font(bold=True, size=14)
    for i in range(1, len(header) + 1):
        ws.cell(r0 + 1, i).font = Font(bold=True)
    if year and month:
        signatures_rows(ws, r + 1, year, month, ncols)
    ws.sheet_view.rightToLeft = True


def _write_line_xlsx(path, data, line):
    """ملف «مجمع-خط»: نفس ورقة الإذن الرسمية الظاهرة في البرنامج."""
    paper_xlsx.build_line_summary_wb(data, line).save(path)


def _write_points_xlsx(path, data, line):
    """ملف «نقاط-خط»: ورقة إذن رسمية مستقلة لكل نقطة."""
    paper_xlsx.build_points_wb(data, line).save(path)


def build_all_lines_wb(data, year, month):
    """كل الخطوط والنقاط بنفس تصميم ورقة البرنامج والطباعة."""
    return paper_xlsx.build_paper_wb(data, year, month)


def _day_folder_name(data, n_saves_same_from):
    d = arnum.to_arabic_indic(int(data["date_from"]))
    return "يوم " + d + (f" ({arnum.to_arabic_indic(n_saves_same_from)})"
                         if n_saves_same_from > 1 else "")


def save_to_disk(year, month, data, n_saves_same_from=1):
    """يحفظ التوزيعة في (أوراق وإيصالات + إجمالي خطوط التوزيع) ويرجع الملفات النسبية."""
    sec = section_dir(year, month)
    day = _day_folder_name(data, n_saves_same_from)
    files = []
    for lp in data.get("papers") or []:
        line = lp["line"]
        line_from = int(lp.get("date_from") or data["date_from"])
        line_to = int(lp.get("date_to") or data["date_to"])
        day_count = max(1, line_to - line_from + 1)
        # 1) أوراق وإيصالات الصرف/يوم F/خط X/
        d1 = sec / FOLDER_PAPERS / day / line["name"]
        d1.mkdir(parents=True, exist_ok=True)
        agg = d1 / f"مجمع-{line['name']}.xlsx"
        pts = d1 / f"نقاط-{line['name']}.xlsx"
        paper = d1 / f"ورقة الإذن-{line['name']}.xlsx"
        _write_line_xlsx(agg, data, line)
        _write_points_xlsx(pts, data, line)
        paper_xlsx.write_paper_file(paper, data, line)
        from core.config import MONTH_NAMES
        payload = {"الجهة": "قطاع وسط سيناء", "القسم": "تفاريد خط الحدود الدولى",
                   "الشهر": MONTH_NAMES[int(month) - 1],
                   "السنة": arnum.to_arabic_indic(int(year)),
                   "آخر تحديث": egtime.now().isoformat(timespec="seconds"),
                   "date_from": line_from, "date_to": line_to,
                   "issue_days": day_count, "line": lp}
        (d1 / "data.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        files += [f"{SECTION_FOLDER}/{FOLDER_PAPERS}/{day}/{line['name']}/{f.name}"
                  for f in (agg, pts, paper, d1 / "data.json")]
        # 2) إجمالي خطوط التوزيع/خط X/يوم F/
        d2 = sec / FOLDER_TOTALS / line["name"] / day
        d2.mkdir(parents=True, exist_ok=True)
        _write_line_xlsx(d2 / agg.name, data, line)
        _write_points_xlsx(d2 / pts.name, data, line)
        files += [f"{SECTION_FOLDER}/{FOLDER_TOTALS}/{line['name']}/{day}/{f.name}"
                  for f in (d2 / agg.name, d2 / pts.name)]
    return files


# ======================================================================
# بيانات الخطوط والنقاط — بيان إكسل مع كل تغيير (الارشيف)
# ======================================================================
def _unused_statement_path(folder):
    path = folder / "بيان.xlsx"
    index = 2
    while path.exists():
        path = folder / f"بيان ({index}).xlsx"
        index += 1
    return path


def write_line_statement(year, month, line):
    """بيان مستقل لكل تغيير، داخل مجلد نسخة الخط، دون الكتابة فوق بيان سابق."""
    today = arnum.to_arabic_indic(egtime.now().day)
    version = f"نسخة {arnum.to_arabic_indic(line.get('id') or 0)}"
    d = section_dir(year, month) / FOLDER_LINES / line["name"] / version / f"يوم {today}"
    d.mkdir(parents=True, exist_ok=True)
    path = _unused_statement_path(d)
    wb = Workbook()
    ws = wb.active
    ws.title = "بيان الخط"
    header = ["م", "اسم النقطة", "القوة", "المسؤول"]
    rows = [[i + 1, p["name"], int(p["force"] or 0), p.get("responsible") or ""]
            for i, p in enumerate(line["points"])]
    period = (f"يوم {arnum.to_arabic_indic(line['date_from'])} إلى "
              f"{arnum.to_arabic_indic(line['date_to'])}"
              if line.get("date_from") is not None else "الفترة غير محددة")
    status = "حالية" if line.get("status") == "current" else "مؤرشفة"
    _sheet(ws, f"بيان «{line['name']}» — {version} — {status} — {period} — قوة {line['total_force']}",
           header, rows, year, month)
    wb.save(path)
    return str(path.relative_to(section_dir(year, month))).replace("\\", "/")


def write_rates_statement(year, month, rates):
    """فولدر اليوم + بيان إكسل لكل المعدلات. يرجع المسار النسبي."""
    today = arnum.to_arabic_indic(egtime.now().day)
    d = section_dir(year, month) / FOLDER_RATES / f"يوم {today}"
    d.mkdir(parents=True, exist_ok=True)
    path = d / "بيان-المعدلات.xlsx"
    index = 2
    while path.exists():
        path = d / f"بيان-المعدلات ({index}).xlsx"
        index += 1
    wb = Workbook()
    ws = wb.active
    ws.title = "المعدلات"
    header = ["م", "القسم", "اسم الصنف", "الوحدة", "المقرر المرجعي",
              "الإضافة اليدوية", "المعدل الفعلي", "التخصيص الأسبوعي",
              "تخصيص التاريخ الفعلي", "الحالة"]
    sec_name = {"tamween": "المقررات التموينية", "contractor": "مقررات المتعهد"}
    rows = []
    for i, r in enumerate(rates):
        weekly = [f"{DAYS[int(e.get('weekday') or 0)]} {MEAL_MAP.get(e.get('meal') or '', '')} "
                  f"{arnum.fmt_qty(e.get('qty'))}" for e in r.get("weekly_custom") or []]
        actual = [f"يوم {arnum.to_arabic_indic(e.get('day'))} "
                  f"{MEAL_MAP.get(e.get('meal') or '', '')} {arnum.fmt_qty(e.get('qty'))} "
                  f"({'بديل' if e.get('mode') == 'replace' else 'إضافة'})"
                  for e in r.get("date_custom") or []]
        rows.append([i + 1, sec_name.get(r["section"], r["section"]), r["name"],
                     r.get("unit") or "",
                     round(float(r.get("reference_rate") or 0), 6),
                     round(float(r.get("manual_rate") or 0), 6),
                     round(float(r.get("effective_rate") or r.get("rate") or 0), 6),
                     "، ".join(weekly), "، ".join(actual),
                     "مفعّل" if r.get("enabled") else "معطّل"])
    _sheet(ws, f"بيان معدلات خط الحدود الدولى — يوم {today}", header, rows,
           year, month)
    wb.save(path)
    return f"{FOLDER_RATES}/يوم {today}/{path.name}"


# ======================================================================
# قراءة الارشيف من القرص
# ======================================================================
def list_line_statements(year, month):
    """كل بيانات الخط القديمة والجديدة، بما فيها مجلدات النسخ والملفات المرقمة."""
    root = section_dir(year, month) / FOLDER_LINES
    result = {}
    if root.is_dir():
        for line_dir in sorted(root.iterdir()):
            if not line_dir.is_dir():
                continue
            items = []
            for path in line_dir.rglob("بيان*.xlsx"):
                if not path.is_file() or path.name.startswith("~$"):
                    continue
                day_part = next((part for part in reversed(path.parts)
                                 if part.startswith("يوم ")), "")
                match = re.search(r"(\d+)", day_part)
                rel = path.relative_to(section_dir(year, month))
                items.append((int(match.group(1)) if match else 0,
                              str(rel).replace("\\", "/")))
            items.sort(key=lambda item: (item[0], item[1]), reverse=True)
            if items:
                result[line_dir.name] = items
    return result


def list_rates_statements(year, month):
    """[(يوم, المسار النسبي لملف البيان)...] — كل بيانات المعدلات دون استبدال."""
    root = section_dir(year, month) / FOLDER_RATES
    out = []
    if root.is_dir():
        for path in root.rglob("بيان-المعدلات*.xlsx"):
            if not path.is_file() or path.name.startswith("~$"):
                continue
            day_part = next((part for part in reversed(path.parts)
                             if part.startswith("يوم ")), "")
            match = re.search(r"(\d+)", day_part)
            rel = path.relative_to(section_dir(year, month))
            out.append((int(match.group(1)) if match else 0,
                        str(rel).replace("\\", "/")))
    out.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return out


# ======================================================================
# حذف ملفات حفظ من القرص
# ======================================================================
def delete_files(year, month, rels):
    """يمسح ملفات حفظ + الفولدرات الفاضية اللي اتخلت وراه (لحد فولدر القسم)."""
    base = months.month_db_path(year, month).parent
    section = base / SECTION_FOLDER
    for rel in rels or []:
        try:
            p = base / rel
            if p.is_file():
                p.unlink()
            d = p.parent
            while d.is_dir() and d != base and d != section:
                if not any(d.iterdir()):
                    d.rmdir()
                    d = d.parent
                else:
                    break
        except OSError:
            pass
