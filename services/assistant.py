# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""المساعد المحلي 🤖 — محرك نوايا عربي يعمل بلا إنترنت وبلا أي نموذج خارجي.

قرار التنفيذ (توجيه المستخدم ٠٦/١٠/٢٠٢٦ «أقل AI أوفلاين»): أي نموذج لغوي حقيقي
حتى لو صغير يحتاج ٥٠–٤٠٠ ميجابايت + محرك استنتاج C++ يُحمَّل وقت البناء، وهذا
يناقض قاعدة «البرنامج محلي صغير بلا إنترنت ولا CDN» ويثقل المثبّت. لذلك بُني
مساعد محلي بلا أي اعتماديات (٠ ميجابايت إضافية) يفهم سلام المستخدم، ويفتح أي
تاب في المنظومة فورًا بالكلام، ويجيب أسئلة الأرقام من بيانات الشهر الحقيقي.

البنية جاهزة لتوصيل نموذج محلي لاحقًا: كل شيء يمر من answer() التي تُرجع
{"reply", "links", "kind"} — يكفي استبدال محرك النوايا بمحرك نموذج بلا تغيير
في الواجهة أو المسارات.
"""
import re

from core import arabic_numbers as arnum, dates, egtime
from core.config import MONTH_NAMES

# ══════════════════════════════════════════════════════════════════════
# وجهات التنقل — كل تاب في المنظومة بكلماته الدارجة
# ══════════════════════════════════════════════════════════════════════
# (المعرّف، العنوان الظاهر، اسم الـendpoint، بارامترات ثابتة، كلمات مفتاحية)
DESTINATIONS = [
    ("dashboard", "الرئيسية", "dashboard", {},
     ["الرئيسية", "الصفحة الرئيسية", "لوحة التحكم", "داشبورد", "البداية"]),

    ("tameedat.day", "التاميدات — تأميدات اليوم المحدد", "tameedat.page", {"tab": "day"},
     ["تأميدات اليوم", "تاميدات اليوم", "التاميدات", "تأميدات", "تاميدات", "تسجيل تأميدة", "تأميدة"]),
    ("tameedat.momoda", "التاميدات — الجهات المومدة بالشهر", "tameedat.page", {"tab": "momoda"},
     ["الجهات المومدة", "المومدة", "الجهات الممدة", "المومده"]),
    ("tameedat.dict", "التاميدات — قاموس ودليل الجهات", "tameedat.page", {"tab": "dict"},
     ["قاموس الجهات", "دليل الجهات", "القاموس"]),
    ("tameedat.report", "التاميدات — التقرير الشامل", "tameedat.page", {"tab": "report"},
     ["تقرير التاميدات", "التقرير الشامل", "تقرير شامل"]),

    ("raghibin.daily", "الراغبين — اليومي", "raghibin.page", {"tab": "daily"},
     ["الراغبين اليومي", "الراغبين", "راغبين", "كشف الراغبين", "رغبة"]),
    ("raghibin.excluded", "الراغبين — عدم الراغبين", "raghibin.page", {"tab": "excluded"},
     ["عدم الراغبين", "غير الراغبين", "المستثنين"]),
    ("raghibin.monthly", "الراغبين — تجميع الكشف العام", "raghibin.page", {"tab": "monthly"},
     ["تجميع الكشف", "الكشف الشهري", "تجميع الراغبين"]),
    ("raghibin.cadres", "الراغبين — الجهات والكوادر المعتمدة", "raghibin.page", {"tab": "cadres"},
     ["الكوادر", "الجهات والكوادر", "الكوادر المعتمدة", "قوة الجهة"]),

    ("rations.tamween", "المقررات التمونيية", "rations.page", {"section": "tamween"},
     ["المقررات التمونيية", "التمونية", "التموين", "مقررات التموين", "مقرر تمويني"]),
    ("rations.contractor", "مقررات المتعهد", "rations.page", {"section": "contractor"},
     ["مقررات المتعهد", "المتعهد", "مقرر المتعهد"]),

    ("warehouses", "مستودعات وسجلات", "warehouses.page", {},
     ["مستودعات وسجلات", "المستودعات", "مخازن وسجلات", "الدورة المخزنية"]),
    ("calc2", "آلة حاسبة ٢ مخازن", "calc2.page", {},
     ["آلة حاسبة", "حاسبة", "اذن 2 مخازن", "إذن ٢ مخازن", "٢ مخازن", "2 مخازن", "مخزنين"]),
    ("recruits", "المجندين", "recruits.page", {},
     ["المجندين", "المجند", "مجندين", "اليومية", "يومية"]),
    ("tarfea", "الترفية", "tarfea.page", {},
     ["الترفية", "ترفية", "الترفيه"]),
    ("health", "الصحة", "health.page", {},
     ["الصحة", "صحة", "الكشف الطبي"]),
    ("stores", "المخازن والثلاجات", "stores.page", {},
     ["المخازن والثلاجات", "الثلاجات", "المخازن"]),
    ("letterhead", "الدباجة والتوقيعات الرسمية", "letterhead.page", {},
     ["الدباجة", "التوقيعات", "اللوجو", "الشعار", "دباجة"]),
    ("backups", "النسخ الاحتياطي والحماية", "backups.page", {},
     ["النسخ الاحتياطي", "النسخ الاحتياطية", "الباك اب", "نسخة احتياطية", "الحماية"]),
]

# ══════════════════════════════════════════════════════════════════════
# تطبيع النص العربي — يوحّد الهمزات والياء والتاء المربوطة ويشيل التشكيل
# ══════════════════════════════════════════════════════════════════════
_DIACRITICS = re.compile(r"[\u0617-\u061a\u064b-\u0652\u0670\u0640]")
_PUNCT = re.compile(r"[^\w\s\u0600-\u06ff]")


def normalize(text):
    """نص موحّد للمقارنة: بلا تشكيل ولا علامات، بألف وياء وهاء موحدة."""
    value = arnum.to_western(text or "")
    value = _DIACRITICS.sub("", value)
    value = _PUNCT.sub(" ", value)
    for source, target in (("أإآٱ", "ا"), ("ىئ", "ي"), ("ة", "ه"), ("ؤ", "و"),
                           ("گ", "ك"), ("ی", "ي")):
        for char in source:
            value = value.replace(char, target)
    return " ".join(value.split()).lower()


def _digit_ar(value):
    return arnum.to_arabic_indic(str(value))


# ══════════════════════════════════════════════════════════════════════
# ردود المجاملة والتعريف
# ══════════════════════════════════════════════════════════════════════
GREETING_WORDS = ("سلام عليكم", "السلام عليكم", "سلام", "اهلا", "أهلا", "هاي", "هلا",
                  "صباح الخير", "مساء الخير", "ازيك", "إزيك", "عامل ايه", "اخبارك")
THANKS_WORDS = ("شكرا", "شكرًا", "متشكر", "تسلم", "جزاك الله", "ربنا يكرمك", "تمام")
WHO_WORDS = ("مين انت", "من انت", "انت مين", "اسمك ايه", "انت ايه")
HELP_WORDS = ("مساعدة", "ساعدني", "مساعده", "بتعرف تعمل ايه", "اوامر", "الاوامر",
              "تعمل ايه", "خيارات")


def _greeting():
    return {"kind": "greeting",
            "reply": "وعليكم السلام ورحمة الله وبركاته 🌿 أنا المساعد المحلي لمنظومة "
                     "التعيينات — بفتحلك أي تاب فورًا وأجاوبك من بيانات الشهر النشط. "
                     "تقدر تكتب مثلًا: «افتح التاميدات» أو «تنبيهات الشهر» أو «عدد الراغبين».",
            "links": []}


def _thanks():
    return {"kind": "thanks",
            "reply": "العفو يا فندم 🌟 تحت أمرك في أي وقت — قولّي تحب تفتح إيه أو تسأل عن إيه.",
            "links": []}


def _whoami():
    return {"kind": "who",
            "reply": "أنا مساعد المنظومة المحلي 🤖 — أعمل داخل البرنامج نفسه، بلا إنترنت "
                     "وبلا أي خدمة خارجية، وكل بياناتي من قاعدة الشهر النشط فقط. "
                     "أقدر أفتحلك أي تاب بالكلام وأقولك أرقام الشهر وتنبيهاته.",
            "links": []}


def _help(year, month, sample=6):
    links = [{"label": dest[1], "target": dest[0]} for dest in DESTINATIONS[:sample]]
    return {"kind": "help",
            "reply": "تحت أمرك 🤖 أقدر:\n"
                     "• أفتح أي تاب أو قسم بالكلام «افتح التاميدات / الراغبين / المقررات».\n"
                     "• أقولك أرقام الشهر: «عدد التأميدات» · «الجهات المومدة» · «إجمالي القوة».\n"
                     "• أطلعلك تنبيهات الشهر «تنبيهات» أو «عدم التطابق».\n"
                     "• أقولك تاريخ اليوم والشهر النشط والحسابات الزمنية.",
            "links": links}


# ══════════════════════════════════════════════════════════════════════
# الإجابة على أسئلة البيانات — من قاعدة الشهر النشط فقط
# ══════════════════════════════════════════════════════════════════════
def _data_answer(question, year, month):
    """يرجع dict أو None لو السؤال ليس سؤال بيانات."""
    from data_access import db_raghibin as rp
    from data_access import db_tameedat as dt
    from data_access import db_rations as dr
    from services import tameed_alerts

    q = question
    month_title = f"{MONTH_NAMES[month - 1]} {_digit_ar(year)}"

    def has(*words):
        return any(word in q for word in words)

    if has("تاريخ اليوم", "النهارده", "اليوم كام", "تاريخ النهارده", "التاريخ"):
        today = egtime.today()
        return {"kind": "data", "reply":
                f"تاريخ اليوم بتوقيت القاهرة: {dates.format_date(today)} — "
                f"{egtime.weekday_ar(today)}. والشهر النشط في البرنامج: {month_title}.",
                "links": []}

    if has("الشهر النشط", "انهي شهر", "أي شهر", "الشهر الحالي"):
        return {"kind": "data",
                "reply": f"الشهر النشط الآن: {month_title} — وكل بياناته معزولة عن أي شهر آخر.",
                "links": []}

    if has("تنبيه", "مش متطابق", "عدم تطابق", "عدم التطابق", "اختلاف"):
        stats = tameed_alerts.summary(year, month)
        rows = tameed_alerts.month_rows(year, month)
        if not rows:
            reply = (f"مفيش أي تنبيه في {month_title} ✔ — كل تأميدات الشهر مطابقة "
                     "للراغبين المسجلين وللكوادر المعتمدة.")
        else:
            first = rows[0]
            reply = (f"في {month_title}: {_digit_ar(stats['problem_rows'])} تنبيهًا على "
                     f"{_digit_ar(stats['days'])} يومًا و{_digit_ar(stats['entities'])} جهة "
                     f"(خطر {_digit_ar(stats['danger'])} · تنبيه {_digit_ar(stats['warn'])} · "
                     f"معلومة {_digit_ar(stats['info'])}).\n"
                     f"أول واحد: يوم {_digit_ar(first['day'])} — {first['entity_name']}: "
                     f"{first['issues'][0]['text']}\n"
                     "جدول التنبيهات كامل أسفل صفحتي التاميدات والراغبين "
                     "(زرار «⚠️ تنبيهات التاميدات والراغبين»).")
        return {"kind": "data", "reply": reply,
                "links": [{"label": "تأميدات اليوم", "target": "tameedat.day"},
                          {"label": "الراغبين اليومي", "target": "raghibin.daily"}]}

    if has("تأميد", "تاميد"):
        summary, totals = dt.month_summary(year, month)
        records = dt.month_records(year, month)
        if not records:
            return {"kind": "data", "reply": f"لا توجد تأميدات مسجلة في {month_title} بعد.",
                    "links": [{"label": "فتح التاميدات", "target": "tameedat.day"}]}
        return {"kind": "data",
                "reply": f"تأميدات {month_title}: {_digit_ar(len(records))} تأميدة على "
                         f"{_digit_ar(totals['entities'])} جهة مومدة — ضباط "
                         f"{_digit_ar(totals['officers'])} · أفراد {_digit_ar(totals['individuals'])} · "
                         f"مجندين {_digit_ar(totals['recruits'])} (إجمالي القوة "
                         f"{_digit_ar(totals['grand'])} على {_digit_ar(totals['active_days'])} يوم سريان).",
                "links": [{"label": "تأميدات اليوم", "target": "tameedat.day"},
                          {"label": "الجهات المومدة", "target": "tameedat.momoda"}]}

    if has("راغب", "رغبة"):
        split = rp.month_willing_split(year, month)
        officers = sum(day["officers"] for day in split.values())
        individuals = sum(day["individuals"] for day in split.values())
        counts = rp.entity_force_counts(year, month)
        force_o = sum(c["officers"] for c in counts.values())
        force_i = sum(c["individuals"] for c in counts.values())
        return {"kind": "data",
                "reply": f"راغبو {month_title}: ضباط {_digit_ar(officers)} · أفراد "
                         f"{_digit_ar(individuals)} (مجموع التسجيلات على كل أيام الشهر).\n"
                         f"وقوة الجهات المسجلة في الكوادر: ضباط {_digit_ar(force_o)} · "
                         f"أفراد {_digit_ar(force_i)} من {_digit_ar(len(counts))} جهة.",
                "links": [{"label": "الراغبين اليومي", "target": "raghibin.daily"},
                          {"label": "الكوادر المعتمدة", "target": "raghibin.cadres"}]}

    if has("قوة", "كوادر", "افراد القوه", "الافراد", "الضباط") and has("عدد", "كام", "اجمالي", "إجمالي", "قوة", "كوادر"):
        counts = rp.entity_force_counts(year, month)
        total = sum(c["officers"] + c["individuals"] for c in counts.values())
        return {"kind": "data",
                "reply": f"قوة الجهات المسجلة في {month_title}: {_digit_ar(len(counts))} جهة — "
                         f"إجمالي {_digit_ar(total)} اسم "
                         f"(ضباط {_digit_ar(sum(c['officers'] for c in counts.values()))} · "
                         f"أفراد {_digit_ar(sum(c['individuals'] for c in counts.values()))}).",
                "links": [{"label": "الكوادر المعتمدة", "target": "raghibin.cadres"}]}

    if has("مقرر", "اصناف", "أصناف"):
        parts = []
        for section, label in (("tamween", "التمونيية"), ("contractor", "المتعهد")):
            kind = dr.get_activation(year, month, section)
            items = dr.get_items(year, month, section, kind or "summer")[0] if kind else []
            parts.append(f"{label}: {_digit_ar(len(items))} صنفًا"
                         + (f" (المقرر النشط: {kind})" if kind else " (لا مقرر مفعّل)"))
        return {"kind": "data",
                "reply": f"مقررات {month_title} — " + " · ".join(parts) + ".",
                "links": [{"label": "المقررات التمونيية", "target": "rations.tamween"},
                          {"label": "مقررات المتعهد", "target": "rations.contractor"}]}

    return None


# ══════════════════════════════════════════════════════════════════════
# المحرك: تطابق النوايا
# ══════════════════════════════════════════════════════════════════════
# أفعال الأمر التي تعني «خذني إلى التاب فورًا»
OPEN_VERBS = ("افتح", "روح", "اذهب", "ادخل", "وديني", "خدني", "هات", "عايز", "عاوز",
              "اروح", "أروح", "اظهر", "وريني")


def match_destination(question):
    """أفضل وجهة مطابقة للسؤال (أطول كلمة مفتاحية تِغلب) أو None."""
    best, best_score = None, 0
    for dest in DESTINATIONS:
        score = 0
        for keyword in dest[4]:
            key = normalize(keyword)
            if key and key in question:
                score += len(key) + 2
        if score > best_score:
            best, best_score = dest, score
    return best if best_score >= 5 else None


def answer(text, year, month):
    """الإجابة الكاملة: {"reply": str, "links": [{"label","target"|"href"}], "kind": str}."""
    question = normalize(text)
    if not question:
        return {"kind": "empty", "reply": "اكتب سؤالك أو اسم التاب وأنا أنفّذ 🤖", "links": []}

    if any(normalize(word) in question for word in GREETING_WORDS):
        return _greeting()
    if any(normalize(word) in question for word in WHO_WORDS):
        return _whoami()
    if any(normalize(word) in question for word in HELP_WORDS):
        return _help(year, month)
    if any(normalize(word) in question for word in THANKS_WORDS):
        return _thanks()

    # أفعال الأمر («افتح …») تُنفَّذ فورًا قبل أي سؤال بيانات
    dest = match_destination(question)
    if dest and any(verb in question for verb in OPEN_VERBS):
        return {"kind": "nav",
                "reply": f"فتحتلك «{dest[1]}» ✅ لو الصفحة ما نقلتش اضغط الرابط تحت.",
                "links": [{"label": dest[1], "target": dest[0]}],
                "navigate": dest[0]}

    data = _data_answer(question, year, month)
    if data:
        return data
    if dest:
        payload = {"kind": "nav",
                   "reply": f"تمام ✅ «{dest[1]}» — اضغط الرابط أو اكتب «افتح {dest[1]}» وأنا أوديك فورًا.",
                   "links": [{"label": dest[1], "target": dest[0]}]}
        if any(verb in question for verb in OPEN_VERBS):
            payload["navigate"] = dest[0]
            payload["reply"] = f"فتحتلك «{dest[1]}» ✅ لو الصفحة ما نقلتش اضغط الرابط تحت."
        return payload

    return {"kind": "unknown",
            "reply": "معلش مفهمتش الطلب ده 🤔 جرّب تكتب: «افتح التاميدات» · «الراغبين» · "
                     "«المقررات التمونيية» · «تنبيهات الشهر» · «عدد التأميدات» — "
                     "أو اكتب «مساعدة» أشوفك كل اللي أقدر أعملة.",
            "links": [{"label": "مساعدة وأوامر", "target": "help"}]}


def quick_prompts():
    """اقتراحات سريعة تظهر كأزرار أعلى صندوق الكتابة."""
    return ["مساعدة", "افتح التاميدات", "الراغبين اليومي", "تنبيهات الشهر",
            "عدد التأميدات", "الجهات المومدة", "إجمالي القوة", "تاريخ اليوم"]
