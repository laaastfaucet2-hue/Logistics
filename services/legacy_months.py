"""Explicit legacy-to-month migration, never automatic historical guesses."""
from data_access import database as db, storage, dataguard, months, db_letterhead as lh
from services.month_copy import insert_registry, copy_letterhead, valid_period


def legacy_registry():
    path = storage.DATA_DIR / "recruits.db"
    if not path.is_file():
        return []
    conn = db.get_conn(path, readonly=True)
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='recruits'").fetchone():
            return []
        return [dict(row) for row in conn.execute("SELECT * FROM recruits ORDER BY id")]
    finally:
        conn.close()


def registry_available():
    return len(legacy_registry())


def letterhead_available():
    return any(db.get_setting(key) for key in lh.KEYS)


def imported(kind, year, month):
    conn = months.get_db(year, month)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS migration_log (kind TEXT PRIMARY KEY, imported_at TEXT)")
        return bool(conn.execute("SELECT 1 FROM migration_log WHERE kind=?", (kind,)).fetchone())
    finally:
        conn.close()


def import_to_month(kind, year, month, replace=False):
    valid_period(year, month)
    if imported(kind, year, month):
        raise ValueError("تم استيراد هذا المصدر للشهر من قبل؛ استخدم النسخ بين الشهور بدلًا من تكراره")
    dataguard.create_backup("pre-migration")
    if kind == "registry":
        rows = legacy_registry()
        if not rows:
            raise ValueError("لا يوجد سجل قديم للاستيراد")
        result = insert_registry(rows, storage.DATA_DIR / "المجندون" / "ملفات",
                                 (year, month), preserve_ids=True)
    elif kind == "letterhead":
        if any(lh.get_all(year, month).values()) and not replace:
            raise ValueError("الشهر له دباجة بالفعل؛ لا تُستبدل دون تأكيد")
        if not letterhead_available():
            raise ValueError("لا توجد دباجة قديمة")
        result = copy_letterhead({key: db.get_setting(key) for key in lh.KEYS},
                                  storage.DATA_DIR / "الدباجة", (year, month))
    else:
        raise ValueError("نوع استيراد غير صالح")
    conn = months.get_db(year, month)
    try:
        with conn:
            conn.execute("INSERT INTO migration_log VALUES (?, datetime('now'))", (kind,))
    finally:
        conn.close()
    return result
