# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""طبقة بيانات توزيع المقررات على الجهات — كلها داخل month.db.

قواعد العمل:
- الجهة الجديدة تُسحب لها أصناف المقرر النشط **في قسمها نفسه** (المتعهد ← المتعهد،
  ولو لا مقرر مفعّل يُستخدم الصيفي احتياطيًا) — بأرقامها (فطار/غداء/عشاء).
- تخصيص الأيام: لكل يوم محدد مقرر خاص اختياري (qty)؛ الفارغ = قيمة الوجبات العامة.
- لا أيام محددة إطلاقًا = الصنف يُصرف يوميًا.
- زر «🔄 تحديث من المقرر النشط» يعيد سحب الأصناف للجهة الموجودة بالفعل.
"""
from data_access import months
from data_access import db_rations as dr


def _seed_qty(conn, eid, src_items):
    for it in src_items:
        conn.execute(
            "INSERT INTO entity_items (entity_id,serial,name,unit,breakfast,lunch,dinner) "
            "VALUES (?,?,?,?,?,?,?)",
            (eid, it["serial"], it["name"], it["unit"],
             it["breakfast"], it["lunch"], it["dinner"]))


def list_entities(year, month):
    conn = months.get_db(year, month)
    entities = [dict(r) for r in conn.execute(
        "SELECT * FROM entities ORDER BY serial").fetchall()]
    for e in entities:
        items = [dict(r) for r in conn.execute(
            "SELECT * FROM entity_items WHERE entity_id=? ORDER BY serial",
            (e["id"],)).fetchall()]
        day_map = {}
        for d in conn.execute(
                "SELECT eid.entity_item_id iid, eid.weekday wd, eid.qty q "
                "FROM entity_item_days eid "
                "JOIN entity_items ei ON ei.id=eid.entity_item_id "
                "WHERE ei.entity_id=?",
                (e["id"],)):
            day_map.setdefault(d["iid"], {})[d["wd"]] = d["q"]
        for it in items:
            dq = day_map.get(it["id"], {})
            it["day_qty"] = dq               # {اليوم: المقرر أو None}
            it["days"] = sorted(dq.keys())
            it["is_custom"] = bool(dq)
        e["items"] = items
    conn.close()
    return entities


def _active_kind_items(year, month, section):
    """أصناف المقرر النشط في القسم نفسه (أو الصيفي احتياطيًا)."""
    kind = dr.get_activation(year, month, section) or "summer"
    items, _ = dr.get_items(year, month, section, kind)
    return kind, items


def add_entity(year, month, section, name):
    """يضيف جهة ويسحب لها أصناف مقرر قسمها النشط. يرجع (عدد الأصناف, نوع المقرر)."""
    kind, src_items = _active_kind_items(year, month, section)
    conn = months.get_db(year, month)
    serial = conn.execute(
        "SELECT COALESCE(MAX(serial),0)+1 s FROM entities").fetchone()["s"]
    cur = conn.execute("INSERT INTO entities (name, serial) VALUES (?,?)",
                       (name, serial))
    _seed_qty(conn, cur.lastrowid, src_items)
    conn.commit()
    conn.close()
    return len(src_items), kind


def resync_entity(year, month, entity_id, section):
    """يمسح أصناف الجهة الحالية ويعيد سحبها من المقرر النشط (يستبدل أيامها وقيمها)."""
    kind, src_items = _active_kind_items(year, month, section)
    conn = months.get_db(year, month)
    conn.execute("DELETE FROM entity_items WHERE entity_id=?", (entity_id,))
    _seed_qty(conn, entity_id, src_items)
    conn.commit()
    conn.close()
    return len(src_items), kind


def delete_entity(year, month, entity_id):
    conn = months.get_db(year, month)
    conn.execute("DELETE FROM entities WHERE id=?", (entity_id,))
    conn.commit()
    conn.close()


def entity_item_exists(year, month, entity_id, name):
    """منع تكرار اسم الصنف داخل جهة واحدة."""
    conn = months.get_db(year, month)
    row = conn.execute(
        "SELECT 1 FROM entity_items WHERE entity_id=? AND TRIM(name)=TRIM(?)",
        (entity_id, name)).fetchone()
    conn.close()
    return row is not None


def add_entity_item(year, month, entity_id, name, unit, breakfast, lunch, dinner):
    conn = months.get_db(year, month)
    serial = conn.execute(
        "SELECT COALESCE(MAX(serial),0)+1 s FROM entity_items WHERE entity_id=?",
        (entity_id,)).fetchone()["s"]
    conn.execute(
        "INSERT INTO entity_items (entity_id,serial,name,unit,breakfast,lunch,dinner) "
        "VALUES (?,?,?,?,?,?,?)",
        (entity_id, serial, name, unit, breakfast, lunch, dinner))
    conn.commit()
    conn.close()


def update_entity_item(year, month, item_id, name, unit, breakfast, lunch, dinner):
    conn = months.get_db(year, month)
    conn.execute(
        "UPDATE entity_items SET name=?, unit=?, breakfast=?, lunch=?, dinner=? WHERE id=?",
        (name, unit, breakfast, lunch, dinner, item_id))
    conn.commit()
    conn.close()


def delete_entity_item(year, month, item_id):
    conn = months.get_db(year, month)
    conn.execute("DELETE FROM entity_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()


def get_entity_item(year, month, item_id):
    conn = months.get_db(year, month)
    row = conn.execute("SELECT * FROM entity_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_days(year, month, entity_item_id, day_qty):
    """يستبدل تخصيص أيام الصنف: {يوم(0-6): مقرر أو None}. قاموس فاضي = صرف يومي."""
    conn = months.get_db(year, month)
    conn.execute("DELETE FROM entity_item_days WHERE entity_item_id=?",
                 (entity_item_id,))
    for wd in sorted(day_qty):
        if 0 <= wd <= 6:
            conn.execute(
                "INSERT INTO entity_item_days (entity_item_id, weekday, qty) "
                "VALUES (?,?,?)",
                (entity_item_id, wd, day_qty[wd]))
    conn.commit()
    conn.close()
