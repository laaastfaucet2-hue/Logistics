# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""🔄 حركة الوارد والمنصرف — بالمخزن · بالصنف · باليوم (بالشهر في السنوي) · بالمورد والمنتج.

الوارد = إذون الإضافة (رصيد أول المدة ليس حركة — مكانه أرصدة المخازن)، والمنصرف = سطور
التفريدة من إذون ٢ مخازن. الكميات بوحدتها دائمًا (لا جمع كجم على لتر).
"""
from ..calc import (EPS, add_unit, card, cell, d, month_name, n, norm, table, unit_card,
                    units_text)

HEAD = ["عدد إذون الوارد", "كمية الوارد", "عدد سطور المنصرف", "كمية المنصرف", "الصافي"]


def _moves(ctx):
    """سطور الحركة فقط (بلا أول المدة) + مفتاح الإذن فريد على مستوى السنة."""
    out = []
    for line in ctx.lines():
        if line["dir"] == "in" and line["opener"]:
            continue
        month = line.get("month", ctx.month)
        key = (month, line["cycle"], line["serial"]) if line["dir"] == "in" else None
        out.append((line, key))
    return out


def _group(moves, key_fn):
    groups = {}
    for line, rkey in moves:
        g = groups.setdefault(key_fn(line), {"receipts": set(), "in": {}, "out_n": 0, "out": {}})
        if line["dir"] == "in":
            g["receipts"].add(rkey)
            add_unit(g["in"], line["unit"], line["qty"])
        else:
            g["out_n"] += 1
            add_unit(g["out"], line["unit"], line["qty"])
    return groups


def _net(g):
    net = dict(g["in"])
    for unit, value in g["out"].items():
        add_unit(net, unit, -value)
    return net


def _cells(g):
    return [n(len(g["receipts"])), cell(units_text(g["in"]), "st-in"), n(g["out_n"]),
            cell(units_text(g["out"]), "st-out"), cell(units_text(_net(g)), "b")]


def build(ctx):
    moves = _moves(ctx)
    total = _group(moves, lambda line: "all").get("all", {"receipts": set(), "in": {},
                                                          "out_n": 0, "out": {}})
    dates = {line.get("month", ctx.month) if ctx.yearly else line["date"] for line, _k in moves}
    cards = [
        card("إذون الوارد", n(len(total["receipts"])), "", "", "📥"),
        card("سطور المنصرف", n(total["out_n"]), "", "", "📤"),
        unit_card("الوارد", total["in"], "⬇️"),
        unit_card("المنصرف", total["out"], "⬆️"),
        card("شهور الحركة" if ctx.yearly else "أيام الحركة", n(len(dates)), "", "", "🗓️"),
    ]
    tables = [_by_store(ctx, moves), _by_item(moves)]
    tables.append(_by_month(moves) if ctx.yearly else _by_day(moves))
    tables.append(_by_source(moves))
    return {"cards": cards, "tables": tables}


def _by_store(ctx, moves):
    groups = _group(moves, lambda line: line["store_id"])
    rows = []
    for target in ctx.targets():
        g = groups.get(target["id"])
        if not g:
            if target["id"]:
                rows.append(norm([cell(target["name"], "b", "store"), n(0), "", n(0), "", ""]))
            continue
        rows.append(norm([cell(target["name"], "b", "store")] + _cells(g)))
    return table("by_store", "بالمخزن", ["المخزن"] + HEAD, rows)


def _by_item(moves):
    groups = _group(moves, lambda line: (line["item"], line["unit"]))
    rows = [norm([cell(item, "b", "item")] + _cells(groups[(item, unit)]))
            for item, unit in sorted(groups)]
    return table("by_item", "بالصنف", ["الصنف"] + HEAD, rows)


def _by_day(moves):
    groups = _group(moves, lambda line: line["date"])
    rows = [norm([cell(d(day), "", "date")] + _cells(groups[day])) for day in sorted(groups) if day]
    return table("by_day", "باليوم", ["اليوم"] + HEAD, rows)


def _by_month(moves):
    groups = _group(moves, lambda line: line.get("month", 0))
    rows = [norm([cell(month_name(m), "b")] + _cells(groups[m])) for m in sorted(groups) if m]
    return table("by_month", "بالشهر", ["الشهر"] + HEAD, rows)


def _by_source(moves):
    groups = {}
    for line, rkey in moves:
        if line["dir"] != "in":
            continue
        key = (line["supplier"], line["producer"], line["item"], line["unit"])
        g = groups.setdefault(key, {"receipts": set(), "qty": 0.0})
        g["receipts"].add(rkey)
        g["qty"] = round(g["qty"] + line["qty"], 6)
    rows = []
    for (supplier, producer, item, unit) in sorted(groups):
        g = groups[(supplier, producer, item, unit)]
        if g["qty"] <= EPS:
            continue
        rows.append(norm([supplier, producer, cell(item, "b", "item"), n(len(g["receipts"])),
                          cell(units_text({unit: g["qty"]}), "st-in")]))
    return table("by_source", "بالمورد والمنتج",
                 ["المورد", "المنتج", "الصنف", "عدد إذون الوارد", "كمية الوارد"], rows)
