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


def _issue(level, text, key):
    return {"level": level, "text": text, "key": key}


def no_tameeda_issue(total_willing):
    """راغبين مسجلين في يوم من غير ما يكون فيه تأميدة للجهة (توجيه ١٠/١٠/٢٠٦)."""
    return _issue(
        "danger",
        f"تم تسجيل {_ar(total_willing)} راغبين في هذا اليوم بلا تأميدة "
        f"لهذه الجهة — سجّل التأميدة في تبويب التاميدات أولًا",
        "no_tameeda")


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
            "سجّل أسماء قوتها (ضباط/أفراد) أولًا",
            "no_cadres"))
    else:
        if not tameeda["officers"] and cadres["officers"]:
            issues.append(_issue("info", "التأميدة بلا ضباط مع وجود قوة ضباط مسجلة",
                                 "no_officers"))
        if not tameeda["individuals"] and cadres["individuals"]:
            issues.append(_issue("info", "التأميدة بلا أفراد مع وجود قوة أفراد مسجلة",
                                 "no_individuals"))

    total_willing = willing["officers"] + willing["individuals"]
    if not total_willing:
        issues.append(_issue(
            "danger",
            "لا يوجد أي راغب مسجل بالأسماء في هذا اليوم — "
            f"التأميدة مسجلة ضباط {_ar(tameeda['officers'])} وأفراد {_ar(tameeda['individuals'])}",
            "no_willing"))
        return issues

    if willing["officers"] < tameeda["officers"]:
        issues.append(_issue(
            "warn",
            f"الراغبون المسجلون ضباط {_ar(willing['officers'])} "
            f"أقل من التأميدة ({_ar(tameeda['officers'])}) — الناقص "
            f"{_ar(tameeda['officers'] - willing['officers'])}",
            "officers_low"))
    elif willing["officers"] > tameeda["officers"]:
        issues.append(_issue(
            "warn",
            f"الراغبون المسجلون ضباط {_ar(willing['officers'])} "
            f"أكثر من التأميدة ({_ar(tameeda['officers'])})",
            "officers_high"))
    if willing["individuals"] < tameeda["individuals"]:
        issues.append(_issue(
            "warn",
            f"الراغبون المسجلون أفراد {_ar(willing['individuals'])} "
            f"أقل من التأميدة ({_ar(tameeda['individuals'])}) — الناقص "
            f"{_ar(tameeda['individuals'] - willing['individuals'])}",
            "individuals_low"))
    elif willing["individuals"] > tameeda["individuals"]:
        issues.append(_issue(
            "warn",
            f"الراغبون المسجلون أفراد {_ar(willing['individuals'])} "
            "أكثر من التأميدة "
            f"({_ar(tameeda['individuals'])})",
            "individuals_high"))
    issues.sort(key=lambda item: LEVEL_ORDER.get(item["level"], 9))
    return issues


def month_rows(year, month, only_issues=True):
    """صفوف التنبيهات لكل تأميدة × كل يوم داخلها — مرتّبة باليوم.

    only_issues=False يعرض كل الأيام السليمة أيضًا (يُستخدم في عرض «الكل»).
    """
    records = dt.month_records(year, month)
    cadres_cache, willing_cache = {}, {}
    ignored = {(i["entity_id"], i["day"], i["issue_key"])
               for i in dt.alert_ignores(year, month)}
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
            key = (entity_id, day)
            visible = [i for i in issues
                       if (key[0], key[1], i["key"]) not in ignored]
            hidden = [i for i in issues if i not in visible]
            if only_issues and not visible and not hidden:
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
                "issues": visible,
                "ignored_issues": hidden,
                "level": visible[0]["level"] if visible else "ok",
                "level_label": LEVEL_LABEL.get(visible[0]["level"], "سليم") if visible else "سليم",
            })
    # أيام بلا تأميدة: راغبين مسجلين من غير تأميدة للجهة (توجيه ١٠/١٠/٢٠)
    covered = set()
    for record in records:
        for d in range(record["day"], (record.get("day_to") or record["day"]) + 1):
            covered.add((record["entity_id"], d))
    for ent in dt.list_entities(year, month):
        eid = ent["id"]
        willing_by_day = rp.month_willing_split(year, month, eid)
        for day in sorted(willing_by_day):
            willing = willing_by_day[day]
            total_w = willing["officers"] + willing["individuals"]
            if (eid, day) in covered or not total_w:
                continue
            issue = no_tameeda_issue(total_w)
            if (eid, day, issue["key"]) in ignored:
                continue
            rows.append({
                "record_id": None,
                "day": day,
                "date_text": dates.period_date(year, month, day),
                "weekday": egtime.weekday_ar(dates.parse_date(
                    f"{year:04d}-{month:02d}-{day:02d}")),
                "entity_id": eid,
                "entity_name": ent["name"],
                "entity_type": ent.get("entity_type") or "—",
                "range_days": 1,
                "tameeda": {"officers": 0, "individuals": 0},
                "recruits": 0,
                "willing": willing,
                "cadres": {"officers": 0, "individuals": 0},
                "attachments": 0,
                "issues": [issue],
                "ignored_issues": [],
                "level": "danger",
                "level_label": LEVEL_LABEL["danger"],
            })
    rows.sort(key=lambda row: (row["day"], row["entity_name"]))
    return rows


def summary(year, month):
    """ملخص الجدول: عدد الصفوف، وعدد كل مستوى (المعروض فقط)، وعدد المُتجاهَل."""
    rows = month_rows(year, month, only_issues=False)
    problem_rows = [row for row in rows if row["issues"]]
    counts = {"danger": 0, "warn": 0, "info": 0}
    for row in problem_rows:
        counts[row["issues"][0]["level"]] += 1
    ignored_total = sum(len(row["ignored_issues"]) for row in rows)
    return {
        "rows": len(rows),
        "problem_rows": len(problem_rows),
        "danger": counts["danger"],
        "warn": counts["warn"],
        "info": counts["info"],
        "ignored": ignored_total,
        "entities": len({row["entity_id"] for row in problem_rows}),
        "days": len({row["day"] for row in problem_rows}),
    }


def ignored_names(year, month):
    """أسماء جهات اتتجاهل تنبيهها الحي («غير مسجلة» في الفورم) — للشهر كله."""
    return dt.alert_ignored_names(year, month)


def record_warning(year, month, entity, day, day_to, officers, individuals):
    """نص تنبيه الحفظ لتأميدة جديدة/معدّلة — يشمل عدد الراغبين وغياب الكوادر.

    يُستدعى من مسار الحفظ (لا يمنع الحفظ) ويُعرض في رسالة الحفظ نفسها.
    """
    entity_id = entity["id"] if isinstance(entity, dict) else entity
    cadres = entity_cadres(year, month, entity_id)
    tameeda = {"officers": officers or 0, "individuals": individuals or 0}
    willing_by_day = rp.month_willing_split(year, month, entity_id)
    ignored = {(i["entity_id"], i["day"], i["issue_key"])
               for i in dt.alert_ignores(year, month)}
    problems = []
    for d in range(int(day), int(day_to or day) + 1):
        willing = willing_by_day.get(d, {"officers": 0, "individuals": 0})
        for issue in record_day_issues(tameeda, willing, cadres):
            if (entity_id, d, issue["key"]) in ignored:
                continue                      # اتجاهل — اتُمسح من كل العرصات
            problems.append(f"يوم {_ar(d)}: {issue['text']}")
    if not problems:
        return None
    listed = " | ".join(problems[:6])
    tail = " … (والمزيد في جدول تنبيهات الشهر)" if len(problems) > 6 else ""
    return ("⚠ تنبيهات الراغبين (لا تمنع الحفظ): " + listed + tail
            + " — راجع جدول التنبيهات أسفل الصفحة")
