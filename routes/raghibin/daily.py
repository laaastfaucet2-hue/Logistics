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
from data_access import db_tameedat as dt
from services import raghibin as rfs

from . import raghibin_bp
from .context import (_category, _ctx, _entity_or_back, _rb, _selected_day,
                      _selected_entity, _slots_vars)


@raghibin_bp.route("/panel")
@login_required
def panel():
    """جسم مودال الراغبين في التأميدات — نفس تصميم النظام المرجعي للمستخدم:
    الجهة المختارة + إضافة سريعة + قائمة القوة بتشيكات + قسمة المربعات."""
    year, month = _ctx()
    entity = _selected_entity(year, month, by_name=True)
    day = _selected_day(year, month)
    return _modal_fragment(year, month, entity, day, _category())


@raghibin_bp.route("/panel/quick_add", methods=["POST"])
@login_required
def panel_quick_add():
    """«إضافة عضو جديد سريع إلى قوة الجهة» من داخل المودال — يرجع الجزء محدثًا."""
    year, month = _ctx()
    entity, back = _entity_or_back(year, month)
    if back:
        return back
    day = _selected_day(year, month)
    cat = request.form.get("qa_cat") if request.form.get("qa_cat") in dr.CATEGORY_KEYS \
        else _category()
    name = " ".join((request.form.get("qa_name") or "").split())
    if name:
        dr.add_person(year, month, entity["id"], cat, name,
                      rank=(request.form.get("qa_rank") or "").strip(),
                      exclude_note=(request.form.get("qa_note") or "").strip())
        rfs.write_entity_files(year, month, entity["id"], entity["name"], day=day)
    return _modal_fragment(year, month, entity, day, cat)


@raghibin_bp.route("/panel/delete/<int:person_id>", methods=["POST"])
@login_required
def panel_delete(person_id):
    """حذف اسم من القوة من داخل المودال (🗑) — يرجع الجزء محدثًا."""
    year, month = _ctx()
    person = dr.get_person(year, month, person_id)
    if person:
        dr.delete_person(year, month, person_id)
        rfs.write_entity_files(year, month, person["entity_id"], person["entity_name"])
        entity = dt.get_entity(year, month, person["entity_id"])
        return _modal_fragment(year, month, entity, _selected_day(year, month),
                               person["category"])
    entity, back = _entity_or_back(year, month)
    return back if back else _modal_fragment(year, month, entity,
                                             _selected_day(year, month), _category())


def _modal_fragment(year, month, entity, day, cat):
    """بناء جزء المودال الموحد: قوة الفئة بعلامات اليوم + المربعات + الإضافة السريعة."""
    variables = _slots_vars(year, month, entity, day)
    state = dr.day_state(year, month, day, entity["id"]) if entity else {}
    persons = dr.list_persons(year, month, entity_id=entity["id"], category=cat) \
        if entity else []
    for person in persons:
        person["willing_today"] = state.get(person["id"])
    variables.update({
        "fcat": cat, "entity": entity, "sel_day": day,
        "force_persons": persons,
        "categories": dr.CATEGORIES,
        "officer_ranks": dr.RANKS["officers"],
        "individual_ranks": dr.RANKS["individuals"],
        "ranks_map": {"officers": dr.RANKS["officers"],
                      "individuals": dr.RANKS["individuals"]},
        "sid": request.values.get("sid", ""),
    })
    return render_template("raghibin/modal_body.html", **variables)


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
