# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""اليومية العامة للمجندين — تعيش داخل قاعدة الشهر month.db (عزل شهري مطلق مثل المقررات).

القاعدة الذهبية: يومية اليوم تُرحَّل لليوم التالي **مرة واحدة فقط** ومن يومٍ **مُثبَّت** —
فلا تنتقل ليومٍ ثالث أبدًا. واليوم المُثبَّت يُقفل ولا يُعدَّل إلا بتأكيد قوي.
"""
from data_access import months

STATUSES = ["حضور", "إجازة", "غياب", "مأمورية", "مستشفى", "أخرى", "سجن", "محكمة", "جزاء"]

_MIGRATE_SQL = """
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day INTEGER NOT NULL,
    recruit_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    note TEXT DEFAULT '',
    condition TEXT DEFAULT '',
    UNIQUE(day, recruit_id)
);
CREATE TABLE IF NOT EXISTS journal_meta (
    day INTEGER PRIMARY KEY,
    locked INTEGER DEFAULT 0,
    done_at TEXT DEFAULT '',
    source_day INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS leave_permits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recruit_id INTEGER NOT NULL,
    from_day INTEGER NOT NULL,
    to_day INTEGER NOT NULL,
    issued_at TEXT DEFAULT '',
    UNIQUE(recruit_id, from_day, to_day)
);
CREATE TABLE IF NOT EXISTS leave_cuts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recruit_id INTEGER NOT NULL,
    period_from INTEGER NOT NULL,
    period_to INTEGER NOT NULL,
    eff_day INTEGER NOT NULL,
    mode TEXT NOT NULL,
    hospital INTEGER DEFAULT 0,
    applied INTEGER DEFAULT 0,
    created_at TEXT DEFAULT ''
);
"""


def ensure_tables(conn):
    conn.executescript(_MIGRATE_SQL)
    # ترحيلة آمنة لمرة واحدة: عمود «الحالة الصحية» لأيام المستشفى
    cols = {r[1] for r in conn.execute("PRAGMA table_info(attendance)").fetchall()}
    if "condition" not in cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN condition TEXT DEFAULT ''")
        conn.commit()


# ==================== قراءة يوم ====================
def get_day_map(year, month, day):
    """{رقم المجند: {status, note, condition}} ليوم محدد."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = conn.execute(
        "SELECT recruit_id, status, note, condition FROM attendance WHERE day=?", (day,)).fetchall()
    conn.close()
    return {r["recruit_id"]: {"status": r["status"], "note": r["note"],
                              "condition": r["condition"] or ""} for r in rows}


def get_meta(year, month, day):
    conn = months.get_db(year, month)
    ensure_tables(conn)
    row = conn.execute(
        "SELECT * FROM journal_meta WHERE day=?", (day,)).fetchone()
    conn.close()
    return dict(row) if row else {"day": day, "locked": 0, "done_at": "", "source_day": 0}


# ==================== كتابة يوم كامل (تثبيت) ====================
def save_day(year, month, day, entries, lock=True, source_day=0):
    """entries = [(recruit_id, status, note)] — يستبدل محتوى اليوم ذرّيًا
    (الحالة الصحية لأيام المستشفى محفوظة — ما تُمسحش عند إعادة التثبيت)."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    old_cond = {r[0]: (r[1] or "") for r in conn.execute(
        "SELECT recruit_id, condition FROM attendance WHERE day=?", (day,)).fetchall()}
    with conn:
        conn.execute("DELETE FROM attendance WHERE day=?", (day,))
        conn.executemany(
            "INSERT INTO attendance (day, recruit_id, status, note, condition) VALUES (?,?,?,?,?)",
            [(day, rid, st, note, old_cond.get(rid, "") if st == "مستشفى" else "")
             for rid, st, note in entries if st in STATUSES])
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
                "INSERT INTO attendance (day, recruit_id, status, note, condition) VALUES (?,?,?,?,?)"
                " ON CONFLICT(day, recruit_id) DO UPDATE SET status=excluded.status,"
                " note=excluded.note, condition=''",
                (d, recruit_id, status, note, ""))
    conn.close()
    return to_day - from_day + 1


def delete_recruit_day(year, month, day, recruit_id):
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        conn.execute("DELETE FROM attendance WHERE day=? AND recruit_id=?", (day, recruit_id))
    conn.close()


# ==================== تصاريح الإجازات (صدرت فعلًا — جولة ٣٥) ====================
def record_leave_permits(year, month, rids, from_day, to_day):
    """تسجيل أن التصريح صدر لـ rids عن المدة (from..to) — يُسجَّل لحظة عمل التصريح
    (فردي أو مجمّع) وبيشغّل تذكير اليومية «أكّد ويتحطوا في اليومية»."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        for rid in rids:
            conn.execute(
                "INSERT INTO leave_permits (recruit_id, from_day, to_day, issued_at) "
                "VALUES (?, ?, ?, datetime('now')) "
                "ON CONFLICT(recruit_id, from_day, to_day) DO UPDATE SET issued_at=excluded.issued_at",
                (int(rid), int(from_day), int(to_day)))
    conn.close()


def month_leave_permits(year, month):
    """كل تصاريح الشهر: {recruit_id: [(from_day, to_day), ...]}."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = conn.execute("SELECT recruit_id, from_day, to_day FROM leave_permits").fetchall()
    conn.close()
    out = {}
    for r in rows:
        out.setdefault(r["recruit_id"], []).append((r["from_day"], r["to_day"]))
    return out


def has_leave_permit(year, month, recruit_id, from_day, to_day):
    """هل صدر تصريح لهذا المجند عن هذه المدة بالظبط؟"""
    return (from_day, to_day) in month_leave_permits(year, month).get(recruit_id, [])


def delete_leave_permit(year, month, recruit_id, from_day, to_day):
    """حذف سجل تصريح (بعد إلغاء إجازة)."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        conn.execute("DELETE FROM leave_permits WHERE recruit_id=? AND from_day=? AND to_day=?",
                     (recruit_id, from_day, to_day))
    conn.close()


# ==================== قطع الإجازات (قرار ١٢/١٠) ====================
def record_leave_cut(year, month, recruit_id, period_from, period_to, eff_day, mode):
    """تسجيل قطع إجازة: mode='now' (يسري النهارده) / 'tomorrow' (يسري بكرة)."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        cur = conn.execute(
            "INSERT INTO leave_cuts (recruit_id, period_from, period_to, eff_day, mode, applied,"
            " created_at) VALUES (?,?,?,?,?,?,datetime('now'))",
            (recruit_id, period_from, period_to, eff_day, mode,
             1 if mode == "now" else 0))
    conn.close()
    return cur.lastrowid


def month_leave_cuts(year, month):
    """كل قطوع الشهر: {recruit_id: [dict, ...]}."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = conn.execute("SELECT * FROM leave_cuts ORDER BY id").fetchall()
    conn.close()
    out = {}
    for r in rows:
        out.setdefault(r["recruit_id"], []).append(dict(r))
    return out


def get_leave_cut(year, month, cut_id):
    conn = months.get_db(year, month)
    ensure_tables(conn)
    row = conn.execute("SELECT * FROM leave_cuts WHERE id=?", (cut_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_cut_applied(year, month, cut_id, hospital=0):
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        conn.execute("UPDATE leave_cuts SET applied=1, hospital=? WHERE id=?", (hospital, cut_id))
    conn.close()


def set_hospital_day(year, month, day, recruit_id, condition="", note=None):
    """حفظ الحالة الصحية (+ الملاحظة اختياريًا) ليوم مستشفى."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        if note is None:
            conn.execute("UPDATE attendance SET condition=? WHERE day=? AND recruit_id=?",
                         (condition, day, recruit_id))
        else:
            conn.execute("UPDATE attendance SET condition=?, note=? WHERE day=? AND recruit_id=?",
                         (condition, note, day, recruit_id))
    conn.close()


def hospital_rows(year, month):
    """أيام المستشفى في الشهر: {recruit_id: [(day, condition, note), ...]} مرتبة."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = conn.execute(
        "SELECT recruit_id, day, condition, note FROM attendance WHERE status='مستشفى'"
        " ORDER BY day").fetchall()
    conn.close()
    out = {}
    for r in rows:
        out.setdefault(r["recruit_id"], []).append(
            (r["day"], r["condition"] or "", r["note"] or ""))
    return out


def delete_status_range(year, month, recruit_id, from_day, to_day, status):
    """حذف أيام من مدى — بس اللي حالتها `status` بالظبط (حماية لما تبقى)."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    n = 0
    with conn:
        for d in range(from_day, to_day + 1):
            cur = conn.execute("DELETE FROM attendance WHERE day=? AND recruit_id=? AND status=?",
                               (d, recruit_id, status))
            n += cur.rowcount
    conn.close()
    return n


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


def latest_statuses(year, month, matrix, upto_day):
    """آخر حالة مسجلة لكل مجند حتى يوم upto_day: {recruit_id: (status, day)}."""
    out = {}
    for rid, days in matrix.items():
        d = min(upto_day, max(days))
        while d >= 1 and d not in days:
            d -= 1
        if d >= 1:
            out[rid] = (days[d], d)
    return out


def attendance_runs(year, month, matrix, day):
    """لكل مجند حالته «حضور» في يوم day: (بداية الفترة المتواصلة, المدة)."""
    out = {}
    for rid, days in matrix.items():
        if days.get(day) != "حضور":
            continue
        start = day
        while days.get(start - 1) == "حضور":
            start -= 1
        out[rid] = (start, day - start + 1)
    return out


def absence_episodes(year, month, matrix, from_day=1, to_day=31):
    """فترات غياب متصلة لكل مجند: {recruit_id: [(from, to)]}."""
    out = {}
    for rid, days in matrix.items():
        seq = sorted(d for d, st in days.items()
                     if st == "غياب" and from_day <= d <= to_day)
        if not seq:
            continue
        start = prev = seq[0]
        for d in seq[1:] + [to_day + 2]:
            if d != prev + 1:
                out.setdefault(rid, []).append((start, prev))
                start = d
            prev = d
    return out
