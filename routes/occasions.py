# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحة «التوثيق والمناسبات» — صفحة دائمة (لا تتبع الشهر/السنة).

توجيه ٠٦/١٠/٢٠٢٦: تسجيل كل مناسبة مهمة (زيارة رسمية / تفتيش / مسمى حر) + معرض صور
+ معرض فيديو يُشغَّل من داخل البرنامج + تقرير على الدباجة والتوقيعات واللوجو وتعديله
وطباعته + إطار. الملفات المحلية لكل مناسبة في فولدرها الخاص (occasions_fs).
"""
from flask import (Blueprint, render_template, request, redirect, url_for, g, jsonify,
                   send_file, flash, current_app)

from core.auth_core import login_required, current_context, current_session
from core import arabic_numbers as arnum
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


def _upload_files(folder):
    """يحفظ ملفات الرفعة داخل فولدر المناسبة — ويُرجع (المحفوظ، المرفوض، الخطأ).

    الحدود (قرار المستخدم): ٣٠ ملفًا في الرفعة الواحدة — وكل ملف حتى ٢ جيجا
    (السقف يُفرض في app.py عبر MAX_CONTENT_LENGTH، وتجاوزه يعرض صفحة عربية).
    """
    saved = {"photo": 0, "video": 0}
    rejected = []
    picked = []
    for kind, bucket in (("photo", "photos"), ("video", "videos")):
        for upload in request.files.getlist(bucket):
            if upload and upload.filename:
                picked.append((kind, upload))
    limit = arnum.to_arabic_indic(str(ofs.MAX_FILES_PER_UPLOAD))
    if len(picked) > ofs.MAX_FILES_PER_UPLOAD:
        return saved, rejected, (f"الحد الأقصى {limit} ملفًا في الرفعة الواحدة — "
                                 f"اخترت {arnum.to_arabic_indic(str(len(picked)))}؛ "
                                 "قسّمها على دفعتين وارفع تاني.")
    for kind, upload in picked:
        if ofs.add_media(folder, kind, upload) is None:
            rejected.append(upload.filename)
        else:
            saved[kind] += 1
    return saved, rejected, ""


def _upload_message(saved, rejected):
    """رسالة عربية واحدة تلخّص نتيجة الرفعة (بلا None ولا صفر مخفي)."""
    limit = arnum.to_arabic_indic(str(ofs.MAX_FILES_PER_UPLOAD))
    parts = []
    if saved["photo"] or saved["video"]:
        parts.append(f"أُضيف {arnum.to_arabic_indic(str(saved['photo']))} صورة و"
                     f"{arnum.to_arabic_indic(str(saved['video']))} فيديو داخل فولدر المناسبة")
    if rejected:
        parts.append(f"وتُرفض {arnum.to_arabic_indic(str(len(rejected)))} ملفًا بنوع غير مدعوم")
    if not parts:
        parts.append(f"لم يُختر أي ملف — الصور وفيديو المناسبة حتى {limit} ملفًا في المرة")
    return " ".join(parts)


def _limits_payload():
    """حدود الرفع للواجهة (يعرضها النموذج وقسم الرفع بالأرقام العربية)."""
    return {"max_files": ofs.MAX_FILES_PER_UPLOAD,
            "max_files_text": arnum.to_arabic_indic(str(ofs.MAX_FILES_PER_UPLOAD)),
            "max_bytes": ofs.MAX_UPLOAD_BYTES,
            "max_text": ofs.UPLOAD_LIMIT_TEXT,
            "photos": sorted(ofs.IMAGE_EXT), "videos": sorted(ofs.VIDEO_EXT)}


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
    # التاب النشط: «search» عند وجود مناسبة مفتوحة أو بحث — و«create» في أول استخدام أو بطلب صريح
    tab = (request.args.get("tab") or "").lower()
    if tab not in ("create", "search"):
        tab = "search" if (selected or query or date_from or date_to) else "create"
    _, token = current_session()
    return render_template(
        "occasions/main.html", sid_token=token or "",
        items=items, selected=selected, item=selected,
        letterhead=_letterhead(selected) if selected else {},
        stats=ofs.stats(),
        kinds=ofs.kinds_in_use(), field_keys=ofs.FIELD_KEYS,
        q=query, date_from=date_from, date_to=date_to, today=egtime.today().isoformat(),
        main_tab=tab,
        ok=request.args.get("ok") or "", err=request.args.get("err") or "",
        limits=_limits_payload(),
    )


@occasions_bp.route("/create", methods=["POST"])
@login_required
def create():
    _ctx()
    values = _values()
    if not values["title"]:
        return _back(err="اكتب مسمى المناسبة الأول (زيارة رسمية / تفتيش / أي مسمى تختاره)")
    folder, payload = ofs.create(values)
    saved, rejected, problem = _upload_files(folder)   # ملفات نفس النموذج (اختيارية)
    if problem:
        return _back(err=f"سُجلت المناسبة «{payload['title']}» — {problem}", folder=str(folder))
    item = ofs.load(folder)
    occasions_docs.build_all(item)          # التقريران يُبنيان فورًا بالدباجة والتوقيعين
    note = _upload_message(saved, rejected) if (saved["photo"] or saved["video"] or rejected) else ""
    return _back(ok=(f"سُجلت المناسبة «{payload['title']}» في فولدرها المحلي مع تقريرها الرسمي"
                     + (f" — {note}" if note else "")),
                 folder=str(folder))


@occasions_bp.route("/save", methods=["POST"])
@login_required
def save():
    """حفظ تعديل المناسبة + إعادة بناء تقريريها (Excel + Word).

    مع معاينة الورق الحية: النموذج قد يطلب ردًّا JSON (data-json=1) ليعرف أن الحفظ
    تم ثم ينزّل Word/Excel بالحالي — وبلا JSON يبقى السلوك القديم (عودة للصفحة برسالة).
    """
    _ctx()
    folder = _folder_arg()
    wants_json = bool(request.form.get("json") or request.args.get("json"))
    if folder is None:
        if wants_json:
            return jsonify({"ok": False, "message": "المناسبة المطلوبة غير موجودة"}), 404
        return _back(err="المناسبة المطلوبة غير موجودة")
    values = _values()
    if not values["title"]:
        if wants_json:
            return jsonify({"ok": False, "message": "المسمى لا يبقى فارغًا"}), 400
        return _back(err="المسمى لا يبقى فارغًا", folder=str(folder))
    ofs.save(folder, values)
    occasions_docs.build_all(ofs.load(folder))
    message = "تم حفظ تعديلات المناسبة وإعادة بناء تقريرها (Excel + Word)"
    if wants_json:
        return jsonify({"ok": True, "message": message, "folder": str(folder)})
    return _back(ok=message, folder=str(folder))



@occasions_bp.route("/media/upload", methods=["POST"])
@login_required
def media_upload():
    _ctx()
    folder = _folder_arg()
    if folder is None:
        return _back(err="المناسبة المطلوبة غير موجودة")
    saved, rejected, problem = _upload_files(folder)
    if problem:
        return _back(err=problem, folder=str(folder))
    if not (saved["photo"] or saved["video"] or rejected):
        return _back(err="اختر صورة أو فيديو أولًا (البرنامج يحفظه داخل فولدر المناسبة)",
                     folder=str(folder))
    return _back(ok=_upload_message(saved, rejected), folder=str(folder))


@occasions_bp.route("/media/upload-json", methods=["POST"])
@login_required
def media_upload_json():
    """رفع ملف واحد من قسم الرفع الآمن في الواجهة (JS) — فيديو الكبير لا يقطع الصفحة.

    يُرجع JSON فيه التقدم والرسالة العربية، ويُستدعى من js/occasions.js مرة لكل ملف.
    """
    _ctx()
    folder = _folder_arg()
    if folder is None:
        return jsonify({"ok": False, "message": "المناسبة المطلوبة غير موجودة"}), 404
    saved, rejected, problem = _upload_files(folder)
    ok = bool(saved["photo"] or saved["video"])
    return jsonify({"ok": ok and not problem, "message": problem or _upload_message(saved, rejected),
                    "photo": saved["photo"], "video": saved["video"],
                    "rejected": rejected, "stats": ofs.stats()})


@occasions_bp.route("/upload-limits")
@login_required
def upload_limits():
    """حدود الرفع كما يفرضها البرنامج فعلًا (تقرؤها الواجهة بلا تخمين)."""
    _ctx()
    payload = _limits_payload()
    payload["server_max_bytes"] = int(current_app.config.get("MAX_CONTENT_LENGTH") or 0)
    return jsonify(payload)


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


@occasions_bp.route("/paper")
@login_required
def paper():
    """معاينة «صفحة ورق» حية للتقرير — بنفس الدباجة والتوقيعات واللوجو (مثل تقارير الصحة)."""
    _ctx()
    folder = _folder_arg()
    if folder is None:
        return _back(err="المناسبة المطلوبة غير موجودة")
    item = ofs.load(folder)
    _, token = current_session()
    return render_template("occasions/paper_report.html", item=item, sid_token=token or "",
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
