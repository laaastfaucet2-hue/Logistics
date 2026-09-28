# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الصحة — جداول شهرية داخل month.db (عزل شهري مطلق مثل اليومية):

- health_days:     أيام الكشف الدوري الثلاثة القابلة للتعديل (افتراضي 1 / 15 / 30).
- health_checkups: من اتم كشف طبي في كل يوم (day, recruit_id) — مصدر الاقتراح والإحصائية.
- health_fields:   نصوص التقارير الأربعة القابلة للتعديل (ترويسة + فقرات + تواقيع).

كل نص له افتراضي ثابت في documents/docx_health.py، والمخزَّن في القاعدة يعلوه.
"""
from data_access import months

_MIGRATE_SQL = """
CREATE TABLE IF NOT EXISTS health_days (
    day INTEGER PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS health_checkups (
    day INTEGER NOT NULL,
    recruit_id INTEGER NOT NULL DEFAULT 0,
    name TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS health_fields (
    report TEXT NOT NULL,
    fkey TEXT NOT NULL,
    fvalue TEXT DEFAULT '',
    PRIMARY KEY(report, fkey)
);
"""


def ensure_tables(conn):
    conn.executescript(_MIGRATE_SQL)
    # ترقية الجداول القديمة: عمود الاسم + إسقاط قيد UNIQUE
    row = conn.execute("PRAGMA table_info(health_checkups)").fetchall()
    cols = {r["name"] for r in row}
    if "name" not in cols:
        with conn:
            conn.executescript("""
                CREATE TABLE health_checkups_new (
                    day INTEGER NOT NULL, recruit_id INTEGER NOT NULL DEFAULT 0,
                    name TEXT DEFAULT '', created_at TEXT DEFAULT '');
                INSERT INTO health_checkups_new(day, recruit_id, name, created_at)
                    SELECT day, recruit_id, '', created_at FROM health_checkups;
                DROP TABLE health_checkups;
                ALTER TABLE health_checkups_new RENAME TO health_checkups;
            """)


# ==================== أيام الكشف الدوري الثلاثة ====================
DEFAULT_DAYS = [1, 15, 30]


def get_days(year, month):
    """أيام الكشف الثلاثة مرتبة — أول تشغيل يزرع الافتراضي 1/15/30."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = [r["day"] for r in conn.execute(
        "SELECT day FROM health_days ORDER BY day").fetchall()]
    if not rows:
        with conn:
            for d in DEFAULT_DAYS:
                conn.execute(
                    "INSERT OR IGNORE INTO health_days(day) VALUES (?)", (d,))
        rows = list(DEFAULT_DAYS)
    conn.close()
    return rows


def set_days(year, month, days):
    """استبدال الأيام الثلاثة — مع نقل سجلات الكشف لأقرب يوم جديد عند تغيّر الرقم."""
    days = sorted({int(d) for d in days if 1 <= int(d) <= 31})[:3]
    if not days:
        days = list(DEFAULT_DAYS)
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        old = [r["day"] for r in conn.execute(
            "SELECT day FROM health_days").fetchall()]
        for d in old:
            if d not in days:
                target = min(days, key=lambda n: abs(n - d))
                conn.execute(
                    "UPDATE OR IGNORE health_checkups SET day=? WHERE day=?",
                    (target, d))
                conn.execute("DELETE FROM health_days WHERE day=?", (d,))
        for d in days:
            conn.execute("INSERT OR IGNORE INTO health_days(day) VALUES (?)", (d,))
    conn.close()
    return days


# ==================== المكتوشون في كل يوم (مربعات أسماء) ====================
def get_day_entries(year, month, day):
    """مكتوشو يوم محدد بترتيب الإدخال: [{name, recruit_id}] —
    recruit_id=0 لاسم مكتوب يدويًا مش موجود في البرنامج."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = conn.execute(
        "SELECT recruit_id, name FROM health_checkups WHERE day=? ORDER BY rowid",
        (day,)).fetchall()
    conn.close()
    return [{"recruit_id": r["recruit_id"] or 0,
             "name": (r["name"] or "").strip()} for r in rows]


def set_day_entries(year, month, day, entries):
    """استبدال مكتوشي يوم محدد ذرّيًا — entries = [(name, recruit_id|0)]."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        conn.execute("DELETE FROM health_checkups WHERE day=?", (day,))
        for name, rid in entries:
            conn.execute(
                "INSERT INTO health_checkups(day, recruit_id, name, created_at)"
                " VALUES (?, ?, ?, datetime('now'))", (day, int(rid or 0), name))
    conn.close()


def month_checkup_ids(year, month):
    """كل ids مجند اتم كشفه في الشهر (مصدر إحصائية «لم يُكشفوا»)."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = {r["recruit_id"] for r in conn.execute(
        "SELECT DISTINCT recruit_id FROM health_checkups WHERE recruit_id > 0").fetchall()}
    conn.close()
    return rows


def day_map_full(year, month, day):
    """خريطة حضور يوم من اليومية — {recruit_id: status} لاقتراح «حاضرو اليوم»."""
    from data_access import db_attendance as da
    return {rid: v["status"] for rid, v in da.get_day_map(year, month, day).items()}


# ==================== نصوص التقارير القابلة للتعديل ====================
def get_fields(year, month, report):
    """حقول تقرير مخزنة (فوق الافتراضيات) — {fkey: fvalue}."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = {r["fkey"]: r["fvalue"] for r in conn.execute(
        "SELECT fkey, fvalue FROM health_fields WHERE report=?", (report,)).fetchall()}
    conn.close()
    return rows


def set_fields(year, month, report, mapping):
    """حفظ مجموعة حقول لتقرير — المفتاح الفارغ يُحذف فيرجع للافتراضي."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        for k, val in mapping.items():
            if val:
                conn.execute(
                    "INSERT INTO health_fields(report, fkey, fvalue) VALUES (?, ?, ?)"
                    " ON CONFLICT(report, fkey) DO UPDATE SET fvalue=excluded.fvalue",
                    (report, k, val))
            else:
                conn.execute(
                    "DELETE FROM health_fields WHERE report=? AND fkey=?",
                    (report, k))
    conn.close()


def delete_field(year, month, report, fkey):
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        conn.execute("DELETE FROM health_fields WHERE report=? AND fkey=?",
                     (report, fkey))
    conn.close()


def reset_report(year, month, report):
    """إرجاع كل نصوص تقرير للافتراضي."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        conn.execute("DELETE FROM health_fields WHERE report=?", (report,))
    conn.close()
