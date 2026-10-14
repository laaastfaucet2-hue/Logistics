"""نسخ خطوط الدولى والفترات والمعدل الفعلي والأوراق الرسمية."""
from datetime import date

from core import egtime
from data_access import db_dowail as dw
from data_access import db_rations as dr
from data_access import months
from services import dowail_build as build
from services import dowail_paper_xlsx
from services import local_audit

YEAR, MONTH = 2031, 9


def test_legacy_migration_versions_archive_restore_and_overlap(app):
    conn = months.get_db(YEAR, MONTH)
    conn.executescript(
        "DROP TABLE IF EXISTS dw_version_points;"
        "DROP TABLE IF EXISTS dw_line_versions;"
        "DROP TABLE IF EXISTS dw_rate_custom_state;"
        "DROP TABLE IF EXISTS dw_rate_custom;"
        "CREATE TABLE IF NOT EXISTS dw_lines ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL);"
        "CREATE TABLE IF NOT EXISTS dw_points ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,line_id INTEGER NOT NULL,name TEXT NOT NULL,"
        "force INTEGER NOT NULL DEFAULT 0,responsible TEXT NOT NULL DEFAULT '',UNIQUE(line_id,name));"
        "DELETE FROM dw_points;DELETE FROM dw_lines;")
    conn.execute("INSERT INTO dw_lines(id,name,created_at) VALUES(1,'خط قديم','2031-09-01T00:00:00')")
    conn.execute("INSERT INTO dw_points(id,line_id,name,force,responsible) VALUES(1,1,'نقطة أصلية',7,'مسؤول')")
    conn.commit()
    conn.close()

    migrated = dw.list_lines(YEAR, MONTH)
    assert len(migrated) == 1
    assert migrated[0]["date_from"] is None and migrated[0]["points"][0]["force"] == 7
    assert dw.update_line_period(YEAR, MONTH, 1, 1, 10) == ""

    new_id, error = dw.create_line_version(YEAR, MONTH, "خط قديم", 11, 20)
    assert error == "" and new_id
    assert dw.get_line(YEAR, MONTH, new_id)["points"] == []
    archived = dw.list_archived_lines(YEAR, MONTH)
    assert archived[0]["points"][0]["name"] == "نقطة أصلية"
    assert dw.update_line_period(YEAR, MONTH, new_id, 5, 15)

    restored_id, error = dw.restore_line(YEAR, MONTH, archived[0]["id"])
    assert error == "" and restored_id
    restored = dw.get_line(YEAR, MONTH, restored_id)
    assert restored["date_from"] is None and restored["points"][0]["force"] == 7
    assert dw.update_line_period(YEAR, MONTH, restored_id, 21, 30) == ""
    assert len(dw.list_archived_lines(YEAR, MONTH)) == 2


def test_effective_rate_and_weekly_actual_per_meal(app):
    dr.add_item(YEAR, MONTH, "tamween", "summer", "أرز اختبار", "كجم", 0, .075, 0)
    dr.set_activation(YEAR, MONTH, "tamween", "summer")
    rate_id = dw.save_rate(YEAR, MONTH, "tamween", "أرز اختبار", .005, "كجم")
    day5 = egtime.weekday_sat0(date(YEAR, MONTH, 5))
    day6 = egtime.weekday_sat0(date(YEAR, MONTH, 6))
    dw.save_rate_custom(
        YEAR, MONTH, rate_id,
        [(day5, "breakfast", .01), (day6, "lunch", .01)],
        [(5, "breakfast", .02, "replace"), (6, "lunch", .03, "add")])

    rate = next(row for row in build.rates_with_custom(YEAR, MONTH)
                if row["name"] == "أرز اختبار")
    assert rate["reference_rate"] == .075
    assert rate["manual_rate"] == .005
    assert rate["effective_rate"] == .08
    dates = build.issue_dates(YEAR, MONTH, 5, 6)
    assert build.person_custom(rate, dates) == .06
    row = build.item_row(rate, 10, dates)
    assert row["custom_total"] == .6
    assert row["total"] == 2.2


def test_dowail_pages_and_point_excel_have_official_identity(client, app, tmp_path):
    line_id, error = dw.create_line_version(YEAR, MONTH, "خط فحص", 1, 3)
    assert error == ""
    point_id = dw.add_point(YEAR, MONTH, line_id, "نقطة فحص", 5)
    dw.save_rate(YEAR, MONTH, "tamween", "صنف فحص", .1, "كجم", is_extra=True)

    for tab in ("lines", "rates", "papers", "totals"):
        response = client.get(f"/calc2/dowail/?tab={tab}&line={line_id}")
        assert response.status_code == 200
    rates_page = client.get("/calc2/dowail/?tab=rates").text
    assert "المقرر المرجعي" in rates_page and "الإضافة اليدوية" in rates_page
    assert "dw-calendar-btn" in rates_page and "🗓" not in rates_page
    assert 'data-combo="dwItemsList"' in rates_page
    assert 'data-combo="dwUnitsList"' in rates_page and "كجم" in rates_page
    papers_page = client.get(f"/calc2/dowail/?tab=papers&line={line_id}&from=1&to=2").text
    assert "عرض وطباعة الخط المحدد" in papers_page
    assert "dw-result-matrix" in papers_page and "معدل الفرد" in papers_page

    paper_page = client.get(f"/calc2/dowail/paper/{line_id}?point={point_id}&from=1&to=2")
    assert paper_page.status_code == 200
    text = paper_page.text
    assert "وزارة الداخلية" in text and "شعار المنظومة" in text
    assert "أمين العهدة" in text and "المندوب المستلم" in text

    line = dw.get_line(YEAR, MONTH, line_id)
    data = build.snapshot_for_selections(YEAR, MONTH, [(line, 1, 2)])
    book = dowail_paper_xlsx.build_points_wb(data, line)
    sheet = book.worksheets[0]
    values = [cell.value for row in sheet.iter_rows() for cell in row if cell.value]
    joined = " ".join(str(value) for value in values)
    assert len(sheet._images) == 1
    assert "وزارة الداخلية" in joined and "أمين العهدة" in joined
    assert "المندوب المستلم" in joined and "نقطة فحص" in joined
    path = tmp_path / "ورقة-نقطة.xlsx"
    book.save(path)
    assert local_audit.audit_workbook(path, YEAR, MONTH) == []
