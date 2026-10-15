# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الزيت (زيت الطعام) — ثوابت مثبتة في ملفات البرنامج + تحويلات كجم↔لتر.

توجيه المستخدم ١٠/١٠:
- مقرر الزيت للشخص الواحد في اليوم: صيفي ٠٫٠١٢ كجم · شتوي ٠٫٠١٥ كجم.
- الوزن النوعي (الكثافة): 0.914 كجم/لتر (= 914 جم/لتر).
  كجم ← لتر: ÷ 0.914   (1.2 كجم = 1.313 لتر)
  لتر ← كجم: × 0.914   (12 لتر = 10.968 كجم)

قاعدة الوحدات (توجيهات المستخدم ١٢/١٠ ثم ١٣/١٠ — التصحيحي النهائي):
- الدفاتر كلها (٣ مخازن/الأرصدة/الإحصائيات) + ١ مخازن بتشتغل
  بالوحدة اللي الصنف بيتضاف بيها (وحدة التعامل/المقرر: كجم/لتر/عد).
- الحاسبة/الإذن (آلة ٢ مخازن) دايمًا بوحدة إضافة الصنف نفسها
  (كجم/لتر/علبة…) لكل الأصناف — من غير أي تحول لجم/مل (تصحيح ١٣/١٠:
  «أنا ضايفة في المقررات بكجم وكل الأصناف كده»).
- الزيت («زيت الطعام» ثابت + أي اسم بيبدأ بـ«زيت»): الدفتر كجم بالجسر
  0.914، والإضافة/الصرف المادي بالوحدة اللي اتضاف بيها (لتر أو كجم)،
  والحاسبة دايمًا كجم (لو المقرر باللتر بيتحول) — القاعدة دي ما اتغيرتش.
"""

from core.config import unit_base, MEASURE_UNITS

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

    قاعدة ١٣/١٠: الحاسبة/الإذن بوحدة إضافة الصنف نفسها (وحدة التعامل)
    بمعامل ١ لكل الأصناف — من غير تحويل لجم/مل.
    الزيت وحده: الحاسبة دايمًا كجم (١٠/١٠) — ولو وحدة المقرر لتر (أو مل)
    بيتحول للجسر × الكثافة (الزيت ممكن يُضاف باللتر أو بكجم).
    """
    if is_oil(name):
        base, _f = unit_base((unit or "").strip())
        if base == "لتر":
            return "كجم", _sw_value(specific_weight) / 1000.0 * _f
        if base == "كجم":
            return "كجم", _f
        return "كجم", 1.0
    han = (unit or "").strip()
    return (han or "وحدة"), 1.0


def calc_to_handle_factor(name, ration_unit, handle_unit, specific_weight=None):
    """معامل تحويل كمية الحاسبة/الإذن إلى وحدة التعامل (الحوض المادي).

    كمية الإذن المحفوظة بوحدة الحاسبة (١٣/١٠: وحدة إضافة الصنف نفسها —
    الزيت كجم) والحوض المادي (إذن ١ مخازن/المخازن) بوحدة التعامل:
    - الزيت: كجم → لتر (÷ ٠٫٩١٤ أو بالوزن النوعي المحفوظ).
    - نفس الوحدة/الأسرة: نسبة unit_base (عادة ١).
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


def measure_factor(from_unit, to_unit, name="", specific_weight=None):
    """معامل تحويل كمية من وحدة قياس لوحدة تانية (١٥/١٠): نفس العائلة بنسبة
    unit_base (٥٠٠ مل = ٠٫٥ لتر)، ولتر↔كجم بالوزن النوعي المحفوظ للصنف أو
    كثافة الزيت ٩١٤ جم/لتر. None = مفيش تحويل معروف."""
    fb, ff = unit_base((from_unit or "").strip())
    tb, tf = unit_base((to_unit or "").strip())
    if fb == tb:
        return ff / tf
    if {fb, tb} != {"كجم", "لتر"}:
        return None
    try:
        sw = float(specific_weight or 0)
    except (TypeError, ValueError):
        sw = 0.0
    if sw <= 0:
        sw = OIL_DENSITY_G_PER_L if is_oil(name) else 0.0
    if sw <= 0:
        return None
    kg_per_l = sw / 1000.0
    return ff * (kg_per_l if fb == "لتر" else 1.0 / kg_per_l) / tf


def pack_to_item_unit(item, inner_unit, capacity, inner_capacity, loose, loose_unit):
    """تغليف بوحدة قياس غير وحدة الصنف (زجاجة ١ لتر وصنف بالكيلو — ١٥/١٠):
    المقاسات بتتحول لوحدة الصنف بالوزن النوعي، فالكمية والرصيد بالتغليف بوحدته.
    يرجع (وحدة المعيار، وزن العبوة، وزن المعيار، السائب، المعامل)."""
    han = (item.get("handle_unit") or "").strip()
    iu = (inner_unit or "").strip()
    if not iu or iu == han or iu not in MEASURE_UNITS or han not in MEASURE_UNITS:
        return inner_unit, capacity, inner_capacity, loose, 1.0
    f = measure_factor(iu, han, item.get("name"), item.get("specific_weight"))
    if f is None:
        raise ValueError(f"التغليف بـ«{iu}» والصنف بـ«{han}» — اكتب الوزن النوعي "
                         f"للصنف في كارته (جم/لتر)")
    lu = (loose_unit or "").strip()
    lf = f if lu in ("", iu) else (
        measure_factor(lu, han, item.get("name"), item.get("specific_weight")) or 1.0
        if lu in MEASURE_UNITS else 1.0)
    return (han, round(float(capacity or 0) * f, 6), round(float(inner_capacity or 0) * f, 6),
            round(float(loose or 0) * lf, 6), f)


def follow_pack_unit(item, inner_unit, only_movement):
    """صنف مالوش حركة غير السطر ده ⇒ وحدته من معيار التغليف زي الصنف الجديد في ١ مخازن
    (١٥/١٠ «الرصيد هيضاف باللتر ويتحول الى كجم»): بين كجم↔لتر وبوزن نوعي معروف بس.
    يرجع (الصنف بوحدته الجديدة، الوحدة القديمة) — أو (الصنف، "") لو مفيش تغيير:
    الصنف اللي عليه حركة تانية وحدته مُثبَّتة والتغليف بيتحول لها بالوزن النوعي."""
    han = (item.get("handle_unit") or "").strip()
    iu = (inner_unit or "").strip()
    if (not only_movement or iu not in MEASURE_UNITS or han not in MEASURE_UNITS
            or unit_base(iu)[0] == unit_base(han)[0]
            or measure_factor(iu, han, item.get("name"), item.get("specific_weight")) is None):
        return item, ""
    return dict(item, handle_unit=iu, base_unit=unit_base(iu)[0]), han


def save_note(item, old_unit, total, conv, from_unit):
    """رسالة الحفظ (١٥/١٠): «وحدة الصنف: كجم ← لتر (١٢٠ لتر = ١٠٩٫٦٨ كجم في ٣ مخازن)»
    لو الوحدة اتغيرت، أو «١٢٠ لتر = ١٠٩٫٦٨ كجم» لو التغليف اتحول لوحدة الصنف."""
    from core import arabic_numbers as arnum
    unit = (item.get("handle_unit") or "").strip()
    if old_unit:
        book, f = ledger_unit(item.get("name"), item.get("ration_unit"), unit,
                              item.get("specific_weight"))
        tail = (f" ({arnum.fmt_qty_trim(total)} {unit} = "
                f"{arnum.fmt_qty_trim(round(total * f, 6))} {book} في ٣ مخازن)"
                if book != unit and total > 0 else "")
        return f"وحدة الصنف: {old_unit} ← {unit}{tail}"
    if abs(conv - 1.0) < 1e-12 or total <= 0:
        return ""
    return (f"{arnum.fmt_qty_trim(round(total / conv, 6))} {from_unit} = "
            f"{arnum.fmt_qty_trim(total)} {unit}")
