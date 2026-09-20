# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""قاعدة بيانات كل شهر (month.db) — الاتصال والتهيئة.

كل شهر له قاعدة مستقلة تمامًا داخل مجلده: database/<سنة>/<شهر>/month.db
ممنوع خلط بيانات شهر بشهر آخر.
"""
import sqlite3

import storage
from config import month_folder

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
    serial INTEGER NOT NULL
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
    weekday INTEGER NOT NULL        -- وجود أي يوم = المقرر مخصص لتلك الأيام فقط
);
"""


def month_db_path(year, month):
    return storage.year_path(year) / month_folder(month) / "month.db"


def get_db(year, month):
    path = month_db_path(year, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_month(year, month):
    """ينشئ جداول الشهر إن لم تكن موجودة."""
    conn = get_db(year, month)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
