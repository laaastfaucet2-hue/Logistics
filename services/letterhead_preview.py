# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""توليد المعاينة الحية لصفحة الدباجة (١٠/١٠):

المستخدم طلب «الشكل اللي بيتولد فعلا» — فبدل شكل عام واحد لكل الملفات،
بنعيد تشغيل المولّدات الحقيقية نفسها على شهر تجريبي خفي (سنة ٠/شهر ١ —
مجلد «database/0» لا يطابق YEAR_RE فلا يظهر في أي قائمة سنوات) ببيانات
نموذجية ثابتة. المعاينة تعرض ناتج التوليد الحقيقي (هيدر/عمود/ترتيب حقيقي)
ببيانات نموذجية — ولا يُقرأ أي ملف من ملفات المستخدم على القرص.

الدباجة واللوجو والتوقيعان في المعاينة = قيم الشهر الحالي الحية (تُبدَّل
في خلايا الناتج التجريبي قبل العرض).
"""
import logging
import re
import threading
from pathlib import Path

from core import arabic_numbers as arnum

# شهر تجريبي خفي: سنة ١ (3 أرقام) لا تظهر في storage.list_years (YEAR_RE = \d{4})
# وسنة ١ صالحة لحسابات datetime.date (سنة ٠ مرفوضة في date())
SY, SM = 1, 1
MARKER = ".preview_generated"
MONTH_NAME = "يناير"
SEED_INV6_DAY = 2   # يوم الجرد التجريبي في توليد 6 مخازن

_lock = threading.Lock()
_seeded = False


def _root(y=None, m=None):
    from data_access import months
    return months.month_db_path(SY if y is None else y, SM if m is None else m).parent


# ======================================================================
# التوليد التجريبي (مرة واحدة لكل عملية سيرفر)
# ======================================================================
def _seed_once():
    global _seeded
    with _lock:
        if _seeded:
            return
        try:
            marker = _root() / MARKER
            if not marker.exists():
                _generate_all()
                marker.write_text("ok", encoding="utf-8")
            _seeded = True
        except Exception:
            logging.exception("letterhead preview: scratch generation failed")


def _generate_all():
    import shutil
    y, m = SY, SM
    from data_access import months
    root = _root()
    if root.exists():          # إعادة توليد نظيفة دائمًا (حراسة ضد التكرار)
        shutil.rmtree(root)
    months.init_month(y, m)
    # 1) المقررات (04/05): أصناف + جهات
    from data_access import db_entities as de
    from data_access import db_rations as drat
    sample_items = {
        "tamween": [("أرز بلدي", "كجم", 0, 0.75, 0), ("سكر", "كجم", 0.12, 0, 0),
                    ("شاي", "جم", 2, 0, 0), ("زيت طعام", "لتر", 0, 0.05, 0)],
        "contractor": [("أسمنت", "كجم", 0, 0, 1.5), ("رمل", "م3", 0, 0.2, 0)],
    }
    for sec, items in sample_items.items():
        for name, unit, b, l, d in items:
            if not drat.item_exists(y, m, sec, "summer", name):
                drat.add_item(y, m, sec, "summer", name, unit, b, l, d)
        if not de.list_entities(y, m, sec):
            de.add_entity(y, m, sec, "قطاع شمال سيناء (نموذج)")
    from documents import xlsx_rations
    for sec in ("tamween", "contractor"):
        xlsx_rations.rebuild(y, m, sec)
        xlsx_rations.rebuild_distribution(y, m, sec)

    # 2) مستودعات وسجلات (06): أصناف + واردات + إذن صرف
    from data_access import db_permits as dperm
    from data_access import db_warehouses as dw
    from core import egtime
    for day, name, qty, unit in ((1, "أرز بلدي", 500, "كجم"),
                                 (1, "سكر", 300, "كجم"),
                                 (1, "زيت طعام", 120, "لتر"),
                                 (2, "أرز بلدي", 200, "كجم")):
        dw.add_receipt(y, m, "supply", day, name, qty, unit)
    dw.add_receipt(y, m, "contractor", 1, "أسمنت", 300, "كجم")
    dperm.save_permit(y, m, {
        "number": 1001, "fiscal_year": egtime.permit_fiscal_year(),
        "date_from": 2, "date_to": 3, "issue_days": 2, "mode": "day",
        "entity_label": "قطاع شمال سيناء (نموذج)", "officers": "",
        "individuals": "", "recruits": "", "meals": ["breakfast", "lunch"],
        "receiver_kind": "فرد", "receiver_rank": "عريف",
        "receiver_name": "فلان الفلاني", "issuer_name": "أمين المخزن",
        "record_ids": [],
        "actuals": {"tamween_أرز بلدي": 60, "tamween_سكر": 40}})
    from services import warehouses_fs
    warehouses_fs.snapshot_all(y, m)

    # 3) التاميدات (07): جهات + تأميدات
    from data_access import db_tameedat as dt
    from services import tameedat_fs
    ents = dt.list_entities(y, m)
    if not ents:
        ent_id = dt.add_entity(y, m, "قطاع الشهيد اشرف جاد (نموذج)", "شرطية")
        ent = dt.get_entity(y, m, ent_id)
        dt.add_record(y, m, 1, ent, 5, 10, 0, "تأميدة نموذجية")
        dt.add_record(y, m, 2, ent, 3, 6, 0)
    tameedat_fs.snapshot_all(y, m)

    # 4) الراغبين (03): قوة + رغبة يوم + ملفات الجهة
    from data_access import db_raghibin as drg
    from services import raghibin as rfs
    ents = dt.list_entities(y, m)
    if ents:
        eid = ents[0]["id"]
        if not drg.list_persons(y, m, entity_id=eid):
            p1, _ = drg.add_person(y, m, eid, "officers", "رصد مصطفى علي")
            p2, _ = drg.add_person(y, m, eid, "officers", "مؤخر خالد سمير")
            p3, _ = drg.add_person(y, m, eid, "individuals", "جندي احمد ابراهيم")
            p4, _ = drg.add_person(y, m, eid, "individuals", "جندي محمود حسن")
            drg.set_day_category(y, m, eid, 1, "officers", [p1])
            drg.set_day_category(y, m, eid, 1, "individuals", [p3])
        rfs.write_entity_files(y, m, eid, ents[0]["name"], day=1)

    # 5) الدولى (14): خط + نقطتين + معدلات + توزيعة
    from data_access import db_dowail as dwd
    from services import dowail_fs
    lines = dwd.list_lines(y, m)
    if not lines:
        lid = dwd.add_line(y, m, "خط العريش (نموذج)")
        dwd.add_point(y, m, lid, "نقطة الفرسات", 20)
        dwd.add_point(y, m, lid, "نقطة الصفا", 30)
        for sec, name, rate, unit in (
                ("tamween", "أرز بلدي", 1, "كجم"), ("tamween", "زيت طعام", 0.5, "لتر"),
                ("contractor", "أسمنت", 2, "كجم")):
            dwd.save_rate(y, m, sec, name, rate, unit)
        from services import dowail_build as ddb
        line = dwd.get_line(y, m, lid)
        data = ddb.snapshot(y, m, 1, 3, 3, "",
                            paper_meta=dwd.get_paper_meta(y, m))
        dowail_fs.save_to_disk(y, m, data, n_saves_same_from=1)
        dowail_fs.write_line_statement(y, m, line)

    # 6) الصحة (13): التقارير الأربعة + كشوف الأيام
    from documents import docx_health
    docx_health.rebuild_all(y, m)

    # 7) المجندين (08)
    from data_access import db_recruits as drec
    from documents import docx_recruits
    if not drec.list_recruits(y, m):
        drec.add_recruit(y, m, {"name": "جندي تجريبي أول", "mil_no": "1001",
                                "service_start": "2025-09-01", "service_end": "2026-08-31"})
        drec.add_recruit(y, m, {"name": "جندي تجريبي ثان", "mil_no": "1002",
                                "service_start": "2025-09-01", "service_end": "2026-08-31"})
    docx_recruits.rebuild_month(y, m)

    # 8) 6 مخازن (جرد الأصناف): جرد يوم تجريبي ثابت من دفاتر ٣ مخازن التجريبية
    from data_access import db_inv6 as di6
    from services import inv6_build as ib6
    from services import inv6_fs as if6
    if not di6.list_days(y, m):
        view = ib6.day_view(y, m, SEED_INV6_DAY)
        di6.save_day(y, m, SEED_INV6_DAY, view["header"], view["rows"])
    if6.save_to_disk(y, m, SEED_INV6_DAY)


# ======================================================================
# المطابقة: ملف المستخدم ↔ ناتج التوليد التجريبي
# ======================================================================
def find_source(rel):
    """ملف التوليد التجريبي المقابل: نفس المسار النسبي → نفس الاسم → None."""
    if not rel:
        return None
    _seed_once()
    root = _root()
    if not root.is_dir():
        return None
    p = root / rel
    if p.is_file() and not p.name.startswith("~$"):
        return p
    # 6 مخازن: اسم ملف الجرد تقني (يوم-شهر-سنة لاتيني) — نطابق على الشكل بس
    if "6-مخازن" in rel and rel.lower().endswith(".xlsx"):
        for q in sorted(root.rglob("*.xlsx")):
            if "6-مخازن" in str(q.relative_to(root)) and not q.name.startswith("~$"):
                return q
    base = Path(rel).name
    cands = [q for q in sorted(root.rglob(base))
             if q.is_file() and not q.name.startswith("~$") and q.name != MARKER]
    return cands[0] if cands else None


# ======================================================================
# خريطة الإحلال الحي: قيم الشهر الحالية مكان قيم الشهر التجريبي
# ======================================================================
def _live_map(year, month):
    from data_access import db_letterhead as lh
    live = lh.get_all(year, month)
    scratch = lh.get_all(SY, SM)
    m = {}
    for k in ("lh_1", "lh_2", "lh_3", "lh_4",
              "sig_right_rank", "sig_right_name",
              "sig_left_rank", "sig_left_name"):
        sv = (scratch.get(k) or "").strip()
        lv = (live.get(k) or "").strip()
        if sv and lv and sv != lv:
            m[sv] = lv
    # اسم الشهر/السنة في سطور «عن شهر»
    from core.config import MONTH_NAMES
    ly = arnum.to_arabic_indic(str(year))
    lm = MONTH_NAMES[int(month) - 1]
    sy_txt = arnum.to_arabic_indic(str(SY))
    m[f"{MONTH_NAME} {sy_txt}"] = f"{lm} {ly}"
    m[MONTH_NAME] = lm
    return m


def _sub(value, m):
    """إحلال حي في نص: القيم الطويلة الأول (١ يناير ← <شهر> <سنة> قبل يناير ← <شهر>)."""
    if value is None:
        return ""
    t = str(value)
    for old in sorted(m, key=len, reverse=True):
        if old:
            t = t.replace(old, m[old])
    return t.strip()


# ======================================================================
# العرض: قراءة ناتج التوليد التجريبي → بيانات معاينة
# ======================================================================
MAX_ROWS, MAX_COLS = 45, 20


def render_xlsx(scratch_path, sheet_i, live_map):
    from openpyxl import load_workbook
    wb = load_workbook(str(scratch_path), data_only=True)
    try:
        sheets = list(wb.sheetnames)
        if not sheets:
            return None
        sheet_i = max(0, min(int(sheet_i), len(sheets) - 1))
        ws = wb.worksheets[sheet_i]
        last_row = min(ws.max_row or 1, MAX_ROWS)
        last_col = min(ws.max_column or 1, MAX_COLS)
        cells = []
        for row in ws.iter_rows(min_row=1, max_row=last_row,
                                max_col=last_col, values_only=True):
            cells.append([_sub(c, live_map) for c in row])
        return {"kind": "xlsx", "sheets": sheets, "sheet_i": sheet_i,
                "cells": cells}
    finally:
        wb.close()


def render_docx(scratch_path, live_map):
    from docx import Document
    doc = Document(str(scratch_path))
    paras = []
    for p in doc.paragraphs:
        t = _sub(p.text, live_map)
        if not t.strip():
            continue
        bold = any(bool(r.bold) for r in p.runs)
        sizes = [r.font.size.pt for r in p.runs if r.font.size]
        size = max(sizes) if sizes else 11
        align = str(p.alignment or "")
        paras.append({"t": t, "b": bold, "s": round(size, 1),
                      "c": "CENTER" in align})
        if len(paras) >= 50:
            break
    tables = []
    for tb in doc.tables[:1]:
        tables.append([[_sub(c.text, live_map) for c in row.cells]
                       for row in tb.rows[:3]])
    return {"kind": "docx", "paras": paras, "tables": tables}


def _inv6_day(rel):
    """يوم الجرد من مسار ملف 6 مخازن (فولدر «يوم ٢» أو اسم d-m-y.xlsx)."""
    m = re.search(r"يوم\s+([0-9\u0660-\u0669]+)", rel or "")
    if m:
        return arnum.parse_int(m.group(1))
    m = re.search(r"(\d+)-\d+-\d+\.xlsx", rel or "")
    if m:
        return int(m.group(1))
    return None


def build_preview(rel, year, month, sheet_i=0):
    """معاينة ملف محلي: الشكل الحقيقي المتولد + الدباجة/التوقيعات الحية.
    يرجع None لو مفيش توليد تجريبي مطابق (يرجع القالب للشكل العام)."""
    src = find_source(rel)
    if src is None:
        return None
    live_map = _live_map(year, month)
    if "6-مخازن" in (rel or ""):
        day = _inv6_day(rel)
        if day:
            # تاريخ الجرد التجريبي ← تاريخ ملف المستخدم الحقيقي (صيغة y/m/d)
            live_map[f"تاريخ الجرد: {SM}/{SY}/{SEED_INV6_DAY}"] = \
                f"تاريخ الجرد: {int(year)}/{int(month)}/{day}"
    if src.suffix.lower() == ".xlsx":
        out = render_xlsx(src, sheet_i, live_map)
    else:
        out = render_docx(src, live_map)
    if out:
        out["rel"] = rel
        out["title"] = Path(rel).name
        out["source_name"] = src.name
    return out
