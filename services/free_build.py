# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""حساب أسطر «٢ مخازن حرة» — بمعدلات التوزيع المستقلة + المخصصات.

قاعدة الحساب (توجيه ٠٨/١٠):
- معدل الفرد اليومى (قاعدة الفطار/غداء/عشاء) ينفذ كل يوم.
- تخصيصات أيام الأسبوع (المخصص) تُضاف فوقه في يومها.
- الكمية = المعدل × القوة × الأيام + مجموع المخصصات × القوة في أيامها.
- الصنف «مخصص الأيام» (أيام محددة في الجهة) يُصرف في أيامه فقط.
"""
from datetime import date

from core import egtime
from core.config import DAYS, MEALS
from data_access import db_tameedat as dt
from services import permit_build as pb
from services import ration_lines as rl

MEAL_LABELS = {k: l for k, l in MEALS}


def is_full_days(item):
    """صنف بأيام أسبوع محددة (من تخصيص الجهة) — صرف في أيامه فقط."""
    return bool(item.get("days"))


def custom_chips(item):
    """شارات المخصص للعرض: [{'label', 'qty', 'weekday'}]."""
    out = []
    if is_full_days(item):
        day_qty = item.get("day_qty") or {}
        for wd in sorted(int(w) for w in item.get("days") or []):
            q = day_qty.get(wd)
            out.append({"label": DAYS[wd] + ("" if q in (None, "") else " " + str(q)),
                        "qty": float(q or 0), "weekday": int(wd), "full": True})
        return out
    for entry in item.get("custom") or []:
        out.append({"label": DAYS[int(entry.get("weekday") or 0)] +
                    " " + MEAL_LABELS.get(entry.get("meal") or "", ""),
                    "qty": float(entry.get("qty") or 0),
                    "weekday": int(entry.get("weekday") or 0)})
    return out


def day_custom(item, weekday):
    """مخصص الصنف ليوم أسبوع (إضافة فوق القاعدة) — صفر للمخصص الأيام."""
    if is_full_days(item):
        return 0.0
    total = 0.0
    for entry in item.get("custom") or []:
        if int(entry.get("weekday", -1)) == weekday:
            total += float(entry.get("qty") or 0)
    return total


def seed_rate(item):
    """معدل البداية: القاعدة (فطار+غداء+عشاء) أو مخصص اليوم إن كان مخصص الأيام."""
    if is_full_days(item):
        vals = [float(v) for v in (item.get("day_qty") or {}).values()
                if v not in (None, "")]
        if vals:
            return max(set(vals), key=vals.count)
    return rl.meal_sum(item)


def rows_for_picks_free(year, month, picks, day_from, day_to, issue_days,
                        section, rates):
    """rows جاهزة للعرض — rate = معدل التوزيع الحر + مخصصات أيام الأسبوع."""
    if section not in ("tamween", "contractor"):
        return []
    grouped = {}
    rates = rates.get(section) or {}
    for pick in picks:
        rec = dt.get_record(year, month, pick["record_id"])
        if not rec:
            continue
        valid = pb.issued_days_for_rec(rec, day_from, day_to, issue_days)
        if not valid:
            continue
        force = int(pick.get("officers") or 0) + int(pick.get("individuals") or 0) \
            + int(pick.get("recruits") or 0)
        items = rl.items_for_entity(year, month, pick["name"], section)
        for item in items:
            name = " ".join((item.get("name") or "").split())
            if not name:
                continue
            g = grouped.setdefault(name, {
                "item": item, "unit": "", "days": set(),
                "day_forces": {}, "catalog_rate": 0.0})
            if item.get("unit") and not g["unit"]:
                g["unit"] = item["unit"]
            if not g["catalog_rate"]:
                g["catalog_rate"] = seed_rate(item)
            for day in valid:
                g["days"].add(day)
                g["day_forces"][day] = g["day_forces"].get(day, 0) + force
    rows = []
    for i, name in enumerate(sorted(grouped)):
        g = grouped[name]
        item = g["item"]
        free_rate = rates.get(name)
        rate = float(free_rate["rate"]) if free_rate else float(g["catalog_rate"])
        full_weekdays = [int(w) for w in (item.get("days") or [])] if is_full_days(item) \
            else None
        base_force_days = 0
        auto_custom = 0.0
        for day in g["days"]:
            wd = egtime.weekday_sat0(date(year, month, day))
            if full_weekdays is not None and wd not in full_weekdays:
                continue
            force_day = g["day_forces"][day]
            base_force_days += force_day
            auto_custom += force_day * day_custom(item, wd)
        auto = round(rate * base_force_days + auto_custom, 6)
        rows.append({
            "serial": i + 1, "name": name, "unit": g["unit"],
            "rate": rate, "days": len(g["days"]),
            "base_force_days": int(base_force_days),
            "auto_custom": round(auto_custom, 6),
            "auto": auto, "actual": auto,
            "custom": custom_chips(item)})
    return rows


def all_rows_for_picks(year, month, picks, day_from, day_to, issue_days, rates):
    """{tamween: rows, contractor: rows} — للدفع للواجهة."""
    return {sec: rows_for_picks_free(year, month, picks, day_from, day_to,
                                     issue_days, sec, rates)
            for sec in ("tamween", "contractor")}


def catalog_rows(year, month, section, rates):
    """كل أصناف القسم (لتاب «معدلات التوزيع» داخل الحرة)."""
    if section not in ("tamween", "contractor"):
        return []
    from data_access import db_rations as dr
    kind = dr.get_activation(year, month, section) or "summer"
    rows, custom = dr.get_items(year, month, section, kind)
    rates = rates.get(section) or {}
    out = []
    for i, item in enumerate(rows):
        name = " ".join((item.get("name") or "").split())
        if not name:
            continue
        item = dict(item)
        item["custom"] = custom.get(item.get("id"), [])
        item["is_custom"] = bool(item["custom"])
        free = rates.get(name)
        seed = seed_rate(item)
        out.append({
            "serial": i + 1, "name": name, "unit": item.get("unit") or "",
            "base": rl.meal_sum(item), "seed": seed,
            "rate": float(free["rate"]) if free else float(seed),
            "custom": custom_chips(item),
            "has_free": bool(free)})
    return out
