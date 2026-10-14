# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مسارات فتح ملفات المستودعات وتنزيلها."""
from flask import abort, redirect, request, url_for

from core.auth_core import login_required
from routes.warehouses import (
    SUB_KEYS, WAREHOUSE_MAP, _ctx, _open_path, _rb, _snapshot,
    warehouses_bp, wf,
)


# ======================================================================
# ملفات التبويبات المحلية: فتح المجلد / فتح الملف / التنزيل (قاعدة أزرار الملفات)
# ======================================================================
def _tab_or_404(cycle, sub):
    if cycle not in WAREHOUSE_MAP or sub not in SUB_KEYS:
        abort(404)


@warehouses_bp.route("/open-folder/<cycle>/<sub>")
@login_required
def open_folder(cycle, sub):
    _tab_or_404(cycle, sub)
    year, month = _ctx()
    path = wf.cycle_dir(year, month, cycle, sub)
    if _open_path(path):
        return _rb(cycle, sub, ok=f"تم فتح مجلد «{wf.SUB_FOLDERS[sub]}» 📂")
    return _rb(cycle, sub,
               err="فتح المجلد متاح عند تشغيل البرنامج على جهازك — استخدم زر التنزيل هنا")


@warehouses_bp.route("/open-file/<cycle>/<sub>")
@login_required
def open_file(cycle, sub):
    _tab_or_404(cycle, sub)
    year, month = _ctx()
    second = request.args.get("file") == "taf3"
    if sub == "wh2":
        # لا يوجد ملف واحد: كل إذن في إكسل منفصل داخل مجلد يومه (توجيه ٠٨/١٠)
        path = wf.cycle_dir(year, month, cycle, "wh2")
        if _open_path(path):
            return _rb(cycle, sub,
                       ok="تم فتح مجلد «٢ مخازن» — كل إذن له ملفه في مجلد يومه 📂")
        return _rb(cycle, sub,
                   err="لا يوجد ملف واحد لتبويب ٢ مخازن — كل إذن له ملفه في مجلد يومه")
    _snapshot(cycle)
    path = wf.file_path(year, month, cycle, sub, second=second)
    if path.exists() and _open_path(path):
        return _rb(cycle, sub, ok=f"تم فتح ملف «{path.name}» 📗")
    return redirect(url_for("warehouses.download", cycle=cycle, sub=sub,
                            **({"file": "taf3"} if second else {})))


@warehouses_bp.route("/permit-file/<cycle>/<int:permit_no>")
@login_required
def permit_file(cycle, permit_no):
    """زر «فتح الاكسل» جنب عرض الإذن في ٢ مخازن (توجيه ٠٨/١٠): يفتح إكسل الإذن
    المنفصل — من أذونات الصرف في تبويب «أذونات الصرف»، ومن تفاريد في تبويب «التغليف»."""
    _tab_or_404(cycle, "wh2")
    year, month = _ctx()
    taf = request.args.get("taf") == "1"
    _snapshot(cycle)   # لو الإذن اتحفظ والمرايا متأخرة — نضمن الملف موجود
    from data_access import db_permits as dp
    permit = next((p for p in dp.list_permits(year, month)
                   if int(p["number"]) == int(permit_no)), None)
    if not permit:
        return _rb(cycle, "wh2", err="الإذن غير موجود في بيانات هذا الشهر")
    try:
        day = int(permit.get("date_from") or 0)
    except (TypeError, ValueError):
        day = 0
    if day < 1:
        return _rb(cycle, "wh2", err="الإذن بلا يوم محدد — لا يوجد له ملف إكسل")
    path = wf.wh2_permit_file_path(year, month, cycle, permit_no, day, taf=taf)
    if path.exists() and _open_path(path):
        return _rb(cycle, "wh2", ok=f"تم فتح «{path.name}» 📗")
    if not path.exists():
        return _rb(cycle, "wh2",
                   err=f"ملف «{path.name}» لم يُنشأ بعد — أعد حفظ الإذن وسيُكتب")
    return _rb(cycle, "wh2",
               err="فتح الملف مباشرة متاح عند تشغيل البرنامج على جهازك — "
                   "افتح مجلد «٢ مخازن» بالزر فوق")


@warehouses_bp.route("/download/<cycle>/<sub>")
@login_required
def download(cycle, sub):
    from core.downloads import attachment
    _tab_or_404(cycle, sub)
    year, month = _ctx()
    second = request.args.get("file") == "taf3"
    if sub == "wh2":
        return _rb(cycle, sub,
                   err="لا يوجد ملف واحد لتنزيله — كل إذن في إكسل منفصل داخل مجلد يومه")
    _snapshot(cycle)
    path = wf.file_path(year, month, cycle, sub, second=second)
    if not path or not path.exists():
        return _rb(cycle, sub, err="الملف لم يُنشأ بعد — أضف بيانات أولًا")
    return attachment(path, f"warehouses-{cycle}-{sub}-{year}-{month:02d}.xlsx")
