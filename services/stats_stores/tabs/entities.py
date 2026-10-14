# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""🏢 الجهات المستلمة — من إذون الصرف (٢ مخازن) كما خرجت فعلًا من المخازن (التفريدة).

الجهة الرئيسية والملحقة تُقسَّم بنفس دالة البرنامج (split_entity_label) في العدّ والتلوين،
والكميات بوحدتها دائمًا. السنوي يضيف عدد إذون كل جهة في كل شهر.
"""
from ..calc import add_unit, card, cell, d, month_name, n, norm, table, units_text
from ..year import entity_names


def _outs(ctx):
    return [line for line in ctx.lines() if line["dir"] == "out"]


def _permit_key(ctx, line):
    return (line.get("month", ctx.month), line["permit"])


def build(ctx):
    outs = _outs(ctx)
    groups = {}
    for line in outs:
        g = groups.setdefault(line["entity"], {"permits": set(), "items": set(), "qty": {},
                                               "stores": [], "last": "", "months": {}})
        g["permits"].add(_permit_key(ctx, line))
        g["items"].add((line["item"], line["unit"]))
        add_unit(g["qty"], line["unit"], line["qty"])
        if line["store"] not in g["stores"]:
            g["stores"].append(line["store"])
        g["last"] = max(g["last"], line["date"])
        g["months"].setdefault(line.get("month", ctx.month), set()).add(line["permit"])
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]["permits"]), kv[0]))
    rows = [norm([cell(label, "", "entity"), n(len(g["permits"])), n(len(g["items"])),
                  cell(units_text(g["qty"]), "st-out"), "، ".join(g["stores"]),
                  cell(d(g["last"]), "", "date")])
            for label, g in ordered]
    top = ordered[0] if ordered else None
    cards = [
        card("الجهات", n(len(entity_names(outs))), "", "", "🏢"),
        card("إذون الصرف", n(len({_permit_key(ctx, l) for l in outs})), "", "", "📤"),
        card("سطور المنصرف", n(len(outs)), "", "", "🧾"),
        card("إذون الأكثر استلامًا", n(len(top[1]["permits"])) if top else n(0),
             top[0] if top else "", "", "🏆"),
    ]
    tables = [table("by_entity", "بالجهة", ["الجهة", "عدد الإذون", "عدد الأصناف", "الكميات",
                                            "المخازن", "آخر صرف"], rows),
              _entity_item(ctx, outs), _store_entity(ctx, outs)]
    if ctx.yearly:
        tables.append(_entity_month(ctx, ordered))
    return {"cards": cards, "tables": tables}


def _entity_item(ctx, outs):
    groups = {}
    for line in outs:
        g = groups.setdefault((line["entity"], line["item"], line["unit"]),
                              {"permits": set(), "qty": 0.0})
        g["permits"].add(_permit_key(ctx, line))
        g["qty"] = round(g["qty"] + line["qty"], 6)
    rows = [norm([cell(entity, "", "entity"), cell(item, "b", "item"), unit,
                  n(len(groups[(entity, item, unit)]["permits"])),
                  cell(units_text({unit: groups[(entity, item, unit)]["qty"]}), "st-out")])
            for entity, item, unit in sorted(groups)]
    return table("entity_item", "الجهة والصنف",
                 ["الجهة", "الصنف", "الوحدة", "عدد الإذون", "الكمية"], rows)


def _store_entity(ctx, outs):
    order = {t["id"]: i for i, t in enumerate(ctx.targets())}
    groups = {}
    for line in outs:
        g = groups.setdefault((line["store_id"], line["entity"]),
                              {"store": line["store"], "permits": set(), "qty": {}})
        g["permits"].add(_permit_key(ctx, line))
        add_unit(g["qty"], line["unit"], line["qty"])
    rows = [norm([cell(g["store"], "", "store"), cell(entity, "", "entity"),
                  n(len(g["permits"])), cell(units_text(g["qty"]), "st-out")])
            for (sid, entity), g in sorted(groups.items(),
                                           key=lambda kv: (order.get(kv[0][0], 99), kv[0][1]))]
    return table("store_entity", "المخزن والجهة", ["المخزن", "الجهة", "عدد الإذون", "الكميات"],
                 rows)


def _entity_month(ctx, ordered):
    months = ctx.yf()["months"]
    span = list(range(1, (months[-1] if months else 0) + 1))
    rows = []
    for label, g in ordered:
        counts = [len(g["months"].get(m, ())) for m in span]
        rows.append(norm([cell(label, "", "entity")] + [n(c) if c else "" for c in counts]
                         + [cell(n(sum(counts)), "b")]))
    head = ["الجهة"] + [month_name(m) for m in span] + ["الإجمالي"]
    return table("entity_month", "الجهة في كل شهر", head, rows)
