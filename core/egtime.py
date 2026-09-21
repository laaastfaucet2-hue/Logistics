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


def fmt_ar(d, with_weekday=True):
    """٢٠٢٦ / ٩ / ٢١ — السبت (أرقام عربية-هندية)."""
    from core import arabic_numbers as arnum
    base = arnum.to_arabic_indic(d.strftime("%Y / %m / %d"))
    return (base + (" — " + weekday_ar(d) if with_weekday else ""))
