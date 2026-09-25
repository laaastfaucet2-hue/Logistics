# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
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
    """قاعدة العرض الموحدة للكميات: ثلاثة أرقام عشرية دائمًا بالعربية المشرقية.

    0.12 → «٠٫١٢٠»   |   75 → «٧٥٫٠٠٠»   |   None/فاضي → «»
    """
    if value is None or value == "":
        return ""
    try:
        f = float(to_western(value))
    except (TypeError, ValueError):
        return str(value)
    return to_arabic_indic(f"{f:.3f}").replace(".", "٫")


def digit_sets():
    """Expose the same digit alphabets to local browser formatters (no duplicate maps)."""
    return {"western": "0123456789", "eastern": _EASTERN, "persian": _PERSIAN}
