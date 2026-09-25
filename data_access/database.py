# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""قاعدة بيانات منظومة مخازن التعيينات (SQLite).

ملف النظام system.db يعيش داخل مجلد database/ الذي يحتوي أيضًا
على مجلدات السنوات والشهور والأقسام (انظر storage.py).
"""
import os
import secrets
import shutil
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

from core.paths import DATA_DIR, RESOURCE_DIR

DB_PATH = DATA_DIR / "system.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'storekeeper',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS warehouses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    location TEXT DEFAULT '',
    keeper_name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    type TEXT DEFAULT 'وحدة',
    contact_name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    address TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    unit TEXT NOT NULL DEFAULT 'قطعة',
    min_stock REAL NOT NULL DEFAULT 0,
    description TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stock (
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
    item_id INTEGER NOT NULL REFERENCES items(id),
    quantity REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (warehouse_id, item_id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    number TEXT UNIQUE NOT NULL,
    date TEXT NOT NULL,
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
    entity_id INTEGER REFERENCES entities(id),
    supplier_name TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transaction_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    item_id INTEGER NOT NULL REFERENCES items(id),
    quantity REAL NOT NULL,
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_context (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    year INTEGER NOT NULL,
    month INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS shared_vocab (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    parent TEXT NOT NULL DEFAULT '',
    UNIQUE(kind, value, parent)
);
"""


def get_conn(path=None, readonly=False):
    from pathlib import Path
    target = Path(path or DB_PATH).resolve()
    if not readonly:
        target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target.as_uri() + "?mode=ro" if readonly else str(target),
                           uri=readonly, timeout=10)
    conn.row_factory = sqlite3.Row
    if not readonly:
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 8000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """ينشئ الجداول + حساب المدير فقط (بدون أي بيانات تجريبية)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    # ---------- حساب المدير فقط ----------
    if not cur.execute("SELECT 1 FROM users WHERE username='mostafa'").fetchone():
        cur.execute(
            "INSERT INTO users (username, password, full_name, role) VALUES (?,?,?,?)",
            ("mostafa", generate_password_hash("779"), "مصطفى", "admin"),
        )

    conn.commit()
    conn.close()


# ======================================================================
# جلسات الدخول بالتوكن (بديل الكوكيز — يعمل داخل المعاينة مهما كان إعداد المتصفح)
# ======================================================================
def create_session(user_id, hours=12):
    """ينشئ توكن جلسة جديد للمستخدم ويرجعه."""
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(hours=hours)).isoformat(sep=" ", timespec="seconds")
    conn = get_conn()
    conn.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)",
                 (token, user_id, expires))
    conn.execute("DELETE FROM sessions WHERE expires_at <= datetime('now','localtime')")
    conn.commit()
    conn.close()
    return token


def get_session_user(token):
    """يرجع بيانات المستخدم صاحب التوكن لو ساري، وإلا None."""
    if not token:
        return None
    conn = get_conn()
    row = conn.execute(
        """SELECT u.id, u.username, u.full_name, u.role FROM sessions s
           JOIN users u ON u.id = s.user_id
           WHERE s.token = ? AND s.expires_at > datetime('now','localtime') AND u.is_active = 1""",
        (token,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_session(token):
    """يحذف توكن الجلسة (تسجيل الخروج)."""
    if not token:
        return
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


# ======================================================================
# سياق السنة/الشهر المحدد لكل مستخدم (يظل محفوظًا بين الجلسات)
# ======================================================================
def get_user_context(user_id):
    """يرجع {'year':…, 'month':…} للمستخدم أو None لو لم يُحدد بعد."""
    conn = get_conn()
    row = conn.execute(
        "SELECT year, month FROM user_context WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_user_context(user_id, year, month):
    """يحفظ السنة والشهر النشطين للمستخدم."""
    month = max(1, min(12, int(month)))
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO user_context (user_id, year, month) VALUES (?,?,?)",
        (user_id, int(year), month))
    conn.commit()
    conn.close()


def reset_context_year(deleted_year, fallback_year):
    """عند حذف سنة: كل مستخدم كان عليها ينتقل تلقائيًا لأحدث سنة متبقية."""
    conn = get_conn()
    conn.execute("UPDATE user_context SET year=? WHERE year=?",
                 (int(fallback_year), int(deleted_year)))
    conn.commit()
    conn.close()


# ======================================================================
# إعدادات عامة (الدباجة، التوقيعات الرسمية...) — مخزنة في system.db
# ======================================================================
def get_setting(key, default=""):
    conn = get_conn()
    row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?,?)",
                 (key, value or ""))
    conn.commit()
    conn.close()


# ======================================================================
# قاموس مشترك دائم (وحدات القياس + محافظات/مدن/قرى يضيفها المستخدم)
# يبقى عبر الشهور — بخلاف vocab الشهري للمجندين الذي يُبذر مرة واحدة.
# ======================================================================
def _ensure_shared_vocab(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS shared_vocab ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "kind TEXT NOT NULL, value TEXT NOT NULL,"
        "parent TEXT NOT NULL DEFAULT '',"
        "UNIQUE(kind, value, parent))")


def vocab_add(kind, value, parent=""):
    value = (value or "").strip()
    parent = (parent or "").strip()
    if not value:
        return
    conn = get_conn()
    _ensure_shared_vocab(conn)
    conn.execute("INSERT OR IGNORE INTO shared_vocab(kind, value, parent) VALUES (?,?,?)",
                 (kind, value, parent))
    conn.commit()
    conn.close()


def vocab_list(kind, parent=None):
    conn = get_conn()
    _ensure_shared_vocab(conn)
    if parent is None:
        rows = conn.execute(
            "SELECT value FROM shared_vocab WHERE kind=? ORDER BY id", (kind,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT value FROM shared_vocab WHERE kind=? AND parent=? ORDER BY id",
            (kind, parent or "")).fetchall()
    conn.close()
    return [r["value"] for r in rows]


def vocab_places_map():
    """{المحافظة: [مدن/قرى مضافة يدويًا]} من القاموس المشترك."""
    conn = get_conn()
    _ensure_shared_vocab(conn)
    rows = conn.execute(
        "SELECT parent, value FROM shared_vocab WHERE kind='place' ORDER BY id").fetchall()
    conn.close()
    out = {}
    for r in rows:
        out.setdefault(r["parent"] or "", []).append(r["value"])
    return out


# ======================================================================
def get_user(username):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1",
                       (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_dashboard_stats():
    conn = get_conn()
    cur = conn.cursor()
    today = datetime.now().date().isoformat()
    month = datetime.now().strftime("%Y-%m")

    total_items = cur.execute("SELECT COUNT(*) c FROM items WHERE is_active=1").fetchone()["c"]
    total_warehouses = cur.execute("SELECT COUNT(*) c FROM warehouses WHERE is_active=1").fetchone()["c"]
    total_entities = cur.execute("SELECT COUNT(*) c FROM entities WHERE is_active=1").fetchone()["c"]
    today_disb = cur.execute(
        "SELECT COUNT(*) c FROM transactions WHERE type='disbursement' AND date=?", (today,)).fetchone()["c"]
    month_disb = cur.execute(
        "SELECT COUNT(*) c FROM transactions WHERE type='disbursement' AND substr(date,1,7)=?", (month,)).fetchone()["c"]
    month_supp = cur.execute(
        "SELECT COUNT(*) c FROM transactions WHERE type='supply' AND substr(date,1,7)=?", (month,)).fetchone()["c"]

    low_stock = [dict(r) for r in cur.execute("""
        SELECT i.code, i.name AS item_name, i.unit, i.min_stock,
               w.name AS warehouse_name, s.quantity,
               CASE WHEN s.quantity <= i.min_stock * 0.5 THEN 'حرج' ELSE 'منخفض' END AS level
        FROM stock s
        JOIN items i ON i.id = s.item_id
        JOIN warehouses w ON w.id = s.warehouse_id
        WHERE s.quantity <= i.min_stock AND i.is_active = 1
        ORDER BY (s.quantity / CASE WHEN i.min_stock = 0 THEN 1 ELSE i.min_stock END)
        LIMIT 8
    """)]

    recent = [dict(r) for r in cur.execute("""
        SELECT t.id, t.type, t.number, t.date, w.name AS warehouse_name,
               e.name AS entity_name, t.supplier_name, u.full_name AS created_by_name,
               (SELECT COUNT(*) FROM transaction_items ti WHERE ti.transaction_id = t.id) AS items_count,
               (SELECT COALESCE(SUM(quantity),0) FROM transaction_items ti WHERE ti.transaction_id = t.id) AS total_qty
        FROM transactions t
        JOIN warehouses w ON w.id = t.warehouse_id
        LEFT JOIN entities e ON e.id = t.entity_id
        LEFT JOIN users u ON u.id = t.created_by
        ORDER BY t.date DESC, t.id DESC
        LIMIT 8
    """)]

    # حركة آخر 7 أيام
    short_days = ["إثن", "ثلا", "أرب", "خمي", "جمع", "سبت", "أحد"]
    labels, disb_data, supp_data = [], [], []
    for i in range(6, -1, -1):
        day = datetime.now().date() - timedelta(days=i)
        labels.append(short_days[day.weekday()])
        iso = day.isoformat()
        disb_data.append(cur.execute(
            "SELECT COUNT(*) c FROM transactions WHERE type='disbursement' AND date=?", (iso,)).fetchone()["c"])
        supp_data.append(cur.execute(
            "SELECT COUNT(*) c FROM transactions WHERE type='supply' AND date=?", (iso,)).fetchone()["c"])

    # الأصناف الأكثر صرفاً
    top = cur.execute("""
        SELECT i.name, SUM(ti.quantity) AS total
        FROM transaction_items ti
        JOIN transactions t ON t.id = ti.transaction_id
        JOIN items i ON i.id = ti.item_id
        WHERE t.type = 'disbursement'
        GROUP BY i.name
        ORDER BY total DESC
        LIMIT 5
    """).fetchall()

    conn.close()
    return {
        "total_items": total_items,
        "total_warehouses": total_warehouses,
        "total_entities": total_entities,
        "today_disb": today_disb,
        "month_disb": month_disb,
        "month_supp": month_supp,
        "low_count": len(low_stock),
        "low_stock": low_stock,
        "recent": recent,
        "chart7": {"labels": labels, "disb": disb_data, "supp": supp_data},
        "top_items": {"labels": [r["name"] for r in top],
                      "data": [r["total"] for r in top]},
    }
