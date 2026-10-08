# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""«تفاريد الدولى» — النقط الحدودية: أوراق وإيصالات الصرف · إجمالي خطوط
التوزيع · إدارة الخطوط والنقاط · تعديل معدلات الأصناف.

معدلات الدولى منفصلة تمامًا عن ٢ مخازن (العادية والحرة) — والحفظ على القرص
يكتب فولدر جوا بيانات الشهر (JSON + Excel).
"""
from pathlib import Path

from flask import (Blueprint, redirect, render_template, request,
                   send_file, url_for)
from core import arabic_numbers as arnum, egtime
from core.auth_core import current_session, login_required
from core.config import MONTH_NAMES
from data_access import db_dowail as dw
from data_access import db_rations as dr
from data_access import months, storage
from services import dowail_build as db
from services import dowail_fs, free_build as fb
from services import permit_build as pb
from routes.calc2 import MEALS, _ctx, _day

dowail_bp = Blueprint("dowail", __name__, url_prefix="/calc2/dowail")

TABS = ("papers", "totals", "lines", "rates")


def _range(year, month):
    last = egtime.days_in_month(year, month)
    f = _day(year, month, request.args.get("from") or request.form.get("date_from"), 1)
    t = _day(year, month, request.args.get("to") or request.form.get("date_to"), last)
    if t < f:
        t = f
    days = arnum.parse_int(request.args.get("days") or request.form.get("issue_days")) \
        or (t - f + 1)
    days = max(1, min(days, t - f + 1))
    return last, f, t, days


def _tab():
    return request.args.get("tab") if request.args.get("tab") in TABS else "papers"


def _base(year, month, last, f, t, days, tab):
    _, token = current_session()
    return {
        "year": year, "month": month, "month_name": MONTH_NAMES[month - 1],
        "days_in_month": last, "day_from": f, "day_to": t, "issue_days": days,
        "tab": tab, "sid": token or "", "cur_tab": "dowail",
        "meals": MEALS,
    }


@dowail_bp.route("")
@dowail_bp.route("/")
@login_required
def page():
    year, month = _ctx()
    months.init_month(year, month)
    last, f, t, days = _range(year, month)
    tab = _tab()
    ctx = _base(year, month, last, f, t, days, tab)
    ctx["lines"] = dw.list_lines(year, month)
    ctx["saves"] = dw.list_saves(year, month)
    ctx["total_active"] = sum(l["active"] for l in ctx["lines"])
    ctx["sel_line_id"] = arnum.parse_int(request.args.get("line"))
    if tab == "papers":
        ctx["papers"] = db.papers(year, month, f, t, days)
        found = db.search_point(year, month, request.args.get("q"))
        ctx["search_q"] = request.args.get("q") or ""
        ctx["search_hit"] = found
    elif tab == "totals":
        ctx["matrix"] = db.totals_matrix(year, month, f, t, days)
    elif tab == "rates":
        ctx["rates_view"] = _rates_view(year, month)
    return render_template(f"dowail/tab_{tab}.html", **ctx)


def _rates_view(year, month):
    """أصناف الدولى: المقررات (تموين/متعهد) + الإضافات — بالمعدلات والمفعّل."""
    saved = {(r["section"], r["name"]): r for r in dw.list_rates(year, month)}
    out = {}
    for section in ("tamween", "contractor"):
        kind = dr.get_activation(year, month, section) or "summer"
        rows, custom = dr.get_items(year, month, section, kind)
        items = []
        for i, item in enumerate(rows):
            name = " ".join((item.get("name") or "").split())
            if not name:
                continue
            item = dict(item)
            item["custom"] = custom.get(item.get("id"), [])
            item["is_custom"] = bool(item["custom"])
            s = saved.get((section, name))
            items.append({
                "serial": i + 1, "name": name, "unit": item.get("unit") or "",
                "base": fb.seed_rate(item),
                "custom": fb.custom_chips(item),
                "rate": float(s["rate"]) if s else 0.0,
                "enabled": int(s["enabled"]) if s else 0,
                "production_year": (s or {}).get("production_year") or "",
                "rate_id": s["id"] if s else None,
                "is_extra": bool(s and s.get("is_extra")),
            })
        for s in dw.list_rates(year, month):
            if s["section"] == section and s.get("is_extra") \
                    and s["name"] not in {it["name"] for it in items}:
                items.append({
                    "serial": len(items) + 1, "name": s["name"],
                    "unit": s.get("unit") or "", "base": 0.0, "custom": [],
                    "rate": float(s["rate"]), "enabled": int(s["enabled"]),
                    "production_year": s.get("production_year") or "",
                    "rate_id": s["id"], "is_extra": True})
        out[section] = items
    return out


# ======================================================================
# إدارة الخطوط والنقاط
# ======================================================================
@dowail_bp.route("/lines", methods=["POST"])
@login_required
def add_line():
    year, month = _ctx()
    dw.add_line(year, month, request.form.get("name"))
    return _back("lines")


@dowail_bp.route("/lines/<int:line_id>/delete", methods=["POST"])
@login_required
def delete_line(line_id):
    year, month = _ctx()
    dw.delete_line(year, month, line_id)
    return _back("lines")


@dowail_bp.route("/points", methods=["POST"])
@login_required
def add_point():
    year, month = _ctx()
    dw.add_point(year, month, arnum.parse_int(request.form.get("line_id")) or 0,
                 request.form.get("name"), request.form.get("force"))
    return _back("lines")


@dowail_bp.route("/points/<int:point_id>/update", methods=["POST"])
@login_required
def update_point(point_id):
    year, month = _ctx()
    force = arnum.parse_int(request.form.get("force"))
    responsible = request.form.get("responsible")
    if request.form.get("responsible_only"):
        dw.update_point(year, month, point_id, responsible=responsible)
    else:
        dw.update_point(year, month, point_id, force=force)
    return _back(request.form.get("from_tab") or "lines")


@dowail_bp.route("/points/<int:point_id>/delete", methods=["POST"])
@login_required
def delete_point(point_id):
    year, month = _ctx()
    dw.delete_point(year, month, point_id)
    return _back("lines")


# ======================================================================
# معدلات الدولى
# ======================================================================
@dowail_bp.route("/rates/add", methods=["POST"])
@login_required
def rates_add():
    year, month = _ctx()
    section = request.form.get("section") if request.form.get("section") \
        in ("tamween", "contractor") else "tamween"
    name = " ".join((request.form.get("name") or "").split())
    if name:
        dw.save_rate(year, month, section, name,
                     arnum.parse_float(request.form.get("rate")) or 0,
                     request.form.get("unit") or "",
                     request.form.get("production_year") or "",
                     is_extra=True)
    return _back("rates")


@dowail_bp.route("/rates/<int:rate_id>/update", methods=["POST"])
@login_required
def rates_update(rate_id):
    year, month = _ctx()
    row = next((r for r in dw.list_rates(year, month) if r["id"] == rate_id), None)
    if row:
        dw.save_rate(year, month, row["section"], row["name"],
                     arnum.parse_float(request.form.get("rate")) or 0,
                     request.form.get("unit") or row.get("unit") or "",
                     request.form.get("production_year") or "",
                     is_extra=bool(row.get("is_extra")))
    return _back("rates")


@dowail_bp.route("/rates/<int:rate_id>/toggle", methods=["POST"])
@login_required
def rates_toggle(rate_id):
    year, month = _ctx()
    dw.toggle_rate(year, month, rate_id)
    return _back("rates")


@dowail_bp.route("/rates/<int:rate_id>/delete", methods=["POST"])
@login_required
def rates_delete(rate_id):
    year, month = _ctx()
    dw.delete_rate(year, month, rate_id)
    return _back("rates")


# ======================================================================
# حفظ / تصفير / السجل
# ======================================================================
@dowail_bp.route("/save", methods=["POST"])
@login_required
def save_tafreeda():
    year, month = _ctx()
    last, f, t, days = _range(year, month)
    data = db.snapshot(year, month, f, t, days,
                       request.form.get("store_keeper"), request.form.get("scribe"))
    rel, _folder = dowail_fs.save_to_disk(year, month, data)
    dw.save_tafreeda(year, month, data, rel)
    return redirect(url_for("dowail.page", tab="papers", ok="اتحفظت التفريدة على القرص"))


@dowail_bp.route("/reset", methods=["POST"])
@login_required
def reset():
    year, month = _ctx()
    last, f, t, days = _range(year, month)
    latest = dw.latest_save_in_range(year, month, f, t)
    if latest:
        import shutil
        folder = dowail_fs.section_dir(year, month).parent
        for rel in (latest.get("files") or []):
            try:
                p = folder / rel
                if p.is_file():
                    p.unlink()
            except OSError:
                pass
        try:
            top = folder / rel_dir_of(latest)
            if top.is_dir():
                shutil.rmtree(top, ignore_errors=True)
        except OSError:
            pass
        dw.delete_save(year, month, latest["id"])
    return redirect(url_for("dowail.page", tab="papers",
                            ok="اتصفّر الحفظ الأخير للفترة — الإحالة من القوى الحالية"))


def rel_dir_of(save):
    files = save.get("files") or []
    return "/".join(files[0].split("/")[:2]) if files else ""


@dowail_bp.route("/saves/<int:save_id>/delete", methods=["POST"])
@login_required
def save_delete(save_id):
    year, month = _ctx()
    save = dw.get_save(year, month, save_id)
    if save:
        import shutil
        base = months.month_db_path(year, month).parent
        try:
            top = base / rel_dir_of(save)
            if top.is_dir() and str(top).startswith(str(base)):
                shutil.rmtree(top, ignore_errors=True)
        except OSError:
            pass
        dw.delete_save(year, month, save_id)
    return _back("papers")


@dowail_bp.route("/file/<int:save_id>/<path:filename>")
@login_required
def save_file(save_id, filename):
    year, month = _ctx()
    save = dw.get_save(year, month, save_id)
    if not save:
        return "الملف مش موجود", 404
    base = months.month_db_path(year, month).parent.resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        return "الملف مش موجود", 404
    return send_file(str(target), as_attachment=True, download_name=target.name)


# ======================================================================
# الأوراق (نقطة / خط) + طباعة النشطة
# ======================================================================
def _paper_ctx(year, month, last, f, t, days):
    ctx = _base(year, month, last, f, t, days, "papers")
    ctx["store_keeper"] = request.args.get("store_keeper") or \
        request.form.get("store_keeper") or ""
    ctx["scribe"] = request.args.get("scribe") or request.form.get("scribe") or ""
    return ctx


@dowail_bp.route("/paper/<int:point_id>")
@login_required
def point_paper(point_id):
    year, month = _ctx()
    last, f, t, days = _range(year, month)
    ctx = _paper_ctx(year, month, last, f, t, days)
    line = None
    point = None
    for l in dw.list_lines(year, month):
        for p in l["points"]:
            if p["id"] == int(point_id):
                line, point = l, p
                break
        if point:
            break
    if not point:
        return redirect(url_for("dowail.page", tab="papers"))
    rates = db.active_rates(year, month)
    ctx["line"], ctx["point"] = line, point
    ctx["rows"] = list(enumerate([db._item_row(r, point["force"], days) for r in rates]))
    return render_template("dowail/paper_point.html", **ctx)


@dowail_bp.route("/line-paper/<int:line_id>")
@login_required
def line_paper(line_id):
    year, month = _ctx()
    last, f, t, days = _range(year, month)
    ctx = _paper_ctx(year, month, last, f, t, days)
    line = dw.get_line(year, month, line_id)
    if not line:
        return redirect(url_for("dowail.page", tab="papers"))
    rates = db.active_rates(year, month)
    rows = []
    for r in rates:
        row = db._item_row(r, line["total_force"], days)
        row["rate"] = round(float(r.get("rate") or 0) * line["total_force"], 6)
        rows.append(row)
    ctx["line"] = line
    ctx["rows"] = list(enumerate(rows))
    return render_template("dowail/paper_line.html", **ctx)


@dowail_bp.route("/print-active")
@login_required
def print_active():
    year, month = _ctx()
    last, f, t, days = _range(year, month)
    ctx = _paper_ctx(year, month, last, f, t, days)
    ctx["papers"] = db.papers(year, month, f, t, days)
    rates = db.active_rates(year, month)
    active = 0
    for lp in ctx["papers"]:
        for pp in lp["points_papers"]:
            if (pp["point"]["force"] or 0) > 0:
                active += 1
                pp["rows"] = list(enumerate(
                    [db._item_row(r, pp["point"]["force"], days) for r in rates]))
    ctx["active_count"] = active
    return render_template("dowail/print_active.html", **ctx)


def _back(tab):
    return redirect(url_for("dowail.page", tab=tab))
