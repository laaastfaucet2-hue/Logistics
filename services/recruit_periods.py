# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مدة حالة المجند «من/إلى» في اليومية العامة + مربعات الأيام في تابات المجندين (توجيه ١٥/١٠).

- «من» = بداية الحالة: المحفوظة مع السطر، أو المشتقة من الأيام المتتالية بنفس الحالة.
- «إلى» اختيارية: لو اتكتبت، الحالة تتسجل على كل الأيام لحدها (بقص آخر الشهر — كل
  شهر منعزل)؛ ولو فاضية = مفتوحة وتترحّل يوم بيوم لحد ما تتغيّر.
- التابات: اليوم المفتوح في المربعات، أو «الشهر كله».
"""
from datetime import date

from core import arabic_numbers as arnum, dates, egtime
from data_access import db_attendance as da

ALL_DAYS = "all"


def iso(year, month, day):
    return date(year, month, day).isoformat()


def _day_in_month(year, month, iso_text, eom):
    """رقم اليوم داخل الشهر لتاريخ ISO: ٠ لو قبل الشهر، eom+1 لو بعده."""
    d = date.fromisoformat(iso_text)
    if (d.year, d.month) < (year, month):
        return 0
    if (d.year, d.month) > (year, month):
        return eom + 1
    return d.day


# ==================== قراءة ====================
def parse_period(year, month, day, raw_from, raw_to):
    """(من، إلى) بصيغة ISO لسطر يومية يوم day — «من» الفاضية = يوم اليومية نفسه."""
    cur = iso(year, month, day)
    p_from = dates.to_iso(raw_from) or cur
    p_to = dates.to_iso(raw_to)
    if p_from > cur:
        raise ValueError("«من» بعد يوم اليومية")
    if p_to and p_to < cur:
        raise ValueError("«إلى» قبل يوم اليومية")
    return p_from, p_to


def period_of(year, month, days, day):
    """مدة الحالة اللي المجند عليها يوم day: {from, to} (to فاضية = مفتوحة).

    days = {يوم: {status, p_from, p_to}} لمجند واحد (من da.month_rows)."""
    row = days.get(day)
    if not row:
        return {"from": "", "to": ""}
    st = row["status"]
    start = day
    while (days.get(start - 1) or {}).get("status") == st:
        start -= 1
    end = day
    while (days.get(end + 1) or {}).get("status") == st:
        end += 1
    p_from = row.get("p_from") or iso(year, month, start)
    if row.get("p_to"):
        p_to = row["p_to"]
    elif row.get("p_from"):
        p_to = ""                                              # مفتوحة صراحةً
    else:
        p_to = iso(year, month, end) if end > day else ""      # سطر قديم: من الأيام نفسها
    return {"from": p_from, "to": p_to}


def day_periods(year, month, day, mrows=None):
    """{رقم المجند: {from, to}} لكل من له حالة يوم day."""
    mrows = da.month_rows(year, month) if mrows is None else mrows
    return {rid: period_of(year, month, days, day)
            for rid, days in mrows.items() if day in days}


def run_length(year, month, p_from, day):
    """عدد الأيام من «من» لحد يوم day (شامل) — حتى لو «من» في شهر قبله."""
    try:
        return (date(year, month, day) - date.fromisoformat(p_from)).days + 1
    except (TypeError, ValueError):
        return 0


# ==================== حفظ اليومية بالمدد ====================
def plan_journal(year, month, day, rows, locked):
    """أيام تتكتب/تتمسح حوالين يوم اليومية لكل سطر بمدة.

    rows = [(rid, status, note, p_from, p_to)] · locked = الأيام المثبتة.
    - قبل اليوم (من «من»): الأيام اللي حالتها مختلفة بس (اليوم المثبت ما يتلمسش لو نفس الحالة).
    - بعد اليوم: لحد «إلى» (بقص آخر الشهر). والمكمّل القديم بعد «إلى» الجديدة أو لو
      الحالة اتغيّرت بيتمسح — عشان الترحيل يكمّل صح.
    يرجع (writes, deletes, clipped) أو ValueError لو يوم مثبت محتاج يتغيّر.
    """
    eom = egtime.days_in_month(year, month)
    mrows = da.month_rows(year, month)
    writes, deletes, clipped = [], [], False

    def guard(d):
        if d in locked:
            raise ValueError("يومية يوم {} مثبتة — افتحها أولًا".format(arnum.to_arabic_indic(d)))

    for rid, st, _note, p_from, p_to in rows:
        days = mrows.get(rid, {})
        old_st = (days.get(day) or {}).get("status")
        start = max(1, _day_in_month(year, month, p_from, eom))
        end = day
        if p_to:
            raw_end = _day_in_month(year, month, p_to, eom)
            clipped = clipped or raw_end > eom
            end = min(eom, raw_end)
        past = [d for d in range(start, day) if (days.get(d) or {}).get("status") != st]
        future = list(range(day + 1, end + 1))
        old_tail = []
        if old_st:
            d = day + 1
            while d <= eom and (days.get(d) or {}).get("status") == old_st:
                old_tail.append(d)
                d += 1
        drop = [d for d in old_tail if d not in future or old_st != st]
        for d in past + drop:
            guard(d)
        for d in future:
            if (days.get(d) or {}).get("status") != st:
                guard(d)
        future = [d for d in future if d not in locked]
        deletes.extend((rid, d) for d in drop if d not in future)
        for seg in _segments(past) + _segments(future):
            writes.append((rid, st, seg[0], seg[-1], p_from, p_to))
    return writes, deletes, clipped


def _segments(days):
    """[٣،٤،٥،٨] ← [[٣،٤،٥]، [٨]] — كل مقطع متصل بيتكتب مرة واحدة."""
    out = []
    for d in sorted(days):
        if out and out[-1][-1] == d - 1:
            out[-1].append(d)
        else:
            out.append([d])
    return out


def apply_plan(year, month, writes, deletes):
    for rid, d in deletes:
        da.delete_recruit_day(year, month, d, rid)
    for rid, st, f, t, p_from, p_to in writes:
        da.set_range(year, month, rid, st, f, t, "", p_from, p_to)


# ==================== تنبيهات ====================
def ended_yesterday(year, month, day, by_id, mrows=None):
    """اللي مدة حالتهم («إلى») خلصت امبارح ومالهمش حالة النهارده: [(الحالة، [أسماء])]."""
    if day <= 1:
        return []
    mrows = da.month_rows(year, month) if mrows is None else mrows
    today = iso(year, month, day)
    groups = {}
    for rid, days in mrows.items():
        prev = days.get(day - 1)
        if rid not in by_id or day in days or not prev:
            continue
        if prev.get("p_to") and prev["p_to"] < today:
            groups.setdefault(prev["status"], []).append(by_id[rid]["name"])
    return [(st, sorted(names)) for st, names in sorted(groups.items())]


def leaving_tomorrow(year, month, day, matrix, by_id, permits=None):
    """حاضرين يوم day وإجازتهم بتبدأ بكرة (مسجلة في اليومية أو بتصريح صادر):
    [{name, rid, permitted}] — تنبيه تاب الحضور «إجازة غدًا — سجّلهم في يومية الغد»."""
    eom = egtime.days_in_month(year, month)
    if day >= eom:
        return []
    permits = da.month_leave_permits(year, month) if permits is None else permits
    out = []
    for rid, days in matrix.items():
        if rid not in by_id or days.get(day) != "حضور":
            continue
        has_permit = any(f == day + 1 for f, _t in permits.get(rid, []))
        if days.get(day + 1) == "إجازة" or has_permit:
            out.append({"rid": rid, "name": by_id[rid]["name"], "permitted": has_permit})
    return sorted(out, key=lambda x: x["name"])


def leave_marks(year, month, matrix, by_id):
    """أيام فيها حد حاضر وإجازته بكرة — نقطة على مربع اليوم في تاب الحضور."""
    eom = egtime.days_in_month(year, month)
    permits = da.month_leave_permits(year, month)
    return {d for d in range(1, eom) if leaving_tomorrow(year, month, d, matrix, by_id, permits)}


# ==================== اليوم المفتوح في التابات ====================
def selected_day(raw, real_day, eom, allow_all=True):
    """اليوم المفتوح من الرابط: رقم، أو ALL_DAYS («الشهر كله»).
    الافتراضي: النهارده لو الشهر الحالي — وإلا الشهر كله (أو يوم ١ لو مفيش «الشهر كله»)."""
    if allow_all and (raw or "").strip() == ALL_DAYS:
        return ALL_DAYS
    day = arnum.parse_int(raw)
    if day and 1 <= day <= eom:
        return day
    if real_day:
        return real_day
    return ALL_DAYS if allow_all else 1


def covers(f, t, day):
    """هل المدة (f..t) — t=None مفتوحة — فيها يوم day؟"""
    return f <= day and (t is None or day <= t)
