# -*- coding: utf-8 -*-
"""الإجازة المجمّعة من تبويب الحضور (توجيه ١٤/١٠):
زر ثابت يفتح نافذة (حاضرو اليوم/كل المجندين) → تصريح بتاريخ اليوم وتسجيل فوري
في اليومية العامة، ونزول «بكرة» يتسجل من بانر اليومية بضغطة «سجّلهم في اليومية».
وكذلك عقد محاذاة جداول المجندين (الأرقام وسط الخانة والنصوص يمين)."""
from pathlib import Path

from data_access import db_attendance as da
from data_access import db_recruits as dr

YEAR, MONTH = 2031, 9
ROOT = Path(__file__).resolve().parents[1]


def _seed(n=3, present_day=1):
    ids = []
    for i in range(n):
        ids.append(dr.add_recruit(YEAR, MONTH, {
            "name": f"مجند{i + 1} جماعي", "mil_no": str(400 + i), "address": "قبل"}))
        da.set_range(YEAR, MONTH, ids[-1], "حضور", present_day, present_day)
    return ids


def _status(rid, day):
    return da.get_day_map(YEAR, MONTH, day).get(rid, {}).get("status")


def test_present_tab_has_pinned_button_and_dialog(client, app):
    _seed()
    page = client.get("/recruits?tab=present&day=1").data.decode("utf-8")
    assert 'id="rcJointBtn"' in page                    # الزرار الثابت
    assert "rc-quickbar" in page                        # شريط لاصق فوق
    assert 'id="rcJointModal"' in page                  # النافذة
    assert 'data-jl-tab="present"' in page and 'data-jl-tab="all"' in page
    assert 'action="/recruits/send-leaves' in page
    assert "js/recruits_joint.js" in page
    # القائمة بكل المجندين وعليها علامة الحضور (تبويب الحاضرين بيفلترها)
    assert page.count('name="rid"') == 3
    assert page.count('data-present=') == 3


def test_today_leave_registers_immediately_with_times(client, app):
    ids = _seed()
    response = client.post("/recruits/send-leaves", data={
        "rid": [str(i) for i in ids], "start": "today", "to": "3",
        "t_present": "١:٠٠", "t_left": "١:٣٠"})
    assert response.status_code == 302
    for rid in ids:
        assert [_status(rid, d) for d in (1, 2, 3)] == ["إجازة"] * 3
    note = da.get_day_map(YEAR, MONTH, 1)[ids[0]]["note"]
    assert "حضروا لحد الساعة" in note and "١:٣٠" in note
    permits = da.month_leave_permits(YEAR, MONTH)
    assert all((1, 3) in permits.get(rid, []) for rid in ids)


def test_tomorrow_leave_defers_until_one_press(client, app):
    ids = _seed()
    response = client.post("/recruits/send-leaves", data={
        "rid": [str(i) for i in ids], "start": "tomorrow", "to": ""})
    assert response.status_code == 302
    # التصريح اتسجل — والتسجيل في اليومية مُرجأ (يوم بكرة لسه فاضي للترحيل التلقائي)
    assert all((2, 2) in da.month_leave_permits(YEAR, MONTH).get(rid, []) for rid in ids)
    assert da.get_day_map(YEAR, MONTH, 2) == {}
    # بانر اليومية فيه الزر اللي بيسجلهم بضغطة
    journal = client.get("/recruits?tab=journal&day=1").data.decode("utf-8")
    assert "سجّلهم في اليومية" in journal
    assert '<input type="hidden" name="day" value="2">' in journal
    assert "مجند1 جماعي" in journal
    # الضغطة بتكتب المدة كاملة
    done = client.post("/recruits/journal/confirm-leaves", data={"day": "2"})
    assert done.status_code == 302
    for rid in ids:
        assert _status(rid, 2) == "إجازة"


def test_tables_alignment_contract():
    css = (ROOT / "static" / "css" / "recruits.css").read_text(encoding="utf-8")
    assert ".rc-page .rt-table th.num" in css and "text-align: center" in css
    assert ".rc-page .rt-table td.num {" in css and "direction: ltr" in css
    assert ".rc-page .rt-table th.mid" in css
    for name in ("recruits_registry", "recruits_journal", "recruits_file",
                 "recruits_lists", "recruits_prison", "recruits_stats"):
        page = (ROOT / "templates" / f"{name}.html").read_text(encoding="utf-8")
        assert "{% block body_class %}rc-page{% endblock %}" in page, name
    present = (ROOT / "templates" / "recruits_lists.html").read_text(encoding="utf-8")
    assert '<th class="num">الرقم العسكري</th>' in present
    assert '<th class="num" title="بداية فترة الحضور المتواصلة">حضور من</th>' in present
