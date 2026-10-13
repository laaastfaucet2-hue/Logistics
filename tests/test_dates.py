"""The yyyy/mm/dd contract is independent of language, locale, and old ISO storage."""
from datetime import date, datetime, timezone
from pathlib import Path
import pytest
from core import dates, egtime


@pytest.mark.parametrize('text, expected', [
    ('٢٢/٠٩/٢٠٢٦', date(2026,9,22)),            # التراثي dd/mm/yyyy لا يزال مقبولًا
    ('٢٠٢٦/٠٩/٢٢', date(2026,9,22)),            # سنة/شهر/يوم
    ('2026/09/22', date(2026,9,22)),
    ('۲۲/۰۹/۲۰۲۶', date(2026,9,22)),
    ('2026-09-22', date(2026,9,22)),
    ('1/2/2031', date(2031,2,1)), ('03/04/2031', date(2031,4,3)),
    ('29/02/2032', date(2032,2,29)), ('29/02/2000', date(2000,2,29)),
    ('2031/04/03', date(2031,4,3)), ('2031/4/3', date(2031,4,3)),
    ('20260922', date(2026,9,22)),            # لوحة أرقام: yyyymmdd
    ('٢٠٢٦٠٩٢٢', date(2026,9,22)),
    ('⁦٢٠٢٦/٠٩/٢٢⁩', date(2026,9,22)),
    ('‏2026/09/22‎', date(2026,9,22)),
    ('01/01/0001', date(1,1,1)), ('31/12/9999', date(9999,12,31)),
    ('0001/01/01', date(1,1,1)), ('9999/12/31', date(9999,12,31)),
])
def test_parse_explicit_year_first_or_legacy(text, expected):
    assert dates.parse_date(text) == expected
    assert dates.to_iso(text) == expected.isoformat()
    assert dates.format_date(text) == dates.format_date(expected)


@pytest.mark.parametrize('text', [
    '12/31/2026', '31/02/2031', '29/02/2031', '29/02/1900', '00/12/2031',
    '01/00/2031', '01/13/2031', '01/01/0000', '1/1/31', '01-02-2031',
    '2026-02-31', '20311322', '20310230', 'not a date', '31/04/2031',
    '2026/04/31', '2026-09-22T00:00:00',
])
def test_impossible_or_month_first_only_input_is_never_guessed(text):
    with pytest.raises(ValueError): dates.to_iso(text)
    assert dates.format_date(text) == '—'


def test_empty_and_zero_padding_are_explicit():
    for value in (None, '', '   '):
        assert dates.to_iso(value) == ''
        assert dates.format_date(value) == '—'
        assert dates.input_date(value) == ''
    assert dates.format_date('3/4/2031') == '٢٠٣١/٠٤/٠٣'
    assert dates.format_date('2031/4/3') == '٢٠٣١/٠٤/٠٣'
    assert dates.format_date(date(1,1,1), arabic=False) == '0001/01/01'
    assert dates.input_date('31/02/2031') == '31/02/2031'  # Preserve rejected draft, don't erase it.
    assert dates.input_date('2026-10-06') == '٢٠٢٦/١٠/٠٦'
    assert dates.period_date(2031,2,30) == '—'


def test_cairo_timestamp_and_weekday_are_year_first():
    epoch = datetime(2026,9,21,22,15,0,tzinfo=timezone.utc).timestamp()
    cairo = egtime.from_timestamp(epoch)
    assert dates.format_datetime(cairo, seconds=True) == '٢٠٢٦/٠٩/٢٢ — ٠١:١٥:٠٠'
    assert egtime.fmt_ar(date(2026,9,22)) == '٢٠٢٦/٠٩/٢٢ — الثلاثاء'
    assert egtime.fmt_ar(date(2026,9,22), False) == '٢٠٢٦/٠٩/٢٢'
    assert dates.document_date(date(2026,9,22)) == '‎٢٠٢٦/٠٩/٢٢‎'


def test_visible_dates_cannot_fall_back_to_native_us_fields():
    root = Path(__file__).resolve().parents[1]
    for page in (root/'templates').rglob('*.html'):
        source = page.read_text(encoding='utf-8')
        assert 'type="date"' not in source and 'type="datetime-local"' not in source, page
        for field in ('cert_date','cert_expiry','service_start','service_end'):
            assert field + ' | aindic' not in source, page
    assert 'toLocaleDateString' not in (root/'static/js/app.js').read_text(encoding='utf-8')
    assert 'yyyy/mm/dd' in (root/'AGENTS.md').read_text(encoding='utf-8')
    assert 'input[data-date]' in (root/'static/js/date-picker.js').read_text(encoding='utf-8')
