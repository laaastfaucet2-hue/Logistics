# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 خط — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تسميات فئات القوة الثلاث: **كلمات عادية** — ضابط / فرد / مجندين.

توجيه المستخدم ٠٨/١٠/٢٠٢٦ (ينسخ ما قبله): «شيل ض و ف و م وحوهم ضابط وفرد
ومجندين عادي في كل الجداول وفي كل حاجة» — فالحروف المختصرة ض/أ/م خرجت من
كل العروض (الشاشات + ملفات Excel المحلية + الكشوف المطبوعة الداخلية +
البحث الذكي)، وبلا سطر «مفتاح الحروف» لأن المفتاح صار فائضًا عن الحاجة.
يُستثنى فقط: أسماء الملفات على القرص (مُعرِّفات لا تتغيّر) وأعمدة
«مسلسل» المختصرة (م) فهي رقم تسلسل وليس فئة قوة.
"""
from core import arabic_numbers as arnum

SHORT = {"officers": "ضابط", "individuals": "فرد", "recruits": "مجندين"}
FULL = {"officers": "ضابط", "individuals": "فرد", "recruits": "مجندين"}

LEGEND = ""
LEGEND_TWO = ""


def _num(value):
    """رقم عربي مشرقي بلا كسور (الأعداد أفراد لا كسور لها)."""
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        number = 0
    return arnum.to_arabic_indic(str(number))


def pair3(officers=0, individuals=0, recruits=0):
    """«ضابط ١٠ · فرد ٢٥ · مجندين ٠» — الفئات الثلاث (التاميدات)."""
    return (f"{SHORT['officers']} {_num(officers)} · "
            f"{SHORT['individuals']} {_num(individuals)} · "
            f"{SHORT['recruits']} {_num(recruits)}")


def pair2(officers=0, individuals=0):
    """«ضابط ١٠ · فرد ٢٥» — الراغبون والكوادر (بلا مجندين)."""
    return f"{SHORT['officers']} {_num(officers)} · {SHORT['individuals']} {_num(individuals)}"


def triple_slash(officers=0, individuals=0, recruits=0):
    """«١٠ / ٢٥ / ٠» بترتيب ضابط/فرد/مجندين — للخلايا المضغوطة داخل جدول التنبيهات."""
    return f"{_num(officers)} / {_num(individuals)} / {_num(recruits)}"


def slash2(officers=0, individuals=0):
    """«١٠ / ٥» بترتيب ضابط/فرد — للخلايا المضغوطة."""
    return f"{_num(officers)} / {_num(individuals)}"


def header3(base="القوة", with_legend=False):
    """عنوان عمود: «القوة (ضابط/فرد/مجندين)»."""
    text = f"{base} (ضابط/فرد/مجندين)" if base else "(ضابط/فرد/مجندين)"
    return f"{text} — {LEGEND}" if with_legend else text


def header2(base="القوة", with_legend=False):
    """عنوان عمود للفئتين: «القوة (ضابط/فرد)»."""
    text = f"{base} (ضابط/فرد)" if base else "(ضابط/فرد)"
    return f"{text} — {LEGEND_TWO}" if with_legend else text


def for_category(offset, officers=0, individuals=0, recruits=0):
    """نص الأعداد لعمود واحد داخل ملفات «عدم الراغبين» (ضابط أو فرد).

    offset إما "officers" أو "individuals" — يُرجع «ضابط ٣» أو «فرد ٧».
    """
    if offset == "officers":
        return f"{SHORT['officers']} {_num(officers)}"
    return f"{SHORT['individuals']} {_num(individuals)}"
