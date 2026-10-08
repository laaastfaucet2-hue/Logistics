# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""«تفاريد الدولى» — خطوط الحراسة ونقاطها + معدلات الدولى + سجل حفظ التفاريد.

كل البيانات جوا قاعدة الشهر المحلية (month.db) — مفيش أي علاقة بترقيم الإذون.
"""
import json

from core import egtime
from data_access import months

SCHEMA = """
CREATE TABLE IF NOT EXISTS dw_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dw_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    force INTEGER NOT NULL DEFAULT 0,
    responsible TEXT NOT NULL DEFAULT '',
    UNIQUE (line_id, name)
);
CREATE TABLE IF NOT EXISTS dw_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    rate REAL NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    production_year TEXT NOT NULL DEFAULT '',
    is_extra INTEGER NOT NULL DEFAULT 0,
    UNIQUE (section, name)
);
CREATE TABLE IF NOT EXISTS dw_saves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    date_from INTEGER NOT NULL,
    date_to INTEGER NOT NULL,
    issue_days INTEGER NOT NULL,
    store_keeper TEXT NOT NULL DEFAULT '',
    scribe TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL,
    files TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
"""


def _conn(year, month):
    conn = months.get_db(year, month)
    conn.executescript(SCHEMA)
    return conn


def _stamp():
    return egtime.now().isoformat(timespec="seconds")


# ======================================================================
# الخطوط
# ======================================================================
def list_lines(year, month):
    """خطوط مع (عدد الأوراق، عدد النشطة، إجمالي القوة)."""
    conn = _conn(year, month)
    out = []
    for row in conn.execute("SELECT * FROM dw_lines ORDER BY id"):
        line = dict(row)
        pts = [dict(p) for p in conn.execute(
            "SELECT * FROM dw_points WHERE line_id=? ORDER BY id", (line["id"],))]
        line["points"] = pts
        line["count"] = len(pts)
        line["active"] = sum(1 for p in pts if (p["force"] or 0) > 0)
        line["total_force"] = sum(int(p["force"] or 0) for p in pts)
        out.append(line)
    conn.close()
    return out


def get_line(year, month, line_id):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM dw_lines WHERE id=?", (int(line_id),)).fetchone()
    pts = [dict(p) for p in conn.execute(
        "SELECT * FROM dw_points WHERE line_id=? ORDER BY id", (int(line_id),))]
    conn.close()
    if not row:
        return None
    line = dict(row)
    line["points"] = pts
    line["count"] = len(pts)
    line["active"] = sum(1 for p in pts if (p["force"] or 0) > 0)
    line["total_force"] = sum(int(p["force"] or 0) for p in pts)
    return line


def add_line(year, month, name):
    name = " ".join((name or "").split())
    if not name:
        return None
    conn = _conn(year, month)
    try:
        cur = conn.execute("INSERT INTO dw_lines (name, created_at) VALUES (?, ?)",
                           (name, _stamp()))
        new_id = cur.lastrowid
        conn.commit()
    except Exception:
        conn.close()
        return None
    conn.close()
    return new_id


def delete_line(year, month, line_id):
    conn = _conn(year, month)
    conn.execute("DELETE FROM dw_points WHERE line_id=?", (int(line_id),))
    conn.execute("DELETE FROM dw_lines WHERE id=?", (int(line_id),))
    conn.commit()
    conn.close()


# ======================================================================
# النقاط
# ======================================================================
def add_point(year, month, line_id, name, force):
    name = " ".join((name or "").split())
    if not name:
        return None
    try:
        force = int(force or 0)
    except (TypeError, ValueError):
        force = 0
    conn = _conn(year, month)
    try:
        cur = conn.execute(
            "INSERT INTO dw_points (line_id, name, force) VALUES (?, ?, ?)",
            (int(line_id), name, force))
        new_id = cur.lastrowid
        conn.commit()
    except Exception:
        conn.close()
        return None
    conn.close()
    return new_id


def update_point(year, month, point_id, force=None, name=None, responsible=None):
    conn = _conn(year, month)
    if force is not None:
        try:
            force = int(force or 0)
        except (TypeError, ValueError):
            force = 0
        conn.execute("UPDATE dw_points SET force=? WHERE id=?", (force, int(point_id)))
    if name:
        name = " ".join(name.split())
        if name:
            conn.execute("UPDATE dw_points SET name=? WHERE id=?", (name, int(point_id)))
    if responsible is not None:
        conn.execute("UPDATE dw_points SET responsible=? WHERE id=?",
                     (responsible, int(point_id)))
    conn.commit()
    conn.close()


def delete_point(year, month, point_id):
    conn = _conn(year, month)
    conn.execute("DELETE FROM dw_points WHERE id=?", (int(point_id),))
    conn.commit()
    conn.close()


# ======================================================================
# معدلات الدولى (منفصلة عن معدلات ٢ مخازن العادية والحرة)
# ======================================================================
def list_rates(year, month):
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM dw_rates ORDER BY"
        " CASE section WHEN 'tamween' THEN 0 ELSE 1 END, id")]
    conn.close()
    return rows


def get_rate(year, month, section, name):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM dw_rates WHERE section=? AND name=?",
                       (section, name)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_rate(year, month, section, name, rate, unit="", production_year="",
              is_extra=False):
    if section not in ("tamween", "contractor"):
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
        "INSERT INTO dw_rates (section, name, unit, rate, production_year, is_extra)"
        " VALUES (?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(section, name) DO UPDATE SET rate=excluded.rate,"
        " unit = CASE WHEN excluded.unit != '' THEN excluded.unit ELSE dw_rates.unit END,"
        " production_year=excluded.production_year, is_extra=excluded.is_extra",
        (section, name, unit, rate, production_year or "", int(bool(is_extra))))
    conn.commit()
    conn.close()


def toggle_rate(year, month, rate_id):
    conn = _conn(year, month)
    conn.execute("UPDATE dw_rates SET enabled = 1 - enabled WHERE id=?", (int(rate_id),))
    conn.commit()
    conn.close()


def delete_rate(year, month, rate_id):
    conn = _conn(year, month)
    conn.execute("DELETE FROM dw_rates WHERE id=?", (int(rate_id),))
    conn.commit()
    conn.close()


# ======================================================================
# حفظ التفريدة على القرص (سجل + ملفات)
# ======================================================================
def save_tafreeda(year, month, data, folder):
    """data: لقطة كاملة JSON-ready. folder: أسماء الملفات المحفوظة."""
    conn = _conn(year, month)
    cur = conn.execute(
        "INSERT INTO dw_saves (label, date_from, date_to, issue_days, store_keeper,"
        " scribe, data, files, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data.get("label") or "", int(data.get("date_from") or 0),
         int(data.get("date_to") or 0), int(data.get("issue_days") or 0),
         data.get("store_keeper") or "", data.get("scribe") or "",
         json.dumps(data, ensure_ascii=False), json.dumps(folder, ensure_ascii=False),
         _stamp()))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def list_saves(year, month):
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT id, label, date_from, date_to, issue_days, store_keeper, scribe,"
        " files, created_at FROM dw_saves ORDER BY id DESC")]
    for r in rows:
        try:
            r["files"] = json.loads(r.get("files") or "[]")
        except (TypeError, ValueError):
            r["files"] = []
    conn.close()
    return rows


def get_save(year, month, save_id):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM dw_saves WHERE id=?", (int(save_id),)).fetchone()
    conn.close()
    if not row:
        return None
    out = dict(row)
    try:
        out["data"] = json.loads(out.get("data") or "{}")
        out["files"] = json.loads(out.get("files") or "[]")
    except (TypeError, ValueError):
        out["data"], out["files"] = {}, []
    return out


def delete_save(year, month, save_id):
    conn = _conn(year, month)
    conn.execute("DELETE FROM dw_saves WHERE id=?", (int(save_id),))
    conn.commit()
    conn.close()


def latest_save_in_range(year, month, date_from, date_to):
    """أحدث حفظ يغطي نفس الفترة (لزرار التصفير) — بحقولها المفكوكة."""
    conn = _conn(year, month)
    row = conn.execute(
        "SELECT * FROM dw_saves WHERE date_from<=? AND date_to>=? ORDER BY id DESC"
        " LIMIT 1", (int(date_to), int(date_from))).fetchone()
    conn.close()
    if not row:
        return None
    out = dict(row)
    try:
        out["files"] = json.loads(out.get("files") or "[]")
    except (TypeError, ValueError):
        out["files"] = []
    return out
