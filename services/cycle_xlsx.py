# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مولّد هيكل ملفات الدورات المخزنية (توجيه ٢٨/٠٩ ليلًا — الإمداد والمتعهد والترفية):

١ مخازن:   ملف بشيتين — «١ مخازن» (بالمعيار) + «١ مخازن تغليف» (تفصيل كروت التغليف).
٢ مخازن:   فولدر «٢ مخازن» فيه ملف مجمع + فولدرات «يوم ١..يوم آخر الشهر» كل يوم
           ملف إيذان الصرف فيه شيت لكل إذن، وفولدر «٢ مخازن تفاريد» فيه ملف مجمع
           + نفس فولدرات الأيام وكل يوم ملف تفاريد ذلك اليوم
           (الكمية والتغليف + تاريخ الانتهاء ومدة الصلاحية + مخزن).
٣ مخازن:   ملفان — «دفتر ٣ مخازن»: شيت أرصدة + شيت مجمع للحركات + شيت لكل صنف،
           و«دفتر ٣ مخازن تغليف»: مجمّع التغليف + شيت لكل صنف + شيت تفاريد ٣ مخازن.

كلها مرايا مقروءة تتكتب مع كل snapshot للدورة — القاعدة تظل مصدر الحقيقة.
"""
import shutil
from datetime import date as _date

from core import arabic_numbers as arnum, dates, egtime
from data_access import db_warehouses as dw
from services.tameedat_fs import _save_xlsx

DAY_FMT = "يوم {}"


def _q(x):
    try:
        return arnum.fmt_qty(float(x))
    except (TypeError, ValueError):
        return x if x is not None else "—"


def _day_folder(day):
    return DAY_FMT.format(arnum.to_arabic_indic(str(day)))


def _sheet_unique(used, title):
    name = "".join(ch for ch in str(title) if ch not in "[]:*?/\\")[:28].strip() or "شيت"
    base, i = name, 2
    while name in used:
        name = "{} {}".format(base[:26], arnum.to_arabic_indic(str(i)))
        i += 1
    used.add(name)
    return name


def _safe_file(title):
    return "".join(ch for ch in str(title) if ch not in "\\/:*?\"<>|").strip() or "ملف"


def _file_name(title):
    return _safe_file(title) + ".xlsx"


def _expiry_left(expiry, year, month, day):
    try:
        exp = _date.fromisoformat(str(expiry)[:10])
    except (TypeError, ValueError):
        return "—"
    left = (exp - _date(year, month, int(day))).days
    if left < 0:
        return "منتهي الصلاحية"
    return arnum.to_arabic_indic(str(left)) + " يوم"


def _detailed_pack(r):
    if not (r.get("pack_kind") or r.get("pack_count") or r.get("pack_loose")):
        return ("بدون تغليف", "—", "—", "—", "—", "—", "—", "—")
    return (r.get("pack_kind") or "—", _q(r.get("pack_count")) or "—",
            _q(r.get("pack_capacity")) or "—", r.get("pack_inner_kind") or "—",
            _q(r.get("pack_inner_count")) or "—", _q(r.get("pack_inner_capacity")) or "—",
            _q(r.get("pack_loose")) if r.get("pack_loose") else "—",
            r.get("pack_loose_unit") or (r.get("unit") or "—"))


def _reset_tree(root):
    """فولدرات الأيام مرآة تتبع الداتا — تُفرَّغ وتُعاد من الصفر."""
    root.mkdir(parents=True, exist_ok=True)
    for sub in tuple(root.iterdir()):
        shutil.rmtree(sub, ignore_errors=True) if sub.is_dir() else sub.unlink()
    return root


def _migrate(root, *old_names):
    """حذف أسماء ملفات/فولدرات قديمة بعد إعادة الهيكلة (مرايا تتتبع الجديد فقط)."""
    for name in old_names:
        path = root / name
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()


# ======================================================================
# ١ مخازن — ملف بشيتين: ١ مخازن + ١ مخازن تغليف
# ======================================================================
WH1_COLS = ["رقم الإذن", "اليوم", "يوم الشهر", "التاريخ", "الصنف", "الكمية",
            "وحدة التعامل", "يعادل (قاعدة)", "وحدة القاعدة", "التغليف", "المخازن",
            "الشركة المنتجة", "المورد", "تاريخ الإنتاج", "تاريخ الصلاحية",
            "مدة الصلاحية (يوم)", "ملاحظات"]
PACK_COLS = ["نوع التغليف", "عدد العبوات", "سعة العبوة", "المعيار بالداخل",
             "عدد المعايير بالداخل", "وزن المعيار الواحد", "كمية سائبة",
             "وحدة السائب"]


def build_wh1(path, year, month, receipts, items,
              normal_sheet="إذون إضافة ١ مخازن", pack_sheet="١ مخازن تغليف"):
    from services import warehouses_fs as wf
    normal, packed = [], []
    for r in sorted(receipts, key=lambda x: x["serial"]):
        row = (r["serial"], wf._wday(r["day"], year, month), r["day"],
               wf._d(r["day"], year, month), wf._item_name(items, r["item_id"]),
               r["qty_handle"], r["unit"], r["qty_base"], r["base_unit"],
               wf._pack_cell(r), wf._stores_cell(r), r["producer"] or "—",
               r["supplier_name"] or "—", wf._date_or_dash(r["prod_date"]),
               wf._date_or_dash(r["exp_date"]),
               r["shelf_days"] if r["shelf_days"] is not None else "—",
               dw.user_notes(r["notes"]) or "—")
        normal.append(row)
        packed.append(row[:9] + _detailed_pack(r) + row[10:])
    used = set()
    _save_xlsx(path, [
        (_sheet_unique(used, normal_sheet), WH1_COLS, normal),
        (_sheet_unique(used, pack_sheet), WH1_COLS[:9] + PACK_COLS + WH1_COLS[10:],
         packed)])
    return path


# ======================================================================
# ٢ مخازن — فولدر «٢ مخازن» (مجمع + الأيام) وفولدر «٢ مخازن تفاريد»
# ======================================================================
PERMIT_COLS = ["الصنف", "الكمية", "الوحدة", "التغليف", "نوع التغليف",
               "سعة العبوة", "المعيار بالداخل", "عدد المعايير بالداخل",
               "وزن المعيار الواحد"]
PERMIT_AGG_COLS = ["رقم الإذن", "من يوم", "إلى يوم", "أيام الصرف", "الجهات",
                   "الصنف", "الكمية الفعلية", "الوحدة", "التغليف"]
TAF_COLS = ["م", "الجهة", "الصنف", "الكمية المنصرفة", "الوحدة",
            "المنصرف بالتغليف", "تغليف الدفعة", "مخزن", "تاريخ الانتهاء",
            "الصلاحية المتبقية", "إذن رقم", "ملاحظات"]


def _pack_spec_of(specs, item_name):
    entry = specs.get(item_name) or {}
    if not entry:
        return {}
    kind = list(entry)[-1]
    sp = entry[kind] or {}
    return {"pack_kind": kind, "pack_capacity": sp.get("capacity"),
            "pack_inner_count": sp.get("inner_count"),
            "pack_inner_capacity": sp.get("inner_capacity"),
            "pack_inner_kind": sp.get("inner_kind")}


def _permit_row(name, qty, unit, spec):
    brk = dw.pack_breakdown(spec.get("pack_kind"), spec.get("pack_capacity"),
                            spec.get("pack_inner_count"), spec.get("pack_inner_capacity"),
                            qty, unit, "—", inner_kind=spec.get("pack_inner_kind")) or "—"
    return (name, _q(qty), unit or "—", brk,
            spec.get("pack_kind") or "بدون تغليف",
            _q(spec.get("pack_capacity")) or "—", spec.get("pack_inner_kind") or "—",
            _q(spec.get("pack_inner_count")) or "—", _q(spec.get("pack_inner_capacity")) or "—")


def _taf_row(i, t, ent, year, month):
    return (i, ent, t["item"], _q(t["qty"]), t["unit"] or "—",
            t.get("issued_label") or _q(t["qty"]),
            t.get("pack_label") or "—", t.get("store_name") or "—",
            dates.format_date(t.get("expiry")) if t.get("expiry") else "—",
            _expiry_left(t.get("expiry"), year, month, int(t.get("date_from") or 1)),
            arnum.to_arabic_indic(str(t.get("permit_no") or "—")),
            t.get("notes") or "—")


def build_wh2_days(wh2_dir, taf_dir, year, month, permits, specs, eom, tafreeda,
                   agg_name="٢ مخازن مجمع", taf_agg_name="٢ مخازن تفاريد مجمع",
                   day_file="إذون صرف يوم {}", taf_day_file="تفاريد يوم {}",
                   agg_sheet="٢ مخازن"):
    """فولدر «٢ مخازن»: ملف مجمع + فولدرات «يوم N» بملف اليوم (شيت لكل إذن).
    فولدر «٢ مخازن تفاريد»: ملف مجمع + نفس الأيام وكل يوم ملف تفاريد اليوم."""
    days_root = wh2_dir
    days_root.mkdir(parents=True, exist_ok=True)
    for sub in tuple(days_root.glob("يوم *")):
        shutil.rmtree(sub, ignore_errors=True) if sub.is_dir() else sub.unlink()
    taf_root = _reset_tree(taf_dir)

    # ---------- المجمع ----------
    agg_rows = []
    for p in permits:
        for it in p["cycle_items"]:
            agg_rows.append((p["number"], p["date_from"], p["date_to"],
                             p["issue_days"], p["entity_label"] or "—",
                             it["name"], _q(it["qty"]), it.get("unit") or "—",
                             _pack_spec_brk(specs, it["name"], it["qty"], it.get("unit"))))
    _save_xlsx(days_root / _file_name(agg_name),
               [(_sheet_unique(set(), agg_sheet), PERMIT_AGG_COLS, agg_rows)])

    # ---------- فولدرات الأيام ----------
    for d in range(1, int(eom) + 1):
        (days_root / _day_folder(d)).mkdir(exist_ok=True)
        (taf_root / _day_folder(d)).mkdir(exist_ok=True)
    by_day = {}
    for p in permits:
        try:
            by_day.setdefault(int(p["date_from"] or 0), []).append(p)
        except (TypeError, ValueError):
            continue
    for day, day_permits in by_day.items():
        if not (1 <= day <= int(eom)) or not day_permits:
            continue
        used = set()
        sheets = []
        for p in day_permits:
            rows = [_permit_row(it["name"], it["qty"], it.get("unit"),
                                _pack_spec_of(specs, it["name"]))
                    for it in p["cycle_items"]]
            sheets.append((_sheet_unique(used, "إذن {}".format(
                arnum.to_arabic_indic(str(p["number"])))), PERMIT_COLS, rows))
        if sheets:
            _save_xlsx(days_root / _day_folder(day) / _file_name(
                day_file.format(arnum.to_arabic_indic(str(day)))), sheets)

    entity = {p["number"]: (p.get("entity_label") or "—") for p in permits}
    groups = {}
    for t in tafreeda or []:
        try:
            day = int(t.get("date_from") or 0)
        except (TypeError, ValueError):
            continue
        if not (1 <= day <= int(eom)):
            continue
        groups.setdefault((day, entity.get(t.get("permit_no"), "—")), []).append(t)
    # مجمع التفاريد
    taf_agg = [_taf_row(i, t, entity.get(t.get("permit_no"), "—"), year, month)
               for i, t in enumerate(tafreeda or [], 1)]
    _save_xlsx(taf_root / _file_name(taf_agg_name),
               [(_sheet_unique(set(), "٢ مخازن تفاريد"), TAF_COLS, taf_agg)])
    # ملف كل يوم
    by_taf_day = {}
    for (day, ent), rows in groups.items():
        by_taf_day.setdefault(day, []).extend((ent, t) for t in rows)
    for day, pairs in by_taf_day.items():
        sheet = [_taf_row(i, t, ent, year, month)
                 for i, (ent, t) in enumerate(pairs, 1)]
        _save_xlsx(taf_root / _day_folder(day) / _file_name(
            taf_day_file.format(arnum.to_arabic_indic(str(day)))),
            [(_sheet_unique(set(), "٢ مخازن تفاريد"), TAF_COLS, sheet)])


def _pack_spec_brk(specs, name, qty, unit):
    sp = _pack_spec_of(specs, name)
    return dw.pack_breakdown(sp.get("pack_kind"), sp.get("pack_capacity"),
                             sp.get("pack_inner_count"), sp.get("pack_inner_capacity"),
                             qty, unit or "—", "—",
                             inner_kind=sp.get("pack_inner_kind")) or "—"


# ======================================================================
# ٣ مخازن — ملفان: الحركة العادية + التغليف
# ======================================================================
def build_wh3(wh3_dir, year, month, items, moves, book1_name, book2_name,
              cycle, aggregated_sheet="٣ مخازن مجمعة",
              tafared_sheet="٣ مخازن تفاريد"):
    from services import warehouses_fs as wf
    specs = dw.pack_specs_map(year, month, cycle)

    units_map = {it["name"]: it["handle_unit"] for it in items}

    def _brk(q, name):
        sp = _pack_spec_of(specs, name)
        return dw.pack_breakdown(sp.get("pack_kind"), sp.get("pack_capacity"),
                                 sp.get("pack_inner_count"),
                                 sp.get("pack_inner_capacity"), q,
                                 units_map.get(name, "—"), "سائب",
                                 inner_kind=sp.get("pack_inner_kind")) or _q(q)

    balance_rows = [(i, it["name"], it["handle_unit"], it["ration_unit"] or "—",
                     it["balance"]) for i, it in enumerate(items, 1)]
    agg_rows, per_item = [], {}
    for idx, (name, _unit, row) in enumerate(moves, 1):
        line = (idx, name, wf._wday(row["day"], year, month), row["day"],
                wf._d(row["day"], year, month), row["permit_no"] or "—",
                row["label"], row["added"], row["issued"], row["balance"],
                row["notes"] or "—")
        agg_rows.append(line)
        per_item.setdefault(name, []).append(
            (len(per_item.get(name, [])) + 1,) + line[1:])
    used = set()
    book1 = [(_sheet_unique(used, "أرصدة الأصناف"),
              ["م", "الصنف", "وحدة التعامل", "وحدة المقرر", "الرصيد"], balance_rows),
             (_sheet_unique(used, aggregated_sheet),
              ["م", "الصنف", "اليوم", "يوم الشهر", "التاريخ", "رقم الإذن",
               "البيان", "مضاف", "منصرف", "الرصيد", "ملاحظات"], agg_rows)]
    for name, rows in sorted(per_item.items()):
        book1.append((_sheet_unique(used, name),
                      ["م", "الصنف", "اليوم", "يوم الشهر", "التاريخ", "رقم الإذن",
                       "البيان", "مضاف", "منصرف", "الرصيد", "ملاحظات"], rows))
    _save_xlsx(wh3_dir / _file_name(book1_name), book1)

    agg_pack = [(idx, name, wf._wday(row["day"], year, month), row["day"],
                 wf._d(row["day"], year, month), row["permit_no"] or "—",
                 row["label"], row["added"], _brk(row["added"], name),
                 row["issued"], _brk(row["issued"], name) if row["issued"] else "—",
                 row["balance"], _brk(row["balance"], name),
                 row["notes"] or "—")
                for idx, (name, _unit, row) in enumerate(moves, 1)]
    taf_rows = []
    for it in items:
        taf3 = wf.taf3_pack_rows(year, month, cycle, it["id"])
        for r in (taf3 or {}).get("rows", []):
            taf_rows.append((len(taf_rows) + 1, it["name"], r["day"],
                             wf._d(r["day"], year, month), r["permit_no"] or "—",
                             r["label"] or "—", r["added_pack"] or "—",
                             r["issued_pack"] or "—", r["bal_pack"] or "—",
                             r["notes"] or "—"))
    used2 = set()
    book2 = [(_sheet_unique(used2, "٣ مخازن مجمعة تغليف"),
              ["م", "الصنف", "اليوم", "يوم الشهر", "التاريخ", "رقم الإذن",
               "البيان", "مضاف", "مضاف بالتغليف", "منصرف",
               "منصرف بالتغليف", "الرصيد", "الرصيد بالتغليف", "ملاحظات"],
              agg_pack),
             (_sheet_unique(used2, tafared_sheet),
              ["م", "الصنف", "يوم الشهر", "التاريخ", "رقم الإذن", "البيان",
               "مضاف بالتغليف", "منصرف بالتغليف", "الرصيد بالتغليف", "ملاحظات"],
              taf_rows)]
    for name in sorted(per_item):
        rows = [(r[0], r[1], r[6], r[7], _brk(r[7], name), r[8],
                 _brk(r[8], name) if r[8] else "—", r[9], _brk(r[9], name), r[10])
                for r in per_item[name]]
        book2.insert(1, (_sheet_unique(used2, name + " تغليف"),
                         ["م", "الصنف", "البيان", "مضاف", "مضاف بالتغليف",
                          "منصرف", "منصرف بالتغليف", "الرصيد",
                          "الرصيد بالتغليف", "ملاحظات"], rows))
    _save_xlsx(wh3_dir / _file_name(book2_name), book2)
    return wh3_dir / _file_name(book2_name)


# ======================================================================
# نقاط الدخول — تُستدعى من مرايا الدورات
# ======================================================================
def build_cycle(year, month, cycle):
    """الهيكل الجديد لدورة مستودعات (supply/contractor/tarfea) — بعد snapshot."""
    from services import warehouses_fs as wf
    wh2 = wf.cycle_dir(year, month, cycle, "wh2")
    _migrate(wh2.parent, "٢ مخازن إذون الصرف")   # ترحيل من الاسم القديم
    items = dw.list_items(year, month, cycle)
    receipts = dw.list_receipts(year, month, cycle, limit=10000)
    permits = dw.permits_book(year, month, cycle)
    specs = dw.pack_specs_map(year, month, cycle)
    eom = egtime.days_in_month(year, month)
    suffix = " ترفية" if cycle == "tarfea" else ""
    build_wh1(wf.cycle_dir(year, month, cycle, "wh1") / _file_name(
        "إذون إضافة ١ مخازن" + suffix), year, month, receipts, items,
        normal_sheet="إذون إضافة ١ مخازن", pack_sheet="١ مخازن تغليف")
    moves = []
    for it in items:
        card = dw.item_card(year, month, it["id"]) or {"rows": []}
        for row in card["rows"]:
            moves.append((it["name"], it["handle_unit"], row))
    build_wh3(wf.cycle_dir(year, month, cycle, "wh3"), year, month, items, moves,
              "دفتر ٣ مخازن" + suffix, "دفتر ٣ مخازن{} تغليف".format(suffix),
              cycle)
    build_wh2_days(wh2, wh2.parent / "٢ مخازن تفاريد", year, month,
                   permits, specs, eom, dw.tafreeda_rows(year, month, cycle))


def build_tarfea(year, month):
    """هيكل الترفية (نفس المستودعات): إيذان الصرف = tarfea_issues بلا مقررات،
    والتفاريد تُبنى من الإيذانات بالتغليف المحسوب من مواصفات الصنف."""
    from data_access import months
    from services import tarfea_fs
    items = dw.list_items(year, month, "tarfea")
    receipts = dw.list_receipts(year, month, "tarfea", limit=10000)
    specs = dw.pack_specs_map(year, month, "tarfea")
    eom = egtime.days_in_month(year, month)
    build_wh1(tarfea_fs.sub_dir(year, month, "wh1") / _file_name(
        "إذون إضافة ١ مخازن ترفية"), year, month, receipts, items,
        normal_sheet="إذون إضافة ١ مخازن ترفية", pack_sheet="١ مخازن ترفية تغليف")
    moves = []
    for it in items:
        card = dw.item_card(year, month, it["id"]) or {"rows": []}
        for row in card["rows"]:
            moves.append((it["name"], it["handle_unit"], row))
    build_wh3(tarfea_fs.sub_dir(year, month, "wh3"), year, month, items, moves,
              "دفتر ٣ مخازن ترفية", "دفتر ٣ مخازن ترفية تغليف", "tarfea")

    wh2 = tarfea_fs.sub_dir(year, month, "wh2")
    taf_dir = wh2.parent / "٢ مخازن تفاريد"
    conn = months.get_db(year, month)
    issues = [dict(r) for r in conn.execute(
        "SELECT * FROM tarfea_issues ORDER BY day, id").fetchall()]
    last_exp = {r["item_id"]: r["exp_date"] for r in conn.execute(
        "SELECT item_id, exp_date FROM wh_ledger WHERE cycle='tarfea' "
        "AND COALESCE(exp_date,'')!='' ORDER BY day, id").fetchall()}
    conn.close()
    names = {it["id"]: it for it in items}
    permits, taf_rows = [], []
    for iss in issues:
        it = names.get(iss["item_id"])
        if not it:
            continue
        permits.append({"number": iss["serial"], "date_from": iss["day"],
                        "date_to": iss["day"], "issue_days": 1,
                        "entity_label": iss["receiver"] or "—",
                        "cycle_items": [{"name": it["name"], "qty": iss["qty"],
                                         "unit": it["handle_unit"]}]})
        sp = _pack_spec_of(specs, it["name"])
        expiry = last_exp.get(iss["item_id"]) or ""
        taf_rows.append({
            "date_from": iss["day"], "permit_no": iss["serial"], "item": it["name"],
            "unit": it["handle_unit"], "qty": iss["qty"],
            "issued_label": dw.pack_breakdown(
                sp.get("pack_kind"), sp.get("pack_capacity"),
                sp.get("pack_inner_count"), sp.get("pack_inner_capacity"),
                iss["qty"], it["handle_unit"], "—",
                inner_kind=sp.get("pack_inner_kind")) or _q(iss["qty"]),
            "pack_label": (sp.get("pack_kind") or "—"), "store_name": "—",
            "expiry": expiry, "notes": iss["notes"] or "",
        })
    build_wh2_days(wh2, taf_dir, year, month, permits, specs, eom, taf_rows,
                   agg_name="٢ مخازن مجمع", taf_agg_name="٢ مخازن تفاريد مجمع",
                   day_file="إذون صرف ترفية يوم {}",
                   taf_day_file="تفاريد ترفية يوم {}")


# ======================================================================
# المخازن والثلاجات — فولدر لكل مخزن (٤ ملفات) + مجمع في جذر القسم
# ======================================================================
def build_store_folders(base, rep, units, year=2026, month=9):
    """جذر القسم: ملفا «حركة المخازن» و«حركة المخازن تغليف» مجمعين،
    وفولدر لكل مخزن فيه: حركة المخزن + حركة المخزن تفاريد
    + جرد المخزن كميات + جرد المخزن تغليف."""
    taf_by_store = {}
    for cycle in ("supply", "contractor"):
        try:
            for t in dw.tafreeda_rows(year, month, cycle):
                taf_by_store.setdefault(t.get("store_id"), []).append(t)
        except Exception:
            continue

    def _exp_left(expiry, day):
        try:
            exp = _date.fromisoformat(str(expiry)[:10])
        except (TypeError, ValueError):
            return "—"
        left = (exp - _date(year, month, int(day))).days
        return "منتهي الصلاحية" if left < 0 else \
            arnum.to_arabic_indic(str(left)) + " يوم"

    all_move, all_move_pack = [], []
    idx = 0
    for target in rep["stores"] + [rep["unassigned"]]:
        store_name = target["store"]["name"]
        folder = base / _safe_file(store_name)
        folder.mkdir(parents=True, exist_ok=True)
        _migrate(folder, "كشف جرد الارصدة.xlsx")
        move_rows, taf_rows = [], []
        for row in target["inn"]:
            idx += 1
            doc = ("إذن إضافة رقم {}".format(arnum.to_arabic_indic(row["serial"]))
                   if row.get("serial") else "رصيد أول المدة")
            move_rows.append((idx, "إضافة",
                              dates.format_date(row["date_iso"]) or row["date_iso"],
                              row["cycle"], row["item"], _q(row["qty"]),
                              row["unit"], row.get("pack_label") or "—", doc))
        for row in target["out"]:
            idx += 1
            doc = "إذن صرف ٢ مخازن رقم {}".format(
                arnum.to_arabic_indic(row["permit_no"]))
            move_rows.append((idx, "صرف",
                              dates.format_date(row["date_iso"]) or row["date_iso"],
                              row["cycle"], row["item"], _q(row["qty"]),
                              row["unit"], row.get("pack_label") or "—", doc))
            taf_rows.append((len(taf_rows) + 1,
                             dates.format_date(row["date_iso"]) or row["date_iso"],
                             row["item"], _q(row["qty"]), row["unit"],
                             row.get("issued_label") or row.get("pack_label") or "—",
                             doc, "—"))
        used = set()
        _save_xlsx(folder / _file_name("حركة المخزن"), [
            (_sheet_unique(used, "حركة المخزن"),
             ["م", "النوع", "التاريخ", "الدورة", "الصنف", "الكمية", "الوحدة",
              "التغليف", "المستند"], move_rows)])
        used = set()
        _save_xlsx(folder / _file_name("حركة المخزن تفاريد"), [
            (_sheet_unique(used, "حركة المخزن تفاريد"),
             ["م", "التاريخ", "الصنف", "الكمية", "الوحدة",
              "المنصرف بالتغليف", "المستند", "الصلاحية"], taf_rows)])
        bal_rows = [(i, name, _q(qty), units.get(name, "—"))
                    for i, (name, qty) in enumerate(sorted(target["balances"].items()), 1)]
        bal_pack = [(i, name, _q(qty),
                     target.get("pack_notes", {}).get(name) or _q(qty))
                    for i, (name, qty) in enumerate(sorted(target["balances"].items()), 1)]
        used = set()
        _save_xlsx(folder / _file_name("جرد المخزن كميات"), [
            (_sheet_unique(used, "جرد المخزن كميات"),
             ["م", "الصنف", "الرصيد", "الوحدة"], bal_rows)])
        used = set()
        _save_xlsx(folder / _file_name("جرد المخزن تغليف"), [
            (_sheet_unique(used, "جرد المخزن تغليف"),
             ["م", "الصنف", "الرصيد", "الرصيد بالتغليف"], bal_pack)])
        for row in move_rows:
            line = (row[0], store_name) + row[1:]
            all_move.append(line)
            all_move_pack.append((line[:7]) + (row[7], line[8]))
    used = set()
    _save_xlsx(base / _file_name("حركة المخازن"), [
        (_sheet_unique(used, "حركة المخازن مجمع"),
         ["م", "المخزن", "النوع", "التاريخ", "الدورة", "الصنف", "الكمية",
          "الوحدة", "التغليف", "المستند"], all_move)])
    used = set()
    _save_xlsx(base / _file_name("حركة المخازن تغليف"), [
        (_sheet_unique(used, "حركة المخازن تغليف مجمع"),
         ["م", "المخزن", "النوع", "التاريخ", "الدورة", "الصنف", "الكمية",
          "الوحدة", "التغليف", "المستند"], all_move_pack)])


# ======================================================================
# مخزن الترفية — مجلد Excel منفصل تمامًا داخل 11-الترفية
# ======================================================================
def build_tarfea_store(base, rep):
    """مخزن الترفية/: حركة المخزن.xlsx (مجمّع + شيت لكل صنف)
    + كشف جرد الأرصدة.xlsx (الكميات + التغليف)."""
    store_dir = base / _safe_file(rep["store_name"])
    store_dir.mkdir(parents=True, exist_ok=True)
    move_rows, per_item = [], {}
    idx = 0
    for row in rep["inn"]:
        idx += 1
        line = (idx, "إضافة", dates.format_date(row["date_iso"]) or row["date_iso"],
                row["item"], _q(row["qty"]), row["unit"],
                row.get("pack_label") or "—", row.get("doc") or "—")
        move_rows.append(line)
        per_item.setdefault(row["item"], []).append(
            (len(per_item.get(row["item"], [])) + 1,) + line[1:])
    for row in rep["out"]:
        idx += 1
        line = (idx, "صرف", dates.format_date(row["date_iso"]) or row["date_iso"],
                row["item"], _q(row["qty"]), row["unit"],
                row.get("pack_label") or "—",
                "{} — إلى: {}".format(row.get("doc") or "—", row.get("receiver") or "—"))
        move_rows.append(line)
        per_item.setdefault(row["item"], []).append(
            (len(per_item.get(row["item"], [])) + 1,) + line[1:])
    used = set()
    book = [(_sheet_unique(used, "حركة المخزن مجمعه"),
             ["م", "النوع", "التاريخ", "الصنف", "الكمية", "الوحدة", "التغليف",
              "المستند"], move_rows)]
    for name, rows in sorted(per_item.items()):
        book.append((_sheet_unique(used, name),
                     ["م", "النوع", "التاريخ", "الصنف", "الكمية", "الوحدة",
                      "التغليف", "المستند"], rows))
    _save_xlsx(store_dir / _file_name("حركة المخزن"), book)
    bal_rows = [(i, name, _q(qty), rep["pack_notes"].get(name) or "—")
                for i, (name, qty) in enumerate(sorted(rep["balances"].items()), 1)]
    used = set()
    _save_xlsx(store_dir / _file_name("كشف جرد الأرصدة"), [
        (_sheet_unique(used, "كشف جرد الأرصدة"),
         ["م", "الصنف", "الرصيد", "التغليف"], bal_rows)])
    return store_dir
