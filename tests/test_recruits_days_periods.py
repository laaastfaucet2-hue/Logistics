# -*- coding: utf-8 -*-
"""المجندين بمربعات الأيام + «من/إلى» في اليومية العامة (توجيه ١٥/١٠).

- اليومية: لكل مجند الحالة + من + إلى (إلى فاضية = مفتوحة وتترحّل يوم بيوم).
- «إلى» بتسجل الحالة على أيامها مقدمًا، ولما تخلص المجند يظهر فاضي + تنبيه.
- لوحتا «إجازة مجمّعة» و«تسجيل سريع» اتشالوا من اليومية؛ الإجازة المجمّعة/الطارئة
  في الحضور على اليوم المفتوح، والحضور بينبّه على اللي إجازته بكرة.
- كل التابات بمربعات أيام + «الشهر كله».
"""
from data_access import db_attendance as da
from data_access import db_recruits as dr

Y, M = 2031, 9


def _seed(n=2):
    return [dr.add_recruit(Y, M, {"name": f"مجند{i + 1} مدة", "mil_no": str(700 + i),
                                  "address": "قبل"}) for i in range(n)]


def _row(rid, day):
    return da.get_day_map(Y, M, day).get(rid)


def _save(client, day, rows):
    data = {"day": str(day)}
    for rid, st, f, t in rows:
        data[f"st_{rid}"] = st
        data[f"from_{rid}"] = f
        data[f"to_{rid}"] = t
    return client.post("/recruits/journal/save", data=data)


def test_journal_has_period_columns_and_old_panels_are_gone(client, app):
    a, _b = _seed()
    page = client.get("/recruits?tab=journal&day=1").data.decode("utf-8")
    assert f'name="from_{a}"' in page and f'name="to_{a}"' in page
    assert 'class="panel rc-daysbox"' in page
    for gone in ("rgSendLeaves", "journal/range", "rc-jchk", "تسجيل سريع: حالة لمدة"):
        assert gone not in page, gone


def test_to_date_fills_days_open_status_carries_and_ended_is_flagged(client, app):
    a, b = _seed()
    r = _save(client, 1, [(a, "حضور", "", ""), (b, "إجازة", "", "2031/09/03")])
    assert r.status_code == 302
    assert [(_row(b, d) or {}).get("status") for d in (1, 2, 3, 4)] == ["إجازة"] * 3 + [None]
    assert _row(b, 2)["p_to"] == "2031-09-03" and _row(a, 1)["p_to"] == ""
    for day in (2, 3):
        page = client.get(f"/recruits?tab=journal&day={day}").data.decode("utf-8")
        assert _row(a, day)["status"] == "حضور"           # المفتوحة اترحّلت
        assert "2031/09/03" in page or "٢٠٣١/٠٩/٠٣" in page
        _save(client, day, [(a, "حضور", "", ""), (b, "إجازة", "2031/09/01", "2031/09/03")])
    page = client.get("/recruits?tab=journal&day=4").data.decode("utf-8")
    assert _row(a, 4)["status"] == "حضور"
    assert _row(b, 4) is None                            # «إلى» خلصت ⇒ فاضي
    assert "انتهت مدة «إجازة» أمس" in page and "مجند2 مدة" in page


def test_locked_day_inside_period_is_rejected(client, app):
    a, _b = _seed()
    _save(client, 1, [(a, "حضور", "", "")])
    client.get("/recruits?tab=journal&day=2")
    r = _save(client, 2, [(a, "إجازة", "2031/09/01", "")])
    assert r.status_code == 302 and "err=" in r.headers["Location"]
    assert _row(a, 1)["status"] == "حضور"
    assert da.get_meta(Y, M, 2)["locked"] == 0               # ما اتثبّتش


def test_changing_status_clears_old_planned_tail(client, app):
    a, b = _seed()
    _save(client, 1, [(a, "حضور", "", ""), (b, "إجازة", "", "2031/09/05")])
    client.get("/recruits?tab=journal&day=2")
    _save(client, 2, [(a, "حضور", "", ""), (b, "حضور", "", "")])
    assert [(_row(b, d) or {}).get("status") for d in (3, 4, 5)] == [None, None, None]
    client.get("/recruits?tab=journal&day=3")
    assert _row(b, 3)["status"] == "حضور"                 # الترحيل كمّل صح


def test_open_leave_has_no_return_banner(client, app):
    _a, b = _seed()
    _save(client, 1, [(b, "إجازة", "", "")])
    page = client.get("/recruits?tab=journal&day=1").data.decode("utf-8")
    assert "راجع من الإجازة" not in page


def test_present_tab_days_box_and_leave_tomorrow_alert(client, app):
    a, b = _seed()
    _save(client, 4, [(a, "حضور", "", ""), (b, "حضور", "", "")])
    r = client.post("/recruits/send-leaves", data={"rid": [str(a)], "start": "tomorrow",
                                                   "day": "4", "to": "6"})
    assert r.status_code == 302
    assert (5, 6) in da.month_leave_permits(Y, M).get(a, [])
    page = client.get("/recruits?tab=present&day=4").data.decode("utf-8")
    assert 'class="panel rc-daysbox"' in page and "rc-allbox" not in page
    assert "إجازة غدًا" in page and "مجند1 مدة" in page
    assert '<input type="hidden" name="day" value="4">' in page
    assert 'class="rc-mark"' in page


def test_emergency_leave_on_opened_day_with_present_until(client, app):
    a, _b = _seed()
    r = client.post("/recruits/send-leaves", data={"rid": [str(a)], "start": "today",
                                                   "day": "5", "to": "6", "t_present": "١:٠٠"})
    assert r.status_code == 302
    assert [(_row(a, d) or {}).get("status") for d in (4, 5, 6)] == [None, "إجازة", "إجازة"]
    assert _row(a, 5)["note"] == "حضر لحد الساعة ١:٠٠"
    assert (_row(a, 6)["p_from"], _row(a, 6)["p_to"]) == ("2031-09-05", "2031-09-06")


def test_list_tabs_have_days_and_whole_month(client, app):
    a, b = _seed()
    da.set_range(Y, M, a, "إجازة", 1, 3)
    da.set_range(Y, M, b, "غياب", 10, 11)
    day3 = client.get("/recruits?tab=leaves&day=3").data.decode("utf-8")
    day9 = client.get("/recruits?tab=leaves&day=9").data.decode("utf-8")
    month = client.get("/recruits?tab=leaves&day=all").data.decode("utf-8")
    assert "مجند1 مدة" in day3 and "مجند1 مدة" not in day9 and "مجند1 مدة" in month
    assert "rc-allbox on" in month and "لا إجازات في هذا اليوم" in day9
    absent = client.get("/recruits?tab=absent&day=11").data.decode("utf-8")
    assert "مجند2 مدة" in absent
    for tab in ("other", "prison"):
        page = client.get(f"/recruits?tab={tab}&day=2").data.decode("utf-8")
        assert 'class="panel rc-daysbox"' in page and "rc-allbox" in page


def test_to_date_after_month_end_is_clipped_with_notice(client, app):
    a, _b = _seed()
    r = _save(client, 28, [(a, "إجازة", "", "2031/10/03")])
    assert r.status_code == 302 and "ok=" in r.headers["Location"]
    assert [(_row(a, d) or {}).get("status") for d in (28, 29, 30)] == ["إجازة"] * 3
    assert _row(a, 30)["p_to"] == "2031-10-03"          # «إلى» الحقيقية محفوظة للعرض


def test_unchanged_status_keeps_period_start_when_from_left_empty(client, app):
    a, _b = _seed()
    _save(client, 1, [(a, "حضور", "", "")])
    client.get("/recruits?tab=journal&day=2")
    client.post("/recruits/journal/save", data={"day": "2", f"st_{a}": "حضور"})
    assert _row(a, 2)["p_from"] == "2031-09-01"
