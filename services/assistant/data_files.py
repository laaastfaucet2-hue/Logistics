# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""إجابات ملفات المنظومة المحلية — ملف يوم محدد + حصر ما على القرص فعليًا.

مصدران رسميان فقط: `services.tameedat_fs` (مسار واسم ملف اليوم) و
`services.files_index` (قراءة القرص مباشرة: عدد الملفات والفولدرات والحجم).
لا تخمين ولا حساب موازٍ — والمساعد قراءة فقط ولا يكتب أي ملف.
"""
from core import egtime

from . import text as T
from .data_answers import (L_TAMEEDAT, _ar, _fmt_date, _month_title, bullets, kv,
                           note, p, result, table)

L_FILES_T = {"label": "حصر ملفات التاميدات", "target": "files.tameedat"}
L_FILES_R = {"label": "حصر ملفات الراغبين", "target": "files.raghibin"}
L_DOWNLOAD = {"label": "تنزيل ملف اليوم", "target": "day.download"}   # بارامتر day يُضاف في المسار


def _day_label(day):
    return _ar(day)


def topic_day_files(year, month, question):
    """«ملف تأميدات يوم ٧» / «فولدر يوم ٩» — ملف اليوم المفتوح وزرّيه يتبعان اليوم."""
    import services.tameedat_fs as tameedat_fs
    day = T.day_number(question)
    last = egtime.days_in_month(year, month)
    if day is None:
        return result("ملفات أي يوم — وكل يوم يتب بيومه", [
            p(f"في تبويب «تأميدات اليوم المحدد» زرّان يتبعان **اليوم المفتوح**: "
              f"«📂 فتح مجلد «تأميدات يوم N»» و«📗 فتح ملف «تاميدات اليوم N.xlsx»»."),
            bullets(["اكتب اليوم صراحةً وأنا اجيبلك ملفه: «ملف تأميدات يوم ٧».",
                     "ملف الشهر الكامل «إجمالي الشهر.xlsx» له زر مستقل بجوارهما.",
                     "كل ملف يوم يحمل الدباجة الرسمية واللوجو والتوقيعين."]),
            note("على نسخة سطح المكتب يفتح الملف مباشرة، وفي معاينة الويب يُنزَّل فورًا."),
        ], links=[L_TAMEEDAT], followups=["تأميدات يوم ٧", "ملف تأميدات يوم ١٥", "أرصدة المخازن"])
    if not 1 <= day <= last:
        return result(f"ملف يوم {_day_label(day)}", [
            note(f"الشهر النشط {_month_title(year, month)} فيه أيام من ١ إلى {_ar(last)} "
                 f"بس — مفيش يوم {_day_label(day)} فيه."),
        ], links=[L_TAMEEDAT], followups=["تأميدات يوم ١", "ملف تأميدات يوم ٧",
                                          "ملخص الشهر"])
    from data_access import db_tameedat as dt
    path = tameedat_fs.day_file(year, month, day)
    exists = path.is_file()
    records = dt.records_for_day(year, month, day)
    name = tameedat_fs.day_file_name(day)
    blocks = [p(f"ملف يوم {_day_label(day)} — {_fmt_date(year, month, day)}:"),
              kv([["اسم الملف", name],
                  ["مجلد اليوم", f"يوم {_day_label(day)}"],
                  ["الحالة", "مُنشأ وجاهز على جهازك" if exists else "لسه فاضي — يُبنى أول تأميدة"],
                  ["تأميدات اليوم", _ar(len(records))]])]
    if records:
        blocks.append(table(["الجهة", "ضابط", "فرد", "مجندين", "الإجمالي"],
                            [[rec["entity_name"], _ar(rec["officers"]),
                              _ar(rec["individuals"]), _ar(rec["recruits"]),
                              _ar(rec["grand_total"])] for rec in records[:6]]))
    links = [dict(L_DOWNLOAD, params={"day": day})] if exists else []
    links.append(L_TAMEEDAT)
    if not exists:
        blocks.append(note("يوم بلا تأميدات مسجلة لسه، فملفه لا يكون مُنشأً — سجّل أي تأميدة "
                           "فيه فيتبني تلقائيًا، أو افتح ملف الشهر كله من زر «إجمالي الشهر»."))
    return result(f"ملف تأميدات يوم {_day_label(day)}", blocks, links=links,
                  followups=[f"تأميدات يوم {_day_label(day)}", "ملخص الشهر", "الملفات المحلية",
                             "إزاي أفتح مجلد الملفات"])


def _section_of(question):
    if T.any_in(question, "راغبين", "الراغبين", "رغبه", "الرغبه", "الكوادر"):
        return "raghibin"
    return "tameedat"


def topic_local_files(year, month, question):
    """«الملفات المحلية / فين الملفات / كم ملف في القسم» — حصر حقيقي من القرص."""
    from services import files_index
    section = _section_of(question)
    try:
        tree = files_index.build_tree(section, year, month)
    except Exception:      # noqa: BLE001 — القرص لا يُسقط المساعد
        tree = None
    if not tree or not tree.get("children"):
        return result("الملفات المحلية على جهازك", [
            p("لسه مفيش ملفات محفوظة لهذا القسم في الشهر النشط — أول حفظ يبنيها تلقائيًا."),
            note("الملفات تُكتب داخل فولدر الشهر في `database/` على جهازك فقط، "
                 "ولا تُرفع لأي مكان."),
        ], links=[L_FILES_T, L_FILES_R], followups=["ملخص الشهر", "مساعدة"])
    rows = []
    for node in tree["children"][:8]:
        rows.append([node["name"] if node["type"] == "dir" else node["name"],
                     _ar(node.get("files", 0)) if node["type"] == "dir" else "—",
                     node.get("size_text") or "—",
                     "اتحدّث الآن" if node.get("fresh") else node.get("mtime_text") or "—"])
    blocks = [p(f"ملفات «{tree['title']}» على جهازك في {_month_title(year, month)}:"),
              kv([["عدد الملفات", _ar(tree["files"])],
                  ["عدد الفولدرات", _ar(tree["folders"])],
                  ["الحجم الكلي", files_index.size_text(tree["bytes"])],
                  ["آخر حصر", f"{tree['checked_at']} — من القرص مباشرة"]]),
              table(["العنصر", "ملفات", "الحجم", "آخر تحديث"], rows)]
    if tree["section"] == "tameedat":
        blocks.append(note("فولدرات الأيام باسم «يوم N» — ويبقى زر المجلد وزر الملف يتبعان "
                           "اليوم المفتوح في تبويب «تأميدات اليوم المحدد»."))
    return result("الملفات المحلية على جهازك", blocks,
                  links=[L_FILES_T, L_FILES_R], followups=["ملف تأميدات يوم ٧",
                                                           "إزاي أفتح مجلد الملفات",
                                                           "ملخص الشهر"])
