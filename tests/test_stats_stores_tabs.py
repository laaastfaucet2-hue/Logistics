# -*- coding: utf-8 -*-
"""تبويبات المخازن الفرعية — الحركة · الصلاحيات · الاستهلاك والتغطية (المرحلة ٢)
+ الجهات · المخازن والتجهيزات · التنبيهات · المقارنة (المرحلة ٣).

كل الأرقام من نفس محرك قسم المخازن، وكل البيانات في مجلد مؤقت (conftest).
"""
from datetime import date

from data_access import db_rations as dr
from data_access import db_stores
from data_access import db_warehouses as dw
from services import stats_stores as ss

from test_stats_stores import MONTH, STORE, TODAY, YEAR, _col, _permit, seed_basic


def _table(view, key):
    return next(t for t in view["tables"] if t["key"] == key)


def _row(table, first):
    return next(r for r in table["rows"] if r[0]["t"] == first)


# ---------------------------------------------------------------- 🔄 الحركة
def test_movement_counts_receipts_and_issue_lines_without_the_opener(app):
    sid = seed_basic()
    dr.add_item(YEAR, MONTH, "tamween", "summer", "عدس", "كجم", 0, 0, 0)
    dw.add_opener(YEAR, MONTH, "supply", "عدس", 40, 1, handle_unit_hint="كجم",
                  exp_iso="2032-01-01", date_iso="2031-09-01", stores=[(sid, STORE, 40)])
    view = ss.build_view("movement", YEAR, MONTH, "month", today=TODAY)
    store = _row(_table(view, "by_store"), STORE)
    head = _table(view, "by_store")
    assert _col(head, store, "عدد إذون الوارد") == "٢"            # أول المدة ليس إذن وارد
    assert _col(head, store, "كمية الوارد") == "٢٠٠٫٠٠٠ كجم"
    assert _col(head, store, "عدد سطور المنصرف") == "٢"           # ١٠٠ من الأولى + ٢٠ من الثانية
    assert _col(head, store, "الصافي") == "٨٠٫٠٠٠ كجم"
    days = [r[0]["t"] for r in _table(view, "by_day")["rows"]]
    assert days == ["٢٠٣١/٠٩/٠١", "٢٠٣١/٠٩/٠٢", "٢٠٣١/٠٩/٠٣"]
    sources = {(r[0]["t"], r[1]["t"]): r[4]["t"] for r in _table(view, "by_source")["rows"]}
    assert sources[("شركة النور", "مطاحن الدلتا")] == "١٠٠٫٠٠٠ كجم"
    yearly = ss.build_view("movement", YEAR, MONTH, "year", today=TODAY)
    assert [r[0]["t"] for r in _table(yearly, "by_month")["rows"]] == ["سبتمبر"]


# ---------------------------------------------------------------- ⏳ الصلاحيات
def test_expiry_counts_live_batches_and_the_opener_with_month_end_for_past_months(app):
    sid = seed_basic()
    dr.add_item(YEAR, MONTH, "tamween", "summer", "عدس", "كجم", 0, 0, 0)
    dw.add_opener(YEAR, MONTH, "supply", "عدس", 40, 1, handle_unit_hint="كجم",
                  exp_iso="2031-09-20", date_iso="2031-09-01", stores=[(sid, STORE, 40)])
    view = ss.build_view("expiry", YEAR, MONTH, "month", today=TODAY)
    batches = _table(view, "batches")
    sources = [_col(batches, r, "المصدر") for r in batches["rows"]]
    assert "رصيد أول المدة" in sources and "إذن إضافة ١" not in sources   # المستهلكة كلها خارج
    opener = next(r for r in batches["rows"] if _col(batches, r, "المصدر") == "رصيد أول المدة")
    assert _col(batches, opener, "الحالة") == "خطر" and _col(batches, opener, "الأيام الباقية") == "٥"
    # بعد انتهاء الشهر: الحساب لآخر يوم في سبتمبر ⇒ منتهية (ولا يتغير بعدها كل يوم)
    later = ss.build_view("expiry", YEAR, MONTH, "month", today=date(2031, 12, 1))
    row = next(r for r in _table(later, "batches")["rows"]
               if _col(batches, r, "المصدر") == "رصيد أول المدة")
    assert _col(batches, row, "الحالة") == "منتهية"
    levels = {r[0]["t"]: r[1]["t"] for r in _table(later, "levels")["rows"]}
    assert levels["منتهية"] == "١" and levels["خطر"] == "٠"
    yearly = ss.build_view("expiry", YEAR, MONTH, "year", today=date(2031, 12, 1))
    assert _table(yearly, "expired_year")["rows"]


# ---------------------------------------------------------------- 📉 الاستهلاك والتغطية
def test_store_coverage_uses_its_own_rate_and_item_uses_the_total_rate(app):
    db_stores.add_store("مخزن أ")
    db_stores.add_store("مخزن ب")
    a, b = (s["id"] for s in db_stores.list_stores())
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز", "كجم", 0, 0, 0)
    dw.add_receipt(YEAR, MONTH, "supply", 1, "أرز", 100, "كجم", exp_iso="2031-11-01",
                   date_iso="2031-09-01", stores=[(a, "مخزن أ", 100)])
    dw.add_receipt(YEAR, MONTH, "supply", 2, "أرز", 100, "كجم", exp_iso="2032-05-01",
                   date_iso="2031-09-02", receipt_no=2, stores=[(b, "مخزن ب", 100)])
    _permit(MONTH, 1, 3, 120)                      # ١٠٠ من «أ» (الأقرب صلاحية) + ٢٠ من «ب»
    view = ss.build_view("consumption", YEAR, MONTH, "month", today=TODAY)   # ١٥ يومًا
    item = _table(view, "by_item")
    assert _col(item, item["rows"][0], "أيام التغطية") == "١٠"     # ٨٠ ÷ (١٢٠ ÷ ١٥)
    stores = _table(view, "by_store")
    row_b = _row(stores, "مخزن ب")
    assert _col(stores, row_b, "أيام التغطية") == "٦٠"            # ٨٠ ÷ (٢٠ ÷ ١٥) — معدله هو
    assert _col(stores, row_b, "متوسط اليوم") == "١٫٣٣٣"
    row_a = _row(stores, "مخزن أ")
    assert _col(stores, row_a, "الحالة") == "نفد"
    balances = ss.build_view("balances", YEAR, MONTH, "month", today=TODAY)
    store_b = _table(balances, f"store_{b}")
    assert _col(store_b, store_b["rows"][0], "متوقع النفاد") == "٢٠٣١/١١/١٤"


# ---------------------------------------------------------------- 🏢 الجهات المستلمة
def test_entities_split_main_and_attached_and_keep_units(app):
    seed_basic()
    _permit(MONTH, 2, 5, 30, entity="الكتيبة الأولى + سرية الدعم")
    view = ss.build_view("entities", YEAR, MONTH, "month", today=TODAY)
    cards = {c["label"]: c["value"] for c in view["cards"]}
    assert cards["الجهات"] == "٣"                      # جهة الاختبار + الكتيبة + السرية
    assert cards["إذون الصرف"] == "٢"
    by_entity = _table(view, "by_entity")
    row = _row(by_entity, "الكتيبة الأولى + سرية الدعم")
    assert _col(by_entity, row, "عدد الإذون") == "١"
    assert _col(by_entity, row, "الكميات") == "٣٠٫٠٠٠ كجم"
    assert _col(by_entity, row, "المخازن") == STORE
    assert _table(view, "entity_item")["rows"] and _table(view, "store_entity")["rows"]
    yearly = ss.build_view("entities", YEAR, MONTH, "year", today=TODAY)
    month_table = _table(yearly, "entity_month")
    assert month_table["head"][-1] == "الإجمالي" and "سبتمبر" in month_table["head"]


# ---------------------------------------------------------------- 🏬 المخازن والتجهيزات
def test_registry_shows_specs_movement_and_missing_data(app):
    seed_basic()
    db_stores.add_store("ثلاجة التبريد", "الجناح الغربي", 40, 2, 1, "ترموستات", "")
    view = ss.build_view("registry", YEAR, MONTH, "month", today=TODAY)
    stores = _table(view, "stores")
    full = _row(stores, "ثلاجة التبريد")
    assert _col(stores, full, "المساحة (م²)") == "٤٠" and _col(stores, full, "المراوح") == "٢"
    assert _col(stores, full, "حركات الوارد") == "٠"
    busy = _row(stores, STORE)
    assert _col(stores, busy, "حركات الوارد") == "٢" and _col(stores, busy, "حركات المنصرف") == "٢"
    assert _col(stores, busy, "آخر حركة") == "٢٠٣١/٠٩/٠٣"
    cards = {c["label"]: c["value"] for c in view["cards"]}
    assert cards["بلا حركة"] == "١" and cards["بيانات ناقصة"] == "١"


# ---------------------------------------------------------------- 🚨 التنبيهات
def test_alerts_cover_shortfall_expiry_and_carry_over_without_unassigned(app):
    sid = seed_basic()
    dr.add_item(YEAR, MONTH, "tamween", "summer", "عدس", "كجم", 0, 0, 0)
    dw.add_receipt(YEAR, MONTH, "supply", 4, "عدس", 10, "كجم", exp_iso="2031-09-10",
                   date_iso="2031-09-04", receipt_no=3)    # من غير توزيع ⇒ «مخزن 1» ومنتهية
    _permit(MONTH, 2, 6, 500)                                        # أرز: المطلوب أكثر من المتاح
    view = ss.build_view("alerts", YEAR, MONTH, "month", today=TODAY)
    rows = _table(view, "alerts")["rows"]
    kinds = {r[0]["t"] for r in rows}
    assert {"صلاحية منتهية", "عجز في الصرف", "بيانات مخزن ناقصة"} <= kinds
    assert "رصيد غير موزع" not in kinds and [t["key"] for t in view["tables"]] == ["alerts"]
    expired = next(r for r in rows if r[0]["t"] == "صلاحية منتهية")
    assert expired[1]["t"] == STORE and expired[2]["t"] == "عدس"
    # السنوي: أغسطس بلا بيانات وسبتمبر بأول مدة مختلف عن آخر الشهر السابق ⇒ فرق ترحيل
    dr.add_item(YEAR, 10, "tamween", "summer", "أرز", "كجم", 0, 0, 0)
    dw.add_opener(YEAR, 10, "supply", "أرز", 15, 1, handle_unit_hint="كجم",
                  exp_iso="2032-01-01", date_iso="2031-10-01", stores=[(sid, STORE, 15)])
    yearly = ss.build_view("alerts", YEAR, 10, "year", today=date(2031, 10, 5))
    carries = _table(yearly, "carries")
    assert carries["rows"] and carries["rows"][0][5]["t"] == "أكتوبر"


# ---------------------------------------------------------------- 📈 المقارنة والاتجاه
def test_compare_has_previous_month_same_month_last_year_and_trend(app):
    from data_access import months, storage
    seed_basic()
    storage.create_year(YEAR - 1)
    months.init_month(YEAR - 1, MONTH)
    dr.add_item(YEAR - 1, MONTH, "tamween", "summer", "أرز", "كجم", 0, 0, 0)
    dw.add_receipt(YEAR - 1, MONTH, "supply", 1, "أرز", 50, "كجم", exp_iso="2031-01-01",
                   date_iso="2030-09-01")
    view = ss.build_view("compare", YEAR, MONTH, "month", today=TODAY)
    table = _table(view, "indicators")
    assert table["head"] == ["المؤشر", "هذا الشهر", "الشهر السابق",
                             "نفس الشهر من السنة السابقة", "نسبة التغير"]
    receipts = _row(table, "إذون الإضافة")
    assert _col(table, receipts, "هذا الشهر") == "٢"
    assert _col(table, receipts, "نفس الشهر من السنة السابقة") == "١"
    yearly = ss.build_view("compare", YEAR, MONTH, "year", today=TODAY)
    trend = _table(yearly, "trend")
    assert trend["head"][0] == "المؤشر" and "سبتمبر" in trend["head"]
    assert any(r[0]["t"] == f"حركات {STORE}" for r in trend["rows"])
