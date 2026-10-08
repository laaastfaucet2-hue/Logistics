# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""إجابات المساعد المحلي على أسئلة بيانات الشهر النشط — من الطبقات الرسمية فقط.

كل إجابة تُبنى من دوال `data_access`/`services` نفسها التي تبني الشاشات، بلا أي
حساب موازٍ وبلا تخزين مؤقت — فالرقم الذي يقوله المساعد هو الرقم الذي على الشاشة.
الشكل الموحّد للإجابة: {"title", "blocks", "links", "followups", "detail"}
والـblocks: {"type": "p"|"bullets"|"kv"|"table"|"note", "text"/"items"/"headers"+"rows"}.
"""
from core import arabic_numbers as arnum
from core import dates, egtime
from core.config import MONTH_NAMES

from . import text as T


# ══════════════════════════════════════════════════════════════════════
# أدوات بناء الإجابات
# ══════════════════════════════════════════════════════════════════════
def _ar(value):
    return arnum.to_arabic_indic(str(value))


def _pair(officers, individuals, recruits=None):
    """«ض ٥ · أ ٣٥ · م ١٦٠» — الأرقام العربية دائمًا."""
    parts = [f"ض {_ar(officers)}", f"أ {_ar(individuals)}"]
    if recruits is not None:
        parts.append(f"م {_ar(recruits)}")
    return " · ".join(parts)


def _month_title(year, month):
    return f"{MONTH_NAMES[month - 1]} {_ar(year)}"


def result(title, blocks, links=None, followups=None, detail=None):
    return {"title": title, "blocks": blocks, "links": links or [],
            "followups": followups or [], "detail": detail or {}}


def p(text):
    return {"type": "p", "text": text}


def bullets(items):
    return {"type": "bullets", "items": list(items)}


def kv(items):
    return {"type": "kv", "items": [list(pair) for pair in items]}


def table(headers, rows):
    return {"type": "table", "headers": list(headers), "rows": [list(r) for r in rows]}


def note(text):
    return {"type": "note", "text": text}


def _fmt_date(year, month, day):
    return dates.format_date(f"{year:04d}-{month:02d}-{day:02d}")


# مربوطة بالوجهات المعروفة (تُفلتر في المسار إن لم يكن الـendpoint موجودًا)
L_TAMEEDAT = {"label": "تأميدات اليوم", "target": "tameedat.day"}
L_MOMODA = {"label": "الجهات المومدة", "target": "tameedat.momoda"}
L_DICT = {"label": "قاموس الجهات", "target": "tameedat.dict"}
L_RAG = {"label": "الراغبين اليومي", "target": "raghibin.daily"}
L_CADRES = {"label": "الكوادر المعتمدة", "target": "raghibin.cadres"}
L_RECRUITS = {"label": "المجندين", "target": "recruits"}
L_WAREHOUSES = {"label": "مستودعات وسجلات", "target": "warehouses"}
L_CALC2 = {"label": "آلة حاسبة ٢ مخازن", "target": "calc2"}
L_RATIONS_T = {"label": "المقررات التمونيية", "target": "rations.tamween"}
L_RATIONS_C = {"label": "مقررات المتعهد", "target": "rations.contractor"}
L_TARFEA = {"label": "الترفية", "target": "tarfea"}
L_BACKUPS = {"label": "النسخ الاحتياطي", "target": "backups"}
L_STORES = {"label": "المخازن والثلاجات", "target": "stores"}
L_OCCASIONS = {"label": "التوثيق والمناسبات", "target": "occasions"}
L_HEALTH = {"label": "الصحة", "target": "health"}


# ══════════════════════════════════════════════════════════════════════
# مطابقة أسماء الجهات (ضبابية — «قسم شرطة نخل» تُطابق حتى بخطأ مطبعي)
# ══════════════════════════════════════════════════════════════════════
def find_entity(question, names):
    """أفضل اسم جهة مذكور في السؤال — بتطابق كل الكلمات أو أقرب نسبة تشابه.

    كلمة واحدة **فريدة** على جهة واحدة تكفي للتعرف («راغبين نخل» ⇒ «قسم شرطة نخل»)،
    شرط ألا تكون الكلمة مشتركة بين جهتين («قسم» مثلًا تظهر في أسماء كثيرة فلا تكفي).
    """
    best, best_score = None, 0.0
    asked = set(question.split())
    keys = []
    for name in names:
        key = T.normalize(name)
        if key:
            keys.append((name, key, key.split()))

    word_count = {}
    for _, _, words in keys:
        for word in set(words):
            word_count[word] = word_count.get(word, 0) + 1

    for name, key, words in keys:
        if key in question:
            return name
        hits = sum(1 for word in words
                   if any(T.similarity(word, token) >= 0.84 for token in asked))
        score = hits / len(words)
        # كلمة واحدة فريدة على جهة واحدة تكفي («راغبين نخل» ⇒ «قسم شرطة نخل»)
        unique = [w for w in words
                  if len(w) >= 3 and word_count.get(w, 0) == 1
                  and any(T.similarity(w, token) >= 0.9 for token in asked)]
        if unique:
            score = max(score, 0.75)
        if score > best_score:
            best, best_score = name, score
    return best if best_score >= 0.6 else None


def _entity_names(year, month):
    from data_access import db_tameedat as dt
    return [row["name"] for row in dt.list_entities(year, month)]


# ══════════════════════════════════════════════════════════════════════
# التواريخ والشهر النشط
# ══════════════════════════════════════════════════════════════════════
def topic_date(year, month, question):
    today = egtime.today()
    days = egtime.days_in_month(year, month)
    items = [["تاريخ اليوم (القاهرة)", f"{dates.format_date(today)} — {egtime.weekday_ar(today)}"],
             ["الشهر النشط", _month_title(year, month)],
             ["أيام الشهر", f"{_ar(days)} يومًا"],
             ["اليوم من الشهر", _ar(today.day) if (today.year, today.month) == (year, month) else "—"]]
    return result("التاريخ والشهر النشط", [kv(items)],
                  links=[L_TAMEEDAT], followups=["ملخص الشهر", "تأميدات اليوم"])


def topic_hijri_weekday(year, month, question):
    day = T.day_number(question) or 1
    from datetime import date
    iso = f"{year:04d}-{month:02d}-{day:02d}"
    return result(f"يوم {_ar(day)}", [
        kv([["التاريخ", _fmt_date(year, month, day)],
            ["اليوم", egtime.weekday_ar(date(year, month, day))]])],
        links=[L_TAMEEDAT], followups=[f"تأميدات يوم {_ar(day)}"])


# ══════════════════════════════════════════════════════════════════════
# ملخص الشهر الشامل
# ══════════════════════════════════════════════════════════════════════
def topic_summary(year, month, question):
    from data_access import db_tameedat as dt
    from services import tameed_alerts, workspace_summary
    records = dt.month_records(year, month)
    _summary, totals = dt.month_summary(year, month)
    stats = tameed_alerts.summary(year, month)
    space = workspace_summary.summarize(year, month)
    rows = [
        ["التأميدات", f"{_ar(len(records))} تأميدة على {_ar(totals['entities'])} جهة"],
        ["إجمالي القوة المسجّلة", f"{_ar(totals['grand'])} "
                                  f"({_pair(totals['officers'], totals['individuals'], totals['recruits'])})"],
        ["أيام التميد الفعلية", _ar(totals["active_days"])],
        ["تنبيهات الشهر", f"{_ar(stats['problem_rows'])} "
                          f"(خطر {_ar(stats['danger'])} · تنبيه {_ar(stats['warn'])})"],
        ["جهات المقررات", _ar(space["entities"])],
        ["المقررات التمونيية", f"{_ar(space['tamween'])} صنفًا"],
        ["مقررات المتعهد", f"{_ar(space['contractor'])} صنفًا"],
        ["المجندون", _ar(space["recruits"])],
        ["النسخ الاحتياطية", _ar(space["backup_count"])],
        ["آخر نسخة", space["backup_date"] or "—"],
    ]
    blocks = [kv(rows)]
    if not records:
        blocks.append(note("الشهر لسه بلا تأميدات مسجلة — ابدأ من تاب «تأميدات اليوم المحدد»."))
    else:
        top = sorted(dt.month_summary(year, month)[0], key=lambda r: -r["grand_total"])[:3]
        blocks.append(bullets([f"{row['name']} — إجمالي {_ar(row['grand_total'])} "
                               f"على {_ar(row['active_days'])} يوم تميد" for row in top]))
    return result(f"ملخص شهر {_month_title(year, month)}", blocks,
                  links=[L_TAMEEDAT, L_MOMODA, L_RAG],
                  followups=["تنبيهات الشهر", "الجهات المومدة", "أرصدة المخازن"])


# ══════════════════════════════════════════════════════════════════════
# التنبيهات
# ══════════════════════════════════════════════════════════════════════
def topic_alerts(year, month, question):
    from services import tameed_alerts
    stats = tameed_alerts.summary(year, month)
    rows = tameed_alerts.month_rows(year, month)
    if not rows:
        return result(f"تنبيهات {_month_title(year, month)}", [
            p("مفيش أي تنبيه ✔ — كل تأميدات الشهر مطابقة للراغبين المسجلين "
              "وللكوادر المعتمدة.")], links=[L_TAMEEDAT, L_RAG],
            followups=["ملخص الشهر", "الجهات المومدة"])
    lines = []
    for row in rows[:5]:
        issues = " | ".join(issue["text"] for issue in row["issues"][:2])
        lines.append(f"يوم {_ar(row['day'])} — {row['entity_name']}: {issues}")
    blocks = [kv([["عدد التنبيهات", _ar(stats["problem_rows"])],
                  ["الأيام", _ar(stats["days"])],
                  ["الجهات", _ar(stats["entities"])],
                  ["التصنيف", f"خطر {_ar(stats['danger'])} · تنبيه {_ar(stats['warn'])} · "
                              f"معلومة {_ar(stats['info'])}"]]),
              bullets(lines)]
    if len(rows) > 5:
        blocks.append(note(f"وفي {_ar(len(rows) - 5)} تنبيهًا آخر — الجدول الكامل أسفل "
                           "صفحتي التاميدات والراغبين (زرار «⚠️ تنبيهات التاميدات والراغبين»)."))
    return result(f"تنبيهات {_month_title(year, month)}", blocks,
                  links=[L_TAMEEDAT, L_RAG], followups=["تأميدات اليوم", "راغبين اليوم"])


# ══════════════════════════════════════════════════════════════════════
# التاميدات
# ══════════════════════════════════════════════════════════════════════
def topic_tameedat_day(year, month, question):
    from data_access import db_tameedat as dt
    day = T.day_number(question)
    if not day:
        day = egtime.today().day if (egtime.today().year, egtime.today().month) == (year, month) else 1
    records = dt.records_for_day(year, month, day)
    title = f"تأميدات يوم {_ar(day)} — {_month_title(year, month)}"
    if not records:
        return result(title, [p(f"مفيش تأميدات مسجلة يوم {_ar(day)} ({_fmt_date(year, month, day)})."),
                              note("تقدر تسجّلها من تاب «تأميدات اليوم المحدد» بعد اختيار اليوم من التقويم.")],
                      links=[L_TAMEEDAT], followups=[f"راغبو يوم {_ar(day)}", "تنبيهات الشهر"])
    rows, tot = [], [0, 0, 0]
    for rec in records:
        tot[0] += rec["officers"] + sum(a["officers"] for a in rec["attachments"])
        tot[1] += rec["individuals"] + sum(a["individuals"] for a in rec["attachments"])
        tot[2] += rec["recruits"] + sum(a["recruits"] for a in rec["attachments"])
        label = rec["entity_name"]
        if rec["attachments"]:
            label += " + " + "، ".join(a["name"] for a in rec["attachments"]) + " (ملحقة)"
        rows.append([label, rec["entity_type"] or "—", _ar(rec["officers"]),
                     _ar(rec["individuals"]), _ar(rec["recruits"]), _ar(rec["grand_total"])])
    blocks = [table(["الجهة", "النوع", "ضابط", "فرد", "مجندين", "الإجمالي"], rows),
              kv([["عدد التأميدات", _ar(len(records))],
                  ["إجمالي اليوم", _pair(tot[0], tot[1], tot[2])],
                  ["مدد زمنية", _ar(sum(1 for r in records if r["range_days"] > 1))]])]
    return result(title, blocks, links=[L_TAMEEDAT],
                  followups=[f"راغبو يوم {_ar(day)}", "الجهات المومدة", "ملخص الشهر"])


def topic_tameedat_entity(year, month, question):
    names = _entity_names(year, month)
    name = find_entity(question, names)
    if not name:
        return _entity_not_found(year, month, question, "الجهة غير موجودة في التاميدات")
    from data_access import db_tameedat as dt
    entity = dt.find_entity_by_name(year, month, name)
    records = [rec for rec in dt.month_records(year, month) if rec["entity_name"] == name]
    stats = dt.dict_month_stats(year, month).get(entity["id"], {})
    own = stats.get("own") or {}
    days = [rec["day"] for rec in records]
    blocks = [p(f"جهة «{name}» في {_month_title(year, month)}:")]
    if not records:
        blocks.append(note("مفيش تأميدات مسجّلة لهذه الجهة في الشهر النشط بعد."))
    else:
        blocks.append(kv([
            ["النوع", entity["entity_type"] or "—"],
            ["عدد التأميدات", _ar(len(records))],
            ["أول يوم", _fmt_date(year, month, min(days))],
            ["آخر يوم", _fmt_date(year, month, max(days))],
            ["إجمالي مسجّل", _pair(round(own.get("total_officers", 0)),
                                   round(own.get("total_individuals", 0)))],
            ["متوسط التأميدة", _pair(round(own.get("avg_officers", 0), 3),
                                     round(own.get("avg_individuals", 0), 3))],
            ["شارة ملحقة", f"×{_ar(stats['att_count'])}" if stats.get("att_count") else "—"],
        ]))
        blocks.append(table(["اليوم", "من – إلى", "ضابط", "فرد", "مجندين", "الإجمالي"],
                            [[_ar(rec["day"]),
                              f"{_fmt_date(year, month, rec['day'])} → {_fmt_date(year, month, rec['day_to'])}",
                              _ar(rec["officers"]), _ar(rec["individuals"]),
                              _ar(rec["recruits"]), _ar(rec["grand_total"])] for rec in records]))
    return result(f"تأميدات «{name}»", blocks, links=[L_TAMEEDAT, L_MOMODA, L_DICT],
                  followups=[f"راغبين {name}", "الجهات المومدة", "تنبيهات الشهر"])


def topic_momoda(year, month, question):
    """الجهات المومدة بالشهر: أيام التميد وعدد التأميدات والإجماليات — من month_summary."""
    from data_access import db_tameedat as dt
    summary, totals = dt.month_summary(year, month)
    if not summary:
        return result(f"الجهات المومدة — {_month_title(year, month)}", [
            p("مفيش جهات مومدة في الشهر النشط بعد — سجّل تأميدة أولًا.")],
            links=[L_TAMEEDAT], followups=["افتح التاميدات", "ملخص الشهر"])
    rows = []
    for index, row in enumerate(sorted(summary, key=lambda item: -item["grand_total"]), 1):
        rows.append([str(index), row["name"] + (" (ملحقة)" if row["kind"] == "attachment" else ""),
                     row["entity_type"] or "—", _ar(row["active_days"]), _ar(row["records"]),
                     _ar(row["total_officers"]), _ar(row["total_individuals"]),
                     _ar(row["total_recruits"]), _ar(row["grand_total"])])
    return result(f"الجهات المومدة — {_month_title(year, month)}", [
        kv([["عدد الجهات المومدة", _ar(totals["entities"])],
            ["إجمالي القوة", _ar(totals["grand"])],
            ["أيام التميد الفعلية", _ar(totals["active_days"])]]),
        table(["م", "الجهة", "النوع", "أيام", "تأميدات", "ضابط", "فرد", "مجندين", "الإجمالي"], rows)],
        links=[L_MOMODA, L_TAMEEDAT], followups=["قاموس الجهات", "تنبيهات الشهر",
                                                 "ملخص الشهر"])


def topic_tameedat_month(year, month, question):
    from data_access import db_tameedat as dt
    records = dt.month_records(year, month)
    summary, totals = dt.month_summary(year, month)
    if not records:
        return result(f"تأميدات {_month_title(year, month)}", [
            p("مفيش تأميدات مسجلة في الشهر النشط بعد.")],
            links=[L_TAMEEDAT], followups=["افتح التاميدات", "ملخص الشهر"])
    top = sorted(summary, key=lambda row: -row["grand_total"])[:5]
    rows = [[str(index), row["name"] + (" (ملحقة)" if row["kind"] == "attachment" else ""),
             row["entity_type"] or "—", _ar(row["active_days"]), _ar(row["records"]),
             _ar(row["total_officers"]), _ar(row["total_individuals"]),
             _ar(row["total_recruits"]), _ar(row["grand_total"])]
            for index, row in enumerate(top, 1)]
    return result(f"تأميدات {_month_title(year, month)}", [
        kv([["عدد التأميدات", _ar(len(records))],
            ["الجهات المومدة", _ar(totals["entities"])],
            ["إجمالي القوة", _ar(totals["grand"])],
            ["الأيام المسجلة", _ar(totals["active_days"])],
            ["إجمالي ضابط/فرد/مجندين", _pair(totals["officers"], totals["individuals"],
                                   totals["recruits"])]]),
        p("أعلى الجهات بالإجمالي:"), table(["م", "الجهة", "النوع", "أيام", "تأميدات",
                                             "ضابط", "فرد", "مجندين", "الإجمالي"], rows)],
        links=[L_TAMEEDAT, L_MOMODA], followups=["الجهات المومدة", "تنبيهات الشهر",
                                                 "تأميدات اليوم"])


# ══════════════════════════════════════════════════════════════════════
# الراغبون والكوادر
# ══════════════════════════════════════════════════════════════════════
def topic_raghibin_day(year, month, question):
    """راغبو يوم محدد: الأسماء المسجّلة فعلًا من ragh_daily — من طبقة البيانات الرسمية."""
    from data_access import db_raghibin as rp
    from data_access import db_tameedat as dt
    day = T.day_number(question)
    if not day:
        today = egtime.today()
        day = today.day if (today.year, today.month) == (year, month) else 1
    if not 1 <= day <= egtime.days_in_month(year, month):
        day = 1
    state = rp.day_state(year, month, day)          # {person_id: willing}
    persons = rp.list_persons(year, month)
    per_entity = {}
    for person in persons:
        if not state.get(person["id"]):
            continue
        row = per_entity.setdefault(person["entity_id"],
                                    {"officers": 0, "individuals": 0, "names": []})
        key = "officers" if person["category"] == "officers" else "individuals"
        row[key] += 1
        row["names"].append(person["full_name"])
    blocks, total_o, total_i = [], 0, 0
    if not per_entity:
        blocks.append(p(f"مفيش أي راغب مسجّل بالأسماء في يوم {_ar(day)} "
                        f"({_fmt_date(year, month, day)})."))
    else:
        rows = []
        for entity_id, row in per_entity.items():
            entity = dt.get_entity(year, month, entity_id) or {}
            total_o += row["officers"]
            total_i += row["individuals"]
            rows.append([entity.get("name", "—"), _ar(row["officers"]), _ar(row["individuals"])])
        rows.sort(key=lambda item: item[0])
        blocks.append(table(["الجهة", "ض مسجّل", "أ مسجّل"], rows))
        blocks.append(kv([["إجمالي المسجّل", _pair(total_o, total_i)],
                          ["عدد الجهات", _ar(len(rows))],
                          ["التاريخ", _fmt_date(year, month, day)]]))
        top = sorted(per_entity.items(), key=lambda item: -(item[1]["officers"]
                                                            + item[1]["individuals"]))[0][1]
        if top["names"]:
            blocks.append(bullets([f"أسماء مسجّلة: {'، '.join(top['names'][:6])}"
                                   + (" …" if len(top["names"]) > 6 else "")]))
    return result(f"راغبو يوم {_ar(day)} — {_month_title(year, month)}", blocks,
                  links=[L_RAG, L_CADRES],
                  followups=[f"تأميدات يوم {_ar(day)}", "الكوادر", "تنبيهات الشهر"])


def _entity_not_found(year, month, question, title):
    """سؤال عن جهة باسم غير موجود: نعرض الجهات المسجلة فعلًا بدل الصمت.

    تُستخدم فقط لو السؤال فيه إشارة صريحة لاسم جهة («… في …») — أما السؤال العام
    («كام ضابط») فيكمل طريقه للموضوع العام المناسب.
    """
    words = question.split()
    if "في" not in words or len(words) < 4:
        return None
    names = _entity_names(year, month)
    blocks = [p("مفيش جهة بهذا الاسم في قاموس الشهر النشط.")]
    if names:
        blocks.append(p("الجهات المسجلة حاليًا:"))
        blocks.append(bullets(names[:10]))
    else:
        blocks.append(note("القاموس فاضي — سجّل تأميدة أولًا وأي جهة جديدة تُضاف تلقائيًا."))
    return result(title, blocks, links=[L_DICT, L_CADRES],
                  followups=["قاموس الجهات", "الكوادر", "ملخص الشهر"])


def topic_raghibin_entity(year, month, question):
    from data_access import db_raghibin as rp
    names = _entity_names(year, month)
    name = find_entity(question, names)
    if not name:
        return _entity_not_found(year, month, question, "الجهة غير موجودة")
    from data_access import db_tameedat as dt
    entity = dt.find_entity_by_name(year, month, name)
    counts = rp.entity_force_counts(year, month).get(entity["id"], {})
    split = rp.month_willing_split(year, month, entity_id=entity["id"])
    willing_o = sum(day["officers"] for day in split.values())
    willing_i = sum(day["individuals"] for day in split.values())
    excluded = [row for row in rp.list_persons(year, month, entity_id=entity["id"], excluded=True)]
    blocks = [p(f"«{name}» — الصورة كاملة في {_month_title(year, month)}:"),
              kv([["قوة الجهة (ض)", _ar(counts.get("officers", 0))],
                  ["قوة الجهة (أ)", _ar(counts.get("individuals", 0))],
                  ["راغبون مسجّلون (ض)", _ar(willing_o)],
                  ["راغبون مسجّلون (أ)", _ar(willing_i)],
                  ["أيام بـ تسجيل", _ar(len(split))],
                  ["مستثنون", _ar(len(excluded))]])]
    if excluded:
        blocks.append(bullets([f"{row['full_name']} — {row.get('exclude_note') or 'بدون سبب مسجّل'}"
                               for row in excluded[:5]]))
    return result(f"راغبو «{name}»", blocks, links=[L_RAG, L_CADRES],
                  followups=[f"تأميدات {name}", "الكوادر", "تنبيهات الشهر"])


def topic_excluded(year, month, question):
    """عدم الراغبين والمستثنون في الشهر — أسماء صريحة من ragh_persons."""
    from data_access import db_raghibin as rp
    from data_access import db_tameedat as dt
    persons = rp.list_persons(year, month, excluded=True)
    if not persons:
        return result("عدم الراغبين والمستثنون", [
            p("مفيش أي شخص مستثنى مسجّل في الشهر النشط ✔")],
            links=[L_RAG], followups=["الكوادر", "راغبين اليوم", "ملخص الشهر"])
    rows = []
    for person in persons[:12]:
        entity = dt.get_entity(year, month, person["entity_id"]) or {}
        rows.append([person["full_name"], person.get("rank") or "—",
                     entity.get("name", "—"), person.get("exclude_note") or "—"])
    return result("عدم الراغبين والمستثنون", [
        p(f"عدد المستثنين: {_ar(len(persons))} من إجمالي قوة الشهر."),
        table(["الاسم", "الرتبة", "الجهة", "السبب"], rows)],
        links=[L_RAG, L_CADRES], followups=["الكوادر", "تنبيهات الشهر"])


def topic_forces(year, month, question):
    from data_access import db_raghibin as rp
    from data_access import db_tameedat as dt
    if T.any_in(question, "اكبر", "أكبر", "اقل", "أقل", "اعلي", "أعلى", "اضعف", "أضعف",
                "اقوي", "أقوى", "ترتيب"):
        return None                # أسئلة المقارنة يقودها موضوع الترتيب (data_rank)
    counts = rp.entity_force_counts(year, month)
    name = find_entity(question, _entity_names(year, month))
    if name:                       # «قوة الحسنة» ⇒ أرقام الجهة نفسها لا الجدول كله
        return _entity_force(name, year, month)
    if not counts:
        return result("أصل القوة", [p("مفيش كوادر مسجّلة في الشهر النشط بعد.")],
                      links=[L_CADRES], followups=["افتح الكوادر"])
    total_o = sum(row["officers"] for row in counts.values())
    total_i = sum(row["individuals"] for row in counts.values())
    rows = []
    for entity_id, row in counts.items():
        entity = dt.get_entity(year, month, entity_id) or {}
        rows.append((row["officers"] + row["individuals"],
                     [entity.get("name", "—"), _ar(row["officers"]),
                      _ar(row["individuals"]),
                      _ar(row["officers"] + row["individuals"])]))
    rows = [row for _total, row in sorted(rows, key=lambda item: -item[0])]
    return result("أصل القوة والكوادر المعتمدة", [
        kv([["عدد الجهات", _ar(len(counts))],
            ["إجمالي الضباط", _ar(total_o)],
            ["إجمالي الأفراد", _ar(total_i)],
            ["الإجمالي", _ar(total_o + total_i)]]),
        table(["الجهة", "ضابط", "فرد", "الإجمالي"], rows[:12])],
        links=[L_CADRES], followups=["راغبين اليوم", "الجهات المومدة", "ملخص الشهر"])


def _entity_numbers(name, year, month):
    """الأرقام المشتركة لأي جهة: القوة المعتمدة + المسجَّل رغبة + التأميدات."""
    from data_access import db_raghibin as rp
    from data_access import db_tameedat as dt
    entity = dt.find_entity_by_name(year, month, name)
    if not entity:
        return None
    counts = rp.entity_force_counts(year, month).get(entity["id"], {})
    split = rp.month_willing_split(year, month, entity_id=entity["id"])
    excluded = rp.list_persons(year, month, entity_id=entity["id"], excluded=True)
    records = [rec for rec in dt.month_records(year, month) if rec["entity_name"] == name]
    return {
        "entity": entity,
        "officers": counts.get("officers", 0),
        "individuals": counts.get("individuals", 0),
        "willing_officers": sum(day["officers"] for day in split.values()),
        "willing_individuals": sum(day["individuals"] for day in split.values()),
        "willing_days": len(split),
        "excluded": len(excluded),
        "tameedat_count": len(records),
        "tameedat_days": sorted(rec["day"] for rec in records),
    }


def _entity_force(name, year, month):
    """قوة جهة بعينها — الفرق بين المعتمد والمسجَّل رغبة والمستثنى."""
    info = _entity_numbers(name, year, month)
    if not info:
        return None
    blocks = [kv([
        ["عدد الضباط (معتمد)", _ar(info["officers"])],
        ["عدد الأفراد (معتمد)", _ar(info["individuals"])],
        ["إجمالي القوة", _ar(info["officers"] + info["individuals"])],
        ["راغبون مسجّلون", _pair(info["willing_officers"], info["willing_individuals"])],
        ["مستثنون", _ar(info["excluded"])],
    ])]
    return result(f"قوة «{name}» — {_month_title(year, month)}", blocks,
                  links=[L_CADRES, L_RAG], followups=[f"تأميدات {name}", "راغبين اليوم"])


def topic_entity_card(year, month, question):
    """بطاقة جهة كاملة عند ذكر اسمها وحدها بلا كلمة سؤال («قسم شرطة نخل»).

    تُستدعى كخطوة أخيرة قبل «مفهمتش» فقط، فلا تزاحم أي موضوع آخر.
    """
    names = _entity_names(year, month)
    name = find_entity(question, names)
    if not name:
        return None
    info = _entity_numbers(name, year, month)
    if not info:
        return None
    blocks = [
        p(f"«{name}» — كل أرقامها في {_month_title(year, month)}:"),
        kv([["نوع الجهة", info["entity"].get("entity_type") or "—"],
            ["القوة المعتمدة", _pair(info["officers"], info["individuals"])],
            ["راغبون مسجّلون", _pair(info["willing_officers"], info["willing_individuals"])],
            ["أيام بـ تسجيل", _ar(info["willing_days"])],
            ["مستثنون", _ar(info["excluded"])],
            ["تأميدات مسجّلة", _ar(info["tameedat_count"])]]),
        table(["اليوم", "التاريخ", "ضابط", "فرد", "مجندين", "الإجمالي"],
              [["—" if rec["day"] is None else _ar(rec["day"]),
                _fmt_date(year, month, rec["day"]) if rec["day"] else "—",
                _ar(rec.get("total_officers", 0)), _ar(rec.get("total_individuals", 0)),
                _ar(rec.get("total_recruits", 0)),
                _ar((rec.get("total_officers", 0) + rec.get("total_individuals", 0)
                     + rec.get("total_recruits", 0)))]
               for rec in _entity_records(name, year, month)][:8]),
    ]
    if not info["tameedat_days"]:
        blocks.append(note("مفيش تأميدات مسجّلة للجهة دي في الشهر النشط."))
    return result(f"بطاقة جهة: {name}", blocks, links=[L_RAG, L_TAMEEDAT, L_CADRES],
                  followups=[f"تأميدات {name}", f"راغبو {name}", "ملخص الشهر"])


def _entity_records(name, year, month):
    from data_access import db_tameedat as dt
    return [rec for rec in dt.month_records(year, month) if rec["entity_name"] == name]


# ══════════════════════════════════════════════════════════════════════
# المقررات والمخازن والأذون
# ══════════════════════════════════════════════════════════════════════
def topic_rations(year, month, question):
    from data_access import db_rations as dr
    blocks = []
    # سؤال عن معدل صنف بالاسم؟ — الإجابة من المقررات التموينية بالظبط،
    # فهي المصدر الذي تتبعه كل جداول معدلات الأصناف (توجيه ٠٨/١٠/٢٠٦)
    from services.assistant import text as T
    def _words(text):
        out = set()
        for w in " ".join(str(text or "").split()):
            out.add(w[2:] if w.startswith("ال") and len(w) > 2 else w)
        return out

    q_words = _words(question)
    tw_kind = dr.get_activation(year, month, "tamween")
    tw_items = dr.get_items(year, month, "tamween", tw_kind)[0] if tw_kind else []
    # كل كلمة من اسم الصنف لازم تكون في السؤال (مع تجاهل «ال» تعريفًا)
    found = [it for it in tw_items
             if it.get("name") and _words(T.normalize(str(it["name"]))) <= q_words]
    if found:
        rows = [[it["name"], it["unit"] or "—",
                 arnum.fmt_qty(it["breakfast"] or 0),
                 arnum.fmt_qty(it["lunch"] or 0),
                 arnum.fmt_qty(it["dinner"] or 0),
                 arnum.fmt_qty((it["breakfast"] or 0) + (it["lunch"] or 0)
                               + (it["dinner"] or 0))]
                for it in found[:5]]
        blocks.append(p("معدلات الصنف — من المقررات التموينية (المصدر الموحد):"))
        blocks.append(table(["الصنف", "الوحدة", "فطار", "غداء", "عشاء", "إجمالي اليوم"],
                            rows))
    for section, label, link in (("tamween", "المقررات التموينية", L_RATIONS_T),
                                 ("contractor", "مقررات المتعهد", L_RATIONS_C)):
        kind = dr.get_activation(year, month, section)
        items = dr.get_items(year, month, section, kind)[0] if kind else []
        if not kind:
            blocks.append(p(f"{label}: لا يوجد مقرر مفعّل في الشهر النشط."))
            continue
        blocks.append(kv([["القسم", label], ["المقرر النشط", kind],
                          ["عدد الأصناف", _ar(len(items))]]))
        if items:
            blocks.append(table(["الصنف", "الوحدة", "فطار", "غداء", "عشاء"],
                                [[item["name"], item["unit"] or "—",
                                  arnum.fmt_qty(item["breakfast"] or 0),
                                  arnum.fmt_qty(item["lunch"] or 0),
                                  arnum.fmt_qty(item["dinner"] or 0)] for item in items[:8]]))
    links = [L_RATIONS_T, L_RATIONS_C]
    return result("المقررات والكميات للفرد", blocks, links=links,
                  followups=["أرصدة المخازن", "إذون ٢ مخازن", "جهات المقررات"])


def topic_warehouses(year, month, question):
    from data_access import db_warehouses as dw
    blocks, rows_total = [], 0
    for cycle, label in (("supply", "التموين"), ("contractor", "المتعهد")):
        items = dw.list_items(year, month, cycle)
        balances = dw.item_balances(year, month, cycle)
        rows = [[item["name"], item.get("handle_unit") or item.get("ration_unit") or "—",
                 arnum.fmt_qty(balances.get(item["id"], 0))] for item in items]
        rows_total += len(rows)
        zero = [row for row in rows if row[2] in ("٠٫٠٠٠", "0.000")]
        blocks.append(kv([["دورة", label], ["عدد الأصناف", _ar(len(rows))],
                          ["أصناف برصيد صفر", _ar(len(zero))]]))
        if rows:
            blocks.append(table(["الصنف", "الوحدة", "الرصيد"], rows[:10]))
    return result("أرصدة المخازن", [p(f"إجمالي {_ar(rows_total)} صنفًا مسجّلًا عبر الدورتين.")] + blocks,
                  links=[L_WAREHOUSES, L_CALC2],
                  followups=["إذون ٢ مخازن", "المقررات", "الترفية"])


def topic_permits(year, month, question):
    from data_access import db_permits as dp
    permits = dp.list_permits(year, month)
    if not permits:
        return result("إذون ٢ مخازن", [p("مفيش أذون صرف مسجّلة في الشهر النشط بعد.")],
                      links=[L_CALC2], followups=["افتح آلة حاسبة ٢ مخازن"])
    days = set()
    for permit in permits:
        days.update(range(permit.get("date_from") or 1, (permit.get("date_to") or 1) + 1))
    rows = [[_ar(permit.get("number") or "—"), permit.get("entity_label") or "—",
             _ar(permit.get("date_from") or 0), _ar(permit.get("date_to") or 0),
             _ar(permit.get("issue_days") or 0)] for permit in permits[:10]]
    return result("إذون صرف ٢ مخازن", [
        kv([["عدد الأذون", _ar(len(permits))], ["أيام صرف مغطاة", _ar(len(days))]]),
        table(["رقم الإذن", "الجهة", "من يوم", "إلى يوم", "أيام الصرف"], rows)],
        links=[L_CALC2, L_WAREHOUSES], followups=["أرصدة المخازن", "التفاريد", "ملخص الشهر"])


def topic_tarfea(year, month, question):
    from data_access import db_tarfea as dtf
    report = dtf.stock_report(year, month)
    issues = dtf.list_issues(year, month)
    if not report:
        return result("الترفية", [p("مفيش أصناف مسجلة في الترفية للشهر النشط.")],
                      links=[L_TARFEA], followups=["افتح الترفية"])
    rows = [[row["name"], row.get("unit") or "—", arnum.fmt_qty(row["balance"])]
            for row in report]
    return result("أرصدة الترفية", [
        kv([["عدد الأصناف", _ar(len(rows))], ["حركات الصرف", _ar(len(issues))],
           ["المخزن", "مخزن الترفية (محدد تلقائيًا — من غير اختيار)"]]),
        table(["الصنف", "الوحدة", "الرصيد"], rows[:10])],
        links=[L_TARFEA], followups=["المخازن والثلاجات", "أرصدة المخازن"])


def topic_stores(year, month, question):
    from data_access import db_stores
    stores = db_stores.list_stores()
    if not stores:
        return result("المخازن والثلاجات", [p("مفيش مخازن مسجّلة بعد.")],
                      links=[L_STORES], followups=["افتح المخازن والثلاجات"])
    rows = [[store.get("name") or "—", store.get("location") or "—",
             _ar(store.get("capacity_m2") or 0)] for store in stores]
    return result("المخازن والثلاجات", [
        p(f"عدد المخازن المسجّلة: {_ar(len(stores))}."),
        table(["المخزن", "الموقع", "السعة (م²)"], rows)],
        links=[L_STORES, L_WAREHOUSES], followups=["أرصدة المخازن", "الترفية"])


# ══════════════════════════════════════════════════════════════════════
# المجندون والصحة والمناسبات والنسخ
# ══════════════════════════════════════════════════════════════════════
def topic_recruits(year, month, question):
    from data_access import db_recruits as dr
    recruits = dr.list_recruits(year, month)
    if not recruits:
        return result("المجندون", [p("مفيش مجندون مسجّلون في الشهر النشط بعد.")],
                      links=[L_RECRUITS], followups=["افتح المجندين"])
    today = egtime.today()
    states = [(row, dr.cert_state(row, today)) for row in recruits]
    expired = [row for row, state in states if state == "expired"]
    soon = [row for row, state in states if state == "soon"]
    near = [(row, dr.days_to_discharge(row, today)) for row in recruits]
    near = [(row, days) for row, days in near if days is not None and 0 <= days <= 90]
    blocks = [kv([["عدد المجندين", _ar(len(recruits))],
                  ["شهادات منتهية", _ar(len(expired))],
                  ["شهادات قرب الانتهاء", _ar(len(soon))],
                  ["قرب انتهاء الخدمة (٩٠ يومًا)", _ar(len(near))]])]
    if expired:
        blocks.append(bullets([f"شهادة منتهية: {row.get('name')} "
                               f"({row.get('mil_no') or '—'})" for row in expired[:6]]))
    if near:
        blocks.append(bullets([f"قرب انتهاء الخدمة: {row.get('name')} — خلال {_ar(days)} يومًا"
                               for row, days in near[:6]]))
    return result("حالة المجندين", blocks, links=[L_RECRUITS],
                  followups=["شهادات منتهية", "ملخص الشهر"])


def topic_health(year, month, question):
    """نظرة الصحة: أيام الكشف المسجّلة + أعضاء الكشف الشهري — من db_health الرسمي."""
    from data_access import db_health
    try:
        days = db_health.month_checkup_ids(year, month)
    except Exception:      # noqa: BLE001 — المساعد لا يسقط بسبب تقرير فارغ
        days = []
    count = len(days) if hasattr(days, "__len__") else 0
    return result("قسم الصحة", [
        kv([["أيام الكشف المسجّلة", _ar(count)],
            ["الشهر", _month_title(year, month)]]),
        note("قسم الصحة يشمل التقارير الطبية والخزانات ومرفقاتها، وكل بياناته داخل "
             "فولدر الشهر المحلي على جهازك.")],
        links=[L_HEALTH], followups=["المجندين", "ملخص الشهر"])


def topic_backups(year, month, question):
    from data_access import dataguard
    from core import dates as _dates
    backups = dataguard.list_backups()
    if not backups:
        return result("النسخ الاحتياطي", [p("مفيش نسخ احتياطية بعد — أنشئ نسخة من صفحة "
                                            "«النسخ الاحتياطي والحماية».")],
                      links=[L_BACKUPS], followups=["افتح النسخ الاحتياطي"])
    latest = backups[0]
    rows = [[item["name"], f"{item['size'] / 1024:.3f} ك.ب.",
             _dates.format_datetime(egtime.from_timestamp(item["mtime"]), seconds=True)]
            for item in backups[:5]]
    return result("النسخ الاحتياطي", [
        kv([["عدد النسخ", f"{_ar(len(backups))} (من أصل {_ar(dataguard.KEEP_N)} محفوظة)"],
            ["آخر نسخة", _dates.format_datetime(egtime.from_timestamp(latest["mtime"]),
                                                seconds=True)]]),
        table(["النسخة", "الحجم", "الوقت"], rows)],
        links=[L_BACKUPS], followups=["ملخص الشهر"])


def topic_occasions(year, month, question):
    from services import occasions_fs
    counts = occasions_fs.stats()
    recent = occasions_fs.list_occasions()[:5]
    blocks = [kv([["عدد المناسبات", _ar(counts["occasions"])],
                  ["الصور", _ar(counts["photos"])],
                  ["الفيديو", _ar(counts["videos"])],
                  ["الأنواع", _ar(counts["kinds"])]])]
    if recent:
        blocks.append(bullets([f"{item.get('title') or '—'} — "
                               f"{item.get('date') or 'بدون تاريخ'}" for item in recent]))
    return result("التوثيق والمناسبات", blocks, links=[L_OCCASIONS],
                  followups=["ملخص الشهر"])


def topic_letterhead(year, month, question):
    from data_access import db_letterhead as lhdb
    values = lhdb.get_all(year, month)
    logo = lhdb.logo_path(year, month)
    lines = [[f"السطر {_ar(index)}", values.get(f"lh_{index}") or "—"] for index in range(1, 5)]
    return result("الدباجة والتوقيعات", [
        kv([["اللوجو", "مرفوع ✔" if logo else "غير مرفوع"],
            ["جاهزية المستند", "جاهز ✔" if values.get("lh_1") else "ناقص — أضف أسطر الدباجة"]]),
        table(["البيان", "النص"], lines),
        note("التوقيعان مثبّتان: يمينًا «رائد / مصطفى نصرالله» — شمالًا "
             "«مقدم / اسامة العجرودى».")],
        links=[{"label": "الدباجة والتوقيعات", "target": "letterhead"}],
        followups=["إزاي أطبع؟", "ملخص الشهر"])
