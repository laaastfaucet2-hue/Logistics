# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""🚨 التنبيهات وغير الموزع — كل ما يحتاج تصرفًا، مرتب بالأهمية.

المصادر: الدفعات الباقية (منتهية/خطر/بدون تاريخ) · الرصيد غير الموزع · عجز الصرف
· تغطية أقل من ٧ أيام · بيانات مخازن ناقصة — والسنوي يضيف فروق الترحيل بين الشهور.
"""
from ..calc import (EPS, LEVEL_CLASS, cell, cover_class, d, days_left, level, month_name, n,
                    norm, q, table)

REGISTRY_FIELDS = (("location", "المكان"), ("capacity_m2", "المساحة"), ("fans", "المراوح"),
                   ("extractors", "الشفاطات"), ("equipment", "التجهيزات"))


def _source(batch):
    return "رصيد أول المدة" if batch["opener"] else f"إذن إضافة {n(batch['serial'])}"


def collect(ctx):
    """قائمة التنبيهات: {kind, store, item, details, action, cls, rank}."""
    out = []
    ref = ctx.ref()
    for b in ctx.live_batches():
        lvl = level(b["expiry"], ref)
        qty = f"{q(b['remaining'])} {b['unit']}".strip()
        if lvl == "expired":
            out.append(_alert("صلاحية منتهية", b["store"], b["item"],
                              f"الباقي {qty} — انتهت {d(b['expiry'])}", "استبعاد الدفعة",
                              "bad", 0))
        elif lvl == "danger":
            left = days_left(b["expiry"], ref)
            out.append(_alert("صلاحية خلال ٣٠ يوم", b["store"], b["item"],
                              f"الباقي {qty} — تنتهي {d(b['expiry'])} ({n(left)} يوم)",
                              "صرفها أولًا", "bad", 1))
        elif lvl == "none":
            out.append(_alert("بدون تاريخ صلاحية", b["store"], b["item"],
                              f"الباقي {qty} — {_source(b)}", "استكمال التاريخ", "warn", 4))
    for s in ctx.shortfalls():
        when = f"{month_name(s['month'])} — " if s.get("month") else ""
        out.append(_alert("عجز في الصرف", "", s["item"],
                          f"{when}إذن {n(s['permit'])}: المطلوب {q(s['need'])} والمصروف "
                          f"{q(s['issued']) or n(0)} {s['unit']}".strip(),
                          "مراجعة الإذن", "bad", 1))
    for (sid, item, unit), e in ctx.keys().items():
        if not sid and e["closing"] > EPS:
            out.append(_alert("رصيد غير موزع", e["store"], item,
                              f"{q(e['closing'])} {unit}".strip(), "توزيعه على مخزن", "warn", 2))
        cover = ctx.cover_store((sid, item, unit))
        if sid and cover_class(cover) == "bad":
            out.append(_alert("تغطية أقل من ٧ أيام", e["store"], item,
                              f"الرصيد {q(e['closing'])} {unit} يكفي {n(int(cover))} يوم",
                              "طلب توريد", "warn", 3))
        for c in e.get("carries") or []:
            out.append(_alert("فرق ترحيل", e["store"], item,
                              f"{month_name(c['month'])}: أول المدة {q(c['opener']) or n(0)} — "
                              f"آخر {month_name(c['prev_month'])} {q(c['prev_closing']) or n(0)} "
                              f"{unit}".strip(), "مراجعة رصيد أول المدة", "warn", 2))
    for store in ctx.stores():
        missing = [label for field, label in REGISTRY_FIELDS
                   if store.get(field) in (None, "") or str(store.get(field)).strip() == ""]
        if missing:
            out.append(_alert("بيانات مخزن ناقصة", store["name"], "",
                              "ناقص: " + "، ".join(missing), "استكمال البيانات", "", 5))
    out.sort(key=lambda a: (a["rank"], a["store"], a["item"]))
    return out


def _alert(kind, store, item, details, action, cls, rank):
    return {"kind": kind, "store": store or "", "item": item or "", "details": details,
            "action": action, "cls": cls, "rank": rank}


def badge(ctx):
    return len(collect(ctx))


def build(ctx):
    items = collect(ctx)
    counts = {}
    for a in items:
        counts[a["kind"]] = counts.get(a["kind"], 0) + 1
    from ..calc import card
    cards = [card(kind, n(count), "", _kind_class(items, kind)) for kind, count in counts.items()]
    if not cards:
        cards = [card("التنبيهات", n(0), "", "good", "✓")]
    tables = [_unassigned(ctx),
              table("alerts", "التنبيهات",
                    ["نوع التنبيه", "المخزن", "الصنف", "التفاصيل", "المطلوب عمله"],
                    [norm([cell(a["kind"], a["cls"]), cell(a["store"], "", "store"),
                           cell(a["item"], "", "item"), a["details"], a["action"]])
                     for a in items])]
    if ctx.yearly:
        tables.append(_carries(ctx))
    return {"cards": cards, "tables": tables}


def _kind_class(items, kind):
    for a in items:
        if a["kind"] == kind:
            return a["cls"]
    return ""


def _unassigned(ctx):
    ref = ctx.ref()
    rows = []
    entries = sorted(((k, e) for k, e in ctx.keys().items() if not k[0] and e["closing"] > EPS),
                     key=lambda kv: kv[0][1])
    for i, ((_sid, item, unit), e) in enumerate(entries, start=1):
        near = ctx.nearest_expiry(sid=0, item=item, unit=unit)
        rows.append(norm([n(i), cell(item, "b", "item"), unit, cell(q(e["closing"]), "b"),
                          cell(d(near), LEVEL_CLASS[level(near, ref)] if near else "", "date")]))
    return table("unassigned", "غير موزع", ["م", "الصنف", "الوحدة", "الرصيد", "أقرب صلاحية"],
                 rows)


def _carries(ctx):
    rows = []
    for (_sid, item, unit), e in sorted(ctx.keys().items(), key=lambda kv: (kv[1]["store"] or "",
                                                                           kv[0][1])):
        for c in e.get("carries") or []:
            rows.append(norm([cell(e["store"], "", "store"), cell(item, "b", "item"), unit,
                              month_name(c["prev_month"]), q(c["prev_closing"]) or n(0),
                              month_name(c["month"]), q(c["opener"]) or n(0),
                              cell(q(c["diff"]), "warn")]))
    return table("carries", "فروق الترحيل",
                 ["المخزن", "الصنف", "الوحدة", "الشهر السابق", "رصيد آخره", "الشهر",
                  "رصيد أول المدة", "الفرق"], rows)
