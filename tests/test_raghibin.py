# -*- coding: utf-8 -*-
"""قسم الراغبين (ج١): قوة الجهات + الحالات + نسخ القوة + ملفات الكوادر الرسمية."""
from openpyxl import load_workbook

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


def test_page_and_section_redirect(client):
    r = client.get("/raghibin?tab=cadres")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    for name in ("الراغبين (يومي)", "عدم الراغبين", "تجميع الكشف العام",
                 "الجهات والكوادر المعتمدة"):
        assert name in body
    r2 = client.get("/sections/raghebeen")
    assert r2.status_code == 302 and "/raghibin" in r2.headers["Location"]
