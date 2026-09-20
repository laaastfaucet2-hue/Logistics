# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""طبقة بيانات توزيع مقررات المتعهد على الجهات — كلها داخل month.db."""
import months
import db_rations as dr


def list_entities(year, month):
    conn = months.get_db(year, month)
    entities = [dict(r) for r in conn.execute(
        "SELECT * FROM entities ORDER BY serial").fetchall()]
    for e in entities:
        items = [dict(r) for r in conn.execute(
            "SELECT * FROM entity_items WHERE entity_id=? ORDER BY serial",
            (e["id"],)).fetchall()]
        days = {}
        for d in conn.execute(
                "SELECT eid.entity_item_id, eid.weekday FROM entity_item_days eid "
                "JOIN entity_items ei ON ei.id=eid.entity_item_id WHERE ei.entity_id=?",
                (e["id"],)):
            days.setdefault(d["entity_item_id"], set()).add(d["weekday"])
        for it in items:
            ds = sorted(days.get(it["id"], set()))
            it["days"] = ds
            it["is_custom"] = bool(ds)
        e["items"] = items
    conn.close()
    return entities


def add_entity(year, month, name):
    """يضيف جهة ويسحب لها أصناف المقرر التموني المفعّل (أو الصيفي احتياطيًا)."""
    kind = dr.get_activation(year, month, "tamween") or "summer"
    src_items, _ = dr.get_items(year, month, "tamween", kind)
    conn = months.get_db(year, month)
    serial = conn.execute("SELECT COALESCE(MAX(serial),0)+1 s FROM entities").fetchone()["s"]
    cur = conn.execute("INSERT INTO entities (name, serial) VALUES (?,?)", (name, serial))
    eid = cur.lastrowid
    for it in src_items:
        conn.execute(
            "INSERT INTO entity_items (entity_id,serial,name,unit,breakfast,lunch,dinner) "
            "VALUES (?,?,?,?,?,?,?)",
            (eid, it["serial"], it["name"], it["unit"],
             it["breakfast"], it["lunch"], it["dinner"]))
    conn.commit()
    conn.close()
    return len(src_items)


def delete_entity(year, month, entity_id):
    conn = months.get_db(year, month)
    conn.execute("DELETE FROM entities WHERE id=?", (entity_id,))
    conn.commit()
    conn.close()


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


def set_days(year, month, entity_item_id, weekdays):
    """يستبدل أيام تخصيص الصنف. قائمة فاضية = صرف يومي عادي."""
    conn = months.get_db(year, month)
    conn.execute("DELETE FROM entity_item_days WHERE entity_item_id=?", (entity_item_id,))
    conn.executemany(
        "INSERT INTO entity_item_days (entity_item_id, weekday) VALUES (?,?)",
        [(entity_item_id, d) for d in sorted(set(weekdays)) if 0 <= d <= 6])
    conn.commit()
    conn.close()
