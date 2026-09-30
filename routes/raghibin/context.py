# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحة قسم الراغبين + السياق المشترك (سنة/شهر/جهة/فئة/بحث) وجديل الرجوع."""
from flask import g, redirect, render_template, request, url_for
from urllib.parse import quote

from core.auth_core import current_context, current_session, login_required
from core.config import MONTH_NAMES
from data_access import db_raghibin as dr
from data_access import db_tameedat as dt
from services import raghibin as rfs

from . import TABS, TAB_KEYS, raghibin_bp


def _ctx():
    return current_context(g.user["id"])


def _rb(tab="cadres", ok=None, err=None, warn=None, **extra):
    """يرجع لصفحة الراغبين مع الحفاظ على التوكن والتاب والجهة والفئة والبحث."""
    _, token = current_session()
    params = {"tab": tab}
    params.update({k: v for k, v in extra.items() if v})
    if token:
        params["sid"] = token
    for key, label in (("ok", ok), ("err", err), ("warn", warn)):
        if label:
            params[key] = label
    base = url_for("raghibin.page")
    separator = "&" if "?" in base else "?"
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return redirect(base + (separator + query if query else ""))


def _selected_entity(year, month):
    """الجهة المحددة من ?e — الافتراضي أول جهة بالقاموس (أو None لو فاضي)."""
    raw = request.args.get("e", "")
    try:
        entity_id = int(raw)
    except ValueError:
        entity_id = 0
    if entity_id:
        entity = dt.get_entity(year, month, entity_id)
        if entity:
            return entity
    entities = dt.list_entities(year, month)
    return entities[0] if entities else None


def _category():
    valid = {k for k, _ in dr.CATEGORIES}
    return request.args.get("c") if request.args.get("c") in valid else "officers"


def _page_vars(tab):
    year, month = _ctx()
    rfs.ensure_folders(year, month)
    query = (request.args.get("q") or "").strip()
    entity = _selected_entity(year, month)
    category = _category()
    counts = dr.entity_force_counts(year, month)
    entities = dt.list_entities(year, month)
    exclude_id = 0
    try:
        exclude_id = int(request.args.get("x", "0") or 0)
    except ValueError:
        exclude_id = 0
    persons = []
    if entity:
        persons = dr.list_persons(year, month, entity_id=entity["id"],
                                  category=category, query=query)
    return {
        "tabs": TABS, "tab": tab,
        "year": year, "month": month, "month_name": MONTH_NAMES[month - 1],
        "q": query, "fcat": category,
        "categories": dr.CATEGORIES,
        "entities": entities,
        "entity": entity,
        "counts": counts,
        "persons": persons,
        "exclude_person": dr.get_person(year, month, exclude_id) if exclude_id else None,
        "section_folder": rfs.base_dir(year, month),
        "total_force": sum(c["officers"] + c["individuals"] for c in counts.values()),
    }


@raghibin_bp.route("")
@raghibin_bp.route("/")
@login_required
def page():
    tab = request.args.get("tab", "daily")
    if tab not in TAB_KEYS:
        tab = "daily"
    return render_template("raghibin/main.html", **_page_vars(tab))
