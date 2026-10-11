# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""محركات الإحصائيات لكل قسم (جولة ٣٦ — موجات ٢/٣): الصحة · المخازن · الترفية.

نفس ميثاق التاب الرئيسي: كروت + جداول + شارات (سليم/تحذير/خطر) — كله حي من month.db.
"""
from core import egtime, dates


# ==================== الصحة ====================
def health_stats(year, month):
    """كروت + «بأيام الكشف» + موقف الرش/الخزانات/المياه — من بيانات الصحة والمجندين."""
    from data_access import db_health, db_recruits

    days = db_health.get_days(year, month)
    roster = db_recruits.list_recruits(year, month)
    roster_ids = {r["id"] for r in roster}

    day_rows, checked_unique, total_checked = [], set(), 0
    for d in days:
        entries = db_health.get_day_entries(year, month, d)
        total_checked += len(entries)
        day_ids = {e["recruit_id"] for e in entries if e["recruit_id"]}
        checked_unique |= day_ids
        day_rows.append({
            "day": d,
            "count": len(entries),
            "missing": max(0, len(roster_ids) - len(day_ids & roster_ids)),
            "peak": False,
        })
    if day_rows:
        top = max(r["count"] for r in day_rows)
        if top > 0:
            for r in day_rows:
                r["peak"] = r["count"] == top

    no_checkup = [r for r in roster if r["id"] not in checked_unique]

    def _report_status(report):
        raw = (db_health.get_fields(year, month, report).get("date_text") or "").strip()
        d = dates.parse_date(raw) if raw else None
        delta = (d - egtime.today()).days if d else None
        if not d:
            return {"label": "لم يُسجل بعد", "badge": "warn", "raw": ""}
        if delta is None:
            return {"label": raw, "badge": "warn", "raw": raw}
        if delta < 0:
            return {"label": "تاريخ سابق: {}".format(dates.format_date(d)),
                    "badge": "bad" if abs(delta) > 90 else "warn", "raw": raw}
        return {"label": dates.format_date(d) + " (منذ {} يوم)".format(delta),
                "badge": "ok" if delta <= 90 else "warn", "raw": raw}

    return {
        "days_count": len(days),
        "roster_count": len(roster),
        "total_checked": total_checked,
        "unique_checked": len(checked_unique),
        "checked_days": sum(1 for r in day_rows if r["count"]),
        "day_rows": day_rows,
        "no_checkup": no_checkup,
        "spray": _report_status("spray"),
        "tanks": _report_status("tanks"),
        "water": _report_status("water"),
        "tank_count": docx_tank_count(year, month),
    }


def docx_tank_count(year, month):
    from documents import docx_health
    try:
        return docx_health.tank_count(year, month)
    except Exception:  # noqa: BLE001
        return 0


# ==================== المخازن والثلاجات ====================
def stores_stats(year, month):
    """حركة وكشف أرصدة كل مخزن + على وشك الصلاحية + توب ٥ أصناف الاستهلاك."""
    from data_access import db_stores
    from data_access import db_warehouses as dw
    from data_access import db_warehouses_stores as dws

    report = dw.stores_report(year, month)
    stores, unassigned = report["stores"], report["unassigned"]

    # شهادات الصلاحية: الدفعات (كل رسالة توريد = دفعة) حسب قرب انتهاء صلاحيتها
    expiring = {"ok": 0, "warn": 0, "bad": 0}
    conn = dw._conn(year, month)
    try:
        for cycle in ("supply", "contractor"):
            for r in conn.execute(
                    "SELECT exp_date FROM wh_receipts WHERE cycle=? AND exp_date<>''", (cycle,)):
                d = dates.parse_date(r["exp_date"])
                if not d:
                    continue
                delta = (d - egtime.today()).days
                expiring["bad" if delta <= 30 else ("warn" if delta <= 90 else "ok")] += 1
    finally:
        conn.close()

    # توب ٥ أصناف الاستهلاك (منصرف 2 مخازن — FEFO)
    issued = {}
    for (_pn, item), qty in dws.fefo_actual_map(year, month, "supply").items():
        issued[item] = issued.get(item, 0.0) + float(qty or 0)
    for (_pn, item), qty in dws.fefo_actual_map(year, month, "contractor").items():
        issued[item] = issued.get(item, 0.0) + float(qty or 0)
    top5 = sorted(issued.items(), key=lambda kv: (-kv[1], kv[0]))[:5]

    rows = []
    for e in stores:
        store = e["store"]
        inn = sum(float(x.get("qty") or 0) for x in e["inn"])
        out = sum(float(x.get("qty") or 0) for x in e["out"])
        items = len(e["balances"])
        rows.append({
            "id": store["id"], "name": store["name"],
            "capacity": store.get("capacity_m2") or "",
            "items": items,
            "inn": inn, "out": out,
            "total": e.get("total") or 0.0,
        })
    un_items = len(unassigned["balances"])
    un_inn = sum(float(x.get("qty") or 0) for x in unassigned["inn"])
    un_out = sum(float(x.get("qty") or 0) for x in unassigned["out"])
    return {
        "rows": rows,
        "unassigned": {"name": "غير موزع", "items": un_items,
                       "inn": un_inn, "out": un_out,
                       "total": unassigned.get("total") or 0.0},
        "expiring": expiring,
        "top5": top5,
        "stores_count": len(stores),
    }


# ==================== الترفية ====================
def tarfea_stats(year, month):
    """الأصناف + الرصيد + الصرف لكل مخزن (1/2/3/5) + توب ٥ — دورة الترفية المستقلة."""
    from data_access import db_warehouses as dw
    from data_access import db_warehouses_stores as dws

    cycle = "tarfea"
    items = []
    try:
        balances = dw.item_balances(year, month, cycle)
    except Exception:  # noqa: BLE001 — دورة بلا أصناف
        balances = {}
    item_names = {it["id"]: it["name"] for it in dw.list_items(year, month, cycle)}
    supplied, issued = {}, {}
    for r in dw.list_receipts(year, month, cycle):
        name = item_names.get(r["item_id"])
        if not name:
            continue
        supplied[name] = supplied.get(name, 0.0) + float(r["qty_handle"] or 0)
    for (_pn, item), qty in dws.fefo_actual_map(year, month, cycle).items():
        issued[item] = issued.get(item, 0.0) + float(qty or 0)
    for it in dw.list_items(year, month, cycle):
        name = it["name"]
        items.append({
            "name": name,
            "unit": it["handle_unit"],
            "supplied": supplied.get(name, 0.0),
            "issued": issued.get(name, 0.0),
            "balance": balances.get(it["id"], 0.0),
        })
    items.sort(key=lambda x: x["name"])
    top5 = [(k, v) for k, v in sorted(issued.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]
    return {
        "item_rows": items,
        "top5": top5,
        "items_count": len(items),
        "supplied_total": sum(supplied.values()),
        "issued_total": sum(issued.values()),
        "stores": tarfea_stores(year, month),
    }


def tarfea_stores(year, month):
    """مخازن الترفية الخمسة (1/2/3/5 + مخزن الترفية) — من سجلات 3 مخازن."""
    from data_access import db_warehouses as dw

    # سطور 3 مخازن = سجلات الصرف على المخازن لكل إذن — نجمعها بالاسم
    try:
        conn = dw._conn(year, month)
        rows = conn.execute(
            "SELECT s.store_name, SUM(s.qty) AS q"
            " FROM wh_receipt_stores s JOIN wh_receipts r ON s.receipt_id=r.id"
            " WHERE r.cycle='tarfea' GROUP BY s.store_name").fetchall()
        conn.close()
        return [(r["store_name"], float(r["q"] or 0)) for r in rows]
    except Exception:  # noqa: BLE001
        return []

# ==================== التاميدات ====================
def tameedat_stats(year, month):
    """كروت + «باليوم» (ذروة 🔥) + «بالجهة» + مقارنة بالشهر اللي فات."""
    from data_access import db_tameedat as dtm

    records = dtm.month_records(year, month)
    summary, totals = dtm.month_summary(year, month)

    day_map = {}
    for rec in records:
        total = rec["officers"] + rec["individuals"] + rec["recruits"]
        for d in range(rec["day"], rec["day_to"] + 1):
            e = day_map.setdefault(d, {"records": 0, "total": 0})
            e["records"] += 1
            e["total"] += total
    day_rows = [{"day": d, "records": v["records"], "total": v["total"]}
                for d, v in sorted(day_map.items())]
    top = max((r["total"] for r in day_rows), default=0)
    for r in day_rows:
        r["peak"] = bool(top) and r["total"] == top

    entity_rows = []
    for row in summary:
        if row["kind"] != "entity":
            continue
        entity_rows.append({
            "name": row["name"], "entity_type": row["entity_type"],
            "records": row["records"], "active_days": row["active_days"],
            "officers": row["total_officers"], "individuals": row["total_individuals"],
            "recruits": row["total_recruits"], "grand": row["grand_total"],
        })
    entity_rows.sort(key=lambda r: (-r["grand"], r["name"]))

    # مقارنة بالشهر اللي فات (إجمالي المومَّدين)
    prev_ratio = None
    if month > 1:
        py, pm = (year, month - 1)
    else:
        py, pm = (year - 1, 12)
    try:
        from data_access import storage
        from core.config import month_folder
        if (storage.year_path(py) / month_folder(pm) / "month.db").exists():
            _s, prev_totals = dtm.month_summary(py, pm)
            tot, prev = totals["grand"], prev_totals["grand"]
            if tot and prev:
                prev_ratio = round((tot - prev) / prev * 100)
    except Exception:  # noqa: BLE001 — المقارنة تجميلية
        prev_ratio = None

    return {
        "totals": totals,
        "day_rows": day_rows,
        "entity_rows": entity_rows,
        "prev_ratio": prev_ratio,
    }


# ==================== الراغبين ====================
def raghibin_stats(year, month):
    """كروت + «بالجهة» (ضباط/أفراد × راغب/إجمالي + ٪) + «عدم الراغبين» + مقارنة."""
    from data_access import db_raghibin as drg

    persons = drg.list_persons(year, month)
    entity_map = {}
    excluded_rows = []
    for p in persons:
        e = entity_map.setdefault(p["entity_id"], {
            "name": p["entity_name"], "entity_type": p["entity_type"],
            "officers": 0, "individuals": 0,
            "officers_ex": 0, "individuals_ex": 0})
        e["officers" if p["category"] == "officers" else "individuals"] += 1
        if p["excluded"]:
            e["officers_ex" if p["category"] == "officers" else "individuals_ex"] += 1
            excluded_rows.append({
                "name": p["full_name"], "rank": p["rank"] or "—",
                "entity": p["entity_name"], "note": p["exclude_note"] or "—",
                "category": p["category"]})
    entity_rows = []
    for e in entity_map.values():
        o, i = e["officers"], e["individuals"]
        oex, iex = e["officers_ex"], e["individuals_ex"]
        willing = (o - oex) + (i - iex)
        total = o + i
        entity_rows.append({
            "name": e["name"], "entity_type": e["entity_type"],
            "officers": o, "officers_w": o - oex,
            "individuals": i, "individuals_w": i - iex,
            "willing": willing, "total": total,
            "pct": round(willing / total * 100) if total else 0,
        })
    entity_rows.sort(key=lambda r: r["name"])

    total = sum(r["total"] for r in entity_rows)
    willing = sum(r["willing"] for r in entity_rows)
    # مقارنة: نسبة الراغبين عن الشهر اللي فات
    prev_ratio = None
    if month > 1:
        py, pm = (year, month - 1)
    else:
        py, pm = (year - 1, 12)
    try:
        from data_access import storage
        from core.config import month_folder
        if (storage.year_path(py) / month_folder(pm) / "month.db").exists():
            prev = drg.list_persons(py, pm)
            p_total = len(prev)
            p_willing = sum(1 for p in prev if not p["excluded"])
            if p_total and total:
                a, b = willing / total, p_willing / p_total
                if b:
                    prev_ratio = round((a - b) / b * 100)
    except Exception:  # noqa: BLE001 — المقارنة تجميلية
        prev_ratio = None

    return {
        "entity_rows": entity_rows,
        "excluded_rows": excluded_rows,
        "total": total,
        "willing": willing,
        "excluded": total - willing,
        "pct": round(willing / total * 100) if total else 0,
        "prev_ratio": prev_ratio,
    }


# ==================== المقررات (التموين/المتعهد) ====================
def rations_stats(year, month, section):
    """بالمواعيد: لكل نوع (صيفي/شتوي/رمضان) الأصناف + إجماليات الوجبات + النشط
    + التوزيع على الجهات (من أذون ٢ مخازن الدورة الفعلية)."""
    from data_access import db_rations as dr
    from data_access import db_warehouses as dw

    active = dr.get_activation(year, month, section) or ""
    cycle = "supply" if section == "tamween" else "contractor"
    kinds = []
    for key, name, icon in (("summer", "صيفي", "☀️"), ("winter", "شتوي", "❄️"),
                            ("ramadan", "رمضان", "🌙")):
        try:
            items, _custom = dr.get_items(year, month, section, key)
        except Exception:  # noqa: BLE001 — نوع بلا أصناف
            items = []
        kinds.append({
            "key": key, "name": name, "icon": icon,
            "count": len(items),
            "breakfast": sum(float(it.get("breakfast") or 0) for it in items),
            "lunch": sum(float(it.get("lunch") or 0) for it in items),
            "dinner": sum(float(it.get("dinner") or 0) for it in items),
            "active": key == active,
        })

    # التوزيع على الجهات: أذون 2 مخازن الدورة مجمعة بالجهة
    dist_map = {}
    for permit in dw.permits_book(year, month, cycle):
        ent = permit.get("entity_label") or "—"
        qty = sum(float(it["qty"] or 0) for it in permit["cycle_items"])
        e = dist_map.setdefault(ent, {"permits": 0, "qty": 0.0, "items": set()})
        e["permits"] += 1
        e["qty"] += qty
        for it in permit["cycle_items"]:
            e["items"].add(it["name"])
    dist_rows = [{"entity": k, "permits": v["permits"], "qty": round(v["qty"], 4),
                  "items_count": len(v["items"])}
                 for k, v in sorted(dist_map.items())]
    return {"kinds": kinds, "dist_rows": dist_rows, "active": active,
            "section": section}


# ==================== الدوايل (تفارييد الدولى) ====================
def dowail_stats(year, month):
    """بالخط (نقاط/قوة/عدد التوزيعات/الإجمالي) + توب ٥ خطوط + مقارنة بالشهر اللي فات."""
    from services import dowail_build as dbb
    from data_access import db_dowail as dw

    # أشهر كامل بنفس باراميترات تاب «الإجماليات» الافتراضي (١ → آخر يوم)
    from core import egtime
    eom = egtime.days_in_month(year, month)
    try:
        matrix = dbb.totals_matrix(year, month, 1, eom, eom)
    except Exception:  # noqa: BLE001 — دورة بلا خطوط/معدلات
        matrix = {"rates": [], "lines": [], "items_total": {}, "grand_force": 0}

    # عدد التوزيعات المحفوظة التي شملت كل خط
    saves = dw.list_saves(year, month)
    save_line_hits = {}
    for s in saves:
        try:
            data = s.get("data") or {}
            for line in (data.get("matrix") or {}).get("lines", []):
                save_line_hits[line["line"]["name"]] = \
                    save_line_hits.get(line["line"]["name"], 0) + 1
        except Exception:  # noqa: BLE001 — لقطة قديمة بهيكل مختلف
            pass

    line_rows = []
    for l in matrix["lines"]:
        line = l["line"]
        total_qty = sum(l["line_total"].values())
        line_rows.append({
            "name": line["name"],
            "points": len(line["points"]),
            "force": line["total_force"],
            "saves": save_line_hits.get(line["name"], 0),
            "total_qty": round(total_qty, 4),
        })
    line_rows.sort(key=lambda r: r["name"])
    top5 = sorted(line_rows, key=lambda r: -r["total_qty"])[:5]
    grand = matrix.get("grand_force") or 0
    grand_qty = sum(matrix.get("items_total", {}).values())

    prev_ratio = None
    if month > 1:
        py, pm = (year, month - 1)
    else:
        py, pm = (year - 1, 12)
    try:
        from data_access import storage
        from core.config import month_folder
        if (storage.year_path(py) / month_folder(pm) / "month.db").exists():
            pm_eom = egtime.days_in_month(py, pm)
            prev_m = dbb.totals_matrix(py, pm, 1, pm_eom, pm_eom)
            prev_qty = sum(prev_m.get("items_total", {}).values())
            if prev_qty and grand_qty:
                a = grand_qty / egtime.days_in_month(year, month)
                b = prev_qty / pm_eom
                prev_ratio = round((a - b) / b * 100)
    except Exception:  # noqa: BLE001 — المقارنة تجميلية
        prev_ratio = None

    return {
        "line_rows": line_rows,
        "top5": top5,
        "grand_force": grand,
        "grand_qty": round(grand_qty, 4),
        "saves_count": len(saves),
        "rates_count": len(matrix.get("rates", [])),
        "prev_ratio": prev_ratio,
    }

# ==================== مستودعات وسجلات (دورة إمداد/متعهد) ====================
def warehouses_stats(year, month, cycle):
    """بالمرود + بالجهة + الأرصدة بشارات صلاحية (🟢🟠) — دورة واحدة."""
    from data_access import db_warehouses as dw
    from data_access import db_warehouses_stores as dws

    # بالمورد: توريدات الدورة
    item_names = {it["id"]: it["name"] for it in dw.list_items(year, month, cycle)}
    sup_map = {}
    for r in dw.list_receipts(year, month, cycle):
        name = r["supplier_name"] or "بدون مورد"
        e = sup_map.setdefault(name, {"count": 0, "qty": 0.0, "items": set()})
        e["count"] += 1
        e["qty"] += float(r["qty_handle"] or 0)
        e["items"].add(item_names.get(r["item_id"], "—"))
    sup_rows = [{"name": k, "count": v["count"], "qty": round(v["qty"], 4),
                 "items_count": len(v["items"])} for k, v in sorted(sup_map.items())]

    # بالجهة: أذون الدورة مجمعة بالجهة (المنصرف من الدفعة الفعلية)
    permits = dw.permits_book(year, month, cycle)
    ent_map = {}
    for p in permits:
        ent = p.get("entity_label") or "—"
        e = ent_map.setdefault(ent, {"permits": 0, "qty": 0.0, "items": set()})
        e["permits"] += 1
        for it in p["cycle_items"]:
            e["qty"] += float(it["qty"] or 0)
            e["items"].add(it["name"])
    ent_rows = [{"entity": k, "permits": v["permits"], "qty": round(v["qty"], 4),
                 "items_count": len(v["items"])} for k, v in sorted(ent_map.items())]

    # الأرصدة + شارات الصلاحية: لكل صنف رصيد + أقرب صلاحية متبقية (FEFO)
    try:
        balances = dw.item_balances(year, month, cycle)
    except Exception:  # noqa: BLE001
        balances = {}
    # المتبقي من كل دفعة (سلسالة) = المضاف − المنصرف من نفس السلسالة
    issued_by_serial = {}
    for t in dws.tafreeda_rows(year, month, cycle):
        issued_by_serial[t["receipt_serial"]] = \
            issued_by_serial.get(t["receipt_serial"], 0.0) + float(t["qty"] or 0)
    lots = {}   # item_id -> [(exp_date, remaining)]
    for r in dw.list_receipts(year, month, cycle):
        rem = float(r["qty_handle"] or 0) - issued_by_serial.get(r["serial"], 0.0)
        if rem > 0:
            lots.setdefault(r["item_id"], []).append((r["exp_date"] or "", rem))
    bal_rows = []
    for it in dw.list_items(year, month, cycle):
        bal = float(balances.get(it["id"], 0.0))
        badge, exp_label, days = "", "", None
        if bal > 0:
            cand = [x for x in lots.get(it["id"], []) if x[0]]
            if cand:
                exp_iso = min(x[0] for x in cand)
                d = dates.parse_date(exp_iso)
                if d:
                    days = (d - egtime.today()).days
                    exp_label = exp_iso
                    if days < 0 or days <= 30:
                        badge = "bad"
                    elif days <= 90:
                        badge = "warn"
                    else:
                        badge = "ok"
            else:
                badge = "ok"   # رصيد بلا صلاحية معروفة
        bal_rows.append({
            "name": it["name"], "unit": it["handle_unit"],
            "balance": round(bal, 4), "badge": badge,
            "exp": exp_label, "exp_days": days,
        })
    bal_rows.sort(key=lambda r: r["name"])
    return {
        "sup_rows": sup_rows,
        "ent_rows": ent_rows,
        "bal_rows": bal_rows,
        "cycle": cycle,
    }

# ==================== جرد مخزن حي (تاب المخازن داخل الإحصائيات) ====================
def stores_inventory(year, month):
    """جرد كل مخزن دلوقت: الصنف · الرصيد · دخل (تاريخ+يوم) · مين صرف · أقرب صلاحية
    متبقية · متوقع الانتهاء (من المتوسط اليومي) — الدورتين معًا."""
    from data_access import db_warehouses as dw
    from data_access import db_warehouses_stores as dws
    from core import arabic_numbers as arnum
    from core.config import MONTH_NAMES
    from datetime import timedelta

    report = dw.stores_report(year, month)

    # permit_no → جهة (الدورتين)
    permit_entity = {}
    from data_access import db_permits as dp
    for cyc in ("supply", "contractor"):
        for p in dw.permits_book(year, month, cyc):
            # كل جهة (رئيسية/ملحقة) كيان مستقل في «صرفها»
            permit_entity[p["number"]] = dp.split_entity_label(p.get("entity_label") or "") or ["—"]

    # المتبقي لكل (مخزن، صنف) من صلاحية + الإجمالي المنصرف لكل صنف (للمتوسط اليومي)
    store_lots = {}      # (store_id, item) -> [exp_date, ...] المتبقي
    issued_tot = {}      # item -> إجمالي المنصرف (للمتوسط)
    for cyc in ("supply", "contractor"):
        items = {it["id"]: it["name"] for it in dw.list_items(year, month, cyc)}
        s_issued = {}
        for t in dws.tafreeda_rows(year, month, cyc):
            if t.get("store_id") is not None:
                s_issued[(t["store_id"], t["item"])] = \
                    s_issued.get((t["store_id"], t["item"]), 0.0) + float(t["qty"] or 0)
            issued_tot[t["item"]] = issued_tot.get(t["item"], 0.0) + float(t["qty"] or 0)
        for r in dw.list_receipts(year, month, cyc):
            name = items.get(r["item_id"])
            if not name or not (r.get("exp_date") or ""):
                continue
            for part in (r.get("stores") or [{"store_id": None, "qty": r["qty_handle"]}]):
                sid = part.get("store_id")
                if sid is None:
                    continue
                rem = float(part.get("qty") or 0) - s_issued.get((sid, name), 0.0)
                if rem > 0:
                    store_lots.setdefault((sid, name), []).append(r["exp_date"])

    # وحدة كل صنف (الدورتين)
    item_units = {}
    for cyc in ("supply", "contractor"):
        for it in dw.list_items(year, month, cyc):
            item_units.setdefault(it["name"], it.get("handle_unit") or "")

    today = egtime.today()
    if (today.year, today.month) == (year, month):
        elapsed = max(1, min(today.day, egtime.days_in_month(year, month)))
    else:
        elapsed = egtime.days_in_month(year, month)

    stores = []
    for e in report["stores"]:
        sid = e["store"]["id"]
        rows = []
        for item, bal in sorted(e["balances"].items()):
            # دخل: أول حركة فيها تاريخ فعلي (date_iso أو day)
            first_inn = next((x for x in e["inn"]
                              if x["item"] == item and (x.get("date_iso") or x.get("day"))), None)
            in_label = "أول المدة"
            if first_inn:
                d = dates.parse_date(first_inn["date_iso"]) if first_inn.get("date_iso") else None
                if not d and first_inn.get("day"):
                    try:
                        from datetime import date as _date
                        d = _date(year, month, int(first_inn["day"]))
                    except (TypeError, ValueError):
                        d = None
                if d:
                    in_label = "{} {} — {}".format(arnum.to_arabic_indic(d.day),
                                                    MONTH_NAMES[d.month - 1],
                                                    egtime.weekday_ar(d))
            issuers = []
            for o in e["out"]:
                if o["item"] == item:
                    for lab in permit_entity.get(o["permit_no"], ["—"]):
                        if lab not in issuers:
                            issuers.append(lab)
            exps = [x for x in store_lots.get((sid, item), []) if x]
            exp_label, badge, exp_days = "", "", None
            if exps and bal > 0:
                exp_iso = min(exps)
                d = dates.parse_date(exp_iso)
                if d:
                    exp_days = (d - today).days
                    exp_label = exp_iso
                    badge = "bad" if exp_days <= 30 else ("warn" if exp_days <= 90 else "ok")
            pace = issued_tot.get(item, 0.0) / elapsed
            out_est = ""
            if bal > 0 and pace > 0:
                left = bal / pace
                out_est = "~{} يوم".format(arnum.to_arabic_indic(max(1, round(left))))
            rows.append({
                "item": item, "unit": item_units.get(item, ""),
                "balance": round(bal, 4),
                "in_label": in_label, "issuers": issuers[:3],
                "issuers_more": max(0, len(issuers) - 3),
                "exp": exp_label, "badge": badge, "exp_days": exp_days,
                "out_est": out_est,
            })
        stores.append({
            "id": sid, "name": e["store"]["name"],
            "capacity": e["store"].get("capacity_m2") or "",
            "total": e.get("total") or 0.0, "items": len(e["balances"]),
            "rows": rows,
        })
    un = report["unassigned"]
    un_rows = [{
        "item": item, "unit": "", "balance": round(bal, 4),
        "in_label": "—", "issuers": [], "issuers_more": 0,
        "exp": "", "badge": "", "exp_days": None, "out_est": "",
    } for item, bal in sorted(un["balances"].items())]
    return {"stores": stores, "unassigned_items": len(un["balances"]),
            "unassigned_rows": un_rows}
