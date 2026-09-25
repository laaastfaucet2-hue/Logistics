# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مسارات «تأميدات اليوم المحدد» — الصفحة الرئيسية + إضافة/تعديل/حذف/لصق التأميدة."""

from flask import render_template, request
from core.auth_core import login_required
from core import arabic_numbers as arnum
from core import dates
from core import egtime
import json
from data_access import db_tameedat as dt
from data_access import db_tameed_rations as snap

from . import TAB_KEYS, tameedat_bp
from .context import _after_write, _ctx, _page_vars, _parse_attachments, _parse_counts, _parse_day_form, _parse_from_to, _parse_range, _rag_warning, _rb, _posted_type


def _store_custom_rations(year, month, record_id):
    raw = (request.form.get("custom_rations_json") or "").strip()
    if not raw:
        return
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return
    if isinstance(payload, dict):
        snap.save_payload(year, month, record_id, payload)


# ======================================================================
# الصفحة الرئيسية — التويبات الأربعة
# ======================================================================
@tameedat_bp.route("")
@tameedat_bp.route("/")
@login_required
def page():
    tab = request.args.get("tab", "day")
    if tab not in TAB_KEYS:
        tab = "day"
    return render_template("tameedat/main.html", **_page_vars(tab))


# ======================================================================
# تأميدات اليوم: إضافة / تعديل / حذف ملحقة تلقائيًا مع السجل / لصق نسخة
# ======================================================================
@tameedat_bp.route("/records/add", methods=["POST"])
@login_required
def record_add():
    year, month = _ctx()
    try:
        if request.form.get("day") is None:            # الواجهة الحالية: من يوم / إلى يوم (لا ترسل تاريخًا كاملًا)
            day, day_to, range_days = _parse_from_to(year, month)
        else:                                          # مسار توافقي: تاريخ كامل + تفعيل مدة
            day = _parse_day_form(year, month)
            day_to, range_days = _parse_range(year, month, day)
        counts = _parse_counts()
        attachments = _parse_attachments()
        name = " ".join((request.form.get("entity_name") or "").split())
        if not name:
            raise ValueError("اكتب اسم الجهة أولًا")
        entity = dt.find_entity_by_name(year, month, name)
        new_entity = entity is None
        # منع الازدواج: نفس إرسال النموذج لا يسجّل تأميدتين مهما تكرر
        date_text = dates.format_date(f"{year:04d}-{month:02d}-{day:02d}")
        if not dt.claim_save_token(year, month, request.form.get("save_token")):
            return _rb(day=f"{year:04d}-{month:02d}-{day:02d}",
                       ok=f"تأميدة «{(entity or {'name': name})['name']}» يوم {date_text} "
                          "محفوظة بالفعل في البيانات المحلية — تجاهلنا الإرسال المكرر "
                          "تلقائيًا حتى لا تتسجل تأميدة مضاعفة.")
        if new_entity:
            entity_type = _posted_type()
            entity_id = dt.add_entity(year, month, name, entity_type)
            entity = dt.get_entity(year, month, entity_id)
        # الجهات الملحقة تُسجّل أيضًا في قاموس الشهر — تعامل كجهة كاملة بنفسها
        new_attached = []
        for att in attachments:
            att_name = " ".join((att.get("name") or "").split())
            if att_name and not dt.find_entity_by_name(year, month, att_name):
                dt.add_entity(year, month, att_name,
                              (att.get("entity_type") or entity["entity_type"]).strip()
                              or "شرطية")
                new_attached.append(att_name)
        new_id = dt.add_record(year, month, day, entity,
                      counts["officers"], counts["individuals"], counts["recruits"],
                      request.form.get("notes"), attachments, day_to=day_to)
        _store_custom_rations(year, month, new_id)
        _after_write(year, month)
    except ValueError as exc:
        return _rb(err=str(exc))
    date_text = dates.format_date(f"{year:04d}-{month:02d}-{day:02d}")
    ok = (f"تم حفظ بيانات تأميدة «{entity['name']}» يوم {date_text} "
          "وتسجيلها في البيانات المحلية.")
    if range_days > 1:
        end_text = dates.format_date(f"{year:04d}-{month:02d}-{day_to:02d}")
        ok += (f" المدة الزمنية مفعّلة: من {date_text} إلى {end_text} "
               f"({arnum.to_arabic_indic(range_days)} أيام) — تظهر سارية في كل أيامها.")
    if new_entity:
        ok += " الجهة كانت غير مسجلة فأُضيفت إلى قاموس الشهر كما طلبت."
    if new_attached:
        listed = "، ".join(f"«{n}»" for n in new_attached[:3])
        ok += f" الجهة الملحقة {listed} أُضيفت هي الأخرى إلى قاموس الشهر تلقائيًا."
    return _rb(day=f"{year:04d}-{month:02d}-{day:02d}", ok=ok,
               warn=_rag_warning(entity, counts))


@tameedat_bp.route("/records/edit/<int:record_id>", methods=["POST"])
@login_required
def record_edit(record_id):
    year, month = _ctx()
    record = dt.get_record(year, month, record_id)
    if not record:
        return _rb(err="التأميدة المطلوبة غير موجودة في هذا الشهر")
    try:
        if request.form.get("day") is None:            # الواجهة الحالية: من يوم / إلى يوم (لا ترسل تاريخًا كاملًا)
            day, day_to, range_days = _parse_from_to(year, month)
        else:                                          # مسار توافقي: تاريخ كامل + تفعيل مدة
            day = _parse_day_form(year, month)
            day_to, range_days = _parse_range(year, month, day)
        counts = _parse_counts()
        attachments = _parse_attachments()
        for att in attachments:  # الملحقات الجديدة تنضم لقاموس الشهر كجهة بنفسها
            att_name = " ".join((att.get("name") or "").split())
            if att_name and not dt.find_entity_by_name(year, month, att_name):
                dt.add_entity(year, month, att_name,
                              (att.get("entity_type") or record["entity_type"]).strip()
                              or "شرطية")
        dt.update_record(year, month, record_id, day,
                         counts["officers"], counts["individuals"], counts["recruits"],
                         request.form.get("notes"), attachments, day_to=day_to)
        _store_custom_rations(year, month, record_id)
        _after_write(year, month)
    except ValueError as exc:
        return _rb(tab="day", err=str(exc), edit=record_id)
    entity = dt.get_entity(year, month, record["entity_id"]) or record
    date_text = dates.format_date(f"{year:04d}-{month:02d}-{day:02d}")
    ok = (f"تم تعديل بيانات تأميدة «{record['entity_name']}» يوم {date_text} "
          "وحفظ التعديلات في البيانات المحلية.")
    if range_days > 1:
        end_text = dates.format_date(f"{year:04d}-{month:02d}-{day_to:02d}")
        ok += f" المدة الزمنية أصبحت من {date_text} إلى {end_text}."
    return _rb(day=f"{year:04d}-{month:02d}-{day:02d}", ok=ok,
               warn=_rag_warning(entity, counts))


@tameedat_bp.route("/records/copy/<int:record_id>", methods=["POST"])
@login_required
def record_paste(record_id):
    """لصق التأميدة المنسوخة كسجل منفصل في يوم آخر من الشهر نفسه."""
    year, month = _ctx()
    source = dt.get_record(year, month, record_id)
    if not source:
        return _rb(err="لا توجد تأميدة منسوخة صالحة — انسخها أولًا")
    target_day = arnum.parse_int(request.form.get("to_day"))
    if target_day is None or not 1 <= target_day <= egtime.days_in_month(year, month):
        return _rb(copy=record_id, err="اختر يومًا صحيحًا داخل الشهر النشط للصق")
    new_id = dt.copy_record(year, month, record_id, target_day)
    snap.copy_payload(year, month, record_id, new_id)
    _after_write(year, month)
    date_text = dates.format_date(f"{year:04d}-{month:02d}-{target_day:02d}")
    return _rb(day=f"{year:04d}-{month:02d}-{target_day:02d}",
               ok=f"تم لصق نسخة منفصلة من تأميدة «{source['entity_name']}» يوم "
                  f"{date_text} (سجل جديد رقم {arnum.to_arabic_indic(new_id)}) "
                  f"بالجهات المومدة الملحقة عليها ({arnum.to_arabic_indic(len(source['attachments']))} ملحقة) "
                  "وتسجيلها في البيانات المحلية.")


@tameedat_bp.route("/records/delete/<int:record_id>", methods=["POST"])
@login_required
def record_delete(record_id):
    """حذف نهائي للتأميدة وملحقاتها — بعد تأكيد المستخدم من المتصفح."""
    year, month = _ctx()
    record = dt.get_record(year, month, record_id)
    if not record:
        return _rb(err="التأميدة المطلوبة غير موجودة في هذا الشهر")
    entity_name = record["entity_name"]
    date_text = dates.format_date(f"{year:04d}-{month:02d}-{record['day']:02d}")
    dt.delete_record(year, month, record_id)
    _after_write(year, month)
    return _rb(day=f"{year:04d}-{month:02d}-{record['day']:02d}",
               ok=f"تم حذف تأميدة «{entity_name}» يوم {date_text} "
                  "مع ملحقاتها من البيانات المحلية.")


