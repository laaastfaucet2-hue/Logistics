# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""فتح ملفات قسم «الراغبين» المحلية على جهاز المستخدم (الربط المحل).

توجيه المستخدم ٠٦/١٠/٢٠٢٦:
  - «فتح مجلد الراغبين» يفتح فولدر **اليوم المفتوح** نفسه (لو اليوم ٧ ⇒ مجلد يوم ٧).
  - بجوار كل جهة مسجلة زر «فتح إكسل راغبين» يفتح ملف إكسل تلك الجهة في يومها.

في نسخة الويب (بلا واجهة رسومية) لا يتظاهر البرنامج بالنجاح: يعلن التعذر
برسالة واضحة بدل الفشل الصامت — قاعدة الربط المحل الملزمة.
"""
import os
import subprocess
import sys

from flask import request
from core.auth_core import login_required
from core import arabic_numbers as arnum
from services.raghibin import files_daily as day_files

from . import raghibin_bp
from .context import _ctx, _rb, _selected_day, _selected_entity


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


def _day_number(year, month):
    """اليوم المطلوب من الرابط (?d=) وإلا اليوم المفتوح حاليًا في القسم."""
    raw = request.values.get("d")
    if raw:
        day = arnum.parse_int(raw)
        if day is None:
            day = 0
        if day:
            from core import egtime
            if 1 <= day <= egtime.days_in_month(year, month):
                return day
    return _selected_day(year, month)


@raghibin_bp.route("/open-folder")
@login_required
def open_day_folder():
    """«📂 فتح مجلد الراغبين» — فولدر اليوم المفتوح بالضبط (يوم ٧ ⇒ مجلد يوم ٧)."""
    year, month = _ctx()
    day = _day_number(year, month)
    folder = day_files.day_dir(year, month, day)
    day_txt = arnum.to_arabic_indic(str(day))
    if _open_path(folder):
        return _rb(tab="daily", d=day, ok=f"تم فتح مجلد «يوم {day_txt}» من قسم الراغبين 📂")
    from flask import url_for
    entity = _selected_entity(year, month)
    extra = ""
    if entity:
        extra = (f" — أو نزّل ملف «{entity['name']}» فورًا من: "
                 f"{url_for('raghibin.download_day_excel')}?d={day}&e={entity['id']}")
    return _rb(tab="daily", d=day, err=(
        f"مجلد «يوم {day_txt}» جاهز محليًا داخل بيانات الشهر، لكن فتح المجلدات متاح "
        "من نسخة سطح المكتب على جهازك (الربط المحلي)" + extra +
        " — أو استخدم زر «فتح إكسل راغبين» بجوار أي جهة للتنزيل من نسخة الويب"))


@raghibin_bp.route("/open-excel")
@login_required
def open_entity_excel():
    """«📗 فتح إكسل راغبين» بجوار الجهة — يبني ملف يوم/جهة ثم يفتحه على الجهاز."""
    year, month = _ctx()
    day = _day_number(year, month)
    entity = _selected_entity(year, month)
    if not entity:
        return _rb(tab="daily", d=day, err="مفيش جهات في قاموس الشهر لسه — سجّل تأميدة أولًا")
    path = day_files.write_day_file(year, month, day, entity["id"], entity["name"])
    day_txt = arnum.to_arabic_indic(str(day))
    if _open_path(path):
        return _rb(tab="daily", d=day, ok=(
            f"تم فتح ملف إكسل «{entity['name']}» ليوم {day_txt} 📗"))
    from flask import url_for
    return _rb(tab="daily", d=day, err=(
        f"ملف إكسل «{entity['name']}» ليوم {day_txt} اتبنى محليًا ويمكن تنزيله الآن "
        f"من: {url_for('raghibin.download_day_excel')}?d={day}&e={entity['id']} — "
        "وفتح الملفات مباشرة متاح من نسخة سطح المكتب"))


@raghibin_bp.route("/day-excel")
@login_required
def download_day_excel():
    """تنزيل ملف يوم/جهة مباشرة — بديل الفتح في نسخة الويب."""
    from core.downloads import attachment
    year, month = _ctx()
    day = _day_number(year, month)
    entity = _selected_entity(year, month)
    if not entity:
        return _rb(tab="daily", d=day, err="اختر جهة أولًا لتنزيل كشف راغبيها")
    path = day_files.write_day_file(year, month, day, entity["id"], entity["name"])
    return attachment(path, fallback=f"raghibin-day{day}.xlsx")
