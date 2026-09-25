# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الأدوات المشتركة ونموذج عرض قسم التاميدات.

سياق السنة/الشهر، جديل الرجوع _rb، التقويم العربي، محللات النماذج
(التواريخ/الأعداد/الملحقات/النوع/الراغبين)، تنبيه الراغبين، مرايا الحفظ،
ونموذج العرض _page_vars للتويبات الأربعة.
"""

import os
import secrets
from datetime import date
from urllib.parse import quote
from flask import g, redirect, request, url_for
from core.auth_core import current_context, current_session
from core.config import DAYS, MONTH_NAMES, month_folder
from core import arabic_numbers as arnum
from core import dates
from core import egtime
from data_access import db_letterhead as lhdb
import json
from data_access import db_tameedat as dt
from data_access import db_tameed_rations as snap
from data_access import db_permits as dp
from services import tameedat_fs

from . import TABS, TYPE_FILTERS


# ======================================================================
# أدوات مشتركة
# ======================================================================
def _ctx():
    return current_context(g.user["id"])


def _rb(tab="day", day=None, filter_key=None, query=None, ok=None, err=None,
        warn=None, **extra):
    """يرجع لصفحة التاميدات مع الحفاظ على التوكن والتبويب واليوم والفلاتر."""
    _, token = current_session()
    params = {"tab": tab}
    if day:
        params["day"] = day
    if filter_key and filter_key != "all":
        params["f"] = filter_key
    if query:
        params["q"] = query
    if token:
        params["sid"] = token
    if ok:
        params["ok"] = ok
    if err:
        params["err"] = err
    if warn:
        params["warn"] = warn
    params.update({k: v for k, v in extra.items() if v})
    base = url_for("tameedat.page")      # يحمل year/month/sid تلقائيًا عبر url_defaults
    separator = "&" if "?" in base else "?"
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return redirect(base + (separator + query if query else ""))


def _selected_day(year, month):
    """اليوم المحدد: أي يوم صحيح داخل الشهر النشط؛ الافتراضي تاريخ اليوم."""
    raw = request.args.get("day")
    if raw:
        try:
            parsed = dates.parse_date(raw)
        except ValueError:
            parsed = None
        if parsed and parsed.year == year and parsed.month == month:
            return parsed.day
    today = egtime.today()
    if today.year == year and today.month == month:
        return today.day
    return 1


def _calendar(year, month, selected):
    """شبكة أيام الشهر النشط للتقويم (أسبوع يبدأ السبت) + علامات الأيام المسجلة."""
    counts = dt.day_counts(year, month)
    issued = dp.issued_days(year, month)
    first = date(year, month, 1)
    offset = (first.weekday() + 2) % 7          # السبت أول الأعمدة
    total_days = egtime.days_in_month(year, month)
    today = egtime.today()
    cells = [{"empty": True}] * offset
    for day in range(1, total_days + 1):
        cells.append({
            "empty": False, "day": day,
            "count": counts.get(day, 0),
            "selected": day == selected,
            "issued": day in issued,
            "is_today": today.year == year and today.month == month and today.day == day,
        })
    while len(cells) % 7:
        cells.append({"empty": True})
    return [cells[i:i + 7] for i in range(0, len(cells), 7)]


def _parse_day_form(year, month):
    """يقرأ تاريخ النموذج dd/mm/yyyy ويفرض أنه داخل الشهر النشط. يرجع اليوم أو يرمي."""
    raw = request.form.get("day", "")
    try:
        parsed = dates.parse_date(raw)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if parsed is None:
        raise ValueError("اكتب تاريخ التأميدة أولًا")
    if parsed.year != year or parsed.month != month:
        raise ValueError(f"التاريخ خارج الشهر النشط — التأميدات تُسجَّل داخل "
                         f"{MONTH_NAMES[month - 1]} {arnum.to_arabic_indic(year)} فقط")
    return parsed.day


def _parse_from_to(year, month):
    """«من يوم / إلى يوم» (واجهة التسجيل الحالية): رقما يوم داخل الشهر النشط.

    يرجع (day, day_to, range_days) — day_to=None حين يتساوى اليومان
    (من ١ إلى ١ = يوم واحد فقط، حسب طلب المستخدم).
    """
    days_in_month = egtime.days_in_month(year, month)
    from_day = arnum.parse_int(request.form.get("day_from"))
    if from_day is None or not 1 <= from_day <= days_in_month:
        raise ValueError(f"«من يوم» يجب أن يكون رقم يوم داخل {MONTH_NAMES[month - 1]} "
                         f"(من ١ إلى {arnum.to_arabic_indic(days_in_month)})")
    to_day = arnum.parse_int(request.form.get("day_to"))
    if to_day is None or not 1 <= to_day <= days_in_month:
        raise ValueError(f"«إلى يوم» يجب أن يكون رقم يوم داخل {MONTH_NAMES[month - 1]} "
                         f"(من ١ إلى {arnum.to_arabic_indic(days_in_month)}) — والمدة لا تعبر شهرًا آخر")
    if to_day < from_day:
        raise ValueError("«إلى يوم» لا يسبق «من يوم» — النهاية قبل البداية")
    return from_day, (to_day if to_day > from_day else None), to_day - from_day + 1


def _parse_range(year, month, start_day):
    """«تفعيل مدة زمنية للتأميدة»: يقرأ نهاية المدة ويتحقق أنها داخل الشهر.

    يرجع (day_to, range_days) — day_to = None حين لا تكون المدة مفعّلة.
    البداية هي تاريخ التأميدة نفسه؛ النهاية من يوم «إلى يوم» المرسل.
    """
    if not request.form.get("range_enabled"):
        return None, 1
    days_in_month = egtime.days_in_month(year, month)
    to_day = arnum.parse_int(request.form.get("day_to"))
    if to_day is None or not 1 <= to_day <= days_in_month:
        raise ValueError(f"«إلى يوم» يجب أن يكون رقم يوم داخل {MONTH_NAMES[month - 1]} "
                         f"(من ١ إلى {arnum.to_arabic_indic(days_in_month)}) — والمدة لا تعبر شهرًا آخر")
    if to_day < start_day:
        raise ValueError("نهاية المدة قبل بدايتها — «إلى يوم» لا يسبق يوم التأميدة")
    return (to_day if to_day > start_day else None), to_day - start_day + 1


def _parse_counts():
    """ضباط/أفراد/مجندين كأعداد صحيحة غير سالبة، والإجمالي مطلوب > ٠."""
    fields = {}
    for key, label in (("officers", "الضباط"), ("individuals", "الأفراد"),
                       ("recruits", "المجندين")):
        value = arnum.parse_int(request.form.get(key))
        if value is None and (request.form.get(key) or "").strip():
            raise ValueError(f"عدد {label} غير صالح — اكتب رقمًا صحيحًا")
        fields[key] = max(0, value or 0)
    if fields["officers"] + fields["individuals"] + fields["recruits"] < 1:
        raise ValueError("سجّل عددًا واحدًا على الأقل (ضباط/أفراد/مجندين)")
    return fields


def _parse_attachments():
    """صفوف الملحقات المرسلة مع النموذج (قوائم متوازية)."""
    names = request.form.getlist("att_name")
    types = request.form.getlist("att_type")
    out = []
    for index, name in enumerate(names):
        if not " ".join((name or "").split()):
            continue
        def _count(field):
            values = request.form.getlist(field)
            return arnum.parse_int(values[index]) if index < len(values) else None
        out.append({
            "name": name,
            "entity_type": types[index] if index < len(types) else "",
            "officers": _count("att_officers") or 0,
            "individuals": _count("att_individuals") or 0,
            "recruits": _count("att_recruits") or 0,
        })
    return out[:20]


def _posted_type():
    """نوع الجهة من النموذج: شرطية/حربية أو نص حر عند «أخرى»."""
    choice = request.form.get("type_choice", "شرطية")
    if choice == "أخرى":
        custom = " ".join((request.form.get("type_other") or "").split())
        if not custom:
            raise ValueError("اكتب نوع الجهة الحر عند اختيار «أخرى»")
        return custom[:60]
    return choice if choice in dt.BASE_TYPES else "شرطية"


def _parse_optional_rag():
    """أعداد الراغبين اختيارية: فارغ = غير مسجلة، وإلا عدد صحيح ≥ ٠."""
    out = {}
    for key, label in (("rag_officers", "راغبين الضباط"),
                       ("rag_individuals", "راغبين الأفراد")):
        raw = (request.form.get(key) or "").strip()
        if not raw:
            out[key] = None
            continue
        value = arnum.parse_int(raw)
        if value is None or value < 0:
            raise ValueError(f"عدد {label} غير صالح — اكتب رقمًا صحيحًا أو اتركه فارغًا")
        out[key] = value
    return out


def _rag_warning(entity, counts):
    """تنبيه راغبين لا يمنع الحفظ: يقارن ضباط/أفراد فقط، والمجندون خارج المقارنة."""
    problems = []
    if entity.get("rag_officers") is not None and counts["officers"] > entity["rag_officers"]:
        problems.append(
            f"الضباط ({arnum.to_arabic_indic(counts['officers'])}) أكثر من راغبين "
            f"الضباط المسجلين ({arnum.to_arabic_indic(entity['rag_officers'])})")
    if (entity.get("rag_individuals") is not None
            and counts["individuals"] > entity["rag_individuals"]):
        problems.append(
            f"الأفراد ({arnum.to_arabic_indic(counts['individuals'])}) أكثر من راغبين "
            f"الأفراد المسجلين ({arnum.to_arabic_indic(entity['rag_individuals'])})")
    if problems:
        return "تنبيه: " + "، ".join(problems) + " — تم الحفظ رغم ذلك حسب رغبتك"
    return None


def _after_write(year, month):
    """مرآة الملفات المحلية بعد أي كتابة ناجحة — التأكيد لا يسبقها."""
    tameedat_fs.snapshot_all(year, month)


def _page_vars(tab):
    year, month = _ctx()
    tameedat_fs.ensure_folders(year, month)
    filter_key = request.args.get("f", "all")
    if filter_key not in {k for k, _ in TYPE_FILTERS}:
        filter_key = "all"
    query = (request.args.get("q") or "").strip()
    selected = _selected_day(year, month)
    day_records = dt.records_for_day(year, month, selected, filter_key, query)
    by_permit = dp.permits_by_record(year, month)
    for rec in day_records:
        rec["permits"] = by_permit.get(rec["id"], [])
    copy_id = arnum.parse_int(request.args.get("copy"))
    edit_id = arnum.parse_int(request.args.get("edit"))
    dedit_id = arnum.parse_int(request.args.get("dedit"))
    copies = dt.get_record(year, month, copy_id) if copy_id else None
    edits = dt.get_record(year, month, edit_id) if edit_id else None
    summary, totals = dt.month_summary(year, month, filter_key)
    entities_list = dt.list_entities(year, month)
    variables = {
        "tabs": TABS, "tab": tab,
        "type_filters": TYPE_FILTERS, "f": filter_key, "q": query,
        "year": year, "month": month, "month_name": MONTH_NAMES[month - 1],
        "sel_day": selected,
        "sel_date_iso": f"{year:04d}-{month:02d}-{selected:02d}",
        "weeks": _calendar(year, month, selected),
        "weekdays": DAYS,
        "day_records": day_records,
        "day_count": len(day_records),
        "day_totals": {
            "officers": sum(r["officers"] for r in day_records),
            "individuals": sum(r["individuals"] for r in day_records),
            "recruits": sum(r["recruits"] for r in day_records),
            "grand": sum(r["grand_total"] for r in day_records),
        },
        "edit_record": edits,
        "custom_rations_json": json.dumps(
            snap.get_payload(year, month, edits["id"]) if edits else {},
            ensure_ascii=False),
        "copy_record_obj": copies,
        "entities": dt.list_entities(year, month),
        "entity_names": dt.entity_names(year, month),
        "dict_edit": dt.get_entity(year, month, dedit_id) if dedit_id else None,
        "dict_counts": {e["id"]: dt.entity_record_count(year, month, e["id"])
                        for e in entities_list},
        "dict_stats": dt.dict_month_stats(year, month),  # المصدر الموحد (مرحلة الإحصاء الواحد)
        "summary": summary, "summary_totals": totals,
        "report_files": _report_files(year, month),
        "can_open": os.name == "nt",
        "lh": [lhdb.get_setting(year, month, f"lh_{i}") for i in range(1, 5)],
        "has_logo": bool(lhdb.get_setting(year, month, "logo_file")),
        "section_folder": "07-التاميدات",
        "tab_folders": tameedat_fs.TAB_FOLDERS,
        "month_folder": month_folder(month),
        "save_token": secrets.token_urlsafe(16),
        "days_in_month": egtime.days_in_month(year, month),
    }
    return variables


def _report_files(year, month):
    folder = tameedat_fs.report_dir(year, month)
    files = []
    for path in sorted(folder.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.suffix.lower() not in (".xlsx", ".docx"):
            continue
        stamp = egtime.from_timestamp(path.stat().st_mtime)
        files.append({"name": path.name, "size": path.stat().st_size,
                      "kind": "Excel" if path.suffix == ".xlsx" else "Word",
                      "mtime": stamps_text(stamp)})
    return files


def stamps_text(stamp):
    return dates.format_datetime(stamp)


