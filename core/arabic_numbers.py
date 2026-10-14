# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


def round3(value):
    """قاعدة التقريب الموحدة (توجيه ١٠/١٠): ثلاثة خانات بعد العلامة، والرقم
    الرابع ٥ أو أكبر → يتقرب لأعلى — على كل كميات المتعهد والإمداد.

    10.9685 → 10.969   ·   10.9682 → 10.968   ·   10.968 → 10.968
    مبني على Decimal (نصف-أعلى حقيقي) مش round() ببايثون (بنكري-راندينج)."""
    try:
        d = Decimal(str(float(value)))
    except (TypeError, ValueError, InvalidOperation):
        return 0.0
    return float(d.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
"""محرك الأرقام العربية — النواة الأولى.

الأساس المعتمد في كل المنظومة:
- الإدخال يُقبل بالأرقام العربية المشرقية (٠١٢٣٤٥٦٧٨٩) أو الفارسية أو الإنجليزية.
- العرض للمستخدم يكون بالأرقام العربية المشرقية.
سيتوسّع الملف لاحقًا بالكميات والتحويلات والحسابات المركّبة.
"""

_EASTERN = "٠١٢٣٤٥٦٧٨٩"
_PERSIAN = "۰۱۲۳۴۵۶۷۸۹"

_TO_WESTERN = {ch: str(i) for i, ch in enumerate(_EASTERN)}
_TO_WESTERN.update({ch: str(i) for i, ch in enumerate(_PERSIAN)})
_TO_WESTERN["٫"] = "."   # الفاصلة العشرية العربية
_TO_WESTERN["،"] = ","   # الفاصلة العربية

_WEST_TO_EASTERN = {str(i): ch for i, ch in enumerate(_EASTERN)}


def to_western(text):
    """يحوّل أي أرقام عربية/فارسية داخل النص إلى أرقام إنجليزية."""
    return "".join(_TO_WESTERN.get(ch, ch) for ch in str(text))


def to_arabic_indic(text):
    """يحوّل الأرقام الإنجليزية إلى أرقام عربية مشرقية (للعرض)."""
    return "".join(_WEST_TO_EASTERN.get(ch, ch) for ch in str(text))


def parse_int(text, default=None):
    """يقرأ عددًا صحيحًا من نص عربي أو إنجليزي، ويرجع default عند الفشل."""
    if text is None:
        return default
    cleaned = to_western(text).strip().replace(",", "")
    try:
        return int(cleaned)
    except ValueError:
        return default


def parse_float(text, default=None):
    """يقرأ عددًا عشريًا من نص عربي أو إنجليزي، ويرجع default عند الفشل."""
    if text is None:
        return default
    cleaned = to_western(text).strip().replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return default


def fmt_qty(value):
    """قاعدة العرض الموحدة للكميات: ثلاثة أرقام عشرية دائمًا بالعربية المشرقية،
    والتقريب نصف-أعلى (قاعدة ١٠/١٠): 10.9685 → «١٠٫٩٦٩».

    0.12 → «٠٫١٢٠»   |   75 → «٧٥٫٠٠٠»   |   None/فاضي → «»
    """
    if value is None or value == "":
        return ""
    try:
        d = Decimal(str(float(to_western(value))))
    except (TypeError, ValueError, InvalidOperation):
        return str(value)
    q = d.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return to_arabic_indic(format(q, "f")).replace(".", "٫")


def fmt_qty_exact(value):
    """القيمة المدخلة بالظبط — بلا أي تقريب (توجيه ١٠/١٠ للمقررات:
    كمون 0.00025 يظهر «٠٫٠٠٢٥» مش «٠٫٠٠»). الأصفار الزائدة آخر الكسر تتنضف:
    0.01 → «٠٫٠١»   |   2 → «٢»   |   None/فاضي → «»
    """
    if value is None or value == "":
        return ""
    try:
        d = Decimal(str(float(to_western(value))))
    except (TypeError, ValueError, InvalidOperation):
        return str(value)
    if d == 0:
        return ""
    q = d.normalize()
    return to_arabic_indic(format(q, "f")).replace(".", "٫")


def fmt_qty_trim(value):
    """كمية بلا أصفار زائدة: الصحيحة تظهر صحيحة والكسر يظهر بكسره (توجيه ٢٦/٠٩).

    50 → «٥٠»   |   1.5 → «١٫٥»   |   0.66 → «٠٫٦٦»   |   None/فاضي → «»
    """
    if value is None or value == "":
        return ""
    try:
        f = float(to_western(value))
    except (TypeError, ValueError):
        return str(value)
    text = f"{f:.3f}".rstrip("0").rstrip(".")
    if text in ("", "-"):
        text = "0"
    return to_arabic_indic(text.replace(".", "٫"))


def digit_sets():
    """Expose the same digit alphabets to local browser formatters (no duplicate maps)."""
    return {"western": "0123456789", "eastern": _EASTERN, "persian": _PERSIAN}
