# -*- coding: utf-8 -*-
"""مخطط جداول دورة «مستودعات وسجلات» — فصلت عن db_warehouses.py
لتحديدها في 1000 سطر (قاعدة إلزامية). بيانات صافية بلا استيرادات."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS wh_suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    name TEXT NOT NULL,
    contact TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    address TEXT DEFAULT '',
    activity TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wh_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    name TEXT NOT NULL,
    ration_unit TEXT DEFAULT '',
    handle_unit TEXT NOT NULL,
    base_unit TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (cycle, name)
);

CREATE TABLE IF NOT EXISTS wh_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    serial INTEGER NOT NULL,
    item_id INTEGER NOT NULL REFERENCES wh_items(id) ON DELETE CASCADE,
    day INTEGER NOT NULL,
    date_iso TEXT NOT NULL,
    qty_handle REAL NOT NULL,
    unit TEXT NOT NULL,
    qty_base REAL NOT NULL,
    base_unit TEXT NOT NULL,
    pack TEXT NOT NULL DEFAULT '{}',
    pack_label TEXT DEFAULT '',
    producer TEXT DEFAULT '',
    supplier_id INTEGER,
    supplier_name TEXT DEFAULT '',
    prod_date TEXT DEFAULT '',
    exp_date TEXT DEFAULT '',
    shelf_days INTEGER,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wh_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    item_id INTEGER NOT NULL REFERENCES wh_items(id) ON DELETE CASCADE,
    day INTEGER NOT NULL,
    date_iso TEXT NOT NULL,
    kind TEXT NOT NULL,             -- opener / add1 / manual (لاحقًا issue2 مع ٤–٧ مخازن)
    permit_no INTEGER NOT NULL DEFAULT 0,
    label TEXT DEFAULT '',
    added REAL NOT NULL DEFAULT 0,
    issued REAL NOT NULL DEFAULT 0,
    balance REAL NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wh_opener_stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    store_id INTEGER,
    store_name TEXT NOT NULL,
    qty REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS wh_receipt_stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id INTEGER NOT NULL REFERENCES wh_receipts(id) ON DELETE CASCADE,
    store_id INTEGER,
    store_name TEXT NOT NULL DEFAULT '',
    qty REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS wh_pack_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    item_id INTEGER NOT NULL REFERENCES wh_items(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    capacity REAL NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (cycle, item_id, kind)
);

CREATE TABLE IF NOT EXISTS wh_row_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    kind TEXT NOT NULL,            -- opener / add1 / issue2 — مفتاح سطر الدفتر
    permit_no INTEGER NOT NULL DEFAULT 0,
    day INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    UNIQUE (cycle, item_id, kind, permit_no, day)
);
"""



NEW_RECEIPT_COLUMNS = (
    ("pack_kind", "TEXT NOT NULL DEFAULT ''"),
    ("pack_count", "REAL"),
    ("pack_capacity", "REAL"),
    ("pack_loose", "REAL"),
    ("pack_inner_count", "REAL"),
    ("pack_inner_capacity", "REAL"),
    ("pack_inner_kind", "TEXT NOT NULL DEFAULT ''"),
    ("pack_loose_unit", "TEXT NOT NULL DEFAULT ''"),
    ("pack_inner_unit", "TEXT NOT NULL DEFAULT ''"),
)

NEW_LEDGER_COLUMNS = (
    ("prod_date", "TEXT DEFAULT ''"),
    ("exp_date", "TEXT DEFAULT ''"),
    ("pack_label", "TEXT DEFAULT ''"),
    # تغليف رصيد أول المدة بنفس خانات إذن ١ مخازن (١٥/١٠) — بدل الجملة بس
    ("pack_kind", "TEXT DEFAULT ''"),
    ("pack_count", "REAL DEFAULT 0"),
    ("pack_capacity", "REAL DEFAULT 0"),
    ("pack_loose", "REAL DEFAULT 0"),
    ("pack_inner_count", "REAL DEFAULT 0"),
    ("pack_inner_capacity", "REAL DEFAULT 0"),
    ("pack_inner_kind", "TEXT DEFAULT ''"),
    ("pack_loose_unit", "TEXT DEFAULT ''"),
    ("pack_inner_unit", "TEXT DEFAULT ''"),
)

NEW_ITEM_COLUMNS = (
    ("specific_weight", "REAL"),
)

NEW_SPEC_COLUMNS = (
    ("inner_count", "REAL DEFAULT 0"),
    ("inner_capacity", "REAL DEFAULT 0"),
    ("inner_kind", "TEXT DEFAULT ''"),
    ("inner_unit", "TEXT DEFAULT ''"),
)
