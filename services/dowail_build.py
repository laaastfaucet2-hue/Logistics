# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""بناء أوراق تفاريد الدولى وإجماليات خطوط التوزيع.

القانون: الحصيلة = معدل الفرد اليومى × القوة × أيام الصرف.
- ورقة النقطة: المعدل = معدل الفرد اليومى، القوة = قوة النقطة.
- ورقة الخط المجمعة: المعدل = معدل الفرد × قوة الخط (الإجمالي)، الحصيلة على نفس القانون.
"""
from data_access import db_dowail as dw

SECTIONS = ("tamween", "contractor")
SECTION_TITLES = {"tamween": "المقررات التموينية", "contractor": "مقررات المتعهد"}


def active_rates(year, month):
    """أصناف الدولى المفعّلة مرتبة (تموينية ثم متعهد)."""
    rates = dw.list_rates(year, month)
    return [r for r in rates if r.get("enabled")]


def _item_row(rate, force, days):
    rate_val = float(rate.get("rate") or 0)
    return {
        "name": rate["name"], "unit": rate.get("unit") or "",
        "rate": rate_val,
        "production_year": rate.get("production_year") or "",
        "days": int(days or 0),
        "total": round(rate_val * int(force or 0) * int(days or 0), 6),
    }


def papers(year, month, day_from, day_to, issue_days):
    """كل أوراق الخطوط: {lines: [{line, points_papers, line_paper, active_count}]}."""
    rates = active_rates(year, month)
    out = []
    for line in dw.list_lines(year, month):
        points_papers = []
        line_force = line["total_force"]
        for p in line["points"]:
            points_papers.append({
                "point": p,
                "rows": [_item_row(r, p["force"], issue_days) for r in rates],
            })
        line_paper_rows = []
        for r in rates:
            row = _item_row(r, line_force, issue_days)
            row["rate"] = round(float(r.get("rate") or 0) * line_force, 6)
            line_paper_rows.append(row)
        out.append({
            "line": line,
            "points_papers": points_papers,
            "active_count": line["active"],
            "line_paper": {"rows": line_paper_rows},
        })
    return out


def totals_matrix(year, month, day_from, day_to, issue_days):
    """مصفوفة (خطوط × نقاط × أصناف) + إجماليات الخطوط + الإجمالي العام."""
    rates = active_rates(year, month)
    lines = []
    items_total = {r["name"]: 0.0 for r in rates}
    line_totals = {}
    for line in dw.list_lines(year, month):
        line_key = line["id"]
        line_totals[line_key] = {r["name"]: 0.0 for r in rates}
        pts = []
        for p in line["points"]:
            cells = {}
            for r in rates:
                qty = round(float(r.get("rate") or 0) * int(p["force"] or 0)
                            * int(issue_days or 0), 6)
                cells[r["name"]] = qty
                line_totals[line_key][r["name"]] += qty
                items_total[r["name"]] += qty
            pts.append({"point": p, "cells": cells})
        lines.append({"line": line, "points": pts,
                      "line_total": line_totals[line_key],
                      "force": line["total_force"]})
    return {
        "rates": rates,
        "lines": lines,
        "items_total": items_total,
        "grand_force": sum(l["line"]["total_force"] for l in lines),
    }


def snapshot(year, month, day_from, day_to, issue_days, store_keeper, scribe):
    """لقطة كاملة للحفظ على القرص."""
    data = {
        "label": f"{int(day_from)}-{int(day_to)}",
        "date_from": int(day_from), "date_to": int(day_to),
        "issue_days": int(issue_days),
        "store_keeper": store_keeper or "", "scribe": scribe or "",
        "papers": papers(year, month, day_from, day_to, issue_days),
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
