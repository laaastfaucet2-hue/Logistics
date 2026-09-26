# -*- coding: utf-8 -*-
"""صيغ التغليف اللفظية الاحترافية — توجيه المستخدم ٢٦/٠٩ مساءً.

كل خطوة الحسبة ظاهرة بالكلام: العدد + مسمى العبوة + وزن الوحدة + عملية الضرب
+ السائب = المجموع، مع دعم التداخل (كارتونة بداخلها علب بوزن معلوم للعلبة).
"""
from core import arabic_numbers as arnum


def _box_word(n):
    """«علبة/علب» بعد العدد — ٣–١٠ علب، وما عداه علبة."""
    n = int(n or 0)
    if 3 <= n <= 10:
        return "علب"
    return "علبة"


def _box_word(n):
    """«علبة/علبتين/علب/علبة» بحسب العدد — لصيغة الكرتونة بداخلها علب."""
    n = int(n or 0)
    if 3 <= n <= 10:
        return "علب"
    return "علبة"


def pack_summary(kind, count, capacity, loose, unit,
                 inner_count=0, inner_capacity=0):
    """(الملخص النصي الاحترافي، المجموع) — توجيه المستخدم ٢٦/٠٩ مساءً.

    الصحيح يظهر صحيحًا والكسر بكسره، وكل خطوة الحسبة ظاهرة:
    - شكارة: «١٩ شكارة × وزن الشكارة ٥٠ كجم = ٩٥٠ كجم + ٥٠ كجم سائب = ١٠٠٠ كجم»
    - كرتونة بداخلها علب: «٤ كرتونة بداخلها ٦ علب × وزن العلبة ١٢ كجم = ٢٨٨ كجم»
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
        if inner_count > 0 and inner_capacity > 0:
            sub = count * inner_count * inner_capacity
            total += sub
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind} "
                        f"بداخلها {arnum.to_arabic_indic(f'{inner_count:g}')} "
                        f"{_box_word(inner_count)} × وزن العلبة "
                        f"{arnum.fmt_qty_trim(inner_capacity)} {unit} = "
                        f"{arnum.fmt_qty_trim(sub)} {unit}")
        elif capacity > 0:
            sub = count * capacity
            total += sub
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind} × وزن "
                        f"ال{kind} {arnum.fmt_qty_trim(capacity)} {unit} = "
                        f"{arnum.fmt_qty_trim(sub)} {unit}")
        else:
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind}")
    if loose > 0:
        total += loose
        bits.append(f"{arnum.fmt_qty_trim(loose)} {unit} سائب")
    label = " + ".join(bits)
    if len(bits) > 1 and total > 0:
        label += f" = {arnum.fmt_qty_trim(total)} {unit}"
    return label, round(total, 6)


def pack_breakdown(kind, capacity, inner_count, inner_capacity, remaining, unit):
    """«إيه التغليف المتبقي بالضبط» — تفكيك الرصيد لعبوات كاملة + سائب.

    ١٧٠ كجم بشكارة ٥٠ ⇒ «٣ شكارة + ٢٠ كجم سائب»؛
    ٢٨ كجم بكرتونة ٦ علب × ٢ كجم ⇒ «٢ كرتونة + ٢ علبة»؛
    ١١٫٩٨٨ كجم ⇒ «٥ علب + ١٫٩٨٨ كجم سائب». بلا مواصفات ⇒ «—».
    """
    kind = (kind or "").strip()
    capacity = float(capacity or 0)
    inner_count = float(inner_count or 0)
    inner_capacity = float(inner_capacity or 0)
    remaining = float(remaining or 0)
    if remaining <= 0:
        return ""
    parts = []
    if inner_count > 0 and inner_capacity > 0:
        carton = inner_count * inner_capacity
        full_cartons = int(remaining // carton)
        rem = remaining - full_cartons * carton
        full_packs = int(rem // inner_capacity)
        rest = round(rem - full_packs * inner_capacity, 6)
        if full_cartons > 0:
            parts.append(f"{arnum.to_arabic_indic(str(full_cartons))} {kind}")
        if full_packs > 0:
            parts.append(f"{arnum.to_arabic_indic(str(full_packs))} "
                         f"{_box_word(full_packs)}")
        if rest > 0.000001:
            parts.append(f"{arnum.fmt_qty_trim(rest)} {unit} سائب")
    elif kind and capacity > 0:
        full = int(remaining // capacity)
        rest = round(remaining - full * capacity, 6)
        if full > 0:
            parts.append(f"{arnum.to_arabic_indic(str(full))} {kind}")
        if rest > 0.000001:
            parts.append(f"{arnum.fmt_qty_trim(rest)} {unit} سائب")
    else:
        parts.append(f"{arnum.fmt_qty_trim(remaining)} {unit}")
    return " + ".join(parts) if parts else ""


def pack_split(kind, count, capacity, loose, unit,
               inner_count=0, inner_capacity=0):
    """(تغليف داخلي، تغليف خارجي) لسطر التفريدة — العمودان المستقلان.

    كرتونة بداخلها علب: الداخلي «٦ علب × وزن العلبة ٢ كجم = ١٢ كجم للكرتونة»
    والخارجي «٤ كرتونة × ١٢ كجم = ٤٨ كجم». بلا علب: الداخلي «—»
    والخارجي الصيغة الكاملة «١٩ شكارة × وزن الشكارة ٥٠ كجم = ٩٥٠ كجم».
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
        outer = (f"{arnum.to_arabic_indic(f'{count:g}')} {kind} × وزن "
                 f"ال{kind} {arnum.fmt_qty_trim(carton_w)} {unit} = "
                 f"{arnum.fmt_qty_trim(count * carton_w)} {unit}")
        if loose > 0:
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
