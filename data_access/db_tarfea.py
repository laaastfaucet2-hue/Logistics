# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""دورة «الترفية» — دورة ثالثة (cycle='tarfea') على محرك المخازن نفسه:

- الكتالوج والأذون والدفتر في جداول wh_* بعمود cycle='tarfea' (عزل تام).
- ٢ مخازن ترفية: صرف يدوي من الصنف — جدول tarfea_issues + سطر منصرف في wh_ledger
  (kind='issue2') فتظهر في كارت ٣ مخازن والأرصدة تلقائيًا.
- ٥ مخازن: سجل يومي **مشتقّ** من رصيد أول المدة وأذون ١ مخازن وصرف ٢ مخازن —
  الكميات بالمعيار (وحدة التعامل) وليس بالتغليف، ومرتبط بالتابات الأخرى (توجيه ٢٩/٠٩).
"""
from core import arabic_numbers as arnum
from core.arabic_numbers import fmt_qty, to_arabic_indic
from data_access import months
from data_access import db_warehouses as dw

CYCLE = "tarfea"


def _conn(year, month):
    conn = months.get_db(year, month)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tarfea_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial INTEGER NOT NULL,
            day INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            qty REAL NOT NULL,
            unit TEXT DEFAULT '',
            receiver TEXT DEFAULT '',
            responsible TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
    """)
    return conn


# ==================== الأصناف (الكتالوج) ====================
def add_item(year, month, name, handle_unit):
    """تسجيل صنف جديد بالاسم ووحدة التعامل — وحدة القاعدة من جدول التحويلات."""
    item, created = dw.resolve_item(year, month, CYCLE, name, handle_unit)
    return item, created


def update_item_unit(year, month, item_id, handle_unit):
    """تغيير وحدة التعامل قبل أول حركة فقط (زي ٣ مخازن في المخازن)."""
    item = dw.get_item(year, month, item_id, CYCLE)
    if not item:
        raise ValueError("الصنف غير موجود في كتالوج الترفية")
    if dw.item_has_movement(year, month, CYCLE, item_id):
        raise ValueError("ممنوع تغيير وحدة التعامل بعد أول حركة على الصنف")
    dw.set_handle_unit(year, month, item_id, handle_unit)


def rename_item(year, month, item_id, name):
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("اكتب اسم الصنف")
    conn = _conn(year, month)
    twin = conn.execute("SELECT id FROM wh_items WHERE cycle=? AND name=?",
                        (CYCLE, name)).fetchone()
    if twin and twin["id"] != item_id:
        conn.close()
        raise ValueError("اسم «{}» مستخدم لصنف آخر في الترفية".format(name))
    with conn:
        conn.execute("UPDATE wh_items SET name=? WHERE id=? AND cycle=?",
                     (name, item_id, CYCLE))
    conn.close()


def delete_item(year, month, item_id):
    """حذف الصنف **بدورته كاملة** (توجيه ٢٩/٠٩): الإيذانات والحركات والافتتاحي
    والتغليف المسجل وإذون صرف ٢ مخازن — كل حاجة بتاعته تتمسح."""
    item = dw.get_item(year, month, item_id, CYCLE)
    if not item:
        raise ValueError("الصنف غير موجود في كتالوج الترفية")
    name = item["name"]
    conn = _conn(year, month)
    with conn:
        conn.execute("DELETE FROM tarfea_issues WHERE item_id=?", (item_id,))
        conn.execute("DELETE FROM wh_ledger WHERE cycle=? AND item_id=?",
                     (CYCLE, item_id))
        conn.execute("DELETE FROM wh_opener_stores WHERE cycle=? AND item_id=?",
                     (CYCLE, item_id))
        conn.execute("DELETE FROM wh_receipt_stores WHERE receipt_id IN"
                     " (SELECT id FROM wh_receipts WHERE cycle=? AND item_id=?)",
                     (CYCLE, item_id))
        conn.execute("DELETE FROM wh_receipts WHERE cycle=? AND item_id=?",
                     (CYCLE, item_id))
        conn.execute("DELETE FROM wh_pack_specs WHERE cycle=? AND item_id=?",
                     (CYCLE, item_id))
        conn.execute("DELETE FROM wh_items WHERE id=? AND cycle=?",
                     (item_id, CYCLE))
    conn.close()
    return name


def list_items(year, month):
    return dw.list_items(year, month, CYCLE)


# ==================== ١ مخازن — إذون الإضافة (محرك المخازن) ====================
def add_receipt(year, month, **kwargs):
    return dw.add_receipt(year, month, CYCLE, **kwargs)


def delete_receipt(year, month, serial):
    dw.delete_receipt(year, month, CYCLE, serial)


def receipt_groups(year, month):
    return dw.receipt_groups(year, month, CYCLE)


def list_receipts(year, month):
    return dw.list_receipts(year, month, CYCLE)


# ==================== ٣ مخازن — الرصيد الافتتاحي والكروت ====================
def add_opener(year, month, **kwargs):
    return dw.add_opener(year, month, CYCLE, **kwargs)


def item_card(year, month, item_id):
    return dw.item_card(year, month, item_id)


def tafreeda_rows(year, month):
    return dw.tafreeda_rows(year, month, CYCLE)


def stock_report(year, month):
    """كشف جرد الأرصدة: آخر رصيد لكل صنف (توجيه ٢٨/٠٩ نفس قاعدة المخازن)."""
    out = []
    for it in list_items(year, month):
        card = dw.item_card(year, month, it["id"]) or {}
        rows = card.get("rows") or []
        last = rows[-1]["balance"] if rows else 0.0
        out.append({"name": it["name"], "unit": it["handle_unit"],
                    "base_unit": it["base_unit"], "balance": last})
    return out


# ==================== ٢ مخازن — إذون الصرف اليدوية ====================
def next_issue_serial(year, month):
    conn = _conn(year, month)
    row = conn.execute("SELECT MAX(serial) AS m FROM tarfea_issues").fetchone()
    conn.close()
    return (row["m"] or 0) + 1


def add_issue(year, month, day, item_id, qty, receiver="",
              responsible="", notes="", serial=None):
    """صرف من صنف بالكمية (بوحدة تعامله) — سطر منصرف في الدفتر + سجل ٢ مخازن."""
    item = dw.get_item(year, month, item_id, CYCLE)
    if not item:
        raise ValueError("اختر صنفًا من كتالوج الترفية")
    qty = float(qty or 0)
    if qty <= 0:
        raise ValueError("اكتب الكمية المنصرفة")
    # لا رصيد سالب: مجموع المنصرف لا يتجاوز المتاح
    card = dw.item_card(year, month, item_id) or {}
    rows = card.get("rows") or []
    balance = rows[-1]["balance"] if rows else 0.0
    if qty > balance + 1e-9:
        raise ValueError("الرصيد لا يكفي: المتاح {} {} فقط".format(
            balance, item["handle_unit"]))
    serial = int(serial) if serial else next_issue_serial(year, month)
    conn = _conn(year, month)
    from core import egtime
    stamp = egtime.now().isoformat(timespec="seconds")
    date_iso = "{:04d}-{:02d}-{:02d}".format(year, month, day)
    label = "صرف ٢ مخازن ترفية — إلى: {}".format((receiver or "—").strip())
    with conn:
        conn.execute(
            "INSERT INTO tarfea_issues (serial, day, item_id, qty, unit,"
            " receiver, responsible, notes, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (serial, day, item_id, qty, item["handle_unit"],
             (receiver or "").strip(), (responsible or "").strip(),
             (notes or "").strip(), stamp))
        conn.execute(
            "INSERT INTO wh_ledger (cycle,item_id,day,date_iso,kind,permit_no,label,"
            "added,issued,balance,notes,created_at)"
            " VALUES (?,?,?,?,?,?,?,0,?,0,?,?)",
            (CYCLE, item_id, day, date_iso, "issue2", serial, label,
             qty, (notes or "").strip(), stamp))
    conn.close()
    return serial


def delete_issue(year, month, issue_id):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM tarfea_issues WHERE id=?",
                       (issue_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("إذن الصرف غير موجود")
    with conn:
        conn.execute("DELETE FROM wh_ledger WHERE cycle=? AND kind='issue2'"
                     " AND permit_no=?", (CYCLE, row["serial"]))
        conn.execute("DELETE FROM tarfea_issues WHERE id=?", (issue_id,))
    conn.close()
    return row


def list_issues(year, month):
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT i.*, w.name AS item_name FROM tarfea_issues i"
        " LEFT JOIN wh_items w ON w.id = i.item_id ORDER BY i.day, i.id").fetchall()]
    conn.close()
    return rows


# ==================== ٥ مخازن — السجل اليومي المشتق ====================
def t5_rows(year, month):
    """سجل ٥ مخازن مشتقّ بالكامل: opener + أذون ١ مخازن + صرف ٢ مخازن —
    القيم بالمعيار (وحدة التعامل) وليس بالتغليف (توجيه المستخدم ٢٩/٠٩)."""
    items = {it["id"]: it for it in list_items(year, month)}
    rows = []
    # رصيد أول المدة
    for it in items.values():
        card = dw.item_card(year, month, it["id"]) or {}
        for r in card.get("rows") or []:
            if r.get("kind") == "opener":
                rows.append({"day": r["day"], "permit_no": 0,
                             "party": "رصيد أول المدة",
                             "added": int(r["added"]) if float(r["added"] or 0).is_integer()
                             else round(float(r["added"] or 0), 3),
                             "issued": 0.0, "unit": it["handle_unit"],
                             "kind": "opener", "serial": 0,
                             "details": "افتتاحي «{}»".format(it["name"]),
                             "responsible": "", "issue_id": 0})
    # أذون ١ مخازن — تجميع بإذن (سطر واحد لكل إذن بالكمية الكلية بالمعيار)
    def _n(x):
        x = float(x or 0)
        return int(x) if x.is_integer() else round(x, 3)

    def _a(x):
        """الرقم بأرقام عربية منسوبة للعرض في تفاصيل السجل."""
        return fmt_qty(float(x)).rstrip("0").rstrip("٫")

    groups = {}
    for r in list_receipts(year, month):
        g = groups.setdefault(r["serial"], {"day": r["day"], "added": 0.0,
                                            "names": [], "units": [],
                                            "party": "", "notes": ""})
        g["added"] += r["qty_handle"] or 0
        g["names"].append("{} {}".format(_a(r["qty_handle"]), r["unit"] or ""))
        if r["unit"] and r["unit"] not in g["units"]:
            g["units"].append(r["unit"])
        g["party"] = r["supplier_name"] or r["producer"] or "إذن إضافة"
        g["notes"] = r["notes"] or ""
    for serial in sorted(groups):
        g = groups[serial]
        rows.append({"day": g["day"], "permit_no": serial,
                     "party": "وارد من: " + g["party"], "added": _n(g["added"]),
                     "issued": 0.0,
                     "unit": g["units"][0] if len(g["units"]) == 1
                     else "مختلط" if g["units"] else "",
                     "kind": "wh1", "serial": serial,
                     "details": "إذن إضافة ١ مخازن ({}): {}".format(
                         to_arabic_indic(str(len(g["names"]))),
                         " + ".join(g["names"])),
                     "responsible": "", "issue_id": 0})
    # إذون صرف ٢ مخازن
    for i in list_issues(year, month):
        rows.append({"day": i["day"], "permit_no": i["serial"],
                     "party": "منصرف إلى: " + (i["receiver"] or "—"),
                     "added": 0.0, "issued": int(i["qty"]) if float(i["qty"]).is_integer()
                     else round(float(i["qty"]), 3),
                     "unit": i["unit"] or (items.get(i["item_id"], {})
                                           .get("handle_unit", "")),
                     "kind": "wh2", "serial": i["serial"],
                     "details": "صرف «{}»{}".format(
                         i["item_name"] or "—",
                         " — " + i["notes"] if i["notes"] else ""),
                     "responsible": i["responsible"] or "",
                     "issue_id": i["id"]})
    rows.sort(key=lambda x: (x["day"], x["kind"] != "opener",
                             x["permit_no"], x["kind"]))
    return rows


# ==================== مخزن الترفية — مخزن مستقل تمامًا (توجيه ٢٨/٠٩ ليلًا) ====================
STORE_NAME = "مخزن الترفية"


def store_report(year, month):
    """تقرير مخزن الترفية: وارد (افتتاحي/إيذانات الإضافة بتوزيعها) + منصرف
    (إيذان صرف ٢ مخازن ترفية) + الأرصدة بالكمية والتغليف — منفصل عن كل الدورات."""
    conn = months.get_db(year, month)
    openers = [dict(r) for r in conn.execute(
        "SELECT * FROM wh_ledger WHERE cycle='tarfea' AND kind='opener'")]
    receipts = [dict(r) for r in conn.execute(
        "SELECT * FROM wh_receipts WHERE cycle='tarfea' ORDER BY day, serial")]
    conn.close()
    items = {it["id"]: it for it in list_items(year, month)}
    opener_parts = dw.opener_stores(year, month, CYCLE)

    inn = []
    for o in openers:
        it = items.get(o["item_id"])
        if not it or not (o["added"] or 0):
            continue
        parts = opener_parts.get(o["item_id"]) or [
            {"store_id": None, "store_name": STORE_NAME, "qty": float(o["added"])}]
        for p in parts:
            inn.append({"date_iso": o["date_iso"], "item": it["name"],
                        "unit": it["handle_unit"], "qty": float(p["qty"] or 0),
                        "pack_label": o["pack_label"] or "",
                        "doc": "رصيد أول المدة"})
    receipt_stores = {}
    if receipts:
        conn = months.get_db(year, month)
        marks = ",".join("?" for _ in receipts)
        for r in conn.execute(
                "SELECT * FROM wh_receipt_stores WHERE receipt_id IN ({})".format(marks),
                [x["id"] for x in receipts]).fetchall():
            receipt_stores.setdefault(r["receipt_id"], []).append(dict(r))
        conn.close()
    for r in receipts:
        it = items.get(r["item_id"])
        if not it:
            continue
        parts = receipt_stores.get(r["id"]) or [
            {"store_name": STORE_NAME, "qty": r["qty_handle"]}]
        for p in parts:
            inn.append({"date_iso": r["date_iso"], "item": it["name"],
                        "unit": it["handle_unit"], "qty": float(p["qty"] or 0),
                        "pack_label": r["pack_label"] or "",
                        "doc": "إذن إضافة رقم {}".format(
                            arnum.to_arabic_indic(str(r["serial"])))})
    inn.sort(key=lambda x: x["date_iso"])

    out = []
    for i in list_issues(year, month):
        out.append({"date_iso": "NaT", "item": i["item_name"] or "—",
                    "unit": i["unit"] or "", "qty": i["qty"],
                    "pack_label": "", "doc": "إذن صرف رقم {}".format(
                        arnum.to_arabic_indic(str(i["serial"]))),
                    "receiver": i["receiver"] or "—"})
    # رتّب المنصرف باليوم الحقيقي من الدفتر (issue2)
    conn = months.get_db(year, month)
    issue_ledger = [dict(r) for r in conn.execute(
        "SELECT * FROM wh_ledger WHERE cycle='tarfea' AND kind='issue2' ORDER BY date_iso, id")]
    conn.close()
    if len(issue_ledger) == len(out):
        for row, led in zip(out, issue_ledger):
            row["date_iso"] = led["date_iso"]
            row["pack_label"] = led.get("pack_label") or ""
    out.sort(key=lambda x: x["date_iso"])

    balances = {}
    for row in inn:
        balances[row["item"]] = balances.get(row["item"], 0.0) + row["qty"]
    for row in out:
        balances[row["item"]] = balances.get(row["item"], 0.0) - row["qty"]
    balances = {k: round(v, 6) for k, v in balances.items() if abs(v) > 1e-9}

    specs = dw.pack_specs_map(year, month, CYCLE)
    pack_notes = {}
    for name, qty in balances.items():
        if qty <= 0 or name not in specs:
            continue
        entry = specs[name]
        kind = list(entry)[-1]
        sp = entry[kind] or {}
        note = dw.pack_breakdown(kind, sp.get("capacity"), sp.get("inner_count"),
                                 sp.get("inner_capacity"), qty,
                                 next((it["handle_unit"] for it in items.values()
                                       if it["name"] == name), ""),
                                 "سائب", inner_kind=sp.get("inner_kind"))
        if note:
            pack_notes[name] = note
    return {"store_name": STORE_NAME, "inn": inn, "out": out,
            "balances": balances, "pack_notes": pack_notes}
