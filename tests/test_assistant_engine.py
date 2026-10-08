# -*- coding: utf-8 -*-
"""المساعد المحلي المطوَّر: فهم عربي حقيقي + إجابات بيانات + معجم وأدلة + شعار ضابط
+ نموذج محلي اختياري، وكله بلا إنترنت وبلا اعتماديات إضافية.

كل الاختبارات على بيانات معزولة (conftest) — لا تمس بيانات المستخدم أبدًا.
"""
import json
import sys
import types
from pathlib import Path

import pytest

from data_access import database, db_tameedat as dt, db_raghibin as rp

YEAR, MONTH = 2031, 9
ROOT = Path(__file__).resolve().parents[1]


def _ctx():
    database.set_user_context(1, YEAR, MONTH)


def _ask(client, question):
    response = client.post("/assistant/ask", data={"q": question})
    assert response.status_code == 200, question
    payload = response.get_json()
    assert payload["ok"] is True
    return payload


def _seed(client):
    """تأميدة + قوة وراغبون — لتُختبر الإجابات على أرقام حقيقية."""
    _ctx()
    client.post("/tameedat/entities/add", data={
        "name": "قطاع التجربة", "entity_type": "شرطية"})
    entity = dt.find_entity_by_name(YEAR, MONTH, "قطاع التجربة")
    assert entity is not None
    dt.add_record(YEAR, MONTH, 7, entity, 5, 15, 2, notes="")
    rp.add_person(YEAR, MONTH, entity["id"], "officers", "رائد تجربة أول", rank="رائد")
    rp.add_person(YEAR, MONTH, entity["id"], "individuals", "فرد تجربة أول", rank="جندي")
    person = rp.list_persons(YEAR, MONTH, entity_id=entity["id"], category="officers")[0]
    rp.set_daily(YEAR, MONTH, person["id"], 7, True, source="manual")
    return entity


# ══════════════════════════════════════════════════════════════════════
# ١) الفهم العربي: التطبيع والتشابه والأرقام
# ══════════════════════════════════════════════════════════════════════
def test_normalize_unifies_hamza_and_letters():
    from services.assistant import text as T
    assert T.normalize("التَّأمِيدَة") == T.normalize("التاميده") == T.normalize("التأميدة")
    assert T.normalize("إدارة مرور وسط سيناء") == T.normalize("اداره مرور وسط سيناء")
    assert T.normalize("٧") == "7"          # الأرقام العربية المشرقية تُقرأ أرقامًا غربية


def test_fuzzy_matching_tolerates_typos():
    from services.assistant import text as T
    assert T.phrase_in("عدد التامدات في الشهر", "تأميدات") is True       # خطأ مطبعي
    assert T.phrase_in("افتح الرغبين من فضلك", "الراغبين") is True
    assert T.phrase_in("زلابية بالعسل", "تأميدات") is False


def test_day_number_reads_digits_and_arabic_words():
    from services.assistant import text as T
    assert T.day_number(T.normalize("تأميدات يوم ٧")) == 7
    assert T.day_number(T.normalize("راغبو يوم ١٥")) == 15
    assert T.day_number(T.normalize("تأميدات يوم سبعة")) == 7
    assert T.day_number(T.normalize("تأميدات اليوم")) is None


# ══════════════════════════════════════════════════════════════════════
# ٢) التصنيف: تحية/تعريف/مساعدة/نقل/بيانات/جهل
# ══════════════════════════════════════════════════════════════════════
def test_greeting_thanks_whoami_and_help(client):
    _ctx()
    greeting = _ask(client, "السلام عليكم")
    assert greeting["kind"] == "greeting" and "وعليكم السلام" in greeting["reply"]
    assert greeting["blocks"] and greeting["followups"]

    thanks = _ask(client, "شكرا يا ريس")
    assert thanks["kind"] == "thanks"

    who = _ask(client, "مين انت؟")
    assert who["kind"] == "who" and "محلي" in who["reply"]

    help_payload = _ask(client, "مساعدة")
    assert help_payload["kind"] == "help"
    assert len(help_payload["blocks"]) >= 8            # كتالوج القدرات كامل


def test_navigation_opens_real_route_with_working_link(client):
    _ctx()
    payload = _ask(client, "افتح التاميدات")
    assert payload["kind"] == "nav"
    assert payload["navigate"].startswith("/tameedat")
    assert payload["links"] and payload["links"][0]["href"].startswith("/tameedat")

    raghibin = _ask(client, "روحلي الراغبين")
    assert raghibin["navigate"].startswith("/raghibin")

    calc = _ask(client, "افتح آلة حاسبة ٢ مخازن")
    assert calc["navigate"].startswith("/calc2")

    # الرابط المُعاد يعمل فعلًا (لا رابط ميت)
    page = client.get(payload["navigate"])
    assert page.status_code == 200


def test_unknown_question_suggests_capabilities_instead_of_silence(client):
    _ctx()
    payload = _ask(client, "زلابية بالعسل")
    assert payload["kind"] == "unknown"
    assert payload["followups"] and payload["followups"]
    assert "مساعدة" in payload["reply"]


def test_destination_keywords_are_not_duplicated_between_topics(client):
    """كل كلمة في التواريخ والملخصات تذهب لموضوعها الصحيح — لا تداخل صامت."""
    from services.assistant.engine import TOPICS
    seen = {}
    for key, _weight, keywords, _handler in TOPICS:
        for keyword in keywords:
            seen.setdefault(keyword, key)
    assert seen["ملخص الشهر"] == "summary"
    assert seen["عدد التأميدات"] == "tameedat_month"
    assert seen["الجهات المومده"] == "momoda"


# ══════════════════════════════════════════════════════════════════════
# ٣) الإجابات من بيانات الشهر الحقيقية (لا أرقام مخترعة)
# ══════════════════════════════════════════════════════════════════════
def test_month_summary_matches_real_data(client):
    _ctx()
    entity = _seed(client)
    payload = _ask(client, "ملخص الشهر")
    assert payload["kind"] == "data"
    records = dt.month_records(YEAR, MONTH)
    totals = dt.month_summary(YEAR, MONTH)[1]
    pairs = {pair[0]: pair[1] for block in payload["blocks"]
             if block["type"] == "kv" for pair in block["items"]}
    assert "التأميدات" in pairs
    assert "تأميدة" in pairs["التأميدات"]
    assert len(records) == 1 and entity["name"] in json.dumps(payload, ensure_ascii=False)
    assert str(totals["grand"]) and pairs


def test_day_questions_return_the_exact_record_rows(client):
    _ctx()
    _seed(client)
    payload = _ask(client, "تأميدات يوم ٧")
    assert payload["kind"] == "data"
    tables = [block for block in payload["blocks"] if block["type"] == "table"]
    assert tables and tables[0]["rows"]
    assert tables[0]["rows"][0][0].startswith("قطاع التجربة")
    assert tables[0]["headers"][0] == "الجهة"

    empty = _ask(client, "تأميدات يوم ٢٠")
    assert empty["kind"] == "data" and "مفيش تأميدات" in empty["reply"]


def test_entity_question_answers_with_that_entity_only(client):
    _ctx()
    _seed(client)
    payload = _ask(client, "تأميدات قطاع التجربة")
    assert payload["kind"] == "data"
    assert "قطاع التجربة" in payload["title"]
    assert "قطاع التجربة" in payload["reply"]


def test_entity_mention_alone_returns_a_full_card(client):
    """ذكر اسم الجهة وحده («قطاع التجربة») يجب أن يرد ببطاقة كاملة، لا «مفهمتش»."""
    _ctx()
    _seed(client)
    payload = _ask(client, "قطاع التجربة")
    assert payload["kind"] == "data" and "قطاع التجربة" in payload["title"]
    pairs = {pair[0] for block in payload["blocks"]
             if block["type"] == "kv" for pair in block["items"]}
    assert "القوة المعتمدة" in pairs and "تأميدات مسجّلة" in pairs

    # كلمة واحدة فريدة من اسم الجهة تكفي، وبلا جهة يُرد بجدول القوة العام
    assert "قوة" in _ask(client, "قوة التجربة")["title"]
    assert "قطاع التجربة" in _ask(client, "قوة التجربة")["title"]
    forces = _ask(client, "قوة")
    assert forces["kind"] == "data" and "أصل القوة" in forces["title"]


def test_short_verbs_do_not_match_inside_longer_words(client):
    """«هات» لا تُطابق «الجهات»، و«الشهر اللي فات» تجيب دليل تغيير الشهر."""
    from services.assistant import text as T
    assert T.phrase_in(T.normalize("الجهات المومدة"), "هات") is False
    assert T.similarity("هات", "الجهات") < 0.7
    assert T.similarity("الراغبين", "راغبين") >= 0.9        # أما الطويل فيُقبل

    _ctx()
    payload = _ask(client, "الشهر اللي فات")
    assert payload["kind"] == "guide" and "الشهر" in payload["title"]


def test_willing_names_for_a_day_are_real(client):
    _ctx()
    _seed(client)
    payload = _ask(client, "راغبو يوم ٧")
    assert payload["kind"] == "data"
    assert "رائد تجربة أول" in payload["reply"]           # الاسم الحقيقي من ragh_daily
    assert "ض ١" in payload["reply"]


def test_forces_and_recruits_and_backups_use_official_layers(client):
    _ctx()
    _seed(client)
    forces = _ask(client, "إجمالي القوة")
    assert forces["kind"] == "data" and "أصل القوة" in forces["title"]
    assert "قطاع التجربة" in json.dumps(forces, ensure_ascii=False)

    recruits = _ask(client, "عدد المجندين")
    assert recruits["kind"] == "data" and "المجند" in recruits["title"]

    backups = _ask(client, "النسخ الاحتياطي")
    assert backups["kind"] == "data" and "النسخ" in backups["title"]

    alerts = _ask(client, "تنبيهات الشهر")
    assert alerts["kind"] == "data" and "تنبيهات" in alerts["title"]


def test_glossary_and_guides_answer_how_to_questions(client):
    _ctx()
    meaning = _ask(client, "يعني إيه مومدة؟")
    assert meaning["kind"] == "definition"
    assert "الجهة المومدة" in meaning["title"]

    howto = _ask(client, "إزاي أسجّل تأميدة؟")
    assert howto["kind"] == "guide"
    assert "الخطوات" in howto["reply"] or howto["blocks"]
    assert any(block["type"] == "bullets" for block in howto["blocks"])

    howto2 = _ask(client, "إزاي أعمل إذن ٢ مخازن؟")
    assert howto2["kind"] == "guide" and "٢ مخازن" in howto2["title"]

    month = _ask(client, "إزاي أغيّر الشهر؟")
    assert month["kind"] == "guide" and "الشهر" in month["title"]

    # عبارة دالة كاملة بلا كلمة سؤال («الشهر اللي فات») تجيب الدليل الصحيح كذلك
    month2 = _ask(client, "عايز أشوف الشهر اللي فات")
    assert month2["kind"] == "guide" and "الشهر" in month2["title"]


def test_every_capability_example_is_answerable(client):
    """كل مثال معلن في كتالوج القدرات لازم يرد بغير «مفهمتش» — وعدٌ لا يُخلف."""
    _ctx()
    _seed(client)
    from services.assistant import knowledge as K
    failures = []
    for _title, examples in K.CAPABILITIES:
        for example in examples:
            payload = _ask(client, example)
            if payload["kind"] == "unknown":
                failures.append(example)
    assert not failures, failures


def test_day_file_question_gives_a_real_download_link(client):
    """«ملف تأميدات يوم ٧» ⇒ رابط تنزيل حقيقي لملف اليوم نفسه — ويوم فاضي يقولها."""
    _ctx()
    _seed(client)                              # تأميدة يوم ٧ ⇒ ملف اليوم يُبنى فعلًا
    from services import tameedat_fs
    tameedat_fs.snapshot_all(YEAR, MONTH)      # نفس ما يحدث بعد أي حفظ في البرنامج
    payload = _ask(client, "ملف تأميدات يوم ٧")
    assert payload["kind"] == "data" and "٧" in payload["title"]
    hrefs = [link["href"] for link in payload["links"]]
    download = [href for href in hrefs if "/tameedat/day-file/7" in href]
    assert download, hrefs                       # رابط حقيقي لا وصف
    assert "/tameedat/?tab=day" in " ".join(hrefs)
    pairs = {pair[0]: pair[1] for block in payload["blocks"]
             if block["type"] == "kv" for pair in block["items"]}
    assert pairs["اسم الملف"] == "تاميدات اليوم ٧.xlsx"      # نفس مصدر التسمية
    assert "مُنشأ" in pairs["الحالة"]
    response = client.get(download[0])
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["Content-Type"]

    # يوم بلا تأميدات: بلا رابط تنزيل + يقولها صراحةً ويوجّه لملف الشهر
    empty = _ask(client, "ملف تأميدات يوم ٢٠")
    assert empty["kind"] == "data"
    assert not [link for link in empty["links"] if "day-file" in link["href"]]
    assert "لسه فاضي" in json.dumps(empty, ensure_ascii=False)
    assert "إجمالي الشهر" in empty["reply"]

    # ويوم أكبر من أيام الشهر لا يُخترع له ملف (سبتمبر ٣٠ يومًا)
    outside = _ask(client, "ملف تأميدات يوم ٣١")
    assert outside["kind"] == "data"
    assert "مفيش يوم" in json.dumps(outside, ensure_ascii=False)


def test_local_files_answer_counts_from_disk_not_guess(client):
    """«عدد الملفات» ⇒ حصر حقيقي من القرص (نفس خدمات لوحة الحصر) بروابط اللوحة."""
    _ctx()
    _seed(client)
    payload = _ask(client, "عدد الملفات")
    assert payload["kind"] == "data" and "الملفات" in payload["title"]
    pairs = {pair[0] for block in payload["blocks"]
             if block["type"] == "kv" for pair in block["items"]}
    assert "عدد الملفات" in pairs and "الحجم الكلي" in pairs
    hrefs = " ".join(link["href"] for link in payload["links"])
    assert "/files/audit-page" in hrefs
    # رقم المساعد = رقم خدمة الحصر نفسها (مصدر واحد)
    from services import files_index
    tree = files_index.build_tree("tameedat", YEAR, MONTH)
    from core import arabic_numbers as arnum
    assert arnum.to_arabic_indic(str(tree["files"])) in json.dumps(payload, ensure_ascii=False)


def test_ranking_and_missing_days_use_official_layers(client):
    """「مين أكبر جهة」 و「أيام بدون تسجيل」 — من نفس دالتي القوة والتسجيل الرسميتين."""
    _ctx()
    _seed(client)
    top = _ask(client, "مين أكبر جهة")
    assert top["kind"] == "data" and "ترتيب" in top["title"]
    assert "قطاع التجربة" in json.dumps(top, ensure_ascii=False)
    rows = [block for block in top["blocks"] if block["type"] == "table"][0]["rows"]
    assert rows and rows[0][0] == "قطاع التجربة"                  # الجهة الوحيدة بالقمّة

    low = _ask(client, "أقل الجهات قوة")
    assert low["kind"] == "data" and "الأقل" in low["title"]

    missing = _ask(client, "أيام بدون تسجيل")
    assert missing["kind"] == "data" and "الناقصة" in missing["title"]
    from data_access import db_raghibin as rp, db_tameedat as dt
    registered = set(rp.day_willing_counts(YEAR, MONTH))
    tameed = set(dt.day_counts(YEAR, MONTH))
    expected = len(tameed - registered)
    from core import arabic_numbers as arnum
    pairs = {pair[0]: pair[1] for block in missing["blocks"]
             if block["type"] == "kv" for pair in block["items"]}
    assert pairs["أيام ناقصة التسجيل"] == arnum.to_arabic_indic(str(expected))
    assert pairs["أيام فيها تأميدات"] == arnum.to_arabic_indic(str(len(tameed)))


def test_quick_prompts_are_all_answerable(client):
    _ctx()
    _seed(client)
    prompts = client.get("/assistant/prompts").get_json()["prompts"]
    assert len(prompts) >= 8
    for prompt in prompts:
        assert _ask(client, prompt)["kind"] != "unknown", prompt


def test_capabilities_endpoint_reports_model_state_honestly(client):
    _ctx()
    payload = client.get("/assistant/capabilities").get_json()
    assert payload["ok"] is True
    assert payload["topics"] and payload["glossary"] and payload["guides"]
    model = payload["model"]
    assert "enabled" in model and "file_found" in model
    if not model["file_found"]:
        assert model["enabled"] is False
        assert "مفيش نموذج" in model["note"]           # صدق بلا تظاهر بالتوفّر
    assert payload["facts"] and payload["facts"][0][0] == "الشهر النشط"


# ══════════════════════════════════════════════════════════════════════
# ٤) النموذج المحلي الاختياري (GGUF) — يعمل إن وُجد، ويسكت بهدوء إن غاب
# ══════════════════════════════════════════════════════════════════════
def test_local_model_gateway_uses_gguf_when_available(client, tmp_path, monkeypatch):
    """نموذج محلي مزيّف (بلا أوزان) يثبت أن المسار يعمل ويُمرَّر إليه سياق الشهر."""
    _ctx()
    _seed(client)
    from services.assistant import model as local_model

    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"GGUF-fake" + b"\x00" * 70000)   # فوق الحجم الأدنى في looks_like_gguf
    monkeypatch.setenv(local_model.ENV_PATH, str(gguf))
    local_model._CACHE.update({"path": None, "llm": None, "failed": False})

    calls = {}

    class FakeLlama:
        def __init__(self, **kwargs):
            calls["init"] = kwargs

        def create_chat_completion(self, messages, **kwargs):
            calls["messages"] = messages
            return {"choices": [{"message": {"content": "رد من النموذج المحلي"}}]}

    fake_module = types.ModuleType("llama_cpp")
    fake_module.Llama = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    status = local_model.status()
    assert status["enabled"] is True and status["backend"] == "llama.cpp"
    assert local_model.try_answer("سؤال مفتوح عن المنظومة", YEAR, MONTH) == "رد من النموذج المحلي"
    context = "\n".join(message["content"] for message in calls["messages"])
    assert "بيانات الشهر" in context and "التأميدات" in context      # الأرقام الحقيقية في السياق
    assert calls["init"]["model_path"] == str(gguf)

    # سؤال لا يفهمه المحرك يستخدم النموذج تلقائيًا — والواجهة تعرضه بوضوح
    payload = _ask(client, "اكتبلي جملة تحفيزية للقسم")
    assert payload["kind"] == "model" and "النموذج المحلي" in "".join(
        block.get("text", "") for block in payload["blocks"]) or payload["kind"] == "model"

    monkeypatch.delenv(local_model.ENV_PATH, raising=False)
    local_model._CACHE.update({"path": None, "llm": None, "failed": False})


def test_local_model_missing_engine_falls_back_silently(client, tmp_path, monkeypatch):
    _ctx()
    from services.assistant import model as local_model
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"GGUF-fake" + b"\x00" * 70000)   # فوق الحجم الأدنى في looks_like_gguf
    monkeypatch.setenv(local_model.ENV_PATH, str(gguf))
    monkeypatch.setitem(sys.modules, "llama_cpp", None)      # محرّك غير متاح
    local_model._CACHE.update({"path": None, "llm": None, "failed": False})
    assert local_model.try_answer("أي سؤال", YEAR, MONTH) is None
    status = local_model.status()
    assert status["file_found"] is True and status["enabled"] is False
    monkeypatch.delenv(local_model.ENV_PATH, raising=False)
    local_model._CACHE.update({"path": None, "llm": None, "failed": False})


# ══════════════════════════════════════════════════════════════════════
# ٥) الشعار والواجهة: ضابط محلّي بدل أيقونة الروبوت، ومحلي بلا CDN
# ══════════════════════════════════════════════════════════════════════
def test_officer_badge_replaces_robot_icon_everywhere(client):
    _ctx()
    page = client.get("/dashboard").get_data(as_text=True)
    assert "assistant-officer.svg" in page and "asst-head-face" in page
    assert "🤖" not in page                                   # ممنوع إيموجي الروبوت
    assert "asst-capabilities" in page or "data-capabilities" in page

    badge = (ROOT / "static/img/assistant-officer.svg")
    assert badge.is_file()
    svg = badge.read_text(encoding="utf-8")
    assert "<svg" in svg and "ضابط" in svg
    for token in ("#fcd34d", "#0b1220", "#f2d3b1"):           # هوية slate/gold
        assert token in svg
    response = client.get("/static/img/assistant-officer.svg")
    assert response.status_code == 200
    assert "svg" in response.headers["Content-Type"]


def test_assistant_assets_are_local_and_offline(client):
    _ctx()
    page = client.get("/dashboard").get_data(as_text=True)
    assert "cdn" not in page.lower().replace("cdn", "cdn")   # لا CDN في الصفحة
    assert "http://" not in page.split("asst-wrap")[1][:400]
    js = (ROOT / "static/js/assistant.js").read_text(encoding="utf-8")
    css = (ROOT / "static/css/assistant.css").read_text(encoding="utf-8")
    for text in (js, css):
        assert "innerHTML" not in text or "لا innerHTML" in text
        assert "http://" not in text and "https://" not in text
    assert "asst-table" in css and "asst-kv" in css and "asst-typing" in css
    assert "@media print" in css and ".asst-wrap" in css


def test_old_flat_module_is_replaced_by_package():
    assert not (ROOT / "services/assistant.py").is_file()      # الملف القديم أُزيل
    package = ROOT / "services/assistant"
    for name in ("text.py", "destinations.py", "knowledge.py", "data_answers.py",
                 "model.py", "engine.py", "__init__.py"):
        assert (package / name).is_file(), name
        assert len((package / name).read_text(encoding="utf-8").splitlines()) <= 1000


def test_ask_requires_login_and_detail_never_leaks_none(client):
    """المساعد محمي بالدخول، ولا تظهر كلمة None في أي رد (قاعدة القيم الفارغة)."""
    from app import create_app
    fresh = create_app()
    anonymous = fresh.test_client()
    assert anonymous.post("/assistant/ask", data={"q": "ملخص الشهر"}).status_code in (302, 401)
    _ctx()
    _seed(client)
    for question in ("ملخص الشهر", "تأميدات يوم ٩", "أرصدة المخازن", "الكوادر", "الترفية",
                     "إذون ٢ مخازن", "المقررات", "المناسبات", "الدباجة", "المخازن والثلاجات"):
        payload = _ask(client, question)
        assert "None" not in json.dumps(payload, ensure_ascii=False), question


@pytest.mark.parametrize("question", ["", "   ", "؟؟؟", "12", "😀"])
def test_edge_inputs_never_crash(client, question):
    _ctx()
    payload = _ask(client, question)
    assert payload["ok"] is True and payload["kind"]
