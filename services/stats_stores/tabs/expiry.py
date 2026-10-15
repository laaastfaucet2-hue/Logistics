# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""⏳ الصلاحيات — الدفعات اللي فيها رصيد فعلًا بعد التفريدة (ومعها رصيد أول المدة).

الحالات: منتهية < ٠ · خطر ٠–٣٠ · قربت ٣١–٩٠ · سليمة > ٩٠ · بدون تاريخ.
الأيام حتى اليوم في الشهر الجاري، وحتى آخر يوم في الشهور الفائتة (ملف سبتمبر ثابت).
السنوي: دفعات آخر الفترة + ما انتهت صلاحيته خلال السنة وفيه رصيد (احتمال هالك).
"""
from ..calc import (EPS, LEVEL_CLASS, LEVEL_LABEL, LEVELS, add_unit, card, cell, d, days_left,
                    level, month_name, n, norm, q, table, units_text)

HEAD = ["المخزن", "الصنف", "المصدر", "المورد", "المنتج", "تاريخ الإنتاج", "تاريخ الصلاحية",
        "الأيام الباقية", "الكمية الباقية", "الحالة"]


def source(batch):
    return "رصيد أول المدة" if batch["opener"] else f"إذن إضافة {n(batch['serial'])}"


def _sort_key(batch):
    return (batch["expiry"] or "9999-12-31", batch["store"], batch["item"])


def badge(ctx):
    ref = ctx.ref()
    return sum(1 for b in ctx.live_batches() if level(b["expiry"], ref) in ("expired", "danger"))


def build(ctx):
    ref = ctx.ref()
    live = sorted(ctx.live_batches(), key=_sort_key)
    counts = {lvl: 0 for lvl in LEVELS}
    qty = {lvl: {} for lvl in LEVELS}
    rows = []
    for b in live:
        lvl = level(b["expiry"], ref)
        counts[lvl] += 1
        add_unit(qty[lvl], b["unit"], b["remaining"])
        left = days_left(b["expiry"], ref)
        rows.append(norm([
            cell(b["store"], "", "store"), cell(b["item"], "b", "item"), source(b),
            b["supplier"], b["producer"], cell(d(b["prod_date"]), "", "date"),
            cell(d(b["expiry"]), LEVEL_CLASS[lvl], "date"),
            n(left) if left is not None else "",
            f"{q(b['remaining'])} {b['unit']}".strip(),
            cell(LEVEL_LABEL[lvl], LEVEL_CLASS[lvl]),
        ]))
    cards = [card(LEVEL_LABEL[lvl], n(counts[lvl]), units_text(qty[lvl]),
                  LEVEL_CLASS[lvl] if counts[lvl] else ("good" if lvl in ("expired", "danger") else ""))
             for lvl in LEVELS]
    summary = [norm([cell(LEVEL_LABEL[lvl], LEVEL_CLASS[lvl]), n(counts[lvl]),
                     units_text(qty[lvl])]) for lvl in LEVELS]
    tables = [table("levels", "ملخص الحالات", ["الحالة", "عدد الدفعات", "الكمية الباقية"], summary),
              table("batches", "الدفعات الباقية", HEAD, rows)]
    if ctx.yearly:
        tables.append(_expired_in_year(ctx))
    return {"cards": cards, "tables": tables}


def _expired_in_year(ctx):
    """دفعات انتهت صلاحيتها خلال السنة وفيها رصيد في آخر شهرها — آخر ظهور لكل دفعة."""
    yf = ctx.yf()
    found = {}
    for month in yf["months"]:
        facts = yf["facts"][month]
        for b in facts["batches"]:
            if b["remaining"] <= EPS or level(b["expiry"], facts["ref"]) != "expired":
                continue
            key = (b["store_id"], b["cycle"], b["item"], b["serial"], b["expiry"])
            found[key] = (month, b)
    rows = []
    for month, b in sorted(found.values(), key=lambda mb: (mb[1]["expiry"], mb[1]["store"])):
        rows.append(norm([cell(b["store"], "", "store"), cell(b["item"], "b", "item"), source(b),
                          cell(d(b["expiry"]), "bad", "date"), month_name(month),
                          f"{q(b['remaining'])} {b['unit']}".strip()]))
    return table("expired_year", "انتهت خلال السنة",
                 ["المخزن", "الصنف", "المصدر", "تاريخ الصلاحية", "آخر شهر", "الكمية الباقية"], rows)
