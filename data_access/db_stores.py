# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""المخازن الفيزيائية — سجل عام مستمر في system.db (لا يتأثر بعزل الشهور).

المخزن أصل مستمر: الاسم/الموقع/السعة بالمتر/عدد المرواح/عدد الشفاطات/التجهيزات.
الحركة والأرصدة شهرية معزولة داخل month.db (انظر db_warehouses.tafreeda_*).
"""
from data_access import database

SCHEMA = """
CREATE TABLE IF NOT EXISTS wh_stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT DEFAULT '',
    capacity_m2 REAL,
    fans INTEGER,
    extractors INTEGER,
    equipment TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def _conn():
    conn = database.get_conn()
    conn.executescript(SCHEMA)
    return conn


def list_stores():
    conn = _conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM wh_stores ORDER BY id")]
    conn.close()
    return rows


def get_store(store_id):
    conn = _conn()
    row = conn.execute("SELECT * FROM wh_stores WHERE id=?", (store_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_store(name, location="", capacity_m2=None, fans=None, extractors=None,
              equipment="", notes=""):
    from core import egtime
    conn = _conn()
    with conn:
        conn.execute(
            "INSERT INTO wh_stores (name,location,capacity_m2,fans,extractors,"
            "equipment,notes,created_at) VALUES (?,?,?,?,?,?,?,?)",
            ((name or "").strip(), (location or "").strip(), capacity_m2,
             fans, extractors, (equipment or "").strip(), (notes or "").strip(),
             egtime.now().isoformat(timespec="seconds")))
    conn.close()


def update_store(store_id, name, location="", capacity_m2=None, fans=None,
                 extractors=None, equipment="", notes=""):
    conn = _conn()
    with conn:
        conn.execute(
            "UPDATE wh_stores SET name=?, location=?, capacity_m2=?, fans=?,"
            " extractors=?, equipment=?, notes=? WHERE id=?",
            ((name or "").strip(), (location or "").strip(), capacity_m2,
             fans, extractors, (equipment or "").strip(), (notes or "").strip(),
             store_id))
    conn.close()


def delete_store(store_id):
    conn = _conn()
    with conn:
        conn.execute("DELETE FROM wh_stores WHERE id=?", (store_id,))
    conn.close()
