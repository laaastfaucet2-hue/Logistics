# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""لقطة المقررات المخصصة لتأميدة واحدة — لا تمس جداول المقررات العامة."""
import json
from data_access import months

SCHEMA = """
CREATE TABLE IF NOT EXISTS tameed_ration_snap (
    record_id INTEGER PRIMARY KEY,
    payload TEXT NOT NULL DEFAULT '{}'
);
"""


def _conn(year, month):
    conn = months.get_db(year, month)
    conn.executescript(SCHEMA)
    return conn


def get_payload(year, month, record_id):
    conn = _conn(year, month)
    row = conn.execute(
        "SELECT payload FROM tameed_ration_snap WHERE record_id=?",
        (record_id,)).fetchone()
    conn.close()
    if not row:
        return {}
    try:
        data = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_payload(year, month, record_id, payload):
    conn = _conn(year, month)
    blob = json.dumps(payload or {}, ensure_ascii=False)
    with conn:
        conn.execute(
            "INSERT INTO tameed_ration_snap(record_id, payload) VALUES(?,?) "
            "ON CONFLICT(record_id) DO UPDATE SET payload=excluded.payload",
            (record_id, blob))
    conn.close()


def delete_payload(year, month, record_id):
    conn = _conn(year, month)
    with conn:
        conn.execute("DELETE FROM tameed_ration_snap WHERE record_id=?", (record_id,))
    conn.close()


def copy_payload(year, month, source_id, dest_id):
    data = get_payload(year, month, source_id)
    if data:
        save_payload(year, month, dest_id, data)
