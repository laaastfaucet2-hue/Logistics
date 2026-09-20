# -*- coding: utf-8 -*-
"""الإعدادات الثابتة للمنظومة — الأقسام والشهور (مصدر واحد للحقيقة).

أي تعديل في أسماء الأقسام أو الشهور يتم من هذا الملف فقط،
وينعكس تلقائيًا على القائمة الجانبية ومجلدات database/ والصفحات.
"""

MONTH_NAMES = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]

# الأقسام الاثنا عشر — ترتيبها ثابت، وتُرقَّم مجلداتها بنفس الترتيب
SECTIONS = [
    {"key": "tamween",   "name": "التموين",   "icon": "🍞"},
    {"key": "malabes",   "name": "الملابس",   "icon": "👕"},
    {"key": "waqoud",    "name": "الوقود",     "icon": "⛽"},
    {"key": "tameedat",  "name": "التاميدات",  "icon": "⚖️"},
    {"key": "tarfea",    "name": "الترفية",    "icon": "🎖️"},
    {"key": "takyeef",   "name": "التكييف",    "icon": "❄️"},
    {"key": "raghebeen", "name": "الراغبين",   "icon": "🙋"},
    {"key": "adawat",    "name": "الأدوات",    "icon": "🔧"},
    {"key": "ohad",      "name": "العُهد",     "icon": "📋"},
    {"key": "nadafa",    "name": "النظافة",    "icon": "🧼"},
    {"key": "inshaat",   "name": "الإنشاءات",  "icon": "🏗️"},
    {"key": "sayarat",   "name": "السيارات",   "icon": "🚗"},
]

SECTION_MAP = {s["key"]: s for s in SECTIONS}


def month_folder(number):
    """اسم مجلد الشهر: 01-يناير ... 12-ديسمبر"""
    return f"{number:02d}-{MONTH_NAMES[number - 1]}"


def section_folder(number, section_name):
    """اسم مجلد القسم داخل الشهر: 01-التموين ... 12-السيارات"""
    return f"{number:02d}-{section_name}"
