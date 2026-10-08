# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""متغيرات مودال «كشف وتسجيل أسماء ضابط/فرد الراغبين».

تُستخدم في: جزء /raghibin/panel (الجلب اللحظي) والعرض المدمج داخل صفحة
التأميدات نفسها (جذري ضد رسم صفحة الدخول داخل المودال: المحتوى موجود
في الصفحة من أول تحميل، والجلب مجرد تحديث اختياري فوقه).
"""
from data_access import db_raghibin as dr
from data_access import db_tameedat as dt


def build(year, month, entity, day, cat, sid=""):
    """متغيرات قالب raghibin/modal_body.html لجهة/يوم/فئة."""
    state = dr.day_state(year, month, day, entity["id"]) if entity else {}
    # قائمة القوة في المودال = غير المستثنين فقط (إدارتهم من «الجهات والكوادر»)
    persons = dr.list_persons(year, month, entity_id=entity["id"], category=cat,
                              excluded=False) if entity else []
    for person in persons:
        person["willing_today"] = state.get(person["id"])
    from routes.raghibin.context import _slots_vars
    variables = _slots_vars(year, month, entity, day)
    variables.update({
        "fcat": cat, "entity": entity, "sel_day": day,
        "force_persons": persons,
        "entity_names": dt.entity_names(year, month),
        "categories": dr.CATEGORIES,
        "officer_ranks": dr.RANKS["officers"],
        "individual_ranks": dr.RANKS["individuals"],
        "ranks_map": {"officers": dr.RANKS["officers"],
                      "individuals": dr.RANKS["individuals"]},
        "sid": sid,
    })
    return variables
