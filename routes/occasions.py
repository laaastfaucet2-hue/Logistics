# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحة «التوثيق والمناسبات» — صفحة دائمة (لا تتبع الشهر/السنة).

توجيه ٠٦/١٠/٢٠٢٦: تسجيل كل مناسبة مهمة (زيارة رسمية / تفتيش / مسمى حر) + معرض صور
+ معرض فيديو يُشغَّل من داخل البرنامج + تقرير على الدباجة والتوقيعات واللوجو وتعديله
وطباعته + إطار وإخطار. الملفات المحلية لكل مناسبة في فولدرها الخاص (occasions_fs).
"""
from flask import (Blueprint, render_template, request, redirect, url_for, g, jsonify,
                   send_file, flash)
from werkzeug.utils import secure_filename

from core.auth_core import login_required, current_context, current_session
from core import dates, egtime
from data_access import dataguard
from documents import occasions_docs
from services import occasions_fs as ofs

occasions_bp = Blueprint("occasions", __name__, url_prefix="/occasions")


def _ctx():
    year, month = current_context(g.user["id"])
    return year, month


def _back(ok=None, err=None, **extra):
    """عودة لصفحة المناسبات مع التوكن (النظام يعمل بـsid بجانب الكوكي)."""
    _, token = current_session()
    params = {key: value for key, value in extra.items() if value not in (None, "")}
    if token:
        params["sid"] = token
    if ok:
        params["ok"] = ok
    if err:
        params["err"] = err
    return redirect(url_for("occasions.page", **params))


def _folder_arg():
    """فولدر المناسبة المطلوب من الرابط — بفحص أنه داخل جذر المناسبات فعلًا."""
    raw = request.values.get("folder") or ""
    base = ofs.root().resolve()
    try:
        path = ofs.Path(raw).resolve()
    except (OSError, ValueError):
        return None
    if path == base or base not in path.parents or not path.is_dir():
        return None
    return path


def _values():
    """قيم النموذج — كل الحقول نصية (لا None في الواجهة)، والتاريخ يُحوَّل ISO."""
    values = {key: (request.form.get(key) or "").strip() for key, _label in ofs.FIELD_KEYS}
    if values.get("date_iso"):
        values["date_iso"] = dates.to_iso(dates.parse_date(values["date_iso"])) or values["date_iso"]
    return values


@occasions_bp.route("")
@occasions_bp.route("/")
@login_required
def page():
    _ctx()
    query = (request.args.get("q") or "").strip()
    date_from = dates.to_iso(dates.parse_date((request.args.get("from") or "").strip())) or ""
    date_to = dates.to_iso(dates.parse_date((request.args.get("to") or "").strip())) or ""
    items = ofs.list_occasions(date_from or None, date_to or None, query)
    current = _folder_arg()
    selected = ofs.load(current) if current else None
    _, token = current_session()
    return render_template(
        "occasions/main.html", sid_token=token or "",
        items=items, selected=selected, stats=ofs.stats(),
        kinds=ofs.kinds_in_use(), field_keys=ofs.FIELD_KEYS,
        q=query, date_from=date_from, date_to=date_to, today=egtime.today().isoformat(),
        ok=request.args.get("ok") or "", err=request.args.get("err") or "",
    )


@occasions_bp.route("/create", methods=["POST"])
@login_required
def create():
    _ctx()
    values = _values()
    if not values["title"]:
        return _back(err="اكتب مسمى المناسبة الأول (زيارة رسمية / تفتيش / أي مسمى تختاره)")
    folder, payload = ofs.create(values)
    item = ofs.load(folder)
    occasions_docs.build_all(item)          # التقريران يُبنيان فورًا بالدباجة والتوقيعين
    return _back(ok=f"سُجلت المناسبة «{payload['title']}» في فولدرها المحلي مع تقريرها الرسمي",
                 folder=str(folder))


@occasions_bp.route("/save", methods=["POST"])
@login_required
def save():
    _ctx()
    folder = _folder_arg()
    if folder is None:
        return _back(err="المناسبة المطلوبة غير موجودة")
    values = _values()
    if not values["title"]:
        return _back(err="المسمى لا يبقى فارغًا", folder=str(folder))
    ofs.save(folder, values)
    occasions_docs.build_all(ofs.load(folder))
    return _back(ok="تم حفظ تعديلات المناسبة وإعادة بناء تقريرها (Excel + Word)",
                 folder=str(folder))


@occasions_bp.route("/media/upload", methods=["POST"])
@login_required
def media_upload():
    _ctx()
    folder = _folder_arg()
    if folder is None:
        return _back(err="المناسبة المطلوبة غير موجودة")
    saved = {"photo": 0, "video": 0}
    for kind, bucket in (("photo", "photos"), ("video", "videos")):
        for upload in request.files.getlist(bucket):
            if upload and upload.filename:
                ofs.add_media(folder, kind, upload)
                saved[kind] += 1
    if not (saved["photo"] or saved["video"]):
        return _back(err="اختر صورة أو فيديو أولًا (البرنامج يحفظه داخل فولدر المناسبة)",
                     folder=str(folder))
    return _back(ok=f"أُضيفت {saved['photo']} صورة و{saved['video']} فيديو داخل فولدر المناسبة",
                 folder=str(folder))


@occasions_bp.route("/media/<kind>/<path:name>")
@login_required
def media(kind, name):
    """خدمة الوسائط محليًا (بلا إنترنت) — بفحص مسار صارم + دعم مشاهدة الفيديو بالتقطيع."""
    folder = _folder_arg()
    if folder is None or kind not in ("photo", "video"):
        return _back(err="الوسيط المطلوب غير موجود")
    path = ofs.media_path(folder, kind, name)
    if path is None:
        return _back(err="الملف غير موجود داخل المناسبة")
    return send_file(str(path), conditional=True)


@occasions_bp.route("/media/delete", methods=["POST"])
@login_required
def media_delete():
    _ctx()
    folder = _folder_arg()
    kind = request.form.get("kind") or ""
    name = request.form.get("name") or ""
    if folder is None or kind not in ("photo", "video"):
        return _back(err="الوسيط المطلوب غير موجود")
    if not ofs.delete_media(folder, kind, name):
        return _back(err="تعذّر حذف الملف — تأكد أنه ما زال داخل المناسبة", folder=str(folder))
    return _back(ok=f"تم حذف «{name}» من المناسبة", folder=str(folder))


@occasions_bp.route("/report")
@login_required
def report():
    """تنزيل التقرير (Excel أو Word) بعد تأكيد وجوده — ويُعاد بناؤه إن كان ناقصًا."""
    _ctx()
    folder = _folder_arg()
    kind = (request.args.get("kind") or "xlsx").lower()
    if folder is None:
        return _back(err="المناسبة المطلوبة غير موجودة")
    item = ofs.load(folder)
    paths = occasions_docs.build_all(item)
    target = paths["docx"] if kind == "docx" else paths["xlsx"]
    fallback = "occasion-report.docx" if kind == "docx" else "occasion-report.xlsx"
    return send_file(str(target), as_attachment=True, download_name=fallback,
                     conditional=False, max_age=0)


@occasions_bp.route("/print")
@login_required
def print_report():
    """صفحة الطباعة الرسمية — نفس الورق: دباجة + لوجو + البيانات + الوصف + توقيعان."""
    _ctx()
    folder = _folder_arg()
    if folder is None:
        return _back(err="المناسبة المطلوبة غير موجودة")
    item = ofs.load(folder)
    _, token = current_session()
    return render_template("occasions/print_report.html", item=item, sid_token=token or "",
                           letterhead=_letterhead(item))


def _letterhead(item):
    from data_access import db_letterhead as lh
    parts = (item.get("date_iso") or "").split("-")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        year, month = int(parts[0]), int(parts[1])
    else:
        year, month = _ctx()
    return lh.template_vars(year, month)


@occasions_bp.route("/delete", methods=["POST"])
@login_required
def delete():
    _ctx()
    folder = _folder_arg()
    if folder is None:
        return _back(err="المناسبة المطلوبة غير موجودة")
    title = ofs.load(folder)["title"]
    if not ofs.delete_occasion(folder):
        return _back(err="تعذّر حذف المناسبة")
    return _back(ok=f"حُذفت المناسبة «{title}» بكل صورها وفيديوهاتها وبقايا تقاريرها")


@occasions_bp.route("/ping")
@login_required
def ping():
    """فحص حياة الصفحة لمن يحرسها برمجيًا (اختبارات/مراقبة)."""
    _ctx()
    return jsonify({"occasions": ofs.stats(), "root": str(ofs.root())})


@occasions_bp.route("/dataroot")
@login_required
def dataroot():
    """معلومة تشخيصية: أين تُحفظ ملفات المناسبات على الجهاز."""
    _ctx()
    return jsonify({"root": str(ofs.root()),
                    "pending": len(dataguard.pending_paths())})
