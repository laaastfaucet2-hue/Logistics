# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""«دفتر 4 مخازن» — راوتات الإدخال: شطب اليومى / سعر الوحدة / سطر الموافقة.

كل حفظ يرجع للتب نفسه (cycle + wh4tab + الصنف المحدد) مع رسالة نجاح.
"""

from flask import Blueprint, redirect, request, url_for
from flask.globals import g
from core import arabic_numbers as arnum
from core.auth_core import current_context, login_required
from data_access import db_wh4 as w4
from data_access import months
from services import wh4_build as wh4b

wh4_bp = Blueprint("wh4", __name__, url_prefix="/warehouses")

CYCLES = ("supply", "contractor")


def _ctx():
    year, month = current_context(g.user["id"])
    months.init_month(year, month)
    return year, month


def _mirror(year, month, cycle):
    """مرايا الإكسل تتحدث بعد أي حفظ — لو الملف مفتوح يتأجل تلقائيًا."""
    try:
        from services import warehouses_fs as wf
        wf.snapshot_cycle(year, month, cycle)
    except Exception:
        import logging
        logging.exception("wh4 mirror failed")


def _cycle():
    return request.form.get("cycle") if request.form.get("cycle") in CYCLES else "supply"


def _back(year, month, ok=None):
    return redirect(url_for(
        "warehouses.page", cycle=_cycle(), sub="wh4",
        wh4tab=request.form.get("wh4tab") or "daily",
        wh4item=request.form.get("wh4item") or "", ok=ok))


@wh4_bp.route("/wh4/strike", methods=["POST"])
@login_required
def strike_save():
    """خلية شطب: صنف + يوم + كمية (فاضي/صفر = مسح الشطب اليدوي).

    ١٣/١٠: الخلية المعروضة = تلقائي (أذون ٢ مخازن) + يدوي، فبيتحفظ هنا
    الجزء اليدوي بس = مدخل الخلية − التلقائي — وإلا الاستهلاك هيتحسب
    مرتين (مرة من الأذون ومرة من الشطب).
    """
    year, month = _ctx()
    day = arnum.parse_int(request.form.get("day")) or 0
    qty = arnum.parse_float(request.form.get("qty"))
    cyc = _cycle()
    if not (1 <= day <= 31):
        return _back(year, month)
    manual = round((qty or 0.0)
                   - wh4b.auto_qty_for(year, month, cyc,
                                       request.form.get("item") or "", day), 6)
    if manual < 0:
        manual = 0.0
    if not w4.set_strike(year, month, cyc, request.form.get("item"), day, manual):
        return _back(year, month, ok=None)
    _mirror(year, month, cyc)
    verb = "اتمسح شطب يدوي" if not manual else "تم حفظ الشطب اليدوي"
    return _back(year, month, ok=f"{verb} «{request.form.get('item')}» — يوم {day}")


@wh4_bp.route("/wh4/price", methods=["POST"])
@login_required
def price_save():
    year, month = _ctx()
    price = arnum.parse_float(request.form.get("price"))
    cyc = _cycle()
    if w4.set_price(year, month, cyc, request.form.get("item"), price):
        _mirror(year, month, cyc)
        return _back(year, month, ok=f"تم حفظ سعر الوحدة لصنف «{request.form.get('item')}»")
    return _back(year, month)


@wh4_bp.route("/wh4/meta", methods=["POST"])
@login_required
def meta_save():
    year, month = _ctx()
    key = request.form.get("key")
    if key in ("approval",) and w4.set_meta(year, month, _cycle(), key,
                                            request.form.get("value")):
        return _back(year, month, ok="تم حفظ سطر الموافقة — يظهر أسفل المسند الرسمي")
    return _back(year, month)
