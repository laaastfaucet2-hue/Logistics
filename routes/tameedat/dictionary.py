# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مسارات «قاموس ودليل الجهات» — إضافة/تعديل/حذف جهة القاموس الشهري."""

from flask import request
from core.auth_core import login_required
from core import arabic_numbers as arnum
from data_access import db_tameedat as dt

from . import tameedat_bp
from .context import _after_write, _ctx, _parse_optional_rag, _rb, _posted_type


# ======================================================================
# قاموس ودليل الجهات
# ======================================================================
@tameedat_bp.route("/entities/add", methods=["POST"])
@login_required
def entity_add():
    year, month = _ctx()
    try:
        name = " ".join((request.form.get("name") or "").split())
        if not name:
            raise ValueError("اكتب اسم الجهة أولًا")
        if dt.find_entity_by_name(year, month, name):
            raise ValueError(f"«{name}» موجودة بالفعل في قاموس هذا الشهر")
        rag = _parse_optional_rag()
        dt.add_entity(year, month, name, _posted_type(),
                      rag["rag_officers"], rag["rag_individuals"],
                      request.form.get("notes"))
        _after_write(year, month)
    except ValueError as exc:
        return _rb(tab="dict", err=str(exc))
    return _rb(tab="dict",
               ok=f"تم حفظ بيانات الجهة «{name}» في قاموس الشهر "
                  "وتسجيلها في البيانات المحلية.")


@tameedat_bp.route("/entities/edit/<int:entity_id>", methods=["POST"])
@login_required
def entity_edit(entity_id):
    year, month = _ctx()
    entity = dt.get_entity(year, month, entity_id)
    if not entity:
        return _rb(tab="dict", err="الجهة المطلوبة غير موجودة في قاموس هذا الشهر")
    try:
        name = " ".join((request.form.get("name") or "").split())
        if not name:
            raise ValueError("اكتب اسم الجهة أولًا")
        same = dt.find_entity_by_name(year, month, name)
        if same and same["id"] != entity_id:
            raise ValueError(f"«{name}» موجودة بالفعل في قاموس هذا الشهر")
        rag = _parse_optional_rag()
        dt.update_entity(year, month, entity_id, name, _posted_type(),
                         rag["rag_officers"], rag["rag_individuals"],
                         request.form.get("notes"))
        _after_write(year, month)
    except ValueError as exc:
        return _rb(tab="dict", err=str(exc), dedit=entity_id)
    return _rb(tab="dict",
               ok=f"تم تعديل بيانات الجهة «{name}» وحفظ التعديلات في البيانات المحلية.")


@tameedat_bp.route("/entities/delete/<int:entity_id>", methods=["POST"])
@login_required
def entity_delete(entity_id):
    """حذف جهة من قاموس الشهر + كل تأميداتها وملحقاتها داخل هذا الشهر فقط."""
    year, month = _ctx()
    entity = dt.get_entity(year, month, entity_id)
    if not entity:
        return _rb(tab="dict", err="الجهة المطلوبة غير موجودة في قاموس هذا الشهر")
    removed = dt.delete_entity(year, month, entity_id)
    _after_write(year, month)
    return _rb(tab="dict",
               ok=f"تم حذف الجهة «{entity['name']}» من قاموس الشهر"
                  + (f" ومعها {arnum.to_arabic_indic(removed)} تأميدة في هذا الشهر"
                     if removed else "")
                  + "، وحُفظ الحذف في البيانات المحلية.")


