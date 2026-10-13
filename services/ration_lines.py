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


def _spread_qty(qty, meals):
    """مجموع اليوم (سلوك قديم) → توزيعه على الوجبات العامة بنسبتها."""
    q = _positive(qty)
    total = sum(meals.values())
    if total > 0:
        return {key: q * meals[key] / total for key in MEAL_KEYS}
    return {"breakfast": q, "lunch": 0.0, "dinner": 0.0}


def daily_meals(item, weekday):
    """مقرر الفرد لهذا اليوم بوجباته {فطار، غداء، عشاء} — بلا صرف = كلها ٠.

    - صنف بأيام محددة (تخصيص الجهة) = يُصرف في أيامه فقط:
      * لو ليومها وجبات مخصصة (day_meals) → هي اللي بتتصرف.
      * لو رقم واحد قديم (day_qty) → بيتوزع على الوجبات العامة.
      * لو مفيش حاجة → الوجبات العامة.
    - صنف بمخصص أيام (custom من المقرر) = مجموع مخصصاته للأيام بتتوزع.
    - غير ذلك = القاعدة اليومية (فطار+غداء+عشاء).
    """
    meals = meal_parts(item)
    if item.get("days"):
        if weekday not in item["days"]:
            return {key: 0.0 for key in MEAL_KEYS}
        dm = (item.get("day_meals") or {}).get(weekday) or {}
        if dm:
            return {
                key: (_positive(dm[key]) if dm.get(key) not in (None, "")
                      else meals[key])
                for key in MEAL_KEYS
            }
        qty = (item.get("day_qty") or {}).get(weekday)
        if qty in (None, ""):
            return dict(meals)
        return _spread_qty(qty, meals)
    custom = item.get("custom") or []
    if custom:
        total = 0.0
        for entry in custom:
            if int(entry.get("weekday", -1)) == weekday:
                total += _positive(entry.get("qty"))
        if total <= 0:
            return {key: 0.0 for key in MEAL_KEYS}
        return _spread_qty(total, meals) if sum(meals.values()) > 0 \
            else {"breakfast": total, "lunch": 0.0, "dinner": 0.0}
    return dict(meals)


def daily_qty(item, weekday):
    """مقرر الفرد لهذا اليوم (مجموع الوجبات) — بلا صرف = ٠."""
    return sum(daily_meals(item, weekday).values())


def day_cell_values(item):
    """قيم عرض مربعات اليوم الثلاثة {0-6: {breakfast,lunch,dinner}} — ١٤/١٠.

    كل خلية = الوجبة الفعلية ليومها (المخصصة، أو الموزعة من رقم قديم،
    أو القيمة العامة). None/0 = المربع يظهر فاضي (يعني «على القيمة العامة»).
    """
    meals = meal_parts(item)
    out = {}
    for wd in range(7):
        if item.get("days") and wd in item["days"]:
            cell = daily_meals(item, wd)
            out[wd] = {k: (v or None) for k, v in cell.items()}
        else:
            out[wd] = {k: (meals[k] or None) for k in MEAL_KEYS}
    return out


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
            base_meals = daily_meals(item, weekday)   # ١٤/١٠: وجبات اليوم الفعلية
            base = sum(base_meals.values())
            key = f"{name}|{day}"
            over = overrides.get(key) or {}
            qty = over["qty"] if "qty" in over else base
            on = over["on"] if "on" in over else (base > 0)
            used, customized = applied_meals(base_meals, over if over else None)
            lines.append({
                "name": name, "unit": item.get("unit") or "",
                "day": day, "weekday": DAYS[weekday],
                "qty": _positive(qty) if on else 0.0, "on": bool(on),
                "base": base, "orig": base_meals, "used": used,
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
