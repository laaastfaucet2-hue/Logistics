# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""🗃️ أرصدة المخازن — لكل صنف في كل مخزن: أول المدة + الوارد − المنصرف = الرصيد.

الشهري: الرصيد بالتغليف (من حالة العبوات) + أقرب صلاحية على الدفعات اللي فيها رصيد
فعلًا + متوقع النفاد بمعدل صرف المخزن نفسه (والإجمالي بمعدل الصنف كله).
السنوي: رصيد أول السنة · وارد ومنصرف السنة · فرق الترحيل · رصيد آخر الفترة
+ أنشط شهر صرف + جدول رصيد آخر كل شهر.
"""
from ..calc import (EPS, card, cell, cover_class, expiry_cell, month_name, n, norm, q, qz,
                    runout_date, table, unit_card)

HEAD_MONTH = ["م", "الصنف", "الوحدة", "رصيد أول المدة", "الوارد", "المنصرف", "الرصيد",
              "الرصيد بالتغليف", "أقرب صلاحية", "متوقع النفاد"]
HEAD_YEAR = ["م", "الصنف", "الوحدة", "رصيد أول السنة", "وارد السنة", "منصرف السنة",
             "فرق الترحيل", "رصيد آخر الفترة", "أنشط شهر صرف"]


def build(ctx):
    view = {"cards": _year_cards(ctx) if ctx.yearly else _month_cards(ctx), "tables": []}
    view["tables"].append(_total(ctx))
    for target in ctx.targets():
        if target["id"]:
            view["tables"].append(_store(ctx, target, f"store_{target['id']}", target["name"]))
    for target in ctx.targets():
        if not target["id"]:
            view["tables"].append(_store(ctx, target, "unassigned", "غير موزع"))
    if ctx.yearly:
        view["tables"].append(_month_end(ctx))
    return view


def badge(ctx):
    return sum(1 for e in ctx.item_keys().values() if e["closing"] > EPS)


# ---------------------------------------------------------------- الكروت
def _unit_card(label, totals, icon, cls=""):
    """الوحدة الأكثر أصنافًا أولًا والباقي تحتها — بلا جمع وحدتين أبدًا."""
    return unit_card(label, {u: v for u, (v, _c) in totals.items()}, icon, cls,
                     counts={u: c for u, (_v, c) in totals.items()})


def _totals(ctx, field):
    """الوحدة → (المجموع، عدد الأصناف)."""
    out = {}
    for (_item, unit), e in ctx.item_keys().items():
        value, count = out.get(unit, (0.0, 0))
        out[unit] = (round(value + e[field], 6), count + 1)
    return out


def _month_cards(ctx):
    keys = ctx.keys()
    covers = [cover_class(ctx.cover_store(k)) for k in keys]
    warn = covers.count("warn") + covers.count("bad")
    unassigned = sum(1 for k, e in keys.items() if not k[0] and e["closing"] > EPS)
    has_unassigned = any(not k[0] for k in keys)
    return [
        card("مخازن وثلاجات", n(len(ctx.stores())), "+ غير موزع" if has_unassigned else "",
             "", "🏬"),
        card("أصناف بالرصيد", n(badge(ctx)), "", "", "📦"),
        _unit_card("الرصيد حسب الوحدة", _totals(ctx, "closing"), "⚖️"),
        card("تغطية أقل من ١٤ يوم", n(warn), f"منها أقل من ٧: {n(covers.count('bad'))}",
             "bad" if covers.count("bad") else "warn" if warn else "good", "📉"),
        card("صنف برصيد غير موزع", n(unassigned), "", "warn" if unassigned else "good", "⚠️"),
    ]


def _year_cards(ctx):
    yf = ctx.yf()
    carries = sum(1 for e in ctx.keys().values() if abs(e["carry"]) > EPS)
    last = f" ({month_name(yf['last'])})" if yf["last"] else ""
    return [
        _unit_card("رصيد أول السنة", _totals(ctx, "opening"), "🗃️"),
        _unit_card("وارد السنة", _totals(ctx, "in"), "📥"),
        _unit_card("منصرف السنة", _totals(ctx, "out"), "📤"),
        _unit_card("رصيد آخر الفترة" + last, _totals(ctx, "closing"), "⚖️"),
        card("فروق الترحيل", n(carries), "", "warn" if carries else "good", "⚠️"),
    ]


# ---------------------------------------------------------------- الجداول
def _row(ctx, i, item, unit, e, pack, expiry, cover):
    if ctx.yearly:
        busiest = max(e["months"].items(), key=lambda kv: kv[1]["out"], default=None)
        busy = month_name(busiest[0]) if busiest and busiest[1]["out"] > EPS else ""
        return norm([n(i), cell(item, "b", "item"), unit, q(e["opening"]),
                     cell(q(e["in"]), "st-in"), cell(q(e["out"]), "st-out"),
                     cell(q(e["carry"]), "warn" if abs(e["carry"]) > EPS else ""),
                     cell(qz(e["closing"]), "b"), busy])
    return norm([n(i), cell(item, "b", "item"), unit, q(e["opening"]),
                 cell(q(e["in"]), "st-in"), cell(q(e["out"]), "st-out"),
                 cell(qz(e["closing"]), "b"), pack, expiry_cell(expiry, ctx.ref()),
                 cell(runout_date(ctx.ref(), cover), cover_class(cover), "date")])


def _foot(ctx, entries):
    units = {}
    for (_item, unit), e in entries:
        slot = units.setdefault(unit, {"opening": 0.0, "in": 0.0, "out": 0.0, "carry": 0.0,
                                       "closing": 0.0})
        for name in slot:
            slot[name] = round(slot[name] + e[name], 6)
    rows = []
    for unit in sorted(units):
        s = units[unit]
        if ctx.yearly:
            rows.append(norm(["", cell("الإجمالي", "b"), unit, q(s["opening"]), q(s["in"]),
                              q(s["out"]), q(s["carry"]), qz(s["closing"]), ""]))
        else:
            rows.append(norm(["", cell("الإجمالي", "b"), unit, q(s["opening"]), q(s["in"]),
                              q(s["out"]), qz(s["closing"]), "", "", ""]))
    return rows


def _head(ctx):
    return HEAD_YEAR if ctx.yearly else HEAD_MONTH


def _total(ctx):
    entries = sorted(ctx.item_keys().items(), key=lambda kv: kv[0])
    rows = [_row(ctx, i, item, unit, e, "", ctx.nearest_expiry(item=item, unit=unit),
                 ctx.cover_item((item, unit)))
            for i, ((item, unit), e) in enumerate(entries, start=1)]
    return table("total", "الإجمالي (كل المخازن)", _head(ctx), rows, _foot(ctx, entries))


def _store(ctx, target, key, title):
    sid = target["id"]
    packs = ctx.packs()
    entries = sorted((((k[1], k[2]), e) for k, e in ctx.keys().items() if k[0] == sid),
                     key=lambda kv: kv[0])
    rows = [_row(ctx, i, item, unit, e, packs.get((sid, item), "") if e["closing"] > EPS else "",
                 ctx.nearest_expiry(sid=sid, item=item, unit=unit),
                 ctx.cover_store((sid, item, unit)))
            for i, ((item, unit), e) in enumerate(entries, start=1)]
    count = sum(1 for _k, e in entries if e["closing"] > EPS)
    return table(key, title, _head(ctx), rows, _foot(ctx, entries), fold=True,
                 badge=f"{n(count)} صنف" if count else "",
                 badge_cls="warn" if not sid and count else "")


def _month_end(ctx):
    yf = ctx.yf()
    last = yf["last"] or 0
    months = list(range(1, last + 1))
    order = {t["id"]: i for i, t in enumerate(ctx.targets())}
    rows = []
    for (sid, item, unit), e in sorted(ctx.keys().items(),
                                       key=lambda kv: (order.get(kv[0][0], 99), kv[0][1])):
        cells = [cell(e["store"], "", "store"), cell(item, "b", "item"), unit]
        for m in months:
            cur = e["months"].get(m)
            cells.append(qz(cur["balance"]) if cur else "")
        rows.append(norm(cells))
    head = ["المخزن", "الصنف", "الوحدة"] + [month_name(m) for m in months]
    return table("month_end", "رصيد آخر كل شهر", head, rows)
