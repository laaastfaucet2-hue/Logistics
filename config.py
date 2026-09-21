# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الإعدادات الثابتة للمنظومة — الأقسام والشهور والمقررات (مصدر واحد للحقيقة).

أي تعديل في الأسماء أو الثوابت يتم من هذا الملف فقط،
وينعكس تلقائيًا على القائمة الجانبية ومجلدات database/ والصفحات.
"""

MONTH_NAMES = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]

# الأقسام الاثنا عشر — الأسماء حرفيًا كما أُمليت، وبنفس الترتيب
SECTIONS = [
    {"key": "supply_records",      "name": "سجلات الامداد",        "icon": "🚚"},
    {"key": "contractor_records",  "name": "سجلات المتعهد",        "icon": "🗂️"},
    {"key": "raghebeen",           "name": "قسم الراغبين",         "icon": "🙋"},
    {"key": "tamween_rations",     "name": "المقررات التمونيية",   "icon": "🍞"},
    {"key": "contractor_rations",  "name": "مقررات المتعهد",       "icon": "📋"},
    {"key": "warehouses_records",  "name": "مستودعات وسجلات",      "icon": "🏪"},
    {"key": "tameedat",            "name": "التاميدات",            "icon": "⚖️"},
    {"key": "mojandeen",           "name": "المجندين",             "icon": "🪖"},
    {"key": "statistics",          "name": "الاحصائيات",           "icon": "📊"},
    {"key": "cold_stores",         "name": "المخازن والثلاجات",    "icon": "🧊"},
    {"key": "tarfea",              "name": "الترفية",              "icon": "🎖️"},
    {"key": "contractor_invoices", "name": "فواتير المتعهد",       "icon": "🧾"},
]

SECTION_MAP = {s["key"]: s for s in SECTIONS}

# صفحات عامة في الشريط الجانبي (ليست أقسامًا شهرية ولا مجلدات لها)
EXTRA_PAGES = [
    {"key": "letterhead", "name": "الدباجة والتوقيعات الرسمية", "icon": "📜"},
    {"key": "calc2",      "name": "آلة حاسبة 2 مخازن",          "icon": "🧮"},
]
EXTRA_MAP = {p["key"]: p for p in EXTRA_PAGES}

# أنواع المقرر الغذائي — التفعيل مقرر واحد فقط لكل قسم
RATION_KINDS = [
    ("summer",  "صيفي",  "☀️"),
    ("winter",  "شتوي",  "❄️"),
    ("ramadan", "رمضان", "🌙"),
]
RATION_KIND_MAP = {k: {"name": n, "icon": i} for k, n, i in RATION_KINDS}

# الوجبات
MEALS = [("breakfast", "فطار"), ("lunch", "غداء"), ("dinner", "عشاء")]
MEAL_MAP = dict(MEALS)

# أيام الأسبوع (0=السبت ... 6=الجمعة)
DAYS = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]

# وحدات القياس المقترحة (تُستخدم لاحقًا في الآلة الحاسبة)
UNITS = ["كجم", "جم", "لتر", "مل", "طن", "قطعة", "علبة", "عبوة",
         "كيس", "كرتونة", "رأس", "صينية", "زجاجة", "فرخة"]


def month_folder(number):
    """اسم مجلد الشهر: 01-يناير ... 12-ديسمبر"""
    return f"{number:02d}-{MONTH_NAMES[number - 1]}"


def section_folder(number, section_name):
    """اسم مجلد القسم داخل الشهر: 01-سجلات الامداد ... 12-فواتير المتعهد"""
    return f"{number:02d}-{section_name}"


# إصدار الملفات الثابتة (CSS/JS) — غيّره مع أي تعديل تصميم ليتحدّث فورًا عند كل مستخدم
STATIC_VER = 8
