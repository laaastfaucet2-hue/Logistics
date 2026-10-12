# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الزيت (زيت الطعام) — ثوابت مثبتة في ملفات البرنامج + تحويلات كجم↔لتر.

توجيه المستخدم ١٠/١٠:
- مقرر الزيت للشخص الواحد في اليوم: صيفي ٠٫٠١٢ كجم · شتوي ٠٫٠١٥ كجم.
- الوزن النوعي (الكثافة): 0.914 كجم/لتر (= 914 جم/لتر).
  كجم ← لتر: ÷ 0.914   (1.2 كجم = 1.313 لتر)
  لتر ← كجم: × 0.914   (12 لتر = 10.968 كجم)

قاعدة الوحدات (توجيه المستخدم ١٢/١٠ — التصحيحي النهائي):
- الدفاتر كلها (٣ مخازن/الأرصدة/الإحصائيات) + ١ مخازن بتشتغل
  بالوحدة اللي الصنف بيتضاف بيها (وحدة التعامل/المقرر: كجم/لتر/عد).
- ما عدا الزيت («زيت الطعام» ثابت + أي اسم بيبدأ بـ«زيت»):
  الدفتر كجم بالجسر 0.914، والإضافة/الصرف المادي بالوحدة اللي اتضاف
  بيها (لتر أو كجم)، والحاسبة دايمًا كجم (لو المقرر باللتر بيتحول).
- باقي الأصناف: الحاسبة/الإذن بالوحدة الدقيقة جم/مل (داخل الحاسبة بس).
"""

from core.config import calc_fine_unit, fine_unit, unit_base

# أسماء أصناف الزيت المعروفة في البرنامج (تُضاف هنا لو اتزود صنف زيت)
# «زيت طعام» بدون «ال» = الاسم المسجل فعلًا في مقررات/مخازن المستخدم (داتا حقيقية)
OIL_ITEM_NAMES = {"زيت الطعام", "زيت طعام"}

# مقرر الزيت للشخص الواحد في اليوم (كجم)
OIL_RATION_KG = {
    "summer": 0.012,     # صيفي
    "winter": 0.015,     # شتوي
}

# الوزن النوعي: 0.914 كجم/لتر = 914 جم/لتر
OIL_DENSITY_KG_PER_L = 0.914
OIL_DENSITY_G_PER_L = 914.0


def is_oil(name):
    """هل الصنف ده من أصناف الزيت (يعمل نظام الكجم/لتر عليه)؟

    قاعدة المستخدم (١٢/١٠): «زيت الطعام» ثابت في الأكواد ما يتغيرش +
    أي مقرر اسمه بيبدأ بكلمة «زيت» (زيت دوار الشمس / زيت زيتون…).
    """
    n = (name or "").strip()
    if not n:
        return False
    return n in OIL_ITEM_NAMES or n == "زيت" or n.startswith("زيت ")


def kg_to_liter(kg):
    """كجم زيت ← لتر (÷ الكثافة)."""
    return float(kg) / OIL_DENSITY_KG_PER_L


def liter_to_kg(liter):
    """لتر زيت ← كجم (× الكثافة)."""
    return float(liter) * OIL_DENSITY_KG_PER_L


def ration_kg(kind):
    """مقرر الزيت اليومي للشخص في كجم حسب الفصل (summer/winter)."""
    return OIL_RATION_KG.get((kind or "").strip(), OIL_RATION_KG["summer"])


def day_total_kg(kind, n_people):
    """إجمالي كجم الزيت لعدد N شخص يومًا واحدًا."""
    return ration_kg(kind) * int(n_people or 0)


def _sw_value(specific_weight):
    try:
        sw = float(specific_weight) if specific_weight not in (None, "") else 0.0
    except (TypeError, ValueError):
        sw = 0.0
    return sw if sw > 0 else OIL_DENSITY_G_PER_L


def ledger_unit(name, ration_unit, handle_unit, specific_weight=None):
    """وحدة دفتر/رصيده للصنف — (الوحدة، معامل من وحدة التعامل → وحدة الدفتر).

    قاعدة المستخدم (١٢/١٠): الدفاتر كلها بتشتغل بالوحدة اللي الصنف بيتضاف
    بيها (وحدة التعامل: كجم/لتر/عد) — ما عدا الزيت («زيت الطعام» أو أي
    اسم بيبدأ بـ«زيت»): دفتره كجم — التعامل كجم فالجسر ١، ولو التعامل
    لتر فالجسر = الكثافة 0.914 (أو وزن النوعي المحفوظ لو مختلف).
    """
    if is_oil(name):
        b, _f = unit_base((handle_unit or "").strip())
        if b == "كجم":
            return "كجم", 1.0
        return "كجم", _sw_value(specific_weight) / 1000.0
    han = (handle_unit or "").strip()
    return (han or "وحدة"), 1.0


def calc_unit(name, unit, specific_weight=None):
    """وحدة الحاسبة/المقرر للصنف — (الوحدة، معامل).

    الزيت: الحاسبة دايمًا كجم (١٠/١٠) — ولو وحدة المقرر لتر (أو مل)
    بيتحول للجسر × الكثافة (قاعدة ١٢/١٠: الزيت ممكن يُضاف باللتر أو
    بكجم). باقي الأصناف: نفس calc_fine_unit الحالي (جم/مل).
    """
    if is_oil(name):
        base, _f = unit_base((unit or "").strip())
        if base == "لتر":
            return "كجم", _sw_value(specific_weight) / 1000.0 * _f
        if base == "كجم":
            return "كجم", _f
        return "كجم", 1.0
    return calc_fine_unit(unit)


def calc_to_handle_factor(name, ration_unit, handle_unit, specific_weight=None):
    """معامل تحويل كمية الحاسبة/الإذن (الوحدة الدقيقة) إلى وحدة التعامل (الحوض المادي).

    كمية الإذن المحفوظة بتتكتب بوحدة الحاسبة (الزيت: كجم · الباقي: جم/مل)
    والحوض المادي (إذن ١ مخازن/المخازن) بوحدة التعامل:
    - الزيت: كجم → لتر (÷ ٠٫٩١٤ أو بالوزن النوعي المحفوظ).
    - نفس الأسرة: نسبة unit_base (جم→كجم = ٠٫٠٠ · مل→لتر = ٠٫٠٠١ …).
    - أسرتان مختلفتان: الجسر = الوزن النوعي (جم/لتر).
    - وحدة مجهولة / وزن نوعي مش متوفر: ١ (بلا تحويل — زي ما هو).
    """
    han = (handle_unit or "").strip()
    if not han:
        return 1.0
    fine_unit, _ = calc_unit(name, ration_unit or "")
    fin_base, fin_f = unit_base(fine_unit) if fine_unit else ("", 1.0)
    han_base, han_f = unit_base(han)
    if is_oil(name):
        sw = _sw_value(specific_weight)
        if fin_base == "كجم" and han_base == "لتر":
            return 1000.0 / sw
        if fin_base == "لتر" and han_base == "كجم":
            return sw / 1000.0
        if fin_base == han_base:
            return fin_f / han_f if han_f else 1.0
        return 1.0
    if not fin_base:
        return 1.0
    if fin_base == han_base:
        return fin_f / han_f if han_f else 1.0
    try:
        sw = float(specific_weight) if specific_weight not in (None, "") else 0.0
    except (TypeError, ValueError):
        sw = 0.0
    if sw > 0:
        grams = fin_f * (1000.0 if fin_base == "كجم" else 1.0)
        if han_base == "لتر":
            return grams / (sw * (han_f or 1.0))
        if han_base == "كجم":
            return grams / (1000.0 * (han_f or 1.0))
    return 1.0
