# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""التجميع: أرصدة كل (مخزن، صنف، وحدة) في الشهر، والسنة كمجموع شهورها.

قواعد السنة (الخطة ٧-٤):
* رصيد أول السنة = رصيد أول المدة في أول شهر فيه بيانات.
* وارد ومنصرف السنة = مجموع الشهور — ورصيد أول المدة لكل شهر لا يدخل المجموع.
* رصيد آخر الفترة = رصيد آخر شهر فيه بيانات.
* فرق الترحيل = رصيد أول المدة في شهر − رصيد آخر الشهر السابق (له بيانات).
  فتتحقق دائمًا: أول السنة + الوارد − المنصرف + فروق الترحيل = آخر الفترة.
"""
from data_access import db_permits as dp

from . import facts as F
from .calc import EPS


def keys_of(facts):
    """{(مخزن، صنف، وحدة): أول المدة/الوارد/المنصرف/الرصيد + عدد الحركات} لشهر واحد."""
    out = {}
    for line in facts["lines"]:
        key = (line["store_id"], line["item"], line["unit"])
        entry = out.setdefault(key, {"store": line["store"], "opener": 0.0, "in": 0.0,
                                     "out": 0.0, "in_n": 0, "out_n": 0})
        if line["dir"] == "in":
            if line["opener"]:
                entry["opener"] += line["qty"]
            else:
                entry["in"] += line["qty"]
                entry["in_n"] += 1
        else:
            entry["out"] += line["qty"]
            entry["out_n"] += 1
    for entry in out.values():
        for name in ("opener", "in", "out"):
            entry[name] = round(entry[name], 6)
        entry["balance"] = round(entry["opener"] + entry["in"] - entry["out"], 6)
    return out


def entity_names(lines):
    names = set()
    for line in lines:
        if line["dir"] == "out":
            names.update(dp.split_entity_label(line["entity"]))
    return names


def metrics(facts):
    """مؤشرات شهر واحد — تُستخدم في الملخص والمقارنة (الوحدات منفصلة دائمًا)."""
    from .calc import level
    lines = facts["lines"]
    keys = keys_of(facts)
    bal_units, in_units, out_units = {}, {}, {}
    for (sid, item, unit), entry in keys.items():
        if entry["balance"] > EPS:
            bal_units[unit] = round(bal_units.get(unit, 0.0) + entry["balance"], 6)
        if entry["in"] > EPS:
            in_units[unit] = round(in_units.get(unit, 0.0) + entry["in"], 6)
        if entry["out"] > EPS:
            out_units[unit] = round(out_units.get(unit, 0.0) + entry["out"], 6)
    live = [b for b in facts["batches"] if b["remaining"] > EPS]
    levels = [level(b["expiry"], facts["ref"]) for b in live]
    return {
        "receipts": len({(l["cycle"], l["serial"]) for l in lines
                         if l["dir"] == "in" and not l["opener"]}),
        "permits": len({l["permit"] for l in lines if l["dir"] == "out"}),
        "out_lines": sum(1 for l in lines if l["dir"] == "out"),
        "in_lines": sum(1 for l in lines if l["dir"] == "in" and not l["opener"]),
        "entities": entity_names(lines),
        "moving": {(l["item"], l["unit"]) for l in lines if not l["opener"]},
        "with_balance": {(k[1], k[2]) for k, e in keys.items() if e["balance"] > EPS},
        "stores_with_balance": {k[0] for k, e in keys.items()
                                if e["balance"] > EPS and k[0] != F.UNASSIGNED_ID},
        "bal_units": bal_units, "in_units": in_units, "out_units": out_units,
        "expired": levels.count("expired"), "danger": levels.count("danger"),
        "near": levels.count("near"), "no_date": levels.count("none"),
    }


def empty_metrics():
    """مؤشرات فترة بلا بيانات — أصفار (لا None على الشاشة)."""
    return {"receipts": 0, "permits": 0, "out_lines": 0, "in_lines": 0, "entities": set(),
            "moving": set(), "with_balance": set(), "stores_with_balance": set(),
            "bal_units": {}, "in_units": {}, "out_units": {},
            "expired": 0, "danger": 0, "near": 0, "no_date": 0, "per_month": {}}


# ---------------------------------------------------------------- السنة
def year_facts(year, today=None, flt=None):
    """شهور السنة التي فيها بيانات (بلا فلتر) + نسخها المصفاة للعرض."""
    raw = {}
    for month in range(1, 13):
        if not F.month_exists(year, month):
            continue
        facts = F.month_facts(year, month, today)
        if facts["has_data"]:
            raw[month] = facts
    months = sorted(raw)
    last = raw[months[-1]] if months else None
    stores = last["stores"] if last else F.registry_rows()
    filtered = {m: F.apply_filter(raw[m], flt) for m in months}
    targets = (filtered[months[-1]]["targets"] if months
               else F.apply_filter(F._empty(year, 12, stores, None, 0), flt)["targets"])
    return {
        "year": year, "months": months, "facts": filtered, "raw": raw,
        "first": months[0] if months else None, "last": months[-1] if months else None,
        "ref": last["ref"] if last else F.ref_date(year, 12, today),
        "elapsed": sum(raw[m]["elapsed"] for m in months),
        "targets": targets,
        "stores": filtered[months[-1]]["stores"] if months else stores,
        "filtered": bool(flt and flt.get("active")),
    }


def year_keys(yf):
    """تجميع السنة لكل (مخزن، صنف، وحدة) + فروق الترحيل بين الشهور."""
    out, prev_bal, prev_month = {}, {}, None
    for month in yf["months"]:
        current = keys_of(yf["facts"][month])
        for key in set(current) | set(prev_bal):
            entry = out.setdefault(key, {"store": None, "opening": 0.0, "in": 0.0, "out": 0.0,
                                         "carry": 0.0, "closing": 0.0, "months": {},
                                         "in_n": 0, "out_n": 0, "carries": []})
            cur = current.get(key)
            opener = cur["opener"] if cur else 0.0
            if prev_month is None:
                entry["opening"] = opener
            else:
                diff = round(opener - prev_bal.get(key, 0.0), 6)
                if abs(diff) > EPS:
                    entry["carry"] = round(entry["carry"] + diff, 6)
                    entry["carries"].append({"month": month, "prev_month": prev_month,
                                             "prev_closing": prev_bal.get(key, 0.0),
                                             "opener": opener, "diff": diff})
            if cur:
                entry["store"] = cur["store"]
                entry["in"] = round(entry["in"] + cur["in"], 6)
                entry["out"] = round(entry["out"] + cur["out"], 6)
                entry["in_n"] += cur["in_n"]
                entry["out_n"] += cur["out_n"]
                entry["months"][month] = cur
            entry["closing"] = cur["balance"] if cur else 0.0
            prev_bal[key] = entry["closing"]
        prev_month = month
    for key, entry in out.items():
        if entry["store"] is None:
            entry["store"] = key_store_name(yf, key[0])
    return out


def key_store_name(yf, sid):
    for target in yf.get("targets") or []:
        if target["id"] == sid:
            return target["name"]
    return ""


def busiest_month(entry):
    """أنشط شهر صرف للصنف — فارغ بلا صرف."""
    best, best_out = None, EPS
    for month, cur in entry["months"].items():
        if cur["out"] > best_out:
            best, best_out = month, cur["out"]
    return best


def year_metrics(yf):
    """مؤشرات السنة: الأعداد مجموع الشهور، والأرصدة والصلاحيات من آخر شهر."""
    if not yf["months"]:
        return None
    per = {m: metrics(yf["facts"][m]) for m in yf["months"]}
    last = per[yf["last"]]
    total = {"receipts": 0, "permits": 0, "out_lines": 0, "in_lines": 0,
             "entities": set(), "moving": set(), "in_units": {}, "out_units": {}}
    for m in yf["months"]:
        cur = per[m]
        for name in ("receipts", "permits", "out_lines", "in_lines"):
            total[name] += cur[name]
        total["entities"] |= cur["entities"]
        total["moving"] |= cur["moving"]
        for name in ("in_units", "out_units"):
            for unit, value in cur[name].items():
                total[name][unit] = round(total[name].get(unit, 0.0) + value, 6)
    for name in ("with_balance", "stores_with_balance", "bal_units",
                 "expired", "danger", "near", "no_date"):
        total[name] = last[name]
    total["per_month"] = per
    return total


def prev_month_of(year, month):
    return (year, month - 1) if month > 1 else (year - 1, 12)


def prev_month_facts(year, month, today=None, flt=None):
    """الشهر السابق (مصفّى) — None لو قاعدته غير موجودة."""
    from data_access import storage
    py, pm = prev_month_of(year, month)
    if py not in storage.list_years() or not F.month_exists(py, pm):
        return None
    return F.apply_filter(F.month_facts(py, pm, today), flt)


def prev_year_facts(year, today=None, flt=None):
    from data_access import storage
    if (year - 1) not in storage.list_years():
        return None
    return year_facts(year - 1, today, flt)
