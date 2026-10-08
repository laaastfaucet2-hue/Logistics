# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""حساب أسطر «٢ مخازن حرة» — نفس الآلية لكن بمعدلات التوزيع المستقلة.

القانون: الكمية = معدل الفرد اليومى × القوة × أيام الصرف — والمعدلات من جدول
التوزيع الحر (نسخة من معدلات الشهر + تعديلات المستخدم) وليس من أعمدة المخازن.
"""
from data_access import db_tameedat as dt
from services import permit_build as pb
from services import ration_lines as rl


def rows_for_picks_free(year, month, picks, day_from, day_to, issue_days,
                        section, rates):
    """rows جاهزة للعرض — rate = معدل التوزيع الحر (fallback: معدل الكتالوج)."""
    if section not in ("tamween", "contractor"):
        return []
    grouped = {}
    rates = rates.get(section) or {}
    for pick in picks:
        rec = dt.get_record(year, month, pick["record_id"])
        if not rec:
            continue
        valid = pb.issued_days_for_rec(rec, day_from, day_to, issue_days)
        if not valid:
            continue
        force = int(pick.get("officers") or 0) + int(pick.get("individuals") or 0) \
            + int(pick.get("recruits") or 0)
        items = rl.items_for_entity(year, month, pick["name"], section)
        for item in items:
            name = " ".join((item.get("name") or "").split())
            if not name:
                continue
            g = grouped.setdefault(name, {"unit": "", "days": set(),
                                          "force_days": 0, "catalog_rate": 0.0})
            g["days"] |= valid
            g["force_days"] += force * len(valid)
            if item.get("unit") and not g["unit"]:
                g["unit"] = item["unit"]
            if not g["catalog_rate"]:
                g["catalog_rate"] = rl.meal_sum(item)
    rows = []
    for i, name in enumerate(sorted(grouped)):
        g = grouped[name]
        free_rate = rates.get(name)
        rate = float(free_rate["rate"]) if free_rate else float(g["catalog_rate"])
        force_days = int(g["force_days"])
        auto = round(rate * force_days, 6)
        rows.append({"serial": i + 1, "name": name, "unit": g["unit"],
                     "rate": rate, "days": len(g["days"]), "force_days": force_days,
                     "auto": auto, "actual": auto})
    return rows


def all_rows_for_picks(year, month, picks, day_from, day_to, issue_days, rates):
    """{tamween: rows, contractor: rows} — للدفع للواجهة."""
    return {sec: rows_for_picks_free(year, month, picks, day_from, day_to,
                                     issue_days, sec, rates)
            for sec in ("tamween", "contractor")}
