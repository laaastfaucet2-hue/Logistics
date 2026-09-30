# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تاب «الجهات والكوادر المعتمدة» — قوة الجهات بالأسماء والرتب وحالة الرغبة.

كل تعديل يُبنى بعده ملفا القوة (ضباط/أفراد) للجهة لحظيًا عبر
services.raghibin.files_rosters — ونسخ القوة لشهر/سنة آخر يبني كل ملفاته.
(منع التكرار ومطابقة الأسماء داخل db_raghibin نفسه.)
"""
from flask import request

from core.auth_core import login_required
from data_access import db_raghibin as dr
from data_access import db_tameedat as dt
from services import raghibin as rfs

from . import raghibin_bp
from .context import _category, _ctx, _rb


def _entity_or_back(year, month):
    """الجهة الهدف من النموذج (?e أو e في الفورم) — لو مفقودة رجوع بتنبيه."""
    raw = request.form.get("e") or request.args.get("e") or ""
    try:
        entity = dt.get_entity(year, month, int(raw))
    except ValueError:
        entity = None
    if not entity:
        return None, _rb("cadres", err="اختر جهة أولًا")
    return entity, None


@raghibin_bp.route("/cadres/add", methods=["POST"])
@login_required
def cadres_add():
    year, month = _ctx()
    entity, back = _entity_or_back(year, month)
    if back:
        return back
    category = _category()
    if request.form.get("cat") in dict(dr.CATEGORIES):
        category = request.form.get("cat")
    name = (request.form.get("name") or "").strip()
    rank = (request.form.get("rank") or "").strip()
    if not name:
        return _rb("cadres", e=entity["id"], c=category, err="اكتب الاسم الرتبعي الكامل")
    person_id, created = dr.add_person(year, month, entity["id"], category, name, rank)
    rfs.write_cadres_files(year, month, entity["id"], entity["name"])
    if created:
        return _rb("cadres", e=entity["id"], c=category,
                   ok=f"تم إضافة {name} إلى قوة {entity['name']}")
    return _rb("cadres", e=entity["id"], c=category, warn=f"{name} موجود بالفعل في القوة")


@raghibin_bp.route("/cadres/exclude/<int:person_id>", methods=["POST"])
@login_required
def cadres_exclude(person_id):
    year, month = _ctx()
    person = dr.get_person(year, month, person_id)
    if not person:
        return _rb("cadres", err="الاسم غير موجود")
    exclude = request.form.get("state", "1") == "1"
    note = (request.form.get("note") or "").strip()
    if exclude and not note:
        return _rb("cadres", e=person["entity_id"], c=person["category"],
                   x=person_id, warn="اكتب سبب الاستثناء (هلاكات/مأمورية/...) ثم أكد")
    dr.set_excluded(year, month, person_id, exclude, note)
    rfs.write_cadres_files(year, month, person["entity_id"], person["entity_name"])
    if exclude:
        return _rb("cadres", e=person["entity_id"], c=person["category"],
                   ok=f"{person['full_name']} الآن «غير راغب» ولن يُحسب في الوجبات")
    return _rb("cadres", e=person["entity_id"], c=person["category"],
               ok=f"تم إرجاع {person['full_name']} للقوة الراغبة")


@raghibin_bp.route("/cadres/delete/<int:person_id>", methods=["POST"])
@login_required
def cadres_delete(person_id):
    year, month = _ctx()
    person = dr.get_person(year, month, person_id)
    if not person:
        return _rb("cadres", err="الاسم غير موجود")
    dr.delete_person(year, month, person_id)
    rfs.write_cadres_files(year, month, person["entity_id"], person["entity_name"])
    return _rb("cadres", e=person["entity_id"], c=person["category"],
               ok=f"تم حذف {person['full_name']} من القوة")


@raghibin_bp.route("/cadres/copy", methods=["POST"])
@login_required
def cadres_copy():
    year, month = _ctx()
    try:
        target_year = int(request.form.get("ty") or 0)
        target_month = int(request.form.get("tm") or 0)
        if not (2000 <= target_year <= 2100 and 1 <= target_month <= 12):
            raise ValueError
    except ValueError:
        return _rb("cadres", err="حدد سنة وشهر هدف صحيحين")
    scope = request.form.get("scope", "one")
    entity_ids = None
    if scope != "all":
        entity, back = _entity_or_back(year, month)
        if back:
            return back
        entity_ids = [entity["id"]]
    copied_entities, copied_names = dr.copy_force(year, month, target_year,
                                                  target_month, entity_ids)
    if copied_entities:
        rfs.write_all_cadres(target_year, target_month)
    return _rb("cadres",
               ok=f"تم نسخ قوة {copied_entities} جهة "
                  f"({copied_names} اسم) إلى الشهر الهدف وملفاتها اتبنت هناك")
