"""وحدات القياس الموحّدة + مدن/قرى المحافظات (إضافة يدوية)."""
from core.config import UNITS
from core.recruit_vocab import GOV_CITIES
from data_access import database, db_rations, db_recruits, months


def test_egypt_has_27_governorates_and_sinai_centers():
    assert len(GOV_CITIES) == 27
    north = GOV_CITIES["شمال سيناء"]
    for name in ("العريش", "الحسنة", "نخل", "بئر العبد", "الجفجافة"):
        assert name in north
    assert "الطور" in GOV_CITIES["جنوب سيناء"]


def test_units_merge_tamween_contractor_and_custom(app):
    months.init_month(2031, 9)
    db_rations.add_item(2031, 9, "tamween", "summer", "أرز", "شيكارة", 1, 1, 1)
    db_rations.add_item(2031, 9, "contractor", "summer", "زيت", "جردل", 1, 1, 1)
    db_rations.remember_unit("ربطة خاصة")
    units = db_rations.collect_units(2031, 9)
    for u in UNITS:
        assert u in units
    assert units.index("كجم") < units.index("شيكارة")
    assert "شيكارة" in units
    assert "جردل" in units
    assert "ربطة خاصة" in units


def test_custom_village_is_remembered_under_governorate(app):
    months.init_month(2031, 9)
    db_recruits.add_recruit(2031, 9, {
        "name": "مجند تجريبي", "mil_no": "99001",
        "governorate": "شمال سيناء", "city": "قرية المليز الشرقية",
    })
    mapping = db_recruits.places_by_gov(2031, 9)
    assert "قرية المليز الشرقية" in mapping["شمال سيناء"]
    assert "قرية المليز الشرقية" in database.vocab_list("place", parent="شمال سيناء")
    govs = db_recruits.govs_for_ui(2031, 9)
    assert govs[:27] == list(GOV_CITIES.keys())


def test_rations_page_lists_shared_units(client):
    months.init_month(2031, 9)
    db_rations.remember_unit("وحدة اختبار")
    page = client.get("/rations/tamween?year=2031&month=9").text
    assert "وحدة اختبار" in page
    assert "قائمة موحّدة للتموين والمتعهد" in page
    rec = client.get("/recruits/?year=2031&month=9").text
    assert "المدينة / القرية" in rec
    assert "rcPlacesMap" in rec
    assert "الحسنة" in rec
