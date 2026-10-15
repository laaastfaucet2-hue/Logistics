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
    # صرف الترفية المباشر (issue2) بيتسجل في الدفتر نفسه — عمود «المَنصُرف»
    # لازم يعكسه وإلّا الرصيد بيطرحه والعمود يظل صفراً (اكتشاف اختبار ١٢/١٠)
    conn = dw._conn(year, month)
    ledger_issued = {r[0]: float(r[1] or 0) for r in conn.execute(
        "SELECT item_id, SUM(issued) FROM wh_ledger WHERE cycle=? "
        "AND kind='issue2' GROUP BY item_id", (cycle,))}
    conn.close()
    for it in dw.list_items(year, month, cycle):
        name = it["name"]
        items.append({
            "name": name,
            "unit": it["handle_unit"],
            "supplied": supplied.get(name, 0.0),
            "issued": issued.get(name, 0.0) + ledger_issued.get(it["id"], 0.0),
            "balance": balances.get(it["id"], 0.0),
        })
    items.sort(key=lambda x: x["name"])
    issued_total = sum(x["issued"] for x in items)
    top5 = [(x["name"], x["issued"]) for x in sorted(
        items, key=lambda x: (-x["issued"], x["name"]))[:5]]
    return {
        "item_rows": items,
        "top5": top5,
        "items_count": len(items),
        "supplied_total": sum(supplied.values()),
        "issued_total": issued_total,
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
        matrix = dbb.totals_matrix(year, month, 1, eom)
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
        name = r["supplier_name"] or "دون مورد"
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
