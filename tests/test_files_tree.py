# -*- coding: utf-8 -*-
"""حصر الملفات المحلية + التحديث اللحظي (توجيه المستخدم ٠٦/١٠/٢٠٢٦).

المستخدم طلب: «حصر كل الملفات المحلية في صفحتي التاميدات والراغبين على شكل شجرة،
والتأكد أنها كلها تتحدث لحظيًا مع البرنامج — ولو الملف مفتوح في Excel ولم يُقفل».

كل الاختبارات هنا على قواعد مؤقتة معزولة (tests/conftest.py) — لا تمس بيانات المستخدم.
"""
import os
import time
from pathlib import Path

import pytest

from core import paths
from data_access import dataguard
from data_access import db_raghibin as drg
from data_access import db_tameedat as dt
from data_access import months
from services import files_index, tameedat_fs
from services.raghibin import files_daily

YEAR, MONTH = 2031, 9
SECTION_ROOTS = {
    "tameedat": lambda: (paths.DATA_DIR / str(YEAR) / "09-سبتمبر" / "07-التاميدات"),
    "raghibin": lambda: (paths.DATA_DIR / str(YEAR) / "09-سبتمبر" / "03-قسم الراغبين"),
}


def _disk_files(root):
    """كل الملفات الحقيقية على القرص (بلا ملفات القفل/الكتابة المؤقتة)."""
    return {p.relative_to(root): p.stat().st_size
            for p in root.rglob("*")
            if p.is_file() and not p.name.startswith("~$") and ".tmp-" not in p.name}


def _snapshot(root):
    return {p: p.stat().st_mtime for p in root.rglob("*") if p.is_file()}


def _entity(name="جهة الحصر"):
    eid = dt.add_entity(YEAR, MONTH, name, "شرطية")
    return eid, dt.get_entity(YEAR, MONTH, eid)


# ==================== ١) الحصر نفسه: كل ملف على القرص يظهر في الشجرة ====================

def test_tree_reports_section_root_and_real_files(app, client):
    months.init_month(YEAR, MONTH)
    eid, entity = _entity("جهة شجرة")
    dt.add_record(YEAR, MONTH, 4, entity, 3, 6, 1)
    tameedat_fs.snapshot_all(YEAR, MONTH)

    response = client.get("/files/tree?section=tameedat")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] and data["root_name"] == "07-التاميدات"
    assert data["files"] >= 3 and data["folders"] >= 4

    root = SECTION_ROOTS["tameedat"]()
    names = {child["name"] for child in data["children"]}
    assert names == {path.name for path in root.iterdir()}
    # كل عدد معلن في الشجرة = عدد حقيقي على القرص (وإلا كان الحصر وهميًا)
    assert data["files"] == len(_disk_files(root))
    for child in data["children"]:
        if child["type"] == "dir":
            assert child["files"] == len(_disk_files(root / child["name"]))


def test_tree_lists_every_raghibin_folder(app, client):
    months.init_month(YEAR, MONTH)
    eid, entity = _entity("جهة الراغبين")
    drg.add_person(YEAR, MONTH, eid, "officers", "محمد محمود", rank="رائد")
    client.get("/raghibin?tab=daily")        # فتح القسم ينشئ الفولدرات الأربعة (سلوك البرنامج)
    files_daily.write_day_file(YEAR, MONTH, 3, eid, entity["name"])

    data = client.get("/files/tree?section=raghibin").get_json()
    names = {child["name"] for child in data["children"]}
    assert {"1. (يومي) الراغبين", "2. عدم الراغبين", "3. تجميع الكشف الشهري العام",
            "4. الجهات والكوادر المعتمدة"} <= names
    daily = next(c for c in data["children"] if c["name"].startswith("1. (يومي)"))
    day3 = next(c for c in daily["children"] if c["name"] == "يوم ٣")
    assert [f["name"] for f in day3["children"]] == ["جهة الراغبين.xlsx"]


def test_tree_hides_lock_and_temp_files_and_sorts_days_numerically(app, client):
    months.init_month(YEAR, MONTH)
    root = SECTION_ROOTS["raghibin"]()
    files_daily.ensure_day_folders(YEAR, MONTH)
    (root / "1. (يومي) الراغبين" / "~$جهة.xlsx").write_bytes(b"lock")
    (root / "1. (يومي) الراغبين" / "x.xlsx.tmp-4321").write_bytes(b"tmp")

    data = client.get("/files/tree?section=raghibin").get_json()
    daily = next(c for c in data["children"] if c["name"].startswith("1. (يومي)"))
    labels = [c["name"] for c in daily["children"]]
    assert "~$جهة.xlsx" not in labels and "x.xlsx.tmp-4321" not in labels
    # يوم ١٠ بعد يوم ٩ (ترتيب رقمي) لا ترتيب نصي عربي
    assert labels[:3] == ["يوم ١", "يوم ٢", "يوم ٣"]
    assert labels.index("يوم ١٠") == labels.index("يوم ٩") + 1


def test_tree_rejects_unknown_section(client):
    assert client.get("/files/tree?section=nope").status_code == 400
    assert client.get("/files/tree").status_code == 200      # الافتراضي: التاميدات


def test_tree_requires_login(app):
    anonymous = app.test_client()
    response = anonymous.get("/files/tree?section=tameedat")
    assert response.status_code == 302 and "/login" in response.headers["Location"]


# ==================== ٢) التحديث اللحظي مع كل حفظ في البرنامج ====================

def test_tameeda_save_rewrites_every_mirror_file(app, client):
    months.init_month(YEAR, MONTH)
    eid, entity = _entity("جهة التحديث")
    dt.add_record(YEAR, MONTH, 2, entity, 1, 1, 0)
    tameedat_fs.snapshot_all(YEAR, MONTH)
    root = SECTION_ROOTS["tameedat"]()
    before = _snapshot(root)
    time.sleep(1.1)                                    # دقة mtime = ثانية

    dt.add_record(YEAR, MONTH, 9, entity, 4, 4, 2)
    tameedat_fs.snapshot_all(YEAR, MONTH)
    after = _snapshot(root)

    changed = [str(p.relative_to(root)) for p in after if after[p] != before.get(p)]
    assert "تأميدات اليوم المحدد/سجلات التأميدات.json" in changed
    assert "تأميدات اليوم المحدد/إجمالي الشهر.xlsx" in changed
    assert "الجهات المومدة بالشهر الحالي/ملخص الجهات المومدة.xlsx" in changed
    assert "قاموس ودليل الجهات/قاموس الجهات.json" in changed
    assert (root / "تأميدات اليوم المحدد" / "يوم ٩" / "تاميدات اليوم ٩.xlsx").is_file()


def test_raghibin_daily_save_rewrites_the_entity_six_files(app, client):
    months.init_month(YEAR, MONTH)
    eid, entity = _entity("جهة لحظية")
    pid, _ = drg.add_person(YEAR, MONTH, eid, "officers", "مصطفى نصرالله", rank="رائد")
    response = client.post("/raghibin/daily/save", data={
        "e": eid, "d": 7, "cat": "officers", "names": ["مصطفى نصرالله"]})
    assert response.status_code == 302

    root = SECTION_ROOTS["raghibin"]()
    written = [str(p.relative_to(root)) for p in root.rglob("*.xlsx")]
    day_file = "1. (يومي) الراغبين/يوم ٧/جهة لحظية.xlsx"
    assert day_file in written
    for expected in ("2. عدم الراغبين/جهة لحظية (ضباط غير راغبين).xlsx",
                     "3. تجميع الكشف الشهري العام/جهة لحظية.xlsx",
                     "4. الجهات والكوادر المعتمدة/جهة لحظية (ضباط).xlsx"):
        assert expected in written

    # تسجيل فرد جديد يوسم ملفات الجهة نفسها «اتحدثت الآن» في الحصر
    data = client.get("/files/tree?section=raghibin&fresh=600").get_json()
    daily = next(c for c in data["children"] if c["name"].startswith("1. (يومي)"))
    day7 = next(c for c in daily["children"] if c["name"] == "يوم ٧")
    assert day7["children"][0]["fresh"] is True
    assert day7["fresh"] is True
    assert pid and drg.day_state(YEAR, MONTH, 7, eid)      # التسجيل وصل للقاعدة فعلًا


def test_cadres_change_updates_entity_files(app, client):
    months.init_month(YEAR, MONTH)
    eid, entity = _entity("جهة القوة")
    root = SECTION_ROOTS["raghibin"]()
    client.post("/raghibin/cadres/add", data={
        "e": eid, "cat": "individuals", "name": "أحمد سيد", "rank": "عريف"})
    path = root / "4. الجهات والكوادر المعتمدة" / "جهة القوة (أفراد).xlsx"
    assert path.is_file() and path.stat().st_size > 0
    data = client.get("/files/tree?section=raghibin").get_json()
    cadres = next(c for c in data["children"] if c["name"].startswith("4."))
    assert cadres["files"] >= 1


def test_pages_show_the_files_panel_and_hide_it_in_print(client):
    tameedat = client.get("/tameedat?tab=day").get_data(as_text=True)
    raghibin = client.get("/raghibin?tab=daily").get_data(as_text=True)
    assert 'id="ftZone"' in tameedat and "الملفات المحلية على جهازك" in tameedat
    assert 'id="ftZone"' in raghibin and "قسم الراغبين" in raghibin
    css = (Path(__file__).resolve().parents[1] / "static/css/files-tree.css").read_text(
        encoding="utf-8")
    assert "@media print" in css and ".ft-zone" in css and "display: none" in css


# ==================== ٣) الملف مفتوح في Excel ولم يُقفل ====================

def test_locked_file_content_is_written_the_moment_it_closes(app, monkeypatch):
    """ويندوز يمنع استبدال ملف مفتوح في Excel — البرنامج يحتفظ بالتحديث ويكتبه
    أول ما يُقفل الملف، فلا يضيع أي تغيير (live-sync)."""
    target = SECTION_ROOTS["tameedat"]()
    root = SECTION_ROOTS["tameedat"]()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "سجلات الاختبار.json"
    path.write_bytes('{"النسخة": 1}'.encode("utf-8"))

    real_replace = os.replace
    state = {"locked": True}

    def fake_replace(src, dst):
        if os.path.abspath(dst) == os.path.abspath(str(path)) and state["locked"]:
            raise PermissionError("[WinError 32] الملف مستخدم من عملية أخرى (Excel)")
        return real_replace(src, dst)

    monkeypatch.setattr(dataguard.os, "replace", fake_replace, raising=False)
    monkeypatch.setattr(dataguard, "RETRY_SECONDS", 0.05)
    monkeypatch.setattr(dataguard, "RETRY_MAX_TRIES", 60)

    new_payload = '{"النسخة": 2}'.encode("utf-8")
    dataguard.atomic_save(lambda tmp: Path(tmp).write_bytes(new_payload), path,
                          zip_check=False)
    assert path.read_bytes() == '{"النسخة": 1}'.encode("utf-8")   # مقفول: ما اتنزلش فورًا
    assert str(path) in dataguard.pending_paths()            # محفوظ في قائمة الانتظار

    state["locked"] = False                                  # «المستخدم قفل الملف»
    for _ in range(60):
        time.sleep(0.05)
        if path.read_bytes() == new_payload:
            break
    assert path.read_bytes() == new_payload
    assert str(path) not in dataguard.pending_paths()
    assert target.exists()


def test_new_day_file_written_even_if_the_previous_one_was_locked(app, client, monkeypatch):
    """حتى لو ملف اليوم مقفول، الحصر يعرض الملف الأخير على القرص والتحديث محفوظ للمرة القادمة."""
    months.init_month(YEAR, MONTH)
    eid, entity = _entity("جهة القفل")
    drg.add_person(YEAR, MONTH, eid, "officers", "سامح يوسف", rank="نقيب")
    files_daily.write_day_file(YEAR, MONTH, 5, eid, entity["name"])
    day_file = SECTION_ROOTS["raghibin"]() / "1. (يومي) الراغبين" / "يوم ٥" / "جهة القفل.xlsx"
    assert day_file.is_file()

    real_replace = os.replace

    def fake_replace(src, dst):
        if os.path.abspath(dst) == os.path.abspath(str(day_file)):
            raise PermissionError("File in use by Excel")
        return real_replace(src, dst)

    monkeypatch.setattr(dataguard.os, "replace", fake_replace, raising=False)
    monkeypatch.setattr(dataguard, "RETRY_SECONDS", 0.05)
    monkeypatch.setattr(dataguard, "RETRY_MAX_TRIES", 40)

    client.post("/raghibin/daily/save", data={
        "e": eid, "d": 5, "cat": "officers", "names": ["سامح يوسف"]})
    # الحفظ نجح (لا خطأ للمستخدم) والتحديث محفوظ في قائمة الانتظار لا ضائعًا
    assert str(day_file) in dataguard.pending_paths()
    # وباقي ملفات الجهة (غير المقفولة) اتحدثت فورًا في نفس اللحظة
    cadres = SECTION_ROOTS["raghibin"]() / "4. الجهات والكوادر المعتمدة" / "جهة القفل (ضباط).xlsx"
    assert cadres.is_file() and cadres.stat().st_size > 0


def test_files_index_never_writes_and_never_crashes_on_missing_folder(app):
    """الحصر قراءة فقط: فولدر قسم غير موجود لا يُسقط الصفحة."""
    tree = files_index.build_tree("tameedat", 2099, 7)
    assert tree["ok"] is True and tree["files"] == 0 and tree["children"] == []
    assert tree["header"].startswith("قطاع وسط سيناء")


# ==================== ٤) شكل الواجهة (توجيه ٠٦/١٠/٢٠٢٦) ====================

def test_footer_has_theme_switch_between_the_two_sentences(client):
    body = client.get("/dashboard").get_data(as_text=True)
    footer = body[body.index('<footer class="footer">'):body.index("</footer>")]
    order = [token for token in ("foot-app", "theme-switch", "foot-note")
             if token in footer]
    assert order == ["foot-app", "theme-switch", "foot-note"]
    assert "ألوان البرنامج" in footer and "كحلي" in footer and "أبيض" in footer \
        and "أزرق" in footer
    sidebar = body[body.index('<aside class="sidebar"'):body.index("</aside>")]
    assert "theme-switch" not in sidebar                    # اتشالت من الشريط الجانبي
    assert "تعمل محليًا على جهازك · احتفظ بنسخة احتياطية من بياناتك" in footer
    assert "وزارة الداخلية — منظومة التعيينات" in footer


def test_english_workspace_brand_is_gone_and_credit_is_written(client):
    for url in ("/dashboard", "/tameedat?tab=day", "/raghibin?tab=daily"):
        body = client.get(url).get_data(as_text=True)
        assert "LOGISTICS WORKSPACE" not in body
        assert "تصميم وتنفيذ رائد/ مصطفى نصرالله" in body


def test_login_card_first_right_aligned_and_no_english_brand(app):
    page = app.test_client().get("/login").get_data(as_text=True)
    assert page.index('<section class="login-card"') < page.index('<section class="login-hero"')
    assert "LOGISTICS WORKSPACE" not in page and "WORKSPACE /" not in page
    assert "تصميم وتنفيذ رائد/ مصطفى نصرالله" in page
    css = (Path(__file__).resolve().parents[1] / "static/css/login.css").read_text(
        encoding="utf-8")
    assert "text-align: right" in css
    assert "direction: rtl" in css
