# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تاب «الراغبين (يومي)» — علامة راغب/لا لكل عضو في اليوم المحدد.

كل علامة تُكتب في ragh_daily (نفس الداتا اللي هيكتبها زرار التأميدة في ج٤ —
source=manual/tamida) وتُحدّث ملف «يوم N/<الجهة>.xlsx» لحظيًا (بناء مستهدف).
المحاولات المحظورة تتحذر ولا تُكتب:
- تسجيل عضو معلّم «غير راغب» راغبًا (يُرجع للقوة من تاب الكوادر أولًا).
- عضو من جهة أخرى غير الجهة المحددة.
"""
from flask import request

from core import arabic_numbers as arnum
from core.auth_core import login_required
from data_access import db_raghibin as dr
from services.raghibin.files_daily import write_day_file

from . import raghibin_bp
from .context import _ctx, _entity_or_back, _rb, _selected_day


@raghibin_bp.route("/daily/toggle", methods=["POST"])
@login_required
def daily_toggle():
    year, month = _ctx()
    entity, back = _entity_or_back(year, month, "daily")
    if back:
        return back
    day = _selected_day(year, month)
    try:
        person_id = int(request.form.get("person_id") or 0)
    except ValueError:
        person_id = 0
    person = dr.get_person(year, month, person_id)
    if not person or person["entity_id"] != entity["id"]:
        return _rb("daily", e=entity["id"], d=day,
                   err="الاسم غير موجود في قوة الجهة المحددة")
    willing = request.form.get("willing") == "1"
    if willing and person["excluded"]:
        reason = person["exclude_note"] or "بدون سبب مسجل"
        return _rb("daily", e=entity["id"], d=day,
                   warn=f"{person['full_name']} معلّم «غير راغب» ({reason}) — "
                        f"أرجعه للقوة من تاب «الجهات والكوادر» أولًا")
    dr.set_daily(year, month, person_id, day, willing, source="manual")
    write_day_file(year, month, day, entity["id"], entity["name"])
    day_txt = arnum.to_arabic_indic(str(day))
    if willing:
        return _rb("daily", e=entity["id"], d=day,
                   ok=f"{person['full_name']} راغب بالوجبة يوم {day_txt} — "
                      f"الملف اتبنى لحظيًا")
    return _rb("daily", e=entity["id"], d=day,
               ok=f"تم تسجيل عدم رغبة {person['full_name']} يوم {day_txt}")
