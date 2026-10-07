# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 خط — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مفتاح الحروف المختصرة للمنظومة (توجيه المستخدم ٠٦/١٠/٢٠٢٦).

    ض = ضابط · أ = أفراد · م = مجندين

المستخدم أمر صراحة: «اكتب ض ديه ضابط، أ ديه أفراد — غير بس الحرفين».
فكل عرض لأعداد الفئات الثلاث في **التاميدات والراغبين** (الشاشات + ملفات Excel
المحلية + الكشوف المطبوعة الداخلية) يستخدم الحروف، مع سطر تعريف صغير LEGEND.
يُستثنى فقط: أسماء الملفات على القرص (مُعرِّفات لا تتغيّر) والمستندات الرسمية
الخارجية (أذونات الصرف) فتبقى بالكلمات الكاملة.
"""
from core import arabic_numbers as arnum

SHORT = {"officers": "ض", "individuals": "أ", "recruits": "م"}
FULL = {"officers": "ضباط", "individuals": "أفراد", "recruits": "مجندين"}

LEGEND = "ض = ضباط · أ = أفراد · م = مجندين"
LEGEND_TWO = "ض = ضباط · أ = أفراد"


def _num(value):
    """رقم عربي مشرقي بلا كسور (الأعداد أفراد لا كسور لها)."""
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        number = 0
    return arnum.to_arabic_indic(str(number))


def pair3(officers=0, individuals=0, recruits=0):
    """«ض ١٠ · أ ٢٥ · م ٠» — الفئات الثلاث (التاميدات)."""
    return (f"{SHORT['officers']} {_num(officers)} · "
            f"{SHORT['individuals']} {_num(individuals)} · "
            f"{SHORT['recruits']} {_num(recruits)}")


def pair2(officers=0, individuals=0):
    """«ض ١٠ · أ ٢٥» — الراغبون والكوادر (بلا مجندين)."""
    return f"{SHORT['officers']} {_num(officers)} · {SHORT['individuals']} {_num(individuals)}"


def triple_slash(officers=0, individuals=0, recruits=0):
    """«١٠ / ٢٥ / ٠» بترتيب ض/أ/م — للخلايا المضغوطة داخل جدول التنبيهات."""
    return f"{_num(officers)} / {_num(individuals)} / {_num(recruits)}"


def slash2(officers=0, individuals=0):
    """«١٠ / ٢٥» بترتيب ض/أ — للخلايا المضغوطة."""
    return f"{_num(officers)} / {_num(individuals)}"


def header3(base="القوة", with_legend=False):
    """عنوان عمود مختصر: «القوة (ض/أ/م)»."""
    text = f"{base} (ض/أ/م)" if base else "(ض/أ/م)"
    return f"{text} — {LEGEND}" if with_legend else text


def header2(base="القوة", with_legend=False):
    """عنوان عمود مختصر للفئتين: «القوة (ض/أ)»."""
    text = f"{base} (ض/أ)" if base else "(ض/أ)"
    return f"{text} — {LEGEND_TWO}" if with_legend else text


def for_category(offset, officers=0, individuals=0, recruits=0):
    """نص الأعداد لعمود واحد داخل ملفات «عدم الراغبين» (ضباط أو أفراد).

    offset إما "officers" أو "individuals" — يُرجع «ض ٣» أو «أ ٧».
    """
    if offset == "officers":
        return f"{SHORT['officers']} {_num(officers)}"
    return f"{SHORT['individuals']} {_num(individuals)}"
