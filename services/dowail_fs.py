# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""حفظ «تفاريد خط الحدود الدولى» على القرص — أربع فولدرات محلية:

14-تفاريد خط الحدود الدولى
├─ أوراق وإيصالات الصرف/يوم F/خط X/  (مجمع-خط.xlsx + نقاط-خط.xlsx + data.json)
├─ إجمالي خطوط التوزيع/خط X/يوم F/  (نفس الـ 2 ملفات إكسل)
├─ إدارة الخطوط والنقاط/خط X/يوم T/  (بيان.xlsx — كل تغيير في الخط/نقاطه)
└─ تعديل معدلات الأصناف/يوم T/       (بيان-المعدلات.xlsx — كل تغيير في المعدلات)

فولدر اليوم في الحفظ = أول يوم التوزيعة (ولو تكرر: «يوم F (2)»).
"""
import json
import re
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from core import arabic_numbers as arnum, egtime
from core.config import DAYS, MEAL_MAP
from data_access import months
from services import dowail_build as dbuild

SECTION_FOLDER = "14-تفاريد خط الحدود الدولى"
FOLDER_PAPERS = "أوراق وإيصالات الصرف"
FOLDER_TOTALS = "إجمالي خطوط التوزيع"
FOLDER_LINES = "إدارة الخطوط والنقاط"
FOLDER_RATES = "تعديل معدلات الأصناف"


def _safe(name):
    return re.sub(r"[^\w\u0600-\u06FF\-]+", "_", name).strip("_") or "عنصر"


def section_dir(year, month):
    """فولدر القسم داخل الشهر."""
    base = months.month_db_path(year, month).parent
    d = base / SECTION_FOLDER
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sheet(ws, title, header, rows):
    ws.append([title])
    ws.append(header)
    for r in rows:
        ws.append(r)
    ws["A1"].font = Font(bold=True, size=14)
    for cell in ws[2]:
        cell.font = Font(bold=True)


def _agg_rows(line, rates, force, dates, year, month):
    """أسطر الأصناف: الحصيلة = المعدل×القوة×الأيام + المخصص×القوة (قاعدة ٢٧)."""
    dd = [date(int(year), int(month), int(x)) for x in dates]
    out = []
    for i, r in enumerate(rates):
        row = dbuild.item_row(r, force, dd)
        out.append([i + 1, row["name"], row["unit"], row["rate"],
                    row["days"], row["total"], ""])
    return out


def _agg_header():
    return ["م", "المادة التموينية المصروفة", "الوحدة", "المعدل اليومى",
            "أيام الصرف", "الحصيلة الإجمالية", "ملاحظات"]


def _write_line_xlsx(path, line, rates, dates, year, month,
                     store_keeper, day_from, day_to):
    """ملف «مجمع-خط»: شيت واحد بكل أصناف الخط."""
    wb = Workbook()
    ws = wb.active
    ws.title = "مجمع الخط"
    rows = _agg_rows(line, rates, line["total_force"], dates, year, month)
    _sheet(ws, f"إذن صرف «{line['name']}» — يومي {day_from} إلى {day_to} "
               f"({len(dates)} يوم) — إجمالي القوة {line['total_force']} فرد/يوم"
               + (f" — أمين المخازن: {store_keeper}" if store_keeper else ""),
           _agg_header(), rows)
    wb.save(path)


def _write_points_xlsx(path, line, rates, dates, year, month,
                       store_keeper, day_from, day_to):
    """ملف «نقاط-خط»: شيت لكل نقطة."""
    wb = Workbook()
    wb.remove(wb.active)
    for p in line["points"]:
        ws = wb.create_sheet(_safe(p["name"])[:31])
        rows = _agg_rows(line, rates, p["force"], dates, year, month)
        _sheet(ws, f"نقطة «{p['name']}» — خط «{line['name']}»"
                   f" (القوة {p['force']}) — يومي {day_from} إلى {day_to} ({len(dates)} يوم)"
                   + (f" — أمين المخازن: {store_keeper}" if store_keeper else ""),
               _agg_header(), rows)
    if not line["points"]:
        ws = wb.create_sheet("النقاط")
        _sheet(ws, f"خط «{line['name']}» — مفيش نقاط", _agg_header(), [])
    wb.save(path)


def _day_folder_name(data, n_saves_same_from):
    d = arnum.to_arabic_indic(int(data["date_from"]))
    return "يوم " + d + (f" ({arnum.to_arabic_indic(n_saves_same_from)})"
                         if n_saves_same_from > 1 else "")


def save_to_disk(year, month, data, n_saves_same_from=1):
    """يحفظ التوزيعة في (أوراق وإيصالات + إجمالي خطوط التوزيع) ويرجع الملفات النسبية."""
    sec = section_dir(year, month)
    day = _day_folder_name(data, n_saves_same_from)
    dates = data.get("dates") or list(range(
        int(data["date_from"]),
        min(int(data["date_from"]) + int(data.get("issue_days") or 1),
            int(data["date_to"]) + 1)))
    y, m = int(data.get("year") or year), int(data.get("month") or month)
    keeper = data.get("store_keeper") or ""
    files = []
    for lp in data.get("papers") or []:
        line = lp["line"]
        # 1) أوراق وإيصالات الصرف/يوم F/خط X/
        d1 = sec / FOLDER_PAPERS / day / line["name"]
        d1.mkdir(parents=True, exist_ok=True)
        agg = d1 / f"مجمع-{line['name']}.xlsx"
        pts = d1 / f"نقاط-{line['name']}.xlsx"
        _write_line_xlsx(agg, line, data["rates"], dates, y, m,
                         keeper, data["date_from"], data["date_to"])
        _write_points_xlsx(pts, line, data["rates"], dates, y, m,
                           keeper, data["date_from"], data["date_to"])
        (d1 / "data.json").write_text(
            json.dumps({"store_keeper": keeper,
                        "date_from": data["date_from"], "date_to": data["date_to"],
                        "issue_days": data["issue_days"], "line": lp},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        files += [f"{SECTION_FOLDER}/{FOLDER_PAPERS}/{day}/{line['name']}/{f.name}"
                  for f in (agg, pts, d1 / "data.json")]
        # 2) إجمالي خطوط التوزيع/خط X/يوم F/
        d2 = sec / FOLDER_TOTALS / line["name"] / day
        d2.mkdir(parents=True, exist_ok=True)
        _write_line_xlsx(d2 / agg.name, line, data["rates"], dates, y, m,
                         keeper, data["date_from"], data["date_to"])
        _write_points_xlsx(d2 / pts.name, line, data["rates"], dates, y, m,
                           keeper, data["date_from"], data["date_to"])
        files += [f"{SECTION_FOLDER}/{FOLDER_TOTALS}/{line['name']}/{day}/{f.name}"
                  for f in (d2 / agg.name, d2 / pts.name)]
    return files


# ======================================================================
# بيانات الخطوط والنقاط — بيان إكسل مع كل تغيير (الارشيف)
# ======================================================================
def write_line_statement(year, month, line):
    """فولدر اليوم + بيان إكسل للحالة الحالية للخط. يرجع المسار النسبي."""
    today = arnum.to_arabic_indic(egtime.now().day)
    d = section_dir(year, month) / FOLDER_LINES / line["name"] / f"يوم {today}"
    d.mkdir(parents=True, exist_ok=True)
    path = d / "بيان.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "بيان الخط"
    header = ["م", "اسم النقطة", "القوة", "المسؤول"]
    rows = [[i + 1, p["name"], int(p["force"] or 0), p.get("responsible") or ""]
            for i, p in enumerate(line["points"])]
    _sheet(ws, f"بيان «{line['name']}» — يوم {today} — إجمالي القوة {line['total_force']}",
           header, rows)
    wb.save(path)
    return f"{FOLDER_LINES}/{line['name']}/يوم {today}/بيان.xlsx"


def write_rates_statement(year, month, rates):
    """فولدر اليوم + بيان إكسل لكل المعدلات. يرجع المسار النسبي."""
    today = arnum.to_arabic_indic(egtime.now().day)
    d = section_dir(year, month) / FOLDER_RATES / f"يوم {today}"
    d.mkdir(parents=True, exist_ok=True)
    path = d / "بيان-المعدلات.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "المعدلات"
    header = ["م", "القسم", "اسم الصنف", "الوحدة", "معدل الفرد اليومى",
              "مخصص الأيام (يُضاف)", "الحالة"]
    sec_name = {"tamween": "المقررات التموينية", "contractor": "مقررات المتعهد"}
    rows = []
    for i, r in enumerate(rates):
        labels = [f"{DAYS[int(e.get('weekday') or 0)]} {MEAL_MAP.get(e.get('meal') or '', '')} "
                  f"{arnum.fmt_qty(e.get('qty'))}" for e in r.get("custom") or []]
        rows.append([i + 1, sec_name.get(r["section"], r["section"]), r["name"],
                     r.get("unit") or "", round(float(r.get("rate") or 0), 6),
                     "، ".join(labels), "مفعّل" if r.get("enabled") else "معطّل"])
    _sheet(ws, f"بيان معدلات خط الحدود الدولى — يوم {today}", header, rows)
    wb.save(path)
    return f"{FOLDER_RATES}/يوم {today}/بيان-المعدلات.xlsx"


# ======================================================================
# قراءة الارشيف من القرص
# ======================================================================
def list_line_statements(year, month):
    """{اسم الخط: [(يوم, المسار النسبي لفولدر اليوم)...]} — أرشيف بيانات الخطوط."""
    root = section_dir(year, month) / FOLDER_LINES
    result = {}
    if root.is_dir():
        for line_dir in sorted(root.iterdir()):
            if not line_dir.is_dir():
                continue
            items = []
            for d in line_dir.iterdir():
                if d.is_dir() and (d / "بيان.xlsx").is_file():
                    m = re.search(r"(\d+)", d.name)
                    items.append((int(m.group(1)) if m else 0,
                                  f"{FOLDER_LINES}/{line_dir.name}/{d.name}/بيان.xlsx"))
            items.sort(reverse=True)
            if items:
                result[line_dir.name] = items
    return result


def list_rates_statements(year, month):
    """[(يوم, المسار النسبي لملف البيان)...] — أرشيف المعدلات."""
    root = section_dir(year, month) / FOLDER_RATES
    out = []
    if root.is_dir():
        for d in root.iterdir():
            if d.is_dir() and (d / "بيان-المعدلات.xlsx").is_file():
                m = re.search(r"(\d+)", d.name)
                out.append((int(m.group(1)) if m else 0,
                            f"{FOLDER_RATES}/{d.name}/بيان-المعدلات.xlsx"))
    out.sort(reverse=True)
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
