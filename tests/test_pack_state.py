# -*- coding: utf-8 -*-
"""حالة العبوات الحقيقية — مصدر واحد (١٤/١٠):

التفريدة بسحب FEFO من كل دفعة بمدير عبواتها (سائب أولًا → باقي مفتوح
→ فتح كاملة — الكاملة ما تتحولش سائب توجيه ٢٧/٠٩)، وكل العارضين (التفريدة
/ دفتر ٣ مخازن / حركة المخازن / كشف الأرصدة) يقرأون نفس الحالة. الدفعات
القديمة بلا تغليف تحتفظ بالسلوك القديم (تفكيك ساد)."""
from data_access import db_permits as dp
from data_access import db_rations as dr
from data_access import db_stores
from data_access import db_warehouses as dw
from data_access import db_warehouses_stores as dws
from data_access import db_tameedat as dt
from data_access import months
from services import warehouses_fs as wf

YEAR, MONTH = 2031, 9


def _init():
    months.init_month(YEAR, MONTH)


def _post(client, url, data, follow=False):
    return client.post(url, data=data, follow_redirects=follow)


def test_pack_state_fefo_single_source(client):
    _init()
    dr.add_item(YEAR, MONTH, "tamween", "summer", "سكر", "كجم", 0, 0, 0)
    dr.add_item(YEAR, MONTH, "tamween", "summer", "زيت الطعام", "لتر", 0, 0, 0)
    dr.add_item(YEAR, MONTH, "tamween", "summer", "ملح", "كجم", 0, 0, 0)
    dr.add_item(YEAR, MONTH, "tamween", "summer", "دقيق", "كجم", 0, 0, 0)
    db_stores.add_store("مخزن السكر")
    store = db_stores.list_stores()[0]
    # ١ مخازن: سكر «٢ شكارة × ٥٠ +  سائب» = ١٠٥ · زيت «٢ جالون × ٥ لتر» = ١٠ · ملح بلا تغليف = ١٠٠
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "receipt_no": "1", "cycle": "supply", "item_name": "سكر", "qty": "١٠٥",
        "day": "2", "pack_kind": "شكارة", "pack_count": "٢", "pack_capacity": "٥٠",
        "pack_loose": "٥", "producer": "مصانع السكر",
        "store_id": [str(store["id"])], "store_qty": ["١٠٥"]})
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "receipt_no": "2", "cycle": "supply", "item_name": "زيت الطعام", "qty": "١٠",
        "day": "2", "pack_kind": "جالون", "pack_count": "٢", "pack_capacity": "٥",
        "pack_loose": "٠", "producer": "مصانع الزيت",
        "store_id": [str(store["id"])], "store_qty": ["١٠"]})
    _post(client, "/warehouses/wh1/add?cycle=supply", {
        "receipt_no": "3", "cycle": "supply", "item_name": "ملح", "qty": "١٠٠",
        "day": "2", "producer": "منجم الملح",
        "store_id": [str(store["id"])], "store_qty": ["١٠٠"]})
    #     # رصيد أول المدة بالتغليف (دقيق): «٢ شكارة × ٥٠ + ٢٠ سائب» = ١٢٠ — بلا توزيع مخازن
    # (الاسم يفتح الكارت تلقائيًا — الصنف من كتالوج التموين)
    _post(client, "/warehouses/wh3/opener?cycle=supply", {
        "cycle": "supply", "item_name": "دقيق", "qty": "١٢٠", "day": "١",
        "pack_kind": "شكارة", "pack_count": "٢", "pack_capacity": "٥٠",
        "pack_loose": "٢٠", "exp_date": "٠١/٠٦/٢٠٣٢"})
    ent_id = dt.add_entity(YEAR, MONTH, "جهة التجارب", "شرطية")
    rec = dt.add_record(YEAR, MONTH, 5, dt.get_entity(YEAR, MONTH, ent_id), 1, 5, 0, "")
    # إذن ١ (يوم ٥): سكر ٣ كجم + زيت ٣ لتر + ملح ٣ كجم
    dp.save_permit(YEAR, MONTH, {
        "number": 1, "fiscal_year": 2026, "date_from": 5, "date_to": 5,
        "issue_days": 1, "mode": "box", "entity_label": "", "officers": 0,
        "individuals": 1, "recruits": 0, "meals": ["lunch"],
        "record_ids": [rec], "actuals": {
            "tamween_سكر": 3, "tamween_زيت الطعام": 2.742, "tamween_ملح": 3}})
    # إذن ٢ (يوم ١٠): سكر ٦٠ كجم (يسحب السائب ٢ + شكارة كاملة + ٨ من التانية)
    dp.save_permit(YEAR, MONTH, {
        "number": 2, "fiscal_year": 2026, "date_from": 10, "date_to": 10,
        "issue_days": 1, "mode": "box", "entity_label": "", "officers": 0,
        "individuals": 1, "recruits": 0, "meals": ["lunch"],
        "record_ids": [rec], "actuals": {"tamween_سكر": 60}})
    # إذن ٣ (يوم ١٥): دقيق ٦٠ من رصيد أول المدة (٢ شكارة + ٢٠ سائب)
    dp.save_permit(YEAR, MONTH, {
        "number": 3, "fiscal_year": 2026, "date_from": 15, "date_to": 15,
        "issue_days": 1, "mode": "box", "entity_label": "", "officers": 0,
        "individuals": 1, "recruits": 0, "meals": ["lunch"],
        "record_ids": [rec], "actuals": {"tamween_دقيق": 60}})

    rows = dws.tafreeda_rows(YEAR, MONTH, "supply")
    r1 = next(r for r in rows if r["item"] == "سكر" and r["permit_no"] == 1)
    r2 = next(r for r in rows if r["item"] == "سكر" and r["permit_no"] == 2)
    rz = next(r for r in rows if r["item"] == "زيت الطعام")
    rm = next(r for r in rows if r["item"] == "ملح")
    # سكر إذن ١: ٣ كجم من السائب — كاملة ما اتفصتتش
    assert r1["issued_label"] == "٣ كجم سائب", r1["issued_label"]
    assert r1["rem_before_label"] == "٢ شكارة + ٥ كجم سائب", r1["rem_before_label"]
    assert r1["rem_after_label"] == "٢ شكارة + ٢ كجم سائب", r1["rem_after_label"]
    # سكر إذن ٢: ٢ سائب + فتح شكارة كاملة + ٨ من الثانية
    assert r2["issued_label"] == "٢ كجم سائب + شكارة مفتوحة (٨ كجم)", r2["issued_label"]
    assert r2["rem_before_label"] == "٢ شكارة + ٢ كجم سائب", r2["rem_before_label"]
    assert r2["rem_after_label"] == "شكارة مفتوحة (٤٢ كجم)", r2["rem_after_label"]
    # الزيت: ما يتحولش سائب أبدًا — «جالون مفتوح (٣ لتر)» والرصيد «جالون + جالون مفتوح (٢ لتر)»
    assert rz["issued_label"] == "جالون مفتوح (٣ لتر)", rz["issued_label"]
    assert rz["rem_before_label"] == "٢ جالون", rz["rem_before_label"]
    assert rz["rem_after_label"] == "١ جالون كامل + جالون مفتوح (٢ لتر)", rz["rem_after_label"]
    # ملح (دفعة قديمة بلا تغليف): السلوك القديم — تفكيك ساد
    assert rm["issued_label"] == "٣ كجم", rm["issued_label"]
    assert rm["rem_before_label"] == "١٠٠ كجم", rm["rem_before_label"]
    assert rm["rem_after_label"] == "٩٧ كجم", rm["rem_after_label"]
    # دقيق: رصيد أول المدة (٢ شكارة + ٢٠ سائب) — الصرف من السائب أولًا ثم يفتح شكارة
    rd = next(r for r in rows if r["item"] == "دقيق")
    assert rd["qty"] == 60.0
    assert rd["issued_label"] == "٢٠ كجم سائب + شكارة مفتوحة (٤٠ كجم)", rd["issued_label"]
    assert rd["rem_before_label"] == "٢ شكارة + ٢٠ كجم سائب", rd["rem_before_label"]
    assert rd["rem_after_label"] == "١ شكارة كاملة + شكارة مفتوحة (١٠ كجم)", rd["rem_after_label"]
    # FEFO الفعلي ما اتغيرش (أرقام الدفاتر)
    fefo = dws.fefo_actual_map(YEAR, MONTH, "supply")
    assert fefo[(1, "سكر")] == 3 and fefo[(2, "سكر")] == 60
    assert fefo[(1, "زيت الطعام")] == 3 and fefo[(1, "ملح")] == 3
    # مصدر واحد: دفتر ٣ مخازن (taf3) يقرأ نفس تسميات الصرف
    item = next(i for i in dw.list_items(YEAR, MONTH, "supply") if i["name"] == "سكر")
    taf3 = wf.taf3_pack_rows(YEAR, MONTH, "supply", item["id"])
    iss = [r for r in taf3["rows"] if r["kind"] == "issue2"]
    assert iss[0]["issued_pack"] == "٣ كجم سائب", iss[0]["issued_pack"]
    assert iss[1]["issued_pack"] == "٢ كجم سائب + شكارة مفتوحة (٨ كجم)", iss[1]["issued_pack"]
    assert "شكارة مفتوحة (٤٢ كجم)" in taf3["balance_pack"], taf3["balance_pack"]
    # حركة المخازن: رصيد كل سطر + كشف الأرصدة من نفس الحالة (مصدر واحد)
    rep = dws.stores_report(YEAR, MONTH)
    tgt = next(t for t in rep["stores"] if t["store"]["id"] == store["id"])
    out_s = [r for r in tgt["out"] if r["item"] == "سكر"]
    in_s = [r for r in tgt["inn"] if r["item"] == "سكر"]
    assert in_s[0]["rem_after"] == "٢ شكارة + ٥ كجم سائب", in_s[0]["rem_after"]
    assert out_s[0]["rem_after"] == "٢ شكارة + ٢ كجم سائب", out_s[0]["rem_after"]
    assert out_s[1]["rem_after"] == "شكارة مفتوحة (٤٢ كجم)", out_s[1]["rem_after"]
    assert tgt["pack_notes"].get("سكر") == "شكارة مفتوحة (٤٢ كجم)", tgt["pack_notes"].get("سكر")
    assert tgt["pack_notes"].get("زيت الطعام") == "١ جالون كامل + جالون مفتوح (٢ لتر)", tgt["pack_notes"].get("زيت الطعام")
    # الصنف القديم بلا تغليف: تفكيك ساد
    # ملح بلا مواصفات تغليف → مفيش pack_note (العارض بيعرض الرصيد بالوحدة)
    assert "ملح" not in tgt["pack_notes"], tgt["pack_notes"]
    out_m = [r for r in tgt["out"] if r["item"] == "ملح"]
    assert out_m[0]["rem_qty"] == 97.0 and out_m[0]["rem_after"] == "", out_m[0]
    # دقيق (رصيد أول المدة بلا توزيع) → الهدف «غير موزع» بحالة التعبئة نفسها
    una = rep["unassigned"]
    in_d = [r for r in una["inn"] if r["item"] == "دقيق"]
    out_d = [r for r in una["out"] if r["item"] == "دقيق"]
    assert in_d[0]["rem_after"] == "٢ شكارة + ٢٠ كجم سائب", in_d[0]["rem_after"]
    assert out_d[0]["rem_after"] == "١ شكارة كاملة + شكارة مفتوحة (١٠ كجم)", out_d[0]["rem_after"]
    assert una["pack_notes"].get("دقيق") == "١ شكارة كاملة + شكارة مفتوحة (١٠ كجم)", una["pack_notes"]
