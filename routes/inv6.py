# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""قسم «6 مخازن (جرد الأصناف)» — دفتر جرد الأصناف.

بيحدد يوم في الشهر، فيجيب كل أصناف دفتر ٣ مخازن (الإمداد + المتعهد) برصيد
ختام اليوم ده (بعد إضافات ١ مخازن ومنصرف ٢ مخازن) بوحدة الصنف في دفتر ٣ مخازن.
«تطبيق الجرد» يحفظ اليوم ويطبع شيت الإكسل المعتمد في:
06-مستودعات وسجلات/6-مخازن/يوم ١/<يوم>-<شهر>-<سنة>.xlsx
"""
import logging
import os
import subprocess
import sys

from flask import (Blueprint, g, redirect, request, url_for, abort)

from core.auth_core import current_context, current_session, login_required
from core import arabic_numbers as arnum
from core import egtime
from core.downloads import attachment
from data_access import db_inv6 as di6
from data_access import months
from services import inv6_build as ib
from services import inv6_fs as if6

inv6_bp = Blueprint("inv6", __name__, url_prefix="/inv6")


def _ctx():
    year, month = current_context(g.user["id"])
    months.init_month(year, month)
    return year, month


def _rb(day=None, ok=None, err=None):
    _, token = current_session()
    params = {}
    if day:
        params["day"] = int(day)
    if ok:
        params["ok"] = ok
    if err:
        params["err"] = err
    if token:
        params["sid"] = token
    return redirect(url_for("inv6.page", **params))


def _open_path(path):
    """يفتح ملف/فولدر في مدير النظام (نفس نمط بقية الأقسام)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        logging.getLogger(__name__).exception("فتح المسار فاشل")


@inv6_bp.route("")
@inv6_bp.route("/")
@login_required
def page():
    # «6 مخازن» فرع جوه صفحة «مستودعات وسجلات» (توجيه ١٠/١٠) — الروابط القديمة
    # توجّه للتبويب نفسه مع الحفاظ على اليوم والرسايل.
    keep = {k: v for k, v in request.args.items() if k in ("day", "ok", "err", "cycle")}
    keep.setdefault("sub", "inv6")
    return redirect(url_for("warehouses.page", **keep))


@inv6_bp.route("/apply", methods=["POST"])
@login_required
def apply():
    year, month = _ctx()
    days_in = egtime.days_in_month(year, month)
    day = arnum.parse_int(request.form.get("day"), 1)
    if not day or not 1 <= day <= days_in:
        return _rb(1, err="يوم الجرد خارج الشهر")
    f = request.form
    header = {
        "day": day,
        "sector": f.get("sector", ""),
        "warehouse": f.get("warehouse", ""),
        "owner_rank": f.get("owner_rank", ""),
        "owner_name": f.get("owner_name", ""),
        "sigs": {
            "chief": {"rank": f.get("sig_chief_rank", ""),
                      "name": f.get("sig_chief_name", "")},
            "manager": {"rank": f.get("sig_manager_rank", ""),
                        "name": f.get("sig_manager_name", "")},
            "committee": [f.get("sig_committee_1", ""),
                          f.get("sig_committee_2", ""),
                          f.get("sig_committee_3", "")],
            "owner": {"rank": f.get("sig_owner_rank", ""),
                      "name": f.get("sig_owner_name", "")},
            "writer": {"rank": f.get("sig_writer_rank", ""),
                       "name": f.get("sig_writer_name", "")},
        },
    }
    rows = []
    for i in range(999):
        item_id = f.get(f"row{i}_item_id")
        if item_id is None:
            break
        try:
            counted = arnum.parse_float(f.get(f"row{i}_counted"), 0.0)
            price = arnum.parse_float(f.get(f"row{i}_price"), 0.0)
        except (ValueError, TypeError):
            counted, price = 0.0, 0.0
        rows.append({
            "cycle": f.get(f"row{i}_cycle", "supply"),
            "item_id": arnum.parse_int(item_id, 0),
            "name": f.get(f"row{i}_name", ""),
            "unit": f.get(f"row{i}_unit", ""),
            "serial": arnum.parse_int(f.get(f"row{i}_serial"), i + 1),
            "book": arnum.parse_float(f.get(f"row{i}_book"), 0.0),
            "counted": counted or 0.0,
            "price": price or 0.0,
            "status_item": f.get(f"row{i}_status_item", "جيدة"),
            "status_issue": f.get(f"row{i}_status_issue", "جيدة"),
        })
    if not rows:
        return _rb(day, err="لا توجد أصناف في دفتر ٣ مخازن لهذا الشهر — سجّل الأصناف أولًا")
    try:
        out = ib.apply_day(year, month, day, header, rows)
    except Exception:
        logging.getLogger(__name__).exception("تطبيق الجرد فاشل")
        return _rb(day, err="وقع خطأ أثناء تطبيق الجرد — حاول مرة أخرى")
    return _rb(day, ok=(f"تم تطبيق جرد اليوم {arnum.to_arabic_indic(str(day))} "
                        f"وحفظ الملف في: {out['rel']}"))


@inv6_bp.route("/delete", methods=["POST"])
@login_required
def delete():
    year, month = _ctx()
    day = arnum.parse_int(request.form.get("day"), 0)
    if not day or not di6.load_day(year, month, day):
        return _rb(1, err="هذا اليوم غير محفوظ")
    di6.delete_day(year, month, day)
    if6.delete_day_files(year, month, day)
    return _rb(1, ok=f"تم حذف جرد اليوم {arnum.to_arabic_indic(str(day))} وملفه")


@inv6_bp.route("/download")
@login_required
def download():
    year, month = _ctx()
    day = arnum.parse_int(request.args.get("day"), 0)
    fpath = if6.day_file(year, month, day) if day else None
    if not fpath or not fpath.is_file():
        # لو مش محفوظ على القرص — تولده من بيانات اليوم المحفوظة
        if day and di6.load_day(year, month, day):
            if6.save_to_disk(year, month, day)
        else:
            abort(404)
        fpath = if6.day_file(year, month, day)
    if not fpath.is_file():
        abort(404)
    return attachment(fpath, fallback="inv6" + fpath.suffix)


@inv6_bp.route("/open")
@login_required
def open():
    year, month = _ctx()
    day = arnum.parse_int(request.args.get("day"), 0)
    target = request.args.get("what", "dir")
    if day:
        if target == "file":
            fpath = if6.day_file(year, month, day)
            if fpath.is_file():
                _open_path(fpath)
        else:
            _open_path(if6._safe_day_dir(year, month, day))
    return _rb(day or None)
