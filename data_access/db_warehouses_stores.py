# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""المخازن الفيزيائية — التفريدة التلقائية (الأقرب صلاحية أولًا) وحركة المخازن.
انفصل عن db_warehouses بقاعدة ≤1000 سطر (نفس نمط db_pack): الاستدعاءات اللي
تحتاج من db_warehouses استيراد مؤجل جوه الدالة (تجنّب الدوران)."""
from core import arabic_numbers as arnum
from data_access import months
from data_access.packaging import pack_breakdown, pack_split, parse_pack_label, PackLedger

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
        # ملخص أول المدة بنفس صيغة pack_summary — يُفكَّك لحقول تغليف (١٤/١٠)
        # علشان الرصيد الافتتاحى يدخل حالة العبوات زي أي إضافة
        _oc, _ok, _ocap, _oloose = parse_pack_label(o.get("pack_label"))
        for part in parts:
            pool.append({
                "item": item, "qty": float(part["qty"]),
                "remaining": float(part["qty"]),
                "expiry": o["exp_date"] or NO_EXPIRY,
                "order": f"{o['date_iso']}-00000",
                "serial": 0, "pack_label": o["pack_label"] or "",
                "pack_kind": _ok, "pack_count": _oc,
                "pack_capacity": _ocap, "pack_loose": _oloose,
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


def _batch_ledger(batch):
    """مدير العبوات لدفعة واحدة (تغليف بالوزن فقط — ١٤/١٠):
    كاملة/سائب/باقي مفتوحة/سالب. الدفعات بلا تغليف (أو بعبوات بعدّ
    المعيار: جركن × ٢٠) ترجع None → السلوك القديم (تفكيك ساد)."""
    from core.config import is_measure_unit
    kind = (batch.get("pack_kind") or "").strip()
    cap = float(batch.get("pack_capacity") or 0)
    if not kind or cap <= 0 or is_measure_unit(kind):
        return None
    led = PackLedger(kind, cap, batch["item"]["handle_unit"])
    if float(batch.get("pack_count") or 0) > 0 or float(batch.get("pack_loose") or 0) > 0:
        led.add(batch.get("pack_count") or 0, batch.get("pack_loose") or 0)
    return led


def _leds_label(leds):
    """تسمية حالة مجموعة مدراء عبوات (مصدر واحد ١٤/١٠): نفس النوع يندمج
    في مدير واحد «٢ شكارة + شكارة مفتوحة (١٨ كجم)» وأنواع مختلفة تتجمع.
    الحالة الصفرية ترجع فاضي (زي تفكيك الأرصدة)."""
    real = [l for l in leds if l is not None]
    if not real:
        return ""
    if all(l.kind == real[0].kind for l in real):
        m = PackLedger(real[0].kind, real[0].capacity, real[0].unit)
        for l in real:
            m.full += l.full
            m.loose = round(m.loose + l.loose, 6)
            m.rest = round(m.rest + l.rest, 6)
            m.deficit = round(m.deficit + l.deficit, 6)
        if m.total() == 0 and m.deficit == 0:
            return ""
        return m.label()
    return " + ".join(l.label() for l in real)


def _state_label(batches):
    """رصيد مخزن صنف بالتغليف — من حالة العبوات الفعلية (مصدر واحد ١٤/١٠).
    دفعات قديمة بلا تغليف → تفكيك ساد على سعتها؛ الدفعات السادة البحتة
    (بلا أي معيار) تندمج في كمية واحدة «١٢٠٠ كجم» مش «٦٠ + ٦٠»."""
    parts = []
    leds = []
    plain_total = 0.0
    for b in batches:
        l = b.get("_led")
        rem = float(b.get("remaining") or 0)
        if l is not None:
            leds.append(l)
        elif rem > 0:
            if not (b.get("pack_kind") or "").strip():
                plain_total = round(plain_total + rem, 6)
            else:
                parts.append(_rem_label(b, rem, ""))
    if plain_total > 0:
        parts.append(f"{arnum.fmt_qty_trim(plain_total)} "
                     f"{batches[0]['item']['handle_unit']}")
    lbl = _leds_label(leds)
    if lbl:
        parts.append(lbl)
    return " + ".join(parts)


@months.memo
def tafreeda_rows(year, month, cycle):
    from data_access import db_warehouses as _dw   # استيراد مؤجل — تجنّب الدوران
    """التفريدة التلقائية: الأقرب صلاحية أولًا — لكل سطر التفكيك ورصيد المخزن كله قبل/بعد."""
    pool = _batch_pool(year, month, cycle)
    # مدير العبوات لكل دفعة — مصدر حالة التغليف الواحد (١٤/١٠): كل الشاشات
    # اللي تقرأ التفريدة (حركة المخازن / FEFO / الدفتر / xlsx) تقرأ الحالة
    # نفسها كاملة/مفتوحة/سائب — والكاملة ما تتحولش سائب (توجيه ٢٧/٠٩).
    for b in pool:
        b["_led"] = _batch_ledger(b)
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
                if take <= 0:
                    continue
                _k = (batch["item"]["name"], batch["store_id"])
                _group = [b for b in pool
                          if b["item"]["name"] == batch["item"]["name"] and b["store_id"] == batch["store_id"]]
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
                # رصيد المخزن كله قبل الصرف — من حالة العبوات الفعلية
                rows[-1]["rem_before_label"] = _state_label(_group)
                # المنصرف (تغليف) — من حالة الدفعة الفعلية: السائب أولًا ثم
                # الباقي المفتوح ثم فتح كاملة (٢٧/٠٩)؛ دفعة بلا تغليف → القديم
                led = batch.get("_led")
                if led is not None:
                    rows[-1]["issued_label"] = led.issued_label(led.take(take))
                else:
                    rows[-1]["issued_label"] = _rem_label(batch, take, "")
                batch["remaining"] = round(batch["remaining"] - take, 6)
                need = round(need - take, 6)
                store_bal[_k] = round(store_bal.get(_k, 0.0) - take, 6)
                rows[-1]["rem_after_label"] = _state_label(_group)
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
                # (١٤/١٠) مرجع سطر التفريدة — لإعادة تطبيق السحبة على الدفعة
                "_tref": row,
            })
            target["balances"][row["item"]] = \
                target["balances"].get(row["item"], 0.0) - row["qty"]
    all_targets = list(report.values()) + [unassigned]
    # (١٤/١٠) حالة العبوات لكل مخزن × صنف — نفس مصدر التفريدة: نبني خطًا
    # زمنيًا لكل مجموعة (كل وارد يزرع دفعتها، كل منصرف يسحب منها) — الرصيد
    # بالتغليف في كل سطر وفي كشف الأرصدة من الحالة الفعلية مش تفكيك ساد.
    _cyc_key = {"الإمداد": "supply", "المتعهد": "contractor"}
    _bidx, _groups = {}, {}
    for _c in ("supply", "contractor"):
        for _b in _batch_pool(year, month, _c):
            _bidx[(_c, _b["store_id"], _b["item"]["name"], _b["serial"])] = _b
            _groups.setdefault((_b["store_id"], _b["item"]["name"]), []).append(_b)
    _state_ok = {k: all(_batch_ledger(b) is not None for b in v)
                 for k, v in _groups.items()}
    _final_state = {}
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
        in_tot, out_tot = {}, {}
        _tid = (target.get("store") or {}).get("id")
        _gs = {}   # item -> {serial: PackLedger} — حالة مجموعة المخزن × الصنف
        for _d, _k, r in seq:
            nm = r["item"]
            delta = float(r["qty"] or 0) if _k == 0 else -float(r["qty"] or 0)
            bal = round(run.get(nm, 0.0) + delta, 6)
            run[nm] = bal
            kind, cap, icnt, icap, ikind = _spec_of(nm)
            r["rem_qty"] = bal
            if _state_ok.get((_tid, nm)):
                _st = _gs.setdefault(nm, {})
                if _k == 0:
                    _b = _bidx.get((_cyc_key.get(r.get("cycle"), ""), _tid, nm,
                                    int(r.get("serial") or 0)))
                    if _b is not None:
                        _st[_b["serial"]] = _batch_ledger(_b)
                else:
                    _led = _st.get((r.get("_tref") or {}).get("receipt_serial"))
                    if _led is not None:
                        _led.take(float(r.get("qty") or 0))
                r["rem_after"] = _leds_label(_st.values())
            else:
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
            else:
                out_tot[nm] = out_tot.get(nm, 0.0) + float(r["qty"] or 0)
                # ١٤/١٠: المنصرف بالتغليف (مثل الوارد) — إجمالي خارج مزدوج
                if kind:
                    r["pack_short"] = (pack_breakdown(kind, cap, icnt, icap,
                                                      float(r["qty"] or 0),
                                                      units.get(nm, ""), "",
                                                      inner_kind=ikind) or "")
        target["in_packs"] = {
            nm: pack_breakdown(*_spec_of(nm)[:4], round(q, 6), units.get(nm, ""),
                               "", inner_kind=_spec_of(nm)[4])
            for nm, q in in_tot.items() if _spec_of(nm)[0]}
        target["out_packs"] = {
            nm: pack_breakdown(*_spec_of(nm)[:4], round(q, 6), units.get(nm, ""),
                               "", inner_kind=_spec_of(nm)[4])
            for nm, q in out_tot.items() if _spec_of(nm)[0]}
        for _nm, _st in _gs.items():
            _final_state[(_tid, _nm)] = _st
    # كشف الأرصدة بالتغليف (١٤/١٠) — من نفس حالة العبوات (المصدر الواحد)،
    # والصنف القديم بلا تغليف بيتفكك ساد على آخر مواصفاته
    for target in all_targets:
        _tid = (target.get("store") or {}).get("id")
        for item_name, qty in target["balances"].items():
            if qty <= 0:
                continue
            _st = _final_state.get((_tid, item_name))
            if _st is not None:
                note = _leds_label(_st.values())
                if note:
                    target["pack_notes"][item_name] = note
                continue
            spec_entry = specs.get(item_name) or {}
            if not spec_entry:
                continue
            # آخر مواصفات مسجلة للصنف (الأحدث تحديثًا) — بنوع تغليفها
            pack_kind = list(spec_entry)[-1]
            spec = spec_entry[pack_kind]
            note = pack_breakdown(pack_kind, spec.get("capacity"),
                                  spec.get("inner_count"), spec.get("inner_capacity"),
                                  qty, units.get(item_name, ""), inner_kind=spec.get("inner_kind"))
            if note:
                target["pack_notes"][item_name] = note
    return {"stores": list(report.values()), "unassigned": unassigned}


def item_day_rows(inn_rows, out_rows, item_name, unit=""):
    """سطر لكل يوم فيه حركة على الصنف (توجيه ١٤/١٠) — مصدر واحد للشاشة والإكسل:
    داخل/خارج اليوم بالتغليف + المورد/المنتج + الرصيد التراكمي في نهاية اليوم.
    الصنف السادة (بلا تغليف) ما يظهرش «تغليف» — التسمية = الكمية بس."""
    moves = []
    for r in inn_rows:
        if r["item"] != item_name:
            continue
        moves.append({"dir": "in", "date": r.get("date_iso") or "",
                      "qty": float(r.get("qty") or 0),
                      "supplier": (r.get("supplier") or "").strip(),
                      "producer": (r.get("producer") or "").strip(),
                      "pack": r.get("pack_short") or r.get("pack_label") or "",
                      "rem_qty": r.get("rem_qty")})
    for r in out_rows:
        if r["item"] != item_name:
            continue
        moves.append({"dir": "out", "date": r.get("date_iso") or "",
                      "qty": float(r.get("qty") or 0),
                      "supplier": "", "producer": "",
                      "pack": r.get("pack_label") or r.get("pack_short") or "",
                      "rem_qty": r.get("rem_qty")})
    moves.sort(key=lambda m: (m["date"], m["dir"]))
    days = {}
    def _plain(q):
        return f"{arnum.fmt_qty_trim(float(q or 0))} {unit or ''}".strip()
    def _add_pack(cell, pack, qty):
        if not pack or pack == _plain(qty) or pack in cell:
            return cell
        return (cell + " + " + pack).strip(" +") if cell else pack
    for m in moves:
        key = m["date"]
        d = days.setdefault(key, {"date": key, "in": 0.0, "out": 0.0,
                                  "in_pack": "", "out_pack": "",
                                  "supplier": "", "producer": "",
                                  "balance": 0.0})
        if m["dir"] == "in":
            d["in"] = round(d["in"] + m["qty"], 6)
            if m["supplier"] and m["supplier"] not in d["supplier"]:
                d["supplier"] = (d["supplier"] + "، " + m["supplier"]).strip("، ")
            if m["producer"] and m["producer"] not in d["producer"]:
                d["producer"] = (d["producer"] + "، " + m["producer"]).strip("، ")
            d["in_pack"] = _add_pack(d["in_pack"], m["pack"], m["qty"])
        else:
            d["out"] = round(d["out"] + m["qty"], 6)
            d["out_pack"] = _add_pack(d["out_pack"], m["pack"], m["qty"])
        if m.get("rem_qty") is not None:
            d["balance"] = float(m["rem_qty"])   # آخر سطر في اليوم = رصيد نهاية اليوم
    return list(days.values())


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
            # ١٤/١٠: إجمالي خارج بالتغليف كمان (المزدوجة على كل الأعمدة)
            "out_pack": (pack_breakdown(kind, sp.get("capacity"), ict[0], ict[1],
                                        outq, unit, "", inner_kind=sp.get("inner_kind"))
                         or "—"),
            "balance_pack": (pack_breakdown(kind, sp.get("capacity"), ict[0], ict[1],
                                            bal, unit, "", inner_kind=sp.get("inner_kind"))
                             or "—"),
        })
    out.sort(key=lambda r: (-r["balance"], r["name"]))
    return out


