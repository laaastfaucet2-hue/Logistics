# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""«الإعدادات» — إدارة المستخدمين وصلاحيات التابات وسجل الحركة والملاحظات.

الجداول (في system.db):
- user_tabs     : صلاحية تاب لكل مستخدم (admin = الكل تلقائيًا)
- activity      : سجل كل حركة بالتاريخ والوقت بالثانية
- notes         : ملحوظة من مستخدم لمستخدم (open/replied/closed)
- note_replies  : الردود فوق الملحوظة
"""
import re
import sqlite3
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from data_access.database import get_conn

SCHEMA = """
CREATE TABLE IF NOT EXISTS user_tabs (
    user_id INTEGER NOT NULL,
    tab_key TEXT NOT NULL,
    PRIMARY KEY (user_id, tab_key)
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    event TEXT NOT NULL,
    page TEXT,
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_act_user_ts ON activity(user_id, ts);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user INTEGER NOT NULL,
    to_user INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    author_seen_at TEXT
);
CREATE TABLE IF NOT EXISTS note_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    from_user INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_replies_note ON note_replies(note_id);
"""


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_users():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


# ======================================================================
# المستخدمون
# ======================================================================
def list_users():
    conn = get_conn(readonly=True)
    rows = conn.execute("""
        SELECT u.*, (SELECT MAX(a.ts) FROM activity a
                      WHERE a.user_id = u.id AND a.event IN ('login', 'page', 'action')) AS last_seen
        FROM users u ORDER BY u.id""").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_full(user_id):
    conn = get_conn(readonly=True)
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


USERNAME_RE = re.compile(r"[a-z0-9][a-z0-9._-]{2,30}")
USERNAME_ERR = "اسم المستخدم: حروف إنجليزية صغيرة وأرقام ونقطة/خط — من ٣ لـ ٣١ حرف"


def create_user(full_name, username, password):
    """ينشئ حسابًا. يرجع (user_id, خطأ) — الخطأ = سبب الرفض."""
    full_name, username = (full_name or "").strip(), (username or "").strip().lower()
    if not full_name or not username or not password:
        return None, "الاسم واسم المستخدم والباسورد كلها مطلوب"
    if len(full_name) > 100:
        return None, "الاسم طويل جدًا — الحد الأقصى ١٠٠ حرف"
    if not USERNAME_RE.fullmatch(username):
        return None, USERNAME_ERR
    if len(password) < 3:
        return None, "الباسورد قصير — ٣ أحرف على الأقل"
    conn = get_conn()
    try:
        if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            return None, "اسم المستخدم موجود بالفعل"
        cur = conn.execute(
            "INSERT INTO users (username, password, full_name, role) VALUES (?,?,?,'storekeeper')",
            (username, generate_password_hash(password), full_name))
        conn.commit()
        return cur.lastrowid, None
    except sqlite3.IntegrityError:
        return None, "اسم المستخدم موجود بالفعل"
    finally:
        conn.close()


def update_user(user_id, full_name=None, username=None, password=None):
    """يعدّل الاسم/اسم المستخدم/الباسورد. يرجع سبب الرفض أو None."""
    conn = get_conn()
    try:
        if full_name is not None:
            if not full_name.strip():
                return "الاسم لازم يكون موجود"
            conn.execute("UPDATE users SET full_name=? WHERE id=?", (full_name.strip(), user_id))
        if username is not None:
            username = username.strip().lower()
            if not username:
                return "اسم المستخدم لازم يكون موجود"
            if not USERNAME_RE.fullmatch(username):
                return USERNAME_ERR
            if conn.execute("SELECT 1 FROM users WHERE id!=? AND username=?",
                             (user_id, username)).fetchone():
                return "اسم المستخدم هذا مستخدم لحساب آخر"
            conn.execute("UPDATE users SET username=? WHERE id=?", (username, user_id))
        if password:
            if len(password) < 3:
                return "الباسورد قصير — ٣ أحرف على الأقل"
            conn.execute("UPDATE users SET password=? WHERE id=?",
                         (generate_password_hash(password), user_id))
        conn.commit()
        return None
    finally:
        conn.close()


def set_active(user_id, active):
    conn = get_conn()
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (1 if active else 0, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = get_conn()
    # كل الجداول المرتبطة بـ FK تتنضف الأول (إلا حذف الحساب يكسر القاعدة)
    conn.execute("DELETE FROM note_replies WHERE note_id IN "
                 "(SELECT id FROM notes WHERE from_user=? OR to_user=?)", (user_id, user_id))
    conn.execute("DELETE FROM note_replies WHERE from_user=?", (user_id,))
    conn.execute("DELETE FROM notes WHERE from_user=? OR to_user=?", (user_id, user_id))
    conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM user_context WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM user_tabs WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM activity WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def admin_count():
    conn = get_conn(readonly=True)
    n = conn.execute("SELECT COUNT(*) c FROM users WHERE role='admin' AND is_active=1").fetchone()["c"]
    conn.close()
    return n


# ======================================================================
# صلاحيات التابات
# ======================================================================
def get_user_tabs(user_id):
    conn = get_conn(readonly=True)
    rows = conn.execute("SELECT tab_key FROM user_tabs WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return {r["tab_key"] for r in rows}


def set_user_tabs(user_id, tab_keys):
    """يستبدل كل صلاحيات المستخدم بالقائمة المعطاة."""
    conn = get_conn()
    conn.execute("DELETE FROM user_tabs WHERE user_id=?", (user_id,))
    conn.executemany("INSERT OR IGNORE INTO user_tabs (user_id, tab_key) VALUES (?,?)",
                     [(user_id, k) for k in sorted(set(tab_keys))])
    conn.commit()
    conn.close()


# ======================================================================
# سجل الحركة (بالثانية)
# ======================================================================
def log_activity(user_id, event, page=None, details=None):
    """يسجل حركة: login/logout/page/action/note — الوقت بالتاريخ والثانية."""
    if not user_id:
        return
    conn = get_conn()
    conn.execute("INSERT INTO activity (user_id, ts, event, page, details) VALUES (?,?,?,?,?)",
                 (user_id, _now(), event, page, (details or "")[:400] or None))
    conn.commit()
    conn.close()


def last_activity_ts(user_id):
    conn = get_conn(readonly=True)
    row = conn.execute("SELECT MAX(ts) m FROM activity WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row["m"]


def list_activity(user_id, limit=400):
    conn = get_conn(readonly=True)
    rows = conn.execute(
        "SELECT ts, event, page, details FROM activity WHERE user_id=? "
        "ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_activity(user_id):
    conn = get_conn(readonly=True)
    row = conn.execute("SELECT COUNT(*) c FROM activity WHERE user_id=?",
                       (user_id,)).fetchone()
    conn.close()
    return row["c"]


def _sessions_from_events(events, gap_seconds=15 * 60):
    """يقسم الأحداث (مرتبة تصاعديًا) على جلسات: فرق أكتر من ١٥ دقيقة = جلسة جديدة.
    يرجع [(اليوم, بداية, نهاية)] — المدة = نهاية−بداية لكل جلسة."""
    from datetime import datetime as dt
    sessions, cur = [], None
    prev = None
    for ts in events:
        t = dt.strptime(ts, "%Y-%m-%d %H:%M:%S")
        if prev is None or (t - prev).total_seconds() > gap_seconds:
            cur = [t.date(), t, t]
            sessions.append(cur)
        else:
            cur[2] = t
        prev = t
    return sessions


def day_stats(user_id, year, month, day):
    """إحصائيات يوم: جلسات + مدة العمل + حركات + إجراءات."""
    prefix = f"{year:04d}-{month:02d}-{day:02d}"
    conn = get_conn(readonly=True)
    rows = conn.execute(
        "SELECT ts, event FROM activity WHERE user_id=? AND ts LIKE ? "
        "ORDER BY ts", (user_id, prefix + "%")).fetchall()
    conn.close()
    tss = [r["ts"] for r in rows]
    sessions = _sessions_from_events(tss)
    work_sec = sum((s[2] - s[1]).total_seconds() for s in sessions)
    return {
        "sessions": len(sessions),
        "work_seconds": int(work_sec),
        "events": len(tss),
        "actions": sum(1 for r in rows if r["event"] in ("action", "login", "logout")),
    }


def month_stats(user_id, year, month):
    """إجمالي شهر: مدة + جلسات + أيام شغل + حركات."""
    prefix = f"{year:04d}-{month:02d}"
    conn = get_conn(readonly=True)
    rows = conn.execute(
        "SELECT ts, event FROM activity WHERE user_id=? AND ts LIKE ? "
        "ORDER BY ts", (user_id, prefix + "%")).fetchall()
    conn.close()
    tss = [r["ts"] for r in rows]
    sessions = _sessions_from_events(tss)
    work_sec = sum((s[2] - s[1]).total_seconds() for s in sessions)
    days = {s[0] for s in sessions}
    return {
        "sessions": len(sessions),
        "work_seconds": int(work_sec),
        "events": len(tss),
        "work_days": len(days),
        "actions": sum(1 for r in rows if r["event"] in ("action", "login", "logout")),
    }


def year_stats(user_id, year):
    prefix = f"{year:04d}"
    conn = get_conn(readonly=True)
    rows = conn.execute(
        "SELECT ts FROM activity WHERE user_id=? AND ts LIKE ? ORDER BY ts",
        (user_id, prefix + "%")).fetchall()
    conn.close()
    tss = [r["ts"] for r in rows]
    sessions = _sessions_from_events(tss)
    return {
        "sessions": len(sessions),
        "work_seconds": int(sum((s[2] - s[1]).total_seconds() for s in sessions)),
        "events": len(tss),
        "work_days": len({s[0] for s in sessions}),
    }


def total_stats(user_id):
    """من أول استخدام: مدة + أيام شغل + حركات."""
    conn = get_conn(readonly=True)
    row = conn.execute(
        "SELECT MIN(ts) first_ts, MAX(ts) last_ts, COUNT(*) c FROM activity WHERE user_id=?",
        (user_id,)).fetchone()
    rows = conn.execute(
        "SELECT ts FROM activity WHERE user_id=? ORDER BY ts", (user_id,)).fetchall()
    conn.close()
    if not row["c"]:
        return {"events": 0, "work_seconds": 0, "work_days": 0, "sessions": 0,
                "first_ts": None, "last_ts": None}
    sessions = _sessions_from_events([r["ts"] for r in rows])
    return {
        "events": row["c"],
        "work_seconds": int(sum((s[2] - s[1]).total_seconds() for s in sessions)),
        "work_days": len({s[0] for s in sessions}),
        "sessions": len(sessions),
        "first_ts": row["first_ts"],
        "last_ts": row["last_ts"],
    }


def fmt_seconds(sec):
    """ثواني → «س س د د ث ث» بالأرقام العربية (للعرض)."""
    from core import arabic_numbers as arnum
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(arnum.to_arabic_indic(f"{h} س"))
    if m or h:
        parts.append(arnum.to_arabic_indic(f"{m} د"))
    parts.append(arnum.to_arabic_indic(f"{s} ث"))
    return " ".join(parts)


def fmt_hm(sec):
    """ثواني → «ساعة + دقيقة» (اليوم — توجيه ١١/١٠: بلا ثواني)."""
    from core import arabic_numbers as arnum
    h, rem = divmod(int(sec), 3600)
    m = rem // 60
    parts = []
    if h:
        parts.append(arnum.to_arabic_indic(f"{h} س"))
    parts.append(arnum.to_arabic_indic(f"{m} د"))
    return " ".join(parts)


def fmt_dhm(sec):
    """ثواني → «يوم + ساعة + دقيقة» (الشهر/السنة/الإجمالي — توجيه ١١/١٠: بلا ثواني)."""
    from core import arabic_numbers as arnum
    d, rem = divmod(int(sec), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    parts = []
    if d:
        parts.append(arnum.to_arabic_indic(f"{d} ي"))
    if h or d:
        parts.append(arnum.to_arabic_indic(f"{h} س"))
    parts.append(arnum.to_arabic_indic(f"{m} د"))
    return " ".join(parts)


# ======================================================================
# الملاحظات والردود
# ======================================================================
def add_note(from_user, to_user, text):
    """السجل التفصيلي («إلى: الاسم») بيتسجل من الروت — هنا بيانات بس."""
    text = (text or "").strip()
    if not text or from_user == to_user:
        return None
    conn = get_conn()
    if not conn.execute("SELECT 1 FROM users WHERE id=? AND is_active=1",
                        (to_user,)).fetchone():
        conn.close()
        return None
    cur = conn.execute(
        "INSERT INTO notes (from_user, to_user, text, created_at) VALUES (?,?,?,?)",
        (from_user, to_user, text, _now()))
    conn.commit()
    note_id = cur.lastrowid
    conn.close()
    return note_id


def reply_note(note_id, from_user, text):
    text = (text or "").strip()
    if not text:
        return None
    conn = get_conn()
    note = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
    if not note:
        conn.close()
        return None
    conn.execute("INSERT INTO note_replies (note_id, from_user, text, created_at) "
                 "VALUES (?,?,?,?)", (note_id, from_user, text, _now()))
    if note["status"] != "closed":
        conn.execute("UPDATE notes SET status='replied' WHERE id=?", (note_id,))
    conn.commit()
    conn.close()
    log_activity(from_user, "note", "settings:notes", f"رد على الملحوظة #{note_id}")
    return True


def close_note(note_id, user_id):
    conn = get_conn()
    note = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
    if note and (note["from_user"] == user_id or note["to_user"] == user_id):
        conn.execute("UPDATE notes SET status='closed' WHERE id=?", (note_id,))
        conn.commit()
    conn.close()


def mark_author_seen(note_id, user_id):
    conn = get_conn()
    note = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
    if note and note["from_user"] == user_id and note["status"] == "replied":
        last = conn.execute(
            "SELECT MAX(created_at) m FROM note_replies WHERE note_id=?",
            (note_id,)).fetchone()["m"]
        if not note["author_seen_at"] or (last and note["author_seen_at"] < last):
            conn.execute("UPDATE notes SET author_seen_at=? WHERE id=?", (last or _now(), note_id))
            conn.commit()
    conn.close()


def note_thread(note_id):
    """ملحوظة + ردودها بالترتيب."""
    conn = get_conn(readonly=True)
    note = conn.execute(
        """SELECT n.*, fu.full_name AS from_name, tu.full_name AS to_name
           FROM notes n
           JOIN users fu ON fu.id = n.from_user
           JOIN users tu ON tu.id = n.to_user
           WHERE n.id=?""", (note_id,)).fetchone()
    if not note:
        conn.close()
        return None
    replies = conn.execute(
        """SELECT r.*, u.full_name AS from_name FROM note_replies r
           JOIN users u ON u.id = r.from_user
           WHERE r.note_id=? ORDER BY r.id""", (note_id,)).fetchall()
    conn.close()
    return {"note": dict(note),
            "replies": [dict(r) for r in replies]}


def list_notes(user_id, role="storekeeper"):
    """ملاحظات المستخدم: اللي إليه + اللي منه (الـ admin كل حاجة).
    مع اسم المُرسِل/المُرسَل إليه ووقت آخر رد وحالة قراءة المُرسِل."""
    if role == "admin":
        where, params = "1=1", ()
    else:
        where, params = "(n.from_user=? OR n.to_user=?)", (user_id, user_id)
    conn = get_conn(readonly=True)
    rows = conn.execute(f"""
        SELECT n.*, fu.full_name AS from_name, tu.full_name AS to_name,
               (SELECT MAX(r.created_at) FROM note_replies r WHERE r.note_id=n.id) AS last_reply_at
        FROM notes n
        JOIN users fu ON fu.id = n.from_user
        JOIN users tu ON tu.id = n.to_user
        WHERE {where} ORDER BY n.id DESC LIMIT 500""", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def unread_counts(user_id):
    """إشعارات المستخدم: (ملحوظات جديدة له، ردود على ملاحظاته)."""
    conn = get_conn(readonly=True)
    to_me = conn.execute(
        "SELECT COUNT(*) c FROM notes WHERE to_user=? AND status='open'",
        (user_id,)).fetchone()["c"]
    for_me = conn.execute("""
        SELECT COUNT(*) c FROM notes
        WHERE from_user=? AND status='replied'
          AND (author_seen_at IS NULL
               OR author_seen_at < (SELECT MAX(created_at) FROM note_replies r
                                    WHERE r.note_id = notes.id))""",
                          (user_id,)).fetchone()["c"]
    conn.close()
    return {"to_me": to_me, "for_me": for_me}
