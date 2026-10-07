# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الملف المحلي لقسم التاميدات — فولدرات بأسماء التويبات داخل فولدر الشهر.

المكان المعتمد (يطلب المستخدم ربط كل شيء محليًا):
    database/<السنة>/<الشهر>/07-التاميدات/
        تأميدات اليوم المحدد/        ← لقطة JSON محدثة لكل سجلات الشهر
        الجهات المومدة بالشهر الحالي/ ← ملخص JSON لكل جهة مومدة
        قاموس ودليل الجهات/          ← لقطة JSON لقاموس الشهر
        طباعة التقرير الشامل/        ← ملفات التقرير (Excel بالدباجة واللوجو + Word)

قاعدة البيانات الحية تظل month.db (حماية WAL والنسخ الاحتياطي تشملها تلقائيًا)،
وهذه الملفات مرآة مقروءة تتحدث بعد كل حفظ/تعديل/حذف ناجح فقط.
"""
import json
import logging

from core import dates, egtime
from core import labels
from core import colors as palette


def entity_color(name):
    """لون الجهة الثابت (بلا #) — نفس لون شريطها في الشاشات."""
    return (palette.color_for("entity", name) or "").lstrip("#") or "132638"
from core.config import SECTIONS, MONTH_NAMES
from data_access import dataguard, storage
from data_access import db_tameedat as dt

TAB_FOLDERS = {
    "day": "تأميدات اليوم المحدد",
    "momoda": "الجهات المومدة بالشهر الحالي",
    "dict": "قاموس ودليل الجهات",
    "report": "طباعة التقرير الشامل",
}

# ملف كل تبويب (يظهر اسمه على زر «فتح ملف» — قاعدة أزرار الملفات الملزمة)
TAB_FILES = {
    "day": "سجلات التأميدات.json",
    "momoda": "ملخص الجهات المومدة.json",
    "dict": "قاموس الجهات.json",
}
# الملفات التي يفتحها المستخدم بزر «فتح الملف» — كلها Excel (توجيه المستخدم ٢٣/٠٩)
TAB_XLSX = {
    "day": "إجمالي الشهر.xlsx",
    "momoda": "ملخص الجهات المومدة.xlsx",
    "dict": "قاموس الجهات.xlsx",
}

# الأزرق الفاتح المعتمد لكل تصميمات Excel — بدل البرتقالي (توجيه ٢٨/٠٩)
XLSX_BLUE = "BDD7EE"
HEAD_ROW = 6          # صف العناوين بعد الدباجة (٥ صفوف) — قاعدة موحّدة مع كل الكشوف


def signatures_rows(ws, row, year, month, ncols):
    """التوقيعان الرسميان أسفل أي ورقة — نفس دالة الراغبين (مصدر واحد)."""
    from services.raghibin import signatures_rows as _sr
    _sr(ws, row, year, month, ncols)
    return row

HEADER_1 = "منطقة وسط وجنوب للأمن المركزي"
HEADER_2 = "قطاع وسط سيناء - قسم التميينات"


def _section_index():
    for index, section in enumerate(SECTIONS, start=1):
        if section["key"] == "tameedat":
            return index
    raise KeyError("tameedat")


def base_dir(year, month):
    """فولدر قسم التاميدات داخل الشهر: database/<سنة>/<شهر>/07-التاميدات"""
    path = storage.section_files_path(year, month, _section_index())
    path.mkdir(parents=True, exist_ok=True)
    return path


def tab_dir(year, month, tab):
    """فولدر تبويب واحد داخل التاميدات — يُنشأ إن لم يوجد."""
    path = base_dir(year, month) / TAB_FOLDERS[tab]
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_folders(year, month):
    """ينشئ الفولدرات الأربعة بأسماء التويبات (تُستدعى عند فتح القسم وكل حفظ)."""
    for key in TAB_FOLDERS:
        tab_dir(year, month, key)
    return base_dir(year, month)


def report_dir(year, month):
    return tab_dir(year, month, "report")


def _meta(year, month):
    return {
        "الجهة": HEADER_1,
        "القسم": HEADER_2,
        "الشهر": MONTH_NAMES[month - 1],
        "السنة": year,
        "آخر تحديث": egtime.now().isoformat(timespec="seconds"),
    }


def _save_json(path, payload):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    data = text.encode("utf-8")
    dataguard.atomic_save(
        lambda tmp: __import__("pathlib").Path(tmp).write_bytes(data),
        path, zip_check=False)


def _record_json(rec):
    return {
        "رقم": rec["id"],
        "اليوم": rec["day"],
        "إلى يوم": rec["day_to"],
        "عدد أيام المدة": rec["range_days"],
        "الجهة": rec["entity_name"],
        "نوع الجهة": rec["entity_type"],
        "ض": rec["officers"],
        "أ": rec["individuals"],
        "م": rec["recruits"],
        "مفتاح الحروف": labels.LEGEND,
        "الإجمالي": rec["total"],
        "ملحقة": [{"الاسم": a["name"], "النوع": a["entity_type"],
                   "ض": a["officers"], "أ": a["individuals"],
                   "م": a["recruits"]} for a in rec["attachments"]],
        "إجمالي التأميدة مع الملحقات": rec["grand_total"],
        "ملاحظات": rec["notes"],
        "آخر تعديل": rec["updated_at"],
    }


def snapshot_all(year, month):
    """يعيد كتابة اللقطات الثلاث بعد أي حفظ/تعديل/حذف ناجح — محليًا وذرّيًا."""
    ensure_folders(year, month)

    records = dt.month_records(year, month)
    _save_json(tab_dir(year, month, "day") / "سجلات التأميدات.json", {
        **_meta(year, month),
        "عدد السجلات": len(records),
        "السجلات": [_record_json(r) for r in records],
    })

    entities = dt.list_entities(year, month)
    _save_json(tab_dir(year, month, "dict") / "قاموس الجهات.json", {
        **_meta(year, month),
        "عدد الجهات": len(entities),
        "الجهات": [{
            "مسلسل": e["serial"], "الاسم": e["name"], "النوع": e["entity_type"],
            "راغبين ض": e["rag_officers"], "راغبين أ": e["rag_individuals"],
            "ملاحظات": e["notes"],
        } for e in entities],
    })

    summary, totals = dt.month_summary(year, month)
    _save_json(tab_dir(year, month, "momoda") / "ملخص الجهات المومدة.json", {
        **_meta(year, month),
        "الجهات": [{
            "الجهة": r["name"], "النوع": r["entity_type"],
            "ملحقة": r["kind"] == "attachment",
            "أيام التميد": r["active_days"], "عدد التأميدات": r["records"],
            "ض": r["total_officers"], "أ": r["total_individuals"],
            "م": r["total_recruits"], "الإجمالي": r["grand_total"],
            "أيام التميد بالتواريخ": [{
                "التأميدة رقم": part["record_id"],
                "من": dates.format_date(f"{year:04d}-{month:02d}-{part['day']:02d}"),
                "إلى": dates.format_date(f"{year:04d}-{month:02d}-{part['day_to']:02d}"),
                "عدد الأيام": part["range_days"],
                "تابعة لتأميدة": (part.get("attachment") and part["parent_name"]) or "",
            } for part in r["participations"]],
            "متوسط يومي": round(r["grand_total"] and
                (r["total_officers"] + r["total_individuals"] + r["total_recruits"])
                / r["active_days"], 1) if r["active_days"] else 0,
        } for r in summary],
        "إجمالي القوة": totals["grand"],
        "الجهات المومدة": totals["entities"],
        "أيام التميد الفعلية": totals["active_days"],
    })
    _snapshot_xlsx(year, month, records, entities, summary)   # مرآة Excel التي يفتحها المستخدم (قاعدة)
    try:   # فولدرات الأيام: كل يوم ملف بتأميداته (توجيه ٢٨/٠٩ ليلًا)
        _snapshot_day_folders(year, month, records)
    except Exception:
        logging.exception("tameedat day folders failed")
    dataguard.auto_backup("write", min_minutes=20)
    return True


def _snapshot_day_folders(year, month, records):
    """سجلات التأميدات: فولدر «يوم N» من ١ لآخر الشهر، كل يوم ملف بتأميداته
    بنفس البطاقات الرأسية — والأيام بلا سجلات تظل فولدرات فاضية."""
    import shutil
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from core import arabic_numbers as arnum
    root = tab_dir(year, month, "day")
    old = root / "سجلات التأميدات.xlsx"
    if old.exists():
        old.unlink()
    for sub in tuple(root.glob("يوم *")):
        shutil.rmtree(sub, ignore_errors=True) if sub.is_dir() else sub.unlink()
    by_day = {}
    for rec in records:
        by_day.setdefault(rec["day"], []).append(rec)
    for day in range(1, egtime.days_in_month(year, month) + 1):
        folder = root / "يوم {}".format(arnum.to_arabic_indic(str(day)))
        folder.mkdir(exist_ok=True)
        if not by_day.get(day):
            continue
        book = Workbook()
        sheet = book.active
        sheet.title = "تأميدات يوم {}".format(arnum.to_arabic_indic(str(day)))
        from documents.official_xlsx import add_letterhead
        add_letterhead(sheet, year, month, 2)      # دباجة + لوجو على كل ملف محلي
        sheet.sheet_view.rightToLeft = True
        head = Font(bold=True, size=12)
        label = Font(bold=True, size=11)
        blue = PatternFill("solid", fgColor=XLSX_BLUE)
        right = Alignment(horizontal="right", vertical="center", readingOrder=2)
        banner = sheet.cell(HEAD_ROW, 1, "تأميدات يوم {} {} {}".format(
            arnum.to_arabic_indic(str(day)), MONTH_NAMES[month - 1], year))
        banner.font = head
        banner.fill = blue
        banner.alignment = right
        sheet.merge_cells(start_row=HEAD_ROW, start_column=1, end_row=HEAD_ROW, end_column=2)
        sheet.append([None, None])
        for rec in by_day[day]:
            sheet.append([None, None])
            sheet.append(["تأميدة رقم {} — {}".format(rec["id"], rec["entity_name"]), None])
            sheet.cell(sheet.max_row, 1).font = head
            sheet.cell(sheet.max_row, 1).fill = blue
            sheet.merge_cells(start_row=sheet.max_row, start_column=1,
                              end_row=sheet.max_row, end_column=2)
            pairs = [
                ("مفتاح الحروف", labels.LEGEND),
                ("النوع", rec["entity_type"] or "—"),
                ("من يوم", dates.format_date(f"{year:04d}-{month:02d}-{rec['day']:02d}")),
                ("إلى يوم", dates.format_date(f"{year:04d}-{month:02d}-{rec['day_to']:02d}")),
                ("عدد أيام المدة", rec["range_days"]),
                ("ض", rec["officers"]), ("أ", rec["individuals"]),
                ("م", rec["recruits"]), ("إجمالي التأميدة", rec["total"]),
                ("إجمالي التأميدة مع الملحقات", rec["grand_total"]),
            ]
            for a in rec.get("attachments", []):
                pairs.append(("ملحقة: {} ({})".format(a["name"], a["entity_type"] or "—"),
                              labels.pair3(a["officers"], a["individuals"], a["recruits"])))
            pairs.append(("ملاحظات", rec.get("notes") or "—"))
            for k, v in pairs:
                sheet.append([k, v])
                sheet.cell(sheet.max_row, 1).font = label
        sheet.column_dimensions["A"].width = 34
        sheet.column_dimensions["B"].width = 46
        signatures_rows(sheet, sheet.max_row + 2, year, month, 2)
        dataguard.atomic_save(book.save,
                              folder / "تاميدات اليوم {}.xlsx".format(
                                  arnum.to_arabic_indic(str(day))), zip_check=False)


def _save_xlsx(path, sheets, year=None, month=None):
    """يكتب ملف Excel عربي RTL — **بدباجة + لوجو + توقيعين** على كل ورقة.

    القاعدة الذهبية (توجيه ٠٦/١٠/٢٠٢٦): كل ملف محلي يحمل الدباجة الرسمية واللوجو
    والتوقيعين، ويرفضه الفحص الذكي (services/local_audit) إن نَقص أحدها.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from documents.official_xlsx import add_letterhead
    book = Workbook()
    first = True
    for title, headers, rows in sheets:
        sheet = book.active if first else book.create_sheet()
        sheet.title = title
        first = False
        ncols = max(len(headers), 3)
        if year and month:
            add_letterhead(sheet, year, month, ncols)      # صفوف ١–٤ (لوجو + وزارة)
            head_row = HEAD_ROW
            # صف ٥: عنوان الورقة + الشهر والسنة (القاعدة الذهبية: اسم الشهر في كل ملف)
            sheet.merge_cells(start_row=5, start_column=1, end_row=5, end_column=ncols)
            from core import arabic_numbers as arnum
            stamp = sheet.cell(5, 1, f"{title} — {MONTH_NAMES[int(month) - 1]} "
                                     f"{arnum.to_arabic_indic(year)}")
            stamp.font = Font(name="Cairo", size=11, bold=True, color="132638")
            stamp.alignment = Alignment(horizontal="center", vertical="center",
                                        readingOrder=2)
        else:                                              # بلا سياق شهر: تبقى المرآة مقروءة
            head_row = 1
        for col, name in enumerate(headers, start=1):
            cell = sheet.cell(head_row, col, name)
            cell.fill = PatternFill("solid", fgColor=XLSX_BLUE)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        for row in rows:
            sheet.append(list(row))
        # لون الجهة الثابت على خلية اسمها (نفس لون شريط الجهة في الشاشات — توجيه ٠٦/١٠)
        entity_col = next((i for i, name in enumerate(headers, start=1) if name == "الجهة"), None)
        if entity_col:
            for r in range(head_row + 1, sheet.max_row + 1):
                value = sheet.cell(r, entity_col).value
                if value:
                    sheet.cell(r, entity_col).font = Font(
                        name="Cairo", size=11, bold=True, color=entity_color(value))
        for idx, name in enumerate(headers, start=1):        # العرض من البيانات (الدباجة مدمجة)
            column = [str(row[idx - 1]) for row in rows if len(row) >= idx and row[idx - 1] is not None]
            width = max([len(str(name))] + [len(v) for v in column] or [10])
            from openpyxl.utils import get_column_letter
            sheet.column_dimensions[get_column_letter(idx)].width = min(max(width + 4, 12), 46)
        if year and month:
            signatures_rows(sheet, sheet.max_row + 2, year, month, ncols)
    dataguard.atomic_save(book.save, path)   # ذرّي + لحظي لو الملف مفتوح عند المستخدم


def _save_day_xlsx(path, year, month, records):
    """«تأميدات اليوم المحدد» — ورقة رأسية عمودية (توجيه ٢٨/٠٩): كل تأميدة بلوك
    صفوف «البيان | القيمة» بدل الجدول العرضي، وأعلى الورقة إجمالي كل التأميدات
    في الشهر (ض/أ/م بملحقاتها) — يتجدد تلقائيًا مع كل حفظ."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    book = Workbook()
    sheet = book.active
    sheet.title = "تأميدات الشهر"
    from documents.official_xlsx import add_letterhead
    add_letterhead(sheet, year, month, 2)      # دباجة + لوجو على كل ملف محلي
    sheet.sheet_view.rightToLeft = True
    head = Font(bold=True, size=12)
    label = Font(bold=True, size=11)
    blue = PatternFill("solid", fgColor=XLSX_BLUE)
    center = Alignment(horizontal="center", vertical="center")
    right = Alignment(horizontal="right", vertical="center", readingOrder=2)

    def banner(row, text):
        cell = sheet.cell(row, 1, text)
        cell.font = head
        cell.fill = blue
        cell.alignment = right
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)

    def block(title, pairs):
        banner(sheet.max_row + 1, title)
        for k, v in pairs:
            sheet.append([k, v])
            sheet.cell(sheet.max_row, 1).font = label
        sheet.append([None, None])

    for col, name in enumerate(("البيان", "القيمة"), start=1):
        cell = sheet.cell(HEAD_ROW, col, name)
        cell.font = head
        cell.fill = blue
        cell.alignment = center

    def _sum(field):
        return (sum(r[field] for r in records)
                + sum(a[field] for r in records for a in r.get("attachments", [])))

    block("إجمالي التأميدات في الشهر — {} {}".format(MONTH_NAMES[month - 1], year), [
        ("عدد التأميدات", len(records)),
        ("مفتاح الحروف", labels.LEGEND),
        ("إجمالي ض", _sum("officers")),
        ("إجمالي أ", _sum("individuals")),
        ("إجمالي م", _sum("recruits")),
        ("الإجمالي العام", sum(r["grand_total"] for r in records)),
    ])
    for rec in records:
        pairs = [
            ("الجهة", rec["entity_name"]),
            ("النوع", rec["entity_type"] or "—"),
            ("من يوم", dates.format_date(f"{year:04d}-{month:02d}-{rec['day']:02d}")),
            ("إلى يوم", dates.format_date(f"{year:04d}-{month:02d}-{rec['day_to']:02d}")),
            ("عدد أيام المدة", rec["range_days"]),
            ("ض", rec["officers"]),
            ("أ", rec["individuals"]),
            ("م", rec["recruits"]),
            ("إجمالي التأميدة", rec["total"]),
            ("إجمالي التأميدة مع الملحقات", rec["grand_total"]),
        ]
        for a in rec.get("attachments", []):
            pairs.append(("ملحقة: {} ({})".format(a["name"], a["entity_type"] or "—"),
                          labels.pair3(a["officers"], a["individuals"], a["recruits"])))
        pairs.append(("ملاحظات", rec.get("notes") or "—"))
        block("تأميدة رقم {} — {}".format(rec["id"], rec["entity_name"]), pairs)
    sheet.column_dimensions["A"].width = 34
    sheet.column_dimensions["B"].width = 46
    signatures_rows(sheet, sheet.max_row + 2, year, month, 2)
    from data_access import dataguard
    dataguard.atomic_save(book.save, path)   # لحظي (توجيه ٢٨/٠٩ ليلًا)


def _snapshot_xlsx(year, month, records, entities, summary):
    """نسخ Excel من جداول التويبات الثلاثة — توجيه المستخدم (٢٣/٠٩): الملفات كلها Excel.
    أي عطل هنا لا يوقف الحفظ: مرآة JSON تظل سليمة ويُسجَّل التحذير."""
    try:
        _save_day_xlsx(tab_dir(year, month, "day") / TAB_XLSX["day"],
                       year, month, records)

        stats = dt.dict_month_stats(year, month)   # المصدر الموحد — لا منطق متوازٍ هنا
        dict_rows = []
        for e in entities:
            st = stats.get(e["id"], {})
            own, att = st.get("own"), st.get("att")
            tot_officers = ((own["total_officers"] if own else 0)
                            + (att["total_officers"] if att else 0))
            tot_individuals = ((own["total_individuals"] if own else 0)
                               + (att["total_individuals"] if att else 0))
            has = bool(st.get("records_total"))
            dict_rows.append((e["serial"], e["name"], e["entity_type"],
                              tot_officers if has else "—",
                              tot_individuals if has else "—",
                              round(own["avg_officers"], 3) if own else "—",
                              round(own["avg_individuals"], 3) if own else "—",
                              round(own["avg_recruits"], 3) if own else "—",
                              st.get("records_total", 0),
                              (f"×{st['att_count']} — {'، '.join(st['att_parents'])}"
                               if st.get("att_count") else "—"),
                              e.get("notes") or "—"))
        _save_xlsx(tab_dir(year, month, "dict") / TAB_XLSX["dict"], [(
            "قاموس الجهات",
            ["م", "الجهة", "النوع", "إجمالي ض", "إجمالي أ",
             "متوسط ض", "متوسط أ", "متوسط م", "عدد التأميدات", "ملحقة على", "ملاحظات"],
            dict_rows)], year=year, month=month)

        momoda_rows = [(idx, r["name"], "ملحقة" if r["kind"] == "attachment" else "رئيسية",
                        r["entity_type"], r["active_days"], r["records"], r["total_officers"],
                        r["total_individuals"], r["total_recruits"], r["grand_total"])
                       for idx, r in enumerate(summary, 1)]
        date_rows = []
        for r in summary:
            for part in r["participations"]:
                date_rows.append((r["name"], part["record_id"],
                                  dates.format_date(f"{year:04d}-{month:02d}-{part['day']:02d}"),
                                  dates.format_date(f"{year:04d}-{month:02d}-{part['day_to']:02d}"),
                                  part["range_days"],
                                  part["parent_name"] if part.get("attachment") else "—"))
        _save_xlsx(tab_dir(year, month, "momoda") / TAB_XLSX["momoda"], [(
            "مفتاح الحروف", ["الشرح"], [[labels.LEGEND]]),
            ("ملخص الجهات المومدة",
             ["م", "الجهة", "الحالة", "النوع", "أيام التميد", "عدد التأميدات",
              "ض", "أ", "م", "الإجمالي"], momoda_rows),
            ("التواريخ من - إلى",
             ["الجهة", "تأميدة رقم", "من", "إلى", "عدد الأيام", "ملحقة على"], date_rows)],
            year=year, month=month)
    except Exception:
        logging.exception("tameedat xlsx mirror failed — JSON snapshots are intact")
