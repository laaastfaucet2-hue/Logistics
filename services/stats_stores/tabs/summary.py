# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""📊 الملخص العام — كروت الموقف + المؤشرات مقارنة بالفترة السابقة + موقف المخازن
+ أعلى الأصناف استهلاكًا + أهم التنبيهات (+ أنشط الشهور في السنوي)."""
from ..calc import (EPS, card, cell, change_class, cover_class, expiry_cell, month_name, n, norm,
                    pct_change, q, qz, table, units_text)
from . import alerts


def build(ctx):
    cur = ctx.metrics()
    prev = ctx.prev_metrics()
    view = {"cards": _cards(ctx, cur), "tables": []}
    view["tables"].append(_indicators(ctx, cur, prev))
    view["tables"].append(_stores(ctx))
    view["tables"].append(_top(ctx))
    view["tables"].append(_alerts(ctx))
    if ctx.yearly:
        view["tables"].append(_months(ctx, cur))
    return view


def _cover_bad(ctx):
    return sum(1 for key in ctx.keys() if cover_class(ctx.cover_store(key)) == "bad")


def _cards(ctx, cur):
    risky = cur["expired"] + cur["danger"]
    bad_cover = _cover_bad(ctx)
    return [
        card("المخازن", n(len(ctx.stores())),
             f"بها رصيد: {n(len(cur['stores_with_balance']))}", "", "🏬"),
        card("أصناف بالرصيد", n(len(cur["with_balance"])), "", "", "📦"),
        card("إذون الإضافة", n(cur["receipts"]), "", "", "📥"),
        card("إذون الصرف", n(cur["permits"]), f"{n(cur['out_lines'])} سطر", "", "📤"),
        card("الجهات المستلمة", n(len(cur["entities"])), "", "", "🏢"),
        card("منتهية / خطر", n(risky), f"منتهية: {n(cur['expired'])}",
             "bad" if risky else "good", "⏳"),
        card("تغطية أقل من ٧ أيام", n(bad_cover), "", "bad" if bad_cover else "good", "📉"),
        card("غير موزع", n(len(cur["unassigned"])), "",
             "warn" if cur["unassigned"] else "good", "⚠️"),
    ]


def indicator_list(ctx, periods):
    """المؤشرات بالترتيب: [(البيان، [قيمة كل فترة]، التنسيق، الزيادة سيئة؟)] — None = لا فترة."""
    def size(m, name):
        return None if m is None else len(m[name])

    def value(m, name):
        return None if m is None else m[name]

    out = [("المخازن", [len(ctx.stores())] + [None] * (len(periods) - 1), n, False)]
    for label, name, fn in (("أصناف بالرصيد", "with_balance", size),
                            ("الأصناف المتحركة", "moving", size),
                            ("إذون الإضافة", "receipts", value), ("إذون الصرف", "permits", value),
                            ("سطور المنصرف", "out_lines", value),
                            ("الجهات المستلمة", "entities", size)):
        out.append((label, [fn(m, name) for m in periods], n, False))
    for label, name in (("الوارد", "in_units"), ("المنصرف", "out_units"), ("الرصيد", "bal_units")):
        units = set()
        for m in periods:
            units |= set(m[name]) if m else set()
        for unit in sorted(units):
            out.append((f"{label} ({unit})" if unit else label,
                        [m[name].get(unit, 0.0) if m else None for m in periods], qz, False))
    out.append(("دفعات منتهية", [value(m, "expired") for m in periods], n, True))
    out.append(("دفعات خطر (٣٠ يوم)", [value(m, "danger") for m in periods], n, True))
    out.append(("أصناف غير موزعة", [size(m, "unassigned") for m in periods], n, True))
    return out


def _indicators(ctx, cur, prev):
    rows = []
    for label, (now, before), fmt, up_bad in indicator_list(ctx, [cur, prev]):
        rows.append(norm([cell(label, "b"), fmt(now),
                          fmt(before) if before is not None else "",
                          cell(pct_change(now, before), change_class(now, before, up_bad))]))
    head = ["البيان", "القيمة", "السنة السابقة" if ctx.yearly else "الشهر السابق", "نسبة التغير"]
    return table("indicators", "المؤشرات", head, rows)


def _stores(ctx):
    keys = ctx.keys()
    rows = []
    for target in ctx.targets():
        sid = target["id"]
        mine = {k: e for k, e in keys.items() if k[0] == sid}
        if sid == 0 and not mine:
            continue
        balance = {}
        for (_s, _item, unit), e in mine.items():
            if e["closing"] > EPS:
                balance[unit] = round(balance.get(unit, 0.0) + e["closing"], 6)
        rows.append(norm([
            cell(target["name"], "b", "store"),
            n(sum(1 for e in mine.values() if e["closing"] > EPS)),
            n(sum(e["in_n"] for e in mine.values())),
            n(sum(e["out_n"] for e in mine.values())),
            units_text(balance),
            expiry_cell(ctx.nearest_expiry(sid=sid), ctx.ref()),
        ]))
    head = ["المخزن", "أصناف بالرصيد", "حركات الوارد", "حركات المنصرف", "الرصيد", "أقرب صلاحية"]
    return table("stores", "موقف المخازن", head, rows)


def _top(ctx):
    items = sorted(((key, e) for key, e in ctx.item_keys().items() if e["out"] > EPS),
                   key=lambda kv: (-kv[1]["out"], kv[0][0]))[:5]
    rows = [norm([n(i), cell(item, "b", "item"), unit, cell(q(e["out"]), "st-out"),
                  n(e["out_n"])])
            for i, ((item, unit), e) in enumerate(items, start=1)]
    return table("top", "أعلى الأصناف استهلاكًا",
                 ["م", "الصنف", "الوحدة", "المنصرف", "سطور المنصرف"], rows)


def _alerts(ctx):
    rows = [norm([cell(a["kind"], a["cls"]), cell(a["store"], "", "store"),
                  cell(a["item"], "", "item"), a["details"]])
            for a in alerts.collect(ctx)[:5]]
    return table("top_alerts", "أهم التنبيهات", ["نوع التنبيه", "المخزن", "الصنف", "التفاصيل"],
                 rows)


def _months(ctx, cur):
    per = cur.get("per_month") or {}
    ordered = sorted(per.items(), key=lambda kv: (-(kv[1]["in_lines"] + kv[1]["out_lines"]),
                                                  kv[0]))
    rows = [norm([cell(month_name(m), "b"), n(m_["in_lines"] + m_["out_lines"]),
                  n(m_["receipts"]), n(m_["permits"]), n(m_["out_lines"]),
                  n(len(m_["moving"]))])
            for m, m_ in ordered]
    return table("months", "أنشط الشهور",
                 ["الشهر", "الحركات", "إذون الإضافة", "إذون الصرف", "سطور المنصرف",
                  "الأصناف المتحركة"], rows)
