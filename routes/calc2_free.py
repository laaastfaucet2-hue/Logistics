# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""«٢ مخازن حرة» — آلة حاسبة ٢ مخازن بترقيمها الخاص وبلا أثر على المخازن.

- معدلات توزيع مستقلة (نسخة من معدلات الشهر أول فتح + قابلة للتعديل من جوة الجدول)
- حفظ إذن تجريبي برقم مستقل + معاينة/إعادة طباعة + حذف
- صفر أثر: لا calc2_permits ولا أرصدة مخازن ولا تفريدة ولا ترقيم حقيقي
"""
from core import arabic_numbers as arnum, egtime
from flask import (Blueprint, jsonify, redirect, render_template, request,
                   url_for)
from data_access import db_calc2_free as c2f
from data_access import db_permits as dp
from data_access import db_tameedat as dt
from core.auth_core import current_session, login_required
from services import free_build as fb
from services import permit_build as pb
from routes.calc2 import (MEALS, MONTH_NAMES, _ctx, _day, _issuers,
                          _selected_picks)

calc2_free_bp = Blueprint("calc2_free", __name__, url_prefix="/calc2/free")

MEAL_KEYS = ("breakfast", "lunch", "dinner")


def _base_args():
    """الفترة والأيام من الطلب — الافتراضي: الشهر كله (تظهر كل التأميدات)."""
    year, month = _ctx()
    last = egtime.days_in_month(year, month)
    day_from = _day(year, month, request.args.get("from") or request.form.get("date_from"), 1)
    day_to = _day(year, month, request.args.get("to") or request.form.get("date_to"), last)
    if day_to < day_from:
        day_to = day_from
    issue_days = arnum.parse_int(request.args.get("days") or request.form.get("issue_days")) \
        or (day_to - day_from + 1)
    issue_days = max(1, min(issue_days, day_to - day_from + 1))
    return year, month, last, day_from, day_to, issue_days


def _records_picks(year, month, day_from, day_to):
    records = pb.overlapping_records(year, month, day_from, day_to)
    picks = pb.entity_picks(records)
    return records, picks


def _free_rates(year, month):
    """المعدلات المستقلة — أول فتح في الشهر: نسخة من معدلات الشهر الحالي."""
    c2f.seed_from_catalog(year, month)
    return c2f.get_rates(year, month)


@calc2_free_bp.route("")
@calc2_free_bp.route("/")
@login_required
def free_page():
    year, month, last, day_from, day_to, issue_days = _base_args()
    _records, picks = _records_picks(year, month, day_from, day_to)
    selected = _selected_picks(picks, request.args.get("selected"))
    officers = sum(p["officers"] for p in selected)
    individuals = sum(p["individuals"] for p in selected)
    recruits = sum(p["recruits"] for p in selected)
    force = officers + individuals + recruits
    label = " + ".join(p["name"] for p in selected)
    rates = _free_rates(year, month)
    preview = None
    permits = c2f.list_permits(year, month)
    tamween = contractor = []
    preview_id = arnum.parse_int(request.args.get("permit"))
    if preview_id is not None:
        preview = c2f.get_permit(year, month, preview_id)
        if preview is None:
            preview_id = None
    if preview is not None:
        day_from, day_to = int(preview["date_from"]), int(preview["date_to"])
        issue_days = int(preview["issue_days"])
        officers = int(preview["officers"] or 0)
        individuals = int(preview["individuals"] or 0)
        recruits = int(preview["recruits"] or 0)
        force = officers + individuals + recruits
        label = preview.get("entity_label") or label
        items = preview.get("items") or []
        tamween = [i for i in items if i.get("section") == "tamween"]
        contractor = [i for i in items if i.get("section") == "contractor"]
        for sec in (tamween, contractor):
            for j, row in enumerate(sec):
                row["serial"] = j + 1
                row["auto"] = row.get("qty_auto", 0)
                row["actual"] = row.get("qty_actual", 0)
    elif selected:
        rows = fb.all_rows_for_picks(year, month, selected, day_from, day_to,
                                     issue_days, rates)
        tamween, contractor = rows["tamween"], rows["contractor"]
    nxt = (max([p["number"] for p in permits] or [0])) + 1
    _, fiscal = dp.peek_next_number(egtime.today())
    _, token = current_session()
    ok = request.args.get("ok") or ""
    err = request.args.get("err") or ""
    view = request.args.get("view") or ""
    catalog = {"tamween": [], "contractor": []}
    if view == "rates":
        catalog = {"tamween": fb.catalog_rows(year, month, "tamween", rates),
                   "contractor": fb.catalog_rows(year, month, "contractor", rates)}
    sub_args = {}
    if request.args.get("from"):
        sub_args["from"] = request.args.get("from")
    if request.args.get("to"):
        sub_args["to"] = request.args.get("to")
    sub_args_rates = dict(sub_args)
    sub_args_rates["view"] = "rates"
    return render_template(
        "calc2/tab_free.html",
        view=view, catalog=catalog,
        year=year, month=month, month_name=MONTH_NAMES[month - 1],
        day_from=day_from, day_to=day_to, issue_days=issue_days,
        picks=picks, pick_groups=pb.pick_groups(year, month, picks),
        selected=selected, selected_groups=pb.pick_groups(year, month, selected),
        officers=officers, individuals=individuals, recruits=recruits,
        force=force, entity_label=label, entity_names=dt.entity_names(year, month),
        tamween=tamween, contractor=contractor,
        meals=MEALS, meal_on={"breakfast": True, "lunch": True, "dinner": True},
        issuers=_issuers(year, month, day_from),
        rates=rates,
        next_free_number=nxt, fiscal_year=fiscal, days_in_month=last,
        permits=permits, preview=preview, preview_id=preview_id,
        sid=token or "", ok=ok, err=err,
        cur_tab="free", sub_args=sub_args, sub_args_rates=sub_args_rates,
    )


@calc2_free_bp.route("/rows")
@login_required
def free_rows():
    """أسطر التابلت تتحدث فور إضافة جهة للمربع — بمعدلات التوزيع الحر."""
    year, month, last, day_from, day_to, issue_days = _base_args()
    _records, picks = _records_picks(year, month, day_from, day_to)
    selected = _selected_picks(picks, request.args.get("selected"))
    rates = _free_rates(year, month)
    out = fb.all_rows_for_picks(year, month, selected, day_from, day_to,
                                issue_days, rates) if selected else {"tamween": [], "contractor": []}
    return jsonify({"tamween": out["tamween"], "contractor": out["contractor"],
                    "days_in_month": last})


def _parse_rows_from_form(form):
    """القراءة: actual_{sec}_{name} و freerate_{sec}_{name} — أسماء أقسام معروفة فقط."""
    items = []
    for key, raw in form.items():
        if not (key.startswith("actual_") or key.startswith("freerate_")):
            continue
        parts = key.split("_", 2)
        if len(parts) != 3 or parts[1] not in ("tamween", "contractor") \
                or not " ".join((parts[2] or "").split()):
            continue
        kind = "actual" if parts[0] == "actual" else "rate"
        items.append({"kind": kind, "section": parts[1], "name": parts[2],
                      "value": arnum.parse_float(raw)})
    return items


@calc2_free_bp.route("/save", methods=["POST"])
@login_required
def free_save():
    """حفظ إذن تجريبي + حفظ معدلات التوزيع المعدلة — بدون أي أثر على المخازن."""
    year, month, last, day_from, day_to, issue_days = _base_args()
    form = request.form
    _records, picks = _records_picks(year, month, day_from, day_to)
    selected = _selected_picks(picks, form.get("selected_json"))
    if not selected:
        return redirect(url_for("calc2_free.free_page", err="اختر جهة على الأقل قبل الحفظ"))
    rates = _free_rates(year, month)
    posted = _parse_rows_from_form(form)
    for entry in posted:
        if entry["kind"] == "rate" and entry["value"] is not None:
            rates[entry["section"]][entry["name"]] = \
                {"unit": (rates[entry["section"]].get(entry["name"]) or {}).get("unit") or "",
                 "rate": entry["value"]}
            c2f.save_rate(year, month, entry["section"], entry["name"], entry["value"])
    rows = fb.all_rows_for_picks(year, month, selected, day_from, day_to,
                                 issue_days, rates)
    items = []
    for sec in ("tamween", "contractor"):
        for row in rows[sec]:
            actual = row["actual"]
            for entry in posted:
                if entry["kind"] == "actual" and entry["section"] == sec \
                        and entry["name"] == row["name"] and entry["value"] is not None:
                    actual = entry["value"]
                    break
            items.append({"section": sec, "name": row["name"], "unit": row["unit"],
                          "rate": row["rate"], "days": row["days"],
                          "force_days": row["force_days"],
                          "qty_auto": row["auto"], "qty_actual": actual})
    officers = arnum.parse_int(form.get("officers"))
    individuals = arnum.parse_int(form.get("individuals"))
    recruits = arnum.parse_int(form.get("recruits"))
    if officers is None:
        officers = sum(p["officers"] for p in selected)
    if individuals is None:
        individuals = sum(p["individuals"] for p in selected)
    if recruits is None:
        recruits = sum(p["recruits"] for p in selected)
    number = c2f.next_number(year, month)
    data = {
        "number": number,
        "fiscal_year": dp.peek_next_number(egtime.today())[1],
        "date_from": day_from, "date_to": day_to, "issue_days": issue_days,
        "entity_label": dt.normalize_entity_name(   # الاسم يتبع قاموس الجهات (توجيه ٠٨/١٠)
            year, month,
            form.get("entity_label") or " + ".join(p["name"] for p in selected)),
        "officers": officers or 0, "individuals": individuals or 0,
        "recruits": recruits or 0,
        "meals": [k for k in MEAL_KEYS if form.get("meal_" + k) == "1"],
        "receiver_kind": form.get("receiver_kind") or "",
        "receiver_rank": form.get("receiver_rank") or "",
        "receiver_name": form.get("receiver_name") or "",
        "issuer_name": form.get("issuer_name") or "",
        "record_ids": [p["record_id"] for p in selected],
        "rates": {k: {n: v["rate"] for n, v in sec.items()} for k, sec in rates.items()},
        "items": items,
    }
    new_id = c2f.save_permit(year, month, data)
    return redirect(url_for("calc2_free.free_page",
                            ok="اتحفظ الإذن التجريبي رقم " + arnum.to_arabic_indic(number)
                               + " — بدون أي أثر على المخازن",
                            **{"from": day_from, "to": day_to, "days": issue_days,
                               "selected": ",".join(p["key"] for p in selected)}))


@calc2_free_bp.route("/rates/save", methods=["POST"])
@login_required
def free_rates_save():
    """حفظ معدلات التوزيع الحرة كاملة (من تاب «معدلات التوزيع»)."""
    year, month = _ctx()
    _free_rates(year, month)
    saved = 0
    for key, raw in request.form.items():
        if not key.startswith("rate_"):
            continue
        parts = key.split("_", 2)
        if len(parts) != 3 or parts[1] not in ("tamween", "contractor"):
            continue
        name = " ".join(parts[2].split())
        if not name:
            continue
        value = arnum.parse_float(raw)
        if value is None:
            continue
        c2f.save_rate(year, month, parts[1], name, value)
        saved += 1
    return redirect(url_for("calc2_free.free_page", view="rates",
                            ok="اتحفظت معدلات التوزيع الحرة (" + arnum.to_arabic_indic(saved) + " صنف)"))


@calc2_free_bp.route("/delete/<int:permit_id>", methods=["POST"])
@login_required
def free_delete(permit_id):
    year, month = _ctx()
    c2f.delete_permit(year, month, permit_id)
    return redirect(url_for("calc2_free.free_page", ok="اتحذف الإذن التجريبي"))
