# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 خط — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مسار حصر الملفات المحلية 📁 — يُغذّي لوحة الشجرة في صفحتي التاميدات والراغبين.

GET /files/tree?section=tameedat|raghibin  → شجرة كاملة (أسماء/أحجام/آخر تحديث)
تُقرأ من القرص في كل نداء، فالصفحة تعرض حالة الملفات الحقيقية لا نسخة مخزّنة.
"""
from flask import Blueprint, jsonify, request

from core.auth_core import current_context, current_session, login_required
from services import files_index, local_audit

files_tree_bp = Blueprint("files_tree", __name__, url_prefix="/files")


@files_tree_bp.route("/tree")
@login_required
def tree():
    user, token = current_session()
    year, month = current_context(user["id"])
    section = (request.args.get("section") or "tameedat").strip()
    if section not in files_index.SECTIONS_INDEX:
        return jsonify({"ok": False, "error": "قسم غير معروف"}), 400
    try:
        fresh = int(request.args.get("fresh") or 25)
    except ValueError:
        fresh = 25
    payload = files_index.build_tree(section, year, month, fresh_seconds=fresh)
    payload["sid"] = token or ""
    return jsonify(payload)


@files_tree_bp.route("/audit")
@login_required
def audit():
    """الفحص الذكي 🛡️ — الدباجة واللوجو والتوقيعان على كل ملفات الشهر المحلية.

    GET /files/audit?section=tameedat|raghibin|both  ⇒ تقرير كامل (قراءة فقط).
    """
    user, token = current_session()
    year, month = current_context(user["id"])
    section = (request.args.get("section") or "both").strip()
    if section == "both":
        payload = local_audit.audit_month(year, month)
    elif section in files_index.SECTIONS_INDEX:
        root = files_index.section_root(section, year, month)
        part = local_audit.audit_tree(root, year, month)
        payload = {"year": year, "month": month, "checked": part["checked"],
                   "ok": part["ok"], "problems": part["problems"],
                   "sections": {section: {"checked": part["checked"], "ok": part["ok"],
                                          "problems": len(part["problems"]),
                                          "folder": str(root)}}}
    else:
        return jsonify({"ok": False, "error": "قسم غير معروف"}), 400
    payload["ok"] = not payload["problems"]
    payload["sid"] = token or ""
    return jsonify(payload)


@files_tree_bp.route("/audit-page")
@login_required
def audit_page():
    """صفحة الفحص الذكي — تُعرض من أي صفحة فيها ملخص الملفات."""
    from flask import render_template
    user, token = current_session()
    year, month = current_context(user["id"])
    section = (request.args.get("section") or "both").strip()
    known = ("tameedat", "raghibin")
    if section in known:
        report = local_audit.audit_month(year, month, sections=(section,))
    else:
        report = local_audit.audit_month(year, month)
    return render_template("files_audit.html", year=year, month=month, report=report,
                           sid=token or "", section=section)
