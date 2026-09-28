# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مولّد هيكل ملفات الدورات المخزنية (توجيه ٢٨/٠٩ مساءً — الإمداد والمتعهد والترفية):

١ مخازن:   ملف بشيتين — «١ مخازن» (بالمعيار) + «١ مخازن تغليف» (تفصيل كروت التغليف).
٢ مخازن:   فولدرات «يوم ١..يوم آخر الشهر» — كل يوم ملف إذون الصرف فيه شيت لكل إذن،
           وفولدر «التفاريد» بنفس فولدرات الأيام وفيه ملف تفريدة لكل جهة
           (الكمية والتغليف + تاريخ الانتهاء ومدة الصلاحية + مصروفة من مخزن إيه).
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
TAFAREED_SHEET = "التفريدة"


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
    name = "".join(ch for ch in str(title) if ch not in "\\/:*?\"<>|").strip()
    return (name or "ملف") + ".xlsx"


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
# ٢ مخازن — فولدرات الأيام + التفاريد
# ======================================================================
PERMIT_COLS = ["الصنف", "الكمية", "الوحدة", "التغليف", "نوع التغليف",
               "عدد العبوات", "سعة العبوة", "المعيار بالداخل",
               "عدد المعايير بالداخل", "وزن المعيار الواحد"]
TAF_COLS = ["م", "الصنف", "الكمية المنصرفة", "الوحدة", "المنصرف بالتغليف",
            "تغليف الدفعة", "مصروفة من مخزن", "تاريخ الانتهاء",
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
            spec.get("pack_kind") or "بدون تغليف", "—",
            _q(spec.get("pack_capacity")) or "—", spec.get("pack_inner_kind") or "—",
            _q(spec.get("pack_inner_count")) or "—", _q(spec.get("pack_inner_capacity")) or "—")


def build_wh2_days(wh2_dir, year, month, permits, specs, eom, tafreeda):
    """فولدرات «يوم N» ١..آخر الشهر: كل يوم ملف إيذان الصرف (شيت لكل إذن)
    والتفاريد بنفس الأيام: ملف تفريدة لكل جهة صرفت في ذلك اليوم."""
    from services import warehouses_fs as wf
    # فولدرات الأيام مباشرة داخل «٢ مخازن إذون الصرف» + فولدر «التفاريد» جنبها
    days_root = wh2_dir
    days_root.mkdir(parents=True, exist_ok=True)
    for sub in tuple(days_root.glob("يوم *")):
        shutil.rmtree(sub, ignore_errors=True) if sub.is_dir() else sub.unlink()
    taf_root = _reset_tree(wh2_dir / "التفاريد")
    for d in range(1, int(eom) + 1):
        (days_root / _day_folder(d)).mkdir(exist_ok=True)
        (taf_root / _day_folder(d)).mkdir(exist_ok=True)

    entity = {p["number"]: (p.get("entity_label") or "—") for p in permits}
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
                "إذون صرف يوم {}".format(arnum.to_arabic_indic(str(day)))), sheets)

    groups = {}
    for t in tafreeda or []:
        try:
            day = int(t.get("date_from") or 0)
        except (TypeError, ValueError):
            continue
        if not (1 <= day <= int(eom)):
            continue
        groups.setdefault((day, entity.get(t.get("permit_no"), "—")), []).append(t)
    for (day, ent), rows in groups.items():
        sheet = [(i, t["item"], _q(t["qty"]), t["unit"] or "—",
                  t.get("issued_label") or _q(t["qty"]),
                  t.get("pack_label") or "—", t.get("store_name") or "—",
                  wf._date_or_dash(t.get("expiry")),
                  _expiry_left(t.get("expiry"), year, month, day),
                  arnum.to_arabic_indic(str(t.get("permit_no") or "—")),
                  t.get("notes") or "—")
                 for i, t in enumerate(rows, 1)]
        _save_xlsx(taf_root / _day_folder(day) / _file_name("تفريدة - {}".format(ent)),
                   [(TAFAREED_SHEET, TAF_COLS, sheet)])


# ======================================================================
# ٣ مخازن — ملفان: الحركة العادية + التغليف
# ======================================================================
def build_wh3(wh3_dir, year, month, items, moves, book1_name, book2_name,
              cycle, aggregated_sheet="٣ مخازن مجمعة",
              tafared_sheet="٣ مخازن تفاريد"):
    """book1: أرصدة الأصناف + مجمّع الحركات + شيت لكل صنف.
    book2: مجمّع التغليف + شيت لكل صنف بالتغليف + شيت تفاريد ٣ مخازن."""
    from services import warehouses_fs as wf
    specs = dw.pack_specs_map(year, month, cycle)

    def _brk(q, name):
        sp = _pack_spec_of(specs, name)
        return dw.pack_breakdown(sp.get("pack_kind"), sp.get("pack_capacity"),
                                 sp.get("pack_inner_count"),
                                 sp.get("pack_inner_capacity"), q, "—", "سائب",
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
        sp = _pack_spec_of(specs, name)
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
    """الهيكل الجديد لدورة مستودعات (supply/contractor) — يُستدعى بعد snapshot."""
    from services import warehouses_fs as wf
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
    build_wh2_days(wf.cycle_dir(year, month, cycle, "wh2"), year, month,
                   permits, specs, eom, dw.tafreeda_rows(year, month, cycle))


def build_tarfea(year, month):
    """هيكل الترفية: إيذان صرف ترفية = tarfea_issues (بلا مقررات) — التفاريد
    تُبنى من الإيذانات نفسها بالتغليف المحسوب من مواصفات الصنف."""
    from data_access import months
    items = dw.list_items(year, month, "tarfea")
    receipts = dw.list_receipts(year, month, "tarfea", limit=10000)
    specs = dw.pack_specs_map(year, month, "tarfea")
    eom = egtime.days_in_month(year, month)
    build_wh1(wh_tarfea_dir(year, month, "wh1") / _file_name(
        "إذون إضافة ١ مخازن ترفية"), year, month, receipts, items,
        normal_sheet="إذون إضافة ١ مخازن ترفية", pack_sheet="١ مخازن ترفية تغليف")
    moves = []
    for it in items:
        card = dw.item_card(year, month, it["id"]) or {"rows": []}
        for row in card["rows"]:
            moves.append((it["name"], it["handle_unit"], row))
    build_wh3(wh_tarfea_dir(year, month, "wh3"), year, month, items, moves,
              "دفتر ٣ مخازن ترفية", "دفتر ٣ مخازن ترفية تغليف", "tarfea")

    conn = months.get_db(year, month)
    issues = [dict(r) for r in conn.execute(
        "SELECT * FROM tarfea_issues ORDER BY day, id").fetchall()]
    conn.close()
    names = {it["id"]: it for it in items}
    conn = months.get_db(year, month)
    last_exp = {r["item_id"]: r["exp_date"] for r in conn.execute(
        "SELECT item_id, exp_date FROM wh_ledger WHERE cycle='tarfea' "
        "AND COALESCE(exp_date,'')!='' ORDER BY day, id").fetchall()}
    conn.close()
    permits = []
    taf_rows = []
    for iss in issues:
        it = names.get(iss["item_id"])
        if not it:
            continue
        permits.append({"number": iss["serial"], "date_from": iss["day"],
                        "date_to": iss["day"],
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
    build_wh2_days(wh_tarfea_dir(year, month, "wh2"), year, month, permits,
                   specs, eom, taf_rows)


def wh_tarfea_dir(year, month, sub):
    from services import tarfea_fs
    return tarfea_fs.sub_dir(year, month, sub)


# ======================================================================
# المخازن والثلاجات — فولدر لكل مخزن: حركة المخزن + كشف جرد الأرصدة
# ======================================================================
def build_store_folders(base, rep, units):
    """فولدر باسم كل مخزن جواه الإكسلين:
    حركة المخزن.xlsx (شيتا: حركة المخازن + حركة المخازن تغليف)
    كشف جرد الارصدة.xlsx (شيتا: كشف جرد الأرصدة + جرد الأرصدة تغليف)."""
    for target in rep["stores"] + [rep["unassigned"]]:
        folder = base / _safe_file(target["store"]["name"])
        folder.mkdir(parents=True, exist_ok=True)
        move_rows, pack_rows = [], []
        idx = 0
        for row in target["inn"]:
            idx += 1
            doc = ("إذن إضافة رقم {}".format(arnum.to_arabic_indic(row["serial"]))
                   if row.get("serial") else "رصيد أول المدة")
            base_line = (idx, "إضافة", dates.format_date(row["date_iso"]) or row["date_iso"],
                         row["cycle"], row["item"], _q(row["qty"]), row["unit"],
                         row.get("pack_label") or "—", doc)
            move_rows.append(base_line)
            pack_rows.append(base_line[:7] + (row.get("pack_label") or "—",
                                              row.get("pack_label") or "—") + base_line[8:])
        for row in target["out"]:
            idx += 1
            doc = "إذن صرف ٢ مخازن رقم {}".format(arnum.to_arabic_indic(row["permit_no"]))
            base_line = (idx, "صرف", dates.format_date(row["date_iso"]) or row["date_iso"],
                         row["cycle"], row["item"], _q(row["qty"]), row["unit"],
                         row.get("pack_label") or "—", doc)
            move_rows.append(base_line)
            pack_rows.append(base_line[:7] + (row.get("pack_label") or "—",
                                              row.get("pack_label") or "—") + base_line[8:])
        used = set()
        _save_xlsx(folder / _file_name("حركة المخزن"), [
            (_sheet_unique(used, "حركة المخازن"),
             ["م", "النوع", "التاريخ", "الدورة", "الصنف", "الكمية", "الوحدة",
              "التغليف", "المستند"], move_rows),
            (_sheet_unique(used, "حركة المخازن تغليف"),
             ["م", "النوع", "التاريخ", "الدورة", "الصنف", "الكمية", "الوحدة",
              "التغليف", "الكمية بالتغليف", "المستند"], pack_rows)])
        bal_rows = [(i, name, _q(qty), units.get(name, "—"))
                    for i, (name, qty) in enumerate(sorted(target["balances"].items()), 1)]
        bal_pack = [(i, name, _q(qty),
                     target.get("pack_notes", {}).get(name) or _q(qty))
                    for i, (name, qty) in enumerate(sorted(target["balances"].items()), 1)]
        used2 = set()
        _save_xlsx(folder / _file_name("كشف جرد الارصدة"), [
            (_sheet_unique(used2, "كشف جرد الأرصدة"),
             ["م", "الصنف", "الرصيد", "الوحدة"], bal_rows),
            (_sheet_unique(used2, "جرد الأرصدة تغليف"),
             ["م", "الصنف", "الرصيد", "الرصيد بالتغليف"], bal_pack)])
