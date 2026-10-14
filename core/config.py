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
    {"key": "health",              "name": "الصحة",                "icon": "🏥"},
]

SECTION_MAP = {s["key"]: s for s in SECTIONS}

# فهرس قسم «الصحة» في SECTIONS (يحدد اسم فولدره الشهري 13-الصحة — لا يُغيَّر)
HEALTH_SECTION_INDEX = len(SECTIONS)  # آخر قسم مضاف

# أدوات إضافية: الدباجة شهرية، والنسخ الاحتياطية عامة للنظام
# «المجندين» ليست هنا: قسم «المجندين» في SECTIONS يفتح الصفحة الحقيقية مباشرة
EXTRA_PAGES = [
    {"key": "letterhead", "name": "الدباجة والتوقيعات الرسمية", "icon": "📜"},
    {"key": "calc2",      "name": "آلة حاسبة 2 مخازن",          "icon": "🧮"},
    {"key": "occasions",  "name": "التوثيق والمناسبات",          "icon": "📸"},
    {"key": "settings",   "name": "الإعدادات",                  "icon": "⚙️"},
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

# آلة حاسبة ٢ مخازن — حدّ «الحالة الكلية للرصيد» (توجيه ٠٦/١٠/٢٠٢٦: يحدده المستخدم)
# القاعدة: المتوفر صفر ⇒ «لا يوجد» · المتبقي بعد الإذن أقل من (الاحتياج × النسبة) ⇒
# «يوشك على النفاذ» · وما فوق ذلك ⇒ «آمن». عدّل رقم النسبة هنا فقط.
STOCK_LOW_RATIO = 0.25

# الوجبات
MEALS = [("breakfast", "فطار"), ("lunch", "غداء"), ("dinner", "عشاء")]
MEAL_MAP = dict(MEALS)

# أيام الأسبوع (0=السبت ... 6=الجمعة)
DAYS = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]

# وحدات القياس الموحّدة — مقررا التموين والمتعهد يقرآن نفس القائمة،
# وأي وحدة يكتبها المستخدم تُحفظ وتظهر في القسمين (انظر db_rations.collect_units)
# الستة الأساسيين ثابتين فوق القائمة (توجيه المستخدم ٢٦/٠٩)
UNITS = [
    "كجم", "جم", "قطعة", "علبة", "باكت", "فتلة",
    "لتر", "مل", "طن", "بلتة", "حبة", "عبوة", "دستة",
    "كيس", "شيكارة", "شكارة", "كرتونة", "صندوق", "جركن",
    "رأس", "فرخة", "صينية", "طبق", "رغيف", "ربطة",
    "زجاجة", "جردل", "برميل", "جالون", "عود", "قفة", "شنطة", "كوب",
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
    "بدون تغليف", "شكارة", "كرتونة", "بلتة", "علبة", "عبوة",
    "صندوق", "ربطة", "دستة", "جردل", "برميل", "دلو",
]

# التحويل التلقائي لوحدة القاعدة عند الإضافة في ١ مخازن: ١ طن = ١٠٠٠ كجم، ١ جم = ٠٫٠٠١ كجم.
# الوحدة التي لا معامل لها (شيكارة، كرتونة، قطعة…) قاعدتها نفسها بمعامل ١ —
# التعامل دائمًا بالوحدة المحددة للصنف في ٣ مخازن.
UNIT_BASE = {
    "كجم": ("كجم", 1.0), "جم": ("كجم", 0.001), "جرام": ("كجم", 0.001), "طن": ("كجم", 1000.0),
    "لتر": ("لتر", 1.0), "مل": ("لتر", 0.001),
}


# التصنيف الرسمي للمعايير (توجيه ٢٧/٠٩): دي كل اللي بتتحول لوزن/حجم —
# وأي معيار تاني خارج القايمة دي بيُعدّ بالعدد زي ما هو (باكت، علبة، شكارة…)
MEASURE_UNITS = ("كجم", "جم", "جرام", "طن", "لتر", "مل")


def unit_base(unit):
    """(وحدة القاعدة، معامل التحويل) لوحدة التعامل — الوحدة غير المعروفة قاعدتها نفسها."""
    key = (unit or "").strip()
    return UNIT_BASE.get(key, (key or "وحدة", 1.0))


def is_measure_unit(unit):
    """هل المعيار وزن/حجم من القايمة الرسمية؟ غير كده بيُعدّ بالعدد (توجيه ٢٧/٠٩)."""
    return (unit or "").strip() in MEASURE_UNITS


def calc_fine_unit(unit):
    """وحدة الحاسبة/المقرر: الدقيقة — الأوزان بالجرام والحجوم بالمل.
    يرجع (الوحدة، معامل التحويل من الوحدة المعطاة) — الكيلو ٠٫٦ → ٦٠٠ جم."""
    key = (unit or "").strip()
    base, factor = unit_base(key)
    if base == "كجم":
        return "جم", factor * 1000.0
    if base == "لتر":
        return "مل", factor * 1000.0
    return key or "وحدة", 1.0


def fine_unit(ration_unit, handle_unit, specific_weight=None):
    """وحدة الدقيقة (جم/مل) — أداة مساعدة للتحويل بين وحدات الأسرة.

    ملاحظة قاعدة ١٢/١٠: وحدة الدفتر مش الدقيقة — الدفتر بيتشغل
    بالوحدة اللي الصنف بيتضاف بيها (وحدة التعامل)، والجسر الوحيد هو
    الزيت (دفتره كجم). شوف `oil_units.ledger_unit` للتطبيق الفعلي.
    - صنف وزن (وحدة المقرر من أسرة كجم) → جم
    - صنف حجم (من أسرة لتر) → مل
    - صنف عدد → وحدة التعامل زي ما هي
    specific_weight (جرام/لتر): الصنف اللي بيتصرف بالوزن ويبقى مخزونه بالحجم.
    يرجع (وحدة الدقيقة، معامل من وحدة التعامل → وحدة الدقيقة)."""
    rat = (ration_unit or "").strip()
    han = (handle_unit or "").strip()
    rat_base, _ = unit_base(rat) if rat else ("", 1.0)
    han_base, han_factor = unit_base(han)
    try:
        sw = float(specific_weight) if specific_weight not in (None, "") else 0.0
    except (TypeError, ValueError):
        sw = 0.0
    if sw > 0:
        return "جم", sw
    if rat_base == "كجم" or (not rat_base and han_base == "كجم"):
        return "جم", han_factor * 1000.0 if han_base == "كجم" else 1.0
    if rat_base == "لتر" or (not rat_base and han_base == "لتر"):
        return "مل", 1000.0 * han_factor if han_base == "لتر" else 1.0
    return han or "وحدة", 1.0


def month_folder(number):
    """اسم مجلد الشهر: 01-يناير ... 12-ديسمبر"""
    return f"{number:02d}-{MONTH_NAMES[number - 1]}"


def section_folder(number, section_name):
    """اسم مجلد القسم داخل الشهر: 01-سجلات الامداد ... 12-فواتير المتعهد"""
    return f"{number:02d}-{section_name}"


# إصدار الملفات الثابتة (CSS/JS) — غيّره مع أي تعديل تصميم ليتحدّث فورًا عند كل مستخدم
STATIC_VER = 234
