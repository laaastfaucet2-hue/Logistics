# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""قاعدة بيانات كل شهر (month.db) — الاتصال والتهيئة والترقيات التدريجية.

كل شهر له قاعدة مستقلة تمامًا داخل مجلده: database/<سنة>/<شهر>/month.db
ممنوع خلط بيانات شهر بشهر آخر.
"""
import sqlite3

from data_access import storage
from core.config import month_folder

SCHEMA = """
CREATE TABLE IF NOT EXISTS ration_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section TEXT NOT NULL,          -- tamween / contractor
    kind TEXT NOT NULL,             -- summer / winter / ramadan
    serial INTEGER NOT NULL,
    name TEXT NOT NULL,
    unit TEXT DEFAULT '',
    breakfast REAL, lunch REAL, dinner REAL
);

CREATE TABLE IF NOT EXISTS ration_custom (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES ration_items(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL,       -- 0=السبت ... 6=الجمعة
    meal TEXT NOT NULL,             -- breakfast / lunch / dinner
    qty REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ration_activation (
    section TEXT PRIMARY KEY,       -- مقرر واحد مفعّل فقط لكل قسم
    kind TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    serial INTEGER NOT NULL,
    section TEXT NOT NULL DEFAULT 'contractor'
);

CREATE TABLE IF NOT EXISTS entity_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    serial INTEGER NOT NULL,
    name TEXT NOT NULL,
    unit TEXT DEFAULT '',
    breakfast REAL, lunch REAL, dinner REAL
);

CREATE TABLE IF NOT EXISTS entity_item_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_item_id INTEGER NOT NULL REFERENCES entity_items(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL,       -- وجود أي يوم = المقرر مخصص لتلك الأيام فقط
    qty REAL                        -- مقرر هذا اليوم تحديدًا؛ الفارغ = قيمة الوجبات العامة
);
"""


def month_db_path(year, month):
    return storage.year_path(year) / month_folder(month) / "month.db"


def _migrate(conn):
    """ترقيات تدريجية لقواعد الشهور المنشأة قبل تطوير المخطط."""
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(entity_item_days)")}
        if cols and "qty" not in cols:
            conn.execute("ALTER TABLE entity_item_days ADD COLUMN qty REAL")
            conn.commit()
    except Exception:
        pass
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(entities)")}
        if cols and "section" not in cols:
            conn.execute("ALTER TABLE entities ADD COLUMN section TEXT NOT NULL DEFAULT 'contractor'")
            conn.commit()
    except Exception:
        pass


def get_db(year, month):
    path = month_db_path(year, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")      # تحمي من التلف عند انقطاع الكهرباء/التشغيل
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 8000")     # انتظار بدل التصادم لو اتنين كتبوا معًا
    conn.execute("PRAGMA foreign_keys = ON")
    _migrate(conn)
    return conn


def init_month(year, month):
    """ينشئ جداول الشهر إن لم تكن موجودة.""" 
    conn = get_db(year, month)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
