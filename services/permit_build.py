# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""قائمة التأميدات (كل جهة لوحدها) وجدول الكميات للأذون."""
from core import arabic_numbers as arnum
from data_access import db_tameedat as dt
from data_access import db_tameed_rations as snap
from services import ration_lines as rl

PALETTE = 6


def overlapping_records(year, month, day_from, day_to):
    seen = {}
    for day in range(int(day_from), int(day_to) + 1):
        for rec in dt.records_for_day(year, month, day):
            seen[rec["id"]] = rec
    return sorted(seen.values(), key=lambda r: (int(r["day"]), int(r["id"])))


def _range_label(day, day_to):
    if day == day_to:
        return f"يوم {arnum.to_arabic_indic(day)} فقط"
    return (f"من {arnum.to_arabic_indic(day)} إلى {arnum.to_arabic_indic(day_to)}"
            f" ({arnum.to_arabic_indic(day_to - day + 1)} أيام)")


def date_label(year, month, day):
    return (f"يوم {arnum.to_arabic_indic(day)}/"
            f"{arnum.to_arabic_indic(month)}/"
            f"{arnum.to_arabic_indic(year)}")


def rec_span(rec):
    start = int(rec["day"])
    end = int(rec.get("day_to") or rec["day"])
    if end < start:
        end = start
    return start, end


def entity_picks(records):
    """كل جهة رئيسية وكل ملحقة سطر مستقل — مجمّعة بصريًا حسب التأميدة واليوم."""
    picks = []
    ordered = sorted(records, key=lambda r: (int(r["day"]), int(r["id"])))
    for rec in ordered:
        rid = rec["id"]
        day, day_to = rec_span(rec)
        color = (int(rid) - 1) % PALETTE
        meta = {
            "record_id": rid, "day": day, "day_to": day_to, "color": color,
            "group_title": rec["entity_name"],
            "range_label": _range_label(day, day_to),
        }
        picks.append({
            **meta, "key": f"main:{rid}", "name": rec["entity_name"],
            "kind": "رئيسية", "label": rec["entity_name"],
            "officers": rec["officers"], "individuals": rec["individuals"],
            "recruits": rec["recruits"], "is_attachment": False, "target": "main",
        })
        for att in rec.get("attachments") or []:
            picks.append({
                **meta, "key": f"att:{rid}:{att['name']}", "name": att["name"],
                "kind": "ملحقة", "label": f"{att['name']} (ملحقة — {rec['entity_name']})",
                "officers": att["officers"], "individuals": att["individuals"],
                "recruits": att["recruits"], "is_attachment": True, "target": att["name"],
            })
    return picks


def pick_groups(year, month, picks):
    """أيام ثم مربعات تأميدة (رئيسية + ملحقاتها) بلون مميز."""
    groups, index = [], {}
    for pick in picks:
        day = pick["day"]
        if day not in index:
            block = {"day": day, "label": date_label(year, month, day), "tameedat": []}
            index[day] = block
            groups.append(block)
        tms = index[day]["tameedat"]
        rid = pick["record_id"]
        tm = next((t for t in tms if t["record_id"] == rid), None)
        if not tm:
            tm = {
                "record_id": rid, "title": pick["group_title"], "color": pick["color"],
                "range_label": pick["range_label"], "day": pick["day"],
                "day_to": pick["day_to"], "picks": [],
            }
            tms.append(tm)
        tm["picks"].append(pick)
    return groups


def pick_by_key(picks, key):
    return next((p for p in picks if p["key"] == key), None)


def issued_days_for_rec(rec, day_from, day_to, issue_days):
    """أيام الصرف = تقاطع نافذة الإذن مع مدة التأميدة — لا تتجاوز أيامها."""
    start, end = int(day_from), int(day_to)
    if end < start:
        end = start
    span = max(1, int(issue_days or (end - start + 1)))
    window = set(range(start, min(start + span, end + 1)))
    r0, r1 = rec_span(rec)
    return window & set(range(r0, r1 + 1))


def rows_for_picks(year, month, picks, day_from, day_to, issue_days, section):
    """كمية الصنف = مجموع (مقرر الجهة × قوتها × أيام صرفها داخل مدة تأميدتها)."""
    grouped = {}
    for pick in picks:
        rec = dt.get_record(year, month, pick["record_id"])
        if not rec:
            continue
        valid = issued_days_for_rec(rec, day_from, day_to, issue_days)
        if not valid:
            continue
        force = pick["officers"] + pick["individuals"] + pick["recruits"]
        payload = snap.get_payload(year, month, rec["id"])
        over = rl.overrides_map(payload, pick["target"], section)
        lines = rl.build_lines(
            year, month, pick["name"], section, min(valid), max(valid), over)
        for line in lines:
            if line["day"] not in valid or not line["on"]:
                continue
            orig = line.get("orig") or {}
            used = line.get("used") or orig
            bucket = grouped.setdefault(line["name"], {
                "name": line["name"], "unit": line["unit"], "dayset": set(),
                "auto": 0.0, "per_person": 0.0,
                "breakfast": orig.get("breakfast") or 0.0,
                "lunch": orig.get("lunch") or 0.0,
                "dinner": orig.get("dinner") or 0.0,
                "customized": False,
                "custom_breakfast": orig.get("breakfast") or 0.0,
                "custom_lunch": orig.get("lunch") or 0.0,
                "custom_dinner": orig.get("dinner") or 0.0,
            })
            bucket["dayset"].add(line["day"])
            bucket["auto"] += force * float(line["qty"] or 0)
            bucket["per_person"] = float(line["qty"] or 0)
            bucket["unit"] = line["unit"] or bucket["unit"]
            bucket["breakfast"] = orig.get("breakfast") or 0.0
            bucket["lunch"] = orig.get("lunch") or 0.0
            bucket["dinner"] = orig.get("dinner") or 0.0
            if line.get("customized"):
                bucket["customized"] = True
                bucket["custom_breakfast"] = used.get("breakfast") or 0.0
                bucket["custom_lunch"] = used.get("lunch") or 0.0
                bucket["custom_dinner"] = used.get("dinner") or 0.0
    rows = []
    for i, item in enumerate(grouped.values(), start=1):
        rows.append({
            "serial": i, "name": item["name"], "unit": item["unit"],
            "per_person": item["per_person"], "days": len(item["dayset"]),
            "auto": item["auto"],
            "breakfast": item["breakfast"], "lunch": item["lunch"],
            "dinner": item["dinner"], "customized": item["customized"],
            "custom_breakfast": item["custom_breakfast"],
            "custom_lunch": item["custom_lunch"],
            "custom_dinner": item["custom_dinner"],
        })
    return rows
