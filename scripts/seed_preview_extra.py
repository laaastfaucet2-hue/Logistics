# -*- coding: utf-8 -*-
"""إكمال داتا العرض 2026/10 بعد seed_preview_demo:
صحة/مجندين · فواتير الدولى · دورة الترفية · مخازن فيزيائية.
التشغيل:  .venv/bin/python scripts/seed_preview_extra.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app

app = create_app()
with app.app_context():
    from data_access import database as db
    from data_access import db_recruits, db_attendance, db_health
    from data_access import db_stores, db_warehouses as dw, db_permits as dp
    from data_access import db_dowail as dwl
    from core import egtime
    from services import warehouses_fs

    db.init_db()
    year, month = 2026, 10
    db.set_user_context(1, year, month)

    # ── إعادة تشغيل آمنة: مسح ما زرعته الجولات السابقة من نفس السكربت ──
    from data_access import months
    conn = months.get_db(year, month)
    db_attendance.ensure_tables(conn)
    conn.execute("DELETE FROM attendance WHERE day IN (9, 10)")
    conn.commit()
    conn.close()
    for r in db_recruits.list_recruits(year, month):
        db_recruits.delete_recruit(year, month, r["id"])
    dwl.reset_month(year, month)
    for r in dw.list_receipts(year, month, "tarfea"):
        dw.delete_receipt(year, month, "tarfea", r["serial"])
    for r in dw.list_receipts(year, month, "supply"):
        if r.get("day") == 4 and (r.get("exp_date") or "") == "2026-11-20":
            dw.delete_receipt(year, month, "supply", r["serial"])

    # ═══ ١) المجندين + اليومية + كشف الصحة ═══
    rosters = [
        {"name": "محمد أحمد", "mil_no": "41001", "governorate": "السويس",
         "service_start": "2025-04-01", "service_end": "2026-03-31"},
        {"name": "أحمد علي", "mil_no": "41002", "governorate": "القاهرة",
         "service_start": "2025-04-01", "service_end": "2026-03-31"},
        {"name": "خالد سعد", "mil_no": "41003", "governorate": "الدقهلية",
         "service_start": "2025-04-01", "service_end": "2026-03-31",
         "has_cert": 1, "cert_date": "2025-10-19", "cert_expiry": "2026-10-19"},
    ]
    rids = []
    for data in rosters:
        rids.append(db_recruits.add_recruit(year, month, data))
    # يوم 9: الكل حاضر
    db_attendance.save_day(year, month, 9, [(r, "حضور", "") for r in rids], lock=True)
    # يوم 10: إجازة (الأولان) + المستشفى (الثالث)
    db_attendance.save_day(year, month, 10, [(rids[0], "إجازة", "تصريح مسبق"),
                                              (rids[1], "إجازة", "تصريح مسبق"),
                                              (rids[2], "مستشفى", "نزول مستشفى")], lock=True)
    db_health.set_days(year, month, [9])
    db_health.set_day_entries(year, month, 9,
                              [("محمد أحمد", rids[0])])
    db_health.set_fields(year, month, "spray", {"date_text": "2026-09-20"})
    print(f"✅ الصحة: {len(rids)} مجندين + يومية (9 حاضر / 10 إجازة+مستشفى) + كشف يوم 9")

    # ═══ ٢) فواتير الدولى: خطان + نقاط + معدلات التموين ═══
    north = dwl.add_line(year, month, "خط الشمال")
    south = dwl.add_line(year, month, "خط الجنوب")
    for line, pts in ((north, (("الفؤاد", 20), ("السلام", 15))),
                      (south, (("الحدود", 25),))):
        line_id = line if isinstance(line, int) else (line or {}).get("id")
        for name, force in pts:
            dwl.add_point(year, month, line_id, name, force)
    dwl.save_rate(year, month, "tamween", "أرز", 0.5, "كجم")
    dwl.save_rate(year, month, "tamween", "سكر", 0.2, "كجم")
    print("✅ الدولى: خط الشمال (الفؤاد ٢٠ + السلام ١٥) + خط الجنوب (الحدود ٢٥) + معدلان")

    # ═══ ٣) دورة الترفية: مورد + ٣ رسائل + إذن صرف ═══
    if not any(s["name"] == "مخزن التموين الرئيسي" for s in db_stores.list_stores()):
        db_stores.add_store("مخزن التموين الرئيسي", location="الساحة الرئيسية",
                            capacity_m2=150)
    if not any(s["name"] == "مخزن الترفية" for s in db_stores.list_stores()):
        db_stores.add_store("مخزن الترفية", location="المنطقة الترفيهية",
                            capacity_m2=80)
    if not any(s["name"] == "ثلاجة المؤن" for s in db_stores.list_stores()):
        db_stores.add_store("ثلاجة المؤن", location="المستودع الرئيسي",
                            capacity_m2=40, fans=2, extractors=1)
    all_stores = db_stores.list_stores()
    supply_store = next(s["id"] for s in all_stores if s["name"] == "مخزن التموين الرئيسي")
    supply_store_name = "مخزن التموين الرئيسي"
    fr_store = next(s["id"] for s in all_stores if s["name"] == "مخزن الترفية")
    fridge_store = next(s["id"] for s in all_stores if s["name"] == "ثلاجة المؤن")

    dw.add_supplier(year, month, "tarfea", "شركة المصايف", contact="م/ وليد",
                    phone="0111111111", activity="مواد ترفية")
    dw.add_receipt(year, month, "tarfea", 3, "غسيل", 60, handle_unit_hint="علبة",
                   supplier_name="شركة المصايف", producer="مصنع النظافة",
                   exp_iso="2027-05-01", stores=[(fr_store, "مخزن الترفية", 60)])
    dw.add_receipt(year, month, "tarfea", 3, "عصير", 120, handle_unit_hint="كرتونة",
                   supplier_name="شركة المصايف", producer="مصنع المذاق",
                   exp_iso="2026-12-15", stores=[(fr_store, "مخزن الترفية", 120)])
    dw.add_receipt(year, month, "tarfea", 9, "غسيل", 40, handle_unit_hint="علبة",
                   supplier_name="شركة المصايف", producer="مصنع النظافة",
                   exp_iso="2027-06-01", stores=[(fr_store, "مخزن الترفية", 40)])
    dp.save_permit(year, month, {
        "number": 20001, "fiscal_year": egtime.permit_fiscal_year(),
        "date_from": 6, "date_to": 6, "issue_days": 1, "mode": "box",
        "entity_label": "المنطقة الترفيهية",
        "officers": 2, "individuals": 10, "recruits": 0,
        "meals": ["breakfast", "lunch", "dinner"],
        "receiver_kind": "ضابط", "receiver_rank": "ملازم",
        "receiver_name": "الملازم أحمد خالد", "issuer_name": "أمين عهدة الترفية",
        "record_ids": [],
        "actuals": {"tarfea_غسيل": 35, "tarfea_عصير": 60},
    })
    warehouses_fs.snapshot_all(year, month)
    print("✅ الترفية: شركة المصايف + ٣ رسائل + إذن 20001 (غسيل ٣٥ / عصير ٦٠)")

    # توزيع رسالة إمداد على المخزنين (لحركة المخازن والثلاجات)
    sup_items = dw.list_items(year, month, "supply")
    if sup_items:
        rice = next((i for i in sup_items if "أرز" in i["name"]), sup_items[0])
        dw.add_receipt(year, month, "supply", 4, rice["name"], 400,
                       handle_unit_hint=rice.get("handle_unit") or "كجم",
                       supplier_name="شركة الإمداد المركزية", producer="مصنع الإنتاج الغذائي",
                       exp_iso="2026-11-20",
                       stores=[(supply_store, supply_store_name, 250),
                                (fridge_store, "ثلاجة المؤن", 150)])
        warehouses_fs.snapshot_all(year, month)
        print("✅ إمداد: رسالة أرز ٤٠٠ (يوم ٤، صلاحية ٢٠٦-١-٢٠) موزعة على المخزن الرئيسي")

    print("تم إكمال داتا العرض بنجاح.")
