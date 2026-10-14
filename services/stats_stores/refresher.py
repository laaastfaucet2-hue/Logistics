# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تحديث ملفات إحصائيات المخازن في الخلفية — تجميع الحفظات ومنع تحديثين معًا.

* schedule(): بعد كل حفظ ناجح (نقطة واحدة في app.py) — الحفظات المتتالية تتجمع في
  تحديث واحد بعد ثانيتين من آخرها، والشاشة لا تنتظره أبدًا.
* عامل خلفي واحد + قفل تشغيل: لا يكتب تحديثان الملفات نفسها في وقت واحد.
* run_year(): كل شهور السنة (المتغير فقط ببصماته) + ملفات السنة + السنة التالية
  (مقارنتها بالسنة دي) — ومرايا قسم المخازن نفسه بعد إذون ١ و٢ مخازن (قرار ٦).
* التحديث اليومي: أول يوم جديد يُحدَّث ملفات الشهر الجاري (الأيام الباقية والتغطية).
* في الاختبارات: background=False يسجل الطلب فقط و flush() ينفذه بنتائج ثابتة.
"""
import logging
import threading
import time

from core import egtime

DEBOUNCE_SECONDS = 2.0
DAILY_CHECK_SECONDS = 600

_LOCK = threading.Lock()
_RUN_LOCK = threading.RLock()
_PENDING = {}
_RUNNING = set()
_STATE = {"due": 0.0, "worker": None, "ticker": None}


def _job(year):
    return _PENDING.setdefault(int(year), {"months": set(), "stores": set(), "create": set(),
                                           "create_year": False})


def schedule(year, month=None, stores=False, create=False, delay=DEBOUNCE_SECONDS,
             background=True):
    """يطلب تحديث ملفات السنة (والشهر المذكور) — يتجمع مع الطلبات القريبة."""
    with _LOCK:
        job = _job(year)
        if month:
            job["months"].add(int(month))
            if stores:
                job["stores"].add(int(month))
            if create:
                job["create"].add(int(month))
        if create:
            job["create_year"] = True
        _STATE["due"] = max(_STATE["due"], time.monotonic() + max(delay, 0))
    if background:
        _ensure_worker()
        start_daily()


def busy(year):
    with _LOCK:
        return int(year) in _PENDING or int(year) in _RUNNING


def locked():
    """قفل التشغيل نفسه — للكتابة اليدوية (فتح/تنزيل/تحديث تبويب) أثناء عمل الخلفية."""
    return _RUN_LOCK


def reset():
    """تفريغ الطلبات المعلقة (الاختبارات)."""
    with _LOCK:
        _PENDING.clear()
        _STATE["due"] = 0.0


def _ensure_worker():
    with _LOCK:
        worker = _STATE["worker"]
        if worker is not None and worker.is_alive():
            return
        worker = threading.Thread(target=_loop, daemon=True, name="stats-stores-refresh")
        _STATE["worker"] = worker
    worker.start()


def _loop():
    while True:
        with _LOCK:
            if not _PENDING:
                _STATE["worker"] = None
                return
            wait = _STATE["due"] - time.monotonic()
        if wait > 0:
            time.sleep(min(wait, 0.5))
            continue
        flush()


def flush():
    """ينفذ كل الطلبات المعلقة الآن (متزامن)."""
    with _LOCK:
        jobs = {year: job for year, job in _PENDING.items()}
        _PENDING.clear()
        _RUNNING.update(jobs)
    try:
        for year in sorted(jobs):
            job = jobs[year]
            try:
                run_year(year, stores=job["stores"], create=job["create"],
                         create_year=job["create_year"])
            except Exception:  # noqa: BLE001 — فشل التحديث لا يوقف العامل
                logging.exception("stats stores refresh failed for %s", year)
    finally:
        with _LOCK:
            _RUNNING.difference_update(jobs)


def run_year(year, stores=(), create=(), create_year=False, today=None):
    """تحديث كامل لسنة: مرايا المخازن للشهور المطلوبة + ١٢ شهرًا + ملفات السنة (+ التالية)."""
    from data_access import storage
    from . import files
    year = int(year)
    with _RUN_LOCK:
        if year not in storage.list_years():
            return 0
        for month in sorted(stores or ()):
            try:
                from services import stores_fs
                stores_fs.snapshot(year, month)
            except Exception:  # noqa: BLE001
                logging.exception("stores section snapshot failed")
        written = 0
        for month in range(1, 13):
            written += files.write_scope(year, month, create=month in (create or ()),
                                         today=today)
        written += files.write_scope(year, None, create=create_year, today=today)
        if (year + 1) in storage.list_years():
            for month in range(1, 13):
                written += files.write_scope(year + 1, month, today=today)
            written += files.write_scope(year + 1, None, today=today)
        return written


def ensure_fresh(year, month, background=True, today=None):
    """فحص سريع عند فتح التبويب: لو فيه تغيير لم يُكتب — يُحدَّث (الخلفية أو فورًا)."""
    from . import files
    if files.is_fresh(year, month, today) and files.is_fresh(year, None, today):
        return False
    if background:
        schedule(year, month, create=True, delay=0)
        return True
    run_year(year, create={int(month)}, create_year=True, today=today)
    return False


def start_daily():
    """مؤقت يومي واحد: أول ما يبدأ يوم جديد يُطلب تحديث ملفات الشهر الجاري."""
    with _LOCK:
        ticker = _STATE["ticker"]
        if ticker is not None and ticker.is_alive():
            return
        ticker = threading.Thread(target=_daily_loop, daemon=True, name="stats-stores-daily")
        _STATE["ticker"] = ticker
    ticker.start()


def _daily_loop():
    last = egtime.today()
    while True:
        time.sleep(DAILY_CHECK_SECONDS)
        today = egtime.today()
        if today == last:
            continue
        last = today
        try:
            from data_access import storage
            if today.year in storage.list_years():
                schedule(today.year, today.month, delay=0)
        except Exception:  # noqa: BLE001
            logging.exception("stats stores daily refresh failed")
