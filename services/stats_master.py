# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""محرك الإحصائيات الرئيسي (القسم ٠٩) — التتبع والاستهلاك.

ثلاث دورات متفصلة تمامًا (الإمداد / المتعهد / الترفية) × نطاقين (شهر/سنة):
- التوريد:  wh_receipts (1 مخازن) — الصنف/المورّد/المنتج/الكمية/التواريخ
- الصرف:    tafreeda_rows (FEFO) + permits (الجهة) + المورّد من الدفعة الفعلية
- المتوسط:  إجمالي صرف الفترة ÷ أيامها لكل صنف + الرصيد الحالي

لا جداول جديدة — كله محسوب من month.db (عزل شهري: عرض السنة = جمع شهورها).
"""
from core import egtime, dates
from core.config import MONTH_NAMES
from data_access import db_warehouses as dw
from data_access import db_warehouses_stores as dws
from data_access import db_permits as dp

CYCLES = (
    ("supply", "الإمداد", "🚚"),
    ("contractor", "المتعهد", "🧾"),
    ("tarfea", "الترفية", "🎖️"),
)
CYCLE_KEYS = tuple(c[0] for c in CYCLES)


def months_of_year(year):
    """الشهور الموجودة من سنة (month.db موجود) — لعرض السنة."""
    from data_access import storage
    from core.config import month_folder
    out = []
    for m in range(1, 13):
        if (storage.year_path(year) / month_folder(m) / "month.db").exists():
            out.append(m)
    return out


# ==================== التوريد (1 مخازن) ====================
def _supply_m(year, month, cycle):
    conn = dw._conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT r.*, i.name AS item_name FROM wh_receipts r"
        " JOIN wh_items i ON r.item_id = i.id"
        " WHERE r.cycle=? ORDER BY r.date_iso, r.serial, r.id", (cycle,))]
    conn.close()
    for r in rows:
        r["item"] = r["item_name"]
        r["month"] = month
        r["date_label"] = _day_label(year, month, r.get("day") or 1, r.get("date_iso") or "")
    return rows


def _day_label(year, month, day, date_iso=""):
    """تسمية اليوم كاملة: «٤ أكتوبر — السبت» (قاعدة: التاريخ مع يوم الأسبوع)."""
    from datetime import date
    d = dates.parse_date(date_iso) if date_iso else None
    if not d:
        try:
            d = date(year, month, int(day))
        except (TypeError, ValueError):
            return ""
    return "{} {} — {}".format(d.day, MONTH_NAMES[d.month - 1], egtime.weekday_ar(d))


def supply_rows(year, month, cycle, scope):
    if scope == "year":
        out = []
        for m in months_of_year(year):
            out.extend(_supply_m(year, m, cycle))
        return out
    return _supply_m(year, month, cycle)


# ==================== الصرف بالتتبع (2 مخازن — FEFO) ====================
def _issue_m(year, month, cycle):
    permits = {p["number"]: p for p in dw.permits_book(year, month, cycle)}
    conn = dw._conn(year, month)
    sup_by_pair, sup_by_serial = {}, {}
    for r in conn.execute(
            "SELECT serial, supplier_name, item_id FROM wh_receipts WHERE cycle=?", (cycle,)):
        sup_by_serial.setdefault(r["serial"], r["supplier_name"] or "")
    items = {it["id"]: it["name"] for it in
             [dict(x) for x in conn.execute("SELECT id, name FROM wh_items WHERE cycle=?", (cycle,))]}
    conn.close()
    out = []
    for row in dws.tafreeda_rows(year, month, cycle):
        permit = permits.get(row["permit_no"]) or {}
        out.append({
            "permit_no": row["permit_no"],
            "date_from": row["date_from"],
            "date_to": row["date_to"],
            "entity": permit.get("entity_label") or "—",
            "entities": dp.split_entity_label(permit.get("entity_label") or ""),
            "item": row["item"],
            "unit": row["unit"],
            "qty": row["qty"],
            "issued_label": row.get("issued_label") or "",
            "supplier": sup_by_serial.get(row["receipt_serial"], ""),
            "producer": row.get("producer") or "",
            "expiry": row.get("expiry") or "",
            "store": row.get("store_name") or "",
            "month": month,
        })
    return out


def issue_rows(year, month, cycle, scope):
    if scope == "year":
        out = []
        for m in months_of_year(year):
            out.extend(_issue_m(year, m, cycle))
        return out
    return _issue_m(year, month, cycle)


# ==================== متوسط الاستهلاك لكل صنف ====================
def _totals_m(year, month, cycle):
    """(توريد لكل صنف, صرف فعلي FEFO لكل صنف) لشهر."""
    supplied, issued = {}, {}
    for r in _supply_m(year, month, cycle):
        supplied[r["item"]] = supplied.get(r["item"], 0.0) + float(r["qty_handle"] or 0)
    for (_pn, item), qty in dws.fefo_actual_map(year, month, cycle).items():
        issued[item] = issued.get(item, 0.0) + float(qty or 0)
    return supplied, issued


def _balances(y, m, cycle):
    """{اسم الصنف: الرصيد النهائي} — من رصيد أول المدة + الإضافات − منصرف الإذون."""
    try:
        balances = dw.item_balances(y, m, cycle)
    except Exception:  # noqa: BLE001 — دورة بلا أصناف
        return {}
    items = {it["id"]: it["name"] for it in dw.list_items(y, m, cycle)}
    return {items[k]: v for k, v in balances.items() if k in items}


def avg_rows(year, month, cycle, scope):
    """متوسط الاستهلاك لكل صنف: {item, unit, supplied, issued, avg, balance}."""
    if scope == "year":
        supplied, issued = {}, {}
        for m in months_of_year(year):
            s, i = _totals_m(year, m, cycle)
            for k, v in s.items():
                supplied[k] = supplied.get(k, 0.0) + v
            for k, v in i.items():
                issued[k] = issued.get(k, 0.0) + v
        days = 365
        balances = _balances(year, month, cycle)   # الرصيد = من الشهر النشط
        month_list = months_of_year(year)
    else:
        supplied, issued = _totals_m(year, month, cycle)
        days = egtime.days_in_month(year, month)
        balances = _balances(year, month, cycle)
        month_list = [month]
    units = {}
    for m in month_list:
        for it in dw.list_items(year, m, cycle):
            units[it["name"]] = it["handle_unit"]
    all_items = sorted(set(supplied) | set(issued) | set(units))
    rows = []
    for name in all_items:
        iss = issued.get(name, 0.0)
        rows.append({
            "item": name,
            "unit": units.get(name, ""),
            "supplied": supplied.get(name, 0.0),
            "issued": iss,
            "avg": round(iss / days, 4) if days else 0.0,
            "balance": balances.get(name, 0.0),
        })
    rows.sort(key=lambda r: (-r["avg"], r["item"]))
    return rows


def year_issue_total(year, cycle):
    """إجمالي صرف السنة (كل شهورها) — بالوحدة."""
    total = 0.0
    for m in months_of_year(year):
        _s, i = _totals_m(year, m, cycle)
        total += sum(i.values())
    return total


def year_ratio_prev(year, cycle):
    """نسبة تغيّر متوسط السنة اليومي عن السنة اللي فاتت (٪) أو None.
    (المقسم 365 يلغى في النسبة — المقارنة على الإجماليات مباشرة)."""
    try:
        cur = year_issue_total(year, cycle)
        prev = year_issue_total(year - 1, cycle)
        if cur and prev:
            return round((cur - prev) / prev * 100)
    except Exception:  # noqa: BLE001 — المقارنة تجميلية
        pass
    return None


def issue_ratio_prev(year, month, cycle):
    """نسبة تغيّر المتوسط اليومي الكلي عن الشهر اللي فات (٪) أو None."""
    from data_access import storage
    from core.config import month_folder
    if month > 1:
        py, pm = (year, month - 1)
    else:
        py, pm = (year - 1, 12)
    try:
        if not (storage.year_path(py) / month_folder(pm) / "month.db").exists():
            return None
        days = egtime.days_in_month(year, month)
        prev_days = egtime.days_in_month(py, pm)
        _s, iss_now = _totals_m(year, month, cycle)
        _s2, iss_prev = _totals_m(py, pm, cycle)
        tot_now, tot_prev = sum(iss_now.values()), sum(iss_prev.values())
        if tot_now and tot_prev:
            a, b = tot_now / days, tot_prev / prev_days
            return round((a - b) / b * 100)
    except Exception:  # noqa: BLE001 — المقارنة تجميلية
        pass
    return None


# ==================== خيارات الفلاتر (من الموجود فعليًا) ====================
def options(year, month, cycle, scope):
    months = months_of_year(year) if scope == "year" else [month]
    items, suppliers, producers, entities = set(), set(), set(), set()
    for m in months:
        for it in dw.list_items(year, m, cycle):
            items.add(it["name"])
        for s in dw.list_suppliers(year, m, cycle):
            if s["name"]:
                suppliers.add(s["name"])
        try:
            conn = dw._conn(year, m)
            for r in conn.execute(
                    "SELECT DISTINCT producer FROM wh_receipts WHERE cycle=? AND producer<>''", (cycle,)):
                producers.add(r["producer"])
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        for p in dw.permits_book(year, m, cycle):
            # كل جهة (رئيسية أو ملحقة) ترشح في القائمة — مش الوسم المجمّع
            entities.update(dp.split_entity_label(p.get("entity_label") or ""))
    return {
        "items": sorted(items),
        "suppliers": sorted(suppliers),
        "producers": sorted(producers),
        "entities": sorted(entities),
    }


# ==================== الفلترة ====================
def apply_filters(supply, issue, avg, f):
    """f = {item, supplier, producer, entity} — تطابق تام على القيم المختارة."""
    item = (f.get("item") or "").strip()
    supplier = (f.get("supplier") or "").strip()
    producer = (f.get("producer") or "").strip()
    entity = (f.get("entity") or "").strip()

    def keep(r, item_key, sup_key, prod_key, ent_key=None):
        if item and r.get(item_key) != item:
            return False
        if supplier and r.get(sup_key) != supplier:
            return False
        if producer and r.get(prod_key) != producer:
            return False
        if ent_key and entity and entity not in (
                r.get("entities") or [r.get(ent_key) or ""]):
            return False
        return True

    issue_f = [r for r in issue if keep(r, "item", "supplier", "producer", "entity")]
    # التوريد: فلتر الجهة = التوريدات للأصناف اللي صرفتها الجهة دي في الفترة
    entity_items = {r["item"] for r in issue_f} if entity else None
    supply_f = [r for r in supply if keep(r, "item", "supplier_name", "producer")
                and (not entity or r["item"] in entity_items)]
    avg_items = {r["item"] for r in supply_f} | {r["item"] for r in issue_f}
    if not (item or supplier or producer or entity):
        avg_f = avg
    else:
        avg_f = [r for r in avg if r["item"] in avg_items]
    return supply_f, issue_f, avg_f


def summary(supply_f, issue_f, avg_f):
    """كروت الملخص الستة."""
    from core import arabic_numbers as arnum
    sup_qty = sum(float(r["qty_handle"] or 0) for r in supply_f)
    iss_qty = sum(float(r["qty"] or 0) for r in issue_f)
    permits = {r["permit_no"] for r in issue_f}
    entities = {n for r in issue_f for n in (r.get("entities") or [])}
    items_moved = {r["item"] for r in supply_f} | {r["item"] for r in issue_f}
    return {
        "sup_count": len(supply_f), "sup_qty": round(sup_qty, 4),
        "iss_count": len(issue_f), "iss_qty": round(iss_qty, 4),
        "permit_count": len(permits),
        "entity_count": len(entities),
        "item_count": len(items_moved),
        "shortfall": 0,   # يُملأ من سطور العجز في الـ template عند الحاجة
    }

# ======================================================================
# تابات الأقسام داخل التاب الرئيسي — تبويبات فرعية فوق، المستخدم يختار (توجيه ١٠/١٠)
# ======================================================================
SECTION_DEFS = {
    "supply": (
        ("health", "🏥", "الصحة"),
        ("stores", "🏬", "المخازن والثلاجات"),
        ("raghibin", "🙋", "الراغبين"),
        ("tameedat", "🚚", "التاميدات"),
        ("rations_tamween", "🥣", "مقررات التموين"),
        ("wh_supply", "📦", "مستودعات الإمداد"),
    ),
    "contractor": (
        ("rations_contractor", "🧾", "مقررات المتعهد"),
        ("wh_contractor", "📦", "مستودعات المتعهد"),
    ),
    "tarfea": (
        ("tarfea", "🎖️", "الترفية"),
    ),
}


def section_defs(cycle):
    """تبويبات التاب الرئيسي: «التتبع» (الرئيسي) + الأقسام التابعة للدورة."""
    return (("track", "📊", "التتبع"),) + SECTION_DEFS.get(cycle, ())


def section_keys(cycle):
    return tuple(k for k, _i, _n in SECTION_DEFS.get(cycle, ()))


def section_detail(cycle, year, month, key):
    """تفاصيل تاب قسم واحد — كروت + جدول مصغّر (حي من month.db).

    كل قسم: {key, icon, title, hint, cards:[C(...)], head:[..], rows:[[cell,...]]}
    """
    from services import stats_sections as ssec
    from core import arabic_numbers as arnum

    def C(label, value, sub="", cls=""):
        return {"label": label, "value": value, "sub": sub, "cls": cls}

    def cell(text, cls="", kind=""):
        return {"t": text, "c": cls, "k": kind}

    BADGE_TEXT = {"ok": "سليم ✔", "warn": "قرب/متأخر", "bad": "متأخر"}
    icon = name = ""
    for k, i, n in SECTION_DEFS.get(cycle, ()):
        if k == key:
            icon, name = i, n
            break
    base = {"key": key, "icon": icon, "title": name, "hint": "",
            "cards": [], "head": [], "rows": []}

    # ─────────── دورة الإمداد ───────────
    if key == "health":
        h = ssec.health_stats(year, month)
        base.update({
            "title": "الصحة — المجندين",
            "hint": "من قسم الصحة والكشف الدوري على المجندين",
            "cards": [
                C("مجندين بالقائمة", arnum.to_arabic_indic(h["roster_count"])),
                C("تم كشفهم", arnum.to_arabic_indic(h["unique_checked"]),
                  "خلال أيام الكشف", "good"),
                C("أيام كشف", arnum.to_arabic_indic(h["checked_days"]),
                  "من {} يوم".format(arnum.to_arabic_indic(h["days_count"])) if h["days_count"] else "لا أيام"),
                C("عدم توقيع الكشف الطبى", arnum.to_arabic_indic(len(h["no_checkup"])),
                  "لم يوقع عليهم الكشف", "warn" if h["no_checkup"] else "good"),
            ],
            "head": ["التقرير", "الموقف", "الشارة"],
            "rows": [[
                cell("الرش والتعقيم"), cell(h["spray"]["label"]),
                cell(BADGE_TEXT[h["spray"]["badge"]], h["spray"]["badge"]),
            ], [
                cell("تطهير الخزانات"), cell(h["tanks"]["label"] + (
                    " • {} خزان".format(arnum.to_arabic_indic(h["tank_count"])) if h["tank_count"] else "")),
                cell(BADGE_TEXT[h["tanks"]["badge"]], h["tanks"]["badge"]),
            ], [
                cell("فحص مياه الشرب"), cell(h["water"]["label"]),
                cell(BADGE_TEXT[h["water"]["badge"]], h["water"]["badge"]),
            ]],
        })
    elif key == "stores":
        st = ssec.stores_stats(year, month)
        exp = st["expiring"]
        inv = ssec.stores_inventory(year, month)
        base.update({
            "hint": "حركة وكشف أرصدة — بالدورتين معًا (إمداد + متعهد) · جرد حي لكل مخزن",
            "cards": [
                C("مخازن", arnum.to_arabic_indic(st["stores_count"])),
                C("دفعات قريبة/متأخرة", arnum.to_arabic_indic(exp["warn"] + exp["bad"]),
                  "{} خطرة".format(arnum.to_arabic_indic(exp["bad"])),
                  "bad" if exp["bad"] else "warn" if exp["warn"] else "good"),
                C("أصناف بالجرد", arnum.to_arabic_indic(sum(r["items"] for r in st["rows"]))),
            ],
            "head": ["توب الاستهلاك", "الكمية المنصرفة"],
            "rows": [[cell(name, "", "item"), cell(arnum.to_arabic_indic(qty))] for name, qty in st["top5"][:3]],
            "inventory": inv["stores"],
            "inventory_unassigned": inv["unassigned_items"],
        })
    elif key == "raghibin":
        rg = ssec.raghibin_stats(year, month)
        base.update({
            "hint": "من قسم الراغبين — نسبة الراغبين لكل جهة",
            "cards": [
                C("قوة إجمالية", arnum.to_arabic_indic(rg["total"])),
                C("راغبين", arnum.to_arabic_indic(rg["willing"]),
                  "{}٪".format(arnum.to_arabic_indic(rg["pct"])), "good"),
                C("غير راغبين", arnum.to_arabic_indic(rg["excluded"]),
                  "بسبب موثق", "warn" if rg["excluded"] else "good"),
            ],
            "head": ["الجهة", "النوع", "راغب", "إجمالي", "النسبة"],
            "rows": [[
                cell(r["name"], "", "entity"), cell(r["entity_type"]),
                cell(arnum.to_arabic_indic(r["willing"]), "num"),
                cell(arnum.to_arabic_indic(r["total"]), "num"),
                cell("{}٪".format(arnum.to_arabic_indic(r["pct"])),
                     "good" if r["pct"] >= 90 else ("warn" if r["pct"] >= 60 else "bad")),
            ] for r in rg["entity_rows"]],
        })
    elif key == "tameedat":
        tm = ssec.tameedat_stats(year, month)
        tot = tm["totals"]
        base.update({
            "hint": "من قسم التاميدات — إجماليات المومَّدين بالجهة",
            "cards": [
                C("تأميدات", arnum.to_arabic_indic(tot["records"])),
                C("مومَّدين (إجمالي)", arnum.to_arabic_indic(tot["grand"]),
                  "{} ضابط و{} فرد".format(arnum.to_arabic_indic(tot["officers"]),
                                          arnum.to_arabic_indic(tot["individuals"]))),
                C("جهة مومَّدة", arnum.to_arabic_indic(tot["entities"])),
            ],
            "head": ["الجهة", "النوع", "عدد التأميدات", "أيام", "المومَّدين"],
            "rows": [[
                cell(r["name"], "", "entity"), cell(r["entity_type"]),
                cell(arnum.to_arabic_indic(r["records"]), "num"),
                cell(arnum.to_arabic_indic(r["active_days"]), "num"),
                cell(arnum.to_arabic_indic(r["grand"]), "num b"),
            ] for r in tm["entity_rows"]],
            "top5": [{"name": r["name"], "grand": r["grand"]}
                     for r in tm["entity_rows"] if r["grand"] > 0][:5],
        })
    elif key in ("rations_tamween", "rations_contractor"):
        section = "tamween" if key == "rations_tamween" else "contractor"
        ra = ssec.rations_stats(year, month, section)
        total_dist = sum(r["qty"] for r in ra["dist_rows"])
        base.update({
            "hint": "النوع المفعّل + توزيع الصرف على الجهات (من ٢ مخازن)",
            "cards": [
                C("النوع المفعّل", next((k["name"] for k in ra["kinds"] if k["active"]), "—"),
                  "من {} أنواع".format(arnum.to_arabic_indic(sum(1 for k in ra["kinds"] if k["count"]))),
                  "good" if ra["active"] else "warn"),
                C("أصناف المفعّل", arnum.to_arabic_indic(next((k["count"] for k in ra["kinds"] if k["active"]), 0))),
                C("جهات استلمت", arnum.to_arabic_indic(len(ra["dist_rows"]))),
                C("إجمالي توزيع", arnum.to_arabic_indic(total_dist)),
            ],
            "head": ["الجهة", "أذون", "أصناف", "الكمية"],
            "rows": [[
                cell(r["entity"], "", "entity"),
                cell(arnum.to_arabic_indic(r["permits"]), "num"),
                cell(arnum.to_arabic_indic(r["items_count"]), "num"),
                cell(arnum.to_arabic_indic(r["qty"]), "num b"),
            ] for r in ra["dist_rows"]],
        })
    elif key in ("wh_supply", "wh_contractor"):
        cycle_w = "supply" if key == "wh_supply" else "contractor"
        wh = ssec.warehouses_stats(year, month, cycle_w)
        base.update({
            "hint": "بالمورد وبالجهة + الأرصدة (أقرب دفعة متبقية FEFO)",
            "cards": [
                C("موردين", arnum.to_arabic_indic(len(wh["sup_rows"]))),
                C("أذون توريد", arnum.to_arabic_indic(sum(r["count"] for r in wh["sup_rows"]))),
                C("جهات صرف", arnum.to_arabic_indic(len(wh["ent_rows"]))),
            ],
            "head": ["الصنف", "الرصيد", "أقرب صلاحية متبقية"],
            "rows": [[
                cell(r["name"], "", "item"),
                cell(arnum.to_arabic_indic(r["balance"]), "num b"),
                cell(r["exp"] or "—", r["badge"] if r["balance"] > 0 else ""),
            ] for r in wh["bal_rows"][:6]],
        })
    elif key == "tarfea":
        tf = ssec.tarfea_stats(year, month)
        base.update({
            "hint": "الدورة المستقلة — التوريد من ١ مخازن والصرف من الدفعة الفعلية (FEFO)",
            "cards": [
                C("أصناف", arnum.to_arabic_indic(tf["items_count"])),
                C("مُورَّد", arnum.to_arabic_indic(tf["supplied_total"]), "وحدة"),
                C("مَنصُرف", arnum.to_arabic_indic(tf["issued_total"]), "وحدة", "good"),
                C("مخازن التوزيع", arnum.to_arabic_indic(len(tf["stores"]))),
            ],
            "head": ["الصنف", "الوحدة", "المورَّد", "المَنصُرف", "الرصيد"],
            "rows": [[
                cell(r["name"], "", "item"), cell(r["unit"]),
                cell(arnum.to_arabic_indic(r["supplied"]), "num"),
                cell(arnum.to_arabic_indic(r["issued"]), "num"),
                cell(arnum.to_arabic_indic(r["balance"]), "num b"),
            ] for r in tf["item_rows"]],
        })

    return base
