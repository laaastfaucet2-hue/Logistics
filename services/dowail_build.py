# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""بناء تفاريد خط الحدود الدولى: أوراق التوزيع + إجماليات خطوط التوزيع.

القانون: الحصيلة = معدل الفرد اليومى × القوة × أيام الصرف.
- نقطة: القوة = قوة النقطة.
- خط (مجمع): المعدل = معدل الفرد × قوة الخط، الحصيلة على نفس القانون.
"""
from data_access import db_dowail as dw


def active_rates(year, month):
    """أصناف الدولى المفعّلة (تموينية ثم متعهد)."""
    rates = dw.list_rates(year, month)
    return [r for r in rates if r.get("enabled")]


def _item_row(rate, force, days):
    rate_val = float(rate.get("rate") or 0)
    return {
        "name": rate["name"], "unit": rate.get("unit") or "",
        "rate": rate_val,
        "days": int(days or 0),
        "total": round(rate_val * int(force or 0) * int(days or 0), 6),
    }


def line_papers(year, month, day_from, day_to, issue_days):
    """بيانات كل خط: نقاطه (بكمياتها) + ورقة الخط المجمعة + إجماليات."""
    rates = active_rates(year, month)
    out = []
    for line in dw.list_lines(year, month):
        points_papers = [{
            "point": p,
            "rows": [_item_row(r, p["force"], issue_days) for r in rates],
        } for p in line["points"]]
        line_paper_rows = []
        for r in rates:
            row = _item_row(r, line["total_force"], issue_days)
            row["rate"] = round(float(r.get("rate") or 0) * line["total_force"], 6)
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
    rates = active_rates(year, month)
    lines = []
    items_total = {r["name"]: 0.0 for r in rates}
    for line in dw.list_lines(year, month):
        if line_id is not None and line["id"] != line_id:
            continue
        line_totals = {r["name"]: 0.0 for r in rates}
        pts = []
        for p in line["points"]:
            cells = {}
            for r in rates:
                qty = round(float(r.get("rate") or 0) * int(p["force"] or 0)
                            * int(issue_days or 0), 6)
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
    data = {
        "label": f"{int(day_from)}-{int(day_to)}",
        "date_from": int(day_from), "date_to": int(day_to),
        "issue_days": int(issue_days),
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
