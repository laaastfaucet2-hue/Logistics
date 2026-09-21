# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""اليومية العامة للمجندين — تعيش داخل قاعدة الشهر month.db (عزل شهري مطلق مثل المقررات).

القاعدة الذهبية: يومية اليوم تُرحَّل لليوم التالي **مرة واحدة فقط** ومن يومٍ **مُثبَّت** —
فلا تنتقل ليومٍ ثالث أبدًا. واليوم المُثبَّت يُقفل ولا يُعدَّل إلا بتأكيد قوي.
"""
import months

STATUSES = ["حضور", "إجازة", "غياب", "مأمورية", "مستشفى", "أخرى"]

_MIGRATE_SQL = """
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day INTEGER NOT NULL,
    recruit_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    note TEXT DEFAULT '',
    UNIQUE(day, recruit_id)
);
CREATE TABLE IF NOT EXISTS journal_meta (
    day INTEGER PRIMARY KEY,
    locked INTEGER DEFAULT 0,
    done_at TEXT DEFAULT '',
    source_day INTEGER DEFAULT 0
);
"""


def ensure_tables(conn):
    conn.executescript(_MIGRATE_SQL)


# ==================== قراءة يوم ====================
def get_day_map(year, month, day):
    """{رقم المجند: {status, note}} ليوم محدد."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = conn.execute(
        "SELECT recruit_id, status, note FROM attendance WHERE day=?", (day,)).fetchall()
    conn.close()
    return {r["recruit_id"]: {"status": r["status"], "note": r["note"]} for r in rows}


def get_meta(year, month, day):
    conn = months.get_db(year, month)
    ensure_tables(conn)
    row = conn.execute(
        "SELECT * FROM journal_meta WHERE day=?", (day,)).fetchone()
    conn.close()
    return dict(row) if row else {"day": day, "locked": 0, "done_at": "", "source_day": 0}


# ==================== كتابة يوم كامل (تثبيت) ====================
def save_day(year, month, day, entries, lock=True, source_day=0):
    """entries = [(recruit_id, status, note)] — يستبدل محتوى اليوم ذرّيًا."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        conn.execute("DELETE FROM attendance WHERE day=?", (day,))
        conn.executemany(
            "INSERT INTO attendance (day, recruit_id, status, note) VALUES (?,?,?,?)",
            [(day, rid, st, note) for rid, st, note in entries if st in STATUSES])
        if lock:
            conn.execute(
                "INSERT INTO journal_meta (day, locked, done_at, source_day) VALUES (?,1,datetime('now'),?)"
                " ON CONFLICT(day) DO UPDATE SET locked=1, done_at=datetime('now'), source_day=?",
                (day, source_day, source_day))
    conn.close()


def unlock_day(year, month, day):
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        conn.execute("UPDATE journal_meta SET locked=0 WHERE day=?", (day,))
    conn.close()


# ==================== إسناد بمدى (من يوم إلى يوم) ====================
def set_range(year, month, recruit_id, status, from_day, to_day, note=""):
    if status not in STATUSES or from_day < 1 or to_day < from_day:
        return 0
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        for d in range(from_day, to_day + 1):
            conn.execute(
                "INSERT INTO attendance (day, recruit_id, status, note) VALUES (?,?,?,?)"
                " ON CONFLICT(day, recruit_id) DO UPDATE SET status=excluded.status, note=excluded.note",
                (d, recruit_id, status, note))
    conn.close()
    return to_day - from_day + 1


def delete_recruit_day(year, month, day, recruit_id):
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        conn.execute("DELETE FROM attendance WHERE day=? AND recruit_id=?", (day, recruit_id))
    conn.close()


# ==================== الترحيل لليوم التالي (مرة واحدة ومن يوم مُثبَّت) ====================
def carry_over_if_needed(year, month, day):
    """لو اليوم فارغ واليوم السابق مُثبَّت → انسخه كمسودة. يرجع (رُحِّلت?, من يوم)."""
    if day <= 1:
        return False, 0
    conn = months.get_db(year, month)
    ensure_tables(conn)
    has = conn.execute("SELECT 1 FROM attendance WHERE day=? LIMIT 1", (day,)).fetchone()
    if has:
        conn.close()
        return False, 0
    prev_meta = conn.execute(
        "SELECT locked FROM journal_meta WHERE day=?", (day - 1,)).fetchone()
    if not (prev_meta and prev_meta["locked"]):
        conn.close()
        return False, 0                   # ← لا ترحيل إلا من يوم مُثبَّت (لا تروح ليوم ٣)
    prev = conn.execute(
        "SELECT recruit_id, status, note FROM attendance WHERE day=?", (day - 1,)).fetchall()
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO attendance (day, recruit_id, status, note) VALUES (?,?,?,?)",
            [(day, r["recruit_id"], r["status"], r["note"]) for r in prev])
        conn.execute(
            "INSERT OR IGNORE INTO journal_meta (day, locked, done_at, source_day) VALUES (?,0,'',?)",
            (day, day - 1))
    conn.close()
    return True, day - 1


# ==================== قراءات الشهر (مصفوفة/كشوف) ====================
def month_matrix(year, month):
    """{recruit_id: {day: status}} لكل الشهر."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = conn.execute(
        "SELECT recruit_id, day, status FROM attendance ORDER BY day").fetchall()
    conn.close()
    out = {}
    for r in rows:
        out.setdefault(r["recruit_id"], {})[r["day"]] = r["status"]
    return out


def days_without_journal(year, month, upto_day):
    """أيام (حتى upto_day) بلا يومية مُثبَّتة."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    locked = {r["day"] for r in conn.execute(
        "SELECT day FROM journal_meta WHERE locked=1").fetchall()}
    filled = {r["day"] for r in conn.execute(
        "SELECT DISTINCT day FROM attendance").fetchall()}
    conn.close()
    return [d for d in range(1, upto_day + 1) if d not in locked and d not in filled]


def leave_ranges(year, month, matrix, from_day=1, to_day=31):
    """مدى إجازة كل مجند داخل الشهر: {recruit_id: [(from, to)]} (أيام متتالية تُدمج)."""
    out = {}
    for rid, days in matrix.items():
        seq = sorted(d for d, st in days.items()
                     if st == "إجازة" and from_day <= d <= to_day)
        if not seq:
            continue
        start = prev = seq[0]
        for d in seq[1:] + [to_day + 2]:
            if d != prev + 1:
                out.setdefault(rid, []).append((start, prev))
                start = d
            prev = d
    return out


def absence_streak(year, month, matrix, upto_day):
    """غياب متواصل ينتهي عند upto_day: {recruit_id: عدد الأيام المتتالية}."""
    out = {}
    for rid, days in matrix.items():
        streak = 0
        d = upto_day
        while d >= 1 and days.get(d) == "غياب":
            streak += 1
            d -= 1
        if streak:
            out[rid] = streak
    return out
