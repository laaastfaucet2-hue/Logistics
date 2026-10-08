# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 خط — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مسارات المساعد المحلي — بلا إنترنت وبلا أي خدمة خارجية.

/assistant/ask          → سؤال/أمر بالعربية: رد كامل (نص + كتل + روابط + اقتراحات).
/assistant/prompts      → الاقتراحات السريعة (اللوحة نفسها مدمجة في base.html).
/assistant/model/select → قائمة «تبديل الموديل» في الشات: «المكتبة الذكية» أو موديل بالاسم.
/assistant/capabilities → القدرات + حالة النموذج المحلي (بصدق).

لا إعدادات ذكاء اصطناعي في الواجهة بتوجيه المستخدم: المستخدم ينزّل ملف GGUF بنفسه
ويضعه في `database/assistant/models/` (وملف «اقرأني» داخل الفولدر يشرح الخطوات).
"""
from flask import Blueprint, g, jsonify, request, url_for

from core.auth_core import current_context, current_session, login_required
from services import assistant as brain

assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")


def _destinations():
    return {dest[0]: dest for dest in brain.DESTINATIONS}


def _href(target, sid="", params=None):
    """يحوّل معرّف الوجهة إلى رابط حقيقي داخل المنظومة (فارغ لو غير متاح).

    `params` تُدمج فوق بارامترات الوجهة الثابتة — بها يصير رابط تنزيل يوم محدد
    («ملف تأميدات يوم ٧» ⇒ `/tameedat/day-file/7`) بلا أي مسار خاص في المساعد.
    """
    if not target or target == "help":
        return ""
    dest = _destinations().get(target)
    if not dest:
        return ""
    try:
        fixed = dict(dest[3])
        fixed.update(params or {})
        url = url_for(dest[2], **fixed)          # url_defaults يضيف year/month للـendpoints المحددة
    except Exception:                            # noqa: BLE001 — رابط لا يوقف الرد أبدًا
        return ""
    if sid:
        url += ("&" if "?" in url else "?") + "sid=" + sid
    return url


def _links(payload, sid):
    links = []
    for link in payload.get("links") or []:
        href = _href(link.get("target"), sid, link.get("params"))
        if href:
            links.append({"label": link["label"], "href": href})
    return links


@assistant_bp.route("/ask", methods=["POST", "GET"])
@login_required
def ask():
    """سؤال بالعربية → رد منظّم + روابط جاهزة (يفتح أي تاب فورًا)."""
    payload = request.get_json(silent=True) or {}
    question = (request.values.get("q") or payload.get("q") or "").strip()
    year, month = current_context(g.user["id"])
    _, sid = current_session()
    payload = brain.answer(question, year, month)
    return jsonify({
        "ok": True,
        "kind": payload.get("kind", "unknown"),
        "title": payload.get("title", ""),
        "reply": payload.get("reply", ""),
        "blocks": payload.get("blocks") or [],
        "links": _links(payload, sid or ""),
        "followups": payload.get("followups") or [],
        "navigate": _href(payload.get("navigate"), sid or "") if payload.get("navigate") else "",
        "year": year, "month": month,
    })


@assistant_bp.route("/prompts")
@login_required
def prompts():
    """الاقتراحات السريعة أعلى صندوق الكتابة."""
    return jsonify({"ok": True, "prompts": brain.quick_prompts()})


@assistant_bp.route("/model/select", methods=["POST"])
@login_required
def model_select():
    """قائمة «تبديل الموديل» في الشات: «المكتبة الذكية» أو موديل GGUF باسمه.

    بلا أي تنزيل: المستخدم ينزّل بنفسه ويضع الملف في `database/assistant/models/`،
    وهنا يُختار الفعّال من الموجود فقط (وبصدق عند غياب الملف أو تلفه).
    """
    from services.assistant import model as brain_model
    from services.assistant import model_store
    payload = request.get_json(silent=True) or {}
    ok, message = model_store.select(payload.get("name", ""))
    return jsonify({"ok": ok, "message": message,
                    "name": model_store.active_name(),
                    "label": model_store.label(),
                    "count": len(model_store.list_models()),
                    "folder": str(model_store.models_dir()),
                    "state": model_store.state(),
                    "status": brain_model.status()})


@assistant_bp.route("/capabilities")
@login_required
def capabilities():
    """القدرات + حالة النموذج المحلي — تُعرض على الواجهة بصدق (بلا تظاهر بالتوفّر)."""
    year, month = current_context(g.user["id"])
    payload = brain.capabilities(year, month)
    return jsonify({"ok": True, **payload})
