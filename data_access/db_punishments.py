# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""السجن والمحكمات والجزاءات — مدد مشتقة من اليومية العامة (توجيه ١٠/١٠).

التسجيل مش من تاب السجن — بيتسجل بحالة المجند في اليومية (سجن/محكمة/جزاء):
- مدة أي نوع = الأيام اللي حالة المجند عليها.
- لو الحالة اتغيرت لحالة تانية بعد المدة → المدة **مقفولة** (إلى = آخر يوم عليها).
- لو الأيام اللي بعد آخر يوم فاضية (معرفش أوقفتها فين) → المدة **مفتوحة** (إلى = None).

مفيش جدول تخزيني — كل حاجة بتتشتق من جدول attendance (مصدر الحقيقة واحد).
"""
from data_access import months

# (مفتاح، اسم التاب الفرعي، الأيقونة، الحالة في اليومية، الاسم الإفرادي للتعبير)
PUNISH_KINDS = [
    ("prison", "السجن", "⛓️", "سجن", "السجن"),
    ("court", "المحكمات", "⚖️", "محكمة", "المحكمة"),
    ("punishment", "الجزاءات", "⚠️", "جزاء", "الجزاء"),
]

KIND_META = {k: dict(kind=k, label=label, icon=icon, status=status, noun=noun)
             for k, label, icon, status, noun in PUNISH_KINDS}
STATUS_BY_KIND = {k: m["status"] for k, m in KIND_META.items()}
KIND_BY_STATUS = {m["status"]: k for k, m in KIND_META.items()}
VALID_KINDS = tuple(KIND_META)


def _month_status_map(year, month):
    """{recruit_id: {day: status}} من اليومية."""
    conn = months.get_db(year, month)
    rows = conn.execute("SELECT recruit_id, day, status FROM attendance").fetchall()
    conn.close()
    by_rid = {}
    for r in rows:
        by_rid.setdefault(r["recruit_id"], {})[int(r["day"])] = r["status"]
    return by_rid


def month_spans(year, month, kind):
    """مدد نوع واحد مشتقة من اليومية:
    [(recruit_id, from_day, to_day_or_None), ...] — to_day=None يعني مفتوحة."""
    meta = KIND_META.get(kind)
    if not meta:
        return []
    st = meta["status"]
    out = []
    for rid, days in sorted(_month_status_map(year, month).items()):
        st_days = sorted(d for d, s in days.items() if s == st)
        if not st_days:
            continue
        run_start = st_days[0]
        for i in range(1, len(st_days)):
            prev_d, cur_d = st_days[i - 1], st_days[i]
            # المدة بتكسر بس لو في يوم **مسجل فعلاً** بحالة تانية جواها
            broken = any(s != st for d2, s in days.items()
                         if prev_d < d2 < cur_d)
            if broken:
                out.append((rid, run_start, _close_end(days, st, st_days[i - 1])))
                run_start = cur_d
        out.append((rid, run_start, _close_end(days, st, st_days[-1])))
    return out


def _close_end(days, st, last):
    """لو يوم محسوب بحالة تانية جاي بعد آخر يوم → مقفولة (آخر يوم) · وإلا مفتوحة (None)."""
    for d, s in days.items():
        if d > last and s != st:
            return last
    return None


def all_spans(year, month, kinds=VALID_KINDS):
    """{(kind, recruit_id): (from_day, to_day_or_None)} لكل الأنواع."""
    out = {}
    for k in kinds:
        for rid, f, t in month_spans(year, month, k):
            out[(k, rid)] = (f, t)
    return out


def span_state(from_day, to_day, real_day):
    """قيد التنفيذ / انتهى / لم يبدأ — حسب اليوم الحقيقي (real_day=0 ⇒ '')."""
    if not real_day:
        return ""
    if to_day is not None and to_day < real_day:
        return "انتهى"
    if from_day > real_day:
        return "لم يبدأ"
    return "قيد التنفيذ"
