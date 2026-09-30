# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تاب «الراغبين (يومي)» + كشف الراغبين في التأميدات (ربط بالاتجاهين).

النموذج (توجيه المستخدم ٣٠/٠٩/٢٠٢٦): حسب تأميدة اليوم تظهر مربعات فاضية ذكية —
١٠ ضباط في التأميدة = ١٠ مربعات ضباط و١٠ للأفراد — تكتب الاسم بالبحث الذكي من
«الجهات والكوادر»، وأي اسم جديد يسأل «هل تريد إضافته كقوة دائمة للجهة؟»
فيدخل تلقائيًا في قوة الكوادر. الحفظ clear-and-set: المربعات هي كشف الراغبين
كاملًا لذلك اليوم/الفئة — ومن يحذف من مربع يُلغى رغبته.

التوجيه النهائي (٣٠/٠٩/٢٠٢٦ مساءً): زرار التأميدة يفتح **صفحة كاملة عادية**
/modal — بنفس آلية كل صفحات النظام (sid في الرابط) — من غير أي جلب خفي:
fetch اتشال من المنظومة كلها لأنه مصدر العطل المتكرر مع الجلسات.
/modal: الصفحة الكاملة · /panel: جزء legacy · /panel/quick_add و/panel/delete:
إضافة سريعة وحذف يرجعون لصفحة الكشف بتحويل عادي · /daily/save: الحفظ الموحد.
"""
import json

from flask import redirect, render_template, request
from urllib.parse import quote

from core import arabic_numbers as arnum
from core.auth_core import login_required
from data_access import db_raghibin as dr
from data_access import db_tameedat as dt
from services import raghibin as rfs
from services.raghibin import modal as rg_modal

from . import raghibin_bp
from .context import (_category, _ctx, _entity_or_back, _rb, _selected_day,
                      _selected_entity)


def _modal_page_url(entity, day, cat, sid=""):
    """رابط صفحة كشف الراغبين الكاملة (تصفح عادي — sid في الرابط)."""
    url = f"/raghibin/modal?c={cat}&d={day}&en={quote(entity['name'])}"
    return url + (f"&sid={quote(sid)}" if sid else "")


@raghibin_bp.route("/modal")
@login_required
def modal_page():
    """صفحة «كشف وتسجيل أسماء الضباط والأفراد الراغبين» الكاملة."""
    from flask import url_for
    year, month = _ctx()
    entity = _selected_entity(year, month, by_name=True)
    day = _selected_day(year, month)
    cat = _category()
    sid = request.values.get("sid", "")
    variables = rg_modal.build(year, month, entity, day, cat, sid=sid)
    # url_for('tameedat.page') بيحمل ?year&month&sid تلقائيًا (url_defaults) — فالفاصل &
    back = url_for("tameedat.page")
    back += ("&" if "?" in back else "?") + "tab=day"
    variables["tameed_back"] = back + (f"&sid={quote(sid)}" if sid else "")
    return render_template("raghibin/modal_page.html", **variables)


@raghibin_bp.route("/panel")
@login_required
def panel():
    """جزء المودال (legacy) — نفس محتوى الصفحة الكاملة بدون هيكل الصفحة."""
    year, month = _ctx()
    entity = _selected_entity(year, month, by_name=True)
    day = _selected_day(year, month)
    return _modal_fragment(year, month, entity, day, _category())


@raghibin_bp.route("/panel/quick_add", methods=["POST"])
@login_required
def panel_quick_add():
    """«إضافة عضو جديد سريع إلى قوة الجهة» — ثم رجوع لصفحة الكشف (تصفح عادي)."""
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
    return redirect(_modal_page_url(entity, day, cat, request.form.get("sid", "")))


@raghibin_bp.route("/panel/delete/<int:person_id>", methods=["POST"])
@login_required
def panel_delete(person_id):
    """حذف اسم من القوة من صفحة الكشف — ثم رجوع إليها (تصفح عادي)."""
    year, month = _ctx()
    person = dr.get_person(year, month, person_id)
    if person:
        dr.delete_person(year, month, person_id)
        rfs.write_entity_files(year, month, person["entity_id"], person["entity_name"])
        entity = dt.get_entity(year, month, person["entity_id"])
        return redirect(_modal_page_url(entity, _selected_day(year, month),
                                        person["category"],
                                        request.form.get("sid", "")))
    entity, back = _entity_or_back(year, month)
    if back:
        return back
    return redirect(_modal_page_url(entity, _selected_day(year, month),
                                    _category(), request.form.get("sid", "")))


def _modal_fragment(year, month, entity, day, cat):
    """جزء المودال — عبر الخدمة المشتركة (نفس محتوى الصفحة الكاملة)."""
    variables = rg_modal.build(year, month, entity, day, cat,
                               sid=request.values.get("sid", ""))
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
    back_to = request.form.get("back", "raghibin")

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
        from core.auth_core import current_session
        from flask import url_for
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
