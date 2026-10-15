# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""📉 الاستهلاك والتغطية — متوسط الصرف اليومي، وأيام التغطية، ومتوقع النفاد.

متوسط اليوم = المنصرف ÷ الأيام المنقضية (حتى اليوم في الشهر الجاري، والشهر كله للفائت).
أيام التغطية = الرصيد ÷ متوسط اليوم — لكل صنف بمعدله الإجمالي، ولكل مخزن بمعدله هو
(تصحيح الخطأ ٣ القديم: رصيد مخزن واحد كان يُقسم على صرف كل المخازن).
"""
from ..calc import (EPS, card, cell, cover_class, coverage_days, daily_rate, month_name, n, norm,
                    q, qz, runout_date, table)

STATUS = {"bad": "خطر", "warn": "تحذير", "ok": "كافٍ"}


def _status(closing, issued, days):
    if issued <= EPS:
        return cell("بلا صرف")
    if closing <= EPS:
        return cell("نفد", "bad")
    cls = cover_class(days)
    return cell(STATUS.get(cls, ""), cls)


def _cover_cells(ctx, closing, issued):
    days = coverage_days(closing, issued, ctx.elapsed())
    rate = daily_rate(issued, ctx.elapsed())
    return [cell(q(issued), "st-out"), q(rate), cell(qz(closing), "b"),
            cell(n(int(days)) if days is not None else "", cover_class(days)),
            cell(runout_date(ctx.ref(), days), cover_class(days), "date"),
            _status(closing, issued, days)], days


def badge(ctx):
    return sum(1 for key in ctx.keys() if key[0] and cover_class(ctx.cover_store(key)) == "bad")


def build(ctx):
    items = ctx.item_keys()
    rows, levels = [], {"bad": 0, "warn": 0, "out": 0}
    for (item, unit), e in sorted(items.items()):
        cells, days = _cover_cells(ctx, e["closing"], e["out"])
        rows.append(norm([cell(item, "b", "item"), unit] + cells))
        if e["out"] > EPS and e["closing"] <= EPS:
            levels["out"] += 1
        elif cover_class(days) in ("bad", "warn"):
            levels[cover_class(days)] += 1
    issued = sum(1 for e in items.values() if e["out"] > EPS)
    cards = [
        card("أصناف منصرفة", n(issued), "", "", "📤"),
        card("تغطية أقل من ٧ أيام", n(levels["bad"]), "", "bad" if levels["bad"] else "good", "🔴"),
        card("تغطية أقل من ١٤ يوم", n(levels["warn"]), "", "warn" if levels["warn"] else "good",
             "🟠"),
        card("نفد رصيدها", n(levels["out"]), "", "bad" if levels["out"] else "good", "⛔"),
        card("الأيام المحسوبة", n(ctx.elapsed()), "", "", "🗓️"),
    ]
    head = ["الصنف", "الوحدة", "المنصرف", "متوسط اليوم", "الرصيد", "أيام التغطية",
            "متوقع النفاد", "الحالة"]
    tables = [table("by_item", "الاستهلاك والتغطية", head, rows), _by_store(ctx), _top(ctx)]
    if ctx.yearly:
        tables.append(_monthly(ctx))
    return {"cards": cards, "tables": tables}


def _by_store(ctx):
    order = {t["id"]: i for i, t in enumerate(ctx.targets())}
    rows = []
    for (sid, item, unit), e in sorted(ctx.keys().items(),
                                       key=lambda kv: (order.get(kv[0][0], 99), kv[0][1])):
        if e["out"] <= EPS and e["closing"] <= EPS:
            continue
        cells, _days = _cover_cells(ctx, e["closing"], e["out"])
        rows.append(norm([cell(e["store"], "", "store"), cell(item, "b", "item"), unit] + cells))
    head = ["المخزن", "الصنف", "الوحدة", "المنصرف", "متوسط اليوم", "الرصيد", "أيام التغطية",
            "متوقع النفاد", "الحالة"]
    return table("by_store", "بالمخزن", head, rows)


def _top(ctx):
    items = sorted(((k, e) for k, e in ctx.item_keys().items() if e["out"] > EPS),
                   key=lambda kv: (-kv[1]["out"], kv[0][0]))[:10]
    rows = []
    for i, ((item, unit), e) in enumerate(items, start=1):
        days = coverage_days(e["closing"], e["out"], ctx.elapsed())
        rows.append(norm([n(i), cell(item, "b", "item"), unit, cell(q(e["out"]), "st-out"),
                          q(daily_rate(e["out"], ctx.elapsed())),
                          cell(n(int(days)) if days is not None else "", cover_class(days))]))
    return table("top", "أعلى ١٠ أصناف",
                 ["م", "الصنف", "الوحدة", "المنصرف", "متوسط اليوم", "أيام التغطية"], rows)


def _monthly(ctx):
    months = ctx.yf()["months"]
    span = list(range(1, (months[-1] if months else 0) + 1))
    rows = []
    for (item, unit), e in sorted(ctx.item_keys().items()):
        if e["out"] <= EPS:
            continue
        values = {m: e["months"].get(m, {}).get("out", 0.0) for m in span}
        busiest = max(values, key=lambda m: values[m]) if values else None
        average = e["out"] / len(months) if months else 0.0
        rows.append(norm([cell(item, "b", "item"), unit]
                         + [cell(q(values[m]), "st-out") for m in span]
                         + [q(average), month_name(busiest) if busiest else ""]))
    head = ["الصنف", "الوحدة"] + [month_name(m) for m in span] + ["متوسط الشهر", "أكثر شهر"]
    return table("monthly", "الاستهلاك الشهري", head, rows)
