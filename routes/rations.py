# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مسارات صفحتي المقررات (التمونيية والمتعهد) — Blueprint مستقل.

ملاحظة: app.py يسجّل هذا الـBlueprint في نهايته، لذا الاستيراد من app آمن هنا.
"""
import os
import sys
import subprocess
from urllib.parse import quote

from flask import (Blueprint, render_template, request, redirect,
                   url_for, g, abort, send_file)

from auth_core import login_required, current_context, current_session
from config import (SECTIONS, RATION_KINDS, RATION_KIND_MAP, MEALS, DAYS, UNITS,
                    MONTH_NAMES)
import arabic_numbers as arnum
import months
import db_rations as dr
import db_entities as de
import xlsx_rations

rations_bp = Blueprint("rations", __name__, url_prefix="/rations")

SECTION_CFG = {
    "tamween":    {"index": 4, "has_dist": False},
    "contractor": {"index": 5, "has_dist": True},
}


def _rb(section, kind=None, tab=None, ok=None, err=None):
    """يرجع لصفحة القسم مع الحفاظ على التوكن ورسالة اختيارية."""
    params = []
    if kind:
        params.append("kind=" + quote(kind))
    if tab:
        params.append("tab=" + quote(tab))
    _, token = current_session()
    if token:
        params.append("sid=" + quote(token))
    if ok:
        params.append("ok=" + quote(ok))
    if err:
        params.append("err=" + quote(err))
    target = url_for("rations.page", section=section)
    return redirect(target + ("?" + "&".join(params) if params else ""))


def _ctx_month():
    year, month = current_context(g.user["id"])
    months.init_month(year, month)
    return year, month


def _page_vars(section, kind):
    import storage
    year, month = current_context(g.user["id"])
    return {
        "section": section,
        "cfg": SECTION_CFG[section],
        "section_name": SECTIONS[SECTION_CFG[section]["index"] - 1]["name"],
        "kind": kind,
        "kinds": RATION_KINDS,
        "kmap": RATION_KIND_MAP,
        "active_kind": dr.get_activation(year, month, section),
        "meals": MEALS,
        "days": DAYS,
        "units": UNITS,
        "years": storage.list_years(),
        "month_names": MONTH_NAMES,
        "year": year,
        "month": month,
        "edit_id": arnum.parse_int(request.args.get("edit")),
        "known_names": dr.known_item_names(year, month, section),
    }


# ======================================================================
# الصفحة الرئيسية للقسم
# ======================================================================
@rations_bp.route("/<section>")
@login_required
def page(section):
    cfg = SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    active = dr.get_activation(year, month, section)
    kind = request.args.get("kind") or active or RATION_KINDS[0][0]
    if kind not in RATION_KIND_MAP:
        kind = RATION_KINDS[0][0]
    xlsx_rations.ensure(year, month, section)
    v = _page_vars(section, kind)
    if cfg["has_dist"] and request.args.get("tab") == "dist":
        v["entities"] = de.list_entities(year, month)
        v["ee"] = arnum.parse_int(request.args.get("ee"))
        v["ee_item"] = de.get_entity_item(year, month, v["ee"]) if v["ee"] else None
        return render_template("rations_dist.html", **v)
    v["items"], v["custom"] = dr.get_items(year, month, section, kind)
    v["edit_item"] = dr.get_item(year, month, v["edit_id"]) if v["edit_id"] else None
    return render_template("rations.html", **v)


# ======================================================================
# الأصناف: إضافة/تعديل/حذف (+ تحديث الإكسل فورًا)
# ======================================================================
@rations_bp.route("/<section>/items/add", methods=["POST"])
@login_required
def item_add(section):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    name = (request.form.get("name") or "").strip()
    kind = request.form.get("kind", RATION_KINDS[0][0])
    if not name:
        return _rb(section, kind=kind, err="اكتب اسم الصنف أولًا")
    if dr.item_exists(year, month, section, kind, name):
        return _rb(section, kind=kind,
                   err=f"«{name}» موجود بالفعل في هذا المقرر — عدّله من زر ✏️")
    dr.add_item(year, month, section, kind, name,
                (request.form.get("unit") or "").strip(),
                arnum.parse_float(request.form.get("breakfast")),
                arnum.parse_float(request.form.get("lunch")),
                arnum.parse_float(request.form.get("dinner")))
    xlsx_rations.rebuild(year, month, section)
    return _rb(section, kind=kind, ok=f"أُضيف الصنف «{name}» وتم تحديث الإكسل")


@rations_bp.route("/<section>/items/edit/<int:item_id>", methods=["POST"])
@login_required
def item_edit(section, item_id):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    name = (request.form.get("name") or "").strip()
    kind = request.form.get("kind", RATION_KINDS[0][0])
    if not name:
        return _rb(section, kind=kind, err="اكتب اسم الصنف أولًا")
    dr.update_item(year, month, item_id, name, (request.form.get("unit") or "").strip(),
                   arnum.parse_float(request.form.get("breakfast")),
                   arnum.parse_float(request.form.get("lunch")),
                   arnum.parse_float(request.form.get("dinner")))
    xlsx_rations.rebuild(year, month, section)
    return _rb(section, kind=kind, ok="تم حفظ التعديل وتحديث الإكسل")


@rations_bp.route("/<section>/items/delete/<int:item_id>", methods=["POST"])
@login_required
def item_delete(section, item_id):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    dr.delete_item(year, month, item_id)
    xlsx_rations.rebuild(year, month, section)
    return _rb(section, kind=request.form.get("kind"), ok="تم حذف الصنف وتحديث الإكسل")


# ======================================================================
# المقرر المخصص (جدول أيام × وجبات لصنف واحد)
# ======================================================================
@rations_bp.route("/<section>/custom/<int:item_id>", methods=["POST"])
@login_required
def custom_save(section, item_id):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    entries = []
    for d in range(7):
        for meal, _label in MEALS:
            qty = arnum.parse_float(request.form.get(f"c_{d}_{meal}", ""))
            if qty is not None:
                entries.append((d, meal, qty))
    dr.save_custom(year, month, item_id, entries)
    xlsx_rations.rebuild(year, month, section)
    return _rb(section, kind=request.form.get("kind"),
               ok="تم حفظ المقرر المخصص وتحديث الإكسل")


# ======================================================================
# التفعيل — مقرر واحد فقط
# ======================================================================
@rations_bp.route("/<section>/activate", methods=["POST"])
@login_required
def activate(section):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    kind = request.form.get("kind", "")
    if kind not in RATION_KIND_MAP:
        return _rb(section, err="نوع مقرر غير صالح")
    dr.set_activation(year, month, section, kind)
    xlsx_rations.rebuild(year, month, section)
    label = RATION_KIND_MAP[kind]["name"]
    return _rb(section, kind=kind,
               ok=f"تم تفعيل المقرر {label} — هو المقرر النشط الوحيد الآن")


# ======================================================================
# نسخ المقرر إلى شهر/سنة أخرى (يستبدل الموجود)
# ======================================================================
@rations_bp.route("/<section>/copy", methods=["POST"])
@login_required
def copy_kind(section):
    import storage
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    kind = request.form.get("kind", RATION_KINDS[0][0])
    to_year = arnum.parse_int(request.form.get("to_year"))
    to_month = arnum.parse_int(request.form.get("to_month"))
    if to_year not in storage.list_years() or to_month is None or not (1 <= to_month <= 12):
        return _rb(section, kind=kind, err="اختر سنة وشهرًا صحيحين للنسخ")
    if to_year == year and to_month == month:
        return _rb(section, kind=kind, err="اختر شهرًا مختلفًا عن الحالي")
    months.init_month(to_year, to_month)
    n = dr.copy_kind(year, month, section, kind, to_year, to_month)
    xlsx_rations.rebuild(to_year, to_month, section)
    tgt = f"{MONTH_NAMES[to_month-1]} {arnum.to_arabic_indic(to_year)}"
    return _rb(section, kind=kind, ok=f"نُسخت {arnum.to_arabic_indic(n)} صنفًا إلى {tgt}")


# ======================================================================
# الجهات (تاب توزيع المقررات — قسم المتعهد فقط)
# ======================================================================
@rations_bp.route("/<section>/entities/add", methods=["POST"])
@login_required
def entity_add(section):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    name = (request.form.get("name") or "").strip()
    if not name:
        return _rb(section, tab="dist", err="اكتب اسم الجهة أولًا")
    n, kind = de.add_entity(year, month, section, name)
    xlsx_rations.rebuild(year, month, section)
    kl = RATION_KIND_MAP[kind]["name"]
    return _rb(section, tab="dist",
               ok=f"أُضيفت «{name}» وسُحبت لها {arnum.to_arabic_indic(n)} صنفًا "
                  f"بأرقامها من المقرر {kl} النشط في هذا القسم")


@rations_bp.route("/<section>/entities/resync/<int:entity_id>", methods=["POST"])
@login_required
def entity_resync(section, entity_id):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    n, kind = de.resync_entity(year, month, entity_id, section)
    xlsx_rations.rebuild(year, month, section)
    kl = RATION_KIND_MAP[kind]["name"]
    return _rb(section, tab="dist",
               ok=f"🔄 أُعيد سحب {arnum.to_arabic_indic(n)} صنفًا "
                  f"من المقرر {kl} النشط — وتحديث الإكسل")


@rations_bp.route("/<section>/entities/delete/<int:entity_id>", methods=["POST"])
@login_required
def entity_delete(section, entity_id):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    de.delete_entity(year, month, entity_id)
    xlsx_rations.rebuild(year, month, section)
    return _rb(section, tab="dist", ok="تم حذف الجهة وجدولها وتحديث الإكسل")


@rations_bp.route("/<section>/eitems/add/<int:entity_id>", methods=["POST"])
@login_required
def eitem_add(section, entity_id):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    name = (request.form.get("name") or "").strip()
    if not name:
        return _rb(section, tab="dist", err="اكتب اسم الصنف أولًا")
    if de.entity_item_exists(year, month, entity_id, name):
        return _rb(section, tab="dist",
                   err=f"«{name}» موجود بالفعل في جدول هذه الجهة — عدّله من زر ✏️")
    de.add_entity_item(year, month, entity_id, name,
                       (request.form.get("unit") or "").strip(),
                       arnum.parse_float(request.form.get("breakfast")),
                       arnum.parse_float(request.form.get("lunch")),
                       arnum.parse_float(request.form.get("dinner")))
    xlsx_rations.rebuild(year, month, section)
    return _rb(section, tab="dist", ok=f"أُضيف «{name}» وتم تحديث الإكسل")


@rations_bp.route("/<section>/eitems/edit/<int:item_id>", methods=["POST"])
@login_required
def eitem_edit(section, item_id):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    name = (request.form.get("name") or "").strip()
    if not name:
        return _rb(section, tab="dist", err="اكتب اسم الصنف أولًا")
    de.update_entity_item(year, month, item_id, name,
                          (request.form.get("unit") or "").strip(),
                          arnum.parse_float(request.form.get("breakfast")),
                          arnum.parse_float(request.form.get("lunch")),
                          arnum.parse_float(request.form.get("dinner")))
    xlsx_rations.rebuild(year, month, section)
    return _rb(section, tab="dist", ok="تم حفظ التعديل وتحديث الإكسل")


@rations_bp.route("/<section>/eitems/delete/<int:item_id>", methods=["POST"])
@login_required
def eitem_delete(section, item_id):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    de.delete_entity_item(year, month, item_id)
    xlsx_rations.rebuild(year, month, section)
    return _rb(section, tab="dist", ok="تم حذف الصنف وتحديث الإكسل")


# ======================================================================
# تخصيص أيام التوزيع لصنف جهة
# ======================================================================
@rations_bp.route("/<section>/eitems/days/<int:item_id>", methods=["POST"])
@login_required
def eitem_days(section, item_id):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    # حفظ دفعة واحدة: كل يوم محدد + مقرره الخاص (فارغ = رقم الوجبات العام)
    day_qty = {}
    for d in range(7):
        if request.form.get(f"wd_{d}") is not None:
            day_qty[d] = arnum.parse_float(request.form.get(f"qty_{d}", ""))
    de.set_days(year, month, item_id, day_qty)
    xlsx_rations.rebuild(year, month, section)
    msg = (f"حُفظ تخصيص {arnum.to_arabic_indic(len(day_qty))} يومًا بمقرراتها ✓"
           if day_qty else "عاد الصنف للصرف اليومي")
    return _rb(section, tab="dist", ok=msg + " — وتحديث الإكسل")


# ======================================================================
# ملفات الإكسل: فتح المجلد / فتح الشيت / تنزيل
# ======================================================================
def _open_path(path):
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


@rations_bp.route("/<section>/open-excel")
@login_required
def open_excel(section):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    path = xlsx_rations.ensure(year, month, section)
    if _open_path(path):
        return _rb(section, ok="تم فتح ملف الإكسل من مجلد القسم 📗")
    return redirect(url_for("rations.download_excel", section=section,
                            sid=request.args.get("sid", "")))


@rations_bp.route("/<section>/open-folder")
@login_required
def open_folder(section):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    path, _ = xlsx_rations.xlsx_path(year, month, section)
    if _open_path(path.parent):
        return _rb(section, ok="تم فتح مجلد القسم 📂")
    return _rb(section, err="فتح المجلد متاح عند تشغيل البرنامج على جهازك — استخدم زر التنزيل هنا")


@rations_bp.route("/<section>/download-excel")
@login_required
def download_excel(section):
    SECTION_CFG.get(section) or abort(404)
    year, month = _ctx_month()
    path = xlsx_rations.ensure(year, month, section)
    return send_file(str(path), as_attachment=True, download_name=path.name)
