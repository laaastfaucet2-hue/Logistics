# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحة «النسخ الاحتياطي والحماية» — إدارة أرشيف ZIP الكامل للبيانات.

كل النسخ داخل database/backups/ — محلية فقط ولا تُرفع على GitHub أبدًا (قاعدة ١٣).
"""
import time
from urllib.parse import quote

from flask import Blueprint, render_template, request, redirect, url_for, abort, send_file

import dataguard
from auth_core import login_required, current_session

backups_bp = Blueprint("backups", __name__, url_prefix="/backups")


def _rb(ok=None, err=None):
    _, token = current_session()
    params = []
    if token:
        params.append("sid=" + quote(token))
    if ok:
        params.append("ok=" + quote(ok))
    if err:
        params.append("err=" + quote(err))
    return redirect(url_for("backups.page") + ("?" + "&".join(params) if params else ""))


def _size_h(num):
    if num < 1024 * 1024:
        return "{:.3f} ك.ب.".format(num / 1024)
    return "{:.3f} م.ب.".format(num / (1024 * 1024))


def _time_h(epoch):
    return time.strftime("%Y / %m / %d — %H:%M:%S", time.localtime(epoch))


# ======================================================================
# الصفحة: حالة الحماية + قائمة النسخ
# ======================================================================
@backups_bp.route("")
@backups_bp.route("/")
@login_required
def page():
    results = dataguard.verify_all()
    broken = [(rel, err) for rel, (ok, err) in results.items() if not ok]
    files = dataguard.data_files()
    total = sum(p.stat().st_size for p in files)
    rows = []
    for b in dataguard.list_backups():
        rows.append({**b, "size_h": _size_h(b["size"]), "time_h": _time_h(b["mtime"])})
    return render_template(
        "backups.html",
        files_count=len(files), total_h=_size_h(total),
        broken=broken, verified_count=len(results),
        backups=rows, backups_count=len(rows),
        keep_n=dataguard.KEEP_N,
        newest=rows[0] if rows else None,
    )


# ======================================================================
# إنشاء نسخة يدوية
# ======================================================================
@backups_bp.route("/create", methods=["POST"])
@login_required
def create():
    try:
        info = dataguard.create_backup("manual")
        return _rb(ok="تم إنشاء النسخة «{}» — {} ملفًا بحجم {}".format(
            info["name"], info["count"], _size_h(info["size"])))
    except Exception as exc:  # noqa: BLE001 — أي فشل يظهر للمستخدم لا يسقط النظام
        return _rb(err="تعذّر إنشاء النسخة: {}".format(exc))


# ======================================================================
# تنزيل نسخة
# ======================================================================
@backups_bp.route("/download/<name>")
@login_required
def download(name):
    if not dataguard.valid_name(name):
        abort(404)
    path = dataguard.backup_dir() / name
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name=name, conditional=False, max_age=0)


# ======================================================================
# استرجاع نسخة (فوق البيانات الحالية بعد نسخة أمان تلقائية)
# ======================================================================
@backups_bp.route("/restore/<name>", methods=["POST"])
@login_required
def restore(name):
    try:
        restored, pre = dataguard.restore_backup(name)
        return _rb(ok="تم استرجاع {} ملفًا من «{}» — واحتياطًا: نُسخت البيانات السابقة في «{}»".format(
            restored, name, pre))
    except (ValueError, FileNotFoundError, IOError) as exc:
        return _rb(err="فشل الاسترجاع: {}".format(exc))


# ======================================================================
# حذف نسخة
# ======================================================================
@backups_bp.route("/delete/<name>", methods=["POST"])
@login_required
def delete(name):
    try:
        dataguard.delete_backup(name)
        return _rb(ok="تم حذف النسخة «{}»".format(name))
    except ValueError as exc:
        return _rb(err=str(exc))
