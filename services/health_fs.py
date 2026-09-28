# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""فولدرات قسم «الصحة» المحلية — داخل فولدر الشهر مثل باقي الأقسام:

database/<سنة>/<شهر>/13-الصحة/
├── الرش والتعقيم/               → محضر رش وتقفيم.docx
├── الكشف الدوري على المجندين/
│   ├── يوم ١/                   → كشف الدوري — يوم ١.docx   (٣ أيام قابلة للتعديل)
│   ├── يوم ١٥/                  → ...
│   └── يوم ٣٠/                  → ...
├── تطهير الخزانات/              → محضر تطهير خزانات.docx
└── فحص مياة الشرب/              → تقرير فحص عينة مياة الشرب.docx

التعديل من داخل البرنامج يُحدّث ملف الفولدر نفسه فورًا (مصدر الحقيقة واحد).
"""
import shutil

from core.config import HEALTH_SECTION_INDEX, MONTH_NAMES
from core import arabic_numbers as arnum
from data_access import storage

SUB_SPRAY = "الرش والتعقيم"
SUB_CHECKUPS = "الكشف الدوري على المجندين"
SUB_TANKS = "تطهير الخزانات"
SUB_WATER = "فحص مياة الشرب"

FILE_SPRAY = "محضر رش وتقفيم.docx"
FILE_TANKS = "محضر تطهير خزانات.docx"
FILE_WATER = "تقرير فحص عينة مياة الشرب.docx"


def section_root(year, month):
    """جذر فولدر الصحة للشهر — 13-الصحة."""
    return storage.section_files_path(year, month, HEALTH_SECTION_INDEX)


def sub_dir(year, month, sub):
    """فولدر تاب فرعي (يُنشأ عند الطلب)."""
    p = section_root(year, month) / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def day_dir(year, month, day):
    """فولدر يوم كشف دوري — «يوم ١٥» داخل فولدر الكشف الدوري."""
    p = sub_dir(year, month, SUB_CHECKUPS) / f"يوم {arnum.to_arabic_indic(day)}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def day_file(year, month, day):
    return day_dir(year, month, day) / f"كشف الدوري — يوم {arnum.to_arabic_indic(day)}.docx"


def report_file(year, month, report):
    """مسار ملف الوورد لتقرير من الثلاثة الثابتة."""
    sub, name = {
        "spray": (SUB_SPRAY, FILE_SPRAY),
        "tanks": (SUB_TANKS, FILE_TANKS),
        "water": (SUB_WATER, FILE_WATER),
    }[report]
    return sub_dir(year, month, sub) / name


def ensure_month(year, month):
    """إنشاء الهيكل كاملًا عند فتح الصفحة — الفولدرات موجودة حتى قبل أول توليد."""
    sub_dir(year, month, SUB_SPRAY)
    sub_dir(year, month, SUB_TANKS)
    sub_dir(year, month, SUB_WATER)
    from data_access import db_health
    for d in db_health.get_days(year, month):
        day_dir(year, month, d)


def month_label(year, month):
    return f"{MONTH_NAMES[month - 1]} {arnum.to_arabic_indic(year)}"


def remove_day_dir(year, month, day):
    """عند تغيير يوم كشف: إزالة فولدره القديم إن لم يعد مستخدمًا."""
    p = section_root(year, month) / SUB_CHECKUPS / f"يوم {arnum.to_arabic_indic(day)}"
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
