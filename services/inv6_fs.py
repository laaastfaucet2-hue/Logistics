# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""حفظ أيام «دفتر 6 مخازن (جرد الأصناف)» على القرص (توجيه ١٠/١٠).

المكان المعتمد:
    database/<السنة>/<الشهر>/06-مستودعات وسجلات/6-مخازن/
        يوم ١/          ← فولدر باسم يوم الجرد (كل يوم فولدر لوحده)
            1-9-2026.xlsx  ← شيت الإكسل مطابق لملف التصميم المعتمد
"""
import shutil

from core import arabic_numbers as arnum
from core.config import SECTIONS
from data_access import storage

SUB = "6-مخازن"


def _section_index():
    for index, section in enumerate(SECTIONS, start=1):
        if section["key"] == "warehouses_records":
            return index
    raise KeyError("warehouses_records")


def _day_dir_path(year, month, day):
    """مسار فولدر يوم الجرد **بلا إنشاء** — توجيه ١٥/١٠: الفولدر بيتعمل عند الحفظ بس،
    مش بمجرد فتح التاب أو تغيير يوم الجرد (كان بيسيب فولدر فاضي ويوهّم المستخدم)."""
    return storage.section_files_path(year, month, _section_index()) / SUB / \
        f"يوم {arnum.to_arabic_indic(str(int(day)))}"


def day_dir(year, month, day):
    """فولدر يوم الجرد: 06-مستودعات وسجلات/6-مخازن/يوم ١ — يُنشَأ عند الحفظ فقط."""
    d = _day_dir_path(year, month, day)
    d.mkdir(parents=True, exist_ok=True)
    return d


def day_file(year, month, day):
    """مسار ملف الإكسل ليوم الجرد: <يوم>/<يوم>-<شهر>-<سنة>.xlsx بأرقام لاتينية.
    لا يُنشئ فولدر — الفحص/العرض/التحميل ما يعملوش مجلدات فاضية."""
    d, m, y = int(day), int(month), int(year)
    return _day_dir_path(year, month, day) / f"{d}-{m}-{y}.xlsx"


def rel_path(year, month, day):
    """المسار النسبي داخل فولدر الشهر (للقوائم والمطابقة)."""
    d, m, y = int(day), int(month), int(year)
    return f"06-مستودعات وسجلات/{SUB}/يوم {arnum.to_arabic_indic(str(d))}/" \
           f"{d}-{m}-{y}.xlsx"


def save_to_disk(year, month, day):
    """يولّد ملف الإكسل ليوم الجرد من البيانات المحفوظة. يرجع المسار النسبي.
    هنا (وقت الحفظ) بس بينشأ فولدر اليوم (توجيه ١٥/١٠)."""
    from data_access import db_inv6 as di6
    from services import inv6_build as ib
    from services import inv6_xlsx as ix
    data = di6.load_day(year, month, day)
    if not data:
        view = ib.day_view(year, month, day)
        header, rows = view["header"], view["rows"]
    else:
        header = data["header"]
        rows = ib._with_diffs(data["rows"])   # الزيادة/النقص بتتكتب في الملف
    fpath = day_file(year, month, day)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    ix.write_day_xlsx(fpath, year, month, day, header, rows)
    return rel_path(year, month, day)


def delete_day_files(year, month, day):
    """يحذف فولدر يوم الجرد (بملفاته) لو موجود."""
    d = _safe_day_dir(year, month, day)
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


def _safe_day_dir(year, month, day):
    """فولدر اليوم دون إنشاؤه (مصدر واحد مع مسار الحفظ)."""
    return _day_dir_path(year, month, day)
