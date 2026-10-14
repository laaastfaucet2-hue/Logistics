"""ضوابط الجداول ولغة الواجهة والإحصائيات."""
from pathlib import Path
import re

from services import stats_master


ROOT = Path(__file__).resolve().parents[1]
ARABIC = "ء-ي"
FORBIDDEN_UI_WORDS = (
    "مفيش", "ما فيش", "النهارده", "بكرة", "علطول", "دايمًا",
    "زرار", "فورم", "تابات", "تويبات", "فولدر", "شيت", "لوجو",
    "لينك", "بالظبط", "لسه", "عايز", "من غير", "فطار", "باسورد",
    "كارت", "كروت", "فلترة", "موديل", "داتا", "بنر", "بانر",
    "كوبي", "توب",
)


def _visible_template_source(path):
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"{#.*?#}", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<script\b.*?</script>", "", text, flags=re.S | re.I)
    text = re.sub(r"<style\b.*?</style>", "", text, flags=re.S | re.I)
    return text


def test_shared_table_system_is_loaded_and_covers_interface_tables():
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    assert "css/tables.css" in base
    assert "js/tables.js" in base
    table_script = (ROOT / "static/js/tables.js").read_text(encoding="utf-8")
    assert 'var selector = "table"' in table_script
    assert "MutationObserver" in table_script
    templates = list((ROOT / "templates").rglob("*.html"))
    table_count = sum(len(re.findall(r"<table\b", p.read_text(encoding="utf-8"), re.I))
                      for p in templates)
    assert table_count >= 100


def test_removed_statistics_sections_are_not_offered():
    supply_keys = {key for key, _icon, _name in stats_master.SECTION_DEFS["supply"]}
    assert not {"raghibin", "rations_tamween", "wh_supply"} & supply_keys


def test_visible_templates_do_not_use_reviewed_colloquial_words():
    findings = []
    for path in (ROOT / "templates").rglob("*.html"):
        text = _visible_template_source(path)
        for word in FORBIDDEN_UI_WORDS:
            pattern = rf"(?<![{ARABIC}]){re.escape(word)}(?![{ARABIC}])"
            if re.search(pattern, text):
                findings.append(f"{path.relative_to(ROOT)}: {word}")
    assert not findings, "\n".join(findings)
