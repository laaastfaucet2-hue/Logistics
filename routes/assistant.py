# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 خط — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مسارات المساعد المحلي 🤖 — بلا إنترنت وبلا أي خدمة خارجية.

/assistant/ask  → سؤال/أمر بالعربية، والرد من محرك النوايا + بيانات الشهر النشط.
/assistant/prompts → الاقتراحات السريعة (اللوحة نفسها مدمجة في base.html).
"""
from flask import Blueprint, g, jsonify, request, url_for

from core.auth_core import current_context, current_session, login_required
from services import assistant as brain

assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")


def _destinations():
    return {dest[0]: dest for dest in brain.DESTINATIONS}


def _href(target, sid=""):
    """يحوّل معرّف الوجهة إلى رابط حقيقي داخل المنظومة."""
    if target == "help":
        return ""
    dest = _destinations().get(target)
    if not dest:
        return ""
    try:
        url = url_for(dest[2], **dest[3])       # url_defaults يضيف year/month للـendpoints المحددة
    except Exception:                            # noqa: BLE001 — رابط لا يوقف الرد أبدًا
        return ""
    if sid:
        url += ("&" if "?" in url else "?") + "sid=" + sid
    return url


@assistant_bp.route("/ask", methods=["POST", "GET"])
@login_required
def ask():
    """سؤال بالعربية → رد نصي + روابط جاهزة (يفتح أي تاب فورًا)."""
    question = (request.values.get("q") or "").strip()
    year, month = current_context(g.user["id"])
    _, sid = current_session()
    payload = brain.answer(question, year, month)
    links = []
    for link in payload.get("links") or []:
        href = _href(link.get("target"), sid or "")
        if href:
            links.append({"label": link["label"], "href": href})
    navigate = _href(payload.get("navigate"), sid or "") if payload.get("navigate") else ""
    return jsonify({"ok": True, "kind": payload["kind"], "reply": payload["reply"],
                    "links": links, "navigate": navigate,
                    "year": year, "month": month})


@assistant_bp.route("/prompts")
@login_required
def prompts():
    """الاقتراحات السريعة أعلى صندوق الكتابة."""
    return jsonify({"ok": True, "prompts": brain.quick_prompts()})
