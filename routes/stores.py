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
from core import egtime
from data_access import months
from data_access import db_warehouses as dw
from data_access import db_warehouses_stores as dws
from data_access import db_stores
from services import stores_fs as sf

stores_bp = Blueprint("stores", __name__, url_prefix="/stores")

TABS = [
    ("mains", "المخازن", "🏬"),
]
# تابات كارت المخزن — 3 تابات لكل مخزن (توجيه ٠٨/١٠) = 3 فولدرات في الملفات
STORE_TABS = [
    ("moves", "سجل حركة المخزن", "📋"),
    ("items", "الأصناف", "📦"),
    ("balance", "كشف جرد أرصدة المخزن", "🗃️"),
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
    """يُحدّث مرايا الإكسل؛ الملف المفتوح يفشل الآن ويتحدث تلقائيًا بعد إغلاقه."""
    try:
        sf.snapshot(year, month)
        return True
    except Exception:
        logging.exception("stores mirror failed")
        return False


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


def _enrich(target):
    """كل صنف داخل المخزن: رصيده وحركته بالتفصيل مرتبة بالتاريخ (تاب المخازن)
    + آخر رصيد في كشف الجرد — تابات لكل صنف (توجيه ٢٧/٠٩ ليلًا)."""
    if not target:
        return target
    items = {}
    for row in target["inn"]:
        it = items.setdefault(row["item"], {"unit": row["unit"], "in": 0.0,
                                            "out": 0.0, "moves": [], "expiry": ""})
        it["in"] += float(row["qty"] or 0)
        it["moves"].append({
            "dir": "in", "date": row["date_iso"], "qty": float(row["qty"] or 0),
            "cycle": row.get("cycle") or "",
            "producer": row.get("producer") or "",
            "supplier": row.get("supplier") or "",
            "doc": ("إذن إضافة رقم " + arnum.to_arabic_indic(str(row["serial"])))
                   if row.get("serial") else "رصيد أول المدة",
            "pack": row.get("pack_label") or "",
            # 🆕 (١٢/١٠) التغليف المختصر + رصيد المخزن بعد السطر (عمودان زي البرنامج القديم)
            "pack_short": row.get("pack_short") or row.get("pack_label") or "",
            "rem_after": row.get("rem_after") or "",
            "rem_qty": row.get("rem_qty"),
            "entity": "", "receiver": "",
            "expiry": row.get("expiry") or ""})
        if row.get("expiry") and (not it["expiry"] or row["expiry"] < it["expiry"]):
            it["expiry"] = row["expiry"]
    for row in target["out"]:
        it = items.setdefault(row["item"], {"unit": row["unit"], "in": 0.0,
                                            "out": 0.0, "moves": [], "expiry": ""})
        it["out"] += float(row["qty"] or 0)
        it["moves"].append({
            "dir": "out", "date": row["date_iso"], "qty": float(row["qty"] or 0),
            "cycle": row.get("cycle") or "",
            "producer": row.get("producer") or "",
            "supplier": row.get("supplier") or "",
            "doc": "إذن صرف ٢ مخازن رقم " + arnum.to_arabic_indic(str(row.get("permit_no") or "")),
            "pack": row.get("pack_label") or "",
            # 🆕 (١٢/١٠) جهة/مندوب من إذن الصرف + رصيد المخزن بعد السطر
            "rem_after": row.get("rem_after") or "",
            "rem_qty": row.get("rem_qty"),
            "entity": row.get("entity") or "",
            "receiver": row.get("receiver") or "",
            "expiry": row.get("expiry") or ""})
    for name, it in items.items():
        it["balance"] = round(target["balances"].get(name, it["in"] - it["out"]), 6)
        it["pack"] = target["pack_notes"].get(name) or ""
        it["in_pack"] = (target.get("in_packs") or {}).get(name) or ""
        # ١٤/١٠: إجمالي خارج بالتغليف (المزدوجة: بالوحدة + بالتغليف)
        it["out_pack"] = (target.get("out_packs") or {}).get(name) or ""
        it["moves"].sort(key=lambda m: (m["date"] or "", m["dir"]))
        # ١٤/١٠: تاب فرعي لكل صنف — سطر لكل يوم نشط (نفس مصدر الإكسل)
        it["days"] = dws.item_day_rows(target["inn"], target["out"], name,
                                       it.get("unit") or "")
    target["items"] = dict(sorted(items.items(), key=lambda kv: -kv[1]["balance"]))
    # سجل حركة المخزن كله: داخل وخارج كل الأصناف بترتيب التواريخ (توجيه ٠٨/١٠)
    all_moves = []
    for name, it in target["items"].items():
        for m in it["moves"]:
            all_moves.append(dict(m, item=name, unit=it["unit"]))
    all_moves.sort(key=lambda m: (m["date"] or "", m["dir"]))
    target["all_moves"] = all_moves
    # تابات فرعية لكل صنف في سجل الحركة (١٤/١٠): الإجماليات فوق + تاب لكل صنف
    target["mv_items"] = [(name, it) for name, it in target["items"].items() if it["moves"]]
    return target


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
    # تابات المخازن: تاب لكل مخزن في التابين معًا — «المخازن» و«حركة وكشف الأرصدة» —
    # ويفتح التاب حركة المخزن وأرصدته وكل صنف داخله بالتفصيل (توجيه ٢٧/٠٩)
    store_tabs = []
    target = None
    store_sel = None
    if tab in ("mains", "movement"):
        report = dw.stores_report(year, month)
        store_tabs = [{"id": e["store"]["id"], "name": e["store"]["name"]}
                      for e in report["stores"]]
        raw = arnum.parse_int(request.args.get("store"))
        pool = {e["store"]["id"]: e for e in report["stores"]}
        if raw == 0 or (raw is None and not store_tabs):
            store_sel, target = 0, report["unassigned"]
        elif raw in pool:
            store_sel, target = raw, pool[raw]
        else:
            target = report["stores"][0]
            store_sel = target["store"]["id"]
        target = _enrich(target)
    # 🆕 (١٢/١٠) «كافة الأصناف (كشف عام)» — كشف مجمّع بكل المخازن (زي البرنامج القديم)
    general = dw.stores_general_report(year, month)
    return render_template(
        "stores/main.html",
        year=year, month=month, month_name=MONTH_NAMES[month - 1],
        tabs=TABS, tab=tab,
        stores=db_stores.list_stores(), editing=editing,
        store_tabs=store_tabs, store_sel=store_sel, target=target,
        store_tabs_data=STORE_TABS,
        general=general,
        tab_file=sf.TAB_FILES[tab],
        tab_folder="سجل المخازن",
        # علم «عليه حركة» لكل مخزن — يُستخدم في نافذة الحذف/النقل
        has_move={s["id"]: dw.store_has_movement(s["id"]) for s in db_stores.list_stores()},
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
        # توجيه ٠٨/١٠: أول ما المخزن يتعمل فولدره يتعمل (3 فولدرات جواه)
        sf.create_store_folder(year, month, name.strip())
        message = f"أُضيف مخزن «{name.strip()}» بمواصفاته وفولدره المحلي — وتسجيلها في البيانات المحلية"
    _snapshot(year, month)
    return _rb("mains", ok=message)


@stores_bp.route("/delete", methods=["POST"])
@login_required
def delete():
    year, month = _ctx()
    store = db_stores.get_store(arnum.parse_int(request.form.get("store_id")) or 0)
    if not store:
        return _rb("mains", err="المخزن غير موجود")
    # قاعدة ٢٦/٠٩: ممنوع حذف مخزن عليه حركة إلا بنقل أصنافه إلى مخزن آخر
    transfer_id = arnum.parse_int(request.form.get("transfer_to"))
    target = db_stores.get_store(transfer_id) if transfer_id else None
    if dw.store_has_movement(store["id"]):
        if not target or target["id"] == store["id"]:
            return _rb("mains", err="ممنوع حذف «%s»: عليه حركة — انقل أصنافه "
                                    "إلى مخزن أو ثلاجة أخرى أولًا" % store["name"])
        moved = dw.move_store_splits(store["id"], target["id"], target["name"])
        db_stores.delete_store(store["id"])
        if not _snapshot(year, month):
            tail = " — ⚠️ إكسل المرايا مفتوح: اقفله وسيُحدَّث تلقائيًا عند أول فتح للصفحة"
        else:
            tail = ""
        return _rb("mains", ok=f"حُذف مخزن «{store['name']}» ونُقلت أصنافه "
                               f"({arnum.to_arabic_indic(moved)}) إلى «{target['name']}»" + tail)
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


# ---------- ملفات المخزن: فتح المجلد / فتح الملف / تنزيل (توجيه ٠٨/١٠) ----------
_STORE_SUBS = {"movement": sf.SUB_MOVEMENT, "items": sf.SUB_ITEMS,
               "balance": sf.SUB_BALANCE}


def _store_name_or_404(store_id):
    if store_id <= 0:
        return dw.UNASSIGNED   # «غير موزع على مخازن» — نفس اسم الفولدر
    store = db_stores.get_store(store_id)
    if not store:
        abort(404)
    return store["name"]


@stores_bp.route("/open-folder-store/<int:store_id>/<sub>")
@login_required
def open_folder_store(store_id, sub):
    if sub not in _STORE_SUBS:
        abort(404)
    year, month = _ctx()
    name = _store_name_or_404(store_id)
    path = sf.store_sub(year, month, name,
                        {"movement": sf.SUB_MOVEMENT, "items": sf.SUB_ITEMS,
                         "balance": sf.SUB_BALANCE}[sub])
    if _open_path(path):
        return _rb("mains", ok=f"تم فتح مجلد «{_STORE_SUBS[sub]}» لمخزن «{name}» 📂")
    return _rb("mains", err="فتح المجلد متاح عند تشغيل البرنامج على جهازك — استخدم زر التنزيل هنا")


@stores_bp.route("/open-file-store/<int:store_id>/<sub>")
@login_required
def open_file_store(store_id, sub):
    if sub not in _STORE_SUBS:
        abort(404)
    year, month = _ctx()
    name = _store_name_or_404(store_id)
    item = (request.args.get("item") or "").strip()
    if sub == "items" and not item:
        return _rb("mains", err="اختر صنفًا من تاب الأصناف لفتح ملفه 📗")
    _snapshot(year, month)
    path = sf.store_file_path(year, month, name, sub, item or None)
    if path.exists() and _open_path(path):
        return _rb("mains", ok=f"تم فتح ملف «{path.name}» 📗")
    return redirect(url_for("stores.download_store", store_id=store_id, sub=sub,
                            **({"item": item} if item else {})))


@stores_bp.route("/download-store/<int:store_id>/<sub>")
@login_required
def download_store(store_id, sub):
    from core.downloads import attachment
    if sub not in _STORE_SUBS:
        abort(404)
    year, month = _ctx()
    name = _store_name_or_404(store_id)
    item = (request.args.get("item") or "").strip()
    if sub == "items" and not item:
        abort(404)
    _snapshot(year, month)
    path = sf.store_file_path(year, month, name, sub, item or None)
    if not path.exists():
        abort(404)
    return attachment(path, f"store-{store_id}-{sub}-{year}{month:02d}.xlsx")
