# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""إجابات المقارنة والترتيب: أكبر/أقل الجهات + الأيام الناقصة في التسجيل.

كل الأرقام من الطبقات الرسمية نفسها (`db_raghibin` · `db_tameedat`) بلا حساب موازٍ:
قوة الجهة المعتمدة، وعدد راغبيها المسجّلين فعليًا، وعدد أيام تسجيلهم، وعدد تأميداتها.
"""
from core import arabic_numbers as arnum

from . import text as T
from .data_answers import (L_CADRES, L_RAG, L_TAMEEDAT, _ar, _month_title, bullets, kv,
                           note, p, result, table)


def _entity_rows(year, month):
    """صف لكل جهة: القوة المعتمدة + المسجَّل رغبة في الشهر + أيام التسجيل + التأميدات."""
    from data_access import db_raghibin as rp
    from data_access import db_tameedat as dt
    counts = rp.entity_force_counts(year, month)
    records = {}
    for rec in dt.month_records(year, month):
        records[rec["entity_name"]] = records.get(rec["entity_name"], 0) + 1
    rows = []
    for entity_id, force in counts.items():
        entity = dt.get_entity(year, month, entity_id) or {}
        name = entity.get("name") or "—"
        split = rp.month_willing_split(year, month, entity_id=entity_id)
        willing = sum(day["officers"] + day["individuals"] for day in split.values())
        total = force["officers"] + force["individuals"]
        rows.append({"name": name, "officers": force["officers"],
                     "individuals": force["individuals"], "total": total,
                     "willing": willing, "days": len(split),
                     "tameedat": records.get(name, 0),
                     "rate": round(100 * willing / total) if total else 0})
    return rows


def topic_top_entities(year, month, question):
    """«أكبر جهة / أقل الجهات قوة / ترتيب الجهات» — مقارنة حقيقية بالشهر النشط."""
    from data_access import db_tameedat as dt
    if not dt.list_entities(year, month):
        return result("ترتيب الجهات", [
            note("مفيش جهات مسجّلة في الشهر النشط بعد — سجّل جهة من «الجهات والكوادر المعتمدة»."),
        ], links=[L_CADRES], followups=["افتح الكوادر", "ملخص الشهر"])
    rows = _entity_rows(year, month)
    if not rows:
        return result("ترتيب الجهات", [
            note("مفيش كوادر معتمدة بالشهر النشط بعد — سجّل الكوادر أولًا."),
        ], links=[L_CADRES], followups=["افتح الكوادر", "ملخص الشهر"])
    ascending = T.any_in(question, "اقل", "اضعف", "اصغر", "ضعيف")
    rows.sort(key=lambda row: row["total"], reverse=not ascending)
    label = "الأقل قوة" if ascending else "الأكبر قوة"
    top = rows[:6]
    blocks = [p(f"{label} في {_month_title(year, month)} (من أصل {_ar(len(rows))} جهة):"),
              table(["الجهة", "القوة المعتمدة", "راغبون مسجّلون", "أيام تسجيل", "تأميدات"],
                    [[row["name"], _ar(row["total"]), _ar(row["willing"]),
                      _ar(row["days"]), _ar(row["tameedat"])] for row in top])]
    first = top[0]
    blocks.append(kv([[f"صاحبة الصدارة ({label})", first["name"]],
                      ["قوتها المعتمدة", _ar(first["total"])],
                      ["مسجَّل من قوتها", f"{_ar(first['willing'])} — نسبة {arnum.to_arabic_indic(str(first['rate']))}٪"],
                      ["تأميداتها في الشهر", _ar(first["tameedat"])]]))
    blocks.append(note("الترتيب على القوة المعتمدة (ضباط + أفراد)؛ والمسجَّل رغبة يُقارَن بها "
                       "لمعرفة نسبة التجاوب — والأرقام نفسها التي في التاميدات والراغبين."))
    return result(f"ترتيب الجهات — {label}", blocks, links=[L_CADRES, L_RAG, L_TAMEEDAT],
                  followups=[f"قوة {first['name']}", f"راغبو {first['name']}",
                             "الأيام الناقصة في التسجيل"])


def topic_missing_days(year, month, question):
    """«أيام بلا تسجيل / أيام فيها تأميدات وبدون راغبين» — مراجعة تسجيل الشهر."""
    from core import egtime
    from data_access import db_raghibin as rp
    from data_access import db_tameedat as dt
    last = egtime.days_in_month(year, month)
    willing_days = set(rp.day_willing_counts(year, month))          # أيام فيها راغبون فعلًا
    tameed_days = set(dt.day_counts(year, month))                   # أيام فيها تأميدات سارية
    mismatch = sorted(tameed_days - willing_days)                   # تأميدات بلا تسجيل رغبة
    no_record = [day for day in range(1, last + 1)
                 if day not in tameed_days and day not in willing_days]
    blocks = [p(f"مراجعة التسجيل في {_month_title(year, month)}:"),
              kv([["أيام الشهر", _ar(last)],
                  ["أيام فيها تسجيل راغبين", _ar(len(willing_days))],
                  ["أيام فيها تأميدات", _ar(len(tameed_days))],
                  ["أيام ناقصة التسجيل", _ar(len(mismatch))]])]
    if mismatch:
        blocks.append(bullets([f"يوم {_ar(day)} — فيه تأميدات ومفيش أي راغب مسجّل فيه"
                               for day in mismatch[:10]]))
        blocks.append(note("التنبيه للمراجعة فقط ولا يمنع أي حفظ — والنقص معناه أن اليوم "
                           "محتاج تسجيل رغبات الجهات اللي فيها."))
        followups = [f"راغبو يوم {_ar(mismatch[0])}", "تنبيهات الشهر", "ملخص الشهر"]
    else:
        blocks.append(note("مفيش أي يوم فيه تأميدات وبدون تسجيل راغبين ✓ — كل الأيام "
                           "المشدودة مسجّل فيها."))
        followups = ["تنبيهات الشهر", "ملخص الشهر", "راغبين اليوم"]
    if no_record:
        blocks.append(note(f"وفيه {_ar(len(no_record))} يوم بلا تأميدات وبلا تسجيل أصلًا "
                           f"(أولها يوم {_ar(no_record[0])}) — طبيعي ومش تنبيه."))
    return result(f"الأيام الناقصة في التسجيل — {_month_title(year, month)}", blocks,
                  links=[L_RAG, L_TAMEEDAT], followups=followups)
