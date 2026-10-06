# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""محرك تنبيهات التاميدات ↔ الراغبين لـ**كل أيام الشهر** (توجيه المستخدم ٠٦/١٠/٢٠٢٦).

المشكلة التي يعالجها: التنبيه كان يظهر ليوم واحد فقط (اليوم المفتوح)، وكان يقارن
الأرقام بلا ذكر عدد الراغبين المسجلين فعلًا، ولا ينبّه أن الجهة غير مسجلة أصلًا في
«الجهات والكوادر المعتمدة». الآن يُبنى جدول تنبيهات للشهر كله يُفتح ويُغلق:

  ١) الجهة غير مسجلة في «الجهات والكوادر المعتمدة» بالراغبين (لا أسماء لها).
  ٢) اليوم بلا أي راغب مسجل بالأسماء مع وجود تأميدة.
  ٣) الراغبون المسجلون أقل من أعداد التأميدة (النقص) أو أكثر منها (الزيادة).
  ٤) التأميدة بلا ضباط أو بلا أفراد بينما القوة مسجلة.

كل المقارنات على ضباط/أفراد فقط — المجندون خارج مقارنة الراغبين (قاعدة ملزمة).
هذه التنبيهات لا تمنع الحفظ أبدًا؛ هي إرشادية فقط.
"""
from core import arabic_numbers as arnum, dates, egtime
from data_access import db_raghibin as rp
from data_access import db_tameedat as dt

LEVEL_ORDER = {"danger": 0, "warn": 1, "info": 2}
LEVEL_LABEL = {"danger": "خطر", "warn": "تنبيه", "info": "معلومة"}


def _ar(value):
    return arnum.to_arabic_indic(str(int(value or 0)))


def _issue(level, text):
    return {"level": level, "text": text}


def entity_cadres(year, month, entity_id):
    """قوة الجهة في «الجهات والكوادر المعتمدة»: أعداد الضباط والأفراد (والمستثنون)."""
    counts = rp.entity_force_counts(year, month, entity_id).get(
        entity_id, {"officers": 0, "individuals": 0,
                    "officers_excluded": 0, "individuals_excluded": 0})
    return counts


def record_day_issues(tameeda, willing, cadres):
    """تنبيهات تأميدة واحدة في يوم واحد — تُرجع قائمة منسدلة مرتّبة بالخطورة."""
    issues = []
    if not cadres["officers"] and not cadres["individuals"]:
        issues.append(_issue(
            "danger",
            "الجهة غير مسجلة في «الجهات والكوادر المعتمدة» بالراغبين — "
            "سجّل أسماء قوتها (ضباط/أفراد) أولًا"))
    else:
        if not tameeda["officers"] and cadres["officers"]:
            issues.append(_issue("info", "التأميدة بلا ضباط مع وجود قوة ضباط مسجلة"))
        if not tameeda["individuals"] and cadres["individuals"]:
            issues.append(_issue("info", "التأميدة بلا أفراد مع وجود قوة أفراد مسجلة"))

    total_willing = willing["officers"] + willing["individuals"]
    if not total_willing:
        issues.append(_issue(
            "danger",
            "مفيش راغب واحد مسجل بالأسماء في اليوم ده — "
            f"التأميدة مسجلة ضباط {_ar(tameeda['officers'])} وأفراد {_ar(tameeda['individuals'])}"))
        return issues

    if willing["officers"] < tameeda["officers"]:
        issues.append(_issue(
            "warn",
            f"الراغبون المسجلون ضباط {_ar(willing['officers'])} "
            f"أقل من التأميدة ({_ar(tameeda['officers'])}) — الناقص "
            f"{_ar(tameeda['officers'] - willing['officers'])}"))
    elif willing["officers"] > tameeda["officers"]:
        issues.append(_issue(
            "warn",
            f"الراغبون المسجلون ضباط {_ar(willing['officers'])} "
            f"أكثر من التأميدة ({_ar(tameeda['officers'])})"))
    if willing["individuals"] < tameeda["individuals"]:
        issues.append(_issue(
            "warn",
            f"الراغبون المسجلون أفراد {_ar(willing['individuals'])} "
            f"أقل من التأميدة ({_ar(tameeda['individuals'])}) — الناقص "
            f"{_ar(tameeda['individuals'] - willing['individuals'])}"))
    elif willing["individuals"] > tameeda["individuals"]:
        issues.append(_issue(
            "warn",
            f"الراغبون المسجلون أفراد {_ar(willing['individuals'])} "
            "أكثر من التأميدة "
            f"({_ar(tameeda['individuals'])})"))
    issues.sort(key=lambda item: LEVEL_ORDER.get(item["level"], 9))
    return issues


def month_rows(year, month, only_issues=True):
    """صفوف التنبيهات لكل تأميدة × كل يوم داخلها — مرتّبة باليوم.

    only_issues=False يعرض كل الأيام السليمة أيضًا (يُستخدم في عرض «الكل»).
    """
    records = dt.month_records(year, month)
    cadres_cache, willing_cache = {}, {}
    rows = []
    for record in records:
        entity_id = record["entity_id"]
        if entity_id not in cadres_cache:
            cadres_cache[entity_id] = entity_cadres(year, month, entity_id)
        if entity_id not in willing_cache:
            willing_cache[entity_id] = rp.month_willing_split(year, month, entity_id)
        cadres = cadres_cache[entity_id]
        willing_by_day = willing_cache[entity_id]
        day_from = record["day"]
        day_to = record.get("day_to") or record["day"]
        for day in range(day_from, day_to + 1):
            willing = willing_by_day.get(day, {"officers": 0, "individuals": 0})
            tameeda = {"officers": record["officers"], "individuals": record["individuals"]}
            issues = record_day_issues(tameeda, willing, cadres)
            if only_issues and not issues:
                continue
            rows.append({
                "record_id": record["id"],
                "day": day,
                "date_text": dates.period_date(year, month, day),
                "weekday": egtime.weekday_ar(dates.parse_date(
                    f"{year:04d}-{month:02d}-{day:02d}")),
                "entity_id": entity_id,
                "entity_name": record["entity_name"],
                "entity_type": record["entity_type"],
                "range_days": record.get("range_days", 1),
                "tameeda": tameeda,
                "recruits": record["recruits"],
                "willing": willing,
                "cadres": {"officers": cadres["officers"], "individuals": cadres["individuals"]},
                "attachments": len(record.get("attachments") or []),
                "issues": issues,
                "level": issues[0]["level"] if issues else "ok",
                "level_label": LEVEL_LABEL.get(issues[0]["level"], "سليم") if issues else "سليم",
            })
    rows.sort(key=lambda row: (row["day"], row["entity_name"]))
    return rows


def summary(year, month):
    """ملخص الجدول: عدد الصفوف، وعدد كل مستوى، وعدد الجهات المتأثرة."""
    rows = month_rows(year, month, only_issues=False)
    problem_rows = [row for row in rows if row["issues"]]
    counts = {"danger": 0, "warn": 0, "info": 0}
    for row in problem_rows:
        counts[row["issues"][0]["level"]] += 1
    return {
        "rows": len(rows),
        "problem_rows": len(problem_rows),
        "danger": counts["danger"],
        "warn": counts["warn"],
        "info": counts["info"],
        "entities": len({row["entity_id"] for row in problem_rows}),
        "days": len({row["day"] for row in problem_rows}),
    }


def record_warning(year, month, entity, day, day_to, officers, individuals):
    """نص تنبيه الحفظ لتأميدة جديدة/معدّلة — يشمل عدد الراغبين وغياب الكوادر.

    يُستدعى من مسار الحفظ (لا يمنع الحفظ) ويُعرض في رسالة الحفظ نفسها.
    """
    entity_id = entity["id"] if isinstance(entity, dict) else entity
    cadres = entity_cadres(year, month, entity_id)
    tameeda = {"officers": officers or 0, "individuals": individuals or 0}
    willing_by_day = rp.month_willing_split(year, month, entity_id)
    problems = []
    for d in range(int(day), int(day_to or day) + 1):
        willing = willing_by_day.get(d, {"officers": 0, "individuals": 0})
        for issue in record_day_issues(tameeda, willing, cadres):
            problems.append(f"يوم {_ar(d)}: {issue['text']}")
    if not problems:
        return None
    listed = " | ".join(problems[:6])
    tail = " … (والمزيد في جدول تنبيهات الشهر)" if len(problems) > 6 else ""
    return ("⚠ تنبيهات الراغبين (لا تمنع الحفظ): " + listed + tail
            + " — راجع جدول التنبيهات أسفل الصفحة")
