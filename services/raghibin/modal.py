# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""متغيرات مودال «كشف وتسجيل أسماء ضابط/فرد الراغبين».

تُستخدم في: جزء /raghibin/panel (الجلب اللحظي) والعرض المدمج داخل صفحة
التأميدات نفسها (جذري ضد رسم صفحة الدخول داخل المودال: المحتوى موجود
في الصفحة من أول تحميل، والجلب مجرد تحديث اختياري فوقه).
"""
from core.config import MONTH_NAMES
from data_access import db_raghibin as dr
from data_access import db_tameedat as dt


def build(year, month, entity, day, cat, sid="", draft_totals=None):
    """متغيرات قالب raghibin/modal_body.html لجهة/يوم/فئة.
    draft_totals (١٤/١٠): عدّادات فورم التأميدة غير المحفوظ — المربعات
    بتتبعها لو مفيش تأميدة محفوظة لليوم."""
    state = dr.day_state(year, month, day, entity["id"]) if entity else {}
    # قائمة القوة في المودال = غير المستثنين فقط (إدارتهم من «الجهات والكوادر»)
    persons = dr.list_persons(year, month, entity_id=entity["id"], category=cat,
                              excluded=False) if entity else []
    for person in persons:
        person["willing_today"] = state.get(person["id"])
    from routes.raghibin.context import _slots_vars
    variables = _slots_vars(year, month, entity, day, draft_totals=draft_totals)
    variables.update({
        "fcat": cat, "entity": entity, "sel_day": day,
        "year": year, "month": month,
        "force_persons": persons,
        "entity_names": dt.entity_names(year, month),
        "categories": dr.CATEGORIES,
        "officer_ranks": dr.RANKS["officers"],
        "individual_ranks": dr.RANKS["individuals"],
        "ranks_map": {"officers": dr.RANKS["officers"],
                      "individuals": dr.RANKS["individuals"]},
        # ١٣/١٠: خريطة (الرتبة، الاسم) لكل فئة — عشان كتابة اسم معروف
        # تملأ مربع الرتبة التلقائي في صفه
        "person_rank_pairs": {cat: [[p.get("rank") or "", p["full_name"]]
                                    for p in dr.list_persons(
                                        year, month,
                                        entity_id=entity["id"],
                                        category=cat)]
                              if entity else []
                              for cat in ("officers", "individuals")},
        "sid": sid,
        "month_names": MONTH_NAMES,
    })
    return variables
