# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""ملفات تبويبات «إحصائيات المخازن والثلاجات» — تحت /stats/stores/.

فتح المجلد · فتح الملف · التنزيل · حالة الملف · التحديث اليدوي — لكل تبويب فرعي
بالشهري والسنوي (قاعدة ٢١). في معاينة الويب يُعلن تعذر الفتح بصراحة مع التنزيل (قاعدة ٢٠).
"""
import os
import subprocess
import sys

from flask import Blueprint, g, jsonify, redirect, request, url_for

from core.auth_core import current_context, login_required
from core.downloads import attachment
from services import stats_stores as ss
from services.stats_stores import files, refresher

stats_stores_bp = Blueprint("stats_stores", __name__, url_prefix="/stats/stores")


def _open_path(path):
    """يفتح مسارًا محليًا بنظام التشغيل؛ False في نسخة الويب (بلا واجهة رسومية)."""
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


def _params():
    year, month = current_context(g.user["id"])
    sub = ss.normalize_sub(request.values.get("sub", ""))
    scope = "year" if request.values.get("scope") == "year" else "month"
    return year, month, sub, scope, (month if scope == "month" else None)


def _back(sub, scope, ok=None, err=None):
    params = {"cycle": "supply", "tab": "stores", "sub": sub, "scope": scope}
    for key in ("f_store", "f_cycle", "f_item"):
        if request.values.get(key):
            params[key] = request.values.get(key)
    if ok:
        params["ok"] = ok
    if err:
        params["err"] = err
    return redirect(url_for("stats.page", **params))


def _ensure_file(sub, year, month, file_month, force=False):
    """ملف التبويب جاهز ومحدّث قبل فتحه أو تنزيله (يُكتب الآن لو ناقص أو قديم)."""
    path = files.tab_file(sub, year, file_month)
    with refresher.locked():
        if force or not path.exists() or not files.is_fresh(year, file_month):
            files.write_scope(year, file_month, keys=[sub], force=force, create=True)
    return path


@stats_stores_bp.route("/open-folder")
@login_required
def open_folder():
    year, month, sub, scope, file_month = _params()
    files.ensure_folders(year, file_month)
    if _open_path(files.tab_dir(sub, year, file_month)):
        return _back(sub, scope, ok=f"تم فتح مجلد «{ss.folder_name(sub)}» 📂")
    return _back(sub, scope, err="فتح المجلد متاح عند تشغيل البرنامج على جهازك — استخدم زر التنزيل هنا")


@stats_stores_bp.route("/open-file")
@login_required
def open_file():
    year, month, sub, scope, file_month = _params()
    path = _ensure_file(sub, year, month, file_month)
    if path.exists() and _open_path(path):
        return _back(sub, scope, ok=f"تم فتح ملف «{path.name}» 📗")
    params = {"sub": sub, "scope": scope}
    return redirect(url_for("stats_stores.download", **params))


@stats_stores_bp.route("/download")
@login_required
def download():
    year, month, sub, scope, file_month = _params()
    path = _ensure_file(sub, year, month, file_month)
    suffix = f"{year}-{month:02d}" if file_month else f"{year}"
    return attachment(path, f"stores-stats-{sub}-{suffix}.xlsx")


@stats_stores_bp.route("/status")
@login_required
def status():
    year, month, sub, scope, file_month = _params()
    payload = files.status(sub, year, file_month, busy=refresher.busy(year))
    payload.update(ok=True, file=ss.file_name(sub, year, file_month))
    return jsonify(payload)


@stats_stores_bp.route("/refresh", methods=["POST"])
@login_required
def refresh():
    """⟳ تحديث ملفي التبويب الآن (الشهري والسنوي) — كتابة كاملة."""
    year, month, sub, scope, _file_month = _params()
    try:
        _ensure_file(sub, year, month, month, force=True)
        _ensure_file(sub, year, month, None, force=True)
    except OSError:
        return _back(sub, scope, err="تعذر تحديث الملفات — أغلق الملف المفتوح وأعد المحاولة")
    return _back(sub, scope, ok=f"تم تحديث ملفي «{ss.folder_name(sub)}»")
