# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحة الدباجة والتوقيعات الرسمية — تُعمَّم على كل ملفات الإكسل والوورد الرسمية.

المحتوى: مربعات أسطر الدباجة (يمين أعلى المستند) + اللوجو (شمال أعلى المستند)
+ توقيعان (رتبة/اسم) يمين وشمال أسفل المستند + معاينة حية لشكل الوورد والإكسل.
"""
from data_access import dataguard
from flask import g
from core.downloads import attachment
import os
import sys
import subprocess
from urllib.parse import quote

from flask import (Blueprint, render_template, request, redirect,
                   url_for, abort, send_file)

from core.auth_core import login_required, current_session, current_context
from data_access import db_letterhead as db
from services import legacy_months
from services.images import save_logo
from services.document_refresh import refresh_month
from core.config import MONTH_NAMES, month_folder
from data_access import storage
from documents import xlsx_rations
from documents import letterhead_docx

letterhead_bp = Blueprint("letterhead", __name__, url_prefix="/letterhead")

ALLOWED_LOGO = {"png", "jpg", "jpeg", "webp"}
SETTING_KEYS = ["lh_1", "lh_2", "lh_3", "lh_4",
                "sig_right_rank", "sig_right_name",
                "sig_left_rank", "sig_left_name"]


def _rb(ok=None, err=None):
    _, token = current_session()
    year, month = _ctx()
    return redirect(url_for("letterhead.page", year=year, month=month, sid=token, ok=ok, err=err))


def _ctx():
    return current_context(g.user["id"])


def _page_vars():
    year, month = _ctx()
    v = db.template_vars(year, month)
    v.update(year=year, month=month, month_name=MONTH_NAMES[month-1],
             legacy_letterhead=legacy_months.letterhead_available() and not legacy_months.imported("letterhead", year, month),
             folder_path=f"database/{year}/{month_folder(month)}/الدباجة/")
    v["can_open"] = os.name == "nt"
    return v


# ======================================================================
# الصفحة + المعاينة الحية
# ======================================================================
@letterhead_bp.route("")
@letterhead_bp.route("/")
@login_required
def page():
    return render_template("letterhead.html", **_page_vars())


# ======================================================================
# حفظ الإعدادات + رفع اللوجو (يعيد بناء الوورد ويحدّث توقيعات كل الإكسل)
# ======================================================================
@letterhead_bp.route("/save", methods=["POST"])
@login_required
def save():
    year, month = _ctx()
    values = {key: (request.form.get(key) or "").strip() for key in SETTING_KEYS}
    file = request.files.get("logo")
    if file and file.filename:
        try:
            values["logo_file"] = save_logo(file.stream, storage.letterhead_dir(year, month))
        except ValueError as exc:
            return _rb(err=str(exc))
    db.save(year, month, values)
    try:
        refresh_month(year, month)
    except (OSError, ValueError):
        return _rb(err="حُفظت الدباجة، لكن تعذّر تحديث مستند؛ أغلق Excel أو Word ثم أعد الحفظ")
    return _rb(ok="حُفظت دباجة هذا الشهر مع اللوجو والتوقيعات، وتحدّثت ملفات Excel وWord الخاصة به")


# ======================================================================
# حذف اللوجو
# ======================================================================
@letterhead_bp.route("/logo/delete", methods=["POST"])
@login_required
def logo_delete():
    year, month = _ctx()
    db.save(year, month, {"logo_file": ""})
    refresh_month(year, month)
    return _rb(ok="حُذف اللوجو من هذا الشهر وتحدّثت مستنداته")


# ======================================================================
# عرض اللوجو داخل الصفحة
# ======================================================================
@letterhead_bp.route("/logo")
@login_required
def logo_view():
    logo = db.get_setting(*_ctx(), "logo_file")
    path = storage.letterhead_dir(*_ctx()) / logo if logo else None
    if not path or not path.exists():
        abort(404)
    return send_file(str(path))


# ======================================================================
# ملف الوورد: تنزيل/فتح + فتح المجلد
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


@letterhead_bp.route("/download-docx")
@login_required
def download_docx():
    path = letterhead_docx.ensure(*_ctx())
    return attachment(path, "letterhead.docx")


@letterhead_bp.route("/download-zip")
@login_required
def download_zip():
    """تنزيل مجلد الدباجة كاملًا (الوورد + اللوجو) أرشيف ZIP — يعمل من أي متصفح."""
    letterhead_docx.ensure(*_ctx())
    zip_path = dataguard.zip_folder_tmp(storage.letterhead_dir(*_ctx()), prefix="letterhead")
    resp = send_file(str(zip_path), as_attachment=True, download_name="letterhead.zip", conditional=False, max_age=0)
    resp.call_on_close(lambda: os.path.exists(zip_path) and os.remove(str(zip_path)))
    return resp


@letterhead_bp.route("/open-docx")
@login_required
def open_docx():
    path = letterhead_docx.ensure(*_ctx())
    if _open_path(path):
        return _rb(ok="تم فتح ملف الوورد 📄")
    return redirect(url_for("letterhead.download_docx",
                            sid=request.args.get("sid", "")))


@letterhead_bp.route("/open-folder")
@login_required
def open_folder():
    if _open_path(storage.letterhead_dir(*_ctx())):
        return _rb(ok="تم فتح مجلد الدباجة 📂")
    return _rb(err="فتح المجلد متاح عند تشغيل البرنامج على جهازك — استخدم زر التنزيل هنا")
