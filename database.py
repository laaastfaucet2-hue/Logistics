"""قاعدة بيانات منظومة مخازن التعيينات (SQLite)."""
import os
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rations.db")

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
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    # ---------- المستخدم الافتراضي ----------
    if not cur.execute("SELECT 1 FROM users WHERE username='mostafa'").fetchone():
        cur.execute(
            "INSERT INTO users (username, password, full_name, role) VALUES (?,?,?,?)",
            ("mostafa", generate_password_hash("admin123"), "مصطفى", "admin"),
        )

    # ---------- المخازن ----------
    if cur.execute("SELECT COUNT(*) c FROM warehouses").fetchone()["c"] == 0:
        warehouses = [
            ("WH-01", "مخزن التعيينات الرئيسي", "القاهرة - مجمع المخازن", "أمين مخزن أول", "01001234567"),
            ("WH-02", "المخزن الفرعي", "الجيزة - منطقة التموين", "أمين مخزن", "01007654321"),
            ("WH-03", "مخزن الطوارئ", "القاهرة - الاحتياطي الاستراتيجي", "أمين مخزن", "01009876543"),
        ]
        cur.executemany(
            "INSERT INTO warehouses (code, name, location, keeper_name, phone) VALUES (?,?,?,?,?)",
            warehouses,
        )

    # ---------- الجهات المستفيدة ----------
    if cur.execute("SELECT COUNT(*) c FROM entities").fetchone()["c"] == 0:
        entities = [
            ("ENT-01", "معسكر الأمن المركزي - القاهرة", "معسكر", "مسؤول التموين", "01001111111"),
            ("ENT-02", "إدارة قوات الأمن - الجيزة", "إدارة", "مسؤول التموين", "01002222222"),
            ("ENT-03", "معسكر التدريب والتأهيل", "معسكر", "مسؤول التموين", "01003333333"),
            ("ENT-04", "الإدارة العامة للمرور", "إدارة", "مسؤول التموين", "01004444444"),
            ("ENT-05", "قطاع الحماية المجتمعية", "قطاع", "مسؤول التموين", "01005555555"),
        ]
        cur.executemany(
            "INSERT INTO entities (code, name, type, contact_name, phone) VALUES (?,?,?,?,?)",
            entities,
        )

    # ---------- التصنيفات والأصناف ----------
    if cur.execute("SELECT COUNT(*) c FROM items").fetchone()["c"] == 0:
        cats = ["حبوب وبقوليات", "معلبات", "زيوت وسمن", "مشروبات",
                "لحوم ودواجن", "خضروات وفاكهة", "توابل وبهارات"]
        cur.executemany("INSERT INTO categories (name) VALUES (?)", [(c,) for c in cats])
        cat_id = {r["name"]: r["id"] for r in cur.execute("SELECT id, name FROM categories")}

        items = [
            ("R-001", "أرز أبيض فاخر", "حبوب وبقوليات", "كجم", 500),
            ("R-002", "مكرونة", "حبوب وبقوليات", "كرتونة", 100),
            ("R-003", "سكر أبيض", "حبوب وبقوليات", "كجم", 400),
            ("R-004", "فول بلدي", "حبوب وبقوليات", "كجم", 300),
            ("R-005", "عدس أصفر", "حبوب وبقوليات", "كجم", 200),
            ("R-006", "فول مدمس معلب", "معلبات", "علبة", 500),
            ("R-007", "صلصة طماطم", "معلبات", "علبة", 400),
            ("R-008", "تونة معلبة", "معلبات", "علبة", 300),
            ("R-009", "زيت طعام", "زيوت وسمن", "لتر", 300),
            ("R-010", "سمن نباتي", "زيوت وسمن", "علبة", 150),
            ("R-011", "شاي", "مشروبات", "علبة", 100),
            ("R-012", "لحوم مجمدة", "لحوم ودواجن", "كجم", 200),
            ("R-013", "دجاج مجمد", "لحوم ودواجن", "كجم", 200),
            ("R-014", "بطاطس", "خضروات وفاكهة", "كجم", 150),
            ("R-015", "بصل", "خضروات وفاكهة", "كجم", 100),
            ("R-016", "ملح طعام", "توابل وبهارات", "كيس", 80),
        ]
        for code, name, cat, unit, minimum in items:
            cur.execute(
                "INSERT INTO items (code, name, category_id, unit, min_stock) VALUES (?,?,?,?,?)",
                (code, name, cat_id[cat], unit, minimum),
            )

    conn.commit()

    # ---------- الأرصدة الافتتاحية + حركات تجريبية ----------
    if cur.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"] == 0:
        _seed_demo_data(conn)

    conn.commit()
    conn.close()


def _seed_demo_data(conn):
    cur = conn.cursor()
    item_id = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM items")}
    wh_id = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM warehouses")}
    ent_id = {r["code"]: r["id"] for r in cur.execute("SELECT id, code FROM entities")}

    # أرصدة افتتاحية
    opening = {
        "WH-01": {"R-001": 5200, "R-002": 640, "R-003": 4100, "R-004": 2200,
                  "R-005": 120, "R-006": 3800, "R-007": 2900, "R-008": 1500,
                  "R-009": 2400, "R-010": 900, "R-011": 60, "R-012": 1600,
                  "R-013": 1900, "R-014": 800, "R-015": 500, "R-016": 700},
        "WH-02": {"R-001": 1200, "R-003": 900, "R-006": 800, "R-009": 500, "R-013": 400},
        "WH-03": {"R-001": 3000, "R-003": 2000, "R-009": 1000, "R-012": 800},
    }
    for wcode, stocks in opening.items():
        for icode, qty in stocks.items():
            cur.execute("INSERT INTO stock (warehouse_id, item_id, quantity) VALUES (?,?,?)",
                        (wh_id[wcode], item_id[icode], qty))

    def add_tx(ttype, number, date, wcode, items_list, ecode=None, supplier="", notes=""):
        cur.execute(
            """INSERT INTO transactions (type, number, date, warehouse_id, entity_id,
                                        supplier_name, notes, created_by)
               VALUES (?,?,?,?,?,?,?,1)""",
            (ttype, number, date, wh_id[wcode],
             ent_id[ecode] if ecode else None, supplier, notes),
        )
        tid = cur.lastrowid
        for icode, qty in items_list:
            cur.execute(
                "INSERT INTO transaction_items (transaction_id, item_id, quantity) VALUES (?,?,?)",
                (tid, item_id[icode], qty),
            )
            delta = qty if ttype == "supply" else -qty
            cur.execute(
                "UPDATE stock SET quantity = quantity + ? WHERE warehouse_id=? AND item_id=?",
                (delta, wh_id[wcode], item_id[icode]),
            )

    today = datetime.now().date()
    d = lambda days_ago: (today - timedelta(days=days_ago)).isoformat()

    # توريدات سابقة
    add_tx("supply", "SUP-2026-0001", d(9), "WH-01",
           [("R-001", 2000), ("R-003", 1500), ("R-009", 800)],
           supplier="الشركة العامة للسلع التموينية", notes="توريد شهري معتمد")
    add_tx("supply", "SUP-2026-0002", d(6), "WH-01",
           [("R-006", 1000), ("R-007", 800), ("R-011", 200)],
           supplier="شركة الأغذية المتحدة", notes="استكمال نواقص المعلبات")
    add_tx("supply", "SUP-2026-0003", d(3), "WH-01",
           [("R-012", 500), ("R-013", 600)],
           supplier="شركة اللحوم والدواجن", notes="توريد لحوم ودواجن مجمدة")
    add_tx("supply", "SUP-2026-0004", d(1), "WH-02",
           [("R-001", 500), ("R-009", 200)],
           supplier="الشركة العامة للسلع التموينية", notes="دعم المخزن الفرعي")

    # صرفيات على مدار الأسبوع (عشان الرسوم البيانية تبقى حية)
    add_tx("disbursement", "DIS-2026-0001", d(6), "WH-01",
           [("R-001", 400), ("R-003", 250), ("R-009", 150)], ecode="ENT-01",
           notes="تعيينات أسبوعية - الدفعة الأولى")
    add_tx("disbursement", "DIS-2026-0002", d(5), "WH-01",
           [("R-006", 300), ("R-007", 200), ("R-011", 40)], ecode="ENT-02",
           notes="صرف معلبات ومشروبات")
    add_tx("disbursement", "DIS-2026-0003", d(4), "WH-01",
           [("R-001", 350), ("R-004", 150), ("R-013", 120)], ecode="ENT-03",
           notes="تعيينات معسكر التدريب")
    add_tx("disbursement", "DIS-2026-0004", d(3), "WH-01",
           [("R-003", 200), ("R-009", 100), ("R-012", 90)], ecode="ENT-01",
           notes="استكمال صرف")
    add_tx("disbursement", "DIS-2026-0005", d(2), "WH-02",
           [("R-001", 150), ("R-009", 60)], ecode="ENT-04",
           notes="صرف من المخزن الفرعي")
    add_tx("disbursement", "DIS-2026-0006", d(1), "WH-01",
           [("R-002", 80), ("R-006", 250), ("R-008", 120)], ecode="ENT-05",
           notes="تعيينات القطاع")
    add_tx("disbursement", "DIS-2026-0007", d(0), "WH-01",
           [("R-001", 300), ("R-003", 180), ("R-007", 150)], ecode="ENT-02",
           notes="صرف اليوم")
    add_tx("disbursement", "DIS-2026-0008", d(0), "WH-01",
           [("R-013", 100), ("R-009", 80), ("R-011", 25)], ecode="ENT-03",
           notes="صرف اليوم - مسائي")


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
