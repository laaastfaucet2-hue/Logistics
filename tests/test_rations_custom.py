"""صرف يومي مقابل تخصيص أيام — أساس آلة 2 مخازن."""
from data_access import db_rations as dr, months


def _item(year=2031, month=9, lunch=0.075, dinner=0):
    months.init_month(year, month)
    dr.add_item(year, month, "tamween", "summer", "أرز بلدي", "كجم", 0, lunch, dinner)
    items, custom = dr.get_items(year, month, "tamween", "summer")
    return items[0], custom.get(items[0]["id"], [])


def test_uncustomized_lunch_is_every_day(app):
    item, custom = _item()
    issued = dr.issuance_map(item, custom)
    assert all(issued[(d, "lunch")] == 0.075 for d in range(7))
    assert (0, "breakfast") not in issued
    assert (0, "dinner") not in issued


def test_zero_general_plus_custom_days_only_those_days(app):
    item, _ = _item(lunch=0)
    dr.save_custom(2031, 9, item["id"], [(0, "lunch", 0.075), (3, "lunch", 0.075)])
    _, custom = dr.get_items(2031, 9, "tamween", "summer")
    issued = dr.issuance_map(item, custom[item["id"]])
    assert issued == {(0, "lunch"): 0.075, (3, "lunch"): 0.075}


def test_custom_save_rejects_missing_item(client):
    months.init_month(2031, 9)
    response = client.post("/rations/tamween/custom/0?year=2031&month=9",
                           data={"kind": "summer", "c_0_lunch": "0.075"},
                           follow_redirects=True)
    assert response.status_code == 200
    assert "الصنف غير موجود" in response.get_data(as_text=True)


def test_custom_form_posts_to_real_item_id(client):
    item, _ = _item()
    page = client.get("/rations/tamween?year=2031&month=9").text
    assert "/custom/0" in page
    assert "replace(\"/custom/0\"" in client.get("/static/js/rations.js").text
    response = client.post(
        f"/rations/tamween/custom/{item['id']}?year=2031&month=9",
        data={"kind": "summer", "c_5_lunch": "٠٫٠٧٥", "c_6_lunch": "0"},
        follow_redirects=True)
    assert response.status_code == 200
    assert "خانة فقط" in response.get_data(as_text=True)
    _, custom = dr.get_items(2031, 9, "tamween", "summer")
    assert custom[item["id"]] == [{"weekday": 5, "meal": "lunch", "qty": 0.075}]
