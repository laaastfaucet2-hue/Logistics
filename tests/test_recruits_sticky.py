# -*- coding: utf-8 -*-
"""تثبيت الأيام والرؤوس في تاب المجندين (طلب ١٤/١٠).

المطلوب: مربع «أيام الشهر» في اليومية العامة ما ينزلش مع النزول في الصفحة،
يخلُص مثبّت فوق تحت الشريطين — وكذلك رؤوس جداول الأيام الطويلة
(«التتبع اليومي» في ملف المجند وجدول يومية المجندين) تفضل ظاهرة وأنت بتنزل.

الفحص هنا على العقد نفسه (CSS + القوالب + السكربت) لأن التثبيت سلوك رسم
في المتصفح، والملفات بتتقدّم بالكاش بستاتيك فير — فبنثبّت الشكل النهائي.
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


def _rules(selector_part):
    """كل قاعدة في CSS فيها السلاسل المطلوبة: [(selector, body), ...]."""
    out = []
    for sel, body in re.findall(r"([^{}]*)\{([^{}]*)\}", CSS):
        if selector_part in sel:
            out.append((sel.strip(), body))
    return out


def test_days_box_is_pinned_and_never_falls_back_to_flow():
    rules = _rules(".rc-daysbox")
    assert rules, "لازم قاعدة .rc-daysbox في recruits.css"
    for _sel, body in rules:
        if "position" in body:                       # أي قاعدة تحدد الموضع = لاصقة
            assert "sticky" in body, f"مربع الأيام لازم يفضل لاصق: {body}"
    pinned = "\n".join(b for _s, b in rules)
    assert "var(--stick-top" in pinned               # الإزاحة من متغير الارتفاعات
    assert "z-index: 30" in pinned                   # فوق المحتوى اللي بيمر تحته
    assert "background: var(--card)" in pinned        # خلفية معتمة (مش شفافة)


def test_sticky_headers_declared_for_long_day_tables():
    rules = _rules(".rc-stickwrap")
    assert rules, "لازم قاعدة .rc-stickwrap"
    joined = "\n".join(sel + "{" + body + "}" for sel, body in rules)
    assert "position: sticky" in joined and "var(--stick-rows" in joined
    assert "overflow-x: clip" in joined               # بلا scroll container يقتل اللزق


def test_journal_page_uses_pin_classes_and_loads_sticky_script(client, app):
    _seed_recruit()
    page = client.get("/recruits?tab=journal").data.decode("utf-8")
    assert 'class="panel rc-daysbox"' in page
    assert "rc-stickwrap" in page                     # جدول اليومية
    assert "js/sticky.js" in page                     # قياس الشريطين


def test_file_daily_table_wrapper_is_scroll_free_on_wide_screens(client, app):
    rid = _seed_recruit()
    page = client.get(f"/recruits?tab=file&rid={rid}&ftab=daily").data.decode("utf-8")
    assert '<div class="table-wrap rc-stickwrap">' in page
    assert 'class="rt-table rc-daily-table"' in page
