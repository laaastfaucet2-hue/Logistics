# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""بناء «دفتر 4 مخازن» — مصفوفة الشطب اليومى + دفتر الشهرى لكل صنف.

توليد تلقائي (بلا إعادة إدخال):
- الأسطر = كل أصناف المقررات التموينية (اسم + وحدة) للدورة الحالية.
- رصيد أول المدة + الوارد + صرفيات أخرى = من ١/٢/٣ مخازن (كارت الصنف).
- «فعلي» = شطب اليومى (wh4_strike) — تراكمي بيقعد يعلى لحد آخر يوم في الشهر.
- «القيمة» = كمية السطر × سعر الوحدة (wh4_price — قابل للتعديل لكل صنف).
- الرصيد = المتبقي بعد كل حركة (السطر الصفراء = أول المدة/الختامي).
"""

from datetime import date

from core import arabic_numbers as arnum
from core import egtime
from core.config import MONTH_NAMES
from data_access import db_rations as dr
from data_access import db_warehouses as dw
from data_access import db_wh4 as w4


def _norm(name):
    return " ".join((name or "").split()).lower()


# ======================================================================
# أصناف الدفتر — كل أصناف المقررات التموينية
# ======================================================================
def ration_items(year, month, cycle):
    """أسطر الدفتر: اسم + وحدة (وحدة الدفتر لو الصنف متطابق في ٣ مخازن) + الحالة."""
    kind = dr.get_activation(year, month, "tamween") or "summer"
    rows, _custom = dr.get_items(year, month, "tamween", kind)
    wh = {_norm(it["name"]): it for it in dw.list_items(year, month, cycle)}
    out = []
    for i, it in enumerate(rows):
        name = " ".join((it.get("name") or "").split())
        if not name:
            continue
        w = wh.get(_norm(name))
        # الوحدة = وحدة المقرر التمويني بالظبط (توجيه ١٠/١٠)
        out.append({
            "id": it.get("id"), "serial": i + 1, "name": name,
            "unit": (it.get("unit") or "").strip(),
            "wh_id": w["id"] if w else None, "status": "مفعّل",
        })
    return out


# ======================================================================
# تاب 1: مصفوفة الشطب اليومى (بند ‖ وحدة ‖ يوم 1..N ‖ المجموع)
# ======================================================================
def auto_qty_for(year, month, cycle, item_name, day):
    """الاستهلاك التلقائي لصنف في يوم = كميات أذون 2 مخازن (date_from = اليوم)."""
    total = 0.0
    for permit in dw.permits_book(year, month, cycle):
        if int(permit.get("date_from") or 0) != day:
            continue
        for entry in permit["cycle_items"]:
            if entry["name"] == item_name:
                total += float(entry.get("qty") or 0)
    return round(total, 6)


def daily_matrix(year, month, cycle):
    last = egtime.days_in_month(year, month)
    strike = w4.strike_map(year, month, cycle)
    # استهلاك تلقائي من أذون ٢ مخازن (اليوم = date_from للإذن) — ١٣/١٠
    auto_map = {}
    for permit in dw.permits_book(year, month, cycle):
        d = int(permit.get("date_from") or 0)
        if not (1 <= d <= last):
            continue
        for entry in permit["cycle_items"]:
            am = auto_map.setdefault(entry["name"], {})
            am[d] = round(am.get(d, 0.0) + float(entry.get("qty") or 0), 6)
    rows = []
    for it in ration_items(year, month, cycle):
        days = strike.get(it["name"], {})
        auto = auto_map.get(it["name"], {})
        total = round(sum(days.values()) + sum(auto.values()), 6)
        rows.append({**it, "days": days, "auto": auto, "total": total})
    day_names = [egtime.weekday_ar(date(year, month, d)) for d in range(1, last + 1)]
    days_total = {d: round(sum((r["days"].get(d, 0) + r["auto"].get(d, 0)) for r in rows), 6)
                  for d in range(1, last + 1)}
    grand = round(sum(r["total"] for r in rows), 6)
    return {"rows": rows, "last": last, "day_names": day_names,
            "days_total": days_total, "grand_total": grand}


# ======================================================================
# تاب 2: دفتر الشهرى لكل صنف (توليد تلقائي)
# ======================================================================
def monthly_ledger(year, month, cycle, item_name):
    """دفتر شهرى لصنف: أسطر زمنية + الرصيد المتتالي + الشيبات.

    الأسطر (بالترتيب الزمني):
    - «رصيد أول المدة» (صفرة) — من ٣ مخازن (لو الصنف مسجل فيها).
    - سطر كامل لكل وردة من المورّد (اسم الشركة + الكمية المضافة) — كل
      إضافة لوحدها (١٣/١٠).
    - سطر واحد «استهلاك <الشهر>» (وردي) على آخر يوم = كل الاستهلاك
      (صرفيات أذون ٢ مخازن + الشطب اليدوي) في عمود «فعلي» — عمود
      «صرفيات أخرى» فاضي دايمًا، ومن غير أسماء جهات (١٣–١٤/١٠).
    - «رصيد ختامي المدة» (صفرة).
    """
    name = " ".join((item_name or "").split())
    if not name:
        return None
    last = egtime.days_in_month(year, month)
    items = {it["name"]: it for it in ration_items(year, month, cycle)}
    it = items.get(name)
    unit = it["unit"] if it else ""
    price = w4.price_map(year, month, cycle).get(name, 0.0)

    # أحداث ١/٢/٣ مخازن (لو الصنف له كارت في ٣ مخازن) — كميات بوحدة الدفتر
    # ١٣/١٠: كل الاستهلاك (صرفيات الجهات + الشطب اليدوي) في سطر واحد
    # «استهلاك <الشهر>» — من غير أسماء جهات. الإضافات كل واحدة سطر
    # مستقل باسم الشركة الموردة.
    events = []      # (date_iso, seq, kind, permit_no, label, added, other, real_delta, real_cum)
    opener_balance = 0.0
    other_total = 0.0
    if it and it.get("wh_id"):
        card = dw.item_card(year, month, it["wh_id"])
        if card:
            uf = float(card.get("unit_factor") or 1.0)
            sup = {int(r["serial"]): (r.get("supplier_name") or "")
                   for r in dw.list_receipts(year, month, cycle)}
            for r in card["rows"]:
                kind = r["kind"]
                iso = (r.get("date_iso") or "").strip()
                if not iso:
                    dnum = int(r.get("day") or 0)
                    if 1 <= dnum <= last:
                        iso = f"{year:04d}-{month:02d}-{dnum:02d}"
                pn = int(r.get("permit_no") or 0)
                if kind == "opener":
                    q = round(float(r.get("added") or 0) * uf, 6)
                    opener_balance = q
                    events.append((iso, 0, "opener", 0, "رصيد أول المدة",
                                   q, 0.0, 0.0, 0.0))
                elif kind == "add1":
                    q = round(float(r.get("added") or 0) * uf, 6)
                    label = sup.get(pn) or r.get("label") or ""
                    events.append((iso, 1, "add1", pn,
                                   label or f"إذن إضافة ١ مخازن رقم {pn}",
                                   q, 0.0, 0.0, 0.0))
                elif kind == "issue2":
                    other_total = round(other_total
                                        + float(r.get("issued") or 0) * uf, 6)

    # الشطب اليومى (يدوي) — بيتجمع في نفس سطر «استهلاك <الشهر>»
    strike_days = w4.strike_map(year, month, cycle).get(name, {})
    strike_total = round(sum(strike_days.values()), 6)
    # ١٤/١٠: كل الاستهلاك (صرفيات الأذون + الشطب اليدوي) في عمود «فعلي»
    # — عمود «صرفيات أخرى» في دفتر 4 مخازن فاضي دايمًا.
    consumed_total = round(other_total + strike_total, 6)
    if consumed_total:
        events.append((f"{year:04d}-{month:02d}-{last:02d}", 4, "strike", 0,
                       f"استهلاك {MONTH_NAMES[month - 1]}",
                       0.0, 0.0, consumed_total, consumed_total))

    # الدمج والزمن + الرصيد المتتالي + القيمة
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    running = 0.0
    rows = []
    for iso, _seq, kind, pn, label, added, other, real_delta, real_cum in events:
        running = round(running + added - other - real_delta, 6)
        if kind in ("opener", "add1"):
            value = round(added * price, 6)
        else:
            # سطر «استهلاك <الشهر>» = كل الاستهلاك (صرفيات + شطب يدوي)
            value = round((other + real_delta) * price, 6)
        day = int(iso[-2:])
        try:
            wday = egtime.weekday_ar(date(year, month, day))
        except (TypeError, ValueError):
            wday = "—"
        rows.append({
            "date_iso": iso, "day": day, "wday": wday, "kind": kind,
            "permit_no": pn, "label": label,
            "added": arnum.round3(added), "other": arnum.round3(other),
            "real": arnum.round3(real_cum), "real_delta": arnum.round3(real_delta),
            "balance": arnum.round3(running), "price": arnum.round3(price),
            "value": arnum.round3(value), "notes": "",
        })
    final_balance = round(running, 6)
    rows.append({
        "date_iso": "", "day": 0, "wday": "—", "kind": "closing", "permit_no": 0,
        "label": "رصيد ختامي المدة", "added": 0.0, "other": 0.0, "real": 0.0,
        "real_delta": 0.0, "balance": arnum.round3(final_balance),
        "price": arnum.round3(price), "value": 0.0, "notes": "",
    })
    return {
        "item_name": name, "item_no": it.get("id") if it else "",
        "unit": unit, "status": it.get("status") if it else "—",
        "price": arnum.round3(price),
        "opener_balance": arnum.round3(opener_balance),
        # استهلاك الشهر الكلى = صرفيات الأذون + الشطب اليدوي (١٣/١٠)
        "consumed": arnum.round3(round(other_total + strike_total, 6)),
        "final_balance": arnum.round3(final_balance),
        "last": last, "rows": rows,
        "month_name": MONTH_NAMES[month - 1], "year": year, "month": month,
        "sign_date": egtime.now().strftime("%Y-%m-%d"),
    }
