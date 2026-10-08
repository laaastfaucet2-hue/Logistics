# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""بناء تفاريد خط الحدود الدولى: أوراق التوزيع + إجماليات خطوط التوزيع.

القانون (قاعدة ٢٧):
- الحصيلة = معدل الفرد اليومى × القوة × أيام الصرف + المخصص × القوة في أيامه.
- أيام الصرف = أول «أيام الصرف» أيام من بداية الفترة (نفس قانون الحرة وأذون ٢ مخازن).
- نقطة: القوة = قوة النقطة.
- خط (مجمع): المعدل = معدل الفرد × قوة الخط، الحصيلة على نفس القانون.
"""
from datetime import date

from core import egtime
from data_access import db_dowail as dw
from data_access import db_rations as dr


def _norm(name):
    return " ".join((name or "").split())


def _custom_map(year, month):
    """{(القسم، اسم الصنف): [أدخال المخصص]} — من مقررات التموين/المتعهد المشتركة."""
    out = {}
    for section in ("tamween", "contractor"):
        kind = dr.get_activation(year, month, section) or "summer"
        rows, custom = dr.get_items(year, month, section, kind)
        for item in rows:
            name = _norm(item.get("name"))
            if name and item.get("id") in custom:
                out[(section, name)] = custom[item["id"]]
    return out


def rates_with_custom(year, month):
    """كل معدلات الدولى (المفعّلة والمعطّلة) — مع مخصص أيام كل صنف."""
    cmap = _custom_map(year, month)
    out = []
    for r in dw.list_rates(year, month):
        r = dict(r)
        r["custom"] = cmap.get((r.get("section"), _norm(r.get("name"))), [])
        out.append(r)
    return out


def active_rates(year, month):
    """أصناف الدولى المفعّلة (تموينية ثم متعهد) — مع مخصصات أيامها."""
    return [r for r in rates_with_custom(year, month) if r.get("enabled")]


def issue_dates(year, month, day_from, day_to, issue_days):
    """تواريخ أيام الصرف = أول «أيام الصرف» أيام من بداية الفترة (list[date])."""
    start = int(day_from)
    end = max(int(day_to), start)
    span = max(1, int(issue_days or 0))
    last = egtime.days_in_month(year, month)
    days = []
    for d in range(start, min(start + span, end + 1)):
        if 1 <= d <= last:
            days.append(date(year, month, d))
    return days


def person_custom(rate, dates):
    """مجموع مخصص الفرد من الصنف عبر أيام الصرف (يُضاف فوق القاعدة)."""
    total = 0.0
    for d in dates:
        wd = egtime.weekday_sat0(d)
        for e in rate.get("custom") or []:
            if int(e.get("weekday", -1)) == wd:
                total += float(e.get("qty") or 0)
    return round(total, 6)


def item_row(rate, force, dates):
    """سطر صنف في ورقة: الحصيلة = المعدل×القوة×الأيام + المخصص×القوة."""
    rate_val = float(rate.get("rate") or 0)
    force = int(force or 0)
    n = len(dates)
    custom_total = round(force * person_custom(rate, dates), 6)
    return {
        "name": rate["name"], "unit": rate.get("unit") or "",
        "rate": rate_val, "days": n,
        "custom_total": custom_total,
        "total": round(rate_val * force * n + custom_total, 6),
    }


def line_papers(year, month, day_from, day_to, issue_days):
    """بيانات كل خط: نقاطه (بكمياتها) + ورقة الخط المجمعة + إجماليات."""
    dates = issue_dates(year, month, day_from, day_to, issue_days)
    rates = active_rates(year, month)
    out = []
    for line in dw.list_lines(year, month):
        points_papers = [{
            "point": p,
            "rows": [item_row(r, p["force"], dates) for r in rates],
        } for p in line["points"]]
        line_paper_rows = []
        for r in rates:
            row = item_row(r, line["total_force"], dates)
            row["rate"] = round(float(r.get("rate") or 0)
                                * int(line["total_force"] or 0), 6)
            line_paper_rows.append(row)
        out.append({
            "line": line,
            "points_papers": points_papers,
            "active_count": line["active"],
            "line_paper": {"rows": line_paper_rows},
        })
    return out


def totals_matrix(year, month, day_from, day_to, issue_days, line_id=None):
    """مصفوفة (خطوط × نقاط × أصناف) + إجماليات الخطوط + الإجمالي العام."""
    dates = issue_dates(year, month, day_from, day_to, issue_days)
    rates = active_rates(year, month)
    n = len(dates)
    pcs = {r["name"]: person_custom(r, dates) for r in rates}
    lines = []
    items_total = {r["name"]: 0.0 for r in rates}
    for line in dw.list_lines(year, month):
        if line_id is not None and line["id"] != line_id:
            continue
        line_totals = {r["name"]: 0.0 for r in rates}
        pts = []
        for p in line["points"]:
            force = int(p["force"] or 0)
            cells = {}
            for r in rates:
                qty = round(float(r.get("rate") or 0) * force * n
                            + force * pcs[r["name"]], 6)
                cells[r["name"]] = qty
                line_totals[r["name"]] += qty
                items_total[r["name"]] += qty
            pts.append({"point": p, "cells": cells})
        lines.append({"line": line, "points": pts,
                      "line_total": line_totals,
                      "force": line["total_force"]})
    return {
        "rates": rates,
        "lines": lines,
        "items_total": items_total,
        "grand_force": sum(l["line"]["total_force"] for l in lines),
    }


def snapshot(year, month, day_from, day_to, issue_days, store_keeper):
    """لقطة كاملة للحفظ على القرص (توزيعة + مصفوفة + معدلات)."""
    dates = issue_dates(year, month, day_from, day_to, issue_days)
    data = {
        "label": f"{int(day_from)}-{int(day_to)}",
        "year": int(year), "month": int(month),
        "date_from": int(day_from), "date_to": int(day_to),
        "issue_days": int(issue_days),
        "dates": [d.day for d in dates],
        "store_keeper": store_keeper or "",
        "rates": active_rates(year, month),
        "papers": line_papers(year, month, day_from, day_to, issue_days),
        "matrix": totals_matrix(year, month, day_from, day_to, issue_days),
    }
    return data


def search_point(year, month, query):
    """بحث سريع عن نقطة بالاسم → (line, point) أو None."""
    q = " ".join((query or "").split())
    if not q:
        return None
    for line in dw.list_lines(year, month):
        for p in line["points"]:
            if q in p["name"] or p["name"] in q:
                return line, p
    return None
