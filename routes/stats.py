# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""التاب الرئيسي ٠٩ — الإحصائيات والتتبع: ٣ دورات متفصلة × نطاق شهر/سنة × ٤ فلاتر ذكية."""
from flask import Blueprint, render_template, request, g

from core import egtime, dates
from core.config import MONTH_NAMES
from core.auth_core import login_required, current_context
from services import stats_master as sm

stats_bp = Blueprint("stats", __name__, url_prefix="/stats")


def _cycle_params():
    """باراميترات الدورة والنطاق والفلاتر والتاب الفرعي — والسياق (سنة/شهر) بقواعد البرنامج."""
    cycle = request.args.get("cycle", "supply")
    if cycle not in sm.CYCLE_KEYS:
        cycle = "supply"
    scope = request.args.get("scope", "month")
    if scope not in ("month", "year"):
        scope = "month"
    tab = request.args.get("tab", "track")
    if tab not in tuple(k for k, _i, _n in sm.section_defs(cycle)):
        tab = "track"
    # year/month من الأرك أو من سياق المستخدم — نفس سلوك بقية الأقسام
    year, month = current_context(g.user["id"])
    filters = {
        "item": request.args.get("f_item", ""),
        "supplier": request.args.get("f_supplier", ""),
        "producer": request.args.get("f_producer", ""),
        "entity": request.args.get("f_entity", ""),
    }
    return cycle, scope, tab, year, month, filters


def _exp_badge(exp_iso):
    """شارة صلاحية ذكية: 🟢 سليم / 🟠 قرب / 🔴 خطر — بالأيام المتبقية."""
    if not exp_iso:
        return "", 0
    try:
        from core import dates
        d = dates.parse_date(exp_iso)
        if not d:
            return "", 0
        delta = (d - egtime.today()).days
    except Exception:  # noqa: BLE001
        return "", 0
    if delta < 0:
        return "bad", delta
    if delta <= 30:
        return "bad", delta
    if delta <= 90:
        return "warn", delta
    return "ok", delta


def _build(cycle, scope, tab, year, month, filters):
    """كل بيانات الصفحة (توريد/صرف/متوسط + تاب القسم المختار) بعد الفلترة + الملخص."""
    supply = sm.supply_rows(year, month, cycle, scope)
    issue = sm.issue_rows(year, month, cycle, scope)
    avg = sm.avg_rows(year, month, cycle, scope)
    for r in supply:
        r["exp_badge"], r["exp_days"] = _exp_badge(r.get("exp_date") or "")
    for r in issue:
        r["exp_badge"], r["exp_days"] = _exp_badge(r.get("expiry") or "")
    supply_f, issue_f, avg_f = sm.apply_filters(supply, issue, avg, filters)
    meta = dict((c[0], (c[1], c[2])) for c in sm.CYCLES)[cycle]
    defs = sm.section_defs(cycle)
    tab_name = next((n for k, _i, n in defs if k == tab), "التتبع")
    return {
        "cycle": cycle, "cycle_name": meta[0], "cycle_icon": meta[1],
        "cycles": sm.CYCLES,
        "stabs": sm.section_defs(cycle), "st_tab": tab, "st_tab_name": tab_name,
        "section": (sm.section_detail(cycle, year, month, tab)
                    if tab != "track" else None),
        "scope": scope, "year": year, "month": month,
        "month_name": MONTH_NAMES[month - 1],
        "year_months": sm.months_of_year(year),
        "options": sm.options(year, month, cycle, scope),
        "filters": filters,
        "supply": supply_f, "issue": issue_f, "avg": avg_f,
        "summary": sm.summary(supply_f, issue_f, avg_f),
        "prev_ratio": (sm.issue_ratio_prev(year, month, cycle) if scope == "month"
                       else sm.year_ratio_prev(year, cycle)),
        "prev_label": ("مقارنة بالشهر اللي فات" if scope == "month"
                       else "مقارنة بالسنة اللي فاتت"),
        "days": egtime.days_in_month(year, month),
        "any_filter": any((v or "").strip() for v in filters.values()),
        "has_data": bool(supply_f or issue_f or avg_f),
    }


@stats_bp.route("/")
@login_required
def page():
    cycle, scope, tab, year, month, filters = _cycle_params()
    ctx = _build(cycle, scope, tab, year, month, filters)
    return render_template("stats_master.html", **ctx)


@stats_bp.route("/print")
@login_required
def print_view():
    cycle, scope, tab, year, month, filters = _cycle_params()
    ctx = _build(cycle, scope, tab, year, month, filters)
    ctx["print_period"] = (
        "{} {}".format(ctx["month_name"], year)
        if scope == "month" else "سنة {}".format(year))
    ctx["now_stamp"] = dates.format_datetime(egtime.now())
    return render_template("stats_print.html", **ctx)
