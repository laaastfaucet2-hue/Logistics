# -*- coding: utf-8 -*-
"""أرشفة السنوات: زرّا «إنشاء سنة جديدة» و«نقل إلى الأرشيف» في الشريط العلوي —
الأرشفة لا تُسمح إلا بعد انتهاء السنة فعلًا، وتسبقها إنشاء سنة بديلة."""
from data_access import database, storage


def _page(client, url="/dashboard"):
    response = client.get(url)
    assert response.status_code == 200
    return response.data.decode("utf-8")


def test_topbar_shows_named_year_actions_without_avatar_letter(client):
    """لا حرف «م» منفردًا؛ الزرّان بأسماء صريحة بجوار السنة النشطة."""
    page = _page(client)
    assert 'class="avatar"' not in page                        # حرف «م» أُزيل (طلب المستخدم)
    assert 'id="addYearBtn"' in page and "إنشاء سنة جديدة" in page
    assert 'id="archiveYearBtn"' in page and "نقل إلى الأرشيف" in page
    assert "وزارة الداخلية" in page                            # الهوية الجديدة في الترويسة
    assert "منطقة وسط وجنوب سيناء" in page and "قطاع الأمن المركزى" in page and "قسم التعيينات" in page


def test_sidebar_hides_records_file_keeps_warehouses(client):
    """«ملف السجلات» محذوف من الشريط — يبقى تاب «مستودعات وسجلات» فقط."""
    page = _page(client)
    start = page.index("<aside")
    end = page.index("</aside>")
    sidebar = page[start:end]
    assert "ملف السجلات" not in sidebar
    assert "سجلات الامداد" not in sidebar
    assert "سجلات المتعهد" not in sidebar
    assert "/sections/supply_records" not in sidebar
    assert "مستودعات وسجلات" in sidebar
    assert "/sections/warehouses_records" in sidebar


def test_archive_blocks_unfinished_year_and_keeps_it(client):
    """سنة ٢٠٣١ الجارية/المستقبلية لا تُؤرشف — رسالة واضحة وتبقى عاملة."""
    response = client.get("/years/archive?year=٢٠٣١", follow_redirects=True)
    text = response.data.decode("utf-8")
    assert "لم تنتهِ بعد" in text and "الأرشفة متاحة بعد اكتمال السنة" in text
    assert 2031 in storage.list_years()
    assert not (storage.archive_dir() / "2031").exists()


def test_archive_moves_finished_year_whole_folder(client):
    """السنة المنتهية تنتقل كاملة إلى database/الأرشيف وتختفي من اختيارات السنوات."""
    assert storage.create_year(2025)                            # سنة منتهية فعلًا
    assert 2025 in storage.list_years()
    response = client.get("/years/archive?year=٢٠٢٥", follow_redirects=True)
    text = response.data.decode("utf-8")
    assert "نُقلت سنة ٢٠٢٥ إلى الأرشيف" in text
    assert (storage.archive_dir() / "2025").is_dir()
    assert 2025 not in storage.list_years()                     # خارج تعرف السنوات
    assert not storage.year_path(2025).exists()


def test_archive_missing_or_junk_year_is_soft_error(client):
    response = client.get("/years/archive?year=٢٩٩٩", follow_redirects=True)
    assert "السنة غير موجودة على النظام" in response.data.decode("utf-8")


def test_year_controls_match_the_reference_program(client):
    """مفاتيح السنة مطابقة للبرنامج التاني بالضبط (طلب المستخدم): مربع «+» amber للإنشاء،
    أرشفة حمراء بالنص «نقل إلى الأرشيف»، وسلة حذف حمراء — والحبّتان بعنواني «السنة الدفترية» و«الشهر المحاسبي»."""
    page = _page(client)
    assert 'id="addYearBtn"' in page and 'class="ctx-add"' in page
    assert "إنشاء سنة جديدة" in page                       # تلميح مربع «+» الأصفر (بلا نص مطابقًا للمرجع)
    assert "نقل إلى الأرشيف" in page and 'class="ctx-arch"' in page  # زر أرشيف أحمر بنص مرئي
    assert 'id="delYearBtn"' in page and "حذف السنة المحددة نهائيًا" in page
    assert "السنة الدفترية" in page and "الشهر المحاسبي" in page  # عناوين حبّتي السياق
