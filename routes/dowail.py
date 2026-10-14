# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تفاريد خط الحدود الدولى: نسخ الخطوط، الأوراق، المعدلات، والمحفوظات."""
import io

from flask import Blueprint, redirect, render_template, request, send_file, url_for
from openpyxl import Workbook

from core import arabic_numbers as arnum
from core import egtime
from core.auth_core import current_session, login_required
from core.config import DAYS, MEALS, MONTH_NAMES
from data_access import db_dowail as dw
from data_access import db_letterhead as lhdb
from data_access import db_rations as dr
from data_access import months
from routes.calc2 import _ctx, _day
from services import dowail_build as db
from services import dowail_fs, dowail_paper_xlsx

dowail_bp = Blueprint("dowail", __name__, url_prefix="/calc2/dowail")
TABS = ("papers", "totals", "lines", "rates")


def _range(year, month):
    last = egtime.days_in_month(year, month)
    f = _day(year, month, request.args.get("from") or request.form.get("date_from"), 1)
    t = _day(year, month, request.args.get("to") or request.form.get("date_to"), last)
    if t < f:
        t = f
    return last, f, t, t - f + 1


def _tab():
    return request.args.get("tab") if request.args.get("tab") in TABS else "papers"


def _base(year, month, last, f, t, tab):
    _, token = current_session()
    return {
        "year": year, "month": month, "month_name": MONTH_NAMES[month - 1],
        "days_in_month": last, "day_from": f, "day_to": t,
        "issue_days": t - f + 1, "tab": tab, "sid": token or "",
        "cur_tab": "dowail",
    }


def _go(tab, ok=None, err=None, **extra):
    args = {"tab": tab}
    args.update(extra)
    if ok:
        args["ok"] = ok
    if err:
        args["err"] = err
    return redirect(url_for("dowail.page", **args))


def _period_text(line):
    if line.get("date_from") is None or line.get("date_to") is None:
        return "الفترة غير محددة"
    return (f"من يوم {arnum.to_arabic_indic(line['date_from'])} "
            f"إلى يوم {arnum.to_arabic_indic(line['date_to'])}")


def _line_period(line, from_value=None, to_value=None):
    """فترة صرف مقصّرة، لكن لا تتجاوز فترة نسخة الخط."""
    if not line or line.get("date_from") is None or line.get("date_to") is None:
        return None, None, "حدد فترة نسخة الخط أولًا من إدارة الخطوط والنقاط"
    lower, upper = int(line["date_from"]), int(line["date_to"])
    f = arnum.parse_int(from_value)
    t = arnum.parse_int(to_value)
    f = lower if f is None else f
    t = upper if t is None else t
    if f < lower or t > upper or t < f:
        return None, None, (
            f"فترة الصرف يجب أن تقع داخل فترة نسخة «{line['name']}» من يوم "
            f"{arnum.to_arabic_indic(lower)} إلى يوم {arnum.to_arabic_indic(upper)}")
    return f, t, ""


def _rates_view(year, month):
    catalog = db.catalog_reference(year, month)
    computed = {(row["section"], row["name"]): row
                for row in db.rates_with_custom(year, month)}
    out = {"tamween": [], "contractor": []}
    for section in out:
        section_catalog = [(key, value) for key, value in catalog.items()
                           if key[0] == section]
        seen = set()
        for _key, ref in section_catalog:
            name = ref["name"]
            seen.add(name)
            saved = computed.get((section, name))
            weekly = (saved or {}).get("weekly_custom") or ref.get("weekly") or []
            dates = (saved or {}).get("date_custom") or []
            row = {
                "serial": len(out[section]) + 1, "name": name,
                "unit": (saved or {}).get("unit") or ref.get("unit") or "",
                "reference_rate": float(ref.get("reference_rate") or 0),
                "manual_rate": float((saved or {}).get("manual_rate") or 0),
                "effective_rate": float((saved or {}).get("effective_rate")
                                        if saved else ref.get("reference_rate") or 0),
                "enabled": int((saved or {}).get("enabled") or 0),
                "rate_id": (saved or {}).get("id"), "is_extra": False,
                "weekly_entries": weekly, "date_entries": dates,
            }
            row["custom"] = db.custom_chips({
                "weekly_custom": weekly, "date_custom": dates})
            out[section].append(row)
        for saved in computed.values():
            if saved["section"] != section or saved["name"] in seen:
                continue
            weekly = saved.get("weekly_custom") or []
            dates = saved.get("date_custom") or []
            row = {
                "serial": len(out[section]) + 1, "name": saved["name"],
                "unit": saved.get("unit") or "", "reference_rate": 0.0,
                "manual_rate": float(saved.get("manual_rate") or 0),
                "effective_rate": float(saved.get("effective_rate") or 0),
                "enabled": int(saved.get("enabled") or 0), "rate_id": saved["id"],
                "is_extra": True, "weekly_entries": weekly, "date_entries": dates,
            }
            row["custom"] = db.custom_chips({
                "weekly_custom": weekly, "date_custom": dates})
            out[section].append(row)
    return out


# ======================================================================
# الصفحة الرئيسية
# ======================================================================
@dowail_bp.route("")
@dowail_bp.route("/")
@login_required
def page():
    year, month = _ctx()
    months.init_month(year, month)
    last, f, t, _days = _range(year, month)
    tab = _tab()
    ctx = _base(year, month, last, f, t, tab)

    if tab == "papers":
        lines = dw.list_lines(year, month)
        selected_id = arnum.parse_int(request.args.get("line"))
        selected = next((line for line in lines if line["id"] == selected_id), None)
        selected = selected or (lines[0] if lines else None)
        range_error = ""
        if selected:
            raw_f = request.args.get("from") if "from" in request.args else None
            raw_t = request.args.get("to") if "to" in request.args else None
            f, t, range_error = _line_period(selected, raw_f, raw_t)
            if range_error:
                if selected.get("date_from") is not None:
                    f, t = int(selected["date_from"]), int(selected["date_to"])
                else:
                    f, t = 1, last
            ctx.update(day_from=f, day_to=t, issue_days=t - f + 1)
        ctx.update(lines=lines, selected_line=selected,
                   sel_line_id=selected["id"] if selected else None,
                   period_error=range_error, saves=dw.list_saves(year, month))
        ctx["current_papers"] = ([db.line_paper(year, month, selected, f, t)]
                                 if selected and not range_error else [])
        dist_id = arnum.parse_int(request.args.get("dist"))
        ctx["dist_save"] = dw.get_save(year, month, dist_id) if dist_id else None
        if ctx["dist_save"] and ctx["dist_save"].get("data"):
            data = db.normalize_snapshot(ctx["dist_save"]["data"])
            ctx["dist_save"]["data"] = data
            ctx["dist_save"]["issue_days"] = data.get("issue_days", 0)
        found = db.search_point(year, month, request.args.get("q"))
        ctx["search_q"] = request.args.get("q") or ""
        ctx["search_hit"] = None
        if found:
            hit_line, point = found
            hf, ht, hit_error = _line_period(hit_line)
            dates = db.issue_dates(year, month, hf, ht) if not hit_error else []
            ctx["search_hit"] = {
                "line": hit_line, "point": point, "date_from": hf, "date_to": ht,
                "error": hit_error,
                "rows": list(enumerate([db.item_row(rate, point["force"], dates)
                                        for rate in db.active_rates(year, month)])),
            }
    elif tab == "totals":
        line_id = arnum.parse_int(request.args.get("line"))
        ctx.update(lines=dw.list_lines(year, month), sel_line_id=line_id,
                   saves=dw.list_saves(year, month))
        archive = (dw.get_save(year, month, arnum.parse_int(request.args.get("dist")))
                   if request.args.get("dist") else None)
        if archive and archive.get("data"):
            archive["data"] = db.normalize_snapshot(archive["data"])
            archive["issue_days"] = archive["data"].get("issue_days", 0)
            matrix = archive["data"].get("matrix") or {}
            if line_id:
                matrix = dict(matrix)
                matrix["lines"] = [item for item in matrix.get("lines") or []
                                   if int(item["line"]["id"]) == line_id]
            ctx.update(matrix=matrix, archive_save=archive)
        else:
            ctx.update(matrix=db.current_period_matrix(year, month, line_id),
                       archive_save=None)
    elif tab == "lines":
        show_archive = request.args.get("archive") == "1"
        lines = dw.list_archived_lines(year, month) if show_archive else dw.list_lines(year, month)
        selected_id = arnum.parse_int(request.args.get("line"))
        selected = next((line for line in lines if line["id"] == selected_id), None)
        selected = selected or (lines[0] if lines else None)
        all_versions = dw.list_versions(year, month)
        ctx.update(
            lines=lines, current_lines=dw.list_lines(year, month),
            archived_lines=dw.list_archived_lines(year, month),
            show_archive=show_archive, selected_line=selected,
            sel_line_id=selected["id"] if selected else None,
            line_statements=dowail_fs.list_line_statements(year, month),
            dw_line_names=sorted({line["name"] for line in all_versions}),
            dw_point_names=sorted({point["name"] for line in all_versions
                                   for point in line.get("points") or []}),
        )
    else:
        view = _rates_view(year, month)
        names = {item["name"] for rows in view.values() for item in rows}
        for section in ("tamween", "contractor"):
            names.update(dr.known_item_names(year, month, section))
        units = set(dr.collect_units(year, month))
        units.update(item["unit"] for rows in view.values() for item in rows
                     if item["unit"])
        ctx.update(rates_view=view,
                   rate_statements=dowail_fs.list_rates_statements(year, month),
                   days=DAYS, meals=MEALS, dw_item_names=sorted(names),
                   dw_units=sorted(units))
    return render_template(f"dowail/tab_{tab}.html", **ctx)


# ======================================================================
# نسخ الخطوط والنقاط
# ======================================================================
def _statement_after(year, month, line_id):
    line = dw.get_line(year, month, line_id)
    if line:
        dowail_fs.write_line_statement(year, month, line)


@dowail_bp.route("/lines", methods=["POST"])
@login_required
def add_line():
    year, month = _ctx()
    name = " ".join((request.form.get("name") or "").split())
    day_from = arnum.parse_int(request.form.get("date_from"))
    day_to = arnum.parse_int(request.form.get("date_to"))
    if day_from is None or day_to is None:
        return _go("lines", err="اكتب فترة النسخة الجديدة من يوم وإلى يوم")
    replaced = next((line for line in dw.list_lines(year, month)
                     if line["name"] == name), None)
    line_id, error = dw.create_line_version(year, month, name, day_from, day_to)
    if error:
        return _go("lines", err=error)
    _statement_after(year, month, line_id)
    text = f"تم إنشاء نسخة حالية فارغة لخط «{name}» ({_period_text(dw.get_line(year, month, line_id))})"
    if replaced:
        text += "، ونُقلت النسخة الحالية السابقة بنقاطها إلى الأرشيف"
    return _go("lines", ok=text, line=line_id)


@dowail_bp.route("/lines/<int:line_id>/period", methods=["POST"])
@login_required
def line_period(line_id):
    year, month = _ctx()
    error = dw.update_line_period(
        year, month, line_id, arnum.parse_int(request.form.get("date_from")),
        arnum.parse_int(request.form.get("date_to")))
    archive = request.form.get("archive") == "1"
    if error:
        return _go("lines", err=error, line=line_id,
                   **({"archive": 1} if archive else {}))
    _statement_after(year, month, line_id)
    return _go("lines", ok="تم حفظ فترة نسخة الخط دون تغيير نقاطها أو قوتها",
               line=line_id, **({"archive": 1} if archive else {}))


@dowail_bp.route("/lines/<int:line_id>/archive", methods=["POST"])
@login_required
def archive_line(line_id):
    year, month = _ctx()
    line = dw.get_line(year, month, line_id)
    if not line or not dw.archive_line(year, month, line_id):
        return _go("lines", err="تعذر أرشفة نسخة الخط")
    return _go("lines", ok=f"نُقلت نسخة «{line['name']}» إلى الأرشيف بنقاطها وقوتها")


@dowail_bp.route("/lines/<int:line_id>/restore", methods=["POST"])
@login_required
def restore_line(line_id):
    year, month = _ctx()
    new_id, error = dw.restore_line(year, month, line_id)
    if error:
        return _go("lines", err=error, archive=1, line=line_id)
    _statement_after(year, month, new_id)
    return _go("lines", ok=("تم نسخ نقاط وقوة النسخة المؤرشفة إلى نسخة حالية جديدة. "
                            "حدد لها فترة غير متداخلة قبل الصرف"), line=new_id)


@dowail_bp.route("/lines/<int:line_id>/delete", methods=["POST"])
@login_required
def delete_line(line_id):
    year, month = _ctx()
    line = dw.get_line(year, month, line_id)
    if not line or line.get("status") != "archived":
        return _go("lines", err="الحذف النهائي متاح للنسخ المؤرشفة فقط")
    dw.delete_line(year, month, line_id)
    return _go("lines", ok=f"تم حذف النسخة المؤرشفة لخط «{line['name']}» نهائيًا", archive=1)


@dowail_bp.route("/points", methods=["POST"])
@login_required
def add_point():
    year, month = _ctx()
    line_id = arnum.parse_int(request.form.get("line_id")) or 0
    point_id = dw.add_point(year, month, line_id, request.form.get("name"),
                            arnum.parse_int(request.form.get("force")) or 0)
    archive = request.form.get("archive") == "1"
    if not point_id:
        return _go("lines", err="تعذر إضافة النقطة؛ راجع الاسم", line=line_id,
                   **({"archive": 1} if archive else {}))
    _statement_after(year, month, line_id)
    return _go("lines", ok="تمت إضافة النقطة إلى هذه النسخة فقط", line=line_id,
               **({"archive": 1} if archive else {}))


@dowail_bp.route("/points/<int:point_id>/update", methods=["POST"])
@login_required
def update_point(point_id):
    year, month = _ctx()
    line, _point = dw.find_point(year, month, point_id)
    if line:
        if request.form.get("responsible_only"):
            dw.update_point(year, month, point_id,
                            responsible=request.form.get("responsible") or "")
        else:
            dw.update_point(year, month, point_id,
                            force=arnum.parse_int(request.form.get("force")))
        _statement_after(year, month, line["id"])
    archive = request.form.get("archive") == "1"
    return _go("lines", ok="تم تحديث بيانات النقطة", line=line["id"] if line else None,
               **({"archive": 1} if archive else {}))


@dowail_bp.route("/points/<int:point_id>/delete", methods=["POST"])
@login_required
def delete_point(point_id):
    year, month = _ctx()
    line, _point = dw.find_point(year, month, point_id)
    if line:
        dw.delete_point(year, month, point_id)
        _statement_after(year, month, line["id"])
    archive = request.form.get("archive") == "1"
    return _go("lines", ok="تم حذف النقطة من هذه النسخة", line=line["id"] if line else None,
               **({"archive": 1} if archive else {}))


# ======================================================================
# المعدلات والتخصيص الأسبوعي/الفعلي
# ======================================================================
def _rates_statement(year, month):
    dowail_fs.write_rates_statement(year, month, db.rates_with_custom(year, month))


@dowail_bp.route("/custom/<int:rate_id>", methods=["POST"])
@login_required
def custom_save(rate_id):
    year, month = _ctx()
    rate = dw.get_rate(year, month, rate_id) if rate_id else None
    if not rate:
        section = request.form.get("section")
        name = request.form.get("item_name")
        rate_id = dw.save_rate(year, month, section, name, 0,
                               request.form.get("item_unit") or "",
                               is_extra=request.form.get("is_extra") == "1",
                               enabled=False)
        rate = dw.get_rate(year, month, rate_id) if rate_id else None
    if not rate:
        return _go("rates", err="تعذر تحديد الصنف المطلوب تخصيصه")
    weekly = []
    for weekday in range(7):
        for meal, _label in MEALS:
            qty = arnum.parse_float(request.form.get(f"c_{weekday}_{meal}"))
            if qty is not None and qty > 0:
                weekly.append((weekday, meal, qty))
    actual = []
    fields = zip(request.form.getlist("date_day"),
                 request.form.getlist("date_meal"),
                 request.form.getlist("date_qty"),
                 request.form.getlist("date_mode"))
    last = egtime.days_in_month(year, month)
    for day_raw, meal, qty_raw, mode in fields:
        day = arnum.parse_int(day_raw)
        qty = arnum.parse_float(qty_raw)
        if day and 1 <= day <= last and meal in dict(MEALS) and qty and qty > 0:
            actual.append((day, meal, qty, "replace" if mode == "replace" else "add"))
    dw.save_rate_custom(year, month, rate_id, weekly, actual)
    _rates_statement(year, month)
    return _go("rates", ok=(f"تم حفظ تخصيص «{rate['name']}»: "
                             f"{arnum.to_arabic_indic(len(weekly))} أسبوعي و"
                             f"{arnum.to_arabic_indic(len(actual))} بتاريخ فعلي"))


@dowail_bp.route("/rates/add", methods=["POST"])
@login_required
def rates_add():
    year, month = _ctx()
    section = request.form.get("section")
    section = section if section in ("tamween", "contractor") else "tamween"
    name = " ".join((request.form.get("name") or "").split())
    if not name:
        return _go("rates", err="اكتب اسم الصنف")
    extra = (section, name) not in db.catalog_reference(year, month)
    unit = " ".join((request.form.get("unit") or "").split())
    rate_id = dw.save_rate(year, month, section, name,
                           arnum.parse_float(request.form.get("rate")) or 0,
                           unit, is_extra=extra)
    if not rate_id:
        return _go("rates", err="تعذر حفظ الصنف")
    if unit:
        dr.remember_unit(unit)
    _rates_statement(year, month)
    return _go("rates", ok="تم حفظ الإضافة اليدوية وتفعيل الصنف")


@dowail_bp.route("/rates/<int:rate_id>/update", methods=["POST"])
@login_required
def rates_update(rate_id):
    year, month = _ctx()
    row = dw.get_rate(year, month, rate_id)
    if row:
        dw.save_rate(year, month, row["section"], row["name"],
                     arnum.parse_float(request.form.get("rate")) or 0,
                     request.form.get("unit") or row.get("unit") or "",
                     is_extra=bool(row.get("is_extra")))
        _rates_statement(year, month)
    return _go("rates", ok="تم حفظ الإضافة اليدوية")


@dowail_bp.route("/rates/<int:rate_id>/toggle", methods=["POST"])
@login_required
def rates_toggle(rate_id):
    year, month = _ctx()
    dw.toggle_rate(year, month, rate_id)
    _rates_statement(year, month)
    return _go("rates", ok="تم تغيير حالة الصنف")


@dowail_bp.route("/rates/<int:rate_id>/delete", methods=["POST"])
@login_required
def rates_delete(rate_id):
    year, month = _ctx()
    dw.delete_rate(year, month, rate_id)
    _rates_statement(year, month)
    return _go("rates", ok="تم حذف إعداد الصنف من الدولى")


# ======================================================================
# توزيع جديد: فترة مستقلة لكل خط حالي
# ======================================================================
def _current_selections(year, month, source):
    selections = []
    for line in dw.list_lines(year, month):
        f, t, error = _line_period(line, source.get(f"from_{line['id']}"),
                                   source.get(f"to_{line['id']}"))
        if error:
            return [], error
        selections.append((line, f, t))
    if not selections:
        return [], "لا توجد خطوط حالية للحفظ"
    return selections, ""


@dowail_bp.route("/save", methods=["POST"])
@login_required
def save_tafreeda():
    year, month = _ctx()
    selections, error = _current_selections(year, month, request.form)
    if error:
        return _go("papers", err=error)
    data = db.snapshot_for_selections(year, month, selections)
    n_same = dw.count_saves_from(year, month, data["date_from"]) + 1
    files = dowail_fs.save_to_disk(year, month, data, n_same)
    save_id = dw.save_tafreeda(year, month, data, files)
    return _go("papers", ok=(f"تم حفظ التوزيع رقم {arnum.to_arabic_indic(save_id)} "
                              "بفترة مستقلة لكل خط"))


# ======================================================================
# الطباعة والتنزيل
# ======================================================================
def _live_snapshot(year, month):
    selections, error = _current_selections(year, month, {})
    return (db.snapshot_for_selections(year, month, selections), "") if not error else ({}, error)


def _saved_snapshot(year, month, save_id):
    save = dw.get_save(year, month, save_id) if save_id else None
    if not save or not save.get("data"):
        return None
    return db.normalize_snapshot(save["data"])


@dowail_bp.route("/papers-all")
@login_required
def papers_all():
    year, month = _ctx()
    months.init_month(year, month)
    dist_id = arnum.parse_int(request.args.get("dist"))
    if dist_id:
        data = _saved_snapshot(year, month, dist_id)
        error = "" if data else "التوزيع المحفوظ غير موجود"
    else:
        data, error = _live_snapshot(year, month)
    if error:
        return _go("papers", err=error)
    lh = [lhdb.get_setting(year, month, f"lh_{index}") for index in range(1, 5)]
    return render_template(
        "dowail/paper_all.html", all_papers=data.get("papers") or [],
        dist_id=dist_id, year=year, month=month,
        month_name=MONTH_NAMES[month - 1], today_iso=egtime.now().strftime("%Y-%m-%d"),
        lh=lh, has_logo=bool(lhdb.logo_path(year, month)),
        sigs=lhdb.get_signatures(), cur_tab="dowail")


@dowail_bp.route("/download-all")
@login_required
def download_all():
    year, month = _ctx()
    months.init_month(year, month)
    dist_id = arnum.parse_int(request.args.get("dist"))
    if dist_id:
        data = _saved_snapshot(year, month, dist_id)
        error = "" if data else "التوزيع المحفوظ غير موجود"
    else:
        data, error = _live_snapshot(year, month)
    if error:
        return _go("papers", err=error)
    book = dowail_fs.build_all_lines_wb(data, year, month)
    buf = io.BytesIO()
    book.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name="تفاريد-الدولى-كل-الخطوط.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@dowail_bp.route("/paper/<int:line_id>")
@login_required
def paper_view(line_id):
    year, month = _ctx()
    months.init_month(year, month)
    point_id = arnum.parse_int(request.args.get("point"))
    dist_id = arnum.parse_int(request.args.get("dist"))
    if dist_id:
        data = _saved_snapshot(year, month, dist_id)
        paper = next((item for item in (data or {}).get("papers") or []
                      if int(item["line"]["id"]) == line_id), None)
        if not paper:
            return _go("papers", err="هذا الخط غير موجود داخل التوزيع المحفوظ")
        line = paper["line"]
    else:
        line = dw.get_line(year, month, line_id)
        f, t, error = _line_period(line, request.args.get("from"), request.args.get("to"))
        if error:
            return _go("papers", err=error, line=line_id)
        data = db.snapshot_for_selections(year, month, [(line, f, t)])
        paper = data["papers"][0]
    f, t = int(paper["date_from"]), int(paper["date_to"])
    docs = []
    if point_id:
        pp = next((item for item in paper["points_papers"]
                   if int(item["point"]["id"]) == point_id), None)
        if not pp:
            return _go("papers", err="هذه النقطة غير موجودة على هذه النسخة")
        docs.append({"kind": "point", "point": pp["point"], "rows": pp["rows"]})
    else:
        docs.append({"kind": "line", "rows": paper["line_paper"]["rows"]})
        docs.extend({"kind": "point", "point": item["point"], "rows": item["rows"]}
                    for item in paper["points_papers"])
    args = {"line_id": line_id}
    if dist_id:
        args["dist"] = dist_id
    else:
        args.update({"from": f, "to": t})
    if point_id:
        args["point"] = point_id
    lh = [lhdb.get_setting(year, month, f"lh_{index}") for index in range(1, 5)]
    return render_template(
        "dowail/paper.html", line=line, docs=docs, dist_id=dist_id,
        point_id=point_id, xlsx_url=url_for("dowail.paper_xlsx", **args),
        year=year, month=month, month_name=MONTH_NAMES[month - 1], f=f, t=t,
        days=t - f + 1, from_iso=f"{year:04d}-{month:02d}-{f:02d}",
        to_iso=f"{year:04d}-{month:02d}-{t:02d}",
        today_iso=egtime.now().strftime("%Y-%m-%d"), lh=lh,
        has_logo=bool(lhdb.logo_path(year, month)),
        sigs=lhdb.get_signatures(), cur_tab="dowail")


@dowail_bp.route("/paper/<int:line_id>/xlsx")
@login_required
def paper_xlsx(line_id):
    year, month = _ctx()
    months.init_month(year, month)
    point_id = arnum.parse_int(request.args.get("point"))
    dist_id = arnum.parse_int(request.args.get("dist"))
    if dist_id:
        data = _saved_snapshot(year, month, dist_id)
        paper = next((item for item in (data or {}).get("papers") or []
                      if int(item["line"]["id"]) == line_id), None)
        if not paper:
            return "هذا الخط غير موجود داخل التوزيع المحفوظ", 404
        line = paper["line"]
    else:
        line = dw.get_line(year, month, line_id)
        f, t, error = _line_period(line, request.args.get("from"), request.args.get("to"))
        if error:
            return error, 400
        data = db.snapshot_for_selections(year, month, [(line, f, t)])
    if point_id:
        point = next((item for item in line.get("points") or []
                      if int(item["id"]) == point_id), None)
        if not point:
            return "هذه النقطة غير موجودة على هذا الخط", 404
        book = Workbook()
        book.remove(book.active)
        ws = book.create_sheet(dowail_paper_xlsx._uniq_sheet(
            book, f"{line['name']}·{point['name']}"))
        dowail_paper_xlsx._write_doc(ws, data, line, "point", point=point)
        filename = f"ورقة الإذن-نقطة {point['name']}.xlsx"
    else:
        book = dowail_paper_xlsx.build_line_paper_wb(data, line)
        filename = f"ورقة الإذن-{line['name']}.xlsx"
    buf = io.BytesIO()
    book.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ======================================================================
# سجل التوزيعات وملفات البيانات
# ======================================================================
@dowail_bp.route("/saves/<int:save_id>/delete", methods=["POST"])
@login_required
def save_delete(save_id):
    year, month = _ctx()
    save = dw.get_save(year, month, save_id)
    if save:
        dowail_fs.delete_files(year, month, save.get("files") or [])
        dw.delete_save(year, month, save_id)
    return _go("papers", ok="تم حذف التوزيعة المحفوظة وملفاتها")


@dowail_bp.route("/file/<int:save_id>/<path:filename>")
@login_required
def save_file(save_id, filename):
    year, month = _ctx()
    if not dw.get_save(year, month, save_id):
        return "الملف غير موجود", 404
    base = months.month_db_path(year, month).parent.resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        return "الملف غير موجود", 404
    return send_file(str(target), as_attachment=True, download_name=target.name)


@dowail_bp.route("/statement/<path:filename>")
@login_required
def statement_file(filename):
    year, month = _ctx()
    section = dowail_fs.section_dir(year, month).resolve()
    target = (section / filename).resolve()
    if not str(target).startswith(str(section)) or not target.is_file():
        return "الملف غير موجود", 404
    return send_file(str(target), as_attachment=True, download_name=target.name)
