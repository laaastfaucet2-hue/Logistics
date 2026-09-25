"""Day-first Gregorian dates for presentation; ISO stays the storage/wire format.

All digit conversion belongs to arabic_numbers. Never infer a US month-first date.
"""
import re
from datetime import date, datetime
from core import arabic_numbers as arnum

DISPLAY_FORMAT = "dd/mm/yyyy"
FORMAT_LABEL = "يوم/شهر/سنة"
EMPTY_DATE = "—"
_DATE_ISO = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")
_DATE_DMY = re.compile(r"^([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})$")
_BIDI_MARKS = dict.fromkeys(map(ord, "\u061c\u200e\u200f\u2066\u2067\u2068\u2069"))


def parse_date(value):
    """A date object, strict ISO, or day/month/year (Arabic/Latin/Persian digits).

    Blank -> None. Invalid or month-first-only input -> ValueError, never a swap.
    Eight digits on a numeric keyboard are read as ddmmyyyy, not yyyymmdd.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = arnum.to_western(value).translate(_BIDI_MARKS).strip()
    if not text:
        return None
    iso = _DATE_ISO.fullmatch(text)
    dmy = _DATE_DMY.fullmatch(text)
    if iso:
        year, month, day = map(int, iso.groups())
    elif dmy:
        day, month, year = map(int, dmy.groups())
    elif re.fullmatch(r"[0-9]{8}", text):
        day, month, year = int(text[:2]), int(text[2:4]), int(text[4:])
    else:
        raise ValueError("اكتب التاريخ بالترتيب يوم/شهر/سنة، مثال: ٢٢/٠٩/٢٠٢٦")
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise ValueError("التاريخ غير صالح؛ راجع اليوم والشهر والسنة") from exc


def to_iso(value):
    """Validate once at the input boundary; keep existing date storage sortable."""
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else ""


def format_date(value, empty=EMPTY_DATE, arabic=True):
    """Display only: zero-padded dd/mm/yyyy, independent of OS/browser locale."""
    try:
        parsed = parse_date(value)
    except (ValueError, TypeError):
        return empty
    if not parsed:
        return empty
    text = f"{parsed.day:02d}/{parsed.month:02d}/{parsed.year:04d}"
    return arnum.to_arabic_indic(text) if arabic else text


def input_date(value):
    """A formatted edit value; preserve invalid draft text so it can be corrected."""
    if value is None:
        return ""
    try:
        return format_date(parse_date(value), empty="")
    except (ValueError, TypeError):
        return str(value)


def period_date(year, month, day):
    """Full date for a journal/leave day inside its explicit month context."""
    try:
        return format_date(date(int(year), int(month), int(day)))
    except (TypeError, ValueError):
        return EMPTY_DATE


def format_datetime(value, seconds=False, empty=EMPTY_DATE):
    """Caller supplies a Cairo-aware datetime; date-only records never shift zones."""
    if not isinstance(value, datetime):
        return empty
    clock = f"{value.hour:02d}:{value.minute:02d}"
    if seconds:
        clock += f":{value.second:02d}"
    return format_date(value) + " — " + arnum.to_arabic_indic(clock)


def document_date(value):
    """Keep the date segment day-first within Arabic Word paragraphs."""
    return "\u200e" + format_date(value, empty="") + "\u200e"
