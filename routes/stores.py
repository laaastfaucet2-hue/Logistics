# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""قسم «المخازن والثلاجات» — موحّد لكل الأصناف (بلا تموينية/متعهد).

تابان: «المخازن» (تسجيل المخازن بمواصفاتها: السعة بالمتر، المرواح، الشفاطات،
التجهيزات) + «حركة وكشف الأرصدة» (حركة كل مخزن داخل/خارج بالتغليف وكشف أرصدته) —
الحركة مطابقة لحركة ٣ مخازن بالتغليف، والتفريدة تلقائية من إذون ٢ مخازن
(الأقرب صلاحية أولًا، وعند التساوي الأقدم إضافةً) فتتجدد تلقائيًا مع أي إذن.
"""
import logging

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from core.auth_core import current_context, current_session, login_required
from core.config import MONTH_NAMES
from core import arabic_numbers as arnum
from data_access import months
from data_access import db_warehouses as dw
from data_access import db_stores
from services import stores_fs as sf

stores_bp = Blueprint("stores", __name__, url_prefix="/stores")

TABS = [
    ("mains", "المخازن", "🏬"),
    ("movement", "حركة وكشف الأرصدة", "📊"),
]
TAB_KEYS = {t[0] for t in TABS}


def _ctx():
    year, month = current_context(g.user["id"])
    months.init_month(year, month)
    return year, month


def _rb(tab="mains", ok=None, err=None):
    _, token = current_session()
    params = {"tab": tab}
    if ok:
        params["ok"] = ok
    if err:
        params["err"] = err
    if token:
        params["sid"] = token
    return redirect(url_for("stores.page", **params))


def _open_path(path):
    import os
    import subprocess
    import sys
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _snapshot(year, month):
    try:
        sf.snapshot(year, month)
    except Exception:
        logging.exception("stores mirror failed")


def _store_fields():
    def opt_float(key):
        value = arnum.parse_float(request.form.get(key))
        return value if value and value > 0 else None

    def opt_int(key):
        value = arnum.parse_int(request.form.get(key))
        return value if value is not None and value >= 0 else None

    return (request.form.get("name"), request.form.get("location"),
            opt_float("capacity_m2"), opt_int("fans"), opt_int("extractors"),
            request.form.get("equipment"), request.form.get("notes"))


@stores_bp.route("")
@stores_bp.route("/")
@login_required
def page():
    year, month = _ctx()
    tab = request.args.get("tab", "mains")
    if tab not in TAB_KEYS:
        tab = "mains"
    try:
        sf.ensure_folders(year, month)
        sf.snapshot(year, month)          # كشف يتجدد تلقائيًا عند كل فتح
    except Exception:
        logging.exception("stores snapshots on open failed")
    editing = None
    if request.args.get("edit"):
        editing = db_stores.get_store(arnum.parse_int(request.args.get("edit")) or 0)
    report = dw.stores_report(year, month) if tab == "movement" else None
    return render_template(
        "stores/main.html",
        year=year, month=month, month_name=MONTH_NAMES[month - 1],
        tabs=TABS, tab=tab,
        stores=db_stores.list_stores(), editing=editing,
        report=report,
        tab_file=sf.TAB_FILES[tab],
    )


@stores_bp.route("/save", methods=["POST"])
@login_required
def save():
    year, month = _ctx()
    store_id = arnum.parse_int(request.form.get("store_id"))
    name, location, capacity, fans, extractors, equipment, notes = _store_fields()
    if not (name or "").strip():
        return _rb("mains", err="اكتب اسم المخزن أولًا")
    if store_id:
        if not db_stores.get_store(store_id):
            return _rb("mains", err="المخزن المطلوب تعديله غير موجود")
        db_stores.update_store(store_id, name, location, capacity, fans,
                               extractors, equipment, notes)
        message = f"عُدّلت مواصفات مخزن «{name.strip()}» — وتسجيلها في البيانات المحلية"
    else:
        db_stores.add_store(name, location, capacity, fans, extractors, equipment, notes)
        message = f"أُضيف مخزن «{name.strip()}» بمواصفاته — وتسجيلها في البيانات المحلية"
    _snapshot(year, month)
    return _rb("mains", ok=message)


@stores_bp.route("/delete", methods=["POST"])
@login_required
def delete():
    year, month = _ctx()
    store = db_stores.get_store(arnum.parse_int(request.form.get("store_id")) or 0)
    if not store:
        return _rb("mains", err="المخزن غير موجود")
    db_stores.delete_store(store["id"])
    _snapshot(year, month)
    return _rb("mains", ok=f"حُذف مخزن «{store['name']}» من السجل — وتسجيلها في البيانات المحلية")


@stores_bp.route("/open-folder/<tab>")
@login_required
def open_folder(tab):
    if tab not in TAB_KEYS:
        abort(404)
    year, month = _ctx()
    sf.ensure_folders(year, month)
    path = sf.file_path(year, month, tab).parent
    if _open_path(path):
        return _rb(tab, ok="تم فتح مجلد المخازن 📂")
    return _rb(tab, err="فتح المجلد متاح عند تشغيل البرنامج على جهازك — استخدم زر التنزيل هنا")


@stores_bp.route("/open-file/<tab>")
@login_required
def open_file(tab):
    if tab not in TAB_KEYS:
        abort(404)
    year, month = _ctx()
    _snapshot(year, month)
    path = sf.file_path(year, month, tab)
    if path.exists() and _open_path(path):
        return _rb(tab, ok=f"تم فتح ملف «{sf.TAB_FILES[tab]}» 📗")
    return redirect(url_for("stores.download", tab=tab))


@stores_bp.route("/download/<tab>")
@login_required
def download(tab):
    from core.downloads import attachment
    if tab not in TAB_KEYS:
        abort(404)
    year, month = _ctx()
    _snapshot(year, month)
    path = sf.file_path(year, month, tab)
    return attachment(path, f"stores-{tab}-{year}-{month:02d}.xlsx")
