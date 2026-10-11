# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحة قسم الراغبين + السياق المشترك (سنة/شهر/جهة/فئة/يوم/بحث) وجديل الرجوع."""
from datetime import date
from flask import g, redirect, render_template, request, url_for
from urllib.parse import quote

from core import arabic_numbers as arnum
from core import egtime
from core import dates
from core.auth_core import current_context, current_session, login_required
from core.config import DAYS, MONTH_NAMES
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


def _selected_entity(year, month, by_name=False):
    """الجهة المحددة: ?e معرف أو ?en اسم (للمودال) أو فورم e —
    الافتراضي أول جهة بالقاموس (أو None لو فاضي)."""
    if by_name:
        name = " ".join((request.values.get("en") or "").split())
        if name:
            entity = dt.find_entity_by_name(year, month, name)
            if entity:
                return entity
        entities = dt.list_entities(year, month)
        return entities[0] if entities else None
    raw = request.values.get("e", "")
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


def _selected_day(year, month):
    """اليوم المحدد للتاب اليومي: ?d أو فورم d — الافتراضي تاريخ اليوم وإلا ١."""
    raw = request.values.get("d", "")
    day = arnum.parse_int(raw) if raw else 0
    if day and 1 <= day <= egtime.days_in_month(year, month):
        return day
    today = egtime.today()
    if today.year == year and today.month == month:
        return today.day
    return 1


def _entity_or_back(year, month, tab="cadres"):
    """الجهة الهدف من النموذج (e) — لو مفقودة رجوع بتنبيه على التاب المطلوب."""
    raw = request.values.get("e") or ""
    try:
        entity = dt.get_entity(year, month, int(raw))
    except ValueError:
        entity = None
    if not entity:
        return None, _rb(tab, err="اختر جهة أولًا")
    return entity, None


def _day_grid(year, month, selected, counts):
    """شبكة أيام الشهر (أسبوع يبدأ السبت) — العلامة عدد راغبين اليوم لجهة التاب."""
    first = date(year, month, 1)
    offset = (first.weekday() + 2) % 7          # السبت أول الأعمدة
    total_days = egtime.days_in_month(year, month)
    today = egtime.today()
    cells = [{"empty": True}] * offset
    for day in range(1, total_days + 1):
        cells.append({
            "empty": False, "day": day,
            "count": counts.get(day, 0),
            "selected": day == selected,
            "is_today": today.year == year and today.month == month and today.day == day,
        })
    while len(cells) % 7:
        cells.append({"empty": True})
    return [cells[i:i + 7] for i in range(0, len(cells), 7)]


def _excluded_vars(year, month, entity, query):
    """متغيرات تاب «عدم الراغبين»: المستثنون (ضباطًا وأفرادًا) لجهة التاب."""
    persons = dr.list_persons(year, month, entity_id=entity["id"], query=query,
                              excluded=True) if entity else []
    return {"excluded_persons": persons,
            "excluded_count": len(persons)}


def _monthly_vars(year, month, entity, category):
    """متغيرات تاب «تجميع الكشف العام»: وجبات الشهر (وجبة/يوم) بالفئة المختارة."""
    meals = dr.month_meals(year, month, entity["id"], category) if entity else {}
    persons = dr.list_persons(year, month, entity_id=entity["id"], category=category,
                              excluded=False) if entity else []
    rows = [{"person": p, "meals": meals.get(p["id"], 0)} for p in persons]
    return {
        "monthly_rows": rows,
        "monthly_total_persons": len(rows),
        "monthly_total_meals": sum(r["meals"] for r in rows),
    }


def _tameed_day_totals(year, month, entity_id, selected):
    """أعداد تأميدة اليوم المحدد للجهة (حسب مداها من-إلى) أو None."""
    officers_total = individuals_total = 0
    for rec in dt.records_for_day(year, month, selected, "all", ""):
        if rec.get("entity_id") != entity_id:
            continue
        if rec["day"] <= selected <= (rec.get("day_to") or rec["day"]):
            officers_total += rec["officers"]
            individuals_total += rec["individuals"]
    if officers_total or individuals_total:
        return {"officers": officers_total, "individuals": individuals_total}
    return None


def _slots_vars(year, month, entity, selected):
    """مربعات اليوم الذكية: عدد المربعات من تأميدة اليوم (توجيه ٣٠/٠٩/٢٠٢٦)،
    والمملوء منها = الراغبون المسجلون بالأسماء (بالأقدمية) + قوة الفئة للكومبو.

    slots[cat] = {tameeda, count, has_tameeda, boxes (أسماء + فراغات), label}
    force[cat] = أسماء القوة غير المستثناة (للبحث الذكي).
    """
    eid = entity["id"] if entity else None
    state = dr.day_state(year, month, selected, eid) if eid else {}
    tameed_totals = _tameed_day_totals(year, month, eid, selected) if eid else None
    slots, force = {}, {}
    for cat, key, label in (("officers", "officers", "الضباط"),
                            ("individuals", "individuals", "فرد")):
        persons = dr.list_persons(year, month, entity_id=eid, category=cat,
                                  excluded=False) if eid else []
        willing = [p["full_name"] for p in persons if state.get(p["id"])]
        tameeda = tameed_totals[key] if tameed_totals else 0
        boxes = list(willing) + [None] * max(0, tameeda - len(willing))
        slots[cat] = {"tameeda": tameeda, "count": len(willing),
                      "has_tameeda": bool(tameed_totals), "boxes": boxes,
                      "label": label}
        force[cat] = [p["full_name"] for p in persons]
    return {"slots": slots, "force": force, "tameed_totals": tameed_totals}


def _daily_vars(year, month, entity, selected):
    """متغيرات تاب «الراغبين (يومي)»: التقويم + المربعات + عدادات + تنبيهات اليوم."""
    eid = entity["id"] if entity else None
    counts_map = dr.day_willing_counts(year, month, eid) if eid else {}
    base = _slots_vars(year, month, entity, selected)
    slots = base["slots"]
    # «من أصل» = حجم القوة المعتمدة للجهة (ضباط/أفراد) — مش عدد مربعات التأميدة
    day_counts = {"officers": slots["officers"]["count"],
                  "individuals": slots["individuals"]["count"],
                  "officers_total": len(base["force"]["officers"]),
                  "individuals_total": len(base["force"]["individuals"])}
    # اسم اليوم (السبت/الأحد/...) + يوم الشهر لكل خلية في الشبكة (توجيه ١٠/١٠)
    day_names = {d: DAYS[(date(year, month, d).weekday() + 2) % 7]
                 for d in range(1, egtime.days_in_month(year, month) + 1)}
    # عداد «الضباط وسياء» (تصميم الاسكرين شوت): ضباط الجهة السيائية نفسها
    is_wastaya = bool(entity) and "وسياء" in entity["name"]
    day_counts["wastaya_officers"] = day_counts["officers"] if is_wastaya else 0
    day_counts["wastaya_officers_total"] = day_counts["officers_total"] if is_wastaya else 0
    # قوة اليوم: كل أعضاء الجهة بحالة يوم اليوم المفتوح (✓ راغب اليوم / ⊘ غير راغب / — غير مسجل)
    force_today = []
    if eid:
        state = dr.day_state(year, month, selected, eid)
        for cat, label in dr.CATEGORIES:
            for p in dr.list_persons(year, month, entity_id=eid, category=cat):
                force_today.append({
                    "rank": p.get("rank") or "—", "name": p["full_name"],
                    "cat": label, "excluded": bool(p["excluded"]),
                    "willing": bool(state.get(p["id"])),
                })
    return {
        "sel_day": selected,
        "weeks": _day_grid(year, month, selected, counts_map),
        "day_counts_map": counts_map,
        "day_names": day_names,
        "weekdays": DAYS,
        "slots": slots,
        "force": base["force"],
        "force_today": force_today,
        "tameed_totals": base["tameed_totals"],
        "day_counts": day_counts,
        # تنبيهات اليوم المفتوح بنفس محرك جدول الشهر: عدد الراغبين + غياب الكوادر
        "day_alert_issues": _day_alert_issues(year, month, entity, base["tameed_totals"],
                                              day_counts),
        "day_cadres": _cadres_of(year, month, entity),
    }


def _cadres_of(year, month, entity):
    """أعداد قوة الجهة في «الجهات والكوادر المعتمدة» — لعرضها في بنر التنبيهات."""
    if not entity:
        return {"officers": 0, "individuals": 0}
    from services import tameed_alerts
    return tameed_alerts.entity_cadres(year, month, entity["id"])


def _day_alert_issues(year, month, entity, tameed_totals, day_counts):
    """تنبيهات اليوم المفتوح: التأميدة مقابل الراغبين المسجلين مقابل الكوادر المعتمدة.

    من غير تأميدة لليوم: ساكت غير ما في راغبين مسجلين — ساعتها ينبه
    «سجلت راغبين من غير تأميدة» (توجيه ١٠/١٠/٢٠٦)."""
    if not entity:
        return []
    from services import tameed_alerts
    if not tameed_totals:
        total_willing = day_counts["officers"] + day_counts["individuals"]
        if total_willing:
            return [tameed_alerts.no_tameeda_issue(total_willing)]
        return []
    return tameed_alerts.record_day_issues(
        {"officers": tameed_totals["officers"], "individuals": tameed_totals["individuals"]},
        {"officers": day_counts["officers"], "individuals": day_counts["individuals"]},
        tameed_alerts.entity_cadres(year, month, entity["id"]))


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
    note_id = 0
    try:
        note_id = int(request.args.get("n", "0") or 0)
    except ValueError:
        note_id = 0
    persons = []
    if entity:
        persons = dr.list_persons(year, month, entity_id=entity["id"],
                                  category=category, query=query)
    return {
        "tabs": TABS, "tab": tab,
        "year": year, "month": month, "month_name": MONTH_NAMES[month - 1],
        "month_names": MONTH_NAMES,
        "q": query, "fcat": category,
        "categories": dr.CATEGORIES,
        "entities": entities,
        "entity": entity,
        "counts": counts,
        "persons": persons,
        "exclude_person": dr.get_person(year, month, exclude_id) if exclude_id else None,
        "note_person": dr.get_person(year, month, note_id) if note_id else None,
        "all_ranks": dr.ALL_RANKS,
        "officer_ranks": dr.RANKS["officers"],
        "individual_ranks": dr.RANKS["individuals"],
        "section_folder": rfs.base_dir(year, month),
        "total_force": sum(c["officers"] + c["individuals"] for c in counts.values()),
        **_alerts_vars(year, month),
    }


def _alerts_vars(year, month):
    """جدول تنبيهات التاميدات ↔ الراغبين لكل أيام الشهر (يُفتح ويُغلق)."""
    try:
        from core.web import alerts_context

        def _alert_href(day):
            base = url_for("raghibin.page")
            sep = "&" if "?" in base else "?"
            return f"{base}{sep}tab=daily&d={int(day)}"

        return alerts_context(year, month, _alert_href)
    except Exception:  # noqa: BLE001 — التنبيهات لا تسقط الصفحة أبدًا
        return {}


def _cadres_vars(year, month, entity, selected):
    """متغيرات تاب «الجهات والكوادر المعتمدة» (تصميم الاسكرين شوت ١٠/١٠):
    توقيتات الاعتماد + المسح الضوئي + السجل المعتمد + كشف القطع."""
    sid = request.args.get("sid", "")
    variables = {"sel_day": selected,
                 "pieces_count": len(dt.list_entities(year, month)),
                 "ranks_map": {"officers": dr.RANKS["officers"],
                               "individuals": dr.RANKS["individuals"]}}
    if entity:
        variables["registry_officers"] = dr.list_persons(
            year, month, entity_id=entity["id"], category="officers")
        variables["registry_individuals"] = dr.list_persons(
            year, month, entity_id=entity["id"], category="individuals")
        variables["approval"] = dr.get_approval(year, month, entity["id"], selected)
        variables["scan_img_url"] = (
            f"/raghibin/scan/img?e={entity['id']}&d={selected}"
            + (f"&sid={quote(sid)}" if sid else ""))
        variables["entity_count"] = len(variables["registry_officers"]) \
            + len(variables["registry_individuals"])
    else:
        variables["registry_officers"] = []
        variables["registry_individuals"] = []
        variables["approval"] = None
        variables["scan_img_url"] = ""
        variables["entity_count"] = 0
    return variables


@raghibin_bp.route("")
@raghibin_bp.route("/")
@login_required
def page():
    tab = request.args.get("tab", "daily")
    if tab not in TAB_KEYS:
        tab = "daily"
    variables = _page_vars(tab)
    year, month = variables["year"], variables["month"]
    entity = variables["entity"]
    if tab == "daily":
        selected = _selected_day(year, month)
        variables.update(_daily_vars(year, month, entity, selected))
    elif tab == "excluded":
        variables.update(_excluded_vars(year, month, entity, variables["q"]))
    elif tab == "monthly":
        variables.update(_monthly_vars(year, month, entity, variables["fcat"]))
    elif tab == "cadres":
        variables.update(_cadres_vars(year, month, entity, _selected_day(year, month)))
    return render_template("raghibin/main.html", **variables)


@raghibin_bp.route("/files/rebuild", methods=["POST"])
@login_required
def files_rebuild():
    """إعادة بناء كل الملفات المحلية للشهر بالدباجة والتوقيعين الرسميين واللوجو
    (يعيد كتابة كل الملفات الحالية — لتجديد الملفات القديمة التي قبل القواعد)."""
    year, month = _ctx()
    ents, days = rfs.rebuild_all(year, month)
    ok = (f"اتعدلت كل الملفات المحلية عن {MONTH_NAMES[month - 1]} {arnum.to_arabic_indic(year)} "
          f"بالدباجة والتوقيعين الرسميين واللوجو — {arnum.to_arabic_indic(ents)} جهة "
          f"وعلي {arnum.to_arabic_indic(days)} يوم يومية.")
    return _rb("files", ok=ok)
