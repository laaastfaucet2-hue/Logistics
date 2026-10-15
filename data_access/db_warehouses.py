# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الدورة «مستودعات وسجلات» — دورتان (عمود cycle): wh_suppliers، wh_items
(كتالوج ٣ مخازن)، wh_receipts (أذون ١ مخازن — الإدخال اليدوي الوحيد)،
wh_ledger (دفتر ٣ مخازن). دفتر ٢ مخازن من أذون آلة الحاسبة (db_permits)."""
import json
import re

from core import arabic_numbers as arnum, dates
from core.config import unit_base, is_measure_unit
from data_access import oil_units as ou
from data_access import months
from data_access.packaging import (pack_summary, pack_split,
                                         pack_breakdown)  # صيغ التغليف اللفظية

SECTION_BY_CYCLE = {"supply": "tamween", "contractor": "contractor", "tarfea": "tarfea"}

from data_access.db_warehouses_schema import (SCHEMA,
        NEW_RECEIPT_COLUMNS, NEW_LEDGER_COLUMNS,
        NEW_ITEM_COLUMNS, NEW_SPEC_COLUMNS)

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
    cols = {r[1] for r in conn.execute("PRAGMA table_info(wh_items)")}
    if cols:
        for name, decl in NEW_ITEM_COLUMNS:
            if name not in cols:
                conn.execute(f"ALTER TABLE wh_items ADD COLUMN {name} {decl}")
        conn.commit()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(wh_pack_specs)")}
    if cols:
        for name, decl in NEW_SPEC_COLUMNS:
            if name not in cols:
                conn.execute(f"ALTER TABLE wh_pack_specs ADD COLUMN {name} {decl}")
        conn.commit()
    # توحيد تسميات التغليف القديمة (قبل قاعدة «الصحيح صحيح والكسر بكسره»)
    rows = conn.execute(
        "SELECT id, unit, pack_kind, pack_count, pack_capacity, pack_loose, pack_inner_unit, "
        "pack_inner_count, pack_inner_capacity, pack_loose_unit, pack_inner_kind, pack_label "
        "FROM wh_receipts WHERE pack_kind != ''").fetchall()
    for r in rows:
        # نفس وحدة الحسبة وقت الحفظ (add_receipt/add_opener): وحدة المعيار لو قياس (١٥/١٠)
        _iu = (r["pack_inner_unit"] or "").strip()
        label, _total = pack_summary(r["pack_kind"], r["pack_count"], r["pack_capacity"],
                                     r["pack_loose"], _iu if is_measure_unit(_iu) else r["unit"],
                                     r["pack_inner_count"], r["pack_inner_capacity"],
                                     r["pack_loose_unit"], r["pack_inner_kind"])
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


# ========== الشركات الموردة — لكل دورة سجلها المنفصل تمامًا ==========
def list_suppliers(year, month, cycle):
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute("SELECT * FROM wh_suppliers WHERE cycle=? ORDER BY id", (cycle,))]
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


# ========== كتالوج ٣ مخازن — الأصناف ووحدة التعامل ==========
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


@months.memo
def list_items(year, month, cycle):
    """أصناف الكتالوج مع أرصدتها من دفتر ٣ مخازن."""
    balances = item_balances(year, month, cycle)
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute("SELECT * FROM wh_items WHERE cycle=? ORDER BY name", (cycle,))]
    conn.close()
    for r in rows:
        r["balance"] = balances.get(r["id"], 0.0)
    return rows


def raw_items(year, month, cycle):
    """أصناف الكتالوج بس (بلا أرصدة) — للمسارات اللي جوا حلقة الحساب:
    حوض الدفعات يستدعيها بدل list_items عشان item_balances → سطور المنصرف
    → تفريد FEFO → الحوض نفسه ما يعملش تكرار لانهائي."""
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute("SELECT * FROM wh_items WHERE cycle=? ORDER BY name", (cycle,))]
    conn.close()
    return rows


def running_balance(conn, cycle, item_id, exclude_id=None):
    """الرصيد التراكمي من السطور الفعلية (مضاف − منصرف) — مش العمود المحفوظ:
    سطور الصرف (issue2) كانت بتخزن رصيدًا قديم فيتضرب حساب السطر التالي منه."""
    if exclude_id:
        row = conn.execute(
            "SELECT COALESCE(SUM(added),0) a, COALESCE(SUM(issued),0) i FROM wh_ledger "
            "WHERE cycle=? AND item_id=? AND id<>?", (cycle, item_id, exclude_id)).fetchone()
    else:
        row = conn.execute(
            "SELECT COALESCE(SUM(added),0) a, COALESCE(SUM(issued),0) i FROM wh_ledger "
            "WHERE cycle=? AND item_id=?", (cycle, item_id)).fetchone()
    return round(float(row["a"] or 0.0) - float(row["i"] or 0.0), 6)


@months.memo
def item_balances(year, month, cycle):
    """{item_id: الرصيد النهائي} — رصيد أول المدة/الإضافات − منصرف إذون ٢ مخازن."""
    conn = _conn(year, month)
    items = [dict(r) for r in conn.execute(
        "SELECT id, name, ration_unit, handle_unit FROM wh_items WHERE cycle=?", (cycle,))]
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


def _norm_item_name(t):
    """تطبيع أسماء الأصناف للمطابقة الذكية (توجيه ١٠/١٠):
    همزات الألف ← ا، «ال» المبدئية لأي كلمة، والمسافات الزائدة —
    «الزيت  الطهي» و«زيت طهي» = نفس الاسم."""
    t = (t or "").strip()
    t = re.sub(r"\s+", " ", t)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = re.sub(r"(^|\s)ال", r"\1", t)
    return t.strip()


def resolve_item(year, month, cycle, name, handle_unit_hint=""):
    """يجلب صنف الكتالوج بالاسم أو ينشئه — إنشاؤه يفتح كارته في ٣ مخازن تلقائيًا.
    المطابقة (توجيه ١٠/١٠): الحرفية أولًا، ثم الاسم بعد التطبيع —
    بلا افتراضات على أسماء مختلفة، والصنف الجديد بيتولد بوحدة المعيار الداخلي لو اتحددت."""
    name = (name or "").strip()
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM wh_items WHERE cycle=? AND name=?",
                       (cycle, name)).fetchone()
    if not row:
        n = _norm_item_name(name)
        if n:
            for r in conn.execute("SELECT * FROM wh_items WHERE cycle=?", (cycle,)):
                if _norm_item_name(r["name"]) == n:
                    row = r
                    break
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


# ========== ١ مخازن — إذون إضافة الأصناف (الإدخال اليدوي الوحيد في الدورة) ==========
def _remember_spec(conn, cycle, item_id, kind, capacity,
                   inner_count=0, inner_capacity=0, inner_kind="", inner_unit=""):
    """يحفظ مواصفات العبوة (الوزن وعدد العلب بداخلها ووزنها ووحته واسمها) للصنف تلقائيًا."""
    if not kind or kind == "بدون تغليف":
        return
    # العبوة العدّية بمعيار فقط (جركن × ٢٠ لتر / شكارة × ٥٠ كجم بلا وزن) تُحفظ أيضًا —
    # من غيرها يضيع التفكيك في تفاريد ٣ مخازن وكارت الصنف (شكوى ٢٧/٠٩: الفلفل والزيت)
    if (not capacity or capacity <= 0) and not (inner_count and inner_count > 0):
        return
    from core import egtime
    conn.execute(
        "INSERT INTO wh_pack_specs (cycle,item_id,kind,capacity,inner_count,"
        "inner_capacity,inner_kind,inner_unit,updated_at) VALUES (?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(cycle,item_id,kind)"
        " DO UPDATE SET capacity=excluded.capacity, inner_count=excluded.inner_count,"
        " inner_capacity=excluded.inner_capacity, inner_kind=excluded.inner_kind,"
        " inner_unit=excluded.inner_unit, updated_at=excluded.updated_at",
        (cycle, item_id, kind, float(capacity or 0), float(inner_count or 0),
         float(inner_capacity or 0), (inner_kind or "").strip(),
         (inner_unit or "").strip(), egtime.now().isoformat(timespec="seconds")))


@months.memo
def pack_specs_map(year, month, cycle):
    """{الصنف: {النوع: {capacity, inner_count, inner_capacity}}} — للتعبئة التلقائية."""
    conn = _conn(year, month)
    rows = conn.execute(
        "SELECT wi.name n, ps.kind k, ps.capacity c, ps.inner_count ic,"
        " ps.inner_capacity ica, ps.inner_kind ik, ps.inner_unit iu FROM wh_pack_specs ps"
        " JOIN wh_items wi ON wi.id=ps.item_id WHERE ps.cycle=? ORDER BY ps.updated_at",
        (cycle,)).fetchall()
    conn.close()
    out = {}
    for r in rows:
        out.setdefault(r["n"], {})[r["k"]] = {"capacity": r["c"], "inner_count": r["ic"], "inner_capacity": r["ica"], "inner_kind": r["ik"] or "", "inner_unit": r["iu"] or ""}
    return out


def _conv_note(total, conv, from_unit, to_unit):
    """«١٢٠ لتر = ١٠٩٫٦٨ كجم» لما التغليف يتحول لوحدة الصنف (١٥/١٠)."""
    if abs(conv - 1.0) < 1e-12 or total <= 0:
        return ""
    return (f"{arnum.fmt_qty_trim(round(total / conv, 6))} {from_unit} = "
            f"{arnum.fmt_qty_trim(total)} {to_unit}")


def add_receipt(year, month, cycle, day, item_name, qty_handle,
                handle_unit_hint="", producer="", supplier_id=None,
                supplier_name="", prod_iso="", exp_iso="", notes="",
                date_iso="", receipt_no=None,
                pack_kind="", pack_count=0, pack_capacity=0, pack_loose=0,
                pack_inner_count=0, pack_inner_capacity=0, pack_loose_unit="",
                pack_inner_kind="", pack_inner_unit="", stores=None,
                allow_same_serial=False):
    """يحفظ إذن إضافة ١ مخازن — رقم يدوي والتغليف يحسب الكمية وstores للتوزيع."""
    from core import egtime
    pack_kind = (pack_kind or "").strip(); pack_inner_kind = (pack_inner_kind or "").strip()
    inner_unit = (pack_inner_unit or "").strip()
    pack_total = 0.0; pack_label_text = ""; extras = []; conv = 1.0; conv_note = ""
    if pack_kind and pack_kind != "بدون تغليف":
        # وحدة المعيار الداخلي (توجيه ١٠/١٠): لو اتحددت فهي الحاكمة لوحدة الإجمالي
        # ووحدة الصنف الجديد — «١٠ كرتونة × ١٢ زجاجة × ٢ لتر = ٢٤٠ لتر» مش كجم.
        # معيار بيُعدّ بلا وحدة ⇒ وحدته هي المعيار نفسه (توجيه ٢٧/٠٩).
        if inner_unit and is_measure_unit(inner_unit):
            handle_unit_hint = inner_unit
        elif pack_inner_kind and not is_measure_unit(pack_inner_kind) and not (handle_unit_hint or "").strip():
            handle_unit_hint = pack_inner_kind
        item_probe, _ = resolve_item(year, month, cycle, item_name, handle_unit_hint)
        # تغليف بوحدة غير وحدة الصنف ⇒ يتحول لوحدته بالوزن النوعي (١٥/١٠)
        _iu0 = inner_unit
        inner_unit, pack_capacity, pack_inner_capacity, pack_loose, conv = ou.pack_to_item_unit(
            item_probe, inner_unit, pack_capacity, pack_inner_capacity, pack_loose, pack_loose_unit)
        if ((pack_loose_unit or "").strip().startswith("علب") and float(pack_loose or 0) > 0 and not (float(pack_inner_capacity or 0) > 0) and (is_measure_unit(item_probe["handle_unit"]) or is_measure_unit((pack_inner_kind or "").strip()))):
            raise ValueError("السائب بالعلب محتاج وزن العلبة — اكتبه أو حوّل السائب للكجم")
        calc_unit = inner_unit if (inner_unit and is_measure_unit(inner_unit)) else item_probe["handle_unit"]
        pack_label_probe, pack_total = pack_summary(pack_kind, pack_count, pack_capacity, pack_loose, calc_unit, pack_inner_count, pack_inner_capacity, pack_loose_unit, pack_inner_kind)
        if pack_total <= 0:
            raise ValueError("اكتب عدد العبوات ووزن العبوة (أو العلب بداخلها) أو الكمية السائبة — "
                             "لا يمكن إذن إضافة بكمية صفر")
        qty_handle = pack_total
        pack_label_text = pack_label_probe
        conv_note = _conv_note(pack_total, conv, _iu0, item_probe["handle_unit"])
    # التغليف له عموده الخاص (توجيه ٢٦/٠٩) — لا يُخلط في الملاحظات
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
    parts = [(int(sid), (sname or "").strip(), round(float(q) * conv, 6))   # التوزيع بوحدة الفورم
             for sid, sname, q in (stores or []) if q and float(q) > 0]
    parts = default_store_parts(cycle, qty_handle, parts)   # مفيش «غير موزع» (١٤/١٠)
    if parts:
        diff = round(qty_handle - sum(q for _s, _n, q in parts), 6)
        if abs(diff) > 0.000001:
            raise ValueError("مجموع الكميات على المخازن لا يساوي كمية الإذن — وزّع الكمية كاملة")
        extras.append("مخازن: " + "، ".join(f"{n} ({arnum.fmt_qty(q)} {item['handle_unit']})" for _s, n, q in parts))
    conn = _conn(year, month)
    if receipt_no:
        if not allow_same_serial:
            exists = conn.execute("SELECT 1 FROM wh_receipts WHERE cycle=? AND serial=?", (cycle, int(receipt_no))).fetchone()
            if exists:
                conn.close()
                raise ValueError(f"رقم الإذن {arnum.to_arabic_indic(receipt_no)} مستخدم من قبل — اكتب رقمًا آخر")
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
                "pack_kind,pack_count,pack_capacity,pack_loose,"
                "pack_inner_count,pack_inner_capacity,pack_loose_unit,pack_inner_kind,pack_inner_unit)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cycle, serial, item["id"], day, date_iso, qty_handle, item["handle_unit"],
                 qty_base, base_unit, "{}", pack_label_text, (producer or "").strip(), supplier_id,
                 supplier_name, prod_iso, exp_iso, shelf_days, notes_text, stamp,
                 pack_kind, float(pack_count or 0), float(pack_capacity or 0),
                 float(pack_loose or 0), float(pack_inner_count or 0),
                 float(pack_inner_capacity or 0), (pack_loose_unit or "").strip(),
                 (pack_inner_kind or "").strip(), inner_unit))
            receipt_id = cur.lastrowid
            for sid, sname, q in parts:
                conn.execute(
                    "INSERT INTO wh_receipt_stores (receipt_id,store_id,store_name,qty)"
                    " VALUES (?,?,?,?)", (receipt_id, sid, sname, q))
            prev_balance = running_balance(conn, cycle, item["id"])
            conn.execute(
                "INSERT INTO wh_ledger (cycle,item_id,day,date_iso,kind,permit_no,label,"
                "added,issued,balance,notes,created_at,prod_date,exp_date,pack_label) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cycle, item["id"], day, date_iso, "add1", serial,
                 f"إذن إضافة ١ مخازن رقم {arnum.to_arabic_indic(serial)}",
                 qty_handle, 0.0, prev_balance + qty_handle, notes_text, stamp,
                 (prod_iso or ""), (exp_iso or ""), pack_label_text))
            _remember_spec(conn, cycle, item["id"], pack_kind, pack_capacity,
                           pack_inner_count, pack_inner_capacity, pack_inner_kind,
                           inner_unit)
    conn.close()
    return {
        "receipt_id": receipt_id, "serial": serial, "item": item, "created": created,
        "qty_handle": qty_handle, "qty_base": qty_base, "base_unit": base_unit,
        "factor": factor, "pack_label": pack_label_text, "conv_note": conv_note,
    }


@months.memo
def list_receipts(year, month, cycle, limit=10000):
    """إذون الدورة مع تفاصيل التغليف وتوزيعها على المخازن (من الأحدث)."""
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM wh_receipts WHERE cycle=? ORDER BY serial ASC, id ASC LIMIT ?",
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


# ========== ٣ مخازن — دفتر الصنف (كارت لكل صنف) + رصيد أول المدة + منصرف إذون ٢ مخازن ==========
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
               pack_inner_count=0, pack_inner_capacity=0, pack_loose_unit="",
               pack_inner_kind="", pack_inner_unit="", prod_iso="", exp_iso="",
               stores=None):
    """رصيد أول المدة: إدخال حقيقي بكل بياناته بتاريخه وتغليفه (توجيه ٢٥/٢٦/٠٩) —
    كمية + شركة منتجة + مورد + تغليف + إنتاج/صلاحية + توزيع على المخازن،
    تمامًا كإذن إضافة ١ مخازن. مرة واحدة لكل صنف وأول سطور الكارت."""
    from core import egtime
    inner_unit = (pack_inner_unit or "").strip()
    # وحدة المعيار الداخلي (توجيه ١٠/١٠) — الحاكمة لوحدة الإجمالي ووحدة الصنف الجديد؛
    # ومعيار بيُعدّ بلا وحدة ⇒ وحدته هي المعيار نفسه (توجيه ٢٧/٠٩)
    if inner_unit and is_measure_unit(inner_unit):
        handle_unit_hint = inner_unit
    elif (pack_kind and pack_kind != "بدون تغليف" and (pack_inner_kind or "").strip()
          and not is_measure_unit(pack_inner_kind) and not (handle_unit_hint or "").strip()):
        handle_unit_hint = pack_inner_kind.strip()
    item, created = resolve_item(year, month, cycle, item_name, handle_unit_hint)
    if has_opener(year, month, item["id"]):
        raise ValueError(
            f"رصيد أول المدة مسجّل بالفعل لصنف «{item['name']}» — لا يُسجل مرتين")
    _iu0 = inner_unit   # تغليف بوحدة غير وحدة الصنف ⇒ يتحول بالوزن النوعي (١٥/١٠)
    inner_unit, pack_capacity, pack_inner_capacity, pack_loose, conv = ou.pack_to_item_unit(
        item, inner_unit, pack_capacity, pack_inner_capacity, pack_loose, pack_loose_unit)
    pack_kind = (pack_kind or "").strip()
    if ((pack_loose_unit or "").strip().startswith("علب") and float(pack_loose or 0) > 0 and not (float(pack_inner_capacity or 0) > 0) and (is_measure_unit(item["handle_unit"]) or is_measure_unit((pack_inner_kind or "").strip()))):
        raise ValueError("السائب بالعلب محتاج وزن العلبة — اكتبه أو حوّل السائب للكجم")
    calc_unit = inner_unit if (inner_unit and is_measure_unit(inner_unit)) else item["handle_unit"]
    label_pack, pack_total = pack_summary(pack_kind, pack_count, pack_capacity, pack_loose, calc_unit, pack_inner_count, pack_inner_capacity, pack_loose_unit, pack_inner_kind)
    qty = pack_total if pack_total > 0 else float(qty)
    if qty <= 0:
        raise ValueError("اكتب كمية رصيد أول المدة أو بيانات التغليف")
    conv_note = _conv_note(pack_total, conv, _iu0, item["handle_unit"])
    prod_iso = (prod_iso or "").strip()
    exp_iso = (exp_iso or "").strip()
    if not exp_iso:
        raise ValueError("تاريخ الصلاحية إلزامي لرصيد أول المدة — زي أي صنف بالظبط")
    if prod_iso and exp_iso and exp_iso < prod_iso:
        raise ValueError("تاريخ الصلاحية قبل تاريخ الإنتاج — صحّح التواريخ")
    parts = [(int(sid), (sname or "").strip(), round(float(q) * (conv if pack_total > 0 else 1.0), 6))
             for sid, sname, q in (stores or []) if q and float(q) > 0]
    parts = default_store_parts(cycle, qty, parts)   # مفيش «غير موزع» (١٤/١٠)
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
    # التغليف له عموده الخاص في الدفتر — لا يُخلط في الملاحظات
    if (notes or "").strip():
        bits.append(notes.strip())
    conn = _conn(year, month)
    stamp = egtime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "INSERT INTO wh_ledger (cycle,item_id,day,date_iso,kind,permit_no,label,"
            "added,issued,balance,notes,created_at,prod_date,exp_date,pack_label) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cycle, item["id"], day, date_iso, "opener", 0, "رصيد أول المدة",
             qty, 0.0, qty + running_balance(conn, cycle, item["id"]),
             " — ".join(bits), stamp, prod_iso, exp_iso, label_pack))
        for sid, sname, q in parts:
            conn.execute(
                "INSERT INTO wh_opener_stores (cycle,item_id,store_id,store_name,qty)"
                " VALUES (?,?,?,?,?)", (cycle, item["id"], sid, sname, q))
        _remember_spec(conn, cycle, item["id"], pack_kind, pack_capacity,
                       pack_inner_count, pack_inner_capacity, pack_inner_kind,
                       inner_unit)
    conn.close()
    return {"item": item, "qty": qty, "created": created, "conv_note": conv_note}


def update_opener(year, month, cycle, item_id, qty, day,
                  producer="", supplier_id=None, supplier_name="",
                  notes="", date_iso="",
                  pack_kind="", pack_count=0, pack_capacity=0, pack_loose=0,
                  pack_inner_count=0, pack_inner_capacity=0, pack_loose_unit="",
                  pack_inner_kind="", pack_inner_unit="", prod_iso="", exp_iso="",
                  stores=None):
    """تعديل رصيد أول المدة (توجيه ٠٨/١٠): نفس فورم التسجيل مُعبّيًا — يُحدَّث
    سطر الأول المدة وتوزيعه على المخازن ومعاير التغليف، وكل الأرصدة اللي
    اتحسبت منه (الجدول/التفاريد/الإكسل) تتحسب من جديد تلقائيًا. الرصيد
    يشتغل بالسالب — المستخدم أجاز ذلك صراحةً."""
    item = get_item(year, month, item_id)
    if not item or not has_opener(year, month, item_id):
        raise ValueError("رصيد أول المدة غير مسجّل لهذا الصنف")
    if ((pack_loose_unit or "").strip().startswith("علب") and float(pack_loose or 0) > 0
            and not (float(pack_inner_capacity or 0) > 0)
            and (is_measure_unit(item["handle_unit"]) or is_measure_unit((pack_inner_kind or "").strip()))):
        raise ValueError("السائب بالعلب محتاج وزن العلبة — اكتبه أو حوّل السائب للكجم")
    pack_kind = (pack_kind or "").strip()
    if pack_kind == "بدون تغليف":
        pack_kind = ""
    _iu0 = inner_unit = (pack_inner_unit or "").strip()
    # تغليف بوحدة غير وحدة الصنف ⇒ يتحول لوحدته بالوزن النوعي (١٥/١٠)
    inner_unit, pack_capacity, pack_inner_capacity, pack_loose, conv = ou.pack_to_item_unit(
        item, inner_unit, pack_capacity, pack_inner_capacity, pack_loose, pack_loose_unit)
    calc_unit = inner_unit if (inner_unit and is_measure_unit(inner_unit)) else item["handle_unit"]
    label_pack, pack_total = pack_summary(pack_kind, pack_count, pack_capacity, pack_loose,
                                          calc_unit, pack_inner_count,
                                          pack_inner_capacity, pack_loose_unit, pack_inner_kind)
    qty = pack_total if pack_total > 0 else float(qty or 0)
    if qty <= 0:
        raise ValueError("اكتب كمية رصيد أول المدة أو بيانات التغليف")
    conv_note = _conv_note(pack_total, conv, _iu0, item["handle_unit"])
    prod_iso = (prod_iso or "").strip()
    exp_iso = (exp_iso or "").strip()
    if not exp_iso:
        raise ValueError("تاريخ الصلاحية إلزامي لرصيد أول المدة — زي أي صنف بالظبط")
    if prod_iso and exp_iso and exp_iso < prod_iso:
        raise ValueError("تاريخ الصلاحية قبل تاريخ الإنتاج — صحّح التواريخ")
    parts = [(int(sid), (sname or "").strip(), round(float(q) * (conv if pack_total > 0 else 1.0), 6))
             for sid, sname, q in (stores or []) if q and float(q) > 0]
    parts = default_store_parts(cycle, qty, parts)   # مفيش «غير موزع» (١٤/١٠)
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
    if (notes or "").strip():
        bits.append(notes.strip())
    conn = _conn(year, month)
    with conn:
        _op_id = conn.execute(
            "SELECT id FROM wh_ledger WHERE cycle=? AND item_id=? AND kind='opener'",
            (cycle, item_id)).fetchone()
        conn.execute(
            "UPDATE wh_ledger SET day=?, date_iso=?, added=?, balance=?, notes=?, "
            "prod_date=?, exp_date=?, pack_label=? "
            "WHERE cycle=? AND item_id=? AND kind='opener'",
            (day, date_iso, qty,
             qty + running_balance(conn, cycle, item_id,
                                   exclude_id=_op_id["id"] if _op_id else None),
             " — ".join(bits), prod_iso, exp_iso, label_pack, cycle, item_id))
        conn.execute("DELETE FROM wh_opener_stores WHERE cycle=? AND item_id=?",
                     (cycle, item_id))
        for sid, sname, q in parts:
            conn.execute(
                "INSERT INTO wh_opener_stores (cycle,item_id,store_id,store_name,qty)"
                " VALUES (?,?,?,?,?)", (cycle, item_id, sid, sname, q))
        _remember_spec(conn, cycle, item_id, pack_kind, pack_capacity,
                       pack_inner_count, pack_inner_capacity, pack_inner_kind,
                       inner_unit)
    conn.close()
    return {"item": item, "qty": qty, "created": False, "conv_note": conv_note}


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
    row = conn.execute("SELECT 1 FROM wh_receipts WHERE cycle=? AND item_id=? LIMIT 1", (cycle, item_id)).fetchone()
    if not row:
        row = conn.execute("SELECT 1 FROM wh_ledger WHERE cycle=? AND item_id=? LIMIT 1", (cycle, item_id)).fetchone()
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
    """حذف صنف يمسحه من كل حاجة — والتفريدة تتجدد بدونه (توجيه ٢٦/٠٩)."""
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


def set_specific_weight(year, month, item_id, value):
    """الوزن النوعي (جرام/لتر) — جسر الصنف اللي بيتصرف بالوزن ويخزن بالحجم."""
    try:
        sw = float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        sw = None
    if sw is not None and sw <= 0:
        sw = None
    conn = _conn(year, month)
    with conn:
        conn.execute("UPDATE wh_items SET specific_weight=? WHERE id=?", (sw, int(item_id)))
    conn.close()


def save_row_note(year, month, cycle, item_id, kind, permit_no, day, notes):
    """ملاحظة يدوية على سطر دفتر ٣ مخازن — تعلو على أي ملاحظات محسوبة،
    والفاص = سطر بلا ملاحظات (ماينزلش على المحسوبة)."""
    conn = _conn(year, month)
    with conn:
        conn.execute(
            "INSERT INTO wh_row_notes (cycle,item_id,kind,permit_no,day,notes,updated_at) "
            "VALUES (?,?,?,?,?,?,datetime('now')) "
            "ON CONFLICT(cycle,item_id,kind,permit_no,day) "
            "DO UPDATE SET notes=excluded.notes, updated_at=excluded.updated_at",
            (cycle, int(item_id), kind, int(permit_no or 0), int(day or 0), (notes or "").strip()))
    conn.close()


@months.memo
def row_notes_map(year, month, cycle, item_id):
    """{(kind, permit_no, day): notes} — ملاحظات المستخدم على أسطر صنف."""
    conn = _conn(year, month)
    out = {}
    for r in conn.execute(
            "SELECT kind, permit_no, day, notes FROM wh_row_notes WHERE cycle=? AND item_id=?",
            (cycle, int(item_id))):
        out[(r["kind"], int(r["permit_no"]), int(r["day"]))] = r["notes"]
    conn.close()
    return out


def issue_rows_for_item(year, month, cycle, item):
    """منصرف الصنف من إذون ٢ مخازن — كمية الإذن تتحول لوحدة تعامل الصنف.
    المنصرف في الدفتر = الاستهلاك الفعلي FEFO (نفس المخزن الفيزيائي)، ولو
    الفعلي أقل من الإذن بيتسجَّل عجز صريح في الملاحظات (قرار الجولة ٣٤):
    ورق الإذن بتتفرم كامله في ٢ مخازن، والدفتر بيتطابق مع اللي خرج فعلًا."""
    from core import arabic_numbers as arnum
    from data_access import db_warehouses_stores as dws
    actuals = dws.fefo_actual_map(year, month, cycle)
    rows = []
    for permit in permits_book(year, month, cycle):
        for entry in permit["cycle_items"]:
            if entry["name"] != item["name"]:
                continue
            # كمية الإذن بوحدة المقرر (اللي الحاسبة سجلتها فيها) والعجز بيتعرض
            # بوحدة الدفتر — الزيت: كجم (توجيه ١٠/١٠)
            qty = float(entry["qty"] or 0)
            _f_unit, _factor = ou.ledger_unit(
                item["name"], item["ration_unit"], item["handle_unit"],
                item.get("specific_weight"))
            _r2h = ou.calc_to_handle_factor(
                item["name"], item["ration_unit"], item["handle_unit"],
                item.get("specific_weight"))
            day = int(permit["date_from"])
            # المنصرف الفعلي (FEFO) بالوحدة المادية — العجز = (إذن بالمادي − المنصرف)
            # × معامل الدفتر، فيطلع بنفس وحدة الدفتر دايما
            issued = actuals.get((int(permit["number"]), item["name"]), 0.0)
            shortfall = round((qty * _r2h - issued) * _factor, 6)
            notes = permit.get("entity_label") or ""
            # 0٫٠١ بالوحدة الدقيقة = ضجيج أرقام عائمة (١٠ مللي جم) — ما ينفعش عجز
            # (الكجم: الضجيج ١ جم — حساسية أعلى زي اللي المستخدم بيتعامل بيها)
            if shortfall > (0.001 if _f_unit == "كجم" else 0.01):
                bits = "عجز: {} — اتصرف {} من {}".format(
                    arnum.fmt_qty(shortfall), arnum.fmt_qty(round(issued * _factor, 6)),
                    arnum.fmt_qty(round(qty * _r2h * _factor, 6)))
                notes = (notes + " — " if notes else "") + bits
            rows.append({
                "kind": "issue2", "day": day,
                "date_iso": f"{year:04d}-{month:02d}-{day:02d}",
                "permit_no": int(permit["number"]),
                "label": f"إذن صرف ٢ مخازن رقم {arnum.to_arabic_indic(permit['number'])}",
                "added": 0.0, "issued": issued,
                "notes": notes,
            })
    return rows


@months.memo
def item_card(year, month, item_id):
    """كارت الصنف: أول المدة + إضافات + منصرف بالترتيب الزمني والرصيد التراكمي."""
    item = get_item(year, month, item_id)
    if not item:
        return None
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM wh_ledger WHERE item_id=? ORDER BY date_iso, id", (item_id,))]
    conn.close()
    for r in issue_rows_for_item(year, month, item["cycle"], item):
        rows.append(r)
    ovr = row_notes_map(year, month, item["cycle"], item_id)
    for r in rows:                       # ملاحظات المستخدم فقط (والبتات الخام للتعديل)
        key = (r["kind"], int(r.get("permit_no") or 0), int(r.get("day") or 0))
        if key in ovr:                   # ملاحظة يدوية → تعلو على المحسوبة
            r["notes"] = ovr[key]
        r["raw_notes"] = r.get("notes") or ""
        r["notes"] = user_notes(r.get("notes"))
    from core import egtime
    from datetime import date as _date
    unit_disp, uf = ou.ledger_unit(item["name"], item["ration_unit"],
                                   item["handle_unit"], item.get("specific_weight"))
    for r in rows:                       # وحدة الدفتر: وحدة الإضافة (الزيت: كجم — قاعدة ١٢/١٠)
        try:
            r["wday"] = egtime.weekday_ar(_date(year, month, int(r.get("day") or 0)))
        except (TypeError, ValueError):
            r["wday"] = "—"
        r["added_d"] = arnum.round3(float(r["added"] or 0) * uf)
        r["issued_d"] = arnum.round3(float(r["issued"] or 0) * uf)

    def sort_key(r):   # رصيد أول المدة أول سطر دايمًا مهما كان يومه (١٥/١٠) — وبعده
        # الترتيب الزمني باليوم (الإضافات قبل المنصرف في نفس اليوم)؛
        # day هو المرجع الدقيق؛ date_iso ممكن يكون فاضي في استلامات ١ مخازن
        return (0 if r["kind"] == "opener" else 1, int(r.get("day") or 0),
                {"opener": 0, "add1": 1}.get(r["kind"], 2), r.get("permit_no") or 0)
    rows.sort(key=sort_key)
    running = 0.0
    out = []
    for r in rows:
        r["open"] = running                                  # رصيد افتتاح اليوم
        running += float(r["added"] or 0) - float(r["issued"] or 0)
        r["balance"] = running                               # رصيد ختام اليوم
        r["open_d"] = arnum.round3(r["open"] * uf)
        r["balance_d"] = arnum.round3(running * uf)
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
        "unit_disp": unit_disp,
        "unit_factor": uf,
        "total_added_d": arnum.round3(sum(float(r["added"] or 0) for r in out) * uf),
        "total_issued_d": arnum.round3(sum(float(r["issued"] or 0) for r in out) * uf),
        "balance_d": arnum.round3(running * uf),
    }


# ========== دفتر ٢ مخازن — إذون آلة الحاسبة (عرض؛ الخصم التلقائي مع ٤–٧ مخازن) ==========
@months.memo
def permits_book(year, month, cycle):
    """أذون ٢ مخازن وأصناف دورة {cycle} — actuals تفصل التموين عن المتعهد."""
    from data_access import db_permits as dp
    prefix = SECTION_BY_CYCLE[cycle] + "_"
    conn = _conn(year, month)
    catalog_units = {r["name"]: r["unit"] for r in conn.execute(
        "SELECT name, unit FROM ration_items WHERE section=?",
        (SECTION_BY_CYCLE[cycle],))}
    handle_units = {r["name"]: r["handle_unit"] for r in conn.execute(
        "SELECT name, handle_unit FROM wh_items WHERE cycle=?", (cycle,))}
    dw_raw = [dict(r) for r in conn.execute(
        "SELECT name, ration_unit, handle_unit, specific_weight FROM wh_items WHERE cycle=?",
        (cycle,))]
    conn.close()
    out = []
    # الكميات الفعلية محفوظة بوحدة الحاسبة (١٣/١٠: وحدة إضافة الصنف —
    # الزيت كجم) — التسمية بوحدة الحاسبة مش وحدة الدفتر
    calc_units = {}
    for it in dw_raw:
        calc_units[it["name"]] = ou.calc_unit(
            it["name"], it["ration_unit"],
            it.get("specific_weight"))[0]
    for permit in dp.list_permits(year, month):
        items = []
        for key, qty in (permit.get("actuals") or {}).items():
            if not str(key).startswith(prefix):
                continue
            name = str(key)[len(prefix):]
            unit = calc_units.get(name) or handle_units.get(name) \
                or catalog_units.get(name) or ""
            items.append({"name": name, "qty": qty, "unit": unit})
        if not items:
            continue   # عزل تام: إذن بلا أصناف لهذه الدورة لا يظهر في دفترها إطلاقًا
        items.sort(key=lambda x: x["name"])
        out.append({**permit, "cycle_items": items})
    return out

def delete_receipt(year, month, cycle, serial):
    """مسح إذن إضافة بسطوره وتوزيعه — تمهيدًا لإعادة حفظه بعد التعديل (توجيه ٢٧/٠٩)."""
    conn = _conn(year, month)
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM wh_receipts WHERE cycle=? AND serial=?", (cycle, int(serial)))]
    for rid in ids:
        conn.execute("DELETE FROM wh_receipt_stores WHERE receipt_id=?",(rid,))
        conn.execute("DELETE FROM wh_receipts WHERE id=?",(rid,))
    conn.execute("DELETE FROM wh_ledger WHERE cycle=? AND kind='add1' AND permit_no=?",(cycle,int(serial)))
    conn.commit(); conn.close()
    return bool(ids)


# المخازن الفيزيائية: التفريدة وحركة المخازن — عاشت في db_warehouses_stores
# (قاعدة الملف ≤1000 سطر — نفس نمط db_pack)
from data_access.db_warehouses_stores import (  # noqa: E402,F401
    UNASSIGNED, NO_EXPIRY, receipt_groups, user_notes, _batch_pool,
    _rem_label, tafreeda_rows, stores_report, stores_general_report,
    default_store_parts, assign_unassigned)

# إعادة تصدير — دوال التغليف عاشت في db_pack (قاعدة الملف ≤1000 سطر)
from data_access.db_pack import card_pack_rows, collect_pack_kinds  # noqa: E402,F401
