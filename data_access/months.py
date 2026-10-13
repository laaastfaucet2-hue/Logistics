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
    meal TEXT,                      -- ١٤/١٠: breakfast/lunch/dinner؛ NULL = صف إرثي (مجموع اليوم)
    qty REAL                        -- مقرر هذا اليوم (والوجبة لو meal)؛ الفارغ = القيمة العامة
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
        if cols and "meal" not in cols:
            # ١٤/١٠: تخصيص اليوم بوجباته الثلاث (فطار/غداء/عشاء)
            conn.execute("ALTER TABLE entity_item_days ADD COLUMN meal TEXT")
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


# ======================================================================
# كاش قراءة لقاعدة الشهر (تصحيح ١٤/١٠ لبطء فتح المستودعات وحفظ الأذون):
# الدوال القرائة كانت بتتكرر مئات المرات في نفس الصفحة/الحفظ (N+1:
# list_items → item_balances → issue_rows → fefo_actual_map + permits_book).
# القيمة تبقى صالحة لحد أي كتابة في قاعدة الشهر (تغيير المارك تايم
# للملف الرئيسي أو الـ WAL) — أي حفظ في أي قسم يطفش الكاش تلقائيًا.
# ======================================================================
import copy as _copy
import functools as _functools
import threading as _threading

_read_cache = {}
_read_cache_lock = _threading.Lock()
_CACHE_MAX = 512


def db_signature(year, month):
    """بصمة حالة قاعدة الشهر (الملف الرئيسي + WAL + SHM)."""
    p = month_db_path(year, month)
    sig = 0
    for name in ("", "-wal", "-shm"):
        try:
            sig = sig * 1000003 + p.with_name(p.name + name).stat().st_mtime_ns
        except OSError:
            pass
    return sig


def memo(fn):
    """يخزّن نتيجة دالة قراءة نقية (year, month, ...) لحد تعديل قاعدة الشهر.

    القيمة المحفوظة مش بتتسلّم أبدًا — كل استدعاء بيرجع نسخة عميقة، فأي
    تعديل على النتيجة من أي مستدعي لا يلوّث الكاش.
    """
    @_functools.wraps(fn)
    def wrap(*args, **kwargs):
        year, month = int(args[0]), int(args[1])
        key = (fn.__name__, args, tuple(sorted(kwargs.items())),
               db_signature(year, month))
        with _read_cache_lock:
            hit = _read_cache.get(key)
        if hit is not None:
            return _copy.deepcopy(hit)
        val = fn(*args, **kwargs)
        with _read_cache_lock:
            if len(_read_cache) >= _CACHE_MAX:
                _read_cache.clear()
            _read_cache[key] = val
        return _copy.deepcopy(val)   # حتى أول استدعاء: المحفوظ لا يُسلَّم أبدًا
    return wrap


def bust_cache():
    """يطفّش كاش القراءة (يُستدعى بعد أي عملية كتابة شاذة أو بذر)."""
    with _read_cache_lock:
        _read_cache.clear()
