# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 100 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الإعدادات الثابتة للمنظومة — الأقسام والشهور (مصدر واحد للحقيقة).

أي تعديل في أسماء الأقسام أو الشهور يتم من هذا الملف فقط،
وينعكس تلقائيًا على القائمة الجانبية ومجلدات database/ والصفحات.
"""

MONTH_NAMES = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]

# الأقسام الاثنا عشر — الأسماء حرفيًا كما أُمليت، وبنفس الترتيب،
# وتُرقَّم مجلداتها داخل كل شهر بنفس الترتيب (01-... حتى 12-...)
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


def month_folder(number):
    """اسم مجلد الشهر: 01-يناير ... 12-ديسمبر"""
    return f"{number:02d}-{MONTH_NAMES[number - 1]}"


def section_folder(number, section_name):
    """اسم مجلد القسم داخل الشهر: 01-سجلات الامداد ... 12-فواتير المتعهد"""
    return f"{number:02d}-{section_name}"
