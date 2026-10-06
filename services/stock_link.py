# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""ربط آلة حاسبة ٢ مخازن بالمخازن — «الرصيد المتوفر بالمخازن» + «الحالة الكلية للرصيد».

توجيه المستخدم ٠٦/١٠/٢٠٢٦: العمودان كانا «قيد التطوير» في `templates/calc2/page.html`،
والمطلوب أن يُقرأ الرصيد **لحظيًا** من نفس مصدر شاشات المستودعات (`db_warehouses`):

* الكمية **بالوحدة الأصلية** لجانبها **الرصيد بالتغليف** (شكارة/كرتونة… عبر `db_pack`).
* «الرصيد بعد هذا الإذن» = المتوفر − الكمية الفعلية لهذا الإذن (بدون أي خصم مزدوج،
  فالخصم الحقيقي يقع مرة واحدة عند حفظ الإذن في `tafreeda_rows`).
* «الحالة الكلية للرصيد» ثلاث حالات: آمن · يوشك على النفاذ · لا يوجد — وحدّها من
  `core.config.STOCK_LOW_RATIO` (يحدده المستخدم).

هذا الملف **قراءة فقط**: لا يكتب أي بيانات ولا يعدّل أرصدة.
"""
from core import arabic_numbers as arnum
from core.config import STOCK_LOW_RATIO
from data_access import db_warehouses as dw
from data_access import packaging

# قسم الآلة الحاسبة ⇒ دورة المخازن (مصدر واحد للربط)
CYCLE_BY_SECTION = {"tamween": "supply", "contractor": "contractor"}

STATUS_SAFE = "آمن"
STATUS_LOW = "يوشك على النفاذ"
STATUS_NONE = "لا يوجد"
STATUS_KEYS = {STATUS_SAFE: "safe", STATUS_LOW: "low", STATUS_NONE: "none"}


def balances(year, month, cycle):
    """{اسم الصنف: {qty, unit}} — مجموع أرصدة الصنف في كل مخازن دورته."""
    out = {}
    for item in dw.list_items(year, month, cycle):
        name = (item.get("name") or "").strip()
        if not name:
            continue
        entry = out.setdefault(name, {"qty": 0.0, "unit": ""})
        entry["qty"] += float(item.get("balance") or 0.0)
        entry["unit"] = entry["unit"] or (item.get("handle_unit")
                                          or item.get("ration_unit") or "")
    return out


def pack_text(year, month, cycle, name, qty, specs=None, units=None):
    """الرصيد بالتغليف: «٢ شكارة + ٢٠ كجم» — بلا مواصفات مسجلة يبقى نص فارغ."""
    specs = specs if specs is not None else dw.pack_specs_map(year, month, cycle)
    entry = (specs.get(name) or {})
    if not entry or abs(float(qty or 0)) <= 0:
        return ""
    kind = list(entry)[-1]                       # آخر مواصفات مسجلة للصنف
    spec = entry[kind] or {}
    if units is None:
        units = {i["name"]: i.get("handle_unit") or "" for i in dw.list_items(year, month, cycle)}
    return packaging.pack_breakdown(kind, spec.get("capacity"), spec.get("inner_count"),
                                    spec.get("inner_capacity"), float(qty),
                                    units.get(name, ""), inner_kind=spec.get("inner_kind"))


def status_of(avail, needed):
    """حالة الرصيد: لا يوجد (صفر) · يوشك على النفاذ (المتبقي < نسبة الحد) · آمن."""
    avail = float(avail or 0)
    needed = float(needed or 0)
    if avail <= 0:
        return STATUS_NONE
    remaining = avail - needed
    if needed > 0 and remaining < needed * float(STOCK_LOW_RATIO):
        return STATUS_LOW
    if needed <= 0 and avail <= 0:
        return STATUS_NONE
    return STATUS_SAFE


def availability(year, month, cycle, name, needed=0.0, cache=None):
    """رصيد صنف واحد: الوحدة + الرصيد + التغليف + المتبقي بعده + الحالة.

    cache: نتيجة `balances(...)` (ونظائرها) لتجنّب إعادة القراءة لكل صف.
    """
    cache = cache or {}
    bal = cache.get("balances") or balances(year, month, cycle)
    entry = bal.get(name) or {"qty": 0.0, "unit": ""}
    avail = float(entry.get("qty") or 0.0)
    pack = pack_text(year, month, cycle, name, avail,
                     specs=cache.get("specs"), units=cache.get("units"))
    remaining = avail - float(needed or 0)
    status = status_of(avail, needed)
    return {
        "name": name, "unit": entry.get("unit") or "",
        "avail": round(avail, 6), "pack": pack,
        "needed": round(float(needed or 0), 6), "remaining": round(remaining, 6),
        "remaining_text": arnum.fmt_qty_trim(remaining),
        "status": status, "key": STATUS_KEYS[status],
    }


def cycle_cache(year, month, cycle):
    """لقطة واحدة لكل دورة تُمرَّر لكل الصفوف (قراءة واحدة بدل صف بصف)."""
    units = {i["name"]: i.get("handle_unit") or i.get("ration_unit") or ""
             for i in dw.list_items(year, month, cycle)}
    return {"balances": balances(year, month, cycle),
            "specs": dw.pack_specs_map(year, month, cycle), "units": units}


def for_rows(year, month, section, rows):
    """{اسم الصنف: بيانات الرصيد} لجدول الآلة الحاسبة — needed = الكمية المقررة تلقائيًا."""
    cycle = CYCLE_BY_SECTION.get(section)
    if not cycle:
        return {}
    cache = cycle_cache(year, month, cycle)
    out = {}
    for row in rows or []:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        needed = float(row.get("auto") or 0.0)
        out[name] = availability(year, month, cycle, name, needed, cache=cache)
    return out


def totals(stock_map):
    """إجمالي حالات الجدول — لشارة أعلى الجدول (آمن/يوشك/لا يوجد)."""
    counts = {STATUS_SAFE: 0, STATUS_LOW: 0, STATUS_NONE: 0}
    for info in (stock_map or {}).values():
        counts[info["status"]] = counts.get(info["status"], 0) + 1
    return counts
