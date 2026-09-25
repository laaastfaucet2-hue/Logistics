# -*- coding: utf-8 -*-
"""قسم التاميدات: عزل شهري، قاموس، سجلات، ملحقات، نسخ/لصق، تنبيه راغبين،
فولدرات محلية بأسماء التويبات، تقرير شامل (Excel بالدباجة واللوجو + Word)،
وتأكيدات حفظ مرئية بعد الكتابة المحلية فعلًا."""
import json
import re
from urllib.parse import unquote

import pytest
from openpyxl import load_workbook

from data_access import database, storage
from data_access import db_tameedat as dt
from data_access import db_letterhead as lhdb
from services import tameedat_fs
from documents import xlsx_tameedat, docx_tameedat
from routes.tameedat import files as routes_tameedat

YEAR, MONTH = 2031, 9


def _ctx(month=MONTH):
    database.set_user_context(1, YEAR, month)


def _get(client, url):
    response = client.get(url)
    assert response.status_code == 200, url
    return response


def _toast(response):
    """نص رسالة التأكيد بعد إعادة التوجيه (ok/err/warn في رابط الهدف)."""
    location = response.headers.get("Location", "")
    assert response.status_code == 302
    return unquote(location)


# ======================================================================
# الدخول والترويسة والتويبات
# ======================================================================
def test_section_listing_opens_real_tameedat_page(client):
    _ctx()
    assert client.get("/sections/tameedat").status_code == 302
    page = _get(client, "/tameedat/")
    assert "قطاع وسط سيناء - قسم التميينات" in page.text
    assert "منطقة وسط وجنوب للأمن المركزي" in page.text
    for tab in ("تأميدات اليوم المحدد", "الجهات المومدة بالشهر الحالي",
                "قاموس ودليل الجهات", "طباعة التقرير الشامل"):
        assert tab in page.text


# ======================================================================
# القاموس الشهري
# ======================================================================
def test_dictionary_starts_empty_and_save_confirmation_is_visible(client):
    _ctx()
    assert dt.list_entities(YEAR, MONTH) == []
    page = _get(client, "/tameedat/?tab=dict")
    assert "القاموس فارغ" in page.text
    response = client.post("/tameedat/entities/add", data={
        "name": "كمين المساعيد", "type_choice": "حربية",
        "rag_officers": "٥", "rag_individuals": "٤٠"})
    toast = _toast(response)
    assert "تم حفظ بيانات الجهة «كمين المساعيد»" in toast
    assert "وتسجيلها في البيانات المحلية." in toast
    page = _get(client, toast.split("?", 1)[1] if toast.startswith("http") else
                "/tameedat/?tab=dict")
    assert "كمين المساعيد" in page.text and "حربية" in page.text
    entity = dt.find_entity_by_name(YEAR, MONTH, "كمين المساعيد")
    assert entity["rag_officers"] == 5 and entity["rag_individuals"] == 40


def test_dictionary_duplicate_rejected(client):
    _ctx()
    dt.add_entity(YEAR, MONTH, "وحدة الجوابات", "شرطية")
    response = client.post("/tameedat/entities/add", data={
        "name": "وحدة  الجوابات", "type_choice": "شرطية"})
    assert "موجودة بالفعل في قاموس هذا الشهر" in _toast(response)


def test_dictionary_edit_updates_record_snapshots(client):
    _ctx()
    eid = dt.add_entity(YEAR, MONTH, "وحدة التموين المركزية", "شرطية")
    entity = dt.get_entity(YEAR, MONTH, eid)
    dt.add_record(YEAR, MONTH, 3, entity, 1, 2, 3)
    response = client.post(f"/tameedat/entities/edit/{eid}", data={
        "name": "وحدة التموين الرئيسية", "type_choice": "أخرى",
        "type_other": "مدنية", "rag_officers": "", "rag_individuals": ""})
    toast = _toast(response)
    assert "تم تعديل بيانات الجهة" in toast
    assert "وحفظ التعديلات في البيانات المحلية." in toast
    record = dt.month_records(YEAR, MONTH)[0]
    assert record["entity_name"] == "وحدة التموين الرئيسية"
    assert record["entity_type"] == "مدنية"


# ======================================================================
# السجلات اليومية
# ======================================================================
def test_unknown_entity_warned_then_added_on_save(client):
    _ctx()
    response = client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "سرية الحراسات",
        "type_choice": "شرطية", "officers": "٣", "individuals": "٢٠", "recruits": "٥٠"})
    toast = _toast(response)
    assert "الجهة كانت غير مسجلة فأُضيفت إلى قاموس الشهر" in toast
    assert "وتسجيلها في البيانات المحلية." in toast
    assert dt.find_entity_by_name(YEAR, MONTH, "سرية الحراسات") is not None
    record = dt.month_records(YEAR, MONTH)[0]
    assert (record["officers"], record["individuals"], record["recruits"]) == (3, 20, 50)
    assert record["total"] == 73


def test_day_must_stay_inside_active_month(client):
    _ctx()
    response = client.post("/tameedat/records/add", data={
        "day": "٢٢/١٠/٢٠٣١", "entity_name": "فوج أسيوط", "officers": "1"})
    assert "التاريخ خارج الشهر النشط" in _toast(response)
    assert dt.month_records(YEAR, MONTH) == []
    response = client.post("/tameedat/records/add", data={
        "day": "09/22/2031", "entity_name": "فوج أسيوط", "officers": "1"})
    assert "التاريخ غير صالح" in _toast(response)


def test_zero_total_rejected_and_counts_validated(client):
    _ctx()
    response = client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "فوج أسيوط"})
    assert "سجّل عددًا واحدًا على الأقل" in _toast(response)
    response = client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "فوج أسيوط", "officers": "abc"})
    assert "عدد الضباط غير صالح" in _toast(response)


def test_attachments_merge_into_parent_totals(client):
    _ctx()
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "معسكر الشيخ زويد", "type_choice": "حربية",
        "officers": "5", "individuals": "40", "recruits": "100",
        "att_name": ["سرية ملحقة"], "att_type": ["حربية"],
        "att_officers": ["2"], "att_individuals": ["10"], "att_recruits": ["30"]})
    record = dt.month_records(YEAR, MONTH)[0]
    assert record["total"] == 145 and record["grand_total"] == 187
    page = _get(client, "/tameedat/?tab=day&day=٢٢/٠٩/٢٠٣١")
    # تأميدة واحدة بملحقاتها = صف واحد بقيم مكدّسة منسقة (طلب المستخدم)
    assert 'class="tm-main"' in page.text and 'class="tm-attrow"' not in page.text
    assert page.text.count('class="num stack"') == 4      # ضباط/أفراد/مجندين/الإجمالي
    assert "ملحقة: سرية ملحقة" in page.text               # اسم الملحقة داخل الصف نفسه
    assert "إجمالي التأميدة — تأميدة <b>واحدة</b>" in page.text
    assert "١٨٧" in page.text                             # إجماليها في خلية الإجمالي
    assert page.text.count('class="tm-print-mini"') == 1  # ورابط طباعتها معها


def test_record_has_four_distinct_actions_edit_copy_permit_delete(client):
    """الأزرار الأربعة بجانب التأميدة: تعديل، نسخ، إذن ٢ مخازن، حذف."""
    _ctx()
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة الأزرار",
        "officers": "1", "individuals": "2", "recruits": "3"})
    page = _get(client, "/tameedat/?tab=day&day=٢٢/٠٩/٢٠٣١")
    assert 'class="tm-actions"' in page.text
    for hook in ("tm-edit", "tm-copy", "tm-permit", "tm-delete"):
        assert hook in page.text, hook
    assert page.text.count("tm-print-mini") == 1  # طباعة المستند تظل متاحة
    record = dt.month_records(YEAR, MONTH)[0]
    assert f"/tameedat/records/delete/{record['id']}" in page.text
    assert 'onsubmit="return confirm(' in page.text
    assert "<bdi" not in re.search(r'onsubmit="([^"]*)"', page.text).group(1)


def test_delete_record_cascades_attachments_and_updates_local_files(client):
    _ctx()
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة التراجع", "type_choice": "شرطية",
        "officers": "5", "individuals": "40", "recruits": "100",
        "att_name": ["سرية ملحقة للحذف"], "att_type": ["شرطية"],
        "att_officers": ["2"], "att_individuals": ["10"], "att_recruits": ["30"]})
    record = dt.month_records(YEAR, MONTH)[0]
    response = client.post(f"/tameedat/records/delete/{record['id']}")
    assert "تم حذف تأميدة" in _toast(response) and "من البيانات المحلية" in _toast(response)
    assert dt.month_records(YEAR, MONTH) == []
    page = _get(client, "/tameedat/?tab=day&day=٢٢/٠٩/٢٠٣١")
    assert "لا توجد تأميدات مسجلة في هذا اليوم" in page.text  # سطر التأميدة اختفى
    body = re.search(r"<tbody>(.*?)</tbody>", page.text, re.S).group(1)
    assert "سرية ملحقة للحذف" not in body      # الملحقة حذفت معها من الجدول
    assert "وحدة التراجع" not in body          # والتأميدة نفسها — القاموس يبقى بنفسه
    assert 'class="tm-act-delete"' not in page.text
    mirror = json.loads((tameedat_fs.base_dir(YEAR, MONTH)
                         / tameedat_fs.TAB_FOLDERS["day"] / "سجلات التأميدات.json")
                        .read_text(encoding="utf-8"))
    assert mirror["عدد السجلات"] == 0  # المرآة المحلية تتحدث مع الحذف
    xlsx_mirror = tameedat_fs.base_dir(YEAR, MONTH) / tameedat_fs.TAB_FOLDERS["day"] / "سجلات التأميدات.xlsx"
    assert xlsx_mirror.is_file() and xlsx_mirror.read_bytes()[:2] == b"PK"   # ملف Excel حقيقي
    again = client.post("/tameedat/records/delete/9999")
    assert "غير موجودة" in _toast(again)


def test_duplicate_entity_same_day_allowed_as_separate_records(client):
    _ctx()
    for _ in range(2):
        client.post("/tameedat/records/add", data={
            "day": "٢٢/٠٩/٢٠٣١", "entity_name": "كمين رفح", "officers": "1",
            "individuals": "5", "recruits": "20"})
    records = dt.records_for_day(YEAR, MONTH, 22)
    assert len(records) == 2 and records[0]["id"] != records[1]["id"]


def test_edit_record_saves_and_confirms(client):
    _ctx()
    entity_id = dt.add_entity(YEAR, MONTH, "كمين الشيخ زويد", "شرطية")
    dt.add_record(YEAR, MONTH, 5, dt.get_entity(YEAR, MONTH, entity_id), 2, 10, 30)
    record_id = dt.month_records(YEAR, MONTH)[0]["id"]
    response = client.post(f"/tameedat/records/edit/{record_id}", data={
        "day": "٠٧/٠٩/٢٠٣١", "officers": "٤", "individuals": "١٢",
        "recruits": "٢٨", "notes": "تعديل مقصود"})
    toast = _toast(response)
    assert "تم تعديل بيانات تأميدة «كمين الشيخ زويد»" in toast
    assert "وحفظ التعديلات في البيانات المحلية." in toast
    record = dt.get_record(YEAR, MONTH, record_id)
    assert record["day"] == 7 and record["total"] == 44


def test_copy_paste_creates_separate_record_with_attachments(client):
    _ctx()
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة المعلومات", "officers": "2",
        "individuals": "8", "recruits": "15",
        "att_name": ["فصيلة"], "att_officers": ["1"], "att_individuals": ["4"],
        "att_recruits": ["9"]})
    source = dt.month_records(YEAR, MONTH)[0]
    response = client.post(f"/tameedat/records/copy/{source['id']}",
                           data={"to_day": "٢٥"})
    toast = _toast(response)
    assert "تم لصق نسخة منفصلة" in toast
    assert "بالجهات المومدة الملحقة" in toast  # النسخ ينقل الملحقات معه
    pasted = dt.records_for_day(YEAR, MONTH, 25)[0]
    assert pasted["id"] != source["id"]
    assert pasted["entity_name"] == "وحدة المعلومات"
    assert pasted["attachments"][0]["name"] == "فصيلة"
    assert pasted["grand_total"] == source["grand_total"]


def test_copy_mode_page_renders_banner_and_paste_box(client):
    _ctx()
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة النسخ", "officers": "2",
        "individuals": "7", "recruits": "12"})
    record = dt.month_records(YEAR, MONTH)[0]
    page = _get(client, f"/tameedat/?tab=day&day=٢٢/٠٩/٢٠٣١&copy={record['id']}")
    assert "tm-copybar" in page.text
    assert "نُسخت تأميدة" in page.text and "وحدة النسخ" in page.text
    other_day = _get(client, f"/tameedat/?tab=day&day=٢٥/٠٩/٢٠٣١&copy={record['id']}")
    assert "لصق هنا يوم" in other_day.text  # زر اللصق يظهر ليوم مختلف
    same_day = _get(client, f"/tameedat/?tab=day&day=٢٢/٠٩/٢٠٣١&copy={record['id']}")
    assert "لصق هنا يوم" not in same_day.text  # لا لصق فوق يوم التأميدة نفسه
    assert "اختر يومًا آخر من التقويم" in same_day.text


def test_raghebeen_excess_is_warning_only_saves_normally(client):
    _ctx()
    client.post("/tameedat/entities/add", data={
        "name": "كمين العريش", "type_choice": "شرطية",
        "rag_officers": "٥", "rag_individuals": "٤٠"})
    response = client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "كمين العريش",
        "officers": "٦", "individuals": "٤٥", "recruits": "٩٩٩"})
    toast = _toast(response)
    assert "warn=" in toast and "تنبيه:" in toast
    assert "الضباط (٦) أكثر من راغبين الضباط المسجلين (٥)" in toast
    assert "الأفراد (٤٥) أكثر من راغبين الأفراد المسجلين (٤٠)" in toast
    assert "٩٩٩" not in toast  # المجندون خارج مقارنة الراغبين تمامًا
    assert "تم الحفظ رغم ذلك حسب رغبتك" in toast
    assert len(dt.month_records(YEAR, MONTH)) == 1  # لم يُمنع الحفظ


def test_type_filters_and_search(client):
    _ctx()
    for name, choice, other in (("كمين أ", "شرطية", ""), ("كتيبة ب", "حربية", ""),
                                ("مستشفى ج", "أخرى", "مدنية")):
        data = {"day": "٢٢/٠٩/٢٠٣١", "entity_name": name, "officers": "1",
                "type_choice": choice}
        if other:
            data["type_other"] = other
        client.post("/tameedat/records/add", data=data)
    assert len(dt.records_for_day(YEAR, MONTH, 22, "police")) == 1
    assert len(dt.records_for_day(YEAR, MONTH, 22, "war")) == 1
    assert len(dt.records_for_day(YEAR, MONTH, 22, "other")) == 1
    assert len(dt.records_for_day(YEAR, MONTH, 22, "all")) == 3
    assert len(dt.records_for_day(YEAR, MONTH, 22, "all", "مستشفى")) == 1


# ======================================================================
# العزل الشهري
# ======================================================================
def test_months_are_fully_isolated(client):
    _ctx()
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة سبتمبر", "officers": "3"})
    assert len(dt.month_records(YEAR, 9)) == 1
    assert dt.month_records(YEAR, 10) == []
    assert dt.list_entities(YEAR, 10) == []
    _ctx(10)
    page = _get(client, "/tameedat/")
    assert "وحدة سبتمبر" not in page.text
    _ctx()


# ======================================================================
# الفولدرات المحلية بأسماء التويبات
# ======================================================================
def test_local_folders_named_after_tabs_with_fresh_snapshots(client):
    _ctx()
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة الحدود", "type_choice": "حربية",
        "officers": "4", "individuals": "22", "recruits": "61"})
    base = tameedat_fs.base_dir(YEAR, MONTH)
    assert base.name == "07-التاميدات"
    assert base.parent.name == "09-سبتمبر"
    for tab, folder in tameedat_fs.TAB_FOLDERS.items():
        assert (base / folder).is_dir(), folder
    records = json.loads((base / tameedat_fs.TAB_FOLDERS["day"]
                          / "سجلات التأميدات.json").read_text(encoding="utf-8"))
    assert records["السجلات"][0]["الجهة"] == "وحدة الحدود"
    assert records["القسم"] == "قطاع وسط سيناء - قسم التميينات"
    dictionary = json.loads((base / tameedat_fs.TAB_FOLDERS["dict"]
                             / "قاموس الجهات.json").read_text(encoding="utf-8"))
    assert dictionary["الجهات"][0]["النوع"] == "حربية"
    summary = json.loads((base / tameedat_fs.TAB_FOLDERS["momoda"]
                          / "ملخص الجهات المومدة.json").read_text(encoding="utf-8"))
    assert summary["إجمالي القوة"] == 87


# ======================================================================
# منع الازدواج (الضغط المزدوج/إعادة الإرسال) + المدة الزمنية + استقلال الملحقات
# ======================================================================
def test_duplicate_submit_with_same_token_creates_one_record(client):
    """شكوى المستخدم: ضغطة واحدة كانت تسجّل تأميدتين — التوكن يمنعها تمامًا."""
    _ctx()
    page = _get(client, "/tameedat/")
    token = re.search(r'name="save_token" value="([^"]+)"', page.text).group(1)
    form = {"day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة المنع", "officers": "3",
            "individuals": "20", "recruits": "80", "save_token": token}
    first = client.post("/tameedat/records/add", data=form)
    assert "وتسجيلها في البيانات المحلية." in _toast(first)
    second = client.post("/tameedat/records/add", data=form)
    assert "تجاهلنا الإرسال المكرر" in _toast(second)
    assert "محفوظة بالفعل" in _toast(second)
    assert len(dt.month_records(YEAR, MONTH)) == 1
    page_after = _get(client, "/tameedat/?tab=day&day=٢٢/٠٩/٢٠٣١")
    assert page_after.text.count('class="tm-main"') == 1


def test_time_range_covers_every_day_and_scales_monthly_totals(client):
    """تفعيل مدة زمنية: التأميدة الواحدة تظهر سارية في كل أيام من يوم إلى يوم."""
    _ctx()
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة المدة", "officers": "٥",
        "individuals": "٣٥", "recruits": "١٦٠", "range_enabled": "1", "day_to": "٢٥"})
    record = dt.month_records(YEAR, MONTH)[0]
    assert record["day_to"] == 25 and record["range_days"] == 4
    for day in (22, 23, 24, 25):  # سارية في كل أيام المدة على الصفحة
        assert dt.records_for_day(YEAR, MONTH, day)[0]["entity_name"] == "وحدة المدة"
    for day in (22, 23, 24, 25):  # وعلامات التقويم تغطي المدة كلها
        assert dt.day_counts(YEAR, MONTH).get(day) == 1
    page = _get(client, "/tameedat/?tab=day&day=٢٣/٠٩/٢٠٣١")
    assert "وحدة المدة" in page.text          # سارية يوم ٢٣ رغم أن تاريخها ٢٢
    assert "من ٢٢ إلى ٢٥" in page.text        # شارة المدة في الجدول
    summary, totals = dt.month_summary(YEAR, MONTH)  # المومدة: ٤ أيام × قوة يومية
    assert summary[0]["active_days"] == 4 and summary[0]["grand_total"] == 800
    assert summary[0]["avg_officers"] == 5 and summary[0]["avg_recruits"] == 160
    momoda_page = _get(client, "/tameedat/?tab=momoda")
    assert "٨٠٠" in momoda_page.text and "متوسط ضباط" not in momoda_page.text   # المتوسطات انتقلت إلى القاموس
    dict_page = _get(client, "/tameedat/?tab=dict")
    assert "متوسط ضباط" in dict_page.text and "متوسط أفراد" in dict_page.text
    assert "متوسط مجندين" in dict_page.text and "عدد التأميدات" in dict_page.text
    assert "ملحقة؟" in dict_page.text and "افتح التواريخ" in dict_page.text


def test_from_to_fields_define_the_tameedah_span(client):
    """«من يوم / إلى يوم» بدل التاريخ والمفتاح: المتساويان يومٌ واحد، الأوسع مدة سارية."""
    _ctx()
    client.post("/tameedat/records/add", data={
        "day_from": "١", "day_to": "١", "entity_name": "وحدة اليوم الواحد", "officers": "٧"})
    single = dt.month_records(YEAR, MONTH)[0]
    assert single["day"] == 1 and single.get("day_to") in (None, 1) and single["range_days"] == 1
    client.post("/tameedat/records/add", data={
        "day_from": "٥", "day_to": "٧", "entity_name": "وحدة المدى", "officers": "٣"})
    ranged = dt.month_records(YEAR, MONTH)[1]
    assert ranged["day"] == 5 and ranged["day_to"] == 7 and ranged["range_days"] == 3
    for day in (5, 6, 7):
        assert dt.records_for_day(YEAR, MONTH, day)[-1]["entity_name"] == "وحدة المدى"
    reversed_ = client.post("/tameedat/records/add", data={
        "day_from": "١٠", "day_to": "٤", "entity_name": "وحدة مقلوبة", "officers": "٣"})
    assert "لا يسبق" in _toast(reversed_)
    beyond = client.post("/tameedat/records/add", data={
        "day_from": "٢", "day_to": "٣٣", "entity_name": "وحدة خارجة", "officers": "٣"})
    assert "لا تعبر شهرًا آخر" in _toast(beyond)
    missing = client.post("/tameedat/records/add", data={
        "day_to": "٥", "entity_name": "وحدة ناقصة", "officers": "٣"})
    assert "«من يوم»" in _toast(missing)
    assert len(dt.month_records(YEAR, MONTH)) == 2


def test_range_validation_blocks_reversed_and_cross_month(client):
    _ctx()
    reversed = client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة المدة", "officers": "1",
        "range_enabled": "1", "day_to": "٢١"})
    assert "لا يسبق يوم التأميدة" in _toast(reversed)
    beyond = client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة المدة", "officers": "1",
        "range_enabled": "1", "day_to": "٣٥"})
    assert "لا تعبر شهرًا آخر" in _toast(beyond)
    missing = client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة المدة", "officers": "1",
        "range_enabled": "1"})
    assert "«إلى يوم»" in _toast(missing)
    assert dt.month_records(YEAR, MONTH) == []


def test_attachments_are_independent_in_momoda_and_dictionary(client):
    """الملحقة جهة قائمة بنفسها: صف مستقل في المومدة، تسجيل تلقائي بالقاموس،
    وإجمالي القوة = القوة الحقيقية مرة واحدة بلا تكرار ولا دمج."""
    _ctx()
    response = client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "قطاع وسط سيناء", "type_choice": "شرطية",
        "officers": "٢", "individuals": "٣٨", "recruits": "١٦٠",
        "att_name": ["قطاع الشهيد أشرف جاد"], "att_type": ["شرطية"],
        "att_officers": ["١"], "att_individuals": ["٤٩"], "att_recruits": ["١٥٠"]})
    toast = _toast(response)
    assert "الجهة الملحقة «قطاع الشهيد أشرف جاد»" in toast  # إشعار انضمامها للقاموس
    summary, totals = dt.month_summary(YEAR, MONTH)
    assert len(summary) == 2
    main = next(r for r in summary if r["kind"] == "entity")
    att = next(r for r in summary if r["kind"] == "attachment")
    assert main["grand_total"] == 200 and att["grand_total"] == 200
    assert main["total_officers"] == 2 and att["total_officers"] == 1
    assert totals["grand"] == 400        # ٢٠٠ + ٢٠٠ — بلا ضغط مزدوج ولا دمج
    assert totals["records"] == 1        # تأميدة واحدة فقط مهما كثرت الجهات
    toast_hint = dt.find_entity_by_name(YEAR, MONTH, "قطاع الشهيد أشرف جاد")
    assert toast_hint is not None        # الملحقة انضمت للقاموس تلقائيًا
    assert dt.entity_record_count(YEAR, MONTH, toast_hint["id"]) == 1
    page = _get(client, "/tameedat/?tab=momoda")
    assert 'class="tm-att-badge"' in page.text and "قطاع الشهيد أشرف جاد" in page.text
    assert "القوة الفعلية مرة واحدة" in page.text
    dictionary_page = _get(client, "/tameedat/?tab=dict")
    assert "قطاع الشهيد أشرف جاد" in dictionary_page.text
    assert "ملحقة ×١" in dictionary_page.text              # حالة الملحقة وعدد مراتها في القاموس
    assert "ملحقة على تأميدة «قطاع وسط سيناء»" in dictionary_page.text  # وعلى مَن داخل قائمة التواريخ


def test_each_tab_has_named_open_folder_and_file_buttons(client):
    """قاعدة أزرار الملفات: كل تويب بزرّي فتح المجلد/الملف باسميهما الصريحين."""
    _ctx()
    expectations = {
        "day": ("فتح مجلد «تأميدات اليوم المحدد»", "فتح ملف «سجلات التأميدات.xlsx»"),
        "momoda": ("فتح مجلد «الجهات المومدة بالشهر الحالي»",
                   "فتح ملف «ملخص الجهات المومدة.xlsx»"),
        "dict": ("فتح مجلد «قاموس ودليل الجهات»", "فتح ملف «قاموس الجهات.xlsx»"),
        "report": ("فتح مجلد «طباعة التقرير الشامل»", "فتح ملف «التقرير الشامل.xlsx»"),
    }
    for tab, (folder_label, file_label) in expectations.items():
        page = _get(client, f"/tameedat/?tab={tab}")
        assert folder_label in page.text, tab                  # اسم المجلد على زره
        assert file_label in page.text, tab                    # اسم الملف على زره
        assert f"/tameedat/open-folder/{tab}" in page.text
        assert f"/tameedat/open-file/{tab}" in page.text
        assert "tm-openbar" in page.text


def test_tab_open_routes_behave_in_web_preview_and_desktop(client, monkeypatch):
    """فتح المجلد/الملف: برسائل صادقة عن وضع المعاينة — وبنجاح حقيقي على سطح المكتب."""
    _ctx()
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة المجلد", "officers": "٥",
        "individuals": "٣٥", "recruits": "١٦٠"})
    # معاينة الويب: الفتح المحلي غير متاح → رسالة واضحة بدل تظاهر النجاح
    monkeypatch.setattr(routes_tameedat, "_open_path", lambda path: False)
    page = client.get("/tameedat/open-folder/day", follow_redirects=True).data.decode()
    assert "نسخة سطح المكتب" in page and "تأميدات اليوم المحدد" in page
    page = client.get("/tameedat/open-file/day", follow_redirects=True).data.decode()
    assert "سجلات التأميدات.xlsx" in page and "نسخة سطح المكتب" in page
    # سطح المكتب: يعلن نجاحه بأنوثة صريحة مع اسم الملف
    monkeypatch.setattr(routes_tameedat, "_open_path", lambda path: True)
    page = client.get("/tameedat/open-file/day", follow_redirects=True).data.decode()
    assert "تم فتح ملف «سجلات التأميدات.xlsx»" in page
    page = client.get("/tameedat/open-file/report", follow_redirects=True).data.decode()
    assert "لا يوجد ملف تقرير محفوظ بعد" in page                # قبل بناء التقرير
    response = client.get("/tameedat/open-folder/not_a_tab")
    assert response.status_code == 404


def test_momoda_days_modal_lists_exact_dates_and_json_saves_them(client):
    """«افتح الأيام بالتواريخ»: قائمة منبثقة بكل تأميدة وتاريخها + حفظ محلي في مكانها."""
    _ctx()
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة الأيام", "officers": "٥",
        "individuals": "٣٥", "recruits": "١٦٠", "range_enabled": "1", "day_to": "٢٤",
        "att_name": ["فصيلة الأيام"], "att_officers": ["١"], "att_individuals": ["٦"],
        "att_recruits": ["٢٠"]})
    page = _get(client, "/tameedat/?tab=momoda")
    assert "افتح الأيام بالتواريخ" in page.text           # الزر تحت الرقم تمامًا كما طلب
    assert "tmDaysModal" in page.text and "طباعة قائمة الأيام" in page.text
    # بطاقات المشاركة مدة الوحدة: من ٢٢/٠٩/٢٠٣١ إلى ٢٤/٠٩/٢٠٣١ (٣ أيام)
    assert "مدة من" in page.text and "إلى" in page.text and "٣ أيام" in page.text
    # الملحقة تظهر بطاقتها مرتبطة بتأميدة أمها — وروابط طباعة لكل تأميدة
    assert "(ملحقة على تأميدة «وحدة الأيام»)" in page.text
    assert "/tameedat/print/" in page.text
    summary, _ = dt.month_summary(YEAR, MONTH)
    main = next(r for r in summary if r["kind"] == "entity")
    assert main["participations"][0]["day"] == 22 and main["participations"][0]["day_to"] == 24
    # الحفظ المحلي في فولدر «الجهات المومدة بالشهر الحالي» بالتواريخ نفسها
    mirror = json.loads((tameedat_fs.base_dir(YEAR, MONTH)
                         / tameedat_fs.TAB_FOLDERS["momoda"] / "ملخص الجهات المومدة.json")
                        .read_text(encoding="utf-8"))
    unit = next(g for g in mirror["الجهات"] if g["الجهة"] == "وحدة الأيام")
    dates_list = unit["أيام التميد بالتواريخ"]
    assert dates_list[0]["من"] == "٢٢/٠٩/٢٠٣١" and dates_list[0]["إلى"] == "٢٤/٠٩/٢٠٣١"
    assert dates_list[0]["عدد الأيام"] == 3
    attached = next(g for g in mirror["الجهات"] if g["الجهة"] == "فصيلة الأيام")
    assert attached["ملحقة"] is True and "أيام التميد بالتواريخ" in attached


def test_paste_keeps_time_range_span_with_month_cap(client):
    """لصق النسخة يحتفظ بنفس المدة، ويُقصّ عند نهاية الشهر إن تجاوزتها."""
    _ctx()
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "وحدة التمدد", "officers": "٤",
        "range_enabled": "1", "day_to": "٢٤"})
    source = dt.month_records(YEAR, MONTH)[0]
    client.post(f"/tameedat/records/copy/{source['id']}", data={"to_day": "٢٥"})
    pasted = dt.records_for_day(YEAR, MONTH, 25)[0]
    assert (pasted["day"], pasted["day_to"]) == (25, 27)      # نفس ال٣ أيام مزاحة
    client.post(f"/tameedat/records/copy/{source['id']}", data={"to_day": "٢٩"})
    capped = next(r for r in dt.records_for_day(YEAR, MONTH, 29))
    assert (capped["day"], capped["day_to"]) == (29, 30)      # مقصوصة عند آخر الشهر


# ======================================================================
# حذف جهة القاموس — cascade داخل الشهر فقط
# ======================================================================
def test_dictionary_delete_cascades_month_records_only(client):
    _ctx()
    eid = dt.add_entity(YEAR, MONTH, "وحدة الحدود الشرقية", "شرطية")
    dt.add_record(YEAR, MONTH, 3, dt.get_entity(YEAR, MONTH, eid), 1, 5, 9)
    dt.add_record(YEAR, MONTH, 4, dt.get_entity(YEAR, MONTH, eid), 2, 6, 10)
    response = client.post(f"/tameedat/entities/delete/{eid}")
    toast = _toast(response)
    assert "تم حذف الجهة «وحدة الحدود الشرقية» من قاموس الشهر" in toast
    assert "ومعها ٢ تأميدة" in toast
    assert "وحُفظ الحذف في البيانات المحلية." in toast
    assert dt.list_entities(YEAR, MONTH) == []
    assert dt.month_records(YEAR, MONTH) == []
    kept_on_records_table = storage.DATA_DIR  # الشهر الآخر لا يتأثر أصلًا
    assert kept_on_records_table is not None


# ======================================================================
# التقرير الشامل — Excel بالدباجة واللوجو وWord
# ======================================================================
def _seed_month(client):
    client.post("/tameedat/entities/add", data={
        "name": "كمين الميدان", "type_choice": "شرطية",
        "rag_officers": "", "rag_individuals": ""})
    client.post("/tameedat/records/add", data={
        "day": "٢٢/٠٩/٢٠٣١", "entity_name": "كمين الميدان",
        "officers": "٣", "individuals": "٣٤", "recruits": "٨١",
        "att_name": ["نقطة صغيرة"], "att_officers": ["١"], "att_individuals": ["٦"],
        "att_recruits": ["٢٠"]})
    client.post("/tameedat/records/add", data={
        "day": "٢٤/٠٩/٢٠٣١", "entity_name": "كمين الميدان",
        "officers": "٣", "individuals": "٣٥", "recruits": "٨٠"})


def test_monthly_excel_has_letterhead_logo_and_both_sheets(client, tmp_path):
    _ctx()
    lhdb.save(YEAR, MONTH, {
        "lh_1": "منطقة وسط وجنوب للأمن المركزي",
        "lh_2": "قطاع وسط سيناء - قسم التميينات",
        "lh_3": "مديرية أمن", "lh_4": "إدارة التموين"})
    from services.images import save_logo
    from PIL import Image
    logo_source = tmp_path / "logo.png"
    Image.new("RGBA", (140, 140), (15, 23, 42, 255)).save(logo_source)
    with logo_source.open("rb") as handle:
        lhdb.save(YEAR, MONTH,
                  {"logo_file": save_logo(handle, storage.letterhead_dir(YEAR, MONTH))})
    _seed_month(client)
    response = client.get("/tameedat/report/build/xlsx")
    assert response.status_code == 200 and response.data[:2] == b"PK"
    assert "filename*=UTF-8" in response.headers["Content-Disposition"]
    path = xlsx_tameedat.xlsx_path(YEAR, MONTH)
    assert path.parent.name == tameedat_fs.TAB_FOLDERS["report"]
    book = load_workbook(path)
    assert book.sheetnames == ["التفصيل اليومي", "الملخص الشهري"]
    daily = book["التفصيل اليومي"]
    assert daily.cell(1, 1).value == "منطقة وسط وجنوب للأمن المركزي"
    assert daily.cell(2, 1).value == "قطاع وسط سيناء - قسم التميينات"
    assert len(daily._images) == 1, "اللوجو يجب أن يكون داخل ملف الإكسل نفسه"
    summary = book["الملخص الشهري"]
    assert summary.cell(1, 1).value == "منطقة وسط وجنوب للأمن المركزي"
    names = [summary.cell(row, 2).value for row in range(8, 11)]
    assert "كمين الميدان" in names and "إجمالي القوة" in names


def test_monthly_docx_and_print_pages(client):
    _ctx()
    lhdb.save(YEAR, MONTH, {"lh_1": "منطقة وسط وجنوب للأمن المركزي",
                            "lh_2": "قطاع وسط سيناء - قسم التميينات"})
    _seed_month(client)
    excel = client.get("/tameedat/report/build/xlsx")
    assert excel.status_code == 200 and excel.data[:2] == b"PK"
    response = client.get("/tameedat/report/build/docx")
    assert response.status_code == 200 and response.data[:2] == b"PK"
    assert docx_tameedat.docx_path(YEAR, MONTH).is_file()
    record_id = dt.month_records(YEAR, MONTH)[0]["id"]
    page = _get(client, f"/tameedat/print/{record_id}")
    assert "تأميدة رقم" in page.text and "كمين الميدان" in page.text
    assert "قطاع وسط سيناء - قسم التميينات" in page.text
    assert "للاسترشاد بهذه التأميدة فقط" in page.text
    report = _get(client, "/tameedat/report/print")
    assert "التفصيل اليومي للتأميدات" in report.text
    assert "الملخص الشهري — الجهات المومدة" in report.text
    assert "إجمالي القوة" in report.text
    listing = _get(client, "/tameedat/?tab=report")
    assert "التقرير الشامل - تأميدات سبتمبر 2031.xlsx" in listing.text
    saved = client.get("/tameedat/report/file/" +
                       "التقرير الشامل - تأميدات سبتمبر 2031.docx")
    assert saved.status_code == 200


def test_report_rejects_traversal_and_unknown_kind(client):
    _ctx()
    assert client.get("/tameedat/report/file/..%2F..%2Fsystem.db").status_code == 404
    assert client.get("/tameedat/report/build/pdf").status_code == 404
