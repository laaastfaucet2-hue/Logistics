# -*- coding: utf-8 -*-
"""سلوك التمرير في تاب المجندين.

المطلوب النهائي: مربع «أيام الشهر» جزء طبيعي من الصفحة؛ عند النزول يختفي
ولا يلاحق المستخدم أو يغطي الجدول. رؤوس الجداول الطويلة وزر الإجازة
المجمّعة وحدهما يظلان مثبتين تحت شريطي البرنامج.

الفحص على عقد CSS + القالب + السكربت لأن التمرير سلوك رسم في المتصفح.
"""
import re
from pathlib import Path

from data_access import db_recruits as recruits

YEAR, MONTH = 2031, 9


def _seed_recruit():
    """مجند واحد يكفي لظهور جدول اليومية وجدول «التتبع اليومي» في القوالب."""
    return recruits.add_recruit(YEAR, MONTH, {"name": "مجند تثبيت", "mil_no": "313",
                                               "address": "قبل"})

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "css" / "recruits.css").read_text(encoding="utf-8")
STICKY_JS = (ROOT / "static" / "js" / "sticky.js").read_text(encoding="utf-8")


def _rules(selector_part):
    """كل قاعدة في CSS فيها السلاسل المطلوبة: [(selector, body), ...]."""
    out = []
    for sel, body in re.findall(r"([^{}]*)\{([^{}]*)\}", CSS):
        if selector_part in sel:
            out.append((sel.strip(), body))
    return out


def test_days_box_stays_in_normal_page_flow():
    rules = _rules(".rc-daysbox")
    assert rules, "لازم قاعدة .rc-daysbox في recruits.css"
    joined = "\n".join(body for _sel, body in rules)
    assert "position: static" in joined
    assert "position: sticky" not in joined
    assert "position: fixed" not in joined
    assert "z-index: 30" not in joined
    assert "max-height:" not in joined


def test_sticky_headers_declared_for_long_day_tables():
    rules = _rules(".rc-stickwrap")
    assert rules, "لازم قاعدة .rc-stickwrap"
    joined = "\n".join(sel + "{" + body + "}" for sel, body in rules)
    assert "position: sticky" in joined and "var(--stick-top" in joined
    assert "var(--stick-rows" not in joined            # مربع الأيام لا يزحزح الرأس
    assert "overflow-x: clip" in joined               # بلا scroll container يقتل اللزق


def test_journal_page_uses_days_and_header_classes_and_loads_sticky_script(client, app):
    _seed_recruit()
    page = client.get("/recruits?tab=journal").data.decode("utf-8")
    assert 'class="panel rc-daysbox"' in page
    assert "rc-stickwrap" in page                     # جدول اليومية
    assert "js/sticky.js" in page                     # قياس الشريطين للرؤوس فقط
    assert 'querySelector(".rc-daysbox")' not in STICKY_JS
    assert "--stick-rows" not in STICKY_JS


def test_file_daily_table_wrapper_is_scroll_free_on_wide_screens(client, app):
    rid = _seed_recruit()
    page = client.get(f"/recruits?tab=file&rid={rid}&ftab=daily").data.decode("utf-8")
    assert '<div class="table-wrap rc-stickwrap">' in page
    assert 'class="rt-table rc-daily-table"' in page
