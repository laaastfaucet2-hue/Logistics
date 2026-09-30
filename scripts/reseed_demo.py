# -*- coding: utf-8 -*-
"""بذر بيانات ٩/٢٠٢٦ التجريبية بعد إعادة بناء بيئة التشغيل — يستدعى مرة واحدة.

المصدر: داتا v103/v103+ المعتمدة (تونة ٥٠ علبة، ملح ١٠٠ على مخزن التموين،
١٣ إذن إمداد، ٣ متعهد، ٣ أذون ٢ مخازن، ١٤ مجند، ٥ تأميدات).
التشغيل:  .venv/bin/python scripts/reseed_demo.py
"""
import sys
sys.path.insert(0, "/home/user/Logistics")

from app import create_app

app = create_app()
with app.app_context():
    from data_access import months, database
    from data_access import db_stores, db_warehouses as dw
    from data_access import db_recruits, db_tameedat, db_tarfea as dt
    from data_access import db_permits
    from services import warehouses_fs as wf, tarfea_fs as tf
    from services import stores_fs, recruits_fs, document_refresh
    from services.tameedat_fs import snapshot_all as tameedat_snap
    from services.bootstrap import bootstrap_year_files

    from data_access import storage
    Y, M = 2026, 9
    database.init_db()
    if Y not in storage.list_years():
        storage.create_year(Y)
    bootstrap_year_files(Y)
    months.init_month(Y, M)
    database.set_user_context(1, Y, M)

    # ═══ ١) المخزن الفيزيائي: التموين ═══
    if not db_stores.list_stores():
        db_stores.add_store("مخزن التموين", location="الساحة الرئيسية", capacity_m2=200)
    supply_store = db_stores.list_stores()[0]
    print("مخازن:", [s["name"] for s in db_stores.list_stores()])

    # ═══ ٢) سجل الإمداد: ١٣ إذن إمداد + ملح افتتاحي ١٠٠ على التموين ═══
    supply_items = [
        ("ملح طعام", "شكارة", 50, 25, "شركة ملح الإسكندرية"),
        ("أرز", "شكارة", 30, 20, "شركة النيل للأغذية"),
        ("زيت طعام", "كرتونة", 40, 12, "شركة العبور للزيوت"),
        ("سكر", "شكارة", 45, 30, "مصنع الحواديتية"),
        ("شاي", "كرتونة", 25, 10, "شركة النيل العامة"),
        ("مكرونة", "كرتونة", 60, 20, "مكرونة مصر"),
        ("عدس", "شكارة", 20, 15, "شركة النيل للأغذية"),
        ("فول مدمس", "كرتونة", 35, 24, "شركة العامرية"),
        ("عصير مانجو", "كرتونة", 48, 12, "العبور للزيوت"),
        ("لبن", "كرتونة", 30, 27, "شركة البركة للألبان"),
        ("تمر", "كرتونة", 18, 10, "مصانع العروبة"),
        ("فول سوداني", "شكارة", 15, 10, "شركة النيل للأغذية"),
        ("ملينات", "كرتونة", 22, 12, "شركة فارما"),
    ]
    day = 1
    if not dw.list_receipts(Y, M, "supply"):
        for name, kind, cnt, inner, prod in supply_items:
            for kk in range(2):
                if day > 26:
                    break
                dw.add_receipt(Y, M, "supply", day, name, float(cnt * inner),
                               handle_unit_hint="كجم" if kind == "شكارة" else "وحدة",
                               producer=prod, supplier_name="الشركة المصرية للتوريدات",
                               date_iso="%04d-%02d-%02d" % (Y, M, day),
                               receipt_no=100 + day)
                day += 2
    print("إذون إمداد:", len(dw.list_receipts(Y, M, "supply")))

    _conn = months.get_db(Y, M)
    has_supply_opener = _conn.execute(
        "SELECT 1 FROM wh_ledger WHERE cycle='supply' AND kind='opener'").fetchone()
    _conn.close()
    if not has_supply_opener:
        dw.add_opener(Y, M, "supply", "ملح طعام", 100.0, 1,
                      handle_unit_hint="كجم",
                      producer="شركة ملح الإسكندرية",
                      supplier_name="الشركة المصرية للتوريدات",
                      date_iso="%04d-%02d-%02d" % (Y, M, 1),
                      exp_iso="%04d-09-01" % (Y + 1),
                      stores=[(supply_store["id"], supply_store["name"], 100.0)])
    print("ملح افتتاحي ١٠٠ على مخزن التموين ✓")

    # ═══ ٣) سجل المتعهد: ٣ أذون ═══
    contractor_items = [
        ("خضار وسوق", 120.0, "كجم", "مؤسسة الخير للخضار"),
        ("لحوم طازجة", 60.0, "كجم", "مذبح أهلًا"),
        ("خبز بلدي", 300.0, "رغيف", "مخبز الأمانة"),
    ]
    if not dw.list_receipts(Y, M, "contractor"):
        for i, (name, qty, unit, prod) in enumerate(contractor_items, 1):
            dw.add_receipt(Y, M, "contractor", i * 3, name, qty,
                           handle_unit_hint=unit, producer=prod,
                           supplier_name="متعهد الأعاشة",
                           date_iso="%04d-%02d-%02d" % (Y, M, i * 3),
                           receipt_no=200 + i)
    print("متعهد:", len(dw.list_receipts(Y, M, "contractor")))

    # ═══ ٤) الترفية: تونة (افتتاحي ١٠ علبة + إضافة ٤٨ كرتونتين + صرف ٨) ═══
    _conn = months.get_db(Y, M)
    has_tuna_opener = _conn.execute(
        "SELECT 1 FROM wh_ledger WHERE cycle='tarfea' AND kind='opener'").fetchone()
    _conn.close()
    if not has_tuna_opener:
        dw.add_opener(Y, M, "tarfea", "تونة", 10.0, 1,
                      handle_unit_hint="علبة",
                      producer="الشركة المصرية للحفظ",
                      supplier_name="الشركة المصرية للتوريدات",
                      date_iso="%04d-%02d-%02d" % (Y, M, 1),
                      exp_iso="%04d-09-01" % (Y + 2))
        dw.add_receipt(Y, M, "tarfea", 8, "تونة", 48.0,
                       handle_unit_hint="علبة",
                       producer="الشركة المصرية للحفظ",
                       supplier_name="شركة الترفية",
                       date_iso="%04d-%02d-%02d" % (Y, M, 8),
                       receipt_no=300, pack_kind="كرتونة", pack_count=2,
                       pack_inner_kind="علبة", pack_inner_count=24)
        tunas = [it for it in dt.list_items(Y, M) if it["name"] == "تونة"]
        dt.add_issue(Y, M, day=12, item_id=tunas[0]["id"], qty=8.0,
                     receiver="صالة الترفية", responsible="الرقيب أول محمد سيد",
                     notes="")
    print("تونة: opener ١٠ + إضافة ٤٨ + صرف ٨ ✓")

    # ═══ ٥) أذون ٢ مخازن (actuals ببادئة الدورة + اليوم رقم) ═══
    if not db_permits.list_permits(Y, M):
        permits = [
            (1, 10, "صالة الترفية", 8, 20, 6,
             {"tamween_ملح طعام": 4.0, "tamween_أرز": 6.0}),
            (2, 12, "الورشة", 2, 10, 3,
             {"tamween_سكر": 5.0, "tamween_شاي": 1.0}),
            (3, 15, "البوابة", 3, 12, 4,
             {"tamween_زيت طعام": 3.0, "tamween_مكرونة": 8.0}),
        ]
        for num, d, ent, off, ind, rec, actuals in permits:
            db_permits.save_permit(Y, M, {
                "number": num, "fiscal_year": Y,
                "date_from": d, "date_to": d + 2,
                "issue_days": 3, "mode": "manual", "entity_label": ent,
                "officers": "%d ضباط" % off, "individuals": "%d أفراد" % ind,
                "recruits": "%d مجندين" % rec,
                "meals": ["breakfast", "lunch", "dinner"],
                "receiver_kind": "وحدة", "receiver_rank": "ملازم أول",
                "receiver_name": ent, "issuer_name": "الرقيب أول محمد سيد",
                "record_ids": [], "actuals": actuals})
    print("أذون ٢ مخازن:", len(db_permits.list_permits(Y, M)))

    # ═══ ٦) المجندين: ١٤ مجند ═══
    names = ["أحمد محمود صابر", "محمد إبراهيم علي", "مصطفى كامل حسن",
             "كريم عبد الله فؤاد", "عمر حسين طنطاوي", "يوسف سامي مرسي",
             "إسلام ناصر عبد العال", "حمزة طلعت رشاد", "أيمن جمال شوقي",
             "شريف ممدوح عبده", "طارق منير سليم", "هاني عصام بدوي",
             "معتز سمير الخولي", "وليد فتحي عبد النبي"]
    have = {r["name"] for r in db_recruits.list_recruits(Y, M)}
    for i, nm in enumerate(names, 1):
        if nm in have:
            continue
        db_recruits.add_recruit(Y, M, {
            "name": nm, "mil_no": "%d/٢٠٢٦" % (1000 + i),
            "service_start": "2026-01-01", "service_end": "2027-12-31",
            "governorate": "القاهرة" if i % 2 else "الجيزة",
            "city": "مدينة نصر" if i % 2 else "الدقي",
            "address": "٢٤ شارع الترعة", "has_cert": 1 if i % 3 == 0 else 0,
            "cert_date": "2026-01-15" if i % 3 == 0 else "",
            "cert_expiry": "2026-07-15" if i % 3 == 0 else ""})
    print("مجندين: ١٤ ✓")

    # ═══ ٧) التأميدات: ٥ جهات + ٥ تأميدات ═══
    ents = [("صالة الترفية", "salon"), ("الورشة", "workshop"),
            ("البوابة", "gate"), ("المخازن", "store"), ("الصالة المغطاة", "hall")]
    ent_ids = []
    existing_ents = {e["name"]: e["id"] for e in db_tameedat.list_entities(Y, M)}
    for nm, tp in ents:
        if nm in existing_ents:
            ent_ids.append(existing_ents[nm])
        else:
            ent_ids.append(db_tameedat.add_entity(Y, M, nm, tp))
    days = [(2, 3, 8, 4), (5, 2, 6, 3), (8, 4, 10, 6), (12, 1, 5, 2), (20, 3, 7, 5)]
    have_days = {r["day"] for r in db_tameedat.month_records(Y, M)}
    for (d, off, ind, rec), eid in zip(days, ent_ids):
        if d in have_days:
            continue
        db_tameedat.add_record(Y, M, d, {"id": eid, "name": ents[ent_ids.index(eid)][0],
                                         "entity_type": ents[ent_ids.index(eid)][1]},
                               "%d ضباط" % off, "%d أفراد" % ind, "%d مجندين" % rec,
                               notes="تأميدة اعتيادية")
    print("تأميدات: ٥ ✓")

    # ═══ ٨) كل المرايا + الوورد ═══
    wf.ensure_folders(Y, M)
    tf.ensure_folders(Y, M)
    wf.snapshot_all(Y, M)
    tf.snapshot(Y, M)
    stores_fs.snapshot(Y, M)
    recruits_fs.snapshot_all(Y, M)
    tameedat_snap(Y, M)
    document_refresh.refresh_month(Y, M)
    print("كل المرايا والوورد ✓")
