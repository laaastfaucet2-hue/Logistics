# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""📈 المقارنة والاتجاه — الفترة الحالية مقابل السابقة (ونفس الشهر من السنة السابقة).

نفس مؤشرات «الملخص العام» (مصدر واحد)، والسنوي يضيف الاتجاه الشهري: كل مؤشر وكل مخزن
على شهور السنة جنبًا إلى جنب.
"""
from ..calc import card, cell, change_class, month_name, n, norm, pct_change, qz, table
from .summary import indicator_list

CARD_KEYS = ("إذون الإضافة", "إذون الصرف", "سطور المنصرف", "الجهات المستلمة")


def build(ctx):
    cur, prev = ctx.metrics(), ctx.prev_metrics()
    periods = [cur, prev] if ctx.yearly else [cur, prev, ctx.last_year_metrics()]
    indicators = indicator_list(ctx, periods)
    prev_label = "السنة السابقة" if ctx.yearly else "الشهر السابق"
    rows = []
    for label, values, fmt, up_bad in indicators:
        now, before = values[0], values[1]
        cells = [cell(label, "b"), fmt(now), fmt(before) if before is not None else ""]
        if not ctx.yearly:
            cells.append(fmt(values[2]) if values[2] is not None else "")
        cells.append(cell(pct_change(now, before), change_class(now, before, up_bad)))
        rows.append(norm(cells))
    head = (["المؤشر", "هذه السنة", "السنة السابقة", "نسبة التغير"] if ctx.yearly else
            ["المؤشر", "هذا الشهر", "الشهر السابق", "نفس الشهر من السنة السابقة", "نسبة التغير"])
    cards = []
    for label, values, fmt, up_bad in indicators:
        if label in CARD_KEYS:
            now, before = values[0], values[1]
            sub = f"{prev_label}: {fmt(before)}" if before is not None else ""
            change = pct_change(now, before)
            cards.append(card(label, fmt(now), f"{sub} ({change})" if change else sub,
                              change_class(now, before, up_bad)))
    tables = [table("indicators", "مقارنة المؤشرات", head, rows)]
    if ctx.yearly:
        tables.append(_trend(ctx, cur))
    return {"cards": cards, "tables": tables}


def _trend(ctx, cur):
    """الاتجاه الشهري: كل مؤشر وكل مخزن على شهور السنة (حتى آخر شهر فيه بيانات)."""
    months = ctx.yf()["months"]
    span = list(range(1, (months[-1] if months else 0) + 1))
    per = cur.get("per_month") or {}
    rows = []

    def add(label, getter, fmt=n):
        values = [getter(per[m]) if m in per else None for m in span]
        rows.append(norm([cell(label, "b")] + [fmt(v) if v is not None else "" for v in values]))

    add("إذون الإضافة", lambda m: m["receipts"])
    add("إذون الصرف", lambda m: m["permits"])
    add("سطور المنصرف", lambda m: m["out_lines"])
    add("الجهات المستلمة", lambda m: len(m["entities"]))
    add("الأصناف المتحركة", lambda m: len(m["moving"]))
    for label, name in (("الوارد", "in_units"), ("المنصرف", "out_units"), ("الرصيد", "bal_units")):
        units = set()
        for m in per.values():
            units |= set(m[name])
        for unit in sorted(units):
            add(f"{label} ({unit})", lambda m, u=unit, k=name: m[k].get(u, 0.0), qz)
    moves = {}
    for line in ctx.lines():
        if line["dir"] == "in" and line["opener"]:
            continue
        slot = moves.setdefault(line["store_id"], {})
        month = line.get("month", ctx.month)
        slot[month] = slot.get(month, 0) + 1
    for target in ctx.targets():
        counts = moves.get(target["id"])
        if counts is None and not target["id"]:
            continue
        values = [int((counts or {}).get(m, 0)) for m in span]
        rows.append(norm([cell(f"حركات {target['name']}", "", "store")]
                         + [n(v) if v else "" for v in values]))
    head = ["المؤشر"] + [month_name(m) for m in span]
    return table("trend", "الاتجاه الشهري", head, rows)
