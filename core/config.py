# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الإعدادات الثابتة للمنظومة — الأقسام والشهور والمقررات (مصدر واحد للحقيقة).

أي تعديل في الأسماء أو الثوابت يتم من هذا الملف فقط،
وينعكس تلقائيًا على القائمة الجانبية ومجلدات database/ والصفحات.
قبل التعديل: اقرأ صندوق «قف» في AGENTS.md ثم CONTRIBUTING.md ثم هذا الملف.
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

# أدوات إضافية: الدباجة شهرية، والنسخ الاحتياطية عامة للنظام
# «المجندين» ليست هنا: قسم «المجندين» في SECTIONS يفتح الصفحة الحقيقية مباشرة
EXTRA_PAGES = [
    {"key": "letterhead", "name": "الدباجة والتوقيعات الرسمية", "icon": "📜"},
    {"key": "calc2",      "name": "آلة حاسبة 2 مخازن",          "icon": "🧮"},
    {"key": "backups",    "name": "النسخ الاحتياطي والحماية",    "icon": "💾"},
]
EXTRA_MAP = {p["key"]: p for p in EXTRA_PAGES}

# ترتيب الأقسام الشهرية في الشريط (طلب المستخدم ٢٤/٠٩/٢٠٢٦) — لا يغيّر أرقام مجلدات database/
NAV_MONTHLY_KEYS = [
    "tameedat", "raghebeen", "calc2", "tamween_rations", "contractor_rations",
    "warehouses_records", "cold_stores", "mojandeen",
]
NAV_SKIP = {"supply_records", "contractor_records"}


def nav_monthly():
    """عناصر الشريط الشهري بالترتيب المعتمد، ثم باقي الأقسام غير المخفية."""
    by_key = {s["key"]: s for s in SECTIONS}
    extra = {p["key"]: p for p in EXTRA_PAGES}
    items, seen = [], set()
    for key in NAV_MONTHLY_KEYS:
        row = by_key.get(key) or extra.get(key)
        if row:
            items.append(row)
            seen.add(key)
    for section in SECTIONS:
        if section["key"] not in NAV_SKIP and section["key"] not in seen:
            items.append(section)
    return items

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

# وحدات القياس الموحّدة — مقررا التموين والمتعهد يقرآن نفس القائمة،
# وأي وحدة يكتبها المستخدم تُحفظ وتظهر في القسمين (انظر db_rations.collect_units)
UNITS = [
    "كجم", "جم", "لتر", "مل", "طن",
    "قطعة", "حبة", "علبة", "عبوة", "بكت", "دستة",
    "كيس", "شيكارة", "كرتونة", "صندوق",
    "رأس", "فرخة", "صينية", "طبق", "رغيف", "ربطة",
    "زجاجة", "جردل", "برميل", "جالون", "عود",
]


# الدورة المخزنية داخل «مستودعات وسجلات» (توجيه المستخدم ٢٥/٠٩/٢٠٢٦):
# دورتان منفصلتان تمامًا — بيانات وملفات — بنفس الشاشات بالضبط،
# وكل دورة تمر بـ ١ مخازن (إذن إضافة) ← ٢ مخازن (آلة الحاسبة) ← ٣ مخازن (دفتر الصنف)
# وحتى ٧ مخازن (مراحل لاحقة). section = مقرر الشهر الذي تسحب منه أصناف الدورة.
WAREHOUSE_CYCLES = [
    {"key": "supply",     "name": "سجل الإمداد", "icon": "🚚", "section": "tamween"},
    {"key": "contractor", "name": "سجل المتعهد", "icon": "🗂️", "section": "contractor"},
]
WAREHOUSE_MAP = {c["key"]: c for c in WAREHOUSE_CYCLES}

# أنواع التغليف في ١ مخازن ورصيد أول المدة (توجيه المستخدم ٢٥/٠٩/٢٠٢٦):
# «مستوى واحد + سائب» — عدد العبوات × سعة العبوة + كمية سائبة = المجموع تلقائي.
# أي نوع يكتبه المستخدم يُحفظ في القاموس المشترك ويظهر في القائمة (vocab: pack_kind).
PACK_KINDS = [
    "بدون تغليف", "شكارة", "كرتونة", "بلات", "علبة", "عبوة",
    "صندوق", "ربطة", "دستة", "جردل", "برميل", "دلو",
]

# التحويل التلقائي لوحدة القاعدة عند الإضافة في ١ مخازن: ١ طن = ١٠٠٠ كجم، ١ جم = ٠٫٠٠١ كجم.
# الوحدة التي لا معامل لها (شيكارة، كرتونة، قطعة…) قاعدتها نفسها بمعامل ١ —
# التعامل دائمًا بالوحدة المحددة للصنف في ٣ مخازن.
UNIT_BASE = {
    "كجم": ("كجم", 1.0), "جم": ("كجم", 0.001), "طن": ("كجم", 1000.0),
    "لتر": ("لتر", 1.0), "مل": ("لتر", 0.001),
}


def unit_base(unit):
    """(وحدة القاعدة، معامل التحويل) لوحدة التعامل — الوحدة غير المعروفة قاعدتها نفسها."""
    key = (unit or "").strip()
    return UNIT_BASE.get(key, (key or "وحدة", 1.0))


def month_folder(number):
    """اسم مجلد الشهر: 01-يناير ... 12-ديسمبر"""
    return f"{number:02d}-{MONTH_NAMES[number - 1]}"


def section_folder(number, section_name):
    """اسم مجلد القسم داخل الشهر: 01-سجلات الامداد ... 12-فواتير المتعهد"""
    return f"{number:02d}-{section_name}"


# إصدار الملفات الثابتة (CSS/JS) — غيّره مع أي تعديل تصميم ليتحدّث فورًا عند كل مستخدم
STATIC_VER = 52
