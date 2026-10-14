# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""بيانات تفاريد الدولى: نسخ الخطوط الزمنية، النقاط، المعدلات، والمحفوظات."""
import json

from core import arabic_numbers as arnum
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
CREATE TABLE IF NOT EXISTS dw_line_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date_from INTEGER,
    date_to INTEGER,
    status TEXT NOT NULL DEFAULT 'current',
    source_version_id INTEGER,
    created_at TEXT NOT NULL,
    archived_at TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS dw_line_current_name
ON dw_line_versions(name) WHERE status='current';
CREATE TABLE IF NOT EXISTS dw_version_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    force INTEGER NOT NULL DEFAULT 0,
    responsible TEXT NOT NULL DEFAULT '',
    UNIQUE (version_id, name)
);
CREATE TABLE IF NOT EXISTS dw_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    rate REAL NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    is_extra INTEGER NOT NULL DEFAULT 0,
    UNIQUE (section, name)
);
CREATE TABLE IF NOT EXISTS dw_rate_custom (
    rate_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    day_key INTEGER NOT NULL,
    meal TEXT NOT NULL,
    qty REAL NOT NULL DEFAULT 0,
    mode TEXT NOT NULL DEFAULT 'add',
    PRIMARY KEY (rate_id, kind, day_key, meal)
);
CREATE TABLE IF NOT EXISTS dw_rate_custom_state (
    rate_id INTEGER PRIMARY KEY,
    weekly_override INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS dw_saves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    date_from INTEGER NOT NULL,
    date_to INTEGER NOT NULL,
    issue_days INTEGER NOT NULL,
    store_keeper TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL,
    files TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
"""


def _stamp():
    return egtime.now().isoformat(timespec="seconds")


def _migrate_legacy(conn):
    """ينسخ الخطوط القديمة مرة واحدة كنسخ حالية بلا فترة، دون حذف أصلها."""
    if conn.execute("SELECT COUNT(*) FROM dw_line_versions").fetchone()[0]:
        return
    for row in conn.execute("SELECT * FROM dw_lines ORDER BY id").fetchall():
        conn.execute(
            "INSERT INTO dw_line_versions"
            " (id,name,date_from,date_to,status,created_at) VALUES(?,?,?,?,?,?)",
            (row["id"], row["name"], None, None, "current", row["created_at"]))
    for point in conn.execute("SELECT * FROM dw_points ORDER BY id").fetchall():
        if conn.execute("SELECT 1 FROM dw_line_versions WHERE id=?",
                        (point["line_id"],)).fetchone():
            conn.execute(
                "INSERT INTO dw_version_points"
                " (id,version_id,name,force,responsible) VALUES(?,?,?,?,?)",
                (point["id"], point["line_id"], point["name"], point["force"],
                 point["responsible"]))
    conn.commit()


def _conn(year, month):
    conn = months.get_db(year, month)
    conn.executescript(SCHEMA)
    _migrate_legacy(conn)
    return conn


def reset_month(year, month):
    """بدء من صفر: مسح جداول الدولى فقط في الشهر المطلوب."""
    conn = months.get_db(year, month)
    conn.executescript(
        "DROP TABLE IF EXISTS dw_version_points;"
        "DROP TABLE IF EXISTS dw_line_versions;"
        "DROP TABLE IF EXISTS dw_rate_custom_state;"
        "DROP TABLE IF EXISTS dw_rate_custom;"
        "DROP TABLE IF EXISTS dw_lines;"
        "DROP TABLE IF EXISTS dw_points;"
        "DROP TABLE IF EXISTS dw_rates;"
        "DROP TABLE IF EXISTS dw_saves;")
    conn.commit()
    conn.close()


# ======================================================================
# نسخ الخطوط والنقاط
# ======================================================================
def _line_dict(conn, row):
    line = dict(row)
    points = [dict(point) for point in conn.execute(
        "SELECT * FROM dw_version_points WHERE version_id=? ORDER BY id",
        (line["id"],))]
    for point in points:
        point["line_id"] = point["version_id"]
    line["points"] = points
    line["count"] = len(points)
    line["active"] = sum(1 for point in points if int(point.get("force") or 0) > 0)
    line["total_force"] = sum(int(point.get("force") or 0) for point in points)
    if line.get("date_from") is not None and line.get("date_to") is not None:
        line["period_days"] = int(line["date_to"]) - int(line["date_from"]) + 1
    else:
        line["period_days"] = 0
    return line


def list_versions(year, month, status=None, name=None):
    conn = _conn(year, month)
    where, values = [], []
    if status in ("current", "archived"):
        where.append("status=?")
        values.append(status)
    if name:
        where.append("name=?")
        values.append(" ".join(str(name).split()))
    clause = " WHERE " + " AND ".join(where) if where else ""
    order = (" ORDER BY name,id" if status == "current" else
             " ORDER BY name, COALESCE(date_from,0) DESC, id DESC")
    rows = [_line_dict(conn, row) for row in conn.execute(
        "SELECT * FROM dw_line_versions" + clause + order, values)]
    conn.close()
    return rows


def list_lines(year, month):
    """النسخة الحالية فقط لكل اسم خط."""
    return list_versions(year, month, status="current")


def list_archived_lines(year, month):
    return list_versions(year, month, status="archived")


def get_line(year, month, line_id):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM dw_line_versions WHERE id=?",
                       (int(line_id),)).fetchone()
    line = _line_dict(conn, row) if row else None
    conn.close()
    return line


def _period_error(conn, name, day_from, day_to, exclude_id=None):
    if day_from is None or day_to is None:
        return ""
    day_from, day_to = int(day_from), int(day_to)
    if day_to < day_from:
        return "تاريخ نهاية الخط يجب ألا يسبق تاريخ البداية"
    rows = conn.execute(
        "SELECT id,date_from,date_to FROM dw_line_versions"
        " WHERE name=? AND date_from IS NOT NULL AND date_to IS NOT NULL",
        (name,)).fetchall()
    for row in rows:
        if exclude_id is not None and int(row["id"]) == int(exclude_id):
            continue
        if day_from <= int(row["date_to"]) and day_to >= int(row["date_from"]):
            return (
                f"الفترة تتداخل مع نسخة الخط رقم {arnum.to_arabic_indic(row['id'])} "
                f"من يوم {arnum.to_arabic_indic(row['date_from'])} "
                f"إلى يوم {arnum.to_arabic_indic(row['date_to'])}")
    return ""


def _checked_period(year, month, day_from, day_to, allow_empty=False):
    if allow_empty and day_from is None and day_to is None:
        return None, None, ""
    if day_from in (None, "") or day_to in (None, ""):
        return None, None, "اكتب تاريخي بداية ونهاية النسخة"
    try:
        day_from, day_to = int(day_from), int(day_to)
    except (TypeError, ValueError):
        return None, None, "فترة نسخة الخط غير صحيحة"
    last = egtime.days_in_month(int(year), int(month))
    if not (1 <= day_from <= last and 1 <= day_to <= last):
        return None, None, ("فترة نسخة الخط يجب أن تكون داخل أيام الشهر من ١ إلى "
                            f"{arnum.to_arabic_indic(last)}")
    if day_to < day_from:
        return None, None, "تاريخ نهاية الخط يجب ألا يسبق تاريخ البداية"
    return day_from, day_to, ""


def create_line_version(year, month, name, day_from, day_to):
    """يؤرشف الحالية للاسم ثم ينشئ نسخة حالية فارغة بفترة غير متداخلة."""
    name = " ".join((name or "").split())
    if not name:
        return None, "اكتب اسم الخط"
    day_from, day_to, error = _checked_period(
        year, month, day_from, day_to, allow_empty=True)
    if error:
        return None, error
    conn = _conn(year, month)
    error = _period_error(conn, name, day_from, day_to)
    if error:
        conn.close()
        return None, error
    try:
        with conn:
            conn.execute(
                "UPDATE dw_line_versions SET status='archived',archived_at=?"
                " WHERE name=? AND status='current'", (_stamp(), name))
            cur = conn.execute(
                "INSERT INTO dw_line_versions"
                " (name,date_from,date_to,status,created_at) VALUES(?,?,?,?,?)",
                (name, day_from, day_to, "current", _stamp()))
            new_id = cur.lastrowid
    except Exception:
        conn.close()
        return None, "تعذر إنشاء نسخة الخط"
    conn.close()
    return new_id, ""


def add_line(year, month, name, day_from=None, day_to=None):
    """توافقية للمستدعين القدامى؛ النسخة الجديدة فارغة."""
    line_id, _error = create_line_version(year, month, name, day_from, day_to)
    return line_id


def update_line_period(year, month, line_id, day_from, day_to):
    day_from, day_to, error = _checked_period(year, month, day_from, day_to)
    if error:
        return error
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM dw_line_versions WHERE id=?",
                       (int(line_id),)).fetchone()
    if not row:
        conn.close()
        return "نسخة الخط غير موجودة"
    error = _period_error(conn, row["name"], day_from, day_to, exclude_id=line_id)
    if error:
        conn.close()
        return error
    conn.execute("UPDATE dw_line_versions SET date_from=?,date_to=? WHERE id=?",
                 (int(day_from), int(day_to), int(line_id)))
    conn.commit()
    conn.close()
    return ""


def restore_line(year, month, line_id):
    """ينسخ المؤرشفة إلى حالية بلا فترة، ويؤرشف الحالية القائمة."""
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM dw_line_versions WHERE id=? AND status='archived'",
                       (int(line_id),)).fetchone()
    if not row:
        conn.close()
        return None, "النسخة المؤرشفة غير موجودة"
    try:
        with conn:
            conn.execute(
                "UPDATE dw_line_versions SET status='archived',archived_at=?"
                " WHERE name=? AND status='current'", (_stamp(), row["name"]))
            cur = conn.execute(
                "INSERT INTO dw_line_versions"
                " (name,date_from,date_to,status,source_version_id,created_at)"
                " VALUES(?,?,?,'current',?,?)",
                (row["name"], None, None, row["id"], _stamp()))
            new_id = cur.lastrowid
            points = conn.execute(
                "SELECT name,force,responsible FROM dw_version_points"
                " WHERE version_id=? ORDER BY id", (int(line_id),)).fetchall()
            conn.executemany(
                "INSERT INTO dw_version_points(version_id,name,force,responsible)"
                " VALUES(?,?,?,?)",
                [(new_id, p["name"], p["force"], p["responsible"]) for p in points])
    except Exception:
        conn.close()
        return None, "تعذر استرجاع نسخة الخط"
    conn.close()
    return new_id, ""


def archive_line(year, month, line_id):
    """ينقل النسخة الحالية إلى الأرشيف مع إبقاء نقاطها وقوتها."""
    conn = _conn(year, month)
    cursor = conn.execute(
        "UPDATE dw_line_versions SET status='archived',archived_at=?"
        " WHERE id=? AND status='current'", (_stamp(), int(line_id)))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def delete_line(year, month, line_id):
    """حذف نهائي لنسخة واحدة (يستعمل من الأرشيف بعد تأكيد صريح)."""
    conn = _conn(year, month)
    with conn:
        conn.execute("DELETE FROM dw_version_points WHERE version_id=?", (int(line_id),))
        conn.execute("DELETE FROM dw_line_versions WHERE id=?", (int(line_id),))
    conn.close()


def find_point(year, month, point_id):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM dw_version_points WHERE id=?",
                       (int(point_id),)).fetchone()
    conn.close()
    if not row:
        return None, None
    point = dict(row)
    point["line_id"] = point["version_id"]
    return get_line(year, month, point["version_id"]), point


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
            "INSERT INTO dw_version_points(version_id,name,force) VALUES(?,?,?)",
            (int(line_id), name, force))
        conn.commit()
        new_id = cur.lastrowid
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
        conn.execute("UPDATE dw_version_points SET force=? WHERE id=?",
                     (force, int(point_id)))
    if name:
        clean = " ".join(name.split())
        if clean:
            conn.execute("UPDATE dw_version_points SET name=? WHERE id=?",
                         (clean, int(point_id)))
    if responsible is not None:
        conn.execute("UPDATE dw_version_points SET responsible=? WHERE id=?",
                     (responsible, int(point_id)))
    conn.commit()
    conn.close()


def delete_point(year, month, point_id):
    conn = _conn(year, month)
    conn.execute("DELETE FROM dw_version_points WHERE id=?", (int(point_id),))
    conn.commit()
    conn.close()


# ======================================================================
# معدلات الدولى وتخصيصاتها
# ======================================================================
def list_rates(year, month):
    conn = _conn(year, month)
    rows = [dict(row) for row in conn.execute(
        "SELECT * FROM dw_rates ORDER BY"
        " CASE section WHEN 'tamween' THEN 0 ELSE 1 END,id")]
    conn.close()
    return rows


def get_rate(year, month, rate_id):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM dw_rates WHERE id=?", (int(rate_id),)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_rate(year, month, section, name, rate, unit="", is_extra=False, enabled=None):
    if section not in ("tamween", "contractor"):
        return None
    name = " ".join((name or "").split())
    if not name:
        return None
    try:
        rate = round(float(rate), 6)
    except (TypeError, ValueError):
        return None
    insert_enabled = 1 if enabled is None else int(bool(enabled))
    conn = _conn(year, month)
    conn.execute(
        "INSERT INTO dw_rates(section,name,unit,rate,enabled,is_extra)"
        " VALUES(?,?,?,?,?,?) ON CONFLICT(section,name) DO UPDATE SET"
        " rate=excluded.rate,unit=CASE WHEN excluded.unit!='' THEN excluded.unit"
        " ELSE dw_rates.unit END,is_extra=excluded.is_extra",
        (section, name, unit, rate, insert_enabled, int(bool(is_extra))))
    conn.commit()
    row = conn.execute("SELECT id FROM dw_rates WHERE section=? AND name=?",
                       (section, name)).fetchone()
    conn.close()
    return int(row["id"]) if row else None


def set_rate_extra(year, month, section, name, is_extra):
    """واجهة توافقية لتغيير وسم الصنف اليدوي."""
    conn = _conn(year, month)
    conn.execute("UPDATE dw_rates SET is_extra=? WHERE section=? AND name=?",
                 (int(bool(is_extra)), section, " ".join((name or "").split())))
    conn.commit()
    conn.close()


def toggle_rate(year, month, rate_id):
    conn = _conn(year, month)
    conn.execute("UPDATE dw_rates SET enabled=1-enabled WHERE id=?", (int(rate_id),))
    conn.commit()
    conn.close()


def delete_rate(year, month, rate_id):
    conn = _conn(year, month)
    with conn:
        conn.execute("DELETE FROM dw_rate_custom_state WHERE rate_id=?", (int(rate_id),))
        conn.execute("DELETE FROM dw_rate_custom WHERE rate_id=?", (int(rate_id),))
        conn.execute("DELETE FROM dw_rates WHERE id=?", (int(rate_id),))
    conn.close()


def get_rate_custom(year, month, rate_id):
    conn = _conn(year, month)
    rows = [dict(row) for row in conn.execute(
        "SELECT kind,day_key,meal,qty,mode FROM dw_rate_custom"
        " WHERE rate_id=? ORDER BY kind,day_key,meal", (int(rate_id),))]
    state = conn.execute(
        "SELECT weekly_override FROM dw_rate_custom_state WHERE rate_id=?",
        (int(rate_id),)).fetchone()
    conn.close()
    weekly, actual = [], []
    for row in rows:
        if row["kind"] == "weekly":
            weekly.append({"weekday": int(row["day_key"]), "meal": row["meal"],
                           "qty": float(row["qty"] or 0)})
        elif row["kind"] == "date":
            actual.append({"day": int(row["day_key"]), "meal": row["meal"],
                           "qty": float(row["qty"] or 0), "mode": row["mode"]})
    return {"weekly": weekly, "dates": actual,
            "weekly_overridden": bool(state and state["weekly_override"])}


def save_rate_custom(year, month, rate_id, weekly, actual):
    """يحفظ دفعة واحدة؛ عند تكرار اليوم/الوجبة تكون آخر خانة هي المعتمدة."""
    weekly_map = {(int(day), meal): float(qty) for day, meal, qty in weekly}
    actual_map = {(int(day), meal): (float(qty), mode)
                  for day, meal, qty, mode in actual}
    conn = _conn(year, month)
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO dw_rate_custom_state(rate_id,weekly_override)"
            " VALUES(?,1)", (int(rate_id),))
        conn.execute("DELETE FROM dw_rate_custom WHERE rate_id=?", (int(rate_id),))
        conn.executemany(
            "INSERT INTO dw_rate_custom(rate_id,kind,day_key,meal,qty,mode)"
            " VALUES(?,'weekly',?,?,?,'add')",
            [(int(rate_id), day, meal, qty)
             for (day, meal), qty in weekly_map.items()])
        conn.executemany(
            "INSERT INTO dw_rate_custom(rate_id,kind,day_key,meal,qty,mode)"
            " VALUES(?,'date',?,?,?,?)",
            [(int(rate_id), day, meal, qty, mode)
             for (day, meal), (qty, mode) in actual_map.items()])
    conn.close()


# ======================================================================
# حفظ التفريدة على القرص
# ======================================================================
def save_tafreeda(year, month, data, folder):
    conn = _conn(year, month)
    date_from = int(data.get("date_from") or 0)
    date_to = int(data.get("date_to") or date_from)
    issue_days = max(1, date_to - date_from + 1)
    cur = conn.execute(
        "INSERT INTO dw_saves(label,date_from,date_to,issue_days,store_keeper,"
        " data,files,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (data.get("label") or "", date_from, date_to, issue_days, "",
         json.dumps(data, ensure_ascii=False), json.dumps(folder, ensure_ascii=False),
         _stamp()))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def list_saves(year, month):
    conn = _conn(year, month)
    rows = [dict(row) for row in conn.execute(
        "SELECT id,label,date_from,date_to,issue_days,store_keeper,data,files,created_at"
        " FROM dw_saves ORDER BY id DESC")]
    for row in rows:
        row["issue_days"] = max(1, int(row["date_to"]) - int(row["date_from"]) + 1)
        try:
            row["files"] = json.loads(row.get("files") or "[]")
        except (TypeError, ValueError):
            row["files"] = []
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
    out["issue_days"] = max(1, int(out["date_to"]) - int(out["date_from"]) + 1)
    return out


def delete_save(year, month, save_id):
    conn = _conn(year, month)
    conn.execute("DELETE FROM dw_saves WHERE id=?", (int(save_id),))
    conn.commit()
    conn.close()


def count_saves_from(year, month, date_from):
    conn = _conn(year, month)
    count = conn.execute("SELECT COUNT(*) FROM dw_saves WHERE date_from=?",
                         (int(date_from),)).fetchone()[0]
    conn.close()
    return count
