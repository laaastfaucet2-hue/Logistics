# -*- coding: utf-8 -*-
"""إغلاق الأقسام المحمية من أزرار الصفحة نفسها."""
import pytest

from data_access import database as db


@pytest.mark.parametrize(
    ("sub", "open_marker"),
    (("log", "سجل المراقبة وإتمام النشاط"),
     ("notes", "ملحوظة جديدة")),
)
def test_close_and_protect_button_locks_section_immediately(app, client, sub, open_marker):
    token = db.create_session(1)

    locked = client.get(f"/settings/?sub={sub}&sid={token}")
    assert locked.status_code == 200
    assert "هذا القسم محمي" in locked.get_data(as_text=True)

    opened = client.post("/settings/gate", data={
        "sid": token, "sub": sub, "password": "7799",
    }, follow_redirects=True)
    assert opened.status_code == 200
    body = opened.get_data(as_text=True)
    assert open_marker in body
    assert db.is_gate_open(token, sub)
    # زر الشريط وزر «إغلاق وحماية» داخل القسم كلاهما POST حقيقي للقفل.
    assert body.count('name="action" value="lock"') >= 2
    assert 'class="sg-inline-lock' in body

    closed = client.post("/settings/gate", data={
        "sid": token, "sub": sub, "action": "lock",
    }, follow_redirects=True)
    assert closed.status_code == 200
    closed_body = closed.get_data(as_text=True)
    assert "هذا القسم محمي" in closed_body
    assert open_marker not in closed_body
    assert not db.is_gate_open(token, sub)
