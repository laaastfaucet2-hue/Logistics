# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""«٢ مخازن حرة» — معدلات توزيع مستقلة + إذون تجريبية برقمها الخاص.

فصل تام عن النظام الحقيقي: لا أثر على calc2_permits ولا على ترقيم الإذون
ولا على أرصدة المخازن ولا على التفريدة — البيانات جوا قاعدة الشهر المحلية.
"""
import json

from core import egtime
from data_access import months

SCHEMA = """
CREATE TABLE IF NOT EXISTS c2f_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    rate REAL NOT NULL DEFAULT 0,
    UNIQUE (cycle, name)
);
CREATE TABLE IF NOT EXISTS c2f_seq (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_number INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS c2f_permits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number INTEGER NOT NULL UNIQUE,
    fiscal_year INTEGER NOT NULL,
    date_from INTEGER NOT NULL,
    date_to INTEGER NOT NULL,
    issue_days INTEGER NOT NULL,
    entity_label TEXT NOT NULL DEFAULT '',
    officers INTEGER NOT NULL DEFAULT 0,
    individuals INTEGER NOT NULL DEFAULT 0,
    recruits INTEGER NOT NULL DEFAULT 0,
    meals TEXT NOT NULL DEFAULT '[]',
    receiver_kind TEXT NOT NULL DEFAULT '',
    receiver_rank TEXT NOT NULL DEFAULT '',
    receiver_name TEXT NOT NULL DEFAULT '',
    issuer_name TEXT NOT NULL DEFAULT '',
    record_ids TEXT NOT NULL DEFAULT '[]',
    rates TEXT NOT NULL DEFAULT '{}',
    items TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
"""

SECTIONS = ("tamween", "contractor")


def _conn(year, month):
    conn = months.get_db(year, month)
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO c2f_seq (id, last_number) VALUES (1, 0)")
    return conn


def _stamp():
    return egtime.now().isoformat(timespec="seconds")


# ======================================================================
# معدلات التوزيع المستقلة (تبدأ نسخة من معدلات الشهر الحالي — توجيه ٠٨/١٠)
# ======================================================================
def get_rates(year, month):
    """{cycle: {name: {"unit", "rate"}}} لكل قسم من قسمي المقررات."""
    conn = _conn(year, month)
    out = {c: {} for c in SECTIONS}
    for r in conn.execute("SELECT cycle, name, unit, rate FROM c2f_rates"):
        out.setdefault(r["cycle"], {})[r["name"]] = {"unit": r["unit"], "rate": r["rate"]}
    conn.close()
    return out


def count_rates(year, month):
    conn = _conn(year, month)
    n = conn.execute("SELECT COUNT(*) AS n FROM c2f_rates").fetchone()["n"]
    conn.close()
    return n


def seed_from_catalog(year, month):
    """أول فتح في الشهر: نسخة من معدل الفرد اليومى (فطار+غداء+عشاء) من القاموس."""
    if count_rates(year, month) > 0:
        return False
    from data_access import db_rations as dr
    conn = _conn(year, month)
    added = 0
    for section in SECTIONS:
        kind = dr.get_activation(year, month, section) or "summer"
        rows, _custom = dr.get_items(year, month, section, kind)
        for item in rows:
            name = " ".join((item.get("name") or "").split())
            if not name:
                continue
            rate = (float(item.get("breakfast") or 0) + float(item.get("lunch") or 0)
                    + float(item.get("dinner") or 0))
            conn.execute(
                "INSERT OR IGNORE INTO c2f_rates (cycle, name, unit, rate) VALUES (?, ?, ?, ?)",
                (section, name, item.get("unit") or "", round(rate, 6)))
            added += 1
    conn.commit()
    conn.close()
    return added > 0


def save_rate(year, month, cycle, name, rate, unit=""):
    """تحديث معدل صنف واحد (INSERT OR REPLACE)."""
    if cycle not in SECTIONS:
        return
    name = " ".join((name or "").split())
    if not name:
        return
    try:
        rate = round(float(rate), 6)
    except (TypeError, ValueError):
        return
    conn = _conn(year, month)
    conn.execute(
        "INSERT INTO c2f_rates (cycle, name, unit, rate) VALUES (?, ?, ?, ?)"
        " ON CONFLICT(cycle, name) DO UPDATE SET rate=excluded.rate,"
        " unit = CASE WHEN excluded.unit != '' THEN excluded.unit ELSE c2f_rates.unit END",
        (cycle, name, unit or "", rate))
    conn.commit()
    conn.close()


# ======================================================================
# ترقيم الإذون التجريبية (سلسلة مستقلة تمامًا عن ترقيم الإذون الحقيقية)
# ======================================================================
def next_number(year, month):
    conn = _conn(year, month)
    row = conn.execute("SELECT last_number FROM c2f_seq WHERE id=1").fetchone()
    nxt = int(row["last_number"] or 0) + 1
    conn.execute("UPDATE c2f_seq SET last_number=? WHERE id=1", (nxt,))
    conn.commit()
    conn.close()
    return nxt


# ======================================================================
# الإذون التجريبية المحفوظة
# ======================================================================
def save_permit(year, month, data):
    conn = _conn(year, month)
    cur = conn.execute(
        "INSERT INTO c2f_permits ("
        "number, fiscal_year, date_from, date_to, issue_days,"
        " entity_label, officers, individuals, recruits, meals,"
        " receiver_kind, receiver_rank, receiver_name, issuer_name,"
        " record_ids, rates, items, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data["number"], data.get("fiscal_year") or 0,
         int(data["date_from"]), int(data["date_to"]), int(data["issue_days"]),
         data.get("entity_label") or "",
         int(data.get("officers") or 0), int(data.get("individuals") or 0),
         int(data.get("recruits") or 0), json.dumps(data.get("meals") or []),
         data.get("receiver_kind") or "", data.get("receiver_rank") or "",
         data.get("receiver_name") or "", data.get("issuer_name") or "",
         json.dumps(data.get("record_ids") or []),
         json.dumps(data.get("rates") or {}, ensure_ascii=False),
         json.dumps(data.get("items") or [], ensure_ascii=False),
         _stamp()))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def _hydrate(row):
    out = dict(row)
    for key, cast in (("meals", list), ("record_ids", list), ("rates", dict), ("items", list)):
        try:
            out[key] = json.loads(out.get(key) or ("[]" if key in ("meals", "record_ids", "items") else "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            out[key] = [] if key in ("meals", "record_ids", "items") else {}
    return out


def list_permits(year, month):
    conn = _conn(year, month)
    rows = [_hydrate(r) for r in conn.execute(
        "SELECT * FROM c2f_permits ORDER BY number DESC")]
    conn.close()
    return rows


def get_permit(year, month, permit_id):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM c2f_permits WHERE id=?", (int(permit_id),)).fetchone()
    conn.close()
    return _hydrate(row) if row else None


def delete_permit(year, month, permit_id):
    conn = _conn(year, month)
    conn.execute("DELETE FROM c2f_permits WHERE id=?", (int(permit_id),))
    conn.commit()
    conn.close()
