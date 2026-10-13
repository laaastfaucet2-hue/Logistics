# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""المخازن الفيزيائية — التفريدة التلقائية (الأقرب صلاحية أولًا) وحركة المخازن.
انفصل عن db_warehouses بقاعدة ≤1000 سطر (نفس نمط db_pack): الاستدعاءات اللي
تحتاج من db_warehouses استيراد مؤجل جوه الدالة (تجنّب الدوران)."""
from core import arabic_numbers as arnum
from data_access import months
from data_access.packaging import pack_breakdown, pack_split

# ========== المخازن الفيزيائية: التفريدة التلقائية (الأقرب صلاحية أولًا) وحركة المخازن ==========
UNASSIGNED = "غير موزع على مخازن"
NO_EXPIRY = "9999-12-31"


def receipt_groups(year, month, cycle):
    from data_access import db_warehouses as _dw   # استيراد مؤجل — تجنّب الدوران
    """إيذانات ١ مخازن مجمعة: إذن واحد قد يشمل كذا صنف — صفوف نفس serial تتجمع."""
    from datetime import date as _date; from core import egtime as _eg
    out = {}
    names = {it["id"]: it["name"] for it in _dw.list_items(year, month, cycle)}
    for r in _dw.list_receipts(year, month, cycle):
        try: wday = _eg.weekday_ar(_date.fromisoformat(r["date_iso"] or ""))
        except ValueError: wday = None
        g = out.setdefault(r["serial"], {"serial": r["serial"], "day": r["day"], "date_iso": r["date_iso"], "wday": wday, "supplier_name": r["supplier_name"], "producer": r["producer"], "notes": user_notes(r["notes"]), "lines": []})
        rr = dict(r); rr["notes"] = user_notes(r["notes"]); rr["item_name"] = names.get(r["item_id"], "—"); g["lines"].append(rr)
    return [out[k] for k in sorted(out)]

def user_notes(notes):
    """ملاحظات المستخدم فقط — البتات التلقائية (مخازن:/منتج:/مورد:) لا تُعرض أبدًا (توجيه ٢٧/٠٩)."""
    segs = [seg.strip() for seg in (notes or "").split(" — ")]
    return " — ".join(seg for seg in segs if seg and not seg.startswith(("مخازن:", "منتج:", "مورد:")))


@months.memo
def _batch_pool(year, month, cycle):
    from data_access import db_warehouses as _dw   # استيراد مؤجل — تجنّب الدوران
    """دفعات الدورة مرتبة: الأقرب صلاحية أولًا وتساوي ⇒ الأقدم إضافةً (قرار المستخدم)."""
    # raw_items (بلا أرصدة) — list_items بتعدي على item_balances وسطر المنصرف
    # بيستدعي التفريد (الحوض نفسه) فتطلع حلقة لا نهائية
    items = {it["id"]: it for it in _dw.raw_items(year, month, cycle)}
    conn = _dw._conn(year, month)
    openers = [dict(r) for r in conn.execute("SELECT * FROM wh_ledger WHERE cycle=? AND kind='opener'", (cycle,))]
    conn.close()
    opener_parts = _dw.opener_stores(year, month, cycle)
    pool = []
    def _opener_producer(o):
        _n = o.get("notes") or ""
        return _n.split("منتج: ")[-1].split(" — ")[0] if "منتج: " in _n else ""
    for r in sorted(_dw.list_receipts(year, month, cycle), key=lambda x: x["id"]):
        item = items.get(r["item_id"])
        if not item:
            continue
        parts = r["stores"] or [{"store_id": None, "store_name": UNASSIGNED,
                                 "qty": r["qty_handle"]}]
        for part in parts:
            pool.append({
                "item": item, "qty": float(part["qty"]),
                "remaining": float(part["qty"]),
                "expiry": r["exp_date"] or NO_EXPIRY,
                "order": f"{r['date_iso']}-{r['id']:05d}",
                "serial": r["serial"], "pack_label": r["pack_label"],
                "pack_kind": r["pack_kind"], "pack_count": r["pack_count"],
                "pack_capacity": r["pack_capacity"], "pack_loose": r["pack_loose"],
                "pack_inner_count": r["pack_inner_count"],
                "pack_inner_capacity": r["pack_inner_capacity"],
                "pack_inner_kind": r["pack_inner_kind"],
                "pack_loose_unit": r["pack_loose_unit"],
                "producer": r["producer"] or "", "notes": r["notes"] or "",
                "store_id": part["store_id"],
                "store_name": part["store_name"] or UNASSIGNED,
            })
    for o in openers:
        item = items.get(o["item_id"])
        if not item:
            continue
        parts = opener_parts.get(o["item_id"]) or [{"store_id": None, "store_name": UNASSIGNED, "qty": float(o["added"] or 0)}]
        for part in parts:
            pool.append({
                "item": item, "qty": float(part["qty"]),
                "remaining": float(part["qty"]),
                "expiry": o["exp_date"] or NO_EXPIRY,
                "order": f"{o['date_iso']}-00000",
                "serial": 0, "pack_label": o["pack_label"] or "",
                "pack_kind": "", "pack_count": 0,
                "pack_capacity": 0, "pack_loose": 0,
                "pack_inner_count": 0, "pack_inner_capacity": 0,
                "pack_inner_kind": "", "pack_loose_unit": "",
                "producer": _opener_producer(o),
                "store_id": part["store_id"],
                "store_name": part["store_name"] or UNASSIGNED,
            })
    pool.sort(key=lambda b: (b["expiry"], b["order"]))
    return pool


def _rem_label(batch, q, rest_word="سائب"):
    """تفكيك الكمية بعبوات الدفعة — الأرصدة بمفتوحة والمصروف بدونه."""
    return pack_breakdown(batch.get("pack_kind"), batch.get("pack_capacity"), batch.get("pack_inner_count"), batch.get("pack_inner_capacity"), q, batch["item"]["handle_unit"], rest_word, inner_kind=batch.get("pack_inner_kind")) or f"{arnum.fmt_qty_trim(q)} {batch['item']['handle_unit']}"


@months.memo
def tafreeda_rows(year, month, cycle):
    from data_access import db_warehouses as _dw   # استيراد مؤجل — تجنّب الدوران
    """التفريدة التلقائية: الأقرب صلاحية أولًا — لكل سطر التفكيك ورصيد المخزن كله قبل/بعد."""
    pool = _batch_pool(year, month, cycle)
    _seqs = {}                           # مسلسل السطر داخل التفريدة الواحدة
    store_bal = {}                       # رصيد المخزن كله (مجموع دفعات الصنف)
    for b in pool:
        _k = (b["item"]["name"], b["store_id"]); store_bal[_k] = round(store_bal.get(_k, 0.0) + b["qty"], 6)  # رصيد المخزن كله
    rows = []
    for permit in _dw.permits_book(year, month, cycle):
        for entry in permit["cycle_items"]:
            need = float(entry["qty"] or 0)
            if need <= 0:
                continue
            # كمية الإذن بوحدة المقرر (حاسبة/دفتر) والحوض المادي بوحدة التعامل —
            # التحويل من وحدة المقرر لوحدتها (الزيت: كجم ÷ 0.914 = لتر، توجيه ١٠/١٠)
            _hit = next((b["item"] for b in pool
                         if b["item"]["name"] == entry["name"]), None)
            if _hit:
                _r2h = _dw.ou.calc_to_handle_factor(
                    _hit.get("name"), _hit.get("ration_unit"),
                    _hit.get("handle_unit"), _hit.get("specific_weight"))
                if _r2h != 1.0:
                    need = need * _r2h
            for batch in pool:
                if need <= 0:
                    break
                if batch["item"]["name"] != entry["name"] or batch["remaining"] <= 0:
                    continue
                take = min(need, batch["remaining"])
                batch["remaining"] = round(batch["remaining"] - take, 6)
                need = round(need - take, 6)
                rows.append({
                    "pack_inner_label": "", "pack_outer_label": "",
                    "permit_no": permit["number"], "date_from": permit["date_from"], "date_to": permit["date_to"],
                    "item": batch["item"]["name"], "unit": batch["item"]["handle_unit"], "store_id": batch["store_id"],
                    "store_name": batch["store_name"], "receipt_serial": batch["serial"],
                    "expiry": batch["expiry"] if batch["expiry"] != NO_EXPIRY else "",
                    "qty": round(take, 6), "pack_label": batch["pack_label"],
                })
                _inner, _outer = pack_split(batch.get("pack_kind"), batch.get("pack_count"), batch.get("pack_capacity"), batch.get("pack_loose"), batch["item"]["handle_unit"], batch.get("pack_inner_count"), batch.get("pack_inner_capacity"), batch.get("pack_loose_unit"))
                rows[-1]["pack_inner_label"], rows[-1]["pack_outer_label"] = _inner, _outer
                rows[-1]["producer"] = batch.get("producer") or ""
                # «١ شكارة + ١٠ كجم» أو «٣٠ كجم» — المنصرف مُفكَّك بعبوات الدفعة
                rows[-1]["issued_label"] = _rem_label(batch, take, "")
                # رصيد المخزن كله قبل الصرف وبعده (اختيار المستخدم — مجموع الدفعات)
                _k = (batch["item"]["name"], batch["store_id"])
                store_bal[_k] = round(store_bal.get(_k, 0.0) - take, 6)
                rows[-1]["rem_before_label"] = _rem_label(batch, round(store_bal[_k] + take, 6)); rows[-1]["rem_after_label"] = _rem_label(batch, store_bal[_k])
                rows[-1]["seq"] = _seqs[permit["number"]] = _seqs.get(permit["number"], 0) + 1; rows[-1]["notes"] = user_notes(batch.get("notes"))
    return rows


@months.memo
def fefo_actual_map(year, month, cycle):
    """المنصرف الفعلي (FEFO) لكل (permit_no, item) — نفس ما استهلكه المخزن
    الفيزيائي من كل إذن. يُستخدم في دفتر ٣ مخازن عشان الدفتر يسجل الأفعال
    ويعلّم العجز صراحة (قرار الجولة ٣٤): الإذن بيرتكم كامل في ورقته، والدفتر
    ما بيطرحش غير اللي اتصرف فعلًا."""
    out = {}
    for r in tafreeda_rows(year, month, cycle):
        key = (r["permit_no"], r["item"])
        out[key] = round(out.get(key, 0.0) + float(r["qty"]), 6)
    return out


def stores_report(year, month):
    from data_access import db_warehouses as _dw   # استيراد مؤجل — تجنّب الدوران
    """حركة وكشف أرصدة كل مخزن — الدورتان معًا (المخازن والثلاجات موحدة لكل الأصناف)."""
    from data_access import db_stores
    from data_access import db_permits as _dp
    stores = db_stores.list_stores()
    # 🆕 (١٢/١٠) جهة/مندوب كل إذن صرف — عمودا «مصروف إلى» و«مندوب الجهة» في سجل الحركة
    permit_meta = {p["number"]: p for p in _dp.list_permits(year, month)}
    report = {s["id"]: {"store": s, "inn": [], "out": [],
                        "balances": {}, "pack_notes": {}, "total": 0.0} for s in stores}
    unassigned = {"store": {"id": None, "name": UNASSIGNED}, "inn": [], "out": [],
                  "balances": {}, "pack_notes": {}, "total": 0.0}
    specs = {}
    units = {}
    for _c in ("supply", "contractor"):
        specs.update(_dw.pack_specs_map(year, month, _c))
        for _it in _dw.list_items(year, month, _c):
            units[_it["name"]] = _it["handle_unit"]
    for cycle, cycle_name in (("supply", "الإمداد"), ("contractor", "المتعهد")):
        items = {it["id"]: it for it in _dw.list_items(year, month, cycle)}
        # رصيد أول المدة: كمية داخل موزعة على مخازنه (أو «غير موزع» بلا توزيع)
        conn = _dw._conn(year, month)
        openers = [dict(r) for r in conn.execute("SELECT * FROM wh_ledger WHERE cycle=? AND kind='opener'", (cycle,))]
        conn.close()
        opener_parts = _dw.opener_stores(year, month, cycle)
        for o in openers:
            item = items.get(o["item_id"])
            if not item or not (o["added"] or 0): continue
            for part in (opener_parts.get(o["item_id"]) or [
                    {"store_id": None, "store_name": UNASSIGNED,
                     "qty": float(o["added"])}]):
                target = report.get(part["store_id"], unassigned)
                qty = float(part["qty"] or 0)
                target["inn"].append({
                    "date_iso": o["date_iso"], "cycle": cycle_name,
                    "item": item["name"], "unit": item["handle_unit"],
                    "qty": qty, "pack_label": o["pack_label"] or "",
                    "serial": 0, "expiry": o["exp_date"] or "",
                })
                target["balances"][item["name"]] = \
                    target["balances"].get(item["name"], 0.0) + qty
        for r in _dw.list_receipts(year, month, cycle):
            item = items.get(r["item_id"])
            if not item:
                continue
            for part in (r["stores"] or [{"store_id": None, "store_name": UNASSIGNED,
                                          "qty": r["qty_handle"]}]):
                target = report.get(part["store_id"], unassigned)
                qty = float(part["qty"] or 0)
                target["inn"].append({
                    "date_iso": r["date_iso"], "day": r.get("day") or 0,
                    "cycle": cycle_name,
                    "item": item["name"], "unit": item["handle_unit"],
                    "qty": qty, "pack_label": r["pack_label"],
                    "serial": r["serial"], "expiry": r["exp_date"] or "",
                    "producer": (r.get("producer") or "").strip(), "supplier": (r.get("supplier_name") or "").strip(),
                })
                target["balances"][item["name"]] = \
                    target["balances"].get(item["name"], 0.0) + qty
        for row in tafreeda_rows(year, month, cycle):
            target = report.get(row["store_id"], unassigned)
            pe = permit_meta.get(row["permit_no"]) or {}
            target["out"].append({
                "date_iso": f"{year:04d}-{month:02d}-{int(row['date_from']):02d}",
                "cycle": cycle_name, "item": row["item"], "unit": row["unit"],
                "qty": row["qty"], "permit_no": row["permit_no"],
                "expiry": row["expiry"],
                "pack_label": row.get("issued_label") or row["pack_label"],
                # 🆕 (١٢/١٠) زي البرنامج القديم: الجهة المستلمة + مندوبها من إذن الصرف
                "entity": (pe.get("entity_label") or "").strip(),
                "receiver": ((pe.get("receiver_rank") or "") + " " +
                              (pe.get("receiver_name") or "")).strip(),
            })
            target["balances"][row["item"]] = \
                target["balances"].get(row["item"], 0.0) - row["qty"]
    all_targets = list(report.values()) + [unassigned]
    for target in all_targets:
        for item_name, qty in target["balances"].items():
            spec_entry = specs.get(item_name) or {}
            if not spec_entry or qty <= 0:
                continue
            # آخر مواصفات مسجلة للصنف (الأحدث تحديثًا) — بنوع تغليفها
            pack_kind = list(spec_entry)[-1]
            spec = spec_entry[pack_kind]
            note = pack_breakdown(pack_kind, spec.get("capacity"),
                                  spec.get("inner_count"), spec.get("inner_capacity"),
                                  qty, units.get(item_name, ""), inner_kind=spec.get("inner_kind"))
            if note:
                target["pack_notes"][item_name] = note
    for target in all_targets:
        target["inn"].sort(key=lambda x: (x["date_iso"], x.get("serial") or 0))
        target["out"].sort(key=lambda x: (x["date_iso"], x.get("permit_no") or 0))
        target["balances"] = {k: round(v, 6) for k, v in target["balances"].items()
                              if abs(v) > 1e-9}
        target["total"] = round(sum(target["balances"].values()), 6)
    # 🆕 (١٢/١٠) «رصيد المخزن (بعد)» لكل سطر + تسميات التغليف المختصرة —
    # الرصيد التراكمي للصنف في المخزن بترتيب التواريخ (الوارد قبل المنصرف في نفس اليوم)
    def _spec_of(name):
        entry = specs.get(name) or {}
        if not entry:
            return ("", 0, 0, 0, "")
        kind = list(entry)[-1]
        sp = entry[kind] or {}
        return (kind, sp.get("capacity") or 0, sp.get("inner_count") or 0,
                sp.get("inner_capacity") or 0, sp.get("inner_kind") or "")

    for target in all_targets:
        seq = ([(r["date_iso"] or "", 0, r) for r in target["inn"]] +
               [(r["date_iso"] or "", 1, r) for r in target["out"]])
        seq.sort(key=lambda t: (t[0], t[1]))
        run = {}
        in_tot = {}
        for _d, _k, r in seq:
            nm = r["item"]
            delta = float(r["qty"] or 0) if _k == 0 else -float(r["qty"] or 0)
            bal = round(run.get(nm, 0.0) + delta, 6)
            run[nm] = bal
            kind, cap, icnt, icap, ikind = _spec_of(nm)
            r["rem_qty"] = bal
            r["rem_after"] = (pack_breakdown(kind, cap, icnt, icap, bal,
                                             units.get(nm, ""), "",
                                             inner_kind=ikind)
                              if kind and bal else "")
            if _k == 0:
                in_tot[nm] = in_tot.get(nm, 0.0) + float(r["qty"] or 0)
                if kind:
                    r["pack_short"] = (pack_breakdown(kind, cap, icnt, icap,
                                                      float(r["qty"] or 0),
                                                      units.get(nm, ""), "",
                                                      inner_kind=ikind) or "")
        target["in_packs"] = {
            nm: pack_breakdown(*_spec_of(nm)[:4], round(q, 6), units.get(nm, ""),
                               "", inner_kind=_spec_of(nm)[4])
            for nm, q in in_tot.items() if _spec_of(nm)[0]}
    return {"stores": list(report.values()), "unassigned": unassigned}


def stores_general_report(year, month):
    """«كافة الأصناف (كشف عام)» (١٢/١٠) — كشف مجمّع لكل أصناف الشهر بكل المخازن:
    إجمالي داخل (تغليف + وحدة) · إجمالي خارج (وحدة) · الرصيد (تغليف + وحدة)."""
    rep = stores_report(year, month)
    from data_access import db_warehouses as _dw
    specs = {}
    units = {}
    for _c in ("supply", "contractor"):
        specs.update(_dw.pack_specs_map(year, month, _c))
        for _it in _dw.list_items(year, month, _c):
            units[_it["name"]] = _it["handle_unit"]
    agg = {}
    for target in rep["stores"] + [rep["unassigned"]]:
        for row in target["inn"]:
            agg.setdefault(row["item"], [0.0, 0.0])[0] += float(row["qty"] or 0)
        for row in target["out"]:
            agg.setdefault(row["item"], [0.0, 0.0])[1] += float(row["qty"] or 0)
    out = []
    for name, (inq, outq) in agg.items():
        inq, outq = round(inq, 6), round(outq, 6)
        bal = round(inq - outq, 6)
        entry = specs.get(name) or {}
        kind = list(entry)[-1] if entry else ""
        sp = (entry.get(kind) or {}) if kind else {}
        unit = units.get(name, "")
        ict = (sp.get("inner_count") or 0), (sp.get("inner_capacity") or 0)
        out.append({
            "name": name, "unit": unit, "in": inq, "out": outq, "balance": bal,
            "in_pack": (pack_breakdown(kind, sp.get("capacity"), ict[0], ict[1],
                                       inq, unit, "", inner_kind=sp.get("inner_kind"))
                        or "—"),
            "balance_pack": (pack_breakdown(kind, sp.get("capacity"), ict[0], ict[1],
                                            bal, unit, "", inner_kind=sp.get("inner_kind"))
                             or "—"),
        })
    out.sort(key=lambda r: (-r["balance"], r["name"]))
    return out


