# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تاب «الجهات والكوادر المعتمدة» — قوة الجهات بالأسماء والرتب وحالة الرغبة.

كل تعديل يُبنى بعده ملفا القوة (ضباط/أفراد) للجهة لحظيًا عبر
services.raghibin.files_rosters — ونسخ القوة لشهر/سنة آخر يبني كل ملفاته.
(منع التكرار ومطابقة الأسماء داخل db_raghibin نفسه.)
"""
from flask import request

from core import arabic_numbers as arnum
from core.auth_core import login_required
from data_access import db_raghibin as dr
from data_access import db_tameedat as dt
from services import raghibin as rfs

from . import raghibin_bp
from .context import _category, _ctx, _entity_or_back, _rb


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
    rfs.write_entity_files(year, month, entity["id"], entity["name"])
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
    rfs.write_entity_files(year, month, person["entity_id"], person["entity_name"])
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
    rfs.write_entity_files(year, month, person["entity_id"], person["entity_name"])
    return _rb("cadres", e=person["entity_id"], c=person["category"],
               ok=f"تم حذف {person['full_name']} من القوة")


@raghibin_bp.route("/cadres/note/<int:person_id>", methods=["POST"])
@login_required
def cadres_note(person_id):
    """📝 تحرير ملاحظة اسم من القوة — من غير تغيير حالته (راغب/غير راغب)."""
    year, month = _ctx()
    person = dr.get_person(year, month, person_id)
    if not person:
        return _rb("cadres", err="الاسم غير موجود")
    note = " ".join((request.form.get("note") or "").split())
    dr.set_note(year, month, person_id, note)
    rfs.write_entity_files(year, month, person["entity_id"], person["entity_name"])
    if note:
        return _rb("cadres", e=person["entity_id"], c=person["category"],
                   ok=f"📝 تم حفظ ملاحظة {person['full_name']}: {note}")
    return _rb("cadres", e=person["entity_id"], c=person["category"],
               ok=f"تم حذف ملاحظة {person['full_name']}")


@raghibin_bp.route("/cadres/entity_add", methods=["POST"])
@login_required
def cadres_entity_add():
    """➕ إضافة جهة جديدة للقوة مباشرة من تاب الكوادر (بنفس نوع القاموس)."""
    year, month = _ctx()
    name = " ".join((request.form.get("new_name") or "").split())
    if not name:
        return _rb("cadres", err="اكتب اسم الجهة أولًا")
    if dt.find_entity_by_name(year, month, name):
        return _rb("cadres", warn=f"الجهة «{name}» موجودة بالفعل في القوة")
    entity_type = (request.form.get("new_type") or "شرطية").strip() or "شرطية"
    entity_id = dt.add_entity(year, month, name, entity_type)
    rfs.write_entity_files(year, month, entity_id, name)
    return _rb("cadres", e=entity_id,
               ok=f"تم إضافة جهة «{name}» ({entity_type}) وبناء ملفاتها — أضف قوتها من الفورم تحت")


@raghibin_bp.route("/cadres/entity_delete/<int:entity_id>", methods=["POST"])
@login_required
def cadres_entity_delete(entity_id):
    """🗑 حذف جهة وكل أسمائها (وقسمتها في قاموس الشهر) + تنظيف ملفاتها."""
    year, month = _ctx()
    entity = dt.get_entity(year, month, entity_id)
    if not entity:
        return _rb("cadres", err="الجهة غير موجودة")
    removed_records = dt.delete_entity(year, month, entity_id)
    removed_files = rfs.remove_entity_files(year, month, entity["name"])
    ok = f"تم حذف جهة «{entity['name']}» وكل أسمائها من هذا الشهر"
    if removed_records:
        ok += f" (معها {arnum.to_arabic_indic(str(removed_records))} تأميدة مسجلة)"
    if removed_files:
        ok += f" و{arnum.to_arabic_indic(str(removed_files))} ملف محلي لها"
    return _rb("cadres", ok=ok)


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
        rfs.write_all(target_year, target_month)
    return _rb("cadres",
               ok=f"تم نسخ قوة {copied_entities} جهة "
                  f"({copied_names} اسم) إلى الشهر الهدف وملفاتها اتبنت هناك")
