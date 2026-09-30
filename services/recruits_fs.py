# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الملفات المحلية لقسم المجندين — ٧ مجلدات بأسماء التويبات (توجيه ٢٨/٠٩):

    database/<السنة>/<الشهر>/08-المجندين/
        أصل القوة/                  ← سجل المجندين.xlsx
        اليومية العامة/             ← اليومية العامة.xlsx (شبكة من يوم ١ إلى آخر الشهر)
                                       + كشف-الحالات-<سنة>-<شهر>.docx
        الحضور/                     ← الحضور.xlsx
        الإجازات/                   ← الإجازات.xlsx + كشف-الإجازات.docx + تصاريح/
        الغياب/                     ← الغياب.xlsx
        أخرى/                       ← أخرى.xlsx
        الإحصائيات والإشعارات/      ← الإحصائيات.xlsx

كلها مرايا مقروءة تتحدث بعد كل حفظ في قسم المجندين، ورؤوسها بالأزرق الفاتح
المعتمد (BDD7EE) عبر المولّد الموحد _save_xlsx.
"""
from datetime import date as _date

from core import arabic_numbers as arnum, egtime
from core.config import MONTH_NAMES
from data_access import storage
from data_access import db_attendance as da
from data_access import db_recruits as dr
from services.tameedat_fs import _save_xlsx, XLSX_BLUE   # المولد الموحد بالأزرق الفاتح

TAB_FOLDERS = {
    "registry": "أصل القوة",
    "journal": "اليومية العامة",
    "present": "الحضور",
    "leaves": "الإجازات",
    "absent": "الغياب",
    "other": "أخرى",
    "stats": "الإحصائيات والإشعارات",
}

TAB_XLSX = {key: name + ".xlsx" for key, name in TAB_FOLDERS.items()}


def dir(year, month, tab):
    """مجلد تويب واحد داخل 08-المجندين — يُنشأ إن لم يوجد."""
    return storage.recruits_dir(year, month, TAB_FOLDERS[tab])


def ensure_folders(year, month):
    for key in TAB_FOLDERS:
        dir(year, month, key)
    return storage.recruits_dir(year, month)


def _meta(year, month):
    return {
        "القسم": "قسم المجندين",
        "الشهر": MONTH_NAMES[month - 1],
        "السنة": year,
        "آخر تحديث": egtime.now().isoformat(timespec="seconds"),
    }


def _day_head(year, month, day):
    """رأس عمود اليوم: اسم اليوم + رقمه بالعربي — من يوم ١ إلى آخر الشهر."""
    wd = egtime.weekday_ar(_date(year, month, day))
    return "{} {}".format(wd, arnum.to_arabic_indic(str(day)))


def snapshot_all(year, month):
    """يعيد كتابة مرايا التويبات السبعة بعد أي حفظ في قسم المجندين."""
    ensure_folders(year, month)
    recruits = dr.list_recruits(year, month)
    names = {r["id"]: r["name"] for r in recruits}
    mils = {r["id"]: (r["mil_no"] or "—") for r in recruits}
    matrix = da.month_matrix(year, month)
    eom = egtime.days_in_month(year, month)

    _registry_xlsx(year, month, recruits)
    _journal_xlsx(year, month, recruits, names, mils, matrix, eom)
    _present_xlsx(year, month, recruits, names, mils, matrix, eom)
    _leaves_xlsx(year, month, recruits, names, mils, matrix, eom)
    _absent_xlsx(year, month, names, mils, matrix)
    _other_xlsx(year, month, names, mils, matrix, eom)
    _stats_xlsx(year, month, recruits, names, mils, matrix, eom)
    return True


# ==================== ١) أصل القوة ====================
def _registry_xlsx(year, month, recruits):
    rows = []
    for idx, r in enumerate(recruits, 1):
        rows.append((idx, r["name"], r["mil_no"] or "—",
                     r["governorate"] or "—", r["city"] or "—",
                     r["address"] or "—",
                     r["service_start"] or "—", r["service_end"] or "—",
                     "نعم" if r["has_cert"] else "لا",
                     r["cert_date"] or "—", r["cert_expiry"] or "—"))
    _save_xlsx(dir(year, month, "registry") / TAB_XLSX["registry"], [(
        "أصل القوة",
        ["م", "الاسم", "الرقم العسكري", "المحافظة", "المدينة", "العنوان",
         "بداية الخدمة", "نهاية الخدمة", "شهادة طبية", "تاريخ الشهادة", "انتهاء الشهادة"],
        rows)])


# ==================== ٢) اليومية العامة — شبكة الشهر كاملة ====================
def _journal_xlsx(year, month, recruits, names, mils, matrix, eom):
    heads = ["م", "الاسم", "الرقم العسكري"]
    heads += [_day_head(year, month, d) for d in range(1, eom + 1)]
    heads += ["حضور", "إجازة", "غياب", "مأمورية", "مستشفى", "أخرى"]
    rows = []
    for idx, r in enumerate(recruits, 1):
        days = matrix.get(r["id"], {})
        counts = {st: 0 for st in da.STATUSES}
        line = [idx, r["name"], mils[r["id"]]]
        for d in range(1, eom + 1):
            st = days.get(d)
            line.append(st if st else "—")
            if st in counts:
                counts[st] += 1
        line += [counts[st] if counts[st] else "—" for st in da.STATUSES]
        rows.append(tuple(line))
    _save_xlsx(dir(year, month, "journal") / TAB_XLSX["journal"], [(
        "اليومية العامة من يوم ١ إلى {}".format(eom), heads, rows)])


# ==================== ٣) الحضور ====================
def _present_xlsx(year, month, recruits, names, mils, matrix, eom):
    lines = []
    for rid, days in matrix.items():
        days_present = sorted(d for d, st in days.items() if st == "حضور")
        if days_present:
            lines.append((names.get(rid, "—"), mils.get(rid, "—"),
                          len(days_present),
                          "، ".join(arnum.to_arabic_indic(str(d))
                                    for d in days_present)))
    lines.sort(key=lambda x: x[0])
    rows = [(i,) + ln for i, ln in enumerate(lines, 1)]
    per_day = []
    for d in range(1, eom + 1):
        dmap = da.get_day_map(year, month, d)
        counts = {st: sum(1 for x in dmap.values() if x["status"] == st)
                  for st in da.STATUSES}
        meta = da.get_meta(year, month, d)
        if counts["حضور"] or meta["locked"]:
            per_day.append((d, _day_head(year, month, d).split()[0],
                            counts["حضور"], counts["إجازة"], counts["غياب"],
                            counts["مأمورية"], counts["مستشفى"], counts["أخرى"],
                            "مُثبّت" if meta["locked"] else "—"))
    _save_xlsx(dir(year, month, "present") / TAB_XLSX["present"], [
        ("الحضور",
         ["م", "الاسم", "الرقم العسكري", "عدد أيام الحضور", "الأيام"], rows),
        ("ملخص الأيام",
         ["اليوم", "اسم اليوم", "حضور", "إجازة", "غياب", "مأمورية", "مستشفى",
          "أخرى", "الحالة"], per_day)])


# ==================== ٤) الإجازات ====================
def _leaves_xlsx(year, month, recruits, names, mils, matrix, eom):
    ranges = da.leave_ranges(year, month, matrix, 1, eom)
    rows = []
    idx = 0
    for r in recruits:
        for (from_day, to_day) in ranges.get(r["id"], []):
            idx += 1
            rows.append((idx, r["name"], mils[r["id"]],
                         to_day - from_day + 1,
                         "{} – {}".format(from_day, to_day),
                         MONTH_NAMES[month - 1], year))
    _save_xlsx(dir(year, month, "leaves") / TAB_XLSX["leaves"], [(
        "الإجازات",
        ["م", "الاسم", "الرقم العسكري", "عدد الأيام", "المدى (من – إلى)",
         "الشهر", "السنة"], rows)])


# ==================== ٥) الغياب ====================
def _absent_xlsx(year, month, names, mils, matrix):
    lines = []
    for rid, days in matrix.items():
        offs = sorted(d for d, st in days.items() if st == "غياب")
        if offs:
            lines.append((names.get(rid, "—"), mils.get(rid, "—"), len(offs),
                          "، ".join(str(d) for d in offs)))
    lines.sort(key=lambda x: x[0])
    rows = [(i,) + ln for i, ln in enumerate(lines, 1)]
    _save_xlsx(dir(year, month, "absent") / TAB_XLSX["absent"], [(
        "الغياب",
        ["م", "الاسم", "الرقم العسكري", "عدد أيام الغياب", "الأيام"], rows)])


# ==================== ٦) أخرى (مأمورية/مستشفى/أخرى) ====================
def _other_xlsx(year, month, names, mils, matrix, eom):
    notes = {}
    for d in range(1, eom + 1):
        for rid, x in da.get_day_map(year, month, d).items():
            if x.get("note"):
                notes[(rid, d)] = x["note"]
    rows = []
    idx = 0
    for rid, days in matrix.items():
        for st in ("مأمورية", "مستشفى", "أخرى"):
            offs = sorted(d for d, s in days.items() if s == st)
            if offs:
                idx += 1
                note = "، ".join(notes[(rid, d)] for d in offs if (rid, d) in notes)
                rows.append((idx, names.get(rid, "—"), mils.get(rid, "—"), st,
                             len(offs), "، ".join(str(d) for d in offs),
                             note or "—"))
    _save_xlsx(dir(year, month, "other") / TAB_XLSX["other"], [(
        "حالات أخرى",
        ["م", "الاسم", "الرقم العسكري", "الحالة", "عدد الأيام", "الأيام",
         "ملاحظات"], rows)])


# ==================== ٧) الإحصائيات والإشعارات ====================
def _stats_xlsx(year, month, recruits, names, mils, matrix, eom):
    rows = []
    for idx, r in enumerate(recruits, 1):
        days = matrix.get(r["id"], {})
        counts = {st: sum(1 for s in days.values() if s == st) for st in da.STATUSES}
        rows.append((idx, r["name"], mils[r["id"]],
                     counts["حضور"], counts["إجازة"], counts["غياب"],
                     counts["مأمورية"], counts["مستشفى"], counts["أخرى"],
                     sum(counts.values())))
    missing = da.days_without_journal(year, month, eom)
    missing_rows = [(d, _day_head(year, month, d).split()[0], "بلا يومية")
                    for d in missing]
    _save_xlsx(dir(year, month, "stats") / TAB_XLSX["stats"], [
        ("إحصائيات المجندين",
         ["م", "الاسم", "الرقم العسكري", "حضور", "إجازة", "غياب", "مأمورية",
          "مستشفى", "أخرى", "إجمالي الأيام المسجلة"], rows),
        ("أيام بلا يومية", ["اليوم", "اسم اليوم", "الحالة"], missing_rows)])
