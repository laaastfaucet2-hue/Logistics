# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""التفاريد الحرة وتفاريد الدول — طبقة بيانات **معزولة تمامًا** (توجيه ٠٦/١٠/٢٠٢٦).

قاعدة المستخدم الملزمة:
  «صفحات عمل تفاريد حرة · تفاريد الدول · معدلات الأصناف حرة تمامًا غير متصلة بالمخازن،
   لها ملفات مستقلة، وتعديلاتها لا تمس مقررات المتعهد/التموينية.»

لذلك هذه الجداول (`ft_*`) لا علاقة لها بجداول المخازن (`wh_*`) ولا بالمقررات (`ration_*`):
* `ft_lines`   خطوط التوزيع (مثل: خط معين · خط النقب).
* `ft_points`  نقاط التوزيع المرتبطة بخط، لكل نقطة قوتها وحالتها.
* `ft_rates`   معدلات الأصناف اليومية للفرد + الوحدة + التفعيل (لقطة من المقررات ثم حرة).
* `ft_rate_days` أيام الصرف المفعّلة (١..١٠) لكل صنف.
* `ft_sheets`  الكشوف المحفوظة (تفريدة حرة أو تفريدة دول) بنصّها الكامل JSON.

لا قراءة ولا كتابة لأي جدول خارج `ft_*` — ويحرسه `tests/test_free_tafreed.py`.
"""
import json

from core import egtime
from data_access import months

MAX_DAYS = 10                     # أيام الصرف في معدلات تفاريد الدول (كما في السكرين شوت)


def _conn(year, month):
    conn = months.get_db(year, month)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ft_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ft_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            force INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ft_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            unit TEXT DEFAULT '',
            rate REAL NOT NULL DEFAULT 0,
            kind TEXT DEFAULT 'tamween',
            active INTEGER NOT NULL DEFAULT 1,
            sort INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ft_rate_days (
            rate_id INTEGER NOT NULL,
            day INTEGER NOT NULL,
            PRIMARY KEY (rate_id, day)
        );
        CREATE TABLE IF NOT EXISTS ft_sheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL DEFAULT 'free',
            title TEXT NOT NULL,
            date_from INTEGER NOT NULL DEFAULT 1,
            date_to INTEGER NOT NULL DEFAULT 1,
            days INTEGER NOT NULL DEFAULT 1,
            force INTEGER NOT NULL DEFAULT 0,
            holder TEXT DEFAULT '',
            writer TEXT DEFAULT '',
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
    """)
    _migrate(conn)
    return conn


def _migrate(conn):
    """ترقية تدريجية لقواعد الشهور المنشأة قبل إضافة سجل الصرف (نمط `months._migrate`)."""
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ft_sheets)")}
        if cols and "printed_at" not in cols:
            conn.execute("ALTER TABLE ft_sheets ADD COLUMN printed_at TEXT DEFAULT ''")
        if cols and "printed_count" not in cols:
            conn.execute("ALTER TABLE ft_sheets ADD COLUMN printed_count INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except Exception:  # noqa: BLE001 — الترقية لا تُسقط أي صفحة
        pass


def _now():
    return egtime.now().isoformat(timespec="seconds")


# ==================== الخطوط ====================
def list_lines(year, month):
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute("SELECT * FROM ft_lines ORDER BY id")]
    for row in rows:
        row["points"] = conn.execute(
            "SELECT COUNT(*) c, COALESCE(SUM(force),0) f,"
            " COALESCE(SUM(CASE WHEN active=1 THEN 1 ELSE 0 END),0) a"
            " FROM ft_points WHERE line_id=?", (row["id"],)).fetchone()
        row["points"] = {"count": row["points"]["c"], "force": row["points"]["f"],
                         "active": row["points"]["a"]}
    conn.close()
    return rows


def get_line(year, month, line_id):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM ft_lines WHERE id=?", (line_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_line(year, month, name, notes="", default_points=0):
    """إضافة خط توزيع — مع نقاط جاهزة فارغة عند الطلب (شبكة سريعة للتسجيل)."""
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("اكتب اسم خط التوزيع")
    conn = _conn(year, month)
    try:
        with conn:
            cur = conn.execute("INSERT INTO ft_lines (name, notes, created_at) VALUES (?,?,?)",
                               (name, (notes or "").strip(), _now()))
            line_id = cur.lastrowid
            for index in range(int(default_points or 0)):
                conn.execute("INSERT INTO ft_points (line_id, name, force, active, created_at)"
                             " VALUES (?,?,?,?,?)",
                             (line_id, f"نقطة {index + 1}", 0, 1, _now()))
    except Exception as exc:
        conn.close()
        raise ValueError(f"خط التوزيع «{name}» مسجّل بالفعل") from exc
    conn.close()
    return line_id


def update_line(year, month, line_id, name=None, notes=None):
    conn = _conn(year, month)
    with conn:
        if name:
            conn.execute("UPDATE ft_lines SET name=? WHERE id=?",
                         (" ".join(name.split()), line_id))
        if notes is not None:
            conn.execute("UPDATE ft_lines SET notes=? WHERE id=?", (notes.strip(), line_id))
    conn.close()


def delete_line(year, month, line_id):
    conn = _conn(year, month)
    with conn:
        conn.execute("DELETE FROM ft_points WHERE line_id=?", (line_id,))
        conn.execute("DELETE FROM ft_lines WHERE id=?", (line_id,))
    conn.close()


# ==================== النقاط ====================
def list_points(year, month, line_id=None):
    conn = _conn(year, month)
    if line_id:
        rows = conn.execute("SELECT * FROM ft_points WHERE line_id=? ORDER BY id",
                            (line_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM ft_points ORDER BY line_id, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_point(year, month, line_id, name, force=0, active=True, notes=""):
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("اكتب اسم النقطة")
    conn = _conn(year, month)
    with conn:
        cur = conn.execute(
            "INSERT INTO ft_points (line_id, name, force, active, notes, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (line_id, name, int(force or 0), 1 if active else 0, (notes or "").strip(), _now()))
        point_id = cur.lastrowid
    conn.close()
    return point_id


def set_point_force(year, month, point_id, force):
    conn = _conn(year, month)
    with conn:
        conn.execute("UPDATE ft_points SET force=? WHERE id=?", (int(force or 0), point_id))
    conn.close()


def set_point_active(year, month, point_id, active):
    conn = _conn(year, month)
    with conn:
        conn.execute("UPDATE ft_points SET active=? WHERE id=?",
                     (1 if active else 0, point_id))
    conn.close()


def delete_point(year, month, point_id):
    conn = _conn(year, month)
    with conn:
        conn.execute("DELETE FROM ft_points WHERE id=?", (point_id,))
    conn.close()


def reset_forces(year, month, line_id=None):
    """«تصفير وإعادة تعيين القوات» — تصفير قوة كل النقاط (اختياريًا لخط واحد)."""
    conn = _conn(year, month)
    with conn:
        if line_id:
            conn.execute("UPDATE ft_points SET force=0 WHERE line_id=?", (line_id,))
        else:
            conn.execute("UPDATE ft_points SET force=0")
    conn.close()


def find_points(year, month, query):
    """بحث سريع عن نقطة بالاسم (لشاشة تفريدات الدول)."""
    like = f"%{(' '.join((query or '').split()))}%"
    conn = _conn(year, month)
    rows = conn.execute(
        "SELECT p.*, l.name line_name FROM ft_points p JOIN ft_lines l ON l.id=p.line_id"
        " WHERE p.name LIKE ? ORDER BY l.name, p.name", (like,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== معدلات الأصناف ====================
def list_rates(year, month, kind=None):
    conn = _conn(year, month)
    if kind:
        rows = conn.execute("SELECT * FROM ft_rates WHERE kind=? ORDER BY sort, id",
                            (kind,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM ft_rates ORDER BY sort, id").fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["days"] = [r["day"] for r in conn.execute(
            "SELECT day FROM ft_rate_days WHERE rate_id=? ORDER BY day", (item["id"],))]
        item["active"] = bool(item["active"])
        out.append(item)
    conn.close()
    return out


def upsert_rate(year, month, name, unit="", rate=0.0, kind="tamween",
                active=True, days=None, sort=0):
    """إضافة/تعديل معدّل صنف — الأيام الافتراضية كل أيام الصرف (١..١٠)."""
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("اكتب اسم الصنف")
    days = list(range(1, MAX_DAYS + 1)) if days is None else [int(d) for d in days]
    conn = _conn(year, month)
    with conn:
        row = conn.execute("SELECT id FROM ft_rates WHERE name=?", (name,)).fetchone()
        if row:
            rate_id = row["id"]
            conn.execute("UPDATE ft_rates SET unit=?, rate=?, kind=?, active=?, sort=?"
                         " WHERE id=?",
                         ((unit or "").strip(), float(rate or 0), kind or "tamween",
                          1 if active else 0, int(sort or 0), rate_id))
        else:
            cur = conn.execute(
                "INSERT INTO ft_rates (name, unit, rate, kind, active, sort, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (name, (unit or "").strip(), float(rate or 0), kind or "tamween",
                 1 if active else 0, int(sort or 0), _now()))
            rate_id = cur.lastrowid
        conn.execute("DELETE FROM ft_rate_days WHERE rate_id=?", (rate_id,))
        for day in days:
            if 1 <= int(day) <= MAX_DAYS:
                conn.execute("INSERT OR IGNORE INTO ft_rate_days (rate_id, day) VALUES (?,?)",
                             (rate_id, int(day)))
    conn.close()
    return rate_id


def toggle_rate_day(year, month, rate_id, day, on):
    conn = _conn(year, month)
    with conn:
        if on:
            conn.execute("INSERT OR IGNORE INTO ft_rate_days (rate_id, day) VALUES (?,?)",
                         (rate_id, int(day)))
        else:
            conn.execute("DELETE FROM ft_rate_days WHERE rate_id=? AND day=?",
                         (rate_id, int(day)))
    conn.close()


def set_rate_active(year, month, rate_id, active):
    conn = _conn(year, month)
    with conn:
        conn.execute("UPDATE ft_rates SET active=? WHERE id=?",
                     (1 if active else 0, rate_id))
    conn.close()


def delete_rate(year, month, rate_id):
    conn = _conn(year, month)
    with conn:
        conn.execute("DELETE FROM ft_rate_days WHERE rate_id=?", (rate_id,))
        conn.execute("DELETE FROM ft_rates WHERE id=?", (rate_id,))
    conn.close()


def seed_rates_from_rations(year, month, overwrite=False):
    """«اسحب الأصناف من مقررات التموين والمتعهد» — **لقطة** تُنسخ ثم تُعدَّل بحرية.

    القراءة من المقررات قراءةً فقط، وبعد النسخ لا توجد أي رابطة: تعديل معدل هنا
    لا يمس المقرر، وتعديل المقرر لا يمس المعدل (عزل تام — توجيه ٠٦/١٠).
    """
    from data_access import db_rations as dr
    added = 0
    existing = {r["name"] for r in list_rates(year, month)}
    for section, kind in (("tamween", "tamween"), ("contractor", "contractor")):
        active_kind = dr.get_activation(year, month, section)     # المقرر المفعّل فقط
        if not active_kind:
            continue
        items, _custom = dr.get_items(year, month, section, active_kind)
        for item in items:
            name = item.get("name")
            if not name or (name in existing and not overwrite):
                continue
            rate = sum(float(item.get(key) or 0)
                       for key in ("breakfast", "lunch", "dinner"))
            upsert_rate(year, month, name, item.get("unit") or "", rate, kind,
                        active=True, sort=int(item.get("serial") or 0))
            added += 1
    return added


# ==================== الكشوف المحفوظة ====================
def save_sheet(year, month, kind, title, payload, date_from=1, date_to=1, days=1,
               force=0, holder="", writer="", sheet_id=None):
    """يحفظ تفريدة (حرة/دول) — التحديث بنفس المعرّف استبدال لا تكرار."""
    title = " ".join((title or "").split()) or "تفريدة"
    body = json.dumps(payload or {}, ensure_ascii=False)
    conn = _conn(year, month)
    with conn:
        if sheet_id:
            conn.execute("UPDATE ft_sheets SET kind=?, title=?, date_from=?, date_to=?,"
                         " days=?, force=?, holder=?, writer=?, payload=? WHERE id=?",
                         (kind, title, int(date_from), int(date_to), int(days), int(force),
                          holder or "", writer or "", body, sheet_id))
            new_id = sheet_id
        else:
            cur = conn.execute(
                "INSERT INTO ft_sheets (kind, title, date_from, date_to, days, force,"
                " holder, writer, payload, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (kind, title, int(date_from), int(date_to), int(days), int(force),
                 holder or "", writer or "", body, _now()))
            new_id = cur.lastrowid
    conn.close()
    return new_id


def _sheet_row(row):
    item = dict(row)
    try:
        item["payload"] = json.loads(item.get("payload") or "{}")
    except (TypeError, ValueError):
        item["payload"] = {}
    return item


def list_sheets(year, month, kind=None, query="", pending=None):
    """كشوف القسم. `pending=True` = بانتظار الصرف · `pending=False` = المنجزة والمصروفة."""
    conn = _conn(year, month)
    sql = "SELECT * FROM ft_sheets"
    params = []
    where = []
    if kind:
        where.append("kind=?")
        params.append(kind)
    if pending is True:
        where.append("COALESCE(printed_count, 0) = 0")
    elif pending is False:
        where.append("COALESCE(printed_count, 0) > 0")
    if query:
        where.append("(title LIKE ? OR holder LIKE ? OR writer LIKE ?)")
        like = f"%{query.strip()}%"
        params.extend([like, like, like])
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    rows = [_sheet_row(r) for r in conn.execute(sql, params)]
    conn.close()
    return rows


def mark_printed(year, month, sheet_id):
    """تسجيل صرف/طباعة إذن التفريدة — ينقلها من «بانتظار الصرف» إلى سجل المنجزة."""
    conn = _conn(year, month)
    with conn:
        conn.execute("UPDATE ft_sheets SET printed_at=?,"
                     " printed_count=COALESCE(printed_count,0)+1 WHERE id=?",
                     (_now(), int(sheet_id)))
    conn.close()
    return sheet_id


def get_sheet(year, month, sheet_id):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM ft_sheets WHERE id=?", (sheet_id,)).fetchone()
    conn.close()
    return _sheet_row(row) if row else None


def delete_sheet(year, month, sheet_id):
    conn = _conn(year, month)
    with conn:
        conn.execute("DELETE FROM ft_sheets WHERE id=?", (sheet_id,))
    conn.close()
