# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""محرّك حساب التفاريد الحرة وتفاريد الدول (توجيه ٠٦/١٠/٢٠٢٦) — حساب فقط، بلا تخزين.

المعادلة المُلزمة من المستخدم: **الكمية = المعدل اليومي للفرد × القوة × أيام الصرف المفعّلة**
مع تحويل الوحدات (جرام ⇄ كجم ⇄ علبة… إلخ) وثلاث خانات عشرية بأرقام عربية،
وسطر «المحسوب للغذاء» لكل صنف بالوحدة الأصلية وبالوحدة المخزنية.
هذا الملف لا يقرأ ولا يكتب أي بيانات — يُمرَّر إليه كل شيء جاهزًا (نقيّ وقابل للاختبار).
"""
from core import arabic_numbers as arnum

# تحويلات الوحدة القاعدية (١ كجم = ١٠٠٠ جم) — بلا مساس بوحدات المخازن
BASE_FACTOR = {"كجم": 1000.0, "جم": 1.0}


def to_base(qty, unit):
    """يحوّل الكمية إلى الوحدة القاعدية (جم) لو الوحدة قياسية، وإلا يرجعها كما هي."""
    factor = BASE_FACTOR.get((unit or "").strip())
    return float(qty or 0) * factor if factor else float(qty or 0)


def to_display(qty, unit):
    """يعرض الكمية بوحدتها: جم الكبيرة تُعرض كجم (١٢٠٠ جم ⇒ ١٫٢٠٠ كجم)."""
    unit = (unit or "").strip()
    if unit == "جم" and abs(float(qty or 0)) >= 1000:
        return round(float(qty or 0) / 1000.0, 3), "كجم"
    return round(float(qty or 0), 3), unit


def row_total(rate, force, days):
    """إجمالي الصنف = المعدل × القوة × أيام الصرف."""
    return round(float(rate or 0) * float(force or 0) * int(days or 0), 3)


def search_days(rate, period_days):
    """أيام الصرف الفعلية للصنف = أيامه المفعّلة الواقعة داخل المدة المختارة.

    هذا هو مصدر «عدد الأيام» في كل الحسابات: لو حدّد المستخدم أيامًا للصنف في تاب
    «معدلات الأصناف» فتُحسب الأيام الواقعة داخل المدة فقط، ولو لم يحدّد فكل المدة.
    مثال: صنف مفعّل أيام ١–١٠ والمدة المختارة ٣ أيام ⇒ ٣ أيام (لا ١٠).
    """
    period = max(0, int(period_days or 0))
    flags = [int(d) for d in (rate.get("days") or []) if str(d).strip().isdigit()]
    flags = [d for d in flags if d > 0]
    if flags:
        return len([d for d in flags if d <= period])
    count = int(rate.get("days_count") or 0)
    if count:
        return min(count, period) if period else count
    return period


def build_rows(rates, force, days, day_flags=None):
    """صفوف التفريدة: لكل صنف مفعّل — المعدل والوحدة والأيام والإجمالي (أصليًّا ومخزنيًّا).

    الصنف المفعّل في أيام كلها خارج المدة المختارة لا يُدرج في الكشف (لا يُصرف أصلًا).
    """
    out = []
    for rate in rates or []:
        if not rate.get("active", True):
            continue
        enabled = search_days(rate, days)
        if rate.get("days") and enabled <= 0:
            continue
        total = row_total(rate.get("rate"), force, enabled)
        shown, unit = to_display(total, rate.get("unit"))
        out.append({
            "serial": len(out) + 1,
            "name": rate.get("name") or "",
            "unit": rate.get("unit") or "",
            "rate": round(float(rate.get("rate") or 0), 3),
            "days": enabled,
            "total": total,
            "shown": shown,
            "shown_unit": unit,
            "base_total": to_base(total, rate.get("unit")),
            "kind": rate.get("kind") or "tamween",
            "day_flags": list(day_flags.get(rate.get("name"), [])) if day_flags else [],
        })
    return out


def days_count_map(rates, days):
    """{الصنف: عدد أيام الصرف داخل المدة المختارة} — نفس منطق `search_days`."""
    out = {}
    for rate in rates or []:
        out[rate.get("name")] = search_days(rate, days)
    return out


def line_summary(lines, force_by_line=None):
    """ملخص الخطوط: لكل خط عدد نقاطه وإجمالي قوته وعدد نقاطه النشطة (بطاقة الخط)."""
    out = []
    for line in lines or []:
        points = line.get("points_list") or []
        total = (force_by_line or {}).get(line["id"])
        if total is None:
            total = sum(int(p.get("force") or 0) for p in points)
        out.append({
            "id": line["id"], "name": line["name"],
            "points": len(points), "force": int(total),
            "active": len([p for p in points if p.get("active")]),
            "points_list": points,
        })
    return out


def distribution_rows(lines, rates, days):
    """بيان التوزيع: صف لكل نقطة (قوتها + إجمالي كل صنف لها) + الإجمالي العام."""
    rows = []
    for line in lines or []:
        for point in line.get("points_list") or []:
            if not point.get("active"):
                continue
            force = int(point.get("force") or 0)
            cells = []
            for rate in rates or []:
                if not rate.get("active", True):
                    continue
                enabled = search_days(rate, days)
                cells.append({
                    "name": rate["name"], "unit": rate.get("unit") or "",
                    "total": row_total(rate.get("rate"), force, enabled),
                })
            rows.append({"line": line["name"], "point": point["name"],
                         "force": force, "cells": cells})
    return rows


def totals_by_item(rows):
    """إجمالي كل صنف على كل الصفوف — لصف «إجمالي القطاعات والخطوط العامة»."""
    out = {}
    for row in rows or []:
        for cell in row.get("cells") or []:
            entry = out.setdefault(cell["name"], {"name": cell["name"],
                                                  "unit": cell["unit"], "total": 0.0})
            entry["total"] = round(entry["total"] + float(cell["total"] or 0), 3)
    return list(out.values())


def fmt(qty):
    """رقم بثلاث خانات عشرية عربية (بلا أصفار زائدة) — مصدر واحد للعرض."""
    return arnum.fmt_qty_trim(qty)
