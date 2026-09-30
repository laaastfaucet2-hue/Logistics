# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""التوقيت المصري — «الآن» الحقيقي للبرنامج بتوقيت القاهرة أينما كان السيرفر."""
from calendar import monthrange
from datetime import datetime, date

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Africa/Cairo")
except Exception:                       # noqa: BLE001 — بيئات بلا tzdata
    from datetime import timezone, timedelta
    _TZ = timezone(timedelta(hours=2))  # القاهرة ثابت التقريب كحل أخير


def now():
    """اللحظة الحالية بتوقيت القاهرة."""
    return datetime.now(_TZ)


def from_timestamp(epoch):
    """A file/archive timestamp displayed in Cairo, not the server machine timezone."""
    return datetime.fromtimestamp(epoch, _TZ)


def today():
    return now().date()


def days_in_month(year, month):
    return monthrange(year, month)[1]


def eom(year, month):
    """آخر يوم في الشهر كـ date."""
    return date(year, month, monthrange(year, month)[1])


# أسماء أيام الأسبوع عربي لأي date (الدالة الأصلية weekday: الاثنين=0)
AR_WEEKDAY = {
    5: "السبت", 6: "الأحد", 0: "الاثنين", 1: "الثلاثاء",
    2: "الأربعاء", 3: "الخميس", 4: "الجمعة",
}


def weekday_ar(d):
    return AR_WEEKDAY[d.weekday()]


def weekday_sat0(d):
    """رقم اليوم في قائمة DAYS: السبت=0 … الجمعة=6."""
    return (d.weekday() + 2) % 7


def permit_fiscal_year(d=None):
    """سنة إذن ٢ مخازن: من ١ يوليو إلى ٣٠ يونيو. ١/٧/٢٠٢٦→٢٠٢٦ و٣٠/٦/٢٠٢٧→٢٠٢٦."""
    d = d or today()
    return d.year if d.month >= 7 else d.year - 1


def fmt_ar(d, with_weekday=True):
    """تاريخ يوم/شهر/سنة: ٢٢/٠٩/٢٠٢٦ — الثلاثاء."""
    from core import dates
    parsed = dates.parse_date(d)
    if parsed is None:
        return dates.EMPTY_DATE
    base = dates.format_date(parsed)
    return base + (" — " + weekday_ar(parsed) if with_weekday else "")
