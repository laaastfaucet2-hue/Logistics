# -*- coding: utf-8 -*-
"""قسم الراغبين (ج١): قوة الجهات + الحالات + نسخ القوة + ملفات الكوادر الرسمية."""
from openpyxl import load_workbook

from services import raghibin as rfs
from services.raghibin import files_monthly as mfs
from services.raghibin import files_rosters as xr

from data_access import db_raghibin as drg
from data_access import db_tameedat as dt
from services import raghibin as rfs

YEAR, MONTH = 2031, 9


def _entity(Y=YEAR, M=MONTH, name="قطاع الشهيد اشرف جاد"):
    eid = dt.add_entity(Y, M, name, "شرطية")
    return eid, name


def test_add_person_and_no_duplicates(app):
    eid, _ = _entity()
    pid, created = drg.add_person(YEAR, MONTH, eid, "officers", "محمد محمود", "رائد")
    assert created
    pid2, created2 = drg.add_person(YEAR, MONTH, eid, "officers", "محمد محمود", "رائد")
    assert not created2 and pid2 == pid
    assert len(drg.list_persons(YEAR, MONTH, entity_id=eid)) == 1
    persons = drg.list_persons(YEAR, MONTH, entity_id=eid, category="officers")
    assert persons[0]["rank"] == "رائد"
    # الفئات منفصلة: نفس الاسم في الأفراد ليس تكرارًا
    _, created_i = drg.add_person(YEAR, MONTH, eid, "individuals", "محمد محمود")
    assert created_i


def test_exclude_toggle_and_warning(app):
    eid, _ = _entity()
    pid, _ = drg.add_person(YEAR, MONTH, eid, "officers", "ابراهيم ناجى عطا الله", "رائد")
    drg.set_excluded(YEAR, MONTH, pid, True, "هلاكات — غير راغب")
    counts = drg.entity_force_counts(YEAR, MONTH, eid)
    assert counts[eid]["officers"] == 1
    assert counts[eid]["officers_excluded"] == 1
    assert drg.list_persons(YEAR, MONTH, entity_id=eid, excluded=False) == []
    drg.set_excluded(YEAR, MONTH, pid, False)
    assert drg.list_persons(YEAR, MONTH, entity_id=eid, excluded=False)


def test_daily_one_meal_per_day(app):
    eid, _ = _entity()
    pid, _ = drg.add_person(YEAR, MONTH, eid, "officers", "مصطفى عبدالحميد", "نقيب")
    drg.set_daily(YEAR, MONTH, pid, 22, True, source="manual")
    drg.set_daily(YEAR, MONTH, pid, 22, True, source="tamida")   # upsert لا يكرر
    drg.set_daily(YEAR, MONTH, pid, 23, True)
    assert drg.month_meals(YEAR, MONTH)[pid] == 2                # وجبة لكل يوم
    assert drg.day_state(YEAR, MONTH, 22, eid) == {pid: True}


def test_copy_force_across_months(app):
    eid, name = _entity()
    pid, _ = drg.add_person(YEAR, MONTH, eid, "officers", "محمد محمود", "رائد")
    drg.set_excluded(YEAR, MONTH, pid, True, "هلاكات")
    drg.set_daily(YEAR, MONTH, pid, 22, True)
    copied_entities, copied_names = drg.copy_force(YEAR, MONTH, 2032, 5)
    assert (copied_entities, copied_names) == (1, 1)
    targets = drg.list_persons(2032, 5)
    assert len(targets) == 1
    assert targets[0]["excluded"] == 1 and targets[0]["exclude_note"] == "هلاكات"
    assert drg.month_meals(2032, 5) == {}          # التسجيلات اليومية لا تُنسخ
    ents = dt.list_entities(2032, 5)
    assert any(e["name"] == name for e in ents)    # الجهة أنشئت بقاموس الشهر الهدف


def test_cadres_files_official_and_states(app):
    eid, name = _entity()
    p1, _ = drg.add_person(YEAR, MONTH, eid, "officers", "محمد محمود", "رائد")
    p2, _ = drg.add_person(YEAR, MONTH, eid, "officers", "ابراهيم ناجى عطا الله", "رائد")
    drg.set_excluded(YEAR, MONTH, p2, True, "هلاكات")
    drg.add_person(YEAR, MONTH, eid, "individuals", "أحمد محمد صابر", "فرد (1)")
    folder = rfs.write_cadres_files(YEAR, MONTH, eid, name)
    off_path = folder / f"{name} (ضباط).xlsx"
    ind_path = folder / f"{name} (أفراد).xlsx"
    assert off_path.exists() and ind_path.exists()
    ws = load_workbook(off_path).active
    assert ws.title == "الضباط"
    assert ws.cell(6, 1).value.startswith("الجهات والكوادر المعتمدة")
    names = [ws.cell(r, 3).value for r in range(8, 10)]
    assert "محمد محمود" in names and "ابراهيم ناجى عطا الله" in names
    states = [ws.cell(r, 4).value for r in range(8, 10)]
    assert "✓ راغب" in states and "⊘ غير راغب" in states
    # الدباجة الرسمية (صفوف ١-٤ مدموجة تمتد لأول ٤ خلايا) + صف الإجمالي بعد البيانات
    merged_starts = {str(rng).split(":")[0] for rng in ws.merged_cells.ranges}
    assert "A1" in merged_starts and "A4" in merged_starts
    total_row = 8 + 2   # صفان بيانات + صف الإجمالي في الصف العاشر
    assert "الإجمالي" in str(ws.cell(total_row, 1).value)
    ws_i = load_workbook(ind_path).active
    assert ws_i.title == "الأفراد والصف"
    assert ws_i.cell(8, 3).value == "أحمد محمد صابر"


def test_daily_toggle_flow_and_day_file(app, client):
    from services.raghibin.files_daily import day_dir
    eid, name = _entity()
    p1, _ = drg.add_person(YEAR, MONTH, eid, "officers", "محمد محمود", "رائد")
    p2, _ = drg.add_person(YEAR, MONTH, eid, "officers", "ابراهيم ناجى عطا الله", "رائد")
    drg.set_excluded(YEAR, MONTH, p2, True, "هلاكات")
    p3, _ = drg.add_person(YEAR, MONTH, eid, "individuals", "أحمد محمد صابر", "فرد (1)")
    r = client.post("/raghibin/daily/toggle", data={
        "e": eid, "d": 22, "person_id": p1, "willing": "1"})
    assert r.status_code == 302
    assert drg.day_state(YEAR, MONTH, 22, eid) == {p1: True}
    path = day_dir(YEAR, MONTH, 22) / f"{name}.xlsx"
    assert path.exists()
    ws = load_workbook(path).active
    assert ws.title == "يوم ٢٢"
    assert "الراغبين في وجبة الطعام" in str(ws.cell(6, 1).value)
    marks = {ws.cell(r, 3).value: (ws.cell(r, 5).value, ws.cell(r, 4).value)
             for r in range(8, 11)}
    assert marks["محمد محمود"][0] == "✓ راغب بالوجبة"
    assert marks["ابراهيم ناجى عطا الله"][0] == "⊘ غير راغب"
    assert marks["أحمد محمد صابر"][0] == "✗ لا"
    total_row = str(ws.cell(11, 1).value)
    assert "الإجمالي: ١ راغبون من أصل ٣" in total_row
    # إلغاء الرغبة يحدّث نفس الملف
    client.post("/raghibin/daily/toggle", data={"e": eid, "d": 22, "person_id": p1,
                                                "willing": "0"})
    assert drg.day_state(YEAR, MONTH, 22, eid) == {p1: False}


def test_toggle_blocked_for_excluded(app, client):
    eid, name = _entity()
    pid, _ = drg.add_person(YEAR, MONTH, eid, "officers", "ابراهيم ناجى عطا الله", "رائد")
    drg.set_excluded(YEAR, MONTH, pid, True, "هلاكات")
    r = client.post("/raghibin/daily/toggle", data={
        "e": eid, "d": 22, "person_id": pid, "willing": "1"})
    assert r.status_code == 302
    assert "warn=" in r.headers["Location"]       # تحذير بدون كتابة
    assert drg.day_state(YEAR, MONTH, 22, eid) == {}


def test_exclude_clears_daily_marks(app):
    eid, _ = _entity()
    pid, _ = drg.add_person(YEAR, MONTH, eid, "officers", "محمد محمود", "رائد")
    drg.set_daily(YEAR, MONTH, pid, 22, True)
    drg.set_excluded(YEAR, MONTH, pid, True, "هلاكات")
    assert drg.month_meals(YEAR, MONTH) == {}     # الاستثناء يسقط تسجيلات اليومية
    drg.set_excluded(YEAR, MONTH, pid, False)
    assert drg.day_state(YEAR, MONTH, 22, eid) == {}   # والإرجاع لا يستعيدها


def test_daily_page_calendar_folders_and_mismatch(app, client):
    from services import raghibin as rfs
    eid, name = _entity()
    p1, _ = drg.add_person(YEAR, MONTH, eid, "officers", "محمد محمود", "رائد")
    p2, _ = drg.add_person(YEAR, MONTH, eid, "officers", "مصطفى عبدالحميد", "نقيب")
    drg.set_daily(YEAR, MONTH, p1, 22, True)
    drg.set_daily(YEAR, MONTH, p2, 22, True)
    dt.add_record(YEAR, MONTH, 22, {"id": eid, "name": name, "entity_type": "شرطية"},
                  10, 10, 10, notes="تأميدة اعتيادية")
    r = client.get(f"/raghibin?tab=daily&e={eid}&d=22")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "عدم تطابق يوم ٢٢" in body                     # ١٠ تأميدة مقابل ٢ راغبين
    assert "ضباط: <b>٢</b> من ٢" in body
    root = rfs.tab_dir(YEAR, MONTH, "daily")
    assert (root / "يوم ١").exists() and (root / "يوم ٣٠").exists()   # فولدرات الشهر كاملة


def test_rank_seniority_ordering(app):
    eid, _ = _entity()
    for rank, name in (("ملازم", "ع"),
                       ("رائد", "ب"), ("لواء", "أ"), ("نقيب", "ج")):
        drg.add_person(YEAR, MONTH, eid, "officers", name, rank)
    drg.add_person(YEAR, MONTH, eid, "individuals", "م1", "عريف")
    drg.add_person(YEAR, MONTH, eid, "individuals", "م2", "مساعد أول")
    drg.add_person(YEAR, MONTH, eid, "individuals", "م3", "رتبة غير معروفة")
    persons = drg.list_persons(YEAR, MONTH, entity_id=eid)
    officers = [p["full_name"] for p in persons if p["category"] == "officers"]
    individuals = [p["full_name"] for p in persons if p["category"] == "individuals"]
    # الضباط: اللواء ← رائد ← نقيب ← ملازم (الأقدمية)
    assert officers == ["أ", "ب", "ج", "ع"]
    # الأفراد: مساعد أول ← عريف ← وغير المعروفة آخر الفئة
    assert individuals == ["م2", "م1", "م3"]
    assert drg.rank_weight("officers", "لواء") < drg.rank_weight("officers", "رائد")
    assert drg.rank_weight("officers", "ملازم") == 9      # آخر رتب معروفة
    assert drg.rank_weight("officers", "غريب") == 11      # غير المعروفة آخر الفئة


def test_excluded_tab_and_files(app, client):
    eid, name = _entity()
    p1, _ = drg.add_person(YEAR, MONTH, eid, "officers", "ابراهيم ناجى عطا الله", "رائد")
    p2, _ = drg.add_person(YEAR, MONTH, eid, "individuals", "كريم فتحي عوض", "فرد (1)")
    drg.set_excluded(YEAR, MONTH, p2, True, "مأمورية خارج القطاع")
    folder = xr.write_excluded_files(YEAR, MONTH, eid, name)
    off = folder / f"{name} (ضباط غير راغبين).xlsx"
    ind = folder / f"{name} (أفراد غير راغبين).xlsx"
    assert off.exists() and ind.exists()
    ws = load_workbook(ind).active
    assert ws.cell(8, 3).value == "كريم فتحي عوض"
    assert ws.cell(8, 4).value == "مأمورية خارج القطاع"
    assert "الإجمالي: ١" in str(ws.cell(9, 1).value)
    r = client.get(f"/raghibin?tab=excluded&e={eid}")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "سجل عدم الراغبين" in body and "كريم فتحي عوض" in body
    assert "إرجاعه للقوة الراغبة" in body


def test_monthly_tab_and_file(app, client):
    eid, name = _entity()
    p1, _ = drg.add_person(YEAR, MONTH, eid, "officers", "محمد محمود", "رائد")
    p2, _ = drg.add_person(YEAR, MONTH, eid, "officers", "مصطفى عبدالحميد", "نقيب")
    p3, _ = drg.add_person(YEAR, MONTH, eid, "officers", "ابراهيم ناجى عطا الله", "رائد")
    drg.set_excluded(YEAR, MONTH, p3, True, "هلاكات")
    drg.set_daily(YEAR, MONTH, p1, 22, True)
    drg.set_daily(YEAR, MONTH, p1, 23, True)
    drg.set_daily(YEAR, MONTH, p2, 22, True)
    path = mfs.write_monthly_file(YEAR, MONTH, eid, name)
    book = load_workbook(path)
    assert book.sheetnames == ["الضباط", "الأفراد والصف"]
    ws = book["الضباط"]
    assert ws.cell(8, 2).value == "رائد / محمد محمود" and ws.cell(8, 3).value == "٢"
    assert ws.cell(9, 3).value == "١"                       # نقيب / مصطفى — وجبة
    names = [ws.cell(r, 2).value for r in range(8, 11)]     # المستثنى خارج الكشف
    assert all("ابراهيم" not in str(n) for n in names)
    assert "إجمالي ٢ فرد | إجمالي الوجبات: ٣ وجبة" in str(ws.cell(10, 1).value)
    r = client.get(f"/raghibin?tab=monthly&e={eid}&c=officers")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "رائد / محمد محمود" in body
    assert "إجمالي الوجبات: ٣ وجبة" in body
    assert "الضباط" in body and "الأفراد" in body


def test_monthly_rebuilds_on_toggle(app, client):
    eid, name = _entity()
    pid, _ = drg.add_person(YEAR, MONTH, eid, "officers", "محمد محمود", "رائد")
    client.post("/raghibin/daily/toggle", data={"e": eid, "d": 5, "person_id": pid,
                                                "willing": "1"})
    ws = load_workbook(mfs.tab_dir(YEAR, MONTH, "monthly") / f"{name}.xlsx")["الضباط"]
    assert ws.cell(8, 3).value == "١"
    assert "إجمالي الوجبات: ١ وجبة" in str(ws.cell(9, 1).value)


def test_page_and_section_redirect(client):
    r = client.get("/raghibin?tab=cadres")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    for name in ("الراغبين (يومي)", "عدم الراغبين", "تجميع الكشف العام",
                 "الجهات والكوادر المعتمدة"):
        assert name in body
    r2 = client.get("/sections/raghebeen")
    assert r2.status_code == 302 and "/raghibin" in r2.headers["Location"]
