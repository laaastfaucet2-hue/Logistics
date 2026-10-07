# -*- coding: utf-8 -*-
"""بذر بيانات تجريبية لمعاينة Arena فقط — جهات مومدة في التاميدات والمقررين.

⚠️ لا يعمل إلا بموافقة صريحة: شغّله بـ LOGISTICS_SEED_DEMO=1
   (حماية لبيانات المستخدم الحقيقية على جهازه — بلا المتغير ده السكربت يرفض العمل).

ما يزرعه (كلّه في الشهر النشط فقط، ولا يمسّ أي شهر آخر):
  1) «التاميدات»: قاموس جهات (شرطية/حربية/مدنية) + تأميدات موزعة على الشهر
     مع مدة زمنية (من يوم/إلى يوم) وجهات ملحقة وسجلات متعددة في نفس اليوم
     وأرقام راغبين لتظهر شاشة التنبيه.
  2) «المقررات التمونيية» و«مقررات المتعهد»: تفعيل مقرر + أصناف بأرقامها
     + نفس الجهات المومدة مسحوبةً لها الأصناف من المقرر النشط.
  3) مرايا الملفات المحلية (JSON + Excel) عبر نفس دوال الحفظ الرسمية.

التشغيل:
    LOGISTICS_SEED_DEMO=1 .venv/bin/python scripts/seed_preview_demo.py
    LOGISTICS_SEED_DEMO=1 .venv/bin/python scripts/seed_preview_demo.py --reset
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if os.environ.get("LOGISTICS_SEED_DEMO") != "1":
    print("مرفوض: هذا السكربت لبذر بيانات تجريبية في معاينة معزولة فقط.")
    print("شغّله هكذا لو أنت متأكد:  LOGISTICS_SEED_DEMO=1 python scripts/seed_preview_demo.py")
    raise SystemExit(1)

from core.paths import DATA_DIR  # noqa: E402

print(f"مجلد البيانات المستهدف: {DATA_DIR}")

from app import create_app  # noqa: E402

app = create_app()

# ══════════════════════════════════════════════════════════════════════
# بيانات البذر — الشهر النشط فقط
# ══════════════════════════════════════════════════════════════════════
# (الاسم، النوع، راغبين ضباط، راغبين أفراد، ملاحظات)
ENTITIES = [
    ("قطاع الشهيد أشرف جاد", "شرطية", 12, 40, "القطاع الرئيسي"),
    ("قسم شرطة نخل", "شرطية", 6, 24, ""),
    ("قسم شرطة الحسنة", "شرطية", 5, 20, ""),
    ("إدارة مرور وسط سيناء", "شرطية", 4, 16, ""),
    ("الحماية المدنية بوسط سيناء", "شرطية", 3, 14, ""),
    ("كتيبة الأمن المركزي ٢١٤", "حربية", 8, 45, ""),
    ("مستشفى سيناء العام", "مدنية", 2, 8, "جهة مدنية"),
]

# (اليوم، اسم الجهة، ضباط، أفراد، مجندين، ملاحظات، يوم النهاية أو None، الملحقات)
RECORDS = [
    (1, "قطاع الشهيد أشرف جاد", 10, 25, 8, "تأميدة بداية الشهر", 3,
     [("قسم شرطة نخل", "شرطية", 3, 10, 0)]),
    (2, "قسم شرطة الحسنة", 4, 18, 0, "", None, []),
    (3, "إدارة مرور وسط سيناء", 3, 12, 2, "", None,
     [("الحماية المدنية بوسط سيناء", "شرطية", 2, 6, 0)]),
    (5, "قطاع الشهيد أشرف جاد", 8, 22, 6, "مدة زمنية أسبوع", 9,
     [("مستشفى سيناء العام", "مدنية", 1, 4, 0)]),
    (8, "كتيبة الأمن المركزي ٢١٤", 6, 30, 12, "", None, []),
    (12, "قسم شرطة الحسنة", 7, 20, 0, "أعداد أكبر من أرقام الراغبين — تنبيه", None, []),
    (15, "قسم شرطة نخل", 5, 20, 4, "", None, []),
    (22, "قطاع الشهيد أشرف جاد", 10, 25, 8, "تأميدة ثانية لنفس الجهة", None, []),
    (22, "مستشفى سيناء العام", 2, 6, 0, "سجل مستقل في نفس اليوم", None, []),
    (28, "الحماية المدنية بوسط سيناء", 3, 10, 4, "", 30,
     [("إدارة مرور وسط سيناء", "شرطية", 1, 5, 0)]),
]

# أصناف المقرر — (الاسم، الوحدة، فطار، غداء، عشاء)
TAMWEEN_ITEMS = [
    ("أرز", "كجم", 0.150, 0.200, 0.150),
    ("مكرونة", "كجم", 0.100, 0.150, 0.100),
    ("سكر", "كجم", 0.020, 0.030, 0.020),
    ("زيت طعام", "لتر", 0.010, 0.015, 0.010),
    ("شاي", "جم", 5, 5, 5),
    ("ملح طعام", "جم", 5, 8, 5),
    ("فول مدمس", "علبة", 0, 1, 0),
    ("صلصة", "علبة", 0, 1, 0),
]
CONTRACTOR_ITEMS = [
    ("خبز", "رغيف", 3, 3, 3),
    ("لحوم", "كجم", 0, 0.200, 0.150),
    ("دواجن", "كجم", 0, 0, 0.200),
    ("خضروات", "كجم", 0, 0.150, 0.100),
    ("فواكه", "كجم", 0.150, 0, 0),
    ("أرز معدة", "كجم", 0, 0.200, 0.150),
]

SECTIONS = (("tamween", TAMWEEN_ITEMS), ("contractor", CONTRACTOR_ITEMS))

# ══════════════════════════════════════════════════════════════════════
# قوة «الجهات والكوادر المعتمدة» + راغبو الأيام — ليعمل جدول التنبيهات
# ══════════════════════════════════════════════════════════════════════
# (عدد الضباط، عدد الأفراد) لكل جهة — أسماء حقيقية الشكل تُبنى من القوائم تحت
FORCE_PLAN = {
    "قطاع الشهيد أشرف جاد": (12, 28),
    "قسم شرطة نخل": (6, 22),
    "قسم شرطة الحسنة": (8, 22),
    "إدارة مرور وسط سيناء": (4, 14),
    "الحماية المدنية بوسط سيناء": (4, 12),
    "كتيبة الأمن المركزي ٢١٤": (7, 32),
}

OFFICER_RANKS = ["مقدم", "رائد", "نقيب", "ملازم أول", "ملازم"]
INDIVIDUAL_RANKS = ["مساعد أول", "مساعد", "رقيب أول", "رقيب", "عريف", "جندي أول", "جندي"]

# أسماء أولى وكُنى عربية واقعية — تُركَّب بالترتيب فيُنتج كل جهة أسماء مميزة
FIRST_NAMES = ["محمد", "أحمد", "مصطفى", "إبراهيم", "خالد", "محمود", "عبدالله", "يوسف",
               "علاء", "هشام", "سامح", "وليد", "طارق", "ناصر", "رامي", "شريف",
               "عمرو", "كريم", "أيمن", "سيد", "ماجد", "جمال", "حسن", "عادل"]
FAMILIES = ["عبدالحميد", "نصرالله", "العجرودى", "السيد", "الشريف", "رمضان", "سالم",
            "الجزار", "الفقي", "منصور", "حجازي", "عبدالعال", "الشوربجي", "زكي",
            "الألفي", "بدوي", "قنديل", "عوض", "الحلواني", "دراز"]

# (اليوم، الجهة): (عدد راغبي الضباط، عدد راغبي الأفراد) — اليوم الغائب = تنبيه «مفيش راغب»
WILLING_PLAN = {
    (1, "قطاع الشهيد أشرف جاد"): (10, 25),      # مطابق تمامًا ✔
    (2, "قطاع الشهيد أشرف جاد"): (10, 25),
    (3, "قطاع الشهيد أشرف جاد"): (10, 25),
    (5, "قطاع الشهيد أشرف جاد"): (8, 22),       # مطابق
    (8, "قطاع الشهيد أشرف جاد"): (8, 12),       # نقص واضح في الأفراد
    (2, "قسم شرطة الحسنة"): (4, 12),            # نقص في الأفراد
    (12, "قسم شرطة الحسنة"): (7, 20),           # مطابق
    (3, "إدارة مرور وسط سيناء"): (3, 12),       # مطابق
    (8, "كتيبة الأمن المركزي ٢١٤"): (6, 30),    # مطابق
    (15, "قسم شرطة نخل"): (5, 20),              # مطابق
    (28, "الحماية المدنية بوسط سيناء"): (3, 10),
    (29, "الحماية المدنية بوسط سيناء"): (3, 10),
    (30, "الحماية المدنية بوسط سيناء"): (3, 10),
}


def _person_name(seq, genderless_offset=0):
    """اسم رباعي ثابت من القوائم — بلا تكرار داخل الجهة (بالترقيم)."""
    first = FIRST_NAMES[(seq + genderless_offset) % len(FIRST_NAMES)]
    middle = FIRST_NAMES[(seq * 3 + 1) % len(FIRST_NAMES)]
    family = FAMILIES[(seq * 7 + 2) % len(FAMILIES)]
    tail = FAMILIES[(seq * 5 + 3) % len(FAMILIES)]
    return f"{first} {middle} {family} {tail}"


def _seed_force(year, month):
    """قوة كل جهة بالأسماء والرتب + راغبو الأيام — من دوال الطبقة الرسمية فقط."""
    from data_access import db_raghibin as rp
    from data_access import db_tameedat as dt

    entities = {e["name"]: e for e in dt.list_entities(year, month)}
    persons = {}          # (entity_name, category) -> [person_id]
    for entity_name, (officers, individuals) in FORCE_PLAN.items():
        entity = entities.get(entity_name)
        if not entity:
            continue
        for category, count, ranks, offset in (
                ("officers", officers, OFFICER_RANKS, 0),
                ("individuals", individuals, INDIVIDUAL_RANKS, 11)):
            ids = []
            for seq in range(count):
                person_id, _created = rp.add_person(
                    year, month, entity["id"], category, _person_name(seq, offset),
                    rank=ranks[seq % len(ranks)])
                ids.append(person_id)
            persons[(entity_name, category)] = ids
    # راغبو الأيام: أول N من كل فئة (بالأقدمية كما تظهر في الشاشة)
    for (day, entity_name), (willing_o, willing_i) in WILLING_PLAN.items():
        for category, count in (("officers", willing_o), ("individuals", willing_i)):
            ids = persons.get((entity_name, category), [])
            for person_id in ids[:count]:
                rp.set_daily(year, month, person_id, day, 1, source="seed")
    print(f"✅ الكوادر والراغبون: {sum(len(v) for v in persons.values())} اسمًا، "
          f"و{len(WILLING_PLAN)} تسجيل يومي")
    return persons


def _rebuild_raghibin_files(year, month, persons):
    """مرايا الراغبين المحلية: ملف كل جهة في يومها + الكوادر + عدم الراغبين + التجميع."""
    from data_access import db_raghibin as rp
    from services.raghibin import files_daily, files_monthly, files_rosters
    from services import raghibin as rp_rfs

    days = {}
    for (day, entity_name) in WILLING_PLAN:
        days.setdefault(entity_name, set()).add(day)
    written = 0
    for entity_name, day_set in days.items():
        people = rp.list_persons(year, month)
        entity_id = next((p["entity_id"] for p in people if p["entity_name"] == entity_name), None)
        if not entity_id:
            continue
        for day in sorted(day_set):
            files_daily.write_day_file(year, month, day, entity_id, entity_name)
            written += 1
        files_monthly.write_monthly_file(year, month, entity_id, entity_name)
        files_rosters.write_excluded_files(year, month, entity_id, entity_name)
    cadres = rp_rfs.write_all_cadres(year, month)      # ملفات القوة (ضباط/أفراد) لكل جهة
    print(f"📄 ملفات الراغبين المحلية: {written} ملف يوم/جهة + ملفات الكوادر والتجميع")
    return written, cadres


def _reset(year, month):
    """يمسح ما زرعه هذا السكربت في الشهر المستهدف فقط — ذرّيًا."""
    from data_access import db_entities as de
    from data_access import db_rations as dr
    from data_access import db_tameedat as dt
    from data_access import months

    for entity in dt.list_entities(year, month):
        dt.delete_entity(year, month, entity["id"])   # يحذف أسماء الراغبين معها (CASCADE)
    for section, _ in SECTIONS:
        for entity in de.list_entities(year, month, section):
            de.delete_entity(year, month, entity["id"])
        for kind in ("summer", "winter", "ramadan"):
            for item in dr.get_items(year, month, section, kind)[0]:
                dr.delete_item(year, month, item["id"])
        conn = months.get_db(year, month)
        conn.execute("DELETE FROM ration_activation WHERE section=?", (section,))
        conn.commit()
        conn.close()
    print("↺ أُعيد ضبط الشهر المستهدف (تاميدات + مقررات القسمين)")


def _seed_tameedat(year, month):
    from data_access import db_tameedat as dt

    ids = {}
    for name, kind, rag_o, rag_i, notes in ENTITIES:
        ids[name] = dt.add_entity(year, month, name, kind, rag_o, rag_i, notes)
    for day, entity_name, officers, individuals, recruits, notes, day_to, atts in RECORDS:
        entity = dt.get_entity(year, month, ids[entity_name])
        attachments = [{"name": a[0], "entity_type": a[1],
                        "officers": a[2], "individuals": a[3], "recruits": a[4]}
                       for a in atts]
        for att in atts:                      # الملحقة جهة كاملة في القاموس أيضًا
            if not dt.find_entity_by_name(year, month, att[0]):
                dt.add_entity(year, month, att[0], att[1])
        dt.add_record(year, month, day, entity, officers, individuals, recruits,
                      notes, attachments, day_to=day_to)
    print(f"✅ التاميدات: {len(ENTITIES)} جهة في القاموس و{len(RECORDS)} تأميدة")


def _seed_rations(year, month):
    from data_access import db_entities as de
    from data_access import db_rations as dr

    for section, items in SECTIONS:
        dr.set_activation(year, month, section, "summer")
        for name, unit, breakfast, lunch, dinner in items:
            dr.add_item(year, month, section, "summer", name, unit,
                        breakfast, lunch, dinner)
            dr.remember_unit(unit)
        added = 0
        for name, _, _, _, _ in ENTITIES:
            count, _kind = de.add_entity(year, month, section, name)
            added += 1 if count else 0
        # تخصيص أيام لصنفين: يظهران يومين محددين فقط (٢ = الاثنين، ٤ = الأربعاء)
        entities = de.list_entities(year, month, section)
        for entity in entities:
            for item in entity["items"]:
                key = item["name"].strip()
                if key in ("دواجن", "فول مدمس"):
                    de.set_days(year, month, item["id"], {2: item["dinner"] or 0.200,
                                                          4: item["dinner"] or 0.200})
        print(f"✅ {section}: {len(items)} صنفًا و{added} جهة مسحوبة من المقرر الصيفي")


def _seed_warehouses(year, month):
    """مستودعات وسجلات: موردون + أرصدة أول المدة بالتغليف + أذون صرف بتفريدتها.

    يجعل تاب «٢ مخازن تفاريد» وأعمدة «الرصيد المتوفر بالمخازن / الحالة الكلية للرصيد»
    في آلة حاسبة ٢ مخازن تعرض أرقامًا حقيقية في المعاينة.
    """
    from data_access import db_permits as dp, db_warehouses as dw, db_tameedat as dt
    from core import egtime

    for cycle, supplier in (("supply", "شركة الإمداد المركزية"),
                            ("contractor", "مورد المتعهد — دواجن سيناء")):
        dw.add_supplier(year, month, cycle, supplier, contact="مقدم/ مسؤول التوريد",
                        phone="0100000000", activity="توريد مواد غذائية")
    # أسماء التغليف بأسماء أصناف المقرر نفسها (قاعدة: لا صنف خارج المقرر)
    pack_plan = {"أرز": ("شكارة", 50.0), "سكر": ("شكارة", 50.0),
                 "مكرونة": ("كرتونة", 10.0), "زيت طعام": ("جركن", 20.0),
                 "شاي": ("كرتونة", 5.0), "ملح طعام": ("شكارة", 25.0),
                 "فول مدمس": ("كرتونة", 12.0), "صلصة": ("كرتونة", 12.0),
                 "خبز": ("كرتونة", 20.0), "لحوم": ("كرتونة", 10.0),
                 "دواجن": ("كرتونة", 10.0), "خضروات": ("شكارة", 20.0),
                 "فواكه": ("شكارة", 20.0), "أرز معدة": ("شكارة", 25.0)}
    seeded_items = 0
    for cycle in ("supply", "contractor"):
        for item in dw.ration_catalog(year, month, cycle):
            name, unit = item["name"], item["unit"] or "كجم"
            pack_kind, capacity = pack_plan.get(name.strip(), ("بدون تغليف", 0.0))
            qty = 300.0 if pack_kind == "بدون تغليف" else capacity * 6
            if dw.has_opener(year, month, (dw.resolve_item(year, month, cycle, name, unit) or
                                           ({}, False))[0].get("id")):
                seeded_items += 1         # رصيد موجود من بذر سابق
                continue
            try:
                dw.add_opener(year, month, cycle, name, qty, 1, handle_unit_hint=unit,
                              exp_iso=egtime.today().replace(year=year + 1).isoformat(),
                              producer="مصنع الإنتاج الغذائي",
                              pack_kind=pack_kind, pack_count=6 if capacity else 0,
                              pack_capacity=capacity)
                seeded_items += 1
            except ValueError:
                continue        # صنف له رصيد مسجّل بالفعل (إعادة بذر)
    # أذون صرف مرتبطة بتأميدات الشهر ⇒ تظهر تفريدتها (FEFO) في تاب ٢ مخازن تفاريد
    records = dt.month_records(year, month)
    permits = 0
    if records:
        for index, rec in enumerate(records[:3], start=1):
          for cycle, section in (("supply", "tamween"), ("contractor", "contractor")):
            entity = dt.get_entity(year, month, rec["entity_id"]) or {}
            catalog = dw.ration_catalog(year, month, cycle)
            actuals = {f"{section}_{it['name']}": round(float(rec["officers"] + rec["individuals"])
                                                        * 0.100, 3)
                       for it in catalog[:4]}
            if not actuals:
                continue
            dp.save_permit(year, month, {
                "number": index if cycle == "supply" else index + 100,
                "fiscal_year": egtime.permit_fiscal_year(),
                "date_from": rec["day"], "date_to": rec.get("day_to") or rec["day"],
                "issue_days": 1, "mode": "box",
                "entity_label": entity.get("name") or rec["entity_name"],
                "officers": rec["officers"], "individuals": rec["individuals"],
                "recruits": rec["recruits"], "meals": ["breakfast", "lunch", "dinner"],
                "receiver_kind": "مندوب الجهة", "receiver_rank": "رائد",
                "receiver_name": "مندوب استلام", "issuer_name": "أمين عهدة ٢ مخازن",
                "record_ids": [rec["id"]], "actuals": actuals,
            })
            permits += 1
    from services import warehouses_fs
    warehouses_fs.snapshot_all(year, month)
    print(f"✅ المستودعات: {seeded_items} صنفًا برصيد افتتاحي و{permits} إذن صرف "
          f"(التفريدة وملفات ٢ مخازن اتحدثت)")


def _rebuild_files(year, month):
    from documents import xlsx_rations
    from services import tameedat_fs

    tameedat_fs.snapshot_all(year, month)
    for section, _ in SECTIONS:
        xlsx_rations.rebuild(year, month, section)
    print("📄 مرايا الملفات المحلية (JSON + Excel) اتحدثت")


def main():
    from data_access import database as db, months

    args = sys.argv[1:]
    with app.app_context():
        db.init_db()
        context = db.get_user_context(1) or {}
        year, month = context.get("year", 2026), context.get("month", 10)
        if "--year" in args:
            year = int(args[args.index("--year") + 1])
        if "--month" in args:
            month = int(args[args.index("--month") + 1])
        months.init_month(year, month)
        print(f"الشهر النشط: {month:02d}/{year}")
        if "--reset" in args:
            _reset(year, month)
        _seed_tameedat(year, month)
        _seed_rations(year, month)
        _seed_warehouses(year, month)
        persons = _seed_force(year, month)
        _rebuild_files(year, month)
        _rebuild_raghibin_files(year, month, persons)
        from services import tameed_alerts
        stats = tameed_alerts.summary(year, month)
        print(f"🔔 تنبيهات الشهر: {stats['problem_rows']} صفًا — "
              f"خطر {stats['danger']} · تنبيه {stats['warn']} · معلومة {stats['info']}")
        print("تم البذر بنجاح — افتح صفحة التاميدات والمقررين للمعاينة.")


if __name__ == "__main__":
    main()
