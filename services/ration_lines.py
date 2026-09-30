# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""بناء أسطر المقرر اليومي لجهة (تموين/متعهد) مع إمكانية التخصيص للتأميدة فقط."""
from datetime import date
from core.config import DAYS
from core import egtime
from data_access import db_rations as dr
from data_access import db_entities as de


def _positive(value):
    if value in (None, ""):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


MEAL_KEYS = ("breakfast", "lunch", "dinner")


def meal_parts(item):
    """مقرر الفطار/الغداء/العشاء حتى لو صفر."""
    return {key: _positive(item.get(key)) for key in MEAL_KEYS}


def meal_sum(item):
    """مجموع فطار + غداء + عشاء إن وُجد كلٌّ منها."""
    return sum(meal_parts(item).values())


def applied_meals(orig, over):
    """مخصص التأميدة على الوجبات؛ كمية يومية تُوزَّع على الوجبات الأصلية."""
    orig = {key: _positive(orig.get(key)) for key in MEAL_KEYS}
    if not over:
        return dict(orig), False
    if any(over.get(key) not in (None, "") for key in MEAL_KEYS):
        used = {}
        for key in MEAL_KEYS:
            if over.get(key) not in (None, ""):
                used[key] = _positive(over.get(key))
            else:
                used[key] = orig[key]
        return used, True
    if not over.get("on", True):
        return {key: 0.0 for key in MEAL_KEYS}, True
    if "qty" not in over:
        return dict(orig), True
    qty = _positive(over.get("qty"))
    total = sum(orig.values())
    if total > 0:
        return {key: qty * orig[key] / total for key in MEAL_KEYS}, True
    return {"breakfast": qty, "lunch": 0.0, "dinner": 0.0}, True


def daily_qty(item, weekday):
    """مقرر الفرد لهذا اليوم من الأسبوع (0=سبت). بلا صرف = ٠."""
    if item.get("is_custom"):
        if weekday not in item.get("days", []):
            return 0.0
        qty = item.get("day_qty", {}).get(weekday)
        if qty not in (None, ""):
            return _positive(qty)
        return meal_sum(item)
    custom = item.get("custom") or []
    if custom:
        total = 0.0
        for entry in custom:
            if int(entry.get("weekday", -1)) == weekday:
                total += _positive(entry.get("qty"))
        return total
    return meal_sum(item)


def items_for_entity(year, month, entity_name, section):
    """أصناف توزيع الجهة إن وُجدت، وإلا المقرر المفعّل في القسم."""
    name = " ".join((entity_name or "").split())
    for entity in de.list_entities(year, month, section):
        if " ".join((entity.get("name") or "").split()) == name:
            return entity.get("items") or []
    kind = dr.get_activation(year, month, section) or "summer"
    rows, custom = dr.get_items(year, month, section, kind)
    for row in rows:
        row["custom"] = custom.get(row["id"], [])
        row["is_custom"] = bool(row["custom"])
    return rows


def build_lines(year, month, entity_name, section, day_from, day_to, overrides=None):
    """أسطر (يوم × صنف) لمدة التأميدة. overrides: {name|day: {qty, on}}."""
    overrides = overrides or {}
    last = egtime.days_in_month(year, month)
    day_from = max(1, min(int(day_from), last))
    day_to = max(day_from, min(int(day_to), last))
    items = items_for_entity(year, month, entity_name, section)
    lines = []
    for day in range(day_from, day_to + 1):
        when = date(year, month, day)
        weekday = egtime.weekday_sat0(when)
        for item in items:
            name = item.get("name") or ""
            base = daily_qty(item, weekday)
            key = f"{name}|{day}"
            over = overrides.get(key) or {}
            qty = over["qty"] if "qty" in over else base
            on = over["on"] if "on" in over else (base > 0)
            orig = meal_parts(item)
            used, customized = applied_meals(orig, over if over else None)
            lines.append({
                "name": name, "unit": item.get("unit") or "",
                "day": day, "weekday": DAYS[weekday],
                "qty": _positive(qty) if on else 0.0, "on": bool(on),
                "base": base, "orig": orig, "used": used,
                "customized": customized,
            })
    return lines


def overrides_map(payload, target, section):
    """payload[target][section] → خريطة name|day."""
    block = ((payload or {}).get(target) or {}).get(section) or []
    out = {}
    for row in block:
        name = row.get("name") or ""
        day = int(row.get("day") or 0)
        if not name or not day:
            continue
        cell = {"qty": row.get("qty"), "on": row.get("on", True)}
        for key in MEAL_KEYS:
            if row.get(key) not in (None, ""):
                cell[key] = row.get(key)
        out[f"{name}|{day}"] = cell
    return out
