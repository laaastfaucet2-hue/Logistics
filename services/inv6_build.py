# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""«دفتر 6 مخازن (جرد الأصناف)» — بيانات تقرير الجرد من دفاتر ٣ مخازن الحقيقية.

قواعد التوجيه (١٠/١٠):
- الأصناف = كل أصناف دفتر ٣ مخازن (سجل الإمداد ثم سجل المتعهد) فقط لا غير.
- الوحدة = وحدة الصنف في دفتر ٣ مخازن (وحدة الدفتر الدقيقة).
- الرصيد الافتراضي = رصيد ختام يوم الجرد: أول المدة + إضافات ١ مخازن −
  منصرف ٢ مخازن (الرصيد التراكمي الفعلي لحد نهاية اليوم).
- الزيادة/النقص = الموجود الفعلي من واقع الجرد − الرصيد الافتراضي.
"""
from core import arabic_numbers as arnum
from core.config import MONTH_NAMES
from data_access import db_inv6 as di6
from data_access import db_letterhead as lhdb
from data_access import db_warehouses as dw
from data_access import oil_units as ou

CYCLES = ("supply", "contractor")
CYCLE_NAMES = {"supply": "سجل الإمداد", "contractor": "سجل المتعهد"}


def _ledger_unit(item):
    """وحدة الصنف في دفتر ٣ مخازن + معامل (وحدة التعامل → وحدة الدفتر)."""
    return ou.ledger_unit(item["name"], item.get("ration_unit"),
                          item.get("handle_unit"), item.get("specific_weight"))


def balance_at_day(card, day):
    """رصيد ختام اليوم: آخر سطر تراكمي ليوم ≤ يوم الجرد (بما فيهم أول المدة)."""
    if not card or not card.get("rows"):
        return 0.0
    last = None
    for r in card["rows"]:
        d = int(r.get("day") or 0)
        if r.get("kind") == "opener" or (1 <= d <= int(day)):
            last = r
    if last is None:
        return 0.0
    return arnum.round3(float(last.get("balance") or 0.0) * card["unit_factor"])


def _with_diffs(rows):
    """يضيف الزيادة/النقص (الموجود الفعلي − الرصيد الدفتري) + قيمه لكل سطر."""
    out = []
    for r in rows:
        r = dict(r)
        diff = round(float(r.get("counted") or 0) - float(r.get("book") or 0), 6)
        r["inc"] = arnum.round3(diff) if diff > 0 else 0.0
        r["dec"] = arnum.round3(-diff) if diff < 0 else 0.0
        r["value"] = arnum.round3(round(float(r.get("price") or 0), 3) *
                                  round(float(r.get("counted") or 0), 3))
        out.append(r)
    return out


def snapshot_items(year, month, day):
    """لقطة أصناف يوم الجرد: الرصيد الافتراضي لكل صنف من ٣ مخازن (دون أي حفظ)."""
    out = []
    serial = 0
    for cycle in CYCLES:
        for item in dw.list_items(year, month, cycle):
            card = dw.item_card(year, month, item["id"])
            unit, _factor = _ledger_unit(item)
            serial += 1
            out.append({
                "cycle": cycle,
                "item_id": item["id"],
                "name": item["name"],
                "unit": unit,
                "book": balance_at_day(card, day),
                "serial": serial,
            })
    return out


def default_header(year, month):
    """رأس اليوم الافتراضي من الدباجة: الجهة/المخزن/صاحب المعدة + التوقيعات."""
    vals = lhdb.get_all(year, month)
    return {
        "day": None,
        "sector": (vals.get("lh_3") or "").strip(),
        "warehouse": (vals.get("lh_4") or "").strip(),
        "owner_rank": (vals.get("sig_left_rank") or "").strip(),
        "owner_name": (vals.get("sig_left_name") or "").strip(),
        "sigs": {
            "chief": {"rank": (vals.get("sig_right_rank") or "").strip(),
                      "name": (vals.get("sig_right_name") or "").strip()},
            "manager": {"rank": "", "name": ""},
            "committee": ["", "", ""],
            "owner": {"rank": (vals.get("sig_left_rank") or "").strip(),
                      "name": (vals.get("sig_left_name") or "").strip()},
            "writer": {"rank": "", "name": ""},
        },
    }


def day_view(year, month, day):
    """بيانات صفحة يوم الجرد: الأصناف + المحفوظ (إن وُجد) + الإحلال على الافتراضي.

    يرجع {header, rows, saved, inc, dec} — rows جاهزة للعرض وللحفظ.
    """
    day = int(day)
    snap = snapshot_items(year, month, day)
    saved = di6.load_day(year, month, day)
    header = saved["header"] if saved else default_header(year, month)
    header["day"] = day
    srows = {int(r["item_id"]): r for r in (saved["rows"] if saved else [])}
    rows = []
    for s in snap:
        sr = srows.get(s["item_id"])
        if sr:
            row = {
                "cycle": s["cycle"], "item_id": s["item_id"], "name": s["name"],
                "unit": s["unit"], "serial": s["serial"],
                "book": float(sr["book"]),
                "counted": float(sr["counted"]),
                "price": float(sr["price"]),
                "status_item": sr["status_item"] or "جيدة",
                "status_issue": sr["status_issue"] or "جيدة",
            }
        else:
            row = {
                "cycle": s["cycle"], "item_id": s["item_id"], "name": s["name"],
                "unit": s["unit"], "serial": s["serial"],
                "book": s["book"], "counted": s["book"], "price": 0.0,
                "status_item": "جيدة", "status_issue": "جيدة",
            }
        rows.append(row)
    return {"header": header, "rows": _with_diffs(rows), "saved": bool(saved)}


def page_context(year, month, raw_day):
    """بيانات تاب «6 مخازن» جوه صفحة مستودعات وسجلات (توجيه ١٠/١٠)."""
    from core import egtime
    from data_access import db_inv6 as di6
    from services import inv6_fs as i6fs
    saved_days = di6.list_days(year, month)
    days_in = egtime.days_in_month(year, month)
    day = arnum.parse_int(raw_day)
    if not day or not 1 <= day <= days_in:
        day = saved_days[0] if saved_days else 1
    view = day_view(year, month, day)
    return {
        "day": day,
        "days_in": days_in,
        "saved_days": saved_days,
        "header": view["header"],
        "rows": view["rows"],
        "has_saved": view["saved"],
        "file_rel": i6fs.rel_path(year, month, day),
        "file_exists": i6fs.day_file(year, month, day).is_file(),
    }


def apply_day(year, month, day, header, rows):
    """«تطبيق الجرد»: لقطة جديدة للرصيد الافتراضي + حفظ اليوم + ملف الإكسل على القرص.

    يرجع {ok, rel} — rel = المسار النسبي للملف داخل فولدر الشهر.
    """
    from services import inv6_fs
    day = int(day)
    snap = {s["item_id"]: s["book"] for s in snapshot_items(year, month, day)}
    clean = []
    for r in rows:
        item_id = int(r["item_id"])
        book = float(snap.get(item_id, r.get("book") or 0))
        counted = arnum.round3(float(r.get("counted") or 0))
        price = arnum.round3(float(r.get("price") or 0))
        diff = round(counted - book, 6)
        clean.append({
            "cycle": r["cycle"], "item_id": item_id, "name": r["name"],
            "unit": r.get("unit") or "",
            "book": book, "counted": counted, "price": price,
            "status_item": r.get("status_item") or "جيدة",
            "status_issue": r.get("status_issue") or "جيدة",
            "serial": int(r.get("serial") or 0),
        })
    di6.save_day(year, month, day, header, clean)
    rel = inv6_fs.save_to_disk(year, month, day)
    return {"ok": True, "rel": rel}


def fmt_date(year, month, day):
    """تاريخ الجرد بالصيغة العربية: ١/٩/٢٠٦."""
    return f"{arnum.to_arabic_indic(str(day))}/{arnum.to_arabic_indic(str(month))}/" \
           f"{arnum.to_arabic_indic(str(year))}"


def month_title(year, month):
    return f"{MONTH_NAMES[month - 1]} {arnum.to_arabic_indic(str(year))}"
