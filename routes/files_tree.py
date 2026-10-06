# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 خط — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مسار حصر الملفات المحلية 📁 — يُغذّي لوحة الشجرة في صفحتي التاميدات والراغبين.

GET /files/tree?section=tameedat|raghibin  → شجرة كاملة (أسماء/أحجام/آخر تحديث)
تُقرأ من القرص في كل نداء، فالصفحة تعرض حالة الملفات الحقيقية لا نسخة مخزّنة.
"""
from flask import Blueprint, jsonify, request

from core.auth_core import current_context, current_session, login_required
from services import files_index

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
