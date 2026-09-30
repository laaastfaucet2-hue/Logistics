# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تاب «الراغبين (يومي)» + جزء المربعات المشترك مع زرار التأميدة (ربط بالاتجاهين).

النموذج (توجيه المستخدم ٣٠/٠٩/٢٠٢٦): حسب تأميدة اليوم تظهر مربعات فاضية ذكية —
١٠ ضباط في التأميدة = ١٠ مربعات ضباط و١٠ للأفراد — تكتب الاسم بالبحث الذكي من
«الجهات والكوادر»، وأي اسم جديد يسأل «هل تريد إضافته كقوة دائمة للجهة؟»
فيدخل تلقائيًا في قوة الكوادر. الحفظ clear-and-set: المربعات هي كشف الراغبين
كاملًا لذلك اليوم/الفئة — ومن يحذف من مربع يُلغى رغبته.

/daily/save: حفظ أسماء فئة بيوم (من التاب أو من زرار التأميدة — نفس الداتا
ونفس بناء الملفات لحظيًا) · /panel: جزء HTML للمربعات (يُضمَّن في التاب ويُجلب
أجاكسًا في مودال التأميدات).
"""
import json

from flask import render_template, request

from core import arabic_numbers as arnum
from core.auth_core import login_required
from data_access import db_raghibin as dr
from services import raghibin as rfs

from . import raghibin_bp
from .context import (_category, _ctx, _entity_or_back, _rb, _selected_day,
                      _selected_entity, _slots_vars)


@raghibin_bp.route("/panel")
@login_required
def panel():
    """جزء مربعات الراغبين — للتضمين في التاب اليومي وللمودال في التأميدات."""
    year, month = _ctx()
    entity = _selected_entity(year, month, by_name=True)
    day = _selected_day(year, month)
    cat = _category()
    variables = _slots_vars(year, month, entity, day)
    variables.update({
        "fcat": cat, "entity": entity, "sel_day": day,
        "back": request.args.get("back", "raghibin"),
        "source": request.args.get("source", "manual"),
    })
    return render_template("raghibin/panel_slots.html", **variables)


@raghibin_bp.route("/daily/save", methods=["POST"])
@login_required
def daily_save():
    year, month = _ctx()
    entity, back = _entity_or_back(year, month, "daily")
    if back:
        return back
    day = _selected_day(year, month)
    cat = _category()
    if request.form.get("cat") in dict(dr.CATEGORIES):
        cat = request.form.get("cat")
    source = "tamida" if request.form.get("source") == "tamida" else "manual"
    back_to = "tameedat" if request.form.get("back") == "tameedat" else "raghibin"

    names = []
    for raw in request.form.getlist("names"):
        name = " ".join((raw or "").split())
        if name and name not in names:
            names.append(name)
    try:
        confirmed_new = {n for n in (json.loads(request.form.get("new_names") or "[]")
                                     if request.form.get("new_names") else [])}
    except json.JSONDecodeError:
        confirmed_new = set()

    warnings, added, resolved_ids = [], [], []
    for name in names:
        person = dr.find_person(year, month, entity["id"], cat, name)
        if person is None and name in confirmed_new:
            dr.add_person(year, month, entity["id"], cat, name)
            added.append(name)
            person = dr.find_person(year, month, entity["id"], cat, name)
        if person is None:
            warnings.append(f"«{name}» غير موجود في القوة ولم يؤكد إضافته — تجاهلناه")
            continue
        if person["excluded"]:
            reason = person["exclude_note"] or "بدون سبب"
            warnings.append(f"«{name}» مستثنى «غير راغب» ({reason}) — تجاهلناه")
            continue
        resolved_ids.append(person["id"])

    count, removed = dr.set_day_category(year, month, entity["id"], day, cat,
                                         resolved_ids, source=source)
    rfs.write_entity_files(year, month, entity["id"], entity["name"], day=day)

    label = dict(dr.CATEGORIES)[cat]
    day_txt = arnum.to_arabic_indic(str(day))
    ok = f"تم تسجيل {arnum.to_arabic_indic(str(count))} راغبين ({label}) يوم {day_txt}"
    if added:
        ok += f" — أُضيفوا للقوة الدائمة: {'، '.join(added)}"
    if removed:
        ok += f" — وأُلغيت رغبة {arnum.to_arabic_indic(str(removed))}" \
              f" محذوفين من المربعات"
    warn = " | ".join(warnings) if warnings else None

    if back_to == "tameedat":
        from urllib.parse import quote
        from flask import redirect, url_for
        from core.auth_core import current_session
        _, token = current_session()
        params = {"tab": "day", "day": f"{year:04d}-{month:02d}-{day:02d}"}
        if token:
            params["sid"] = token
        if ok:
            params["ok"] = ok
        if warn:
            params["warn"] = warn
        base = url_for("tameedat.page")
        separator = "&" if "?" in base else "?"
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return redirect(f"{base}{separator}{query}")
    return _rb("daily", e=entity["id"], d=day, c=cat, ok=ok, warn=warn)
