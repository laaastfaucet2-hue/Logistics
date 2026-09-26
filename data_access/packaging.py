# -*- coding: utf-8 -*-
"""صيغ التغليف اللفظية الاحترافية — توجيه المستخدم ٢٦/٠٩ مساءً وجلسة المربع الموحد.

النموذج المعتمد: وزن العبوة الواحدة (الكرتونة كام؟) هو المرجع للمجموع،
والعلب بداخلها تفصيل اختياري — ولو فيه فرق بين وزن العبوة وحاصل ضرب العلب
تُظهر الصيغ الفرق بوضوح. السائب يدخل بوحدة التعامل أو بالعلب (يتحول بوزن العلبة).
"""
from core import arabic_numbers as arnum


def _box_word(n):
    """«علبة/علب» بعد العدد — ٣–١٠ علب، وما عداه علبة."""
    n = int(n or 0)
    if 3 <= n <= 10:
        return "علب"
    return "علبة"


def _is_loose_boxes(loose_unit):
    """هل السائب مُدخل بالعلب؟ («علبة» أو «علب»)."""
    return (loose_unit or "").strip().startswith("علب")


_FEM_KINDS = {"شكارة", "علبة", "بلتة", "كرتونة", "قطعة", "فتلة"}


def _full_word(kind):
    """«كاملة» للمؤنث و«كامل» للمذكر — تُلحق بالعبوات الكاملة عند وجود مفتوحة."""
    return "كاملة" if (kind or "").strip() in _FEM_KINDS else "كامل"


def _open_pack(kind):
    """«شكارة مفتوحة / جركن مفتوح» — العبوة المفتوحة اللي جواها الباقي."""
    kind = (kind or "").strip()
    word = "مفتوحة" if kind in _FEM_KINDS else "مفتوح"
    return f"{kind} {word}"


def pack_diff_note(capacity, inner_count, inner_capacity, unit):
    """جملة الفرق بين وزن العبوة وحاصل ضرب العلب — فاضية لو مفيش فرق أو علب."""
    capacity = float(capacity or 0)
    inner_count = float(inner_count or 0)
    inner_capacity = float(inner_capacity or 0)
    if capacity <= 0 or inner_count <= 0 or inner_capacity <= 0:
        return ""
    sub = inner_count * inner_capacity
    diff = round(capacity - sub, 6)
    if abs(diff) <= 0.001:
        return ""
    word = "فوق" if diff > 0 else "تحت"
    return (f"فرق {arnum.fmt_qty_trim(abs(diff))} {unit} {word} حاصل العلب "
            f"({arnum.fmt_qty_trim(sub)} {unit})")


def pack_summary(kind, count, capacity, loose, unit,
                 inner_count=0, inner_capacity=0, loose_unit=""):
    """(الملخص النصي الاحترافي، المجموع) — كل خطوة الحسبة ظاهرة بالكلام.

    - شكارة: «١٩ شكارة × وزن الشكارة ٥٠ كجم = ٩٥٠ كجم + ٥٠ كجم سائب = ١٠٠٠ كجم»
    - كرتونة بعleb: «١٠ كرتونة × وزن الكرتونة ١٢ كجم (بداخلها ٦ علب × ٢ كجم) = ١٢٠ كجم»
    - بلا وزن للعبوة: «٤ كرتونة بداخلها ٦ علب × وزن العلبة ٢ كجم = ٤٨ كجم»
    - سائب بالعلب: «٥ علب × ٢ كجم = ١٠ كجم سائب»
    """
    kind = (kind or "").strip()
    count = float(count or 0)
    capacity = float(capacity or 0)
    loose = float(loose or 0)
    inner_count = float(inner_count or 0)
    inner_capacity = float(inner_capacity or 0)
    total = 0.0
    bits = []
    if kind and kind != "بدون تغليف" and count > 0:
        if capacity > 0:
            sub = count * capacity
            total += sub
            detail = ""
            if inner_count > 0 and inner_capacity > 0:
                detail = (f" (بداخلها {arnum.to_arabic_indic(f'{inner_count:g}')} "
                          f"{_box_word(inner_count)} × "
                          f"{arnum.fmt_qty_trim(inner_capacity)} {unit})")
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind} × وزن "
                        f"ال{kind} {arnum.fmt_qty_trim(capacity)} {unit}{detail} = "
                        f"{arnum.fmt_qty_trim(sub)} {unit}")
        elif inner_count > 0 and inner_capacity > 0:
            sub = count * inner_count * inner_capacity
            total += sub
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind} "
                        f"بداخلها {arnum.to_arabic_indic(f'{inner_count:g}')} "
                        f"{_box_word(inner_count)} × وزن العلبة "
                        f"{arnum.fmt_qty_trim(inner_capacity)} {unit} = "
                        f"{arnum.fmt_qty_trim(sub)} {unit}")
        else:
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind}")
    if loose > 0:
        if _is_loose_boxes(loose_unit) and inner_capacity > 0:
            loose_kg = loose * inner_capacity
            total += loose_kg
            bits.append(f"{arnum.to_arabic_indic(f'{loose:g}')} "
                        f"{_box_word(loose)} × "
                        f"{arnum.fmt_qty_trim(inner_capacity)} {unit} = "
                        f"{arnum.fmt_qty_trim(loose_kg)} {unit} سائب")
        else:
            total += loose
            bits.append(f"{arnum.fmt_qty_trim(loose)} {unit} سائب")
    label = " + ".join(bits)
    if len(bits) > 1 and total > 0:
        label += f" = {arnum.fmt_qty_trim(total)} {unit}"
    return label, round(total, 6)


def pack_breakdown(kind, capacity, inner_count, inner_capacity, remaining, unit,
                   rest_word="سائب"):
    """تفكيك كمية لعبوات + الباقي جوه عبوة مفتوحة (توجيه المستخدم ٢٦/٠٩).

    ١٧٠ كجم بشكارة ٥٠ ⇒ «٣ شكارة كاملة + شكارة مفتوحة (٢٠ كجم)»؛
    ١٥٠ كجم ⇒ «٣ شكارة»؛ صيغة المصروف (rest_word="") تبقى بدون «كاملة/مفتوحة»:
    «١ شكارة + ١٠ كجم». ٢٨ كجم بكرتونة ٦ علب × ٢ ⇒ «٢ كرتونة + ٢ علبة»؛
    ١١٫٩٨٨ كجم ⇒ «٥ علب كاملة + علبة مفتوحة (١٫٩٨٨ كجم)». بلا مواصفات ⇒ «—».
    """
    kind = (kind or "").strip()
    capacity = float(capacity or 0)
    inner_count = float(inner_count or 0)
    inner_capacity = float(inner_capacity or 0)
    remaining = float(remaining or 0)
    if remaining <= 0:
        return ""
    open_mode = (rest_word == "سائب")          # الأرصدة تُظهر العبوة المفتوحة
    parts = []
    if inner_count > 0 and inner_capacity > 0:
        carton = inner_count * inner_capacity
        full_cartons = int(remaining // carton)
        rem = remaining - full_cartons * carton
        full_packs = int(rem // inner_capacity)
        rest = round(rem - full_packs * inner_capacity, 6)
        _fw = f" {_full_word(kind)}" if open_mode and rest > 0.000001 else ""
        if full_cartons > 0:
            parts.append(f"{arnum.to_arabic_indic(str(full_cartons))} {kind}{_fw}")
        if full_packs > 0:
            parts.append(f"{arnum.to_arabic_indic(str(full_packs))} "
                         f"{_box_word(full_packs)}{_fw}")
        if rest > 0.000001:
            if open_mode:
                parts.append(f"{_open_pack(_box_word(1))} "
                             f"({arnum.fmt_qty_trim(rest)} {unit})")
            else:
                parts.append(f"{arnum.fmt_qty_trim(rest)} {unit}")
    elif kind and capacity > 0:
        full = int(remaining // capacity)
        rest = round(remaining - full * capacity, 6)
        if full > 0:
            _fw = f" {_full_word(kind)}" if open_mode and rest > 0.000001 else ""
            parts.append(f"{arnum.to_arabic_indic(str(full))} {kind}{_fw}")
        if rest > 0.000001:
            if open_mode:
                parts.append(f"{_open_pack(kind)} "
                             f"({arnum.fmt_qty_trim(rest)} {unit})")
            else:
                parts.append(f"{arnum.fmt_qty_trim(rest)} {unit}")
    else:
        parts.append(f"{arnum.fmt_qty_trim(remaining)} {unit}")
    return " + ".join(parts) if parts else ""


def pack_split(kind, count, capacity, loose, unit,
               inner_count=0, inner_capacity=0, loose_unit=""):
    """(تغليف داخلي، تغليف خارجي) لسطر التفريدة — العمودان المستقلان.

    كرتونة بعلب: الداخلي «٦ علب × وزن العلبة ٢ كجم = ١٢ كجم للكرتونة»
    (+ جملة الفرق لو وزن الكرتونة المكتوب لا يطابق) والخارجي
    «١٠ كرتونة × وزن الكرتونة ١٢ كجم = ١٢٠ كجم». بلا علب: الداخلي «—».
    """
    kind = (kind or "").strip()
    count = float(count or 0)
    capacity = float(capacity or 0)
    loose = float(loose or 0)
    inner_count = float(inner_count or 0)
    inner_capacity = float(inner_capacity or 0)
    if not kind or kind == "بدون تغليف" or count <= 0:
        return "", ""
    if inner_count > 0 and inner_capacity > 0:
        carton_w = inner_count * inner_capacity
        inner = (f"{arnum.to_arabic_indic(f'{inner_count:g}')} {_box_word(inner_count)}"
                 f" × وزن العلبة {arnum.fmt_qty_trim(inner_capacity)} {unit}"
                 f" = {arnum.fmt_qty_trim(carton_w)} {unit} لل{kind}")
        diff = pack_diff_note(capacity, inner_count, inner_capacity, unit)
        if diff:
            inner += f" ({diff})"
        ref_w = capacity if capacity > 0 else carton_w
        outer = (f"{arnum.to_arabic_indic(f'{count:g}')} {kind} × وزن "
                 f"ال{kind} {arnum.fmt_qty_trim(ref_w)} {unit} = "
                 f"{arnum.fmt_qty_trim(count * ref_w)} {unit}")
        if loose > 0:
            if _is_loose_boxes(loose_unit) and inner_capacity > 0:
                outer += (f" + {arnum.to_arabic_indic(f'{loose:g}')} "
                          f"{_box_word(loose)} × "
                          f"{arnum.fmt_qty_trim(inner_capacity)} {unit} سائب")
            else:
                outer += f" + {arnum.fmt_qty_trim(loose)} {unit} سائب"
        return inner, outer
    if capacity > 0:
        inner = ""
        outer = (f"{arnum.to_arabic_indic(f'{count:g}')} {kind} × وزن "
                 f"ال{kind} {arnum.fmt_qty_trim(capacity)} {unit} = "
                 f"{arnum.fmt_qty_trim(count * capacity)} {unit}")
        if loose > 0:
            outer += f" + {arnum.fmt_qty_trim(loose)} {unit} سائب"
        return inner, outer
    return "", f"{arnum.to_arabic_indic(f'{count:g}')} {kind}"
