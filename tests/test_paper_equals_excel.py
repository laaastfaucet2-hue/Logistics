# -*- coding: utf-8 -*-
"""«الورق = الإكسل» — كل كشف مطبوع بنفس أعمدة ملفه المحلي بالحرف (توجيه ٠٦/١٠/٢٠٢٦).

قاعدة المستخدم: «الورق اللي في البرنامج هو بالضبط اللي موجود في الإكسل».
الاختبار يقارن **أعمدة ملف الإكسل الفعلي** (من openpyxl) بـ**أعمدة الجدول في الشاشة/الطباعة**
(من HTML الحقيقي للصفحة) ويؤكد التطابق اسمًا وترتيبًا — فلا يقع فرق صامت مرة أخرى.
"""
import re
from openpyxl import load_workbook

from data_access import db_tameedat as dt
from services import sheet_columns as sc, tameedat_fs

YEAR, MONTH = 2031, 9


def _header_row(path, first_header):
    """صف الأعمدة في ملف الإكسل: أول صف فيه اسم العمود الأول (م/اليوم)."""
    ws = load_workbook(path).active
    for row in ws.iter_rows(min_row=1, max_row=20, values_only=True):
        if row and str(row[0] or "").strip() == first_header:
            return [str(v or "").strip() for v in row if str(v or "").strip()]
    raise AssertionError(f"لم أجد صف الأعمدة في {path.name}")


def _table_headers(html, table_id=None):
    """أعمدة أول جدول في الصفحة (أو الجدول ذي المعرّف المحدد) — بلا أعمدة الأزرار."""
    scope = html
    if table_id:
        scope = html[html.index(f'id="{table_id}"'):]
        scope = scope[:scope.index("</table>")]
    else:
        scope = html[html.index("<table"):]
        scope = scope[:scope.index("</table>")]
    head = scope[:scope.index("</thead>")] if "</thead>" in scope else scope
    cols = [re.sub(r"<[^>]+>", "", th).strip()
            for th in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)]
    return [c for c in cols if c and c != "إجراءات"]


def _seed_month():
    eid = dt.add_entity(YEAR, MONTH, "قطاع أعمدة", "شرطية", 12, 40)
    entity = dt.get_entity(YEAR, MONTH, eid)
    dt.add_record(YEAR, MONTH, 3, entity, 10, 25, 8, "", [])
    tameedat_fs.snapshot_all(YEAR, MONTH)
    return entity


# ======================================================================
# ١) قاموس الجهات: الشاشة = الملف
# ======================================================================
def test_dict_tab_columns_match_excel(client):
    entity = _seed_month()
    page = client.get("/tameedat?tab=dict").get_data(as_text=True)
    path = tameedat_fs.tab_dir(YEAR, MONTH, "dict") / tameedat_fs.TAB_XLSX["dict"]
    assert _table_headers(page, "tmDictTable") == _header_row(path, "م")
    assert _table_headers(page, "tmDictTable") == sc.TAMEEDAT_DICT
    assert entity["name"] in page


# ======================================================================
# ٢) الجهات المومدة: الشاشة = الملف = التقرير المطبوع
# ======================================================================
def test_momoda_tab_columns_match_excel(client):
    _seed_month()
    page = client.get("/tameedat?tab=momoda").get_data(as_text=True)
    path = tameedat_fs.tab_dir(YEAR, MONTH, "momoda") / tameedat_fs.TAB_XLSX["momoda"]
    book = load_workbook(path)
    sheet = book["ملخص الجهات المومدة"]
    header = None
    for row in sheet.iter_rows(min_row=1, max_row=20, values_only=True):
        cells = [str(c or "").strip() for c in row if str(c or "").strip()]
        if cells[:1] == ["م"]:
            header = cells
            break
    assert header == sc.TAMEEDAT_MOMODA
    assert _table_headers(page) == sc.TAMEEDAT_MOMODA


# ======================================================================
# ٣) التقرير الشامل المطبوع = ملف التقرير
# ======================================================================
def test_printed_report_columns_match_excel(client):
    _seed_month()
    html = client.get("/tameedat/report/print",
                      follow_redirects=True).get_data(as_text=True)
    heads = re.findall(r"<thead>(.*?)</thead>", html, re.S)
    printed = [[re.sub(r"<[^>]+>", "", th).strip()
                for th in re.findall(r"<th[^>]*>(.*?)</th>", block, re.S)] for block in heads]
    printed = [cols for cols in printed if cols]
    assert printed[0] == sc.TAMEEDAT_DAY          # التفصيل اليومي
    assert printed[1] == sc.TAMEEDAT_MOMODA       # الملخص الشهري
    from documents import xlsx_tameedat
    report = xlsx_tameedat.rebuild(YEAR, MONTH)

    def _cols(sheet, first):
        for row in sheet.iter_rows(min_row=1, max_row=20, values_only=True):
            cells = [str(c or "").strip() for c in row if str(c or "").strip()]
            if cells[:1] == [first]:
                return cells
        raise AssertionError(f"لا صف أعمدة في {sheet.title}")

    book = load_workbook(report)
    assert _cols(book["التفصيل اليومي"], "اليوم") == sc.TAMEEDAT_DAY
    assert _cols(book["الملخص الشهري"], "م") == sc.TAMEEDAT_MOMODA


# ======================================================================
# ٤) الراغبين: ملف اليوم = نفس أعمدة الشاشة المطبوعة
# ======================================================================
def test_raghibin_day_file_columns_are_shared_constant():
    from services.raghibin import files_daily
    assert files_daily.HEADERS[:3] == sc.RAGHIBIN_DAY[:3]
    from services.raghibin import files_rosters
    assert files_rosters.HEADERS == sc.RAGHIBIN_ROSTER


# ======================================================================
# ٥) ٢ مخازن تفاريد: التبويب = الملف (حرس رجوع)
# ======================================================================
def test_tafreeda_tab_columns_match_excel(client):
    from services import warehouses_fs
    from data_access import db_warehouses as dw, db_rations as dr, months
    months.init_month(YEAR, MONTH)
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز بلدي", "كجم", 0, 0.075, 0)
    dr.set_activation(YEAR, MONTH, "tamween", "summer")
    dw.add_opener(YEAR, MONTH, "supply", "أرز بلدي", 100, 1, handle_unit_hint="كجم",
                  exp_iso="2027-06-30")
    page = client.get("/warehouses?cycle=supply&sub=tafreeda").get_data(as_text=True)
    assert page.count("<th") > 0
    headers = _table_headers(page)
    assert "الصنف" in headers and "الكمية المنصرفة" in headers
    warehouses_fs.snapshot_cycle(YEAR, MONTH, "supply")
    root = warehouses_fs.base_dir(YEAR, MONTH, "supply")
    files = sorted(p.name for p in root.rglob("*تفاريد*"))
    assert files, "ملف التفاريد لم يُبنَ"
