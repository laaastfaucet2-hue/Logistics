# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مسارات ملفات التاميدات المحلية: فتح المجلد/الملف + الطباعة والتقرير الشامل."""

import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from flask import abort, render_template, request, url_for
from core.auth_core import login_required
from core.config import MONTH_NAMES
from core import arabic_numbers as arnum
from core import dates
from core import egtime
from core.downloads import attachment
from data_access import db_letterhead as lhdb
from data_access import db_tameedat as dt
from data_access import db_rations as dr
from documents import docx_tameedat
from documents import xlsx_tameedat
from services import tameedat_fs

from . import tameedat_bp
from .context import _after_write, _ctx, _rb, _selected_day


# ======================================================================
# طباعة تأميدة واحدة (المستند الرسمي — بالدباجة والتوقيعات)
# ======================================================================
@tameedat_bp.route("/print/<int:record_id>")
@login_required
def print_one(record_id):
    year, month = _ctx()
    record = dt.get_record(year, month, record_id)
    if not record:
        return _rb(err="التأميدة المطلوبة غير موجودة في هذا الشهر")
    kind = dr.get_activation(year, month, "contractor") or "summer"
    ration_items, _ = dr.get_items(year, month, "contractor", kind)
    return render_template(
        "tameedat/print_one.html",
        record=record, year=year, month=month,
        month_name=MONTH_NAMES[month - 1],
        date_iso=f"{year:04d}-{month:02d}-{record['day']:02d}",
        weekday=egtime.weekday_ar(date(year, month, record["day"])),
        serial_month=[r["id"] for r in dt.month_records(year, month)].index(record_id) + 1,
        lh=[lhdb.get_setting(year, month, f"lh_{i}") for i in range(1, 5)],
        sig_right=(lhdb.get_setting(year, month, "sig_right_rank"),
                   lhdb.get_setting(year, month, "sig_right_name")),
        sig_left=(lhdb.get_setting(year, month, "sig_left_rank"),
                  lhdb.get_setting(year, month, "sig_left_name")),
        has_logo=bool(lhdb.get_setting(year, month, "logo_file")),
        ration_kind=kind, ration_items=ration_items,
    )


# ======================================================================
# ملفات التويبات المحلية: فتح المجلد / فتح الملف باسميه (قاعدة أزرار الملفات)
# ======================================================================
def _open_path(path):
    """يفتح مسارًا محليًا بنظام التشغيل؛ False في نسخة الويب (بلا واجهة رسومية)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _tab_or_404(tab):
    if tab not in tameedat_fs.TAB_FOLDERS:
        abort(404)
    return tab


@tameedat_bp.route("/open-folder/<tab>")
@login_required
def open_tab_folder(tab):
    """يفتح فولدر التبويب على الجهاز.

    تبويب «تأميدات اليوم المحدد» يتبع **اليوم المفتوح نفسه** (يوم ٧ ⇒ فولدر يوم ٧)
    مثل قسم الراغبين بالضبط — الزر يسمّي اليوم ويعلن تاريخه في رسالة النجاح.
    """
    tab = _tab_or_404(tab)
    year, month = _ctx()
    if tab == "day":
        day = _selected_day(year, month)
        day_txt = arnum.to_arabic_indic(str(day))
        folder = tameedat_fs.day_dir(year, month, day)
        name = f"تأميدات يوم {day_txt}"
        day_iso = f"{year:04d}-{month:02d}-{day:02d}"
        if _open_path(folder):
            return _rb(tab=tab, day=day_iso,
                       ok=f"تم فتح مجلد «تأميدات يوم {day_txt}» على جهازك 📂")
        # نسخة الويب: لا تتظاهر بالنجاح — رسالة صادقة + تنزيل ملف اليوم نفسه فورًا
        path = tameedat_fs.day_file(year, month, day)
        extra = ""
        if path.is_file():
            from flask import url_for
            extra = (f" — أو نزّل ملف «{tameedat_fs.day_file_name(day)}» فورًا من: "
                     f"{url_for('tameedat.day_file_download', day=day)}")
        else:
            extra = " — ويومك ده بلا تأميدات مسجلة، فالفولدر فاضي لحد ما تسجّل فيه"
        return _rb(tab=tab, day=day_iso, err=(
            f"مجلد «تأميدات يوم {day_txt}» من تبويب «تأميدات اليوم المحدد» جاهز محليًا "
            "داخل بيانات الشهر، لكن فتح المجلدات متاح من نسخة سطح المكتب على جهازك "
            "(الربط المحل)" + extra))
    folder = tameedat_fs.tab_dir(year, month, tab)
    name = tameedat_fs.TAB_FOLDERS[tab]
    if _open_path(folder):
        return _rb(tab=tab, ok=f"تم فتح مجلد «{name}» على جهازك 📂")
    return _rb(tab=tab, err=(f"مجلد «{name}» جاهز محليًا داخل بيانات الشهر، لكن فتح "
                             "المجلدات متاح من نسخة سطح المكتب على جهازك (الربط المحل) — "
                             "في نسخة الويب استخدم أزرار التنزيل وطباعة التقرير"))


def _open_day_file(year, month):
    """«📗 فتح ملف «تاميدات اليوم N.xlsx»» — ملف اليوم المفتوح نفسه (نسخة سطح المكتب).

    في نسخة الويب لا يتظاهر بالنجاح: رسالة صادقة + رابط تنزيل ملف اليوم فورًا.
    """
    day = _selected_day(year, month)
    day_txt = arnum.to_arabic_indic(str(day))
    day_iso = f"{year:04d}-{month:02d}-{day:02d}"
    fname = tameedat_fs.day_file_name(day)
    path = tameedat_fs.day_file(year, month, day)
    if not path.is_file():
        return _rb(tab="day", day=day_iso, err=(
            f"يوم {day_txt} مفيه تأميدات مسجلة بعد، فملفه «{fname}» لا يكون مُنشأً — "
            "سجّل أي تأميدة في اليوم ده فيتبني الملف تلقائيًا، أو افتح ملف الشهر كله من: "
            f"{url_for('tameedat.open_tab_file', tab='day', scope='month')}"))
    if _open_path(path):
        return _rb(tab="day", day=day_iso,
                   ok=f"تم فتح ملف «{fname}» — تأميدات يوم {day_txt} 📗")
    return _rb(tab="day", day=day_iso, err=(
        f"ملف «{fname}» محفوظ محليًا في فولدر «تأميدات يوم {day_txt}» داخل بيانات الشهر، "
        "لكن فتح الملفات متاح من نسخة سطح المكتب على جهازك (الربط المحل) — أو نزّله فورًا من: "
        f"{url_for('tameedat.day_file_download', day=day)}"))


def _open_month_day_file(year, month):
    """ملف الشهر الكامل «إجمالي الشهر.xlsx» — يبقى متاحًا بجوار ملف اليوم (?scope=month)."""
    fname = tameedat_fs.TAB_XLSX["day"]
    path = tameedat_fs.tab_dir(year, month, "day") / fname
    if not path.is_file():
        return _rb(tab="day",
                   err=f"ملف «{fname}» لم يُنشأ بعد — احفظ أي بيانات في هذا التبويب أولًا")
    if _open_path(path):
        return _rb(tab="day", ok=f"تم فتح ملف «{fname}» — إجمالي الشهر كله 📗")
    return _rb(tab="day", err=(
        f"ملف «{fname}» محفوظ محليًا في فولدر «تأميدات اليوم المحدد»، لكن فتح الملفات متاح "
        "من نسخة سطح المكتب على جهازك (الربط المحل) — أو استخدم زر تنزيل ملف اليوم"))


@tameedat_bp.route("/open-file/<tab>")
@login_required
def open_tab_file(tab):
    """يفتح ملف الإكسل المحلي على الجهاز.

    تبويب «تأميدات اليوم المحدد» صار **يتبع اليوم المفتوح** مثل زر المجلد بالضبط
    (توجيه المستخدم ٠٧/١٠/٢٠٢٦: «كل يوم يتب بيومة»): يوم ٧ ⇒ ملف «تاميدات اليوم ٧.xlsx».
    وملف الشهر الكامل «إجمالي الشهر.xlsx» يبقى متاحًا بالطلب نفسه مع `?scope=month`.
    """
    tab = _tab_or_404(tab)
    year, month = _ctx()
    if tab == "day":
        if request.args.get("scope") == "month":
            return _open_month_day_file(year, month)
        return _open_day_file(year, month)
    if tab == "report":
        folder = tameedat_fs.report_dir(year, month)
        candidates = sorted(folder.glob("*.xlsx"), key=lambda p: p.stat().st_mtime,
                            reverse=True)
        if not candidates:
            return _rb(tab="report", err="لا يوجد ملف تقرير محفوظ بعد — ابنِ تقرير الإكسل أولًا")
        path, _ = candidates[0], None
        fname = path.name
    else:
        fname = tameedat_fs.TAB_XLSX[tab]
        path = tameedat_fs.tab_dir(year, month, tab) / fname
        if not path.is_file():
            return _rb(tab=tab, err=f"ملف «{fname}» لم يُنشأ بعد — احفظ أي بيانات في هذا التبويب أولًا")
    if _open_path(path):
        return _rb(tab=tab, ok=f"تم فتح ملف «{fname}» على جهازك 📗")
    return _rb(tab=tab, err=(f"ملف «{fname}» محفوظ محليًا في فولدر التبويب، لكن فتح "
                             "الملفات متاح من نسخة سطح المكتب على جهازك (الربط المحل)"))

@tameedat_bp.route("/day-file/<int:day>")
@login_required
def day_file_download(day):
    """تنزيل ملف إكسل يوم محدد من تبويب «تأميدات اليوم المحدد» — بديل الفتح في نسخة الويب."""
    year, month = _ctx()
    if not 1 <= day <= egtime.days_in_month(year, month):
        abort(404)
    path = tameedat_fs.day_file(year, month, day)
    if not path.is_file():
        return _rb(tab="day", day=f"{year:04d}-{month:02d}-{day:02d}",
                   err=(f"يوم {arnum.to_arabic_indic(str(day))} مفيه تأميدات مسجلة بعد — "
                        "سجّل تأميدة أولًا فيتبني ملف اليوم تلقائيًا"))
    return attachment(path, f"tameedat-day-{day:02d}-{year}-{month:02d}.xlsx")


@tameedat_bp.route("/report/build/<fmt>")
@login_required
def report_build(fmt):
    """يبني التقرير رسميًا ويحفظه محليًا في فولدر «طباعة التقرير الشامل» ثم ينزّله."""
    year, month = _ctx()
    if fmt == "xlsx":
        path = xlsx_tameedat.rebuild(year, month)
        _after_write(year, month)
        return attachment(path, f"tameedat-{year}-{month:02d}.xlsx")
    if fmt == "docx":
        path = docx_tameedat.rebuild(year, month)
        _after_write(year, month)
        return attachment(path, f"tameedat-{year}-{month:02d}.docx")
    abort(404)


@tameedat_bp.route("/report/file/<name>")
@login_required
def report_download(name):
    """تنزيل ملف تقرير سبق حفظه محليًا (مسار مؤمّن داخل فولدر التقرير فقط)."""
    year, month = _ctx()
    if Path(name).name != name:
        abort(404)
    path = tameedat_fs.report_dir(year, month) / name
    if not path.is_file() or path.suffix.lower() not in (".xlsx", ".docx"):
        return _rb(tab="report", err="الملف غير موجود — أعد بناء التقرير")
    return attachment(path, f"tameedat-{year}-{month:02d}{path.suffix}")


@tameedat_bp.route("/report/print")
@login_required
def report_print():
    """نسخة الطباعة الرسمية (PDF من نافذة الطباعة) — تفصيل يومي + ملخص شهري."""
    year, month = _ctx()
    summary, totals = dt.month_summary(year, month)
    return render_template(
        "tameedat/print_report.html",
        year=year, month=month, month_name=MONTH_NAMES[month - 1],
        records=dt.month_records(year, month),
        summary=summary, totals=totals,
        build_stamp=dates.format_datetime(egtime.now()),
        lh=[lhdb.get_setting(year, month, f"lh_{i}") for i in range(1, 5)],
        sig_right=(lhdb.get_setting(year, month, "sig_right_rank"),
                   lhdb.get_setting(year, month, "sig_right_name")),
        sig_left=(lhdb.get_setting(year, month, "sig_left_rank"),
                  lhdb.get_setting(year, month, "sig_left_name")),
        has_logo=bool(lhdb.get_setting(year, month, "logo_file")),
    )


@tameedat_bp.route("/report/open-folder")
@login_required
def report_open_folder():
    year, month = _ctx()
    folder = tameedat_fs.report_dir(year, month)
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(folder))  # type: ignore[attr-defined]  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return _rb(tab="report",
                   err="فتح المجلد متاح عند تشغيل البرنامج على جهازك — استخدم أزرار التنزيل")
    return _rb(tab="report", ok="تم فتح فولدر «طباعة التقرير الشامل» من الملف المحلي 📂")
