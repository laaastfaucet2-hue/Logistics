# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""حساب تفاريد الدولى بفترات نسخ الخطوط والمعدلات الفعلية والمخصصات."""
from datetime import date

from core import arabic_numbers as arnum
from core import egtime
from core.config import DAYS, MEAL_MAP
from data_access import db_dowail as dw
from data_access import db_rations as dr
from services import free_build as fb


def _norm(name):
    return " ".join((name or "").split())


def catalog_reference(year, month):
    """مرجع المقررات الأصلي حسب (القسم، الاسم)، مع مخصصه الأسبوعي القديم."""
    out = {}
    for section in ("tamween", "contractor"):
        kind = dr.get_activation(year, month, section) or "summer"
        rows, custom = dr.get_items(year, month, section, kind)
        for item in rows:
            name = _norm(item.get("name"))
            if not name:
                continue
            item = dict(item)
            item["custom"] = custom.get(item.get("id"), [])
            out[(section, name)] = {
                "item_id": item.get("id"),
                "name": name,
                "unit": item.get("unit") or "",
                "reference_rate": round(float(fb.seed_rate(item) or 0), 6),
                "weekly": custom.get(item.get("id"), []),
                "item": item,
            }
    return out


def rates_with_custom(year, month):
    """المعدل الفعلي = المرجعي + الإضافة اليدوية، مع مخصص أسبوعي وتاريخي."""
    catalog = catalog_reference(year, month)
    out = []
    for saved in dw.list_rates(year, month):
        rate = dict(saved)
        ref = catalog.get((rate["section"], _norm(rate["name"]))) or {}
        local = dw.get_rate_custom(year, month, rate["id"])
        weekly = (local["weekly"] if local.get("weekly_overridden")
                  else list(ref.get("weekly") or []))
        reference = float(ref.get("reference_rate") or 0)
        manual = float(rate.get("rate") or 0)
        rate.update({
            "item_id": ref.get("item_id"),
            "reference_rate": round(reference, 6),
            "manual_rate": round(manual, 6),
            "effective_rate": round(reference + manual, 6),
            "rate": round(reference + manual, 6),
            "custom": weekly,
            "weekly_custom": weekly,
            "date_custom": local["dates"],
        })
        out.append(rate)
    return out


def active_rates(year, month):
    return [rate for rate in rates_with_custom(year, month) if rate.get("enabled")]


def custom_chips(rate):
    chips = []
    for entry in rate.get("weekly_custom") or rate.get("custom") or []:
        weekday = int(entry.get("weekday") or 0)
        meal = MEAL_MAP.get(entry.get("meal") or "", "")
        chips.append({
            "label": f"{DAYS[weekday]} {meal}".strip(),
            "qty": float(entry.get("qty") or 0), "kind": "weekly",
        })
    for entry in rate.get("date_custom") or []:
        mode = "إضافة" if entry.get("mode") != "replace" else "بديل الأسبوعي"
        meal = MEAL_MAP.get(entry.get("meal") or "", "")
        chips.append({
            "label": f"يوم {entry.get('day')} {meal} — {mode}".strip(),
            "qty": float(entry.get("qty") or 0), "kind": "date",
        })
    return chips


def issue_dates(year, month, day_from, day_to):
    last = egtime.days_in_month(year, month)
    start = max(1, min(int(day_from), last))
    end = max(start, min(int(day_to), last))
    return [date(int(year), int(month), day) for day in range(start, end + 1)]


def _weekly_custom(rate, current):
    """مخصص اليوم الأسبوعي مفصولًا حسب الوجبة."""
    weekday = egtime.weekday_sat0(current)
    result = {}
    for entry in rate.get("weekly_custom") or rate.get("custom") or []:
        if int(entry.get("weekday", -1)) == weekday:
            meal = entry.get("meal") or ""
            result[meal] = result.get(meal, 0.0) + float(entry.get("qty") or 0)
    return result


def _date_custom(rate, current):
    """مخصص التاريخ مفصولًا حسب الوجبة، وكل وجبة لها إضافة/بديل مستقل."""
    result = {}
    for entry in rate.get("date_custom") or []:
        if int(entry.get("day") or 0) == current.day:
            result[entry.get("meal") or ""] = {
                "qty": float(entry.get("qty") or 0),
                "mode": "replace" if entry.get("mode") == "replace" else "add",
            }
    return result


def person_custom(rate, dates):
    """المخصص للفرد: تاريخ الوجبة يضاف لأسبوعيها أو يستبدله وحده."""
    total = 0.0
    for current in dates:
        weekly = _weekly_custom(rate, current)
        actual = _date_custom(rate, current)
        for meal in set(weekly) | set(actual):
            base = weekly.get(meal, 0.0)
            dated = actual.get(meal)
            if dated:
                total += dated["qty"] if dated["mode"] == "replace" else base + dated["qty"]
            else:
                total += base
    return round(total, 6)


def _effective_rate(rate):
    if "effective_rate" in rate:
        return float(rate.get("effective_rate") or 0)
    return float(rate.get("rate") or 0)


def item_row(rate, force, dates):
    effective = _effective_rate(rate)
    reference = float(rate.get("reference_rate") or 0)
    manual = float(rate.get("manual_rate") if "manual_rate" in rate else
                   rate.get("rate") or 0)
    force = int(force or 0)
    custom_total = round(force * person_custom(rate, dates), 6)
    return {
        "name": rate["name"], "unit": rate.get("unit") or "",
        "reference_rate": reference, "manual_rate": manual,
        "rate": effective, "days": len(dates),
        "custom_total": custom_total,
        "total": round(effective * force * len(dates) + custom_total, 6),
    }


def _paper_for_line(line, rates, dates):
    return {
        "line": line,
        "date_from": dates[0].day if dates else None,
        "date_to": dates[-1].day if dates else None,
        "issue_days": len(dates),
        "dates": [current.day for current in dates],
        "points_papers": [{
            "point": point,
            "rows": [item_row(rate, point["force"], dates) for rate in rates],
        } for point in line.get("points") or []],
        "active_count": int(line.get("active") or 0),
        "line_paper": {
            "rows": [item_row(rate, line.get("total_force"), dates) for rate in rates],
        },
    }


def line_papers(year, month, day_from, day_to, lines=None):
    dates = issue_dates(year, month, day_from, day_to)
    rates = active_rates(year, month)
    return [_paper_for_line(line, rates, dates)
            for line in (lines if lines is not None else dw.list_lines(year, month))]


def line_paper(year, month, line, day_from, day_to):
    return _paper_for_line(line, active_rates(year, month),
                           issue_dates(year, month, day_from, day_to))


def _matrix_for_specs(specs, rates, line_id=None):
    lines, items_total = [], {rate["name"]: 0.0 for rate in rates}
    for line, dates in specs:
        if line_id is not None and int(line["id"]) != int(line_id):
            continue
        line_totals = {rate["name"]: 0.0 for rate in rates}
        points = []
        for point in line.get("points") or []:
            cells = {}
            for rate in rates:
                quantity = item_row(rate, point.get("force"), dates)["total"]
                cells[rate["name"]] = quantity
                line_totals[rate["name"]] += quantity
                items_total[rate["name"]] += quantity
            points.append({"point": point, "cells": cells})
        lines.append({
            "line": line, "points": points, "line_total": line_totals,
            "force": int(line.get("total_force") or 0),
            "date_from": dates[0].day if dates else None,
            "date_to": dates[-1].day if dates else None,
            "issue_days": len(dates),
        })
    return {
        "rates": rates, "lines": lines, "items_total": items_total,
        "grand_force": sum(int(item["line"].get("total_force") or 0) for item in lines),
    }


def totals_matrix(year, month, day_from, day_to, line_id=None):
    dates = issue_dates(year, month, day_from, day_to)
    specs = [(line, dates) for line in dw.list_lines(year, month)]
    return _matrix_for_specs(specs, active_rates(year, month), line_id)


def current_period_matrix(year, month, line_id=None):
    specs = []
    for line in dw.list_lines(year, month):
        if line.get("date_from") is None or line.get("date_to") is None:
            continue
        specs.append((line, issue_dates(year, month, line["date_from"], line["date_to"])))
    return _matrix_for_specs(specs, active_rates(year, month), line_id)


def snapshot_for_selections(year, month, selections):
    """لقطة واحدة؛ لكل خط فترة صرف مستقلة داخل فترته الأصلية."""
    rates = active_rates(year, month)
    specs, papers, periods = [], [], []
    for line, day_from, day_to in selections:
        dates = issue_dates(year, month, day_from, day_to)
        specs.append((line, dates))
        papers.append(_paper_for_line(line, rates, dates))
        periods.append({
            "line_id": line["id"], "name": line["name"],
            "date_from": int(day_from), "date_to": int(day_to),
            "issue_days": len(dates),
        })
    starts = [period["date_from"] for period in periods] or [1]
    ends = [period["date_to"] for period in periods] or [1]
    return {
        "label": " · ".join(
            f"{p['name']} {arnum.to_arabic_indic(p['date_from'])}–{arnum.to_arabic_indic(p['date_to'])}"
            for p in periods),
        "year": int(year), "month": int(month),
        "date_from": min(starts), "date_to": max(ends),
        "issue_days": max(ends) - min(starts) + 1,
        "line_periods": periods, "rates": rates, "papers": papers,
        "matrix": _matrix_for_specs(specs, rates),
    }


def snapshot(year, month, day_from, day_to):
    selections = [(line, day_from, day_to) for line in dw.list_lines(year, month)]
    return snapshot_for_selections(year, month, selections)


def _saved_rate(rate):
    rate = dict(rate)
    if "effective_rate" not in rate:
        value = float(rate.get("rate") or 0)
        rate.update(reference_rate=0.0, manual_rate=value, effective_rate=value,
                    weekly_custom=rate.get("custom") or [], date_custom=[])
    rate["rate"] = float(rate.get("effective_rate") or 0)
    return rate


def normalize_snapshot(data):
    """يعيد بناء محفوظ قديم أو جديد دون تعديل الأصل على القرص."""
    if not data:
        return {}
    out = dict(data)
    try:
        year, month = int(out["year"]), int(out["month"])
    except (KeyError, TypeError, ValueError):
        return out
    rates = [_saved_rate(rate) for rate in out.get("rates") or []]
    specs, papers = [], []
    for old in out.get("papers") or []:
        line = old.get("line")
        if not line:
            continue
        day_from = int(old.get("date_from") or out.get("date_from") or 1)
        day_to = int(old.get("date_to") or out.get("date_to") or day_from)
        dates = issue_dates(year, month, day_from, day_to)
        specs.append((line, dates))
        papers.append(_paper_for_line(line, rates, dates))
    out["rates"], out["papers"] = rates, papers
    out["matrix"] = _matrix_for_specs(specs, rates)
    if papers:
        out["date_from"] = min(p["date_from"] for p in papers)
        out["date_to"] = max(p["date_to"] for p in papers)
        out["issue_days"] = out["date_to"] - out["date_from"] + 1
    return out


def search_point(year, month, query, include_archive=False):
    query = _norm(query)
    if not query:
        return None
    lines = dw.list_versions(year, month) if include_archive else dw.list_lines(year, month)
    for line in lines:
        for point in line["points"]:
            if query in point["name"] or point["name"] in query:
                return line, point
    return None
