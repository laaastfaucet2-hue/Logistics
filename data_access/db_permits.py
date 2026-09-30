# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""أذون صرف ٢ مخازن — رقم البون لسنة ١ يوليو–٣٠ يونيو، والسجلات داخل month.db."""
import json
from data_access import months, database
from core import egtime

SCHEMA = """
CREATE TABLE IF NOT EXISTS calc2_permits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number INTEGER NOT NULL,
    fiscal_year INTEGER NOT NULL,
    date_from INTEGER NOT NULL,
    date_to INTEGER NOT NULL,
    issue_days INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT 'combined',
    entity_label TEXT NOT NULL DEFAULT '',
    officers INTEGER NOT NULL DEFAULT 0,
    individuals INTEGER NOT NULL DEFAULT 0,
    recruits INTEGER NOT NULL DEFAULT 0,
    meals TEXT NOT NULL DEFAULT '["breakfast","lunch","dinner"]',
    receiver_kind TEXT NOT NULL DEFAULT '',
    receiver_rank TEXT NOT NULL DEFAULT '',
    receiver_name TEXT NOT NULL DEFAULT '',
    issuer_name TEXT NOT NULL DEFAULT '',
    record_ids TEXT NOT NULL DEFAULT '[]',
    actuals TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
"""


def _conn(year, month):
    conn = months.get_db(year, month)
    conn.executescript(SCHEMA)
    return conn


def _seq_key(fiscal_year):
    return f"permit_seq_{int(fiscal_year)}"


def peek_next_number(when=None):
    fiscal = egtime.permit_fiscal_year(when)
    raw = database.get_setting(_seq_key(fiscal)) or "0"
    try:
        last = int(raw)
    except (TypeError, ValueError):
        last = 0
    return last + 1, fiscal


def take_number(posted=None, when=None):
    """يرجع الرقم المستخدم ويحدّث السلسلة. رقم يدوي أكبر من الأخير يصبح الأصل."""
    fiscal = egtime.permit_fiscal_year(when)
    key = _seq_key(fiscal)
    raw = database.get_setting(key) or "0"
    try:
        last = int(raw)
    except (TypeError, ValueError):
        last = 0
    if posted:
        number = int(posted)
    else:
        number = last + 1
    if number > last:
        database.set_setting(key, str(number))
    return number, fiscal


def permit_number_exists(year, month, number, fiscal_year=None):
    """هل رقم الإذن مستخدم بالفعل في السنة المالية؟ (لتحديث بدل التكرار)"""
    conn = _conn(year, month)
    fiscal = fiscal_year or egtime.permit_fiscal_year()
    row = conn.execute(
        "SELECT 1 FROM calc2_permits WHERE number=? AND fiscal_year=? LIMIT 1",
        (int(number), int(fiscal))).fetchone()
    conn.close()
    return bool(row)


def strip_item_from_permits(year, month, section, name):
    """حذف صنف: يمسحه من كميات كل أذون الصرف المحفوظة (توجيه «يحذف من كل حاجة»)."""
    prefix = "tamween_" if section == "tamween" else "contractor_"
    key = prefix + name
    conn = _conn(year, month)
    touched = 0
    with conn:
        for row in conn.execute("SELECT id, actuals FROM calc2_permits").fetchall():
            try:
                actuals = json.loads(row["actuals"] or "{}")
            except (ValueError, TypeError):
                continue
            if key in actuals:
                actuals.pop(key, None)
                conn.execute("UPDATE calc2_permits SET actuals=? WHERE id=?",
                             (json.dumps(actuals, ensure_ascii=False), row["id"]))
                touched += 1
    conn.close()
    return touched


def save_permit(year, month, data):
    """يحفظ إذن الصرف — والرقم الموجود مسبقًا يُستبدل (تحديث) لا يتكرر."""
    conn = _conn(year, month)
    stamp = egtime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "DELETE FROM calc2_permits WHERE number=? AND fiscal_year=?",
            (int(data["number"]), int(data["fiscal_year"])))
        cur = conn.execute(
            "INSERT INTO calc2_permits (number, fiscal_year, date_from, date_to, issue_days,"
            " mode, entity_label, officers, individuals, recruits, meals,"
            " receiver_kind, receiver_rank, receiver_name, issuer_name,"
            " record_ids, actuals, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (data["number"], data["fiscal_year"], data["date_from"], data["date_to"],
             data["issue_days"], data["mode"], data["entity_label"],
             data["officers"], data["individuals"], data["recruits"],
             json.dumps(data.get("meals") or ["breakfast", "lunch", "dinner"]),
             data.get("receiver_kind") or "", data.get("receiver_rank") or "",
             data.get("receiver_name") or "", data.get("issuer_name") or "",
             json.dumps(data.get("record_ids") or []),
             json.dumps(data.get("actuals") or {}), stamp))
        pid = cur.lastrowid
    conn.close()
    return pid


def permits_by_record(year, month):
    """{record_id: [أذون]} — أي إذن محفوظ مربوط بالتأميدة."""
    out = {}
    for permit in list_permits(year, month):
        for rid in permit["record_ids"]:
            try:
                key = int(rid)
            except (TypeError, ValueError):
                continue
            out.setdefault(key, []).append(permit)
    return out


def list_permits(year, month):
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM calc2_permits ORDER BY number, id").fetchall()]
    conn.close()
    for row in rows:
        row["meals"] = json.loads(row["meals"] or "[]")
        row["record_ids"] = json.loads(row["record_ids"] or "[]")
        row["actuals"] = json.loads(row["actuals"] or "{}")
    return rows


def issued_days(year, month):
    """أيام الشهر التي غطاها أي إذن محفوظ."""
    days = set()
    for permit in list_permits(year, month):
        start = permit["date_from"]
        span = max(1, int(permit["issue_days"]))
        for day in range(start, start + span):
            if day <= permit["date_to"]:
                days.add(day)
    return days


def covered_days(year, month, record_id):
    """أيام التأميدة التي غطاها إذن محفوظ."""
    days = set()
    for permit in list_permits(year, month):
        if int(record_id) not in [int(x) for x in permit["record_ids"]]:
            continue
        start = permit["date_from"]
        span = max(1, int(permit["issue_days"]))
        for day in range(start, start + span):
            if day <= permit["date_to"]:
                days.add(day)
    return days
