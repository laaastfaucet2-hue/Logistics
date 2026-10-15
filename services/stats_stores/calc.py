# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""حسابات وتنسيقات مشتركة لتبويبات إحصائيات المخازن — نص الخلية نفسه للشاشة والإكسل.

* الكمية بـ fmt_qty (ثلاث خانات عربية) والفارغ نص فاضي: «—» على الشاشة وخلية فاضية في الإكسل.
* لا تُجمع كميات وحدات مختلفة أبدًا: الإجمالي منفصل لكل وحدة.
* حالات الصلاحية: منتهية < ٠ · خطر ٠–٣٠ · قربت ٣١–٩٠ · سليمة > ٩٠ · بدون تاريخ.
* التغطية بالأيام = الرصيد ÷ متوسط الصرف اليومي: < ٧ خطر · < ١٤ تحذير.
"""
from datetime import timedelta

from core import arabic_numbers as arnum
from core import dates
from core.config import MONTH_NAMES

EPS = 1e-6
DANGER_DAYS = 30
NEAR_DAYS = 90
COVER_DANGER = 7
COVER_WARN = 14

LEVELS = ("expired", "danger", "near", "ok", "none")
LEVEL_LABEL = {"expired": "منتهية", "danger": "خطر", "near": "قربت", "ok": "سليمة",
               "none": "بدون تاريخ"}
LEVEL_CLASS = {"expired": "bad", "danger": "bad", "near": "warn", "ok": "ok", "none": ""}


# ---------------------------------------------------------------- تنسيق الخلايا
def q(value):
    """كمية بثلاث خانات عربية — والصفر/الفارغ نص فاضي (يظهر «—»)."""
    if value in (None, ""):
        return ""
    value = round(float(value), 6)
    if abs(value) < EPS:
        return ""
    return arnum.fmt_qty(value)


def qz(value):
    """كمية تُكتب حتى لو صفر (أرصدة مقارنة: صفر له معنى)."""
    if value in (None, ""):
        return ""
    return arnum.fmt_qty(round(float(value), 6))


def n(value):
    """عدد صحيح بأرقام عربية — والصفر يُكتب «٠»."""
    return arnum.to_arabic_indic(str(int(value or 0)))


def nz(value):
    """عدد صحيح — والصفر نص فاضي."""
    return n(value) if value else ""


def d(value):
    """تاريخ yyyy/mm/dd بأرقام عربية — والفارغ نص فاضي."""
    return dates.format_date(value, empty="") if value else ""


def month_name(month):
    return MONTH_NAMES[int(month) - 1] if month else ""


def cell(text, cls="", kind=""):
    """خلية جدول: النص نفسه في الشاشة والإكسل + لون/نوع للشاشة فقط."""
    return {"t": text if text is not None else "", "c": cls, "k": kind}


def card(label, value, sub="", cls="", icon=""):
    return {"label": label, "value": value, "sub": sub, "cls": cls, "icon": icon}


def table(key, title, head, rows, foot=None, fold=False, badge="", badge_cls=""):
    """جدول واحد = ورقة واحدة في الإكسل بنفس العنوان والأعمدة والصفوف."""
    return {"key": key, "title": title, "head": list(head), "rows": rows,
            "foot": foot or [], "fold": fold, "badge": badge, "badge_cls": badge_cls,
            "wide": len(head) > 10}


def norm(row):
    """صف خلايا → قائمة خلايا موحدة (نص بسيط يتحول لخلية)."""
    return [c if isinstance(c, dict) else cell(c) for c in row]


# ---------------------------------------------------------------- الوحدات
def add_unit(totals, unit, value):
    unit = unit or ""
    totals[unit] = round(totals.get(unit, 0.0) + float(value or 0), 6)
    return totals


def unit_card(label, totals, icon="", cls="", counts=None):
    """كارت كمية: الوحدة الأكثر أصنافًا (ثم الأكبر) قيمةً رئيسية والباقي تحتها — بلا جمع وحدتين."""
    counts = counts or {}
    order = sorted(totals, key=lambda u: (-counts.get(u, 0), -abs(totals[u]), u))
    parts = [f"{arnum.fmt_qty(round(totals[u], 6))} {u}".strip() for u in order
             if abs(totals[u]) > EPS]
    return card(label, parts[0] if parts else n(0), " · ".join(parts[1:]), cls, icon)


def units_text(totals, zero=False):
    """«١٢٠٫٠٠٠ كجم · ٣٠٫٠٠٠ لتر» — كل وحدة منفصلة، بلا جمع وحدات مختلفة."""
    parts = []
    for unit in sorted(totals):
        value = totals[unit]
        if abs(value) < EPS and not zero:
            continue
        parts.append(f"{arnum.fmt_qty(round(value, 6))} {unit}".strip())
    return " · ".join(parts)


# ---------------------------------------------------------------- الصلاحية
def days_left(expiry, ref):
    parsed = dates.parse_date(expiry) if expiry else None
    if not parsed:
        return None
    return (parsed - ref).days


def level(expiry, ref):
    left = days_left(expiry, ref)
    if left is None:
        return "none"
    if left < 0:
        return "expired"
    if left <= DANGER_DAYS:
        return "danger"
    if left <= NEAR_DAYS:
        return "near"
    return "ok"


def expiry_cell(expiry, ref):
    """تاريخ الصلاحية ملوّن بحالته — النص التاريخ فقط."""
    if not expiry:
        return cell("")
    return cell(d(expiry), LEVEL_CLASS[level(expiry, ref)], "date")


# ---------------------------------------------------------------- التغطية
def coverage_days(balance, issued, elapsed):
    """أيام التغطية = الرصيد ÷ (المنصرف ÷ الأيام المنقضية) — None بلا صرف أو بلا رصيد."""
    balance = float(balance or 0)
    issued = float(issued or 0)
    if balance <= EPS or issued <= EPS or not elapsed:
        return None
    return balance / (issued / float(elapsed))


def cover_class(days):
    if days is None:
        return ""
    if days < COVER_DANGER:
        return "bad"
    if days < COVER_WARN:
        return "warn"
    return "ok"


def runout_date(ref, days):
    """تاريخ النفاد المتوقع = تاريخ المرجع + أيام التغطية."""
    if days is None:
        return ""
    return d((ref + timedelta(days=int(days))).isoformat())


def daily_rate(issued, elapsed):
    if not elapsed:
        return 0.0
    return float(issued or 0) / float(elapsed)


# ---------------------------------------------------------------- المقارنة
def pct_change(current, previous):
    """نسبة التغير «+١٢٪» / «−٥٪» — فاضية بلا فترة سابقة أو أساس صفري."""
    if previous in (None, "") or current in (None, ""):
        return ""
    previous = float(previous)
    if abs(previous) < EPS:
        return ""
    value = (float(current) - previous) / abs(previous) * 100
    text = arnum.to_arabic_indic(f"{abs(value):.0f}") + "٪"
    if round(value) > 0:
        return "+" + text
    if round(value) < 0:
        return "−" + text
    return text


def change_class(current, previous, up_is_bad=False):
    if previous in (None, "") or current in (None, ""):
        return ""
    if abs(float(current) - float(previous)) < EPS:
        return ""
    up = float(current) > float(previous)
    return ("bad" if up else "ok") if up_is_bad else ("ok" if up else "warn")
