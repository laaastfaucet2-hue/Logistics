# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""🏬 إحصائيات المخازن والثلاجات — ٩ تبويبات فرعية، لكل تبويب مجلد وملف إكسل شهري وسنوي.

الواجهة العامة لباقي البرنامج:
    SUBTABS · visible_subtabs() · build_view() · page_context() · parse_filters()
    after_save()  ← النقطة الوحيدة بعد أي حفظ ناجح (app.py)
    schedule() · refresh_now()

الحساب كله من دوال قسم المخازن (stores_report + محرك التفريدة)، والشاشة والطباعة والإكسل
تقرأ نفس الناتج من build_view (لا يختلف الورق عن الإكسل).
"""
from core import arabic_numbers as arnum
from core import egtime
from core.config import MONTH_NAMES

from . import facts as F
from .subtabs import DEFAULT_SUB, SUBTAB_MAP, SUBTABS, file_name, folder_name, period_text

TITLE = "إحصائيات المخازن والثلاجات"
CYCLE_OPTIONS = ("الكل", "الإمداد", "المتعهد")
BADGE_CLASS = {"expiry": "bad", "consumption": "warn", "alerts": "bad"}
REFRESH_PREFIXES = ("/warehouses", "/inv6", "/calc2", "/stores", "/rations", "/month-copy",
                    "/letterhead", "/backups")

__all__ = ["SUBTABS", "visible_subtabs", "visible_keys", "build_view", "page_context",
           "parse_filters", "after_save", "schedule", "refresh_now", "file_name",
           "folder_name", "period_text"]


def visible_keys():
    from .tabs import modules
    ready = modules()
    return [t["key"] for t in SUBTABS if t["key"] in ready]


def visible_subtabs():
    return [SUBTAB_MAP[k] for k in visible_keys()]


def normalize_sub(sub):
    return sub if sub in visible_keys() else DEFAULT_SUB


def build_view(key, year, month, scope="month", flt=None, today=None, ctx=None):
    """ناتج التبويب الواحد (كروت + جداول) — نفسه للشاشة والطباعة والإكسل."""
    from .tabs import Ctx, builders
    ctx = ctx or Ctx(year, month, scope, flt, today)
    view = builders()[key](ctx)
    tab = SUBTAB_MAP[key]
    view.setdefault("cards", [])
    view.setdefault("tables", [])
    view.update(key=key, name=tab["name"], icon=tab["icon"], period=ctx.period(),
                scope=ctx.scope)
    return view


# ---------------------------------------------------------------- الفلاتر
def parse_filters(args, stores=None):
    """فلاتر الشاشة (المخزن/الدورة/الصنف) من الرابط — الإكسل دائمًا بلا فلتر."""
    stores = F.registry_rows() if stores is None else stores
    raw_store = (args.get("f_store") or "").strip()
    raw_cycle = (args.get("f_cycle") or "").strip()
    item = (args.get("f_item") or "").strip()
    store = None
    if raw_store == F.unassigned_name():
        store = F.UNASSIGNED_ID
    elif raw_store:
        store = next((s["id"] for s in stores if s["name"] == raw_store), None)
    cycle = F.CYCLE_BY_NAME.get(raw_cycle)
    return {"store": store, "cycle": cycle, "item": item,
            "active": store is not None or bool(cycle) or bool(item),
            "raw": {"f_store": raw_store if store is not None else "",
                    "f_cycle": raw_cycle if cycle else "", "f_item": item}}


def filter_text(flt):
    parts = []
    if flt["raw"]["f_store"]:
        parts.append(f"المخزن: {flt['raw']['f_store']}")
    if flt["raw"]["f_cycle"]:
        parts.append(f"الدورة: {flt['raw']['f_cycle']}")
    if flt["raw"]["f_item"]:
        parts.append(f"الصنف: {flt['raw']['f_item']}")
    return " · ".join(parts)


# ---------------------------------------------------------------- الصفحة
def _badges(ctx):
    from .tabs import modules
    out = {}
    for key, module in modules().items():
        badge = getattr(module, "badge", None)
        if badge:
            value = badge(ctx)
            if value:
                out[key] = value
    return out


def _item_options(year, month, scope, today):
    from .tabs import Ctx
    full = Ctx(year, month, scope, None, today)
    names = {line["item"] for line in full.lines()} | {b["item"] for b in full.batches()}
    return sorted(n for n in names if n)


def page_context(year, month, scope, sub, args, background=True, today=None):
    """كل ما يحتاجه قالب التبويب: الهيدر والتبويبات بأرقامها والفلاتر وشريط الملفات والبيانات."""
    from . import files, refresher
    from .tabs import Ctx
    today = today or egtime.today()
    sub = normalize_sub(sub)
    scope = "year" if scope == "year" else "month"
    stores = F.registry_rows()
    flt = parse_filters(args, stores)
    ctx = Ctx(year, month, scope, flt, today)
    view = build_view(sub, year, month, scope, ctx=ctx)
    badges = _badges(ctx)
    refresher.ensure_fresh(year, month, background=background, today=today)
    file_month = month if scope == "month" else None
    busy = refresher.busy(year)
    tab = SUBTAB_MAP[sub]
    months = ctx.months() if scope == "year" else []
    if scope == "year":
        span = (f"من {MONTH_NAMES[months[0] - 1]} إلى {MONTH_NAMES[months[-1] - 1]}"
                if len(months) > 1 else MONTH_NAMES[months[0] - 1] if months else "")
    else:
        span = ""
    cycle_label = F.CYCLE_NAMES.get(flt["cycle"]) or "الإمداد + المتعهد"
    return {
        "sub": sub, "tab": tab, "scope": scope, "view": view, "flt": flt,
        "filters": flt["raw"], "filter_text": filter_text(flt),
        "filters_set": {k: v for k, v in flt["raw"].items() if v},
        "tabs": [dict(t, badge=badges.get(t["key"]), badge_cls=BADGE_CLASS.get(t["key"], ""))
                 for t in visible_subtabs()],
        "period": ctx.period(), "title": f"{TITLE} — {ctx.period()}",
        "sub_line": " · ".join(p for p in (cycle_label, span) if p),
        "print_title": f"{TITLE} — {tab['name']} — {ctx.period()}",
        "folder_name": folder_name(sub), "file_name": file_name(sub, year, file_month),
        "path_text": files.path_text(sub, file_month),
        "status": files.status(sub, year, file_month, busy=busy),
        "busy": busy,
        "options": {"stores": [s["name"] for s in stores] + [F.unassigned_name()],
                    "cycles": list(CYCLE_OPTIONS),
                    "items": _item_options(year, month, scope, today)},
        "has_data": ctx.has_data(),
        "wide": any(t.get("wide") for t in view["tables"]),
        "keep": {"cycle": "supply", "tab": "stores", "sub": sub, "scope": scope,
                 **{k: v for k, v in flt["raw"].items() if v}},
    }


# ---------------------------------------------------------------- التحديث
def schedule(year, month=None, **kwargs):
    from . import refresher
    return refresher.schedule(year, month, **kwargs)


def refresh_now(year, month=None, today=None):
    """تحديث فوري متزامن لملفات السنة (والشهر المذكور يُنشأ حتى لو فارغًا)."""
    from . import refresher
    return refresher.run_year(year, create={int(month)} if month else (), create_year=True,
                              today=today)


def after_save(path, form, year, month, background=True):
    """بعد أي حفظ ناجح يأثر على المخازن: طلب تحديث الملفات (يتجمع في الخلفية)."""
    from data_access import storage
    from . import refresher
    if not path.startswith(REFRESH_PREFIXES):
        return False
    stores = not path.startswith("/stores")
    if path.startswith("/backups/restore"):
        for each in storage.list_years():
            refresher.schedule(each, None, background=background)
        return True
    refresher.schedule(year, month, stores=stores, background=background)
    if path.startswith("/month-copy"):
        form = form or {}
        ty = arnum.parse_int(form.get("target_year"))
        value = str(form.get("target_month") or "").strip()
        tm = MONTH_NAMES.index(value) + 1 if value in MONTH_NAMES else arnum.parse_int(value)
        if ty in storage.list_years() and tm and 1 <= tm <= 12:
            refresher.schedule(ty, tm, stores=True, background=background)
    return True
