# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""ملف المجند الشامل عبر كل الشهور (المرحلة ٤).

هوية المجند بين الشهور = الرقم العسكري (mil_no) — كل شهر له جدول recruits
مستقل بإيدزات خاصة. الخدمة بتقرأ الشهور الموجودة فعليًا على القرص (قراءة فقط
بدون إنشاء شهور فارغة)، وتبني: ملخص كل شهر + فترات الحالات + الخط الزمني
(الأحدث أولًا) + الإجماليات.
"""
import sqlite3

from core import arabic_numbers as arnum, dates
from core.config import MONTH_NAMES, month_folder
from data_access import db_attendance as da, db_recruits as dr
from data_access import storage

FILE_STATUSES = ("إجازة", "مأمورية", "مستشفى", "غياب", "أخرى")
FILE_ICONS = {"إجازة": "🏖️", "مأمورية": "🧭", "مستشفى": "🏥",
              "غياب": "🚫", "أخرى": "➕"}


def available_months():
    """الشهور الموجودة فعليًا على القرص [(year, month)] تصاعديًا (الأقدم أولًا)."""
    out = []
    for year in sorted(storage.list_years()):
        for m in range(1, 13):
            if (storage.year_path(year) / month_folder(m) / "month.db").exists():
                out.append((year, m))
    return out


def _runs(days, status):
    """فترات متصلة لحالة معينة من أيام مجند واحد {day: status} → [(from, to)]."""
    seq = sorted(d for d, st in days.items() if st == status)
    if not seq:
        return []
    out = []
    start = prev = seq[0]
    for d in seq[1:]:
        if d != prev + 1:
            out.append((start, prev))
            start = d
        prev = d
    out.append((start, prev))
    return out


def _month_row(year, month, mil_no):
    """بيانات المجند في شهر واحد — None لو مش في أصل قوة الشهر ده."""
    path = storage.year_path(year) / month_folder(month) / "month.db"
    if not path.exists():
        return None
    conn = sqlite3.connect(str(path), timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id FROM recruits WHERE mil_no=?", (mil_no,)).fetchone()
        if not row:
            return None
        rid = row["id"]
        att = conn.execute(
            "SELECT day, status FROM attendance WHERE recruit_id=? ORDER BY day",
            (rid,)).fetchall()
        permit_rows = conn.execute(
            "SELECT from_day, to_day FROM leave_permits WHERE recruit_id=?",
            (rid,)).fetchall()
    except sqlite3.OperationalError:
        return None                      # شهر قديم بلا جدول recruits
    finally:
        conn.close()
    days = {a["day"]: a["status"] for a in att}
    counts = {st: 0 for st in da.STATUSES}
    for st in days.values():
        counts[st] += 1
    return {
        "year": year, "month": month, "month_name": MONTH_NAMES[month - 1],
        "year_ar": arnum.to_arabic_indic(year), "month_label": MONTH_NAMES[month - 1] + " " + arnum.to_arabic_indic(year),
        "counts": counts, "recorded": len(att),
        "ranges": {st: _runs(days, st) for st in FILE_STATUSES},
        "permits": {(p["from_day"], p["to_day"]) for p in permit_rows},
    }


def build(year, month, rid):
    """ملف المجند كاملًا — None لو المجند مش في أصل قوة شهر السياق."""
    r = dr.get_recruit(year, month, rid)
    if not r:
        return None
    months_data = [row for row in
                   (_month_row(y, m, r["mil_no"]) for y, m in available_months())
                   if row]
    timeline = []
    for row in months_data:
        y, m = row["year"], row["month"]
        for st in FILE_STATUSES:
            for f, t in row["ranges"][st]:
                text = "{} من {} إلى {} ({} يومًا)".format(
                    st, dates.period_date(y, m, f), dates.period_date(y, m, t),
                    arnum.to_arabic_indic(t - f + 1))
                if st == "إجازة" and (f, t) in row["permits"]:
                    text += " ✓ تصريح"
                timeline.append({"ymd": (y, m, f), "icon": FILE_ICONS[st],
                                 "status": st, "text": text,
                                 "month": row["month_label"]})
    for field, icon, label in (("service_start", "🎖️", "دخول الخدمة"),
                               ("service_end", "🏁", "انتهاء الخدمة")):
        parsed = dates.parse_date(r.get(field) or "")
        if parsed:
            timeline.append({"ymd": (parsed.year, parsed.month, parsed.day),
                             "icon": icon, "status": "",
                             "text": label + " " + dates.format_date(parsed),
                             "month": MONTH_NAMES[parsed.month - 1] + " " + arnum.to_arabic_indic(parsed.year)})
    timeline.sort(key=lambda x: x["ymd"], reverse=True)
    totals = {st: 0 for st in da.STATUSES}
    for row in months_data:
        for st in da.STATUSES:
            totals[st] += row["counts"][st]
    return {
        "recruit": r,
        "months": sorted(months_data, key=lambda x: (x["year"], x["month"]), reverse=True),
        "timeline": timeline,
        "totals": totals,
        "n_months": len(months_data),
        "n_recorded": sum(row["recorded"] for row in months_data),
    }
