"""آلة حاسبة ٢ مخازن + المقررات المخصصة + توزيع التموين."""
from datetime import date
from core import egtime
from data_access import db_rations as dr, db_entities as de, db_tameedat as dt
from data_access import db_permits as dp, db_tameed_rations as snap
from services import ration_lines as rl, permit_build as pb

YEAR, MONTH = 2031, 9


def test_permit_fiscal_year_july_to_june():
    assert egtime.permit_fiscal_year(date(2026, 7, 1)) == 2026
    assert egtime.permit_fiscal_year(date(2027, 6, 30)) == 2026
    assert egtime.permit_fiscal_year(date(2027, 7, 1)) == 2027


def test_qty_is_meals_times_force_times_days(app):
    dr.add_item(YEAR, MONTH, "tamween", "summer", "جبنة", "علبة", 0.5, 0, 0.5)
    dr.set_activation(YEAR, MONTH, "tamween", "summer")
    item = dr.get_items(YEAR, MONTH, "tamween", "summer")[0][0]
    assert rl.meal_sum(item) == 1.0
    lines = rl.build_lines(YEAR, MONTH, "جهة", "tamween", 1, 10, {})
    cheese = [ln for ln in lines if ln["name"] == "جبنة" and ln["on"]]
    assert len(cheese) == 10
    assert cheese[0]["qty"] == 1.0
    force = 30
    auto = force * sum(ln["qty"] for ln in cheese)
    assert auto == 300


def test_override_does_not_change_master_table(app):
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز بلدي", "كجم", 0, 0.075, 0)
    eid = dt.add_entity(YEAR, MONTH, "قطاع وسط سيناء", "شرطية")
    rec_id = dt.add_record(YEAR, MONTH, 1, dt.get_entity(YEAR, MONTH, eid), 10, 10, 10, "", [])
    snap.save_payload(YEAR, MONTH, rec_id, {
        "main": {"tamween": [{"name": "أرز بلدي", "day": 1, "qty": 0.08, "on": True}]}
    })
    master = dr.get_items(YEAR, MONTH, "tamween", "summer")[0][0]
    assert master["lunch"] == 0.075
    over = rl.overrides_map(snap.get_payload(YEAR, MONTH, rec_id), "main", "tamween")
    lines = rl.build_lines(YEAR, MONTH, "قطاع وسط سيناء", "tamween", 1, 1, over)
    rice = next(ln for ln in lines if ln["name"] == "أرز بلدي")
    assert rice["qty"] == 0.08


def test_tamween_dist_is_separate_from_contractor(app):
    de.add_entity(YEAR, MONTH, "tamween", "جهة تموين")
    de.add_entity(YEAR, MONTH, "contractor", "جهة متعهد")
    t_names = [e["name"] for e in de.list_entities(YEAR, MONTH, "tamween")]
    c_names = [e["name"] for e in de.list_entities(YEAR, MONTH, "contractor")]
    assert "جهة تموين" in t_names and "جهة تموين" not in c_names
    assert "جهة متعهد" in c_names and "جهة متعهد" not in t_names


def test_permit_number_advances_and_manual_sets_next(app):
    n1, _ = dp.take_number(None, date(2026, 9, 1))
    n2, _ = dp.take_number(None, date(2026, 9, 2))
    assert n2 == n1 + 1
    n10, _ = dp.take_number(10, date(2026, 10, 1))
    assert n10 == 10
    n11, _ = dp.take_number(None, date(2026, 11, 1))
    assert n11 == 11


def test_entity_picks_are_separate_no_combined(app):
    eid = dt.add_entity(YEAR, MONTH, "وسط سيناء", "شرطية")
    rec_id = dt.add_record(
        YEAR, MONTH, 1, dt.get_entity(YEAR, MONTH, eid), 10, 10, 10, "",
        [{"name": "أشرف جاد", "entity_type": "شرطية", "officers": 5, "individuals": 5, "recruits": 5}])
    rec = dt.get_record(YEAR, MONTH, rec_id)
    picks = pb.entity_picks([rec])
    assert [p["kind"] for p in picks] == ["رئيسية", "ملحقة"]
    assert picks[0]["name"] == "وسط سيناء" and picks[1]["name"] == "أشرف جاد"
    assert all("مجمع" not in p["label"] for p in picks)
    groups = pb.pick_groups(YEAR, MONTH, picks)
    assert len(groups) == 1 and groups[0]["day"] == 1
    assert "يوم" in groups[0]["label"]
    assert len(groups[0]["tameedat"]) == 1
    assert [p["kind"] for p in groups[0]["tameedat"][0]["picks"]] == ["رئيسية", "ملحقة"]


def test_issue_clipped_to_tameedah_days_not_permit_window(app):
    dr.add_item(YEAR, MONTH, "tamween", "summer", "جبنة", "علبة", 0.5, 0, 0.5)
    dr.set_activation(YEAR, MONTH, "tamween", "summer")
    eid = dt.add_entity(YEAR, MONTH, "قطاع الشهيد اشرف جاد", "شرطية")
    rec_id = dt.add_record(
        YEAR, MONTH, 24, dt.get_entity(YEAR, MONTH, eid), 10, 10, 10, "", [], day_to=27)
    rec = dt.get_record(YEAR, MONTH, rec_id)
    picks = pb.entity_picks([rec])
    rows = pb.rows_for_picks(YEAR, MONTH, picks, 24, 28, 5, "tamween")
    cheese = next(r for r in rows if r["name"] == "جبنة")
    assert cheese["days"] == 4
    assert cheese["auto"] == 120
    assert cheese["breakfast"] == 0.5 and cheese["lunch"] == 0 and cheese["dinner"] == 0.5
    assert cheese["customized"] is False
    att_eid = dt.add_entity(YEAR, MONTH, "ملحقة وسط", "شرطية")
    rec2 = dt.add_record(
        YEAR, MONTH, 24, dt.get_entity(YEAR, MONTH, att_eid), 1, 1, 1, "",
        [{"name": "جهة ملحقة فقط", "entity_type": "شرطية", "officers": 2, "individuals": 2, "recruits": 2}],
        day_to=24)
    att_pick = [p for p in pb.entity_picks([dt.get_record(YEAR, MONTH, rec2)]) if p["is_attachment"]]
    g = pb.pick_groups(YEAR, MONTH, att_pick)
    assert g[0]["tameedat"][0]["title"] == "ملحقة وسط"
    assert [p["name"] for p in g[0]["tameedat"][0]["picks"]] == ["جهة ملحقة فقط"]


def test_tameedah_shows_permit_made_after_save(client, app):
    eid = dt.add_entity(YEAR, MONTH, "قطاع وسط سيناء", "شرطية")
    rec_id = dt.add_record(YEAR, MONTH, 1, dt.get_entity(YEAR, MONTH, eid), 10, 10, 10, "", [])
    page = client.get("/tameedat/?tab=day&day=2031-09-01").text
    assert "عمل إذن صرف ٢ مخازن" in page
    assert "تم عمل إذن ٢ مخازن" not in page
    dp.save_permit(YEAR, MONTH, {
        "number": 1, "fiscal_year": 2031, "date_from": 1, "date_to": 1, "issue_days": 1,
        "mode": "combined", "entity_label": "قطاع وسط سيناء",
        "officers": 10, "individuals": 10, "recruits": 10,
        "record_ids": [rec_id], "actuals": {},
    })
    page = client.get("/tameedat/?tab=day&day=2031-09-01").text
    assert "تم عمل إذن ٢ مخازن" in page


def test_rows_endpoint_fills_meals_when_entity_selected(client, app):
    dr.add_item(YEAR, MONTH, "tamween", "summer", "جبنة", "علبة", 0.5, 0, 0.5)
    dr.set_activation(YEAR, MONTH, "tamween", "summer")
    eid = dt.add_entity(YEAR, MONTH, "قطاع الشهيد اشرف جاد", "شرطية")
    rec_id = dt.add_record(YEAR, MONTH, 22, dt.get_entity(YEAR, MONTH, eid), 10, 10, 10, "", [])
    data = client.get("/calc2/rows?from=22&to=22&selected=main:" + str(rec_id)).get_json()
    cheese = next(r for r in data["tamween"] if r["name"] == "جبنة")
    assert cheese["breakfast"] == 0.5 and cheese["lunch"] == 0 and cheese["dinner"] == 0.5
    assert cheese["auto"] == 30
    empty = client.get("/calc2/rows?from=22&to=22").get_json()
    assert empty["tamween"] == []


def test_pages_render(client):
    page = client.get("/calc2/").text
    assert client.get("/calc2/").status_code == 200
    assert "تحميل قائمة التأميدات" in page
    assert "الجهات المحددة في هذا الإذن" in page
    assert "اسم الصنف" in page
    assert "الرصيد المتوفر بالمخازن" in page
    assert "الرصيد المتوفر بالعهدة" not in page
    dash = client.get("/dashboard").text
    assert dash.find("التاميدات") < dash.find("قسم الراغبين") < dash.find("آلة حاسبة 2 مخازن")
    dist = client.get("/rations/tamween?tab=dist")
    assert dist.status_code == 200
    assert "توزيع المقررات على الجهات" in dist.text
    day = client.get("/tameedat/")
    assert "المقررات والتخصيص التفاعلي للمتعهد والتموين للجهة الحالية" in day.text
    assert "تسجيل أسماء الضباط والأفراد الراغبين للجهة الحالية" in day.text
    assert "tmRationsModal" in day.text
    assert "قيد التطوير" in day.text
