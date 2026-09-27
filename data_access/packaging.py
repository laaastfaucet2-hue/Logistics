# -*- coding: utf-8 -*-
"""صيغ التغليف اللفظية الاحترافية — توجيه المستخدم ٢٦/٠٩ مساءً وجلسة المربع الموحد.

النموذج المعتمد: وزن العبوة الواحدة (الكرتونة كام؟) هو المرجع للمجموع،
والعلب بداخلها تفصيل اختياري — ولو فيه فرق بين وزن العبوة وحاصل ضرب العلب
تُظهر الصيغ الفرق بوضوح. السائب يدخل بوحدة التعامل أو بالعلب (يتحول بوزن العلبة).
"""
import re

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
                 inner_count=0, inner_capacity=0, loose_unit="", inner_kind=""):
    """(الملخص النصي الاحترافي، المجموع) — كل خطوة الحسبة ظاهرة بالكلام.

    - شكارة: «١٩ شكارة × وزن الشكارة ٥٠ كجم = ٩٥٠ كجم + ٥٠ كجم سائب = ١٠٠٠ كجم»
    - كرتونة بعleb: «١٠ كرتونة × وزن الكرتونة ١٢ كجم (بداخلها ٦ علب × ٢ كجم) = ١٢٠ كجم»
    - بلا وزن للعبوة: «٤ كرتونة بداخلها ٦ علب × وزن العلبة ٢ كجم = ٤٨ كجم»
    - بعدّ الوحدات (توجيه ٢٧/٠٩): «١٠ بلتة بداخلها ٢٧ باكت = ٢٧٠ باكت»
    - سائب بالعلب: «٥ علب × ٢ كجم = ١٠ كجم سائب»
    """
    kind = (kind or "").strip()
    inner_kind = (inner_kind or "").strip()
    count = float(count or 0)
    capacity = float(capacity or 0)
    loose = float(loose or 0)
    inner_count = float(inner_count or 0)
    inner_capacity = float(inner_capacity or 0)
    iword = inner_kind or _box_word(inner_count)      # اسم الوحدة الداخلية
    total = 0.0
    bits = []
    if kind and kind != "بدون تغليف" and count > 0:
        if capacity > 0:
            sub = count * capacity
            total += sub
            detail = ""
            if inner_count > 0:
                detail = (f" (بداخلها {arnum.to_arabic_indic(f'{inner_count:g}')} "
                          f"{iword}"
                          + (f" × {arnum.fmt_qty_trim(inner_capacity)} {unit}"
                             if inner_capacity > 0 else "") + ")")
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind} × وزن "
                        f"ال{kind} {arnum.fmt_qty_trim(capacity)} {unit}{detail} = "
                        f"{arnum.fmt_qty_trim(sub)} {unit}")
        elif inner_count > 0 and inner_capacity > 0:
            sub = count * inner_count * inner_capacity
            total += sub
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind} "
                        f"بداخلها {arnum.to_arabic_indic(f'{inner_count:g}')} "
                        f"{iword} × وزن ال{inner_kind or 'علبة'} "
                        f"{arnum.fmt_qty_trim(inner_capacity)} {unit} = "
                        f"{arnum.fmt_qty_trim(sub)} {unit}")
        elif inner_count > 0:
            sub = count * inner_count
            total += sub
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind} "
                        f"بداخلها {arnum.to_arabic_indic(f'{inner_count:g}')} "
                        f"{iword} = {arnum.fmt_qty_trim(sub)} {iword}")
        else:
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind}")
    if loose > 0:
        if _is_loose_boxes(loose_unit) and inner_capacity > 0:
            loose_kg = loose * inner_capacity
            total += loose_kg
            bits.append(f"{arnum.to_arabic_indic(f'{loose:g}')} "
                        f"{iword if inner_kind else _box_word(loose)} × "
                        f"{arnum.fmt_qty_trim(inner_capacity)} {unit} = "
                        f"{arnum.fmt_qty_trim(loose_kg)} {unit} سائب")
        elif _is_loose_boxes(loose_unit) and inner_kind:
            # عدّ الوحدات: السائب بالعلب يُجمع كما هو — لا وزن مطلوب (توجيه ٢٧/٠٩)
            total += loose
            bits.append(f"{arnum.to_arabic_indic(f'{loose:g}')} {iword} سائب")
        elif _is_loose_boxes(loose_unit):
            total += loose
            bits.append(f"{arnum.to_arabic_indic(f'{loose:g}')} "
                        f"{_box_word(loose)} سائب")
        else:
            total += loose
            unit_word = iword if (inner_kind and not capacity and not inner_capacity) \
                else (unit or iword)
            bits.append(f"{arnum.fmt_qty_trim(loose)} {unit_word} سائب")
    label = " + ".join(bits)
    if len(bits) > 1 and total > 0:
        sum_unit = iword if (inner_kind and capacity <= 0
                             and inner_capacity <= 0) else (unit or iword)
        label += f" = {arnum.fmt_qty_trim(total)} {sum_unit}"
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
            parts.append(f"{arnum.to_arabic_indic(str(full_packs))} {_box_word(full_packs)}{_fw}")
        if rest > 0.000001:
            if open_mode:
                parts.append(f"{_open_pack(_box_word(1))} ({arnum.fmt_qty_trim(rest)} {unit})")
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
                parts.append(f"{_open_pack(kind)} ({arnum.fmt_qty_trim(rest)} {unit})")
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


def parse_pack_label(label):
    """(count, kind, capacity, loose) من صيغة الملخص الموحدة — أصفار لو ما لقتش."""
    label = (label or "").strip()
    if not label or label == "—":
        return 0.0, "", 0.0, 0.0
    _num = r"([\d٠-٩]+(?:[\.٫][\d٠-٩]+)?)"
    cnt, kind, cap, loose = 0.0, "", 0.0, 0.0
    m = re.search(_num + r"\s+([^\s×=+]+)\s*×", label)
    if m:
        cnt, kind = arnum.parse_float(m.group(1)) or 0.0, m.group(2)
        c = re.search(r"وزن ال[^\s]+\s+" + _num, label)
        cap = arnum.parse_float(c.group(1)) if c else 0.0
    else:
        m = re.match(r"^" + _num + r"\s+([^\s×=+]+)$", label)
        if m:
            cnt, kind = arnum.parse_float(m.group(1)) or 0.0, m.group(2)
    l = re.search(r"\+\s*" + _num + r"\s+([^\s=]+)\s+سائب", label)
    if l:
        loose = arnum.parse_float(l.group(1)) or 0.0
    return cnt, kind, cap, loose


class PackLedger:
    """رصيد عبوات الصنف (توجيه ٢٧/٠٩ مساءً): الكاملة ما تتحولش سائب —
    الصرف يسحب من السائب أولًا، ثم من المفتوحة، ثم يفتح عبوة كاملة."""

    def __init__(self, kind="", capacity=0.0, unit=""):
        self.kind = (kind or "").strip()
        self.capacity = float(capacity or 0)
        self.unit = unit or ""
        self.full = 0.0      # عبوات كاملة مقفولة
        self.loose = 0.0     # سائب حر بوحدة التعامل
        self.rest = 0.0      # باقي عبوة مفتوحة

    def set_kind(self, kind, capacity):
        if not self.kind and (kind or "").strip():
            self.kind = (kind or "").strip()
            self.capacity = float(capacity or 0)

    def add(self, count, loose):
        self.full += float(count or 0)
        self.loose += float(loose or 0)

    def add_qty(self, q):
        self.loose += float(q or 0)

    def take(self, q):
        q = float(q or 0)
        t = min(q, self.loose)
        self.loose = round(self.loose - t, 6)
        q = round(q - t, 6)
        if q > 0 and self.rest > 0:
            t = min(q, self.rest)
            self.rest = round(self.rest - t, 6)
            q = round(q - t, 6)
        while q > 0 and self.full >= 1 and self.capacity > 0:
            self.full -= 1
            if self.capacity >= q:
                self.rest = round(self.capacity - q, 6)
                q = 0
            else:
                q = round(q - self.capacity, 6)

    def label(self):
        if not self.kind:
            return f"{arnum.fmt_qty_trim(round(self.loose, 6))} {self.unit}".strip()
        parts = []
        fem = self.kind in _FEM_KINDS
        if self.rest > 0:
            if self.full > 0:
                parts.append(f"{arnum.to_arabic_indic(f'{self.full:g}')} {self.kind} {'كاملة' if fem else 'كامل'}")
            parts.append(f"{_open_pack(self.kind)} ({arnum.fmt_qty_trim(self.rest)} {self.unit})")
        elif self.full > 0:
            parts.append(f"{arnum.to_arabic_indic(f'{self.full:g}')} {self.kind}")
        if self.loose > 0 or not parts:
            parts.append(f"{arnum.fmt_qty_trim(round(self.loose, 6))} {self.unit} سائب")
        return " + ".join(parts)
