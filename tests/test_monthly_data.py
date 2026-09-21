import pytest
from data_access import db_recruits as recruits, db_letterhead as lh, db_attendance as attendance, storage, database
from services import month_copy, legacy_months
from services.bootstrap import bootstrap_year_files


def add(year=2031, month=9, number="123"):
    return recruits.add_recruit(year, month, {"name": "اسم اختبار مؤقت", "mil_no": number, "address": "قبل"})


def test_registry_edit_and_delete_are_isolated(app):
    rid = add()
    plan = month_copy.preview("registry", (2031,9), (2031,10))
    month_copy.execute("registry", (2031,9), (2031,10), plan["fingerprint"])
    target = recruits.list_recruits(2031,10)[0]
    target["name"] = "تعديل في أكتوبر"
    recruits.update_recruit(2031,10,target["id"],target)
    assert recruits.get_recruit(2031,9,rid)["name"] == "اسم اختبار مؤقت"
    recruits.delete_recruit(2031,10,target["id"])
    assert recruits.get_recruit(2031,9,rid)


def test_copy_skips_duplicates_and_never_copies_attendance(app):
    rid = add()
    attendance.save_day(2031,9,1,[(rid,"حضور","")])
    add(month=10)
    plan = month_copy.preview("registry", (2031,9), (2031,10))
    assert plan["skipped"] == 1
    result = month_copy.execute("registry", (2031,9), (2031,10), plan["fingerprint"])
    assert result == {"added":0,"skipped":1}
    assert attendance.month_matrix(2031,10) == {}
    with pytest.raises(ValueError):
        recruits.delete_recruit(2031,9,rid)


def test_selected_copy_to_another_year(app):
    a = add(number="1")
    add(number="2")
    storage.create_year(2032)
    bootstrap_year_files(2032)
    plan = month_copy.preview("registry", (2031,9), (2032,1), [a])
    month_copy.execute("registry", (2031,9), (2032,1), plan["fingerprint"], [a])
    assert [r["mil_no"] for r in recruits.list_recruits(2032,1)] == ["1"]
    assert not recruits.list_recruits(2032,2)


def test_copy_requires_same_previewed_data(app):
    rid = add()
    plan = month_copy.preview("registry", (2031,9), (2031,10))
    row = recruits.get_recruit(2031,9,rid)
    row["name"] = "changed since preview"
    recruits.update_recruit(2031,9,rid,row)
    with pytest.raises(ValueError, match="تغيّرت"):
        month_copy.execute("registry", (2031,9), (2031,10), plan["fingerprint"])
    assert not recruits.list_recruits(2031,10)


@pytest.mark.parametrize("target", [(2031,9),(2031,13),(2099,1),(2031,None)])
def test_invalid_copy_target(app,target):
    add()
    with pytest.raises(ValueError):
        month_copy.preview("registry",(2031,9),target)


def test_letterhead_replacement_requires_explicit_confirmation(app):
    lh.save(2031,9,{"lh_1":"المصدر"})
    lh.save(2031,10,{"lh_1":"الوجهة"})
    plan = month_copy.preview("letterhead",(2031,9),(2031,10))
    with pytest.raises(ValueError):
        month_copy.execute("letterhead",(2031,9),(2031,10),plan["fingerprint"])
    assert lh.get_setting(2031,10,"lh_1") == "الوجهة"
    month_copy.execute("letterhead",(2031,9),(2031,10),plan["fingerprint"],replace=True)
    lh.save(2031,10,{"lh_1":"تعديل الوجهة"})
    assert lh.get_setting(2031,9,"lh_1") == "المصدر"


def test_legacy_import_preserves_ids_daily_links_and_original(app):
    legacy = storage.DATA_DIR / "recruits.db"
    conn = database.get_conn(legacy)
    conn.executescript(recruits.SCHEMA)
    conn.execute("INSERT INTO recruits(id,name,mil_no) VALUES (73,?,?)",("سجل قديم مؤقت","555"))
    conn.commit();conn.close()
    attendance.save_day(2031,9,7,[(73,"إجازة","")])
    assert not recruits.list_recruits(2031,9)  # No implicit migration on opening.
    legacy_months.import_to_month("registry",2031,9)
    assert recruits.get_recruit(2031,9,73)["mil_no"] == "555"
    assert attendance.get_day_map(2031,9,7)[73]["status"] == "إجازة"
    assert not recruits.list_recruits(2031,10)
    assert legacy.exists() and legacy_months.registry_available() == 1
    with pytest.raises(ValueError):
        legacy_months.import_to_month("registry",2031,9)


def test_certificate_uncheck_is_enforced_server_side(client):
    response=client.post('/recruits/save?year=2031&month=9',data={"name":"تجربة","mil_no":"١٥",
        "cert_date":"2030-01-01","cert_expiry":"2033-01-01"},follow_redirects=True)
    assert response.status_code==200
    row=recruits.list_recruits(2031,9)[0]
    assert row['mil_no']=='15'
    assert row['has_cert']==0 and row['cert_date']==row['cert_expiry']==row['cert_photo']==''


def test_explicit_period_prevents_other_tab_context_leak(client):
    database.set_user_context(1,2031,10)
    client.post('/recruits/save?year=2031&month=9',data={"name":"سبتمبر","mil_no":"5"})
    assert recruits.list_recruits(2031,9)
    assert not recruits.list_recruits(2031,10)
