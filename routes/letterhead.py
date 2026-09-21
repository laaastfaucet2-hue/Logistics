# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحة الدباجة والتوقيعات الرسمية — تُعمَّم على كل ملفات الإكسل والوورد الرسمية.

المحتوى: مربعات أسطر الدباجة (يمين أعلى المستند) + اللوجو (شمال أعلى المستند)
+ توقيعان (رتبة/اسم) يمين وشمال أسفل المستند + معاينة حية لشكل الوورد والإكسل.
"""
import dataguard
import os
import sys
import subprocess
from urllib.parse import quote

from flask import (Blueprint, render_template, request, redirect,
                   url_for, abort, send_file)

from auth_core import login_required, current_session
import database as db
import storage
import xlsx_rations
import letterhead_docx

letterhead_bp = Blueprint("letterhead", __name__, url_prefix="/letterhead")

ALLOWED_LOGO = {"png", "jpg", "jpeg", "webp"}
SETTING_KEYS = ["lh_1", "lh_2", "lh_3", "lh_4",
                "sig_right_rank", "sig_right_name",
                "sig_left_rank", "sig_left_name"]


def _rb(ok=None, err=None):
    _, token = current_session()
    params = []
    if token:
        params.append("sid=" + quote(token))
    if ok:
        params.append("ok=" + quote(ok))
    if err:
        params.append("err=" + quote(err))
    return redirect(url_for("letterhead.page") + ("?" + "&".join(params) if params else ""))


def _page_vars():
    v = {k: db.get_setting(k) for k in SETTING_KEYS}
    logo = db.get_setting("logo_file")
    v["has_logo"] = bool(logo and (storage.letterhead_dir() / logo).exists())
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
    for key in SETTING_KEYS:
        db.set_setting(key, (request.form.get(key) or "").strip())

    file = request.files.get("logo")
    if file and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ALLOWED_LOGO:
            return _rb(err="صيغة اللوجو غير مدعومة — المسموح: PNG / JPG / WEBP")
        for old in storage.letterhead_dir().glob("logo.*"):
            old.unlink()
        dataguard.atomic_save(file.save,
                              storage.letterhead_dir() / f"logo.{ext}", zip_check=False)
        db.set_setting("logo_file", f"logo.{ext}")

    letterhead_docx.rebuild()
    synced = xlsx_rations.rebuild_all()
    return _rb(ok=f"تم الحفظ ✔ أُعيد بناء ملف الوورد وتحديث التوقيعات في {synced} ملف إكسل")


# ======================================================================
# حذف اللوجو
# ======================================================================
@letterhead_bp.route("/logo/delete", methods=["POST"])
@login_required
def logo_delete():
    logo = db.get_setting("logo_file")
    path = storage.letterhead_dir() / logo if logo else None
    if path and path.exists():
        path.unlink()
    db.set_setting("logo_file", "")
    letterhead_docx.rebuild()
    return _rb(ok="تم حذف اللوجو وتحديث ملف الوورد")


# ======================================================================
# عرض اللوجو داخل الصفحة
# ======================================================================
@letterhead_bp.route("/logo")
@login_required
def logo_view():
    logo = db.get_setting("logo_file")
    path = storage.letterhead_dir() / logo if logo else None
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
    path = letterhead_docx.ensure()
    return send_file(str(path), as_attachment=True, download_name=path.name, conditional=False, max_age=0)


@letterhead_bp.route("/download-zip")
@login_required
def download_zip():
    """تنزيل مجلد الدباجة كاملًا (الوورد + اللوجو) أرشيف ZIP — يعمل من أي متصفح."""
    letterhead_docx.ensure()
    zip_path = dataguard.zip_folder_tmp(storage.letterhead_dir(), prefix="letterhead")
    resp = send_file(str(zip_path), as_attachment=True, download_name="letterhead.zip", conditional=False, max_age=0)
    resp.call_on_close(lambda: os.path.exists(zip_path) and os.remove(str(zip_path)))
    return resp


@letterhead_bp.route("/open-docx")
@login_required
def open_docx():
    path = letterhead_docx.ensure()
    if _open_path(path):
        return _rb(ok="تم فتح ملف الوورد 📄")
    return redirect(url_for("letterhead.download_docx",
                            sid=request.args.get("sid", "")))


@letterhead_bp.route("/open-folder")
@login_required
def open_folder():
    if _open_path(storage.letterhead_dir()):
        return _rb(ok="تم فتح مجلد الدباجة 📂")
    return _rb(err="فتح المجلد متاح عند تشغيل البرنامج على جهازك — استخدم زر التنزيل هنا")
