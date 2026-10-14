# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""بيانات شهر واحد لإحصائيات المخازن في مرة واحدة — من دوال قسم المخازن نفسها.

المصدر الوحيد: `stores_report` (حركة كل مخزن للدورتين) + `remaining_batches`
(الباقي الفعلي في كل دفعة بعد التفريدة FEFO). لا حساب موازٍ.

الناتج قاموس للقراءة فقط (لا يُعدَّل من أي تبويب):
    lines      سطور الحركة: وارد (أول المدة/إذن إضافة) ومنصرف (تفريدة إذون ٢ مخازن)
    batches    الدفعات بالباقي الفعلي (إذون الإضافة + رصيد أول المدة)
    shortfalls عجز الصرف: المطلوب في الإذن أكثر من المصروف فعلًا
    packs      الرصيد بالتغليف لكل (مخزن، صنف) — من حالة العبوات نفسها
    stores     سجل المخازن بمواصفاته · targets المخازن + «غير موزع»

يُحفظ مؤقتًا في الذاكرة ببصمة قاعدة الشهر + سجل المخازن (في system.db) + تاريخ المرجع.
"""
import hashlib
import json
import threading
from datetime import date

from core import egtime

CYCLES = (("supply", "الإمداد"), ("contractor", "المتعهد"))
CYCLE_NAMES = dict(CYCLES)
CYCLE_BY_NAME = {name: key for key, name in CYCLES}
UNASSIGNED_ID = 0

_CACHE = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 64


def unassigned_name():
    from data_access.db_warehouses_stores import UNASSIGNED
    return UNASSIGNED


# ---------------------------------------------------------------- التواريخ
def ref_date(year, month, today=None):
    """تاريخ حساب الصلاحية والتغطية: اليوم في الشهر الجاري، وآخر الشهر للشهور الفائتة."""
    today = today or egtime.today()
    if (year, month) == (today.year, today.month):
        return today
    if (year, month) < (today.year, today.month):
        return date(year, month, egtime.days_in_month(year, month))
    return date(year, month, 1)


def elapsed_days(year, month, today=None):
    """الأيام المنقضية لمتوسط الصرف: حتى اليوم في الشهر الجاري، والشهر كله غير ذلك."""
    today = today or egtime.today()
    if (year, month) == (today.year, today.month):
        return today.day
    return egtime.days_in_month(year, month)


def is_current(year, month, today=None):
    today = today or egtime.today()
    return (year, month) == (today.year, today.month)


# ---------------------------------------------------------------- البصمات
def month_signature(year, month):
    """بصمة ثابتة لقاعدة الشهر: الملف + WAL الممتلئ فقط (القراءة لا تغيّرها)."""
    from data_access import months
    path = months.month_db_path(year, month)
    try:
        stat = path.stat()
    except OSError:
        return (0,)
    parts = [stat.st_mtime_ns, stat.st_size]
    try:
        wal = path.with_name(path.name + "-wal").stat()
        if wal.st_size > 0:
            parts += [wal.st_mtime_ns, wal.st_size]
    except OSError:
        pass
    return tuple(parts)


def registry_rows():
    from data_access import db_stores
    return db_stores.list_stores()


def registry_signature(rows=None):
    """بصمة محتوى سجل المخازن (system.db يتغير مع كل طلب فلا تصلح بصمة الملف)."""
    rows = registry_rows() if rows is None else rows
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def month_exists(year, month):
    from data_access import months
    return months.month_db_path(year, month).exists()


# ---------------------------------------------------------------- البناء
def month_facts(year, month, today=None):
    """بيانات الشهر (مخزنة مؤقتًا) — قاموس للقراءة فقط."""
    year, month = int(year), int(month)
    stores = registry_rows()
    ref = ref_date(year, month, today)
    key = (year, month, month_signature(year, month), registry_signature(stores), ref,
           elapsed_days(year, month, today))
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
    if hit is not None:
        return hit
    facts = _build(year, month, stores, ref, key[-1])
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = facts
    return facts


def clear_cache():
    with _CACHE_LOCK:
        _CACHE.clear()


def _empty(year, month, stores, ref, elapsed):
    unassigned = unassigned_name()
    return {
        "year": year, "month": month, "ref": ref, "elapsed": elapsed,
        "days": egtime.days_in_month(year, month),
        "stores": stores,
        "targets": [{"id": s["id"], "name": s["name"]} for s in stores]
        + [{"id": UNASSIGNED_ID, "name": unassigned}],
        "lines": [], "batches": [], "shortfalls": [], "packs": {},
        "has_data": False, "filtered": False,
    }


def _build(year, month, stores, ref, elapsed):
    facts = _empty(year, month, stores, ref, elapsed)
    if not month_exists(year, month):
        return facts
    from data_access import db_warehouses_stores as dws
    known = {s["id"]: s["name"] for s in stores}
    report = dws.stores_report(year, month)
    lines, packs = facts["lines"], facts["packs"]
    for target in report["stores"] + [report["unassigned"]]:
        sid = target["store"].get("id")
        sid = sid if sid in known else UNASSIGNED_ID
        name = known.get(sid) or unassigned_name()
        for row in target["inn"]:
            serial = int(row.get("serial") or 0)
            lines.append(_line("in", sid, name, row, serial=serial, opener=not serial,
                               supplier=row.get("supplier"), producer=row.get("producer")))
        for row in target["out"]:
            lines.append(_line("out", sid, name, row, permit=int(row.get("permit_no") or 0),
                               entity=row.get("entity")))
        for item, label in (target.get("pack_notes") or {}).items():
            if label:
                packs[(sid, item)] = label
    facts["batches"] = _batches(year, month, known)
    facts["shortfalls"] = _shortfalls(year, month)
    facts["has_data"] = bool(lines)
    return facts


def _line(direction, sid, store, row, serial=0, opener=False, permit=0, entity="",
          supplier="", producer=""):
    return {
        "dir": direction, "opener": opener, "store_id": sid, "store": store,
        "cycle": CYCLE_BY_NAME.get(row.get("cycle"), ""),
        "item": row.get("item") or "", "unit": row.get("unit") or "",
        "qty": round(float(row.get("qty") or 0), 6),
        "date": row.get("date_iso") or "", "serial": serial, "permit": permit,
        "entity": (entity or "").strip(), "supplier": (supplier or "").strip(),
        "producer": (producer or "").strip(), "expiry": row.get("expiry") or "",
    }


def _batches(year, month, known):
    """الدفعات بالباقي الفعلي بعد التفريدة — مع بيانات إذن الإضافة (المورد/الإنتاج)."""
    from data_access import db_warehouses as dw
    from data_access import db_warehouses_stores as dws
    out = []
    for cycle, _name in CYCLES:
        meta = {}
        for rec in dw.list_receipts(year, month, cycle):
            meta.setdefault((rec["serial"], rec["item_id"]), rec)
        for batch in dws.remaining_batches(year, month, cycle):
            sid = batch["store_id"] if batch["store_id"] in known else UNASSIGNED_ID
            rec = meta.get((batch["serial"], batch["item_id"]), {}) if batch["serial"] else {}
            out.append({
                "store_id": sid, "store": known.get(sid) or unassigned_name(),
                "cycle": cycle, "item": batch["item"], "unit": batch["unit"] or "",
                "qty": batch["qty"], "remaining": batch["remaining"],
                "expiry": batch["expiry"], "serial": batch["serial"],
                "opener": not batch["serial"],
                "producer": (batch["producer"] or rec.get("producer") or "").strip(),
                "supplier": (rec.get("supplier_name") or "").strip(),
                "prod_date": rec.get("prod_date") or "",
                "date": rec.get("date_iso") or "",
            })
    return out


def _shortfalls(year, month):
    """عجز الصرف لكل (إذن، صنف): المطلوب بوحدة التعامل − المصروف فعلًا (FEFO)."""
    from data_access import db_warehouses as dw
    from data_access import db_warehouses_stores as dws
    from data_access import oil_units as ou
    out = []
    for cycle, _name in CYCLES:
        items = {it["name"]: it for it in dw.raw_items(year, month, cycle)}
        actual = dws.fefo_actual_map(year, month, cycle)
        for permit in dw.permits_book(year, month, cycle):
            for entry in permit["cycle_items"]:
                need = float(entry["qty"] or 0)
                item = items.get(entry["name"])
                if need <= 0 or not item:
                    continue
                need *= ou.calc_to_handle_factor(item["name"], item["ration_unit"],
                                                 item["handle_unit"], item.get("specific_weight"))
                issued = actual.get((int(permit["number"]), entry["name"]), 0.0)
                short = round(need - issued, 6)
                if short > 0.001:
                    out.append({
                        "cycle": cycle, "item": entry["name"], "unit": item["handle_unit"] or "",
                        "permit": int(permit["number"]), "need": round(need, 6),
                        "issued": round(issued, 6), "short": short,
                        "entity": (permit.get("entity_label") or "").strip(),
                        "date": f"{year:04d}-{month:02d}-{int(permit['date_from']):02d}",
                    })
    return out


# ---------------------------------------------------------------- الفلاتر
def apply_filter(facts, flt):
    """نسخة مصفاة للشاشة والطباعة (المخزن/الدورة/الصنف) — الإكسل دائمًا كامل."""
    if not flt or not flt.get("active"):
        return facts
    store, cycle, item = flt.get("store"), flt.get("cycle"), flt.get("item")

    def keep(row, with_store=True):
        if with_store and store is not None and row.get("store_id") != store:
            return False
        if cycle and row.get("cycle") != cycle:
            return False
        return not (item and row.get("item") != item)

    out = dict(facts)
    out["lines"] = [r for r in facts["lines"] if keep(r)]
    out["batches"] = [b for b in facts["batches"] if keep(b)]
    out["shortfalls"] = ([s for s in facts["shortfalls"] if keep(s, False)]
                         if store is None else [])
    if store is not None:
        out["targets"] = [t for t in facts["targets"] if t["id"] == store]
        out["stores"] = [s for s in facts["stores"] if s["id"] == store]
    out["packs"] = {} if cycle else {k: v for k, v in facts["packs"].items()
                                     if not item or k[1] == item}
    out["filtered"] = True
    return out
