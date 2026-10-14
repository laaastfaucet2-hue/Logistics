# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""التبويبات الفرعية التسعة لإحصائيات المخازن والثلاجات — مصدر واحد للاسم والمجلد والملف.

اسم مجلد التبويب = رقمه واسمه كما على الشاشة (بنفس أسلوب مجلدات الراغبين «1. …»)،
واسم الملف = اسم التبويب + الشهر أو السنة (Excel لا يفتح ملفين بنفس الاسم معًا).
"""
from core import arabic_numbers as arnum
from core.config import MONTH_NAMES

SUBTABS = (
    {"key": "summary", "no": 1, "icon": "📊", "name": "الملخص العام"},
    {"key": "balances", "no": 2, "icon": "🗃️", "name": "أرصدة المخازن"},
    {"key": "movement", "no": 3, "icon": "🔄", "name": "حركة الوارد والمنصرف"},
    {"key": "expiry", "no": 4, "icon": "⏳", "name": "الصلاحيات"},
    {"key": "consumption", "no": 5, "icon": "📉", "name": "الاستهلاك والتغطية"},
    {"key": "entities", "no": 6, "icon": "🏢", "name": "الجهات المستلمة"},
    {"key": "registry", "no": 7, "icon": "🏬", "name": "المخازن والتجهيزات"},
    {"key": "alerts", "no": 8, "icon": "🚨", "name": "التنبيهات"},
    {"key": "compare", "no": 9, "icon": "📈", "name": "المقارنة والاتجاه"},
)
SUBTAB_MAP = {t["key"]: t for t in SUBTABS}
# مجلدات تبويبات اتغير اسمها وبتتمسح لو لسه موجودة (١٤/١٠: اتشال «غير الموزع»)
LEGACY_FOLDERS = ("8. التنبيهات وغير الموزع",)
DEFAULT_SUB = "summary"


def folder_name(key):
    """«2. أرصدة المخازن» — رقم التبويب واسمه بالضبط."""
    tab = SUBTAB_MAP[key]
    return f"{tab['no']}. {tab['name']}"


def period_text(year, month=None):
    """«أكتوبر ٢٠٢٦» للشهري و«سنة ٢٠٢٦» للسنوي."""
    if month:
        return f"{MONTH_NAMES[int(month) - 1]} {arnum.to_arabic_indic(year)}"
    return f"سنة {arnum.to_arabic_indic(year)}"


def file_name(key, year, month=None):
    """«أرصدة المخازن — أكتوبر ٢٠٢٦.xlsx» أو «أرصدة المخازن — سنة ٢٠٢٦.xlsx»."""
    return f"{SUBTAB_MAP[key]['name']} — {period_text(year, month)}.xlsx"
