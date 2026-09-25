# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""آلة حاسبة ٢ مخازن — تحميل قائمة التأميدات وجمع الجهات في مربع الإذن."""
import json
from flask import Blueprint, render_template, request, g, redirect, url_for, jsonify
from core.auth_core import login_required, current_context, current_session
from core.config import MONTH_NAMES, MEALS
from core import arabic_numbers as arnum, egtime
from data_access import months, db_permits as dp, db_tameedat as dt
from data_access import db_recruits, db_attendance
from services import permit_build as pb

calc2_bp = Blueprint("calc2", __name__, url_prefix="/calc2")


def _ctx():
    year, month = current_context(g.user["id"])
    months.init_month(year, month)
    return year, month


def _rb(ok=None, err=None, **extra):
    _, token = current_session()
    params = {}
    if token:
        params["sid"] = token
    if ok:
        params["ok"] = ok
    if err:
        params["err"] = err
    params.update({k: v for k, v in extra.items() if v not in (None, "")})
    return redirect(url_for("calc2.page", **params))


def _day(year, month, raw, fallback):
    n = arnum.parse_int(raw)
    last = egtime.days_in_month(year, month)
    if n is None or n < 1 or n > last:
        return fallback
    return n


def _issuers(year, month, day):
    people = db_recruits.list_recruits(year, month)
    day_map = db_attendance.get_day_map(year, month, day)
    out = []
    for rec in people:
        st = (day_map.get(rec["id"]) or {}).get("status")
        if rec.get("has_cert") and st == "حضور":
            out.append(rec)
    return out


def _selected_picks(picks, raw):
    keys = []
    if raw:
        try:
            parsed = json.loads(raw)
            keys = parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            keys = [k for k in raw.split(",") if k]
    if not keys:
        keys = [k for k in (request.args.get("selected") or request.args.get("permit") or "").split(",") if k]
    out, seen = [], set()
    for key in keys:
        if key.startswith("combined:"):
            rid = key.split(":", 1)[1]
            key = f"main:{rid}"
        pick = pb.pick_by_key(picks, key)
        if pick and pick["key"] not in seen:
            out.append(pick)
            seen.add(pick["key"])
    return out


@calc2_bp.route("")
@calc2_bp.route("/")
@login_required
def page():
    year, month = _ctx()
    last = egtime.days_in_month(year, month)
    today = egtime.today()
    default = today.day if today.year == year and today.month == month else 1
    day_from = _day(year, month, request.args.get("from"), default)
    day_to = _day(year, month, request.args.get("to"), day_from)
    if day_to < day_from:
        day_to = day_from
    records = pb.overlapping_records(year, month, day_from, day_to)
    picks = pb.entity_picks(records)
    selected = _selected_picks(picks, request.args.get("box"))
    issue_days = arnum.parse_int(request.args.get("days")) or (day_to - day_from + 1)
    issue_days = max(1, min(issue_days, day_to - day_from + 1))
    officers = sum(p["officers"] for p in selected)
    individuals = sum(p["individuals"] for p in selected)
    recruits = sum(p["recruits"] for p in selected)
    force = officers + individuals + recruits
    label = " + ".join(p["name"] for p in selected)
    tamween = pb.rows_for_picks(year, month, selected, day_from, day_to, issue_days, "tamween") if selected else []
    contractor = pb.rows_for_picks(year, month, selected, day_from, day_to, issue_days, "contractor") if selected else []
    nxt, fiscal = dp.peek_next_number(egtime.today())
    return render_template(
        "calc2/page.html",
        year=year, month=month, month_name=MONTH_NAMES[month - 1],
        day_from=day_from, day_to=day_to, issue_days=issue_days,
        picks=picks, pick_groups=pb.pick_groups(year, month, picks),
        selected=selected, selected_groups=pb.pick_groups(year, month, selected),
        officers=officers, individuals=individuals, recruits=recruits,
        force=force, entity_label=label,
        tamween=tamween, contractor=contractor,
        meals=MEALS, issuers=_issuers(year, month, day_from),
        next_number=nxt, fiscal_year=fiscal, days_in_month=last,
        meal_on={"breakfast": True, "lunch": True, "dinner": True},
    )


@calc2_bp.route("/rows")
@login_required
def rows():
    """كميات الجدول تتحدث فور إضافة جهة للمربع بدون حفظ الإذن."""
    year, month = _ctx()
    last = egtime.days_in_month(year, month)
    today = egtime.today()
    default = today.day if today.year == year and today.month == month else 1
    day_from = _day(year, month, request.args.get("from"), default)
    day_to = _day(year, month, request.args.get("to"), day_from)
    if day_to < day_from:
        day_to = day_from
    issue_days = arnum.parse_int(request.args.get("days")) or (day_to - day_from + 1)
    issue_days = max(1, min(issue_days, day_to - day_from + 1))
    records = pb.overlapping_records(year, month, day_from, day_to)
    picks = pb.entity_picks(records)
    selected = _selected_picks(picks, request.args.get("selected"))
    tamween = pb.rows_for_picks(year, month, selected, day_from, day_to, issue_days, "tamween") if selected else []
    contractor = pb.rows_for_picks(year, month, selected, day_from, day_to, issue_days, "contractor") if selected else []
    return jsonify({"tamween": tamween, "contractor": contractor, "days_in_month": last})


@calc2_bp.route("/save", methods=["POST"])
@login_required
def save():
    year, month = _ctx()
    day_from = _day(year, month, request.form.get("date_from"), 1)
    day_to = _day(year, month, request.form.get("date_to"), day_from)
    if day_to < day_from:
        day_to = day_from
    issue_days = arnum.parse_int(request.form.get("issue_days")) or (day_to - day_from + 1)
    issue_days = max(1, min(issue_days, day_to - day_from + 1))
    posted = arnum.parse_int(request.form.get("number"))
    number, fiscal = dp.take_number(posted, egtime.today())
    meals = [m for m, _ in MEALS if request.form.get("meal_" + m)]
    if not meals:
        meals = ["breakfast", "lunch", "dinner"]
    records = pb.overlapping_records(year, month, day_from, day_to)
    picks = pb.entity_picks(records)
    selected = _selected_picks(picks, request.form.get("selected_json"))
    if not selected:
        return _rb(err="حط جهة واحدة على الأقل في مربع الجهات المحددة", **{"from": day_from, "to": day_to})
    actuals = {}
    for field, value in request.form.items():
        if field.startswith("actual_"):
            actuals[field[7:]] = arnum.parse_float(value)
    record_ids = sorted({int(p["record_id"]) for p in selected})
    label = (request.form.get("entity_label") or " + ".join(p["name"] for p in selected)).strip()
    dp.save_permit(year, month, {
        "number": number, "fiscal_year": fiscal,
        "date_from": day_from, "date_to": day_to, "issue_days": issue_days,
        "mode": "box",
        "entity_label": label,
        "officers": arnum.parse_int(request.form.get("officers")) or sum(p["officers"] for p in selected),
        "individuals": arnum.parse_int(request.form.get("individuals")) or sum(p["individuals"] for p in selected),
        "recruits": arnum.parse_int(request.form.get("recruits")) or sum(p["recruits"] for p in selected),
        "meals": meals,
        "receiver_kind": request.form.get("receiver_kind") or "",
        "receiver_rank": request.form.get("receiver_rank") or "",
        "receiver_name": request.form.get("receiver_name") or "",
        "issuer_name": request.form.get("issuer_name") or "",
        "record_ids": record_ids,
        "actuals": actuals,
    })
    names = "، ".join(p["name"] for p in selected)
    ok = (f"حُفظ إذن صرف رقم {arnum.to_arabic_indic(number)} للجهات: {names} "
          f"من يوم {arnum.to_arabic_indic(day_from)} "
          f"لمدة {arnum.to_arabic_indic(issue_days)} يومًا.")
    keys = ",".join(p["key"] for p in selected)
    return _rb(ok=ok, **{"from": day_from, "to": day_to, "selected": keys, "days": issue_days})
