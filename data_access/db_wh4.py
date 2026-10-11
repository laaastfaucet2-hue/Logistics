# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""«دفتر 4 مخازن» — بيانات الشطب اليومي وسعر الوحدة وإعدادات الموافقة.

ثلاث جداول صغيرة جوا قاعدة الشهر:
- wh4_strike: شطب يومي (صنف × يوم) — إدخال المستخدم (وحدة الدفتر).
- wh4_price: سعر الوحدة لكل صنف (يُحسب منه عمود القيمة تلقائيًا).
- wh4_meta: إعدادات نصية (سطر الموافقة «موافق من (مستودع)»…).

الدفتر نفسه توليد تلقائي من ١/٢/٣ مخازن — راجع services/wh4_build.py.
"""

from core import egtime
from data_access import months

SCHEMA = """
CREATE TABLE IF NOT EXISTS wh4_strike (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    item_name TEXT NOT NULL,
    day INTEGER NOT NULL,
    qty REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE (cycle, item_name, day)
);
CREATE TABLE IF NOT EXISTS wh4_price (
    cycle TEXT NOT NULL,
    item_name TEXT NOT NULL,
    price REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (cycle, item_name)
);
CREATE TABLE IF NOT EXISTS wh4_meta (
    cycle TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (cycle, key)
);
"""


def _conn(year, month):
    conn = months.get_db(year, month)
    conn.executescript(SCHEMA)
    return conn


def _stamp():
    return egtime.now().isoformat(timespec="seconds")


# ======================================================================
# الشطب اليومى (صنف × يوم) — وحدة الدفتر
# ======================================================================
def set_strike(year, month, cycle, item_name, day, qty):
    """يحفظ خلية شطب — فاضي/صفر = شطب يوم ده (حذف)."""
    name = " ".join((item_name or "").split())
    if not name:
        return False
    conn = _conn(year, month)
    if qty:
        conn.execute(
            "INSERT INTO wh4_strike (cycle,item_name,day,qty,updated_at) VALUES (?,?,?,?,?) "
            "ON CONFLICT(cycle,item_name,day) DO UPDATE SET qty=excluded.qty, "
            "updated_at=excluded.updated_at",
            (cycle, name, int(day), float(qty), _stamp()))
    else:
        conn.execute("DELETE FROM wh4_strike WHERE cycle=? AND item_name=? AND day=?",
                     (cycle, name, int(day)))
    conn.commit()
    conn.close()
    return True


def strike_map(year, month, cycle):
    """{(اسم الصنف): {يوم: كمية}} — مصفوفة الشطب كلها للشهر."""
    conn = _conn(year, month)
    rows = conn.execute("SELECT item_name, day, qty FROM wh4_strike WHERE cycle=?",
                        (cycle,)).fetchall()
    conn.close()
    out = {}
    for r in rows:
        q = float(r["qty"] or 0)
        if q > 0:
            out.setdefault(r["item_name"], {})[int(r["day"])] = round(q, 6)
    return out


# ======================================================================
# سعر الوحدة (يُحسب منه عمود القيمة في دفتر الشهرى)
# ======================================================================
def set_price(year, month, cycle, item_name, price):
    name = " ".join((item_name or "").split())
    if not name:
        return False
    conn = _conn(year, month)
    if price:
        conn.execute(
            "INSERT INTO wh4_price (cycle,item_name,price,updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(cycle,item_name) DO UPDATE SET price=excluded.price, "
            "updated_at=excluded.updated_at",
            (cycle, name, float(price), _stamp()))
    else:
        conn.execute("DELETE FROM wh4_price WHERE cycle=? AND item_name=?", (cycle, name))
    conn.commit()
    conn.close()
    return True


def price_map(year, month, cycle):
    conn = _conn(year, month)
    rows = conn.execute("SELECT item_name, price FROM wh4_price WHERE cycle=?", (cycle,)).fetchall()
    conn.close()
    return {r["item_name"]: float(r["price"] or 0) for r in rows}


# ======================================================================
# إعدادات نصية (الموافقة…)
# ======================================================================
def set_meta(year, month, cycle, key, value):
    conn = _conn(year, month)
    value = (value or "").strip()
    if value:
        conn.execute(
            "INSERT INTO wh4_meta (cycle,key,value,updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(cycle,key) DO UPDATE SET value=excluded.value, "
            "updated_at=excluded.updated_at",
            (cycle, key, value, _stamp()))
    else:
        conn.execute("DELETE FROM wh4_meta WHERE cycle=? AND key=?", (cycle, key))
    conn.commit()
    conn.close()


def get_meta(year, month, cycle, key):
    conn = _conn(year, month)
    row = conn.execute("SELECT value FROM wh4_meta WHERE cycle=? AND key=?",
                       (cycle, key)).fetchone()
    conn.close()
    return row["value"] if row else ""
