# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""🏬 المخازن والتجهيزات — بيانات كل مخزن من سجل المخازن + حركته في الفترة.

البيان الناقص يظهر «—» ويُحسب في كارت «بيانات ناقصة» وفي تبويب التنبيهات. السنوي يضيف
عدد حركات كل مخزن في كل شهر وعدد الشهور التي كانت فيها حركة.
"""
from core import arabic_numbers as arnum

from ..calc import EPS, card, cell, d, month_name, n, norm, table
from .alerts import REGISTRY_FIELDS

HEAD = ["المخزن", "المكان", "المساحة (م²)", "المراوح", "الشفاطات", "التجهيزات",
        "أصناف بها رصيد", "حركات الوارد", "حركات المنصرف", "آخر حركة", "ملاحظات"]


def _number(value):
    if value in (None, ""):
        return ""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    return arnum.to_arabic_indic(f"{value:g}")


def _missing(store):
    return [label for field, label in REGISTRY_FIELDS
            if store.get(field) in (None, "") or str(store.get(field)).strip() == ""]


def _activity(ctx):
    """لكل مخزن: حركات الوارد/المنصرف وآخر تاريخ حركة والشهور (بلا رصيد أول المدة)."""
    out = {}
    for line in ctx.lines():
        if line["dir"] == "in" and line["opener"]:
            continue
        a = out.setdefault(line["store_id"], {"in": 0, "out": 0, "last": "", "months": {}})
        a["in" if line["dir"] == "in" else "out"] += 1
        a["last"] = max(a["last"], line["date"])
        month = line.get("month", ctx.month)
        a["months"][month] = a["months"].get(month, 0) + 1
    return out


def build(ctx):
    activity = _activity(ctx)
    keys = ctx.keys()
    rows, idle, incomplete, with_balance = [], 0, 0, 0
    for store in ctx.stores():
        sid = store["id"]
        a = activity.get(sid, {"in": 0, "out": 0, "last": ""})
        items = sum(1 for k, e in keys.items() if k[0] == sid and e["closing"] > EPS)
        idle += 0 if (a["in"] or a["out"]) else 1
        incomplete += 1 if _missing(store) else 0
        with_balance += 1 if items else 0
        rows.append(norm([
            cell(store["name"], "b", "store"), (store.get("location") or "").strip(),
            _number(store.get("capacity_m2")), _number(store.get("fans")),
            _number(store.get("extractors")), (store.get("equipment") or "").strip(),
            n(items), cell(n(a["in"]), "st-in" if a["in"] else ""),
            cell(n(a["out"]), "st-out" if a["out"] else ""), cell(d(a["last"]), "", "date"),
            (store.get("notes") or "").strip(),
        ]))
    cards = [
        card("المخازن", n(len(ctx.stores())), "", "", "🏬"),
        card("بها رصيد", n(with_balance), "", "", "📦"),
        card("بلا حركة", n(idle), "", "warn" if idle else "good", "💤"),
        card("بيانات ناقصة", n(incomplete), "", "warn" if incomplete else "good", "📝"),
    ]
    tables = [table("stores", "البيانات والحركة", HEAD, rows)]
    if ctx.yearly:
        tables.append(_monthly(ctx, activity))
    return {"cards": cards, "tables": tables}


def _monthly(ctx, activity):
    months = ctx.yf()["months"]
    span = list(range(1, (months[-1] if months else 0) + 1))
    rows = []
    for target in ctx.targets():
        a = activity.get(target["id"])
        if not a and not target["id"]:
            continue
        counts = [(a or {}).get("months", {}).get(m, 0) for m in span]
        rows.append(norm([cell(target["name"], "b", "store")]
                         + [n(c) if c else "" for c in counts]
                         + [n(sum(1 for c in counts if c)), cell(n(sum(counts)), "b")]))
    head = ["المخزن"] + [month_name(m) for m in span] + ["شهور بها حركة", "إجمالي الحركات"]
    return table("monthly", "الحركة الشهرية", head, rows)
