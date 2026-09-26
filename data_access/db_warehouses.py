# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الدورة المخزنية «مستودعات وسجلات» — سجل الإمداد وسجل المتعهد (جداول month.db).

دورتان منفصلتان تمامًا (عمود cycle في كل جدول) وبنفس البنية بالضبط:
- wh_suppliers: الشركات الموردة (نموذج تعريفي شامل) — منفصلة كليًا عن بيانات
  الشركات المنتجة في فواتير المتعهد.
- wh_items: كتالوج ٣ مخازن — كل صنف ووحدة التعامل المحددة له في الدورة كلها.
- wh_receipts: أذون ١ مخازن (إذن إضافة صنف) — الإدخال اليدوي الوحيد في الدورة.
- wh_ledger: دفتر ٣ مخازن — كارت لكل صنف (مسلسل/يوم/تاريخ/رقم إذن/مضاف/منصرف/رصيد).
دفتر ٢ مخازن يُقرأ من أذون آلة الحاسبة (db_permits) — عرض في هذه الدفعة،
والخصم التلقائي لدفاتر ٣ مخازن يُبنى مع مراحل ٤–٧ مخازن.
"""
import json

from core import arabic_numbers as arnum, dates
from core.config import unit_base
from data_access import months

SECTION_BY_CYCLE = {"supply": "tamween", "contractor": "contractor"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS wh_suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    name TEXT NOT NULL,
    contact TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    address TEXT DEFAULT '',
    activity TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wh_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    name TEXT NOT NULL,
    ration_unit TEXT DEFAULT '',
    handle_unit TEXT NOT NULL,
    base_unit TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (cycle, name)
);

CREATE TABLE IF NOT EXISTS wh_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    serial INTEGER NOT NULL,
    item_id INTEGER NOT NULL REFERENCES wh_items(id) ON DELETE CASCADE,
    day INTEGER NOT NULL,
    date_iso TEXT NOT NULL,
    qty_handle REAL NOT NULL,
    unit TEXT NOT NULL,
    qty_base REAL NOT NULL,
    base_unit TEXT NOT NULL,
    pack TEXT NOT NULL DEFAULT '{}',
    pack_label TEXT DEFAULT '',
    producer TEXT DEFAULT '',
    supplier_id INTEGER,
    supplier_name TEXT DEFAULT '',
    prod_date TEXT DEFAULT '',
    exp_date TEXT DEFAULT '',
    shelf_days INTEGER,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wh_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    item_id INTEGER NOT NULL REFERENCES wh_items(id) ON DELETE CASCADE,
    day INTEGER NOT NULL,
    date_iso TEXT NOT NULL,
    kind TEXT NOT NULL,             -- opener / add1 / manual (لاحقًا issue2 مع ٤–٧ مخازن)
    permit_no INTEGER NOT NULL DEFAULT 0,
    label TEXT DEFAULT '',
    added REAL NOT NULL DEFAULT 0,
    issued REAL NOT NULL DEFAULT 0,
    balance REAL NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wh_opener_stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    store_id INTEGER,
    store_name TEXT NOT NULL,
    qty REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS wh_receipt_stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id INTEGER NOT NULL REFERENCES wh_receipts(id) ON DELETE CASCADE,
    store_id INTEGER,
    store_name TEXT NOT NULL DEFAULT '',
    qty REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS wh_pack_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    item_id INTEGER NOT NULL REFERENCES wh_items(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    capacity REAL NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (cycle, item_id, kind)
);
"""


NEW_RECEIPT_COLUMNS = (
    ("pack_kind", "TEXT NOT NULL DEFAULT ''"),
    ("pack_count", "REAL"),
    ("pack_capacity", "REAL"),
    ("pack_loose", "REAL"),
)

NEW_LEDGER_COLUMNS = (
    ("prod_date", "TEXT DEFAULT ''"),
    ("exp_date", "TEXT DEFAULT ''"),
)


def _migrate_tables(conn):
    """ترقية تدريجية: أعمدة التغليف لإذون الإضافة وأعمدة الإنتاج/الصلاحية للدفتر."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(wh_receipts)")}
    if cols:
        for name, decl in NEW_RECEIPT_COLUMNS:
            if name not in cols:
                conn.execute(f"ALTER TABLE wh_receipts ADD COLUMN {name} {decl}")
        conn.commit()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(wh_ledger)")}
    if cols:
        for name, decl in NEW_LEDGER_COLUMNS:
            if name not in cols:
                conn.execute(f"ALTER TABLE wh_ledger ADD COLUMN {name} {decl}")
        conn.commit()
    # توحيد تسميات التغليف القديمة (قبل قاعدة «الصحيح صحيح والكسر بكسره»)
    rows = conn.execute(
        "SELECT id, unit, pack_kind, pack_count, pack_capacity, pack_loose, pack_label "
        "FROM wh_receipts WHERE pack_kind != ''").fetchall()
    for r in rows:
        label, _total = pack_summary(r["pack_kind"], r["pack_count"],
                                     r["pack_capacity"], r["pack_loose"], r["unit"])
        if label and label != r["pack_label"]:
            conn.execute("UPDATE wh_receipts SET pack_label=? WHERE id=?",
                         (label, r["id"]))
    if rows:
        conn.commit()


def _conn(year, month):
    conn = months.get_db(year, month)
    conn.executescript(SCHEMA)
    _migrate_tables(conn)
    return conn


# ======================================================================
# الشركات الموردة — لكل دورة سجلها المنفصل تمامًا
# ======================================================================
def list_suppliers(year, month, cycle):
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM wh_suppliers WHERE cycle=? ORDER BY id", (cycle,))]
    conn.close()
    return rows


def get_supplier(year, month, supplier_id, cycle=None):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM wh_suppliers WHERE id=?", (supplier_id,)).fetchone()
    conn.close()
    data = dict(row) if row else None
    if data and cycle and data["cycle"] != cycle:
        return None
    return data


def add_supplier(year, month, cycle, name, contact="", phone="",
                 address="", activity="", notes=""):
    from core import egtime
    conn = _conn(year, month)
    with conn:
        conn.execute(
            "INSERT INTO wh_suppliers (cycle,name,contact,phone,address,activity,notes,created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (cycle, (name or "").strip(), (contact or "").strip(), (phone or "").strip(),
             (address or "").strip(), (activity or "").strip(), (notes or "").strip(),
             egtime.now().isoformat(timespec="seconds")))
    conn.close()


def update_supplier(year, month, supplier_id, name, contact="", phone="",
                    address="", activity="", notes=""):
    conn = _conn(year, month)
    with conn:
        conn.execute(
            "UPDATE wh_suppliers SET name=?, contact=?, phone=?, address=?,"
            " activity=?, notes=? WHERE id=?",
            ((name or "").strip(), (contact or "").strip(), (phone or "").strip(),
             (address or "").strip(), (activity or "").strip(), (notes or "").strip(),
             supplier_id))
    conn.close()


def delete_supplier(year, month, supplier_id):
    conn = _conn(year, month)
    with conn:
        conn.execute("DELETE FROM wh_suppliers WHERE id=?", (supplier_id,))
    conn.close()


# ======================================================================
# كتالوج ٣ مخازن — الأصناف ووحدة التعامل
# ======================================================================
def ration_catalog(year, month, cycle):
    """أصناف مقرر الدورة من جداول المقررات (بدون تكرار) — مصدر السحب الأول."""
    section = SECTION_BY_CYCLE[cycle]
    from data_access import db_rations as dr
    conn = months.get_db(year, month)
    rows = conn.execute(
        "SELECT name, unit FROM ration_items WHERE section=? ORDER BY id",
        (section,)).fetchall()
    conn.close()
    seen, out = set(), []
    for r in rows:
        name = (r["name"] or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append({"name": name, "unit": (r["unit"] or "").strip()})
    return out


def list_items(year, month, cycle):
    """أصناف الكتالوج مع أرصدتها من دفتر ٣ مخازن."""
    balances = item_balances(year, month, cycle)
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM wh_items WHERE cycle=? ORDER BY name", (cycle,))]
    conn.close()
    for r in rows:
        r["balance"] = balances.get(r["id"], 0.0)
    return rows


def item_balances(year, month, cycle):
    """{item_id: الرصيد النهائي} — رصيد أول المدة/الإضافات − منصرف إذون ٢ مخازن."""
    conn = _conn(year, month)
    items = [dict(r) for r in conn.execute(
        "SELECT id, name, ration_unit, handle_unit FROM wh_items WHERE cycle=?",
        (cycle,))]
    rows = conn.execute(
        "SELECT item_id, added, issued FROM wh_ledger WHERE cycle=? ORDER BY id",
        (cycle,)).fetchall()
    conn.close()
    out = {}
    for r in rows:
        out[r["item_id"]] = out.get(r["item_id"], 0.0) + float(r["added"] or 0) \
            - float(r["issued"] or 0)
    for item in items:
        for row in issue_rows_for_item(year, month, cycle, item):
            out[item["id"]] = out.get(item["id"], 0.0) - float(row["issued"] or 0)
    return out


def get_item(year, month, item_id, cycle=None):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM wh_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    data = dict(row) if row else None
    if data and cycle and data["cycle"] != cycle:
        return None
    return data


def set_handle_unit(year, month, item_id, handle_unit):
    """تغيير وحدة تعامل الصنف — تُطبق على الحركات الجديدة (القديمة تظل بوحدتها)."""
    base_unit, _ = unit_base(handle_unit)
    conn = _conn(year, month)
    with conn:
        conn.execute("UPDATE wh_items SET handle_unit=?, base_unit=? WHERE id=?",
                     (handle_unit.strip(), base_unit, item_id))
    conn.close()


def resolve_item(year, month, cycle, name, handle_unit_hint=""):
    """يجلب صنف الكتالوج بالاسم أو ينشئه: وحدة التعامل من الكتالوج، وإلا وحدة
    المقرر، وإلا الوحدة المختارة في النموذج. إنشاء الكارت هنا = فتح الصنف في ٣ مخازن تلقائيًا."""
    name = (name or "").strip()
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM wh_items WHERE cycle=? AND name=?",
                       (cycle, name)).fetchone()
    conn.close()
    if row:
        return dict(row), False
    ration_unit = ""
    for it in ration_catalog(year, month, cycle):
        if it["name"].lower() == name.lower():
            ration_unit = it["unit"]
            break
    handle = (handle_unit_hint or "").strip() or ration_unit or "كجم"
    base_unit, _ = unit_base(handle)
    from core import egtime
    conn = _conn(year, month)
    with conn:
        cur = conn.execute(
            "INSERT INTO wh_items (cycle,name,ration_unit,handle_unit,base_unit,created_at)"
            " VALUES (?,?,?,?,?,?)",
            (cycle, name, ration_unit, handle, base_unit,
             egtime.now().isoformat(timespec="seconds")))
        item_id = cur.lastrowid
    conn.close()
    return get_item(year, month, item_id), True


# ======================================================================
# ١ مخازن — إذون إضافة الأصناف (الإدخال اليدوي الوحيد في الدورة)
# ======================================================================
def pack_summary(kind, count, capacity, loose, unit):
    """(الملخص النصي، المجموع) لتغليف «مستوى واحد + سائب» — الأرقام كلها عربية.

    مثال المستخدم: شكارة سعتها ٥٠ + ٣٠ سائب = ٨٠ كجم — أو بلاتة ٢٧ + ٣ عصير = ٣٠.
    """
    kind = (kind or "").strip()
    count = float(count or 0)
    capacity = float(capacity or 0)
    loose = float(loose or 0)
    total = 0.0
    bits = []
    if kind and kind != "بدون تغليف":
        if count > 0 and capacity > 0:
            total += count * capacity
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind} × "
                        f"{arnum.fmt_qty_trim(capacity)} {unit}")
        elif count > 0:
            bits.append(f"{arnum.to_arabic_indic(f'{count:g}')} {kind}")
    if loose > 0:
        total += loose
        bits.append(f"{arnum.fmt_qty_trim(loose)} {unit} سائب")
    label = " + ".join(bits)
    if bits and total > 0 and (count and capacity):
        label += f" = {arnum.fmt_qty_trim(total)} {unit}"
    return label, round(total, 6)


def _remember_spec(conn, cycle, item_id, kind, capacity):
    """يحفظ سعة العبوة للصنف على الاتصال المفتوح نفسه (تفادي قفل القاعدة)."""
    if not kind or kind == "بدون تغليف" or not capacity or capacity <= 0:
        return
    from core import egtime
    conn.execute(
        "INSERT INTO wh_pack_specs (cycle,item_id,kind,capacity,updated_at)"
        " VALUES (?,?,?,?,?)"
        " ON CONFLICT(cycle,item_id,kind)"
        " DO UPDATE SET capacity=excluded.capacity, updated_at=excluded.updated_at",
        (cycle, item_id, kind, float(capacity),
         egtime.now().isoformat(timespec="seconds")))


def pack_specs_map(year, month, cycle):
    """{اسم الصنف: {نوع التغليف: آخر سعة}} — لتعبئة السعة تلقائيًا في النموذج."""
    conn = _conn(year, month)
    rows = conn.execute(
        "SELECT wi.name n, ps.kind k, ps.capacity c FROM wh_pack_specs ps"
        " JOIN wh_items wi ON wi.id=ps.item_id WHERE ps.cycle=? ORDER BY ps.updated_at",
        (cycle,)).fetchall()
    conn.close()
    out = {}
    for r in rows:
        out.setdefault(r["n"], {})[r["k"]] = r["c"]
    return out


def collect_pack_kinds():
    """قائمة أنواع التغليف: الثوابت + ما كتبه المستخدم (قاموس مشترك pack_kind)."""
    kinds = []
    from core.config import PACK_KINDS
    from data_access import database as db
    for kind in list(PACK_KINDS):
        if kind not in kinds:
            kinds.append(kind)
    for kind in db.vocab_list("pack_kind"):
        if kind not in kinds:
            kinds.append(kind)
    return kinds


def add_receipt(year, month, cycle, day, item_name, qty_handle,
                handle_unit_hint="", producer="", supplier_id=None,
                supplier_name="", prod_iso="", exp_iso="", notes="",
                date_iso="", receipt_no=None,
                pack_kind="", pack_count=0, pack_capacity=0, pack_loose=0,
                stores=None):
    """يحفظ إذن إضافة ١ مخازن ويسجل حركته في دفتر ٣ مخازن — ويرجع بياناته.

    - رقم الإذن يدوي (فاضي = يكمّل التسلسل، وأكبر رقم يصبح أصل التسلسل).
    - التغليف «مستوى واحد + سائب»: عدد العبوات × سعة العبوة + سائب = الكمية
      تُحسب تلقائيًا، وسعة العبوة تُحفظ للصنف (تعبئ تلقائيًا بعدها).
    - stores: قائمة (store_id, store_name, qty) لتوزيع الكمية على مخزن أو أكثر.
    """
    from core import egtime
    pack_kind = (pack_kind or "").strip()
    pack_total = 0.0
    pack_label_text = ""
    extras = []
    if pack_kind and pack_kind != "بدون تغليف":
        item_probe, _ = resolve_item(year, month, cycle, item_name, handle_unit_hint)
        pack_label_probe, pack_total = pack_summary(
            pack_kind, pack_count, pack_capacity, pack_loose, item_probe["handle_unit"])
        if pack_total <= 0:
            raise ValueError("اكتب عدد العبوات وسعة العبوة أو الكمية السائبة — "
                             "لا يمكن إذن إضافة بكمية صفر")
        qty_handle = pack_total
        pack_label_text = pack_label_probe
        extras.append("تغليف: " + pack_label_probe)
    elif pack_kind:
        pack_kind = ""
    qty_handle = float(qty_handle)
    item, created = resolve_item(year, month, cycle, item_name, handle_unit_hint)
    base_unit, factor = unit_base(item["handle_unit"])
    qty_base = qty_handle * factor
    shelf_days = None
    if prod_iso and exp_iso:
        try:
            d1 = dates.parse_date(prod_iso)
            d2 = dates.parse_date(exp_iso)
            if d1 and d2:
                shelf_days = (d2 - d1).days
        except (TypeError, ValueError):
            shelf_days = None
    supplier_id = int(supplier_id) if supplier_id else None
    supplier_name = (supplier_name or "").strip()
    if supplier_id and not supplier_name:
        sup = get_supplier(year, month, supplier_id)
        supplier_name = sup["name"] if sup else ""
    parts = [(int(sid), (sname or "").strip(), float(q)) for sid, sname, q in (stores or [])
             if q and float(q) > 0]
    if parts:
        diff = round(qty_handle - sum(q for _s, _n, q in parts), 6)
        if abs(diff) > 0.000001:
            raise ValueError("مجموع الكميات على المخازن لا يساوي كمية الإذن — "
                             "وزّع الكمية كاملة على المخازن")
        extras.append("مخازن: " + "، ".join(
            f"{n} ({arnum.fmt_qty(q)} {item['handle_unit']})" for _s, n, q in parts))
    conn = _conn(year, month)
    if receipt_no:
        exists = conn.execute(
            "SELECT 1 FROM wh_receipts WHERE cycle=? AND serial=?",
            (cycle, int(receipt_no))).fetchone()
        if exists:
            conn.close()
            raise ValueError(
                f"رقم الإذن {arnum.to_arabic_indic(receipt_no)} مستخدم من قبل في هذه "
                "الدورة — اكتب رقمًا آخر أو اتركه فاضيًا ليُكمّل التسلسل")
        serial = int(receipt_no)
    else:
        serial = (conn.execute(
            "SELECT COALESCE(MAX(serial),0)+1 s FROM wh_receipts WHERE cycle=?",
            (cycle,)).fetchone()["s"])
    stamp = egtime.now().isoformat(timespec="seconds")
    notes_text = " — ".join([b for b in [(notes or "").strip()] + extras if b])
    with conn:
            cur = conn.execute(
                "INSERT INTO wh_receipts (cycle,serial,item_id,day,date_iso,qty_handle,unit,"
                "qty_base,base_unit,pack,pack_label,producer,supplier_id,supplier_name,"
                "prod_date,exp_date,shelf_days,notes,created_at,"
                "pack_kind,pack_count,pack_capacity,pack_loose)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cycle, serial, item["id"], day, date_iso, qty_handle, item["handle_unit"],
                 qty_base, base_unit, "{}", pack_label_text, (producer or "").strip(), supplier_id,
                 supplier_name, prod_iso, exp_iso, shelf_days, notes_text, stamp,
                 pack_kind, float(pack_count or 0), float(pack_capacity or 0),
                 float(pack_loose or 0)))
            receipt_id = cur.lastrowid
            for sid, sname, q in parts:
                conn.execute(
                    "INSERT INTO wh_receipt_stores (receipt_id,store_id,store_name,qty)"
                    " VALUES (?,?,?,?)", (receipt_id, sid, sname, q))
            balance = conn.execute(
                "SELECT COALESCE(balance,0) b FROM wh_ledger WHERE cycle=? AND item_id=?"
                " ORDER BY id DESC LIMIT 1", (cycle, item["id"])).fetchone()
            prev_balance = float(balance["b"]) if balance else 0.0
            conn.execute(
                "INSERT INTO wh_ledger (cycle,item_id,day,date_iso,kind,permit_no,label,"
                "added,issued,balance,notes,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (cycle, item["id"], day, date_iso, "add1", serial,
                 f"إذن إضافة ١ مخازن رقم {arnum.to_arabic_indic(serial)}",
                 qty_handle, 0.0, prev_balance + qty_handle, notes_text, stamp))
            _remember_spec(conn, cycle, item["id"], pack_kind, pack_capacity)
    conn.close()
    return {
        "receipt_id": receipt_id, "serial": serial, "item": item, "created": created,
        "qty_handle": qty_handle, "qty_base": qty_base, "base_unit": base_unit,
        "factor": factor, "pack_label": extras[0][len("تغليف: "):] if extras and extras[0].startswith("تغليف: ") else "",
    }


def list_receipts(year, month, cycle, limit=10000):
    """إذون الدورة مع تفاصيل التغليف وتوزيعها على المخازن (من الأحدث)."""
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM wh_receipts WHERE cycle=? ORDER BY serial DESC, id DESC LIMIT ?",
        (cycle, limit))]
    splits = {}
    for r in conn.execute(
            "SELECT rs.receipt_id rid, rs.store_id, rs.store_name, rs.qty"
            " FROM wh_receipt_stores rs JOIN wh_receipts wr ON wr.id=rs.receipt_id"
            " WHERE wr.cycle=? ORDER BY rs.id", (cycle,)):
        splits.setdefault(r["rid"], []).append(
            {"store_id": r["store_id"], "store_name": r["store_name"],
             "qty": float(r["qty"] or 0)})
    conn.close()
    for r in rows:
        r["stores"] = splits.get(r["id"], [])
        r["pack_total"] = round(
            float(r["pack_count"] or 0) * float(r["pack_capacity"] or 0)
            + float(r["pack_loose"] or 0), 6)
    return rows


# ======================================================================
# ٣ مخازن — دفتر الصنف (كارت لكل صنف) + رصيد أول المدة + منصرف إذون ٢ مخازن
# ======================================================================
def _convert(qty, from_unit, to_unit):
    """يحوّل كمية بين وحدتين عبر وحدات القاعدة (طن→كجم→طن…). غير المعروفة معاملها ١."""
    _base1, factor_from = unit_base(from_unit)
    _base2, factor_to = unit_base(to_unit)
    if not factor_to:
        return qty
    return round(qty * factor_from / factor_to, 6)


def has_opener(year, month, item_id):
    conn = _conn(year, month)
    row = conn.execute(
        "SELECT 1 FROM wh_ledger WHERE item_id=? AND kind='opener' LIMIT 1",
        (item_id,)).fetchone()
    conn.close()
    return bool(row)


def add_opener(year, month, cycle, item_name, qty, day, handle_unit_hint="",
               producer="", supplier_id=None, supplier_name="",
               notes="", date_iso="",
               pack_kind="", pack_count=0, pack_capacity=0, pack_loose=0,
               prod_iso="", exp_iso="", stores=None):
    """رصيد أول المدة: إدخال حقيقي بكل بياناته (توجيه ٢٥/٠٩ وتوسيع ٢٦/٠٩) —
    كمية + شركة منتجة + مورد + تغليف + إنتاج/صلاحية + توزيع على المخازن،
    تمامًا كإذن إضافة ١ مخازن. مرة واحدة لكل صنف، وأول سطور الكارت."""
    from core import egtime
    item, created = resolve_item(year, month, cycle, item_name, handle_unit_hint)
    if has_opener(year, month, item["id"]):
        raise ValueError(
            f"رصيد أول المدة مسجّل بالفعل لصنف «{item['name']}» — لا يُسجل مرتين")
    pack_kind = (pack_kind or "").strip()
    label_pack, pack_total = pack_summary(pack_kind, pack_count, pack_capacity,
                                          pack_loose, item["handle_unit"])
    qty = pack_total if pack_total > 0 else float(qty)
    if qty <= 0:
        raise ValueError("اكتب كمية رصيد أول المدة أو بيانات التغليف")
    prod_iso = (prod_iso or "").strip()
    exp_iso = (exp_iso or "").strip()
    if not exp_iso:
        raise ValueError("تاريخ الصلاحية إلزامي لرصيد أول المدة — زي أي صنف بالظبط")
    if prod_iso and exp_iso and exp_iso < prod_iso:
        raise ValueError("تاريخ الصلاحية قبل تاريخ الإنتاج — صحّح التواريخ")
    parts = [(int(sid), (sname or "").strip(), float(q)) for sid, sname, q in (stores or [])
             if q and float(q) > 0]
    if parts:
        diff = round(qty - sum(q for _s, _n, q in parts), 6)
        if abs(diff) > 0.000001:
            raise ValueError("مجموع الكميات على المخازن لا يساوي كمية رصيد أول المدة — "
                             "وزّع الكمية كاملة على المخازن")
    supplier_id = int(supplier_id) if supplier_id else None
    supplier_name = (supplier_name or "").strip()
    if supplier_id and not supplier_name:
        sup = get_supplier(year, month, supplier_id)
        supplier_name = sup["name"] if sup else ""
    bits = []
    if (producer or "").strip():
        bits.append("منتج: " + producer.strip())
    if supplier_name:
        bits.append("مورد: " + supplier_name)
    if label_pack:
        bits.append("تغليف: " + label_pack)
    if (notes or "").strip():
        bits.append(notes.strip())
    conn = _conn(year, month)
    stamp = egtime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "INSERT INTO wh_ledger (cycle,item_id,day,date_iso,kind,permit_no,label,"
            "added,issued,balance,notes,created_at,prod_date,exp_date) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cycle, item["id"], day, date_iso, "opener", 0, "رصيد أول المدة",
             qty, 0.0, qty, " — ".join(bits), stamp, prod_iso, exp_iso))
        for sid, sname, q in parts:
            conn.execute(
                "INSERT INTO wh_opener_stores (cycle,item_id,store_id,store_name,qty)"
                " VALUES (?,?,?,?,?)", (cycle, item["id"], sid, sname, q))
        _remember_spec(conn, cycle, item["id"], pack_kind, pack_capacity)
    conn.close()
    return {"item": item, "qty": qty, "created": created}


def opener_stores(year, month, cycle):
    """توزيع أرصدة أول المدة على المخازن: {item_id: [{store_id,store_name,qty}]}."""
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT item_id, store_id, store_name, qty FROM wh_opener_stores WHERE cycle=?",
        (cycle,))]
    conn.close()
    out = {}
    for r in rows:
        out.setdefault(r["item_id"], []).append(r)
    return out


def _iter_month_conns():
    """اتصالات كل قواعد الشهور الموجودة (بلا إنشاء) — المخازن أصل مستمر عبر الشهور."""
    from data_access import storage
    for year in storage.list_years():
        for month in range(1, 13):
            path = months.month_db_path(year, month)
            if not path.exists():
                continue
            conn = _conn(year, month)
            yield year, month, conn
            conn.close()


def store_has_movement(store_id):
    """هل للمخزن حركة توزيع في أي شهر (إذون إضافة أو أرصدة أول مدة)؟"""
    for _y, _m, conn in _iter_month_conns():
        for table in ("wh_receipt_stores", "wh_opener_stores"):
            row = conn.execute(
                f"SELECT 1 FROM {table} WHERE store_id=? LIMIT 1", (store_id,)).fetchone()
            if row:
                return True
    return False


def item_has_movement(year, month, cycle, item_id):
    """هل للصنف أي حركة (إذن إضافة أو رصيد أول المدة أو صرف)؟"""
    conn = _conn(year, month)
    row = conn.execute(
        "SELECT 1 FROM wh_receipts WHERE cycle=? AND item_id=? LIMIT 1",
        (cycle, item_id)).fetchone()
    if not row:
        row = conn.execute(
            "SELECT 1 FROM wh_ledger WHERE cycle=? AND item_id=? LIMIT 1",
            (cycle, item_id)).fetchone()
    conn.close()
    return bool(row)


def item_name_in_use(year, month, name):
    """هل الاسم مفتوح كارت له في ٣ مخازن (أي دورة)؟ — يمنع إعادة التسمية."""
    for cycle in ("supply", "contractor"):
        conn = _conn(year, month)
        row = conn.execute(
            "SELECT 1 FROM wh_items WHERE cycle=? AND name=? LIMIT 1",
            (cycle, name)).fetchone()
        conn.close()
        if row:
            return True
    return False


def cascade_purge_item(year, month, cycle, name):
    """حذف صنف يمسحه من كل حاجة (توجيه ٢٦/٠٩): الكارت وإذون الإضافة والتوزيعات
    ورصيد أول المدة والدفتر وسعة التغليف — والتفريدة تتجدد تلقائيًا بدونه."""
    conn = _conn(year, month)
    with conn:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM wh_items WHERE cycle=? AND name=?", (cycle, name))]
        for item_id in ids:
            conn.execute(
                "DELETE FROM wh_receipt_stores WHERE receipt_id IN "
                "(SELECT id FROM wh_receipts WHERE item_id=?)", (item_id,))
            conn.execute("DELETE FROM wh_receipts WHERE item_id=?", (item_id,))
            conn.execute("DELETE FROM wh_opener_stores WHERE cycle=? AND item_id=?",
                         (cycle, item_id))
            conn.execute("DELETE FROM wh_ledger WHERE cycle=? AND item_id=?",
                         (cycle, item_id))
            conn.execute("DELETE FROM wh_pack_specs WHERE cycle=? AND item_id=?",
                         (cycle, item_id))
        conn.execute("DELETE FROM wh_items WHERE cycle=? AND name=?", (cycle, name))
    conn.close()
    return len(ids)


def move_store_splits(store_id, new_store_id, new_store_name):
    """نقل توزيعات مخزن إلى مخزن آخر في كل الشهور (قبل حذفه)."""
    moved = 0
    for _y, _m, conn in _iter_month_conns():
        with conn:
            cur = conn.execute(
                "UPDATE wh_receipt_stores SET store_id=?, store_name=? WHERE store_id=?",
                (new_store_id, new_store_name, store_id))
            moved += cur.rowcount
            cur = conn.execute(
                "UPDATE wh_opener_stores SET store_id=?, store_name=? WHERE store_id=?",
                (new_store_id, new_store_name, store_id))
            moved += cur.rowcount
    return moved


def issue_rows_for_item(year, month, cycle, item):
    """حركات المنصرف لهذا الصنف من إذون ٢ مخازن المحفوظة (دفتر الإضافة والتخصيم).

    كمية الإذن بوحدة المقرر — تُحوَّل لوحدة تعامل الصنف تلقائيًا.
    """
    from core import arabic_numbers as arnum
    rows = []
    for permit in permits_book(year, month, cycle):
        for entry in permit["cycle_items"]:
            if entry["name"] != item["name"]:
                continue
            from_unit = item["ration_unit"] or item["handle_unit"]
            qty = _convert(float(entry["qty"] or 0), from_unit, item["handle_unit"])
            day = int(permit["date_from"])
            rows.append({
                "kind": "issue2", "day": day,
                "date_iso": f"{year:04d}-{month:02d}-{day:02d}",
                "permit_no": int(permit["number"]),
                "label": f"إذن صرف ٢ مخازن رقم {arnum.to_arabic_indic(permit['number'])}",
                "added": 0.0, "issued": qty,
                "notes": permit.get("entity_label") or "",
            })
    return rows


def item_card(year, month, item_id):
    """كارت الصنف: رصيد أول المدة + إضافات ١ مخازن + منصرف إذون ٢ مخازن،
    مرتبة زمنيًا بالرصيد التراكمي — بوحدة تعامل الصنف."""
    item = get_item(year, month, item_id)
    if not item:
        return None
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM wh_ledger WHERE item_id=? ORDER BY date_iso, id", (item_id,))]
    conn.close()
    for r in issue_rows_for_item(year, month, item["cycle"], item):
        rows.append(r)

    def sort_key(r):
        return (r["date_iso"], 0 if r["kind"] == "opener" else 1,
                r.get("permit_no") or 0)
    rows.sort(key=sort_key)
    running = 0.0
    out = []
    for r in rows:
        running += float(r["added"] or 0) - float(r["issued"] or 0)
        r["balance"] = running
        out.append(r)
    opener = next((r for r in out if r["kind"] == "opener"), None)
    return {
        "item": item,
        "rows": out,
        "opener_row": opener,
        "has_opener": opener is not None,
        "total_added": sum(float(r["added"] or 0) for r in out),
        "total_issued": sum(float(r["issued"] or 0) for r in out),
        "balance": running,
    }


# ======================================================================
# دفتر ٢ مخازن — إذون آلة الحاسبة (عرض؛ الخصم التلقائي مع ٤–٧ مخازن)
# ======================================================================
def permits_book(year, month, cycle):
    """أذون ٢ مخازن المحفوظة بالشهر وأصناف دورة {cycle} داخل كل إذن فقط.

    مفاتيح actuals بصيغة «{section}_{اسم الصنف}» — فيُفصل أصناف التموين عن المتعهد.
    يقرأ الوحدات مباشرة من الجدول (لا list_items) تفاديًا لدورة استدعاء.
    """
    from data_access import db_permits as dp
    prefix = SECTION_BY_CYCLE[cycle] + "_"
    conn = _conn(year, month)
    catalog_units = {r["name"]: r["unit"] for r in conn.execute(
        "SELECT name, unit FROM ration_items WHERE section=?",
        (SECTION_BY_CYCLE[cycle],))}
    handle_units = {r["name"]: r["handle_unit"] for r in conn.execute(
        "SELECT name, handle_unit FROM wh_items WHERE cycle=?", (cycle,))}
    conn.close()
    out = []
    for permit in dp.list_permits(year, month):
        items = []
        for key, qty in (permit.get("actuals") or {}).items():
            if not str(key).startswith(prefix):
                continue
            name = str(key)[len(prefix):]
            unit = handle_units.get(name) or catalog_units.get(name) or ""
            items.append({"name": name, "qty": qty, "unit": unit})
        if not items:
            continue   # عزل تام: إذن بلا أصناف لهذه الدورة لا يظهر في دفترها إطلاقًا
        items.sort(key=lambda x: x["name"])
        out.append({**permit, "cycle_items": items})
    return out

# ======================================================================
# المخازن الفيزيائية: التفريدة التلقائية (الأقرب صلاحية أولًا) وحركة المخازن
# ======================================================================
UNASSIGNED = "غير موزع على مخازن"
NO_EXPIRY = "9999-12-31"


def _batch_pool(year, month, cycle):
    """دفعات الدورة (إذون الإضافة + رصيد أول المدة) مقسومة على المخازن، مرتبة
    وفق قرار المستخدم: الأقرب انتهاءً أولًا؛ وتساوي ⇒ الأقدم إضافةً (الأبعد في الإضافة)."""
    items = {it["id"]: it for it in list_items(year, month, cycle)}
    conn = _conn(year, month)
    openers = [dict(r) for r in conn.execute(
        "SELECT * FROM wh_ledger WHERE cycle=? AND kind='opener'", (cycle,))]
    conn.close()
    opener_parts = opener_stores(year, month, cycle)
    pool = []
    for r in sorted(list_receipts(year, month, cycle), key=lambda x: x["id"]):
        item = items.get(r["item_id"])
        if not item:
            continue
        parts = r["stores"] or [{"store_id": None, "store_name": UNASSIGNED,
                                 "qty": r["qty_handle"]}]
        for part in parts:
            pool.append({
                "item": item, "qty": float(part["qty"]),
                "remaining": float(part["qty"]),
                "expiry": r["exp_date"] or NO_EXPIRY,
                "order": f"{r['date_iso']}-{r['id']:05d}",
                "serial": r["serial"], "pack_label": r["pack_label"],
                "store_id": part["store_id"],
                "store_name": part["store_name"] or UNASSIGNED,
            })
    for o in openers:
        item = items.get(o["item_id"])
        if not item:
            continue
        parts = opener_parts.get(o["item_id"]) or [
            {"store_id": None, "store_name": UNASSIGNED, "qty": float(o["added"] or 0)}]
        for part in parts:
            pool.append({
                "item": item, "qty": float(part["qty"]),
                "remaining": float(part["qty"]),
                "expiry": o["exp_date"] or NO_EXPIRY,
                "order": f"{o['date_iso']}-00000",
                "serial": 0, "pack_label": "",
                "store_id": part["store_id"],
                "store_name": part["store_name"] or UNASSIGNED,
            })
    pool.sort(key=lambda b: (b["expiry"], b["order"]))
    return pool


def tafreeda_rows(year, month, cycle):
    """التفريدة التلقائية: كميات كل إذن صرف ٢ مخازن تتوزع على دفعات المخازن.

    الأقرب صلاحية يُصرف أولًا؛ وعند تطابق رصيدين يُصرف الأقدم إضافةً.
    الكمية محوّلة لوحدة تعامل الصنف، ومع كل سطر تغليف الدفعة الأصلية.
    """
    pool = _batch_pool(year, month, cycle)
    rows = []
    for permit in permits_book(year, month, cycle):
        for entry in permit["cycle_items"]:
            need = float(entry["qty"] or 0)
            if need <= 0:
                continue
            for batch in pool:
                if need <= 0:
                    break
                if batch["item"]["name"] != entry["name"] or batch["remaining"] <= 0:
                    continue
                take = min(need, batch["remaining"])
                batch["remaining"] = round(batch["remaining"] - take, 6)
                need = round(need - take, 6)
                rows.append({
                    "permit_no": permit["number"],
                    "date_from": permit["date_from"], "date_to": permit["date_to"],
                    "item": batch["item"]["name"],
                    "unit": batch["item"]["handle_unit"],
                    "store_id": batch["store_id"], "store_name": batch["store_name"],
                    "receipt_serial": batch["serial"],
                    "expiry": batch["expiry"] if batch["expiry"] != NO_EXPIRY else "",
                    "qty": round(take, 6), "pack_label": batch["pack_label"],
                })
    return rows


def stores_report(year, month):
    """حركة وكشف أرصدة كل مخزن — الدورتان معًا (المخازن والثلاجات موحدة لكل الأصناف)."""
    from data_access import db_stores
    stores = db_stores.list_stores()
    report = {s["id"]: {"store": s, "inn": [], "out": [],
                        "balances": {}, "total": 0.0} for s in stores}
    unassigned = {"store": {"id": None, "name": UNASSIGNED}, "inn": [], "out": [],
                  "balances": {}, "total": 0.0}
    for cycle, cycle_name in (("supply", "الإمداد"), ("contractor", "المتعهد")):
        items = {it["id"]: it for it in list_items(year, month, cycle)}
        # رصيد أول المدة: كمية داخل موزعة على مخازنه (أو «غير موزع» بلا توزيع)
        conn = _conn(year, month)
        openers = [dict(r) for r in conn.execute(
            "SELECT * FROM wh_ledger WHERE cycle=? AND kind='opener'", (cycle,))]
        conn.close()
        opener_parts = opener_stores(year, month, cycle)
        for o in openers:
            item = items.get(o["item_id"])
            if not item or not (o["added"] or 0):
                continue
            for part in (opener_parts.get(o["item_id"]) or [
                    {"store_id": None, "store_name": UNASSIGNED,
                     "qty": float(o["added"])}]):
                target = report.get(part["store_id"], unassigned)
                qty = float(part["qty"] or 0)
                target["inn"].append({
                    "date_iso": o["date_iso"], "cycle": cycle_name,
                    "item": item["name"], "unit": item["handle_unit"],
                    "qty": qty, "pack_label": "",
                    "serial": 0, "expiry": o["exp_date"] or "",
                })
                target["balances"][item["name"]] = \
                    target["balances"].get(item["name"], 0.0) + qty
        for r in list_receipts(year, month, cycle):
            item = items.get(r["item_id"])
            if not item:
                continue
            for part in (r["stores"] or [{"store_id": None, "store_name": UNASSIGNED,
                                          "qty": r["qty_handle"]}]):
                target = report.get(part["store_id"], unassigned)
                qty = float(part["qty"] or 0)
                target["inn"].append({
                    "date_iso": r["date_iso"], "cycle": cycle_name,
                    "item": item["name"], "unit": item["handle_unit"],
                    "qty": qty, "pack_label": r["pack_label"],
                    "serial": r["serial"], "expiry": r["exp_date"] or "",
                })
                target["balances"][item["name"]] = \
                    target["balances"].get(item["name"], 0.0) + qty
        for row in tafreeda_rows(year, month, cycle):
            target = report.get(row["store_id"], unassigned)
            target["out"].append({
                "date_iso": f"{year:04d}-{month:02d}-{int(row['date_from']):02d}",
                "cycle": cycle_name, "item": row["item"], "unit": row["unit"],
                "qty": row["qty"], "permit_no": row["permit_no"],
                "expiry": row["expiry"], "pack_label": row["pack_label"],
            })
            target["balances"][row["item"]] = \
                target["balances"].get(row["item"], 0.0) - row["qty"]
    all_targets = list(report.values()) + [unassigned]
    for target in all_targets:
        target["inn"].sort(key=lambda x: (x["date_iso"], x.get("serial") or 0))
        target["out"].sort(key=lambda x: (x["date_iso"], x.get("permit_no") or 0))
        target["balances"] = {k: round(v, 6) for k, v in target["balances"].items()
                              if abs(v) > 1e-9}
        target["total"] = round(sum(target["balances"].values()), 6)
    return {"stores": list(report.values()), "unassigned": unassigned}
