# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""دفتر 5 مخازن (صادر المخزن التقصيلى — توزيع 5 مخازن) — سجل تلقائي 100%.

(توجيه المستخدم ١١/١٠/٢٠٢٦): دفتر واحد لكل دورة، يتكوّن تلقائيًا من حركة
١ مخازن (إذون الإضافة) + ٢ مخازن (إذون الصرف) — نفس الحركات اللي بتشكّل
دفتر ٣ مخازن. القواعد الذهبية:
· كل رقم إذن لازم يتسجل — لا سطر يدوي ولا إدخال.
· **رصيد أول المدة ممنوع منعًا باتًا** — السجل يبدأ من الإذونات علطول.
· الكميات بوحدة التعامل (نفس قاعدة ٥ مخازن الترفية ٢٩/٠٩) — مش بالفلوس.
· الأعمدة بالمللى: م · التاريخ · رقم الإذن · الجهة · المصدر · مصروف إلى ·
  قيمة الأصناف المضافة · قيمة الأصناف المنصرفة · البيان والملحوظات والتفاصيل ·
  المسؤول والمراقب · إجراءات.
الدورات الثلاث (الإمداد/المتعهد/الترفية) بنفس الشكل تمامًا — اسم الدورة
بيظهر في شريط عنوان ملف الإكسل.
"""
from core import arabic_numbers as arnum
from data_access import db_warehouses as dw

TITLES = {
    "supply": "سجلات الإمداد والتموين",
    "contractor": "سجلات المتعهد",
    "tarfea": "سجلات الترفيه",
}
STORE_NAMES = {
    "supply": "مخزن الإمداد",
    "contractor": "مخزن المتعهد",
    "tarfea": "مخزن الترفية",
}
BOOK_TITLE = "دفتر حركه صادر ووارد المخزن التقصيلى (توزيع 5 مخازن) — {}"


def _n(x):
    """رقم منسób: ٢١٠ مش ٢١٠٫٠ — ٣ خانات كحد أقصى زي بقية الدفاتر."""
    x = float(x or 0)
    return int(x) if abs(x - round(x)) < 1e-9 else round(x, 3)


def _a(x):
    """الرقم بأرقام عربية بلا أصفار زائدة (٥٠ مش ٥٠٫٠٠) — قاعدة fmt_qty_trim."""
    return arnum.fmt_qty_trim(x) or arnum.fmt_qty_trim(0) or "\u0660"


def _date_iso(year, month, day):
    return "{:04d}-{:02d}-{:02d}".format(int(year), int(month), int(day or 0))


# ======================================================================
# الدورتان الإمداد/المتعهد — من wh_receipts + calc2_permits
# ======================================================================
def _main_entity(year, month, permit):
    """الجهة المستلمة (نفس قاعدة تاب ٢ مخازن): أول سجل مرتبط + ملحقات."""
    from data_access import db_tameedat as dtm
    mains, extras = [], []
    for rid in (permit.get("record_ids") or []):
        rec = dtm.get_record(year, month, rid)
        if not rec:
            continue
        mains.append(rec["entity_name"])
        extras.extend(rec.get("attachments") or [])
    return (mains[0] if mains else (permit.get("entity_label") or "—"), extras)


def _receipt_rows(year, month, cycle):
    """سطر لكل إذن إضافة (١ مخازن) — مجمّع برقم الإذن بالكمية الكلية."""
    items = {it["id"]: it for it in dw.raw_items(year, month, cycle)}
    groups = {}
    for r in dw.list_receipts(year, month, cycle, limit=100000):
        g = groups.setdefault(r["serial"], {"day": r["day"], "added": 0.0,
                                            "names": [], "party": "", "notes": ""})
        g["added"] += float(r.get("qty_handle") or 0)
        name = (items.get(r["item_id"]) or {}).get("name") or "—"
        g["names"].append("{} {} {}".format(name, _a(r.get("qty_handle")),
                                            r.get("unit") or ""))
        g["party"] = (r.get("supplier_name") or r.get("producer")
                      or g["party"] or "")
        g["notes"] = r.get("notes") or ""
    out = []
    for serial in sorted(groups):
        g = groups[serial]
        out.append({
            "day": int(g["day"]), "date_iso": _date_iso(year, month, g["day"]),
            "permit_no": int(serial), "kind": "add1",
            "party": g["party"] or "إذن إضافة", "source": STORE_NAMES[cycle],
            "issued_to": "", "added": _n(g["added"]), "issued": 0.0,
            "details": "إذن إضافة ١ مخازن ({}){}: {}".format(
                arnum.to_arabic_indic(str(len(g["names"]))),
                " — " + g["notes"] if g["notes"] else "",
                " + ".join(g["names"])),
            "responsible": "أمين المخزن", "ref_id": 0,
        })
    return out


def _issue_rows(year, month, cycle):
    """سطر لكل إذن صرف (٢ مخازن) — المنصرف الفعلي (FEFO) زي ما في ٣ مخازن.
    كل رقم إذن بيظهر — ولو مفيش مخزون مسجّل بيظهر بكمية ٠ مع بيان الإذن."""
    items = {it["name"]: it for it in dw.raw_items(year, month, cycle)}
    taf = {}
    for t in dw.tafreeda_rows(year, month, cycle):
        taf.setdefault(t["permit_no"], []).append(t)
    out = []
    for p in dw.permits_book(year, month, cycle):
        no = int(p["number"])
        day = int(p.get("date_from") or 0)
        entity, _extras = _main_entity(year, month, p)
        actual = taf.get(no, [])
        total = sum(float(t.get("qty") or 0) for t in actual)
        by_item = {}
        for t in actual:
            g = by_item.setdefault(t["item"], {"unit": t.get("unit") or "", "qty": 0.0})
            g["qty"] += float(t.get("qty") or 0)
        bits = ["{} {} {}".format(n, _a(g["qty"]), g["unit"])
                for n, g in sorted(by_item.items())]
        if bits:
            details = "إذن صرف ٢ مخازن: " + " + ".join(bits)
            if total <= 0:
                details += " (لم يُصرف)"
        else:
            # بلا تنفيذ (مخزون غير مسجّل) — بيان بأصناف الإذن بوحدة التعامل
            conv = []
            for it in p.get("cycle_items") or []:
                rec = items.get(it["name"])
                factor = 1.0
                if rec:
                    factor = dw.ou.calc_to_handle_factor(
                        rec.get("name"), rec.get("ration_unit"),
                        rec.get("handle_unit"), rec.get("specific_weight"))
                conv.append("{} {} {}".format(
                    it["name"], _a(float(it.get("qty") or 0) * factor),
                    it.get("unit") or (rec or {}).get("handle_unit") or ""))
            details = "إذن صرف ٢ مخازن (بلا تنفيذ — بلا مخزون مسجّل): " \
                + " + ".join(conv) if conv else "إذن صرف ٢ مخازن (بلا أصناف)"
        out.append({
            "day": day, "date_iso": _date_iso(year, month, day),
            "permit_no": no, "fiscal": int(p.get("fiscal_year") or 0),
            "kind": "issue2", "party": "", "source": "", "issued_to": entity,
            "added": 0.0, "issued": _n(total), "details": details,
            "responsible": (p.get("issuer_name") or "").strip(),
            "ref_id": 0,
        })
    return out


def rows(year, month, cycle):
    """أسطر الدفتر للدورتين الإمداد/المتعهد — الإضافة قبل الصرف في نفس اليوم."""
    out = _receipt_rows(year, month, cycle) + _issue_rows(year, month, cycle)
    out.sort(key=lambda x: (x["day"], 0 if x["kind"] == "add1" else 1,
                            x["permit_no"], x["kind"]))
    return out


# ======================================================================
# دورة الترفية — من tarfea receipts/issues (نفس الشكل تمامًا — توجيه ١١/١٠)
# ======================================================================
def tarfea_rows(year, month):
    from data_access import db_tarfea as dt
    items = {it["id"]: it for it in dt.list_items(year, month)}
    groups = {}
    for r in dt.list_receipts(year, month):
        g = groups.setdefault(r["serial"], {"day": r["day"], "added": 0.0,
                                            "names": [], "party": "", "notes": ""})
        g["added"] += float(r.get("qty_handle") or 0)
        name = (items.get(r.get("item_id")) or {}).get("name") or "—"
        g["names"].append("{} {} {}".format(name, _a(r.get("qty_handle")),
                                            r.get("unit") or ""))
        g["party"] = (r.get("supplier_name") or r.get("producer")
                      or g["party"] or "")
        g["notes"] = r.get("notes") or ""
    out = []
    for serial in sorted(groups):
        g = groups[serial]
        out.append({
            "day": int(g["day"]), "date_iso": _date_iso(year, month, g["day"]),
            "permit_no": int(serial), "kind": "add1",
            "party": g["party"] or "إذن إضافة", "source": STORE_NAMES["tarfea"],
            "issued_to": "", "added": _n(g["added"]), "issued": 0.0,
            "details": "إذن إضافة ١ مخازن ({}){}: {}".format(
                arnum.to_arabic_indic(str(len(g["names"]))),
                " — " + g["notes"] if g["notes"] else "",
                " + ".join(g["names"])),
            "responsible": "أمين المخزن", "ref_id": 0,
        })
    for i in dt.list_issues(year, month):
        out.append({
            "day": int(i["day"]), "date_iso": _date_iso(year, month, i["day"]),
            "permit_no": int(i["serial"]), "kind": "issue2",
            "party": "", "source": "", "issued_to": (i.get("receiver") or "—").strip(),
            "added": 0.0, "issued": _n(i.get("qty")),
            "details": "إذن صرف ٢ مخازن: {} {} {}".format(
                i.get("item_name") or "—", _a(i.get("qty")),
                i.get("unit") or (items.get(i.get("item_id")) or {})
                .get("handle_unit") or ""),
            "responsible": (i.get("responsible") or "").strip(),
            "ref_id": int(i.get("id") or 0),
        })
    out.sort(key=lambda x: (x["day"], 0 if x["kind"] == "add1" else 1,
                            x["permit_no"], x["kind"]))
    return out


def context(year, month, cycle):
    """سياق التاب: الأسطر + الإجماليات + شريط العنوان — للدورة المطلوبة."""
    if cycle == "tarfea":
        rws = tarfea_rows(year, month)
    else:
        rws = rows(year, month, cycle)
    total_added = _n(sum(float(r["added"] or 0) for r in rws))
    total_issued = _n(sum(float(r["issued"] or 0) for r in rws))
    last = rws[-1] if rws else None
    return {
        "rows": rws, "total_added": total_added, "total_issued": total_issued,
        "count": len(rws),
        "last": last["date_iso"] if last else "—",
        "title": BOOK_TITLE.format(TITLES.get(cycle, "سجلات الدورة")),
        "store": STORE_NAMES.get(cycle, "المخزن"),
    }
