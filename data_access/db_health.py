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
    recruit_id INTEGER NOT NULL,
    created_at TEXT DEFAULT '',
    UNIQUE(day, recruit_id)
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


# ==================== المكتوشون في كل يوم ====================
def get_day_recruits(year, month, day):
    """ids المجندين المكتوشين في يوم كشف محدد."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = [r["recruit_id"] for r in conn.execute(
        "SELECT recruit_id FROM health_checkups WHERE day=? ORDER BY recruit_id",
        (day,)).fetchall()]
    conn.close()
    return rows


def set_day_recruits(year, month, day, recruit_ids):
    """استبدال قائمة مكتوشي يوم محدد ذرّيًا."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    with conn:
        conn.execute("DELETE FROM health_checkups WHERE day=?", (day,))
        for rid in recruit_ids:
            conn.execute(
                "INSERT OR IGNORE INTO health_checkups(day, recruit_id, created_at)"
                " VALUES (?, ?, datetime('now'))", (day, int(rid)))
    conn.close()


def month_checkup_ids(year, month):
    """كل ids اتم كشفه في الشهر (مصدر إحصائية «لم يُكشفوا»)."""
    conn = months.get_db(year, month)
    ensure_tables(conn)
    rows = {r["recruit_id"] for r in conn.execute(
        "SELECT DISTINCT recruit_id FROM health_checkups").fetchall()}
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
