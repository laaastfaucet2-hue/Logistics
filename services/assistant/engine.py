# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""محرك المساعد المحلي — تصنيف النية ثم الإجابة: بيانات حقيقية أو معجم أو دليل أو تنقل.

الترتيب المُلزم: تحية/شكر/تعريف ← مساعدة ← مصطلحات وأدلة ← أمر تنقل صريح ←
أسئلة البيانات ← مطابقة تاب ضعيفة ← نموذج محلي (إن وُجد ملف GGUF) ← اقتراحات.

لا إنترنت ولا خدمة خارجية في أي خطوة، ولا تعديل لأي بيانات إطلاقًا.
"""
from core import arabic_numbers as arnum

from . import data_answers as data
from . import data_files as files_data
from . import data_rank as rank_data
from . import knowledge as K
from . import model as local_model
from . import text as T
from .destinations import DESTINATIONS, label as dest_label, resolve, wants_navigation


# ══════════════════════════════════════════════════════════════════════
# جدول المواضيع: (المفتاح، وزن أساس، كلمات مفتاحية، الدالة)
# ══════════════════════════════════════════════════════════════════════
TOPICS = [
    ("summary", 6, ["ملخص الشهر", "ملخص", "الوضع العام", "قولي الوضع", "الاحصائيات",
                    "احصائيات", "تقرير الشهر", "نظره عامه", "نظرة عامة", "الصوره العامه",
                    "الصورة العامة"], data.topic_summary),

    ("alerts", 6, ["تنبيهات", "التنبيهات", "في مشاكل", "مشاكل", "عدم التطابق",
                   "عدم تطابق", "تحذيرات", "اخطاء", "أخطاء", "نواقص"], data.topic_alerts),

    ("permits", 7, ["اذون ٢ مخازن", "اذون 2 مخازن", "اذون صرف", "اذن صرف", "عدد الاذون",
                    "الاذون", "٢ مخازن", "2 مخازن"], data.topic_permits),

    ("warehouses", 6, ["ارصده المخازن", "الارصده", "ارصدة", "الرصيد المتوفر", "رصيد المخزن",
                       "المستودعات", "مستودعات وسجلات", "الدورة المخزنية", "الاصناف في المخزن",
                       "اصناف المخزن", "المخزون"], data.topic_warehouses),

    ("tarfea", 7, ["الترفيه", "ترفيه", "رصيد الترفيه", "اصناف الترفيه"], data.topic_tarfea),

    ("rations", 5, ["المقررات", "المقرر", "مقرر", "اصناف المقرر", "الكميات للفرد",
                    "المقرر النشط", "نشاط المقرر", "التموين", "التمونيه", "المتعهد"],
     data.topic_rations),

    ("recruits", 6, ["المجندين", "المجند", "عدد المجندين", "شهادات", "شهاده صحيه",
                     "قرب انتهاء الخدمه", "انتهاء الخدمه", "اليوميه"], data.topic_recruits),

    ("health", 7, ["الصحه", "التقارير الطبيه", "الخزانات", "الكشف الطبي"], data.topic_health),

    ("backups", 7, ["النسخ الاحتياطي", "النسخ الاحتياطيه", "الباك اب", "اخر نسخه",
                    "عدد النسخ"], data.topic_backups),

    ("occasions", 7, ["المناسبات", "التوثيق", "الصور", "الفيديو", "معرض الصور"],
     data.topic_occasions),

    ("letterhead", 7, ["الدباجه", "اللوجو", "التوقيعات", "الشعار"], data.topic_letterhead),

    ("stores", 7, ["المخازن والثلاجات", "الثلاجات", "سعه المخزن", "المخازن الفيزيائيه"],
     data.topic_stores),

    ("excluded", 7, ["المستثنين", "المستثني", "عدم الراغبين", "غير الراغبين",
                     "الهلاكات", "المعفي", "الاعفاء"], data.topic_excluded),

    ("forces", 5, ["اصل القوه", "قوه الجهات", "الكوادر", "الجهات والكوادر", "اجمالي القوه",
                   "اجمالي الضباط", "عدد الضباط", "عدد الافراد", "قوه الجهه",
                   "قوه", "القوه", "قوة", "القوة",
                   "الكوادر المعتمده", "ضابط", "ضباط", "افراد", "فرد"],
     data.topic_forces),

    ("raghibin_entity", 8, ["راغبين جهه", "راغبو جهه", "راغبين", "راغبو", "عدد الراغبين",
                            "رغبه", "ضابط", "ضباط", "افراد", "فرد", "قوه الجهه",
                            "قوه الجهات"], data.topic_raghibin_entity),

    ("raghibin", 5, ["راغبين", "راغبو", "عدد الراغبين", "تسجيلات الراغبين",
                     "راغبين اليوم", "راغبو اليوم"], data.topic_raghibin_day),

    ("tameedat_day", 6, ["تاميدات يوم", "تأميدات يوم", "تاميدات اليوم", "تأميدات اليوم",
                         "تاميده اليوم", "سجلات يوم", "تاميدات بتاريخ"], data.topic_tameedat_day),

    ("tameedat_entity", 6, ["تاميدات جهه", "تأميدات جهه", "تاميدات", "تأميدات", "مده التميد",
                            "ايام التميد", "مواعيد التاميدات"], data.topic_tameedat_entity),

    ("momoda", 6, ["الجهات المومده", "المومده", "الجهات الممده", "جهات مومده",
                   "عدد الجهات المومده"], data.topic_momoda),

    ("tameedat_month", 4, ["عدد التاميدات", "عدد التأميدات", "تاميدات الشهر", "تأميدات الشهر",
                           "تاميدات", "تأميدات"], data.topic_tameedat_month),

    ("day_files", 7, ["ملف يوم", "ملف تاميدات يوم", "ملف تاميدات", "ملف تأميدات يوم",
                      "فولدر يوم", "مجلد يوم", "ملف اليوم", "اكسل يوم", "تنزيل ملف يوم",
                      "نزل ملف يوم"], files_data.topic_day_files),

    ("local_files", 6, ["الملفات المحليه", "حصر الملفات", "ملفات القسم", "فين الملفات",
                        "عدد الملفات", "الملفات على جهازي", "ملفات التاميدات",
                        "ملفات الراغبين"], files_data.topic_local_files),

    ("top_entities", 6, ["اكبر جهه", "اكبر قوه", "اعلي جهه", "اقل جهه", "اقل قوه",
                         "ترتيب الجهات", "مين اكبر", "مين اقل", "اقوي جهه", "اضعف جهه",
                         "اكبر جهات", "اقل جهات", "اكبر القوه", "اقل القوه", "اعلي القوه",
                         "اقوي جهات", "اضعف جهات", "ترتيب القوه", "الجهات الاكبر",
                         "الجهات الاقل"], rank_data.topic_top_entities),

    ("missing_days", 6, ["ايام بدون تسجيل", "ايام بلا تسجيل", "ايام ناقصه",
                         "ايام مفيهاش تسجيل", "ايام مفيهاش راغبين", "ايام بدون راغبين",
                         "تسجيل ناقص"], rank_data.topic_missing_days),

    ("date", 5, ["تاريخ اليوم", "النهارده", "اليوم كام", "تاريخ النهارده", "الشهر النشط",
                 "انهي شهر", "اي شهر", "الشهر الحالي", "التاريخ", "اليوم ايه"], data.topic_date),
]


def _score_topic(keywords, question):
    score = 0
    for keyword in keywords:
        key = T.normalize(keyword)
        if not key:
            continue
        if key in question:
            score += len(key) + 2 + (3 if " " in key else 0)
        elif T.phrase_in(question, key, threshold=0.86):
            score += (len(key) + 2) * 0.75
    return score


# ══════════════════════════════════════════════════════════════════════
# تحويل كتل الإجابة إلى نص بسيط (للرد النصي وos التوافق مع أي واجهة قديمة)
# ══════════════════════════════════════════════════════════════════════
def blocks_to_text(payload):
    if payload.get("reply"):
        return payload["reply"]
    lines = []
    title = payload.get("title")
    if title:
        lines.append(title)
    for block in payload.get("blocks") or []:
        kind = block.get("type")
        if kind == "p":
            lines.append(block["text"])
        elif kind == "note":
            lines.append("ملاحظة: " + block["text"])
        elif kind == "bullets":
            lines.extend("• " + item for item in block["items"])
        elif kind == "kv":
            lines.extend(f"{pair[0]}: {pair[1]}" for pair in block["items"])
        elif kind == "table":
            lines.append(" · ".join(block["headers"]))
            lines.extend(" | ".join(str(cell) for cell in row) for row in block["rows"])
    return "\n".join(lines)


def _finish(payload, kind):
    payload.setdefault("title", "")
    payload.setdefault("blocks", [])
    payload.setdefault("links", [])
    payload.setdefault("followups", [])
    payload["kind"] = kind
    payload["reply"] = blocks_to_text(payload)
    return payload


# ══════════════════════════════════════════════════════════════════════
# ردود المجاملة والتعريف والمساعدة
# ══════════════════════════════════════════════════════════════════════
GREETING_PHRASES = ("السلام عليكم", "سلام عليكم", "سلام", "اهلا", "هاي", "هلا",
                    "صباح الخير", "مساء الخير", "ازيك", "إزيك", "عامل ايه", "اخبارك",
                    "تحيه طيبه", "مرحبا")
THANKS_PHRASES = ("شكرا", "متشكر", "تسلم", "جزاك الله", "ربنا يكرمك", "تمام", "برافو",
                  "احسنت")
WHO_PHRASES = ("مين انت", "من انت", "انت مين", "اسمك ايه", "انت ايه", "بتشتغل ازاي",
               "انت شغال بالذكاء الاصطناعي", "انت نموذج ايه")
HELP_PHRASES = ("مساعده", "ساعدني", "بتعرف تعمل ايه", "اوامر", "الاوامر", "تعمل ايه",
                "خيارات", "بتعرف ايه", "ايه اللي تعرفه", "قدرات", "اطلب ايه",
                "اسال عن ايه", "اسالك عن ايه")


def _greeting(year, month):
    stats = _quick_facts(year, month)
    return _finish({
        "title": "أهلاً بك",
        "blocks": [data.p("وعليكم السلام ورحمة الله وبركاته — أنا المساعد المحلي "
                          "لمنظومة مخازن التعيينات، شغّال داخل البرنامج بلا إنترنت "
                          "وعلى بيانات الشهر النشط فقط."),
                   data.kv(stats)],
        "links": [data.L_TAMEEDAT, data.L_RAG],
        "followups": ["ملخص الشهر", "تنبيهات الشهر", "افتح التاميدات"],
    }, "greeting")


def _quick_facts(year, month):
    """سطران سريعان بصدق البيانات الحالية — يُستخدمان في التحية والمساعدة."""
    from data_access import db_tameedat as dt
    from services import tameed_alerts
    records = dt.month_records(year, month)
    totals = dt.month_summary(year, month)[1]
    stats = tameed_alerts.summary(year, month)
    return [["الشهر النشط", data._month_title(year, month)],
            ["التأميدات", f"{data._ar(len(records))} تأميدة · "
                          f"إجمالي {data._ar(totals['grand'])}"],
            ["التنبيهات", data._ar(stats["problem_rows"])]]


def _thanks(year, month):
    return _finish({
        "title": "العفو",
        "blocks": [data.p("العفو يا فندم — تحت أمرك في أي وقت. تحب أفتحلك تاب معيّن "
                          "أو أسألك عن أرقام الشهر؟")],
        "followups": ["ملخص الشهر", "تنبيهات الشهر", "افتح الراغبين"],
    }, "thanks")


def _whoami(year, month):
    status = local_model.status()
    model_line = ("ويشغّل نموذجًا محليًا اختياريًا إن وُجد ملفه داخل بياناتك، "
                  "وبدونه يعمل بمحرك النوايا المحلي — والاثنان بلا إنترنت."
                  if status["enabled"] else
                  "ولا يحتاج أي إنترنت ولا أي خدمة خارجية.")
    return _finish({
        "title": "تعريف",
        "blocks": [data.p("أنا المساعد المحلي لمنظومة مخازن التعيينات — أعمل داخل "
                          "البرنامج نفسه على بيانات الشهر النشط: أفتح أي تاب بالكلام، "
                          "وأجيب أرقام التأميدات والراغبين والمقررات والمخازن والمجندين "
                          "والتنبيهات والنسخ الاحتياطية، وأشرح المصطلحات وخطوات العمل. "
                          + model_line),
                   data.note("القراءة فقط: لا أحفظ ولا أعدّل أي بيانات — كل ما أقوله "
                             "من الشاشات والقواعد نفسها.")],
        "links": [data.L_TAMEEDAT, data.L_RAG],
        "followups": ["مساعدة", "ملخص الشهر"],
    }, "who")


def _help(year, month):
    blocks = [data.p("تحت أمرك — دي كل حاجة أقدر أعملها في المنظومة:")]
    for title, examples in K.CAPABILITIES:
        blocks.append(data.p("▪ " + title))
        blocks.append(data.bullets(["مثال: " + example for example in examples[:3]]))
    blocks.append(data.kv(_quick_facts(year, month)))
    return _finish({
        "title": "المساعد المحلي — القدرات",
        "blocks": blocks,
        "links": [{"label": "تأميدات اليوم", "target": "tameedat.day"},
                  {"label": "الراغبين اليومي", "target": "raghibin.daily"},
                  {"label": "المجندين", "target": "recruits"}],
        "followups": ["ملخص الشهر", "أرصدة المخازن", "إزاي أسجّل تأميدة"],
    }, "help")


# ══════════════════════════════════════════════════════════════════════
# المعجم والأدلة
# ══════════════════════════════════════════════════════════════════════
DEFINITION_TRIGGERS = ("يعني ايه", "ايه معني", "معني", "تعريف", "اشرح", "اشرحلي",
                       "وضح", "ايه هو", "ايه هي", "عباره عن", "بتعني ايه", "فايده")


def _definition(question, year, month):
    if not T.any_in(question, *DEFINITION_TRIGGERS):
        return None
    best, best_score = None, 0
    for key, entry in K.GLOSSARY.items():
        score = _score_topic(entry["terms"] + [key], question)
        if score > best_score:
            best, best_score = entry, score
    if not best:
        return None
    blocks = [data.p(best["text"])]
    related = [item for item in K.GLOSSARY if item != best["title"]][:4]
    return _finish({
        "title": best["title"],
        "blocks": blocks,
        "links": [data.L_DICT, data.L_TAMEEDAT],
        "followups": ["يعني إيه " + item for item in related[:3]] + ["مساعدة"],
    }, "definition")


GUIDE_TRIGGERS = ("ازاي", "إزاي", "كيف", "طريقه", "خطوات", "اعمل ايه", "منين",
                  "ادل", "اشرحلي الخطوات", "عايز اسجل", "عاوز اسجل")


def _guide(question, year, month):
    """الدليل يُجاب إذا سأل المستخدم «إزاي/كيف…» أو ذكر عبارة دالة كاملة

    («الشهر اللي فات» ⇒ دليل تغيير الشهر) — أقوى من نتيجة موضوع عام، فلا يُخفي دقة.
    """
    triggered = T.any_in(question, *GUIDE_TRIGGERS)
    best, best_score = None, 0
    for key, entry in K.GUIDES.items():
        score = _score_topic(entry["terms"], question)
        if score > best_score:
            best, best_score = entry, score
    if not best:
        return None
    if not triggered and best_score < 12:      # عبارة مركّبة كاملة فقط بلا كلمة سؤال
        return None
    link = data.L_TAMEEDAT
    from .destinations import by_key
    if best.get("link"):
        link = {"label": dest_label(best["link"]), "target": best["link"]} \
            if by_key(best["link"]) else data.L_TAMEEDAT
    return _finish({
        "title": "خطوات: " + best["title"],
        "blocks": [data.p("الخطوات بالترتيب:")] + [data.bullets(best["steps"])],
        "links": [link],
        "followups": ["مساعدة", "ملخص الشهر", "افتح التاميدات"],
    }, "guide")


# ══════════════════════════════════════════════════════════════════════
# المحرك
# ══════════════════════════════════════════════════════════════════════
def answer(text, year, month):
    """الإجابة الكاملة: {reply, blocks, links, followups, kind[, navigate, title]}."""
    raw = (text or "").strip()
    question = T.normalize(raw)
    if not question:
        return _finish({
            "title": "اكتب سؤالك",
            "blocks": [data.p("اكتب سؤالك أو اسم التاب وأنا أنفّذ — مثال: «افتح التاميدات» "
                              "أو «عدد التأميدات» أو «تأميدات يوم ٧».")],
            "followups": K.QUICK_PROMPTS[:4],
        }, "empty")

    short = len(question.split()) <= 4
    if short and T.any_in(question, *GREETING_PHRASES):
        return _greeting(year, month)
    if short and T.any_in(question, *THANKS_PHRASES):
        return _thanks(year, month)
    if T.any_in(question, *WHO_PHRASES):
        return _whoami(year, month)
    if T.any_in(question, *HELP_PHRASES):
        return _help(year, month)

    definition = _definition(question, year, month)
    if definition:
        return definition
    guide = _guide(question, year, month)
    if guide:
        return guide

    destination = resolve(question)
    if destination and wants_navigation(question):
        return _finish({
            "title": "فتح " + destination[1],
            "blocks": [data.p(f"اتفضل — فتحت لك «{destination[1]}».")],
            "links": [{"label": destination[1], "target": destination[0]}],
            "navigate": destination[0],
            "followups": ["مساعدة", "ملخص الشهر"],
        }, "nav")

    # المواضيع مرتّبة بالنتيجة، ويُجرَّب كل موضوع حتى يرد أحدها فعلًا:
    # موضوع «جهة محددة» يرجع None لو مفيش جهة في السؤال فينتقل للذي يليه تلقائيًا.
    ranked = sorted(((_score_topic(keywords, question) * (weight / 5.0), key, handler)
                     for key, weight, keywords, handler in TOPICS), reverse=True)
    for score, key, handler in ranked:
        if score < 4:
            break
        try:
            payload = handler(year, month, question)
        except Exception:      # noqa: BLE001 — موضوع واحد لا يُسقط المساعد
            payload = None
        if payload:
            payload.setdefault("followups", ["مساعدة", "ملخص الشهر"])
            return _finish(payload, "data")

    # ذكر جهة بالاسم وحدها («قسم شرطة نخل» / «الحسنة» / «مرور وسط سيناء»)
    entity_card = data.topic_entity_card(year, month, question)
    if entity_card:
        entity_card.setdefault("followups", ["مساعدة", "ملخص الشهر"])
        return _finish(entity_card, "data")

    # مطابقة تاب عامة (كلمة القسم بلا فعل أمر)
    if destination:
        return _finish({
            "title": destination[1],
            "blocks": [data.p(f"«{destination[1]}» — اكتب «افتح {destination[1]}» "
                              "وأنا أنقلك فورًا، أو اضغط الرابط تحت.")],
            "links": [{"label": destination[1], "target": destination[0]}],
            "followups": ["مساعدة", "ملخص الشهر"],
        }, "nav")

    # نموذج محلي اختياري (GGUF داخل بيانات المستخدم) — إن وُجد فقط
    model_reply = local_model.try_answer(raw, year, month)
    if model_reply:
        return _finish({
            "title": "رد النموذج المحلي",
            "blocks": [data.p(model_reply)],
            "links": [data.L_TAMEEDAT, data.L_RAG],
            "followups": ["مساعدة", "ملخص الشهر"],
        }, "model")

    suggestions = _suggest(question)
    blocks = [data.p("معلش، مفهمتش الطلب ده. جرّب واحد من دول:"),
              data.bullets(suggestions)]
    if not local_model.status()["enabled"]:
        blocks.append(data.note(
            "ولو قصدك سؤالًا مفتوحًا (زي «اكتبلي جملة»): ده بيرد عليه موديل لغوي — "
            "اختار واحدًا من قائمة «تبديل الموديل» فوق لوحة المساعد، والقائمة نفسها "
            "بتوضّح حالة المكتبة والموديل."))
    blocks.append(data.note("اكتب «مساعدة» أشوفك كل الأسئلة والأوامر اللي أقدر أرد عليها."))
    return _finish({
        "title": "معلش، مفهمتش",
        "blocks": blocks,
        "followups": suggestions[:3] + ["مساعدة"],
    }, "unknown")


def _suggest(question):
    """اقتراحات ذكية عند عدم الفهم — من قدرات المساعد نفسها."""
    flat = [example for _title, examples in K.CAPABILITIES for example in examples]
    ranked = sorted(flat, key=lambda item: -T.similarity(T.normalize(item), question))
    return ranked[:4]


def quick_prompts():
    """الاقتراحات السريعة أعلى صندوق الكتابة (عدد معروض محدود بلا فوضى)."""
    return list(K.QUICK_PROMPTS[:K.VISIBLE_PROMPTS])


def capabilities(year=None, month=None):
    """كتالوج القدرات + الأرقام السريعة — يخدم واجهة اللوحة."""
    payload = {"topics": [{"title": title, "examples": examples}
                          for title, examples in K.CAPABILITIES],
               "glossary": [entry["title"] for entry in K.GLOSSARY.values()],
               "guides": [entry["title"] for entry in K.GUIDES.values()],
               "model": local_model.status()}
    if year and month:
        payload["facts"] = _quick_facts(year, month)
    return payload
