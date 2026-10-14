# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""«الإعدادات» — أربعة تبويبات: تسجيل المستخدمين · سجلات المستخدمين ·
المتابعة والملاحظات · الهوية للمنظمة (توجيه ١٠/١٠).

كل تبويب له صلاحية مستقلة (settings:users / settings:log / settings:notes /
settings:identity) يحددها الـ admin من تبويب تسجيل المستخدمين.

الأقسام المحمية (log/notes): الرمز الرئيسي يفتحها مرة واحدة لباقي
الجلسة (قرار المستخدم ١٤/١٠) — مفتاح الفتح مرتبط بتوكن الجلسة.
"""
from flask import Blueprint, g, redirect, render_template, request, send_file, url_for

from core.auth_core import login_required
from core import arabic_numbers as arnum, dates, egtime
from core import tabs_registry as tr
from data_access import db_users
from data_access import database as db
from data_access import storage

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

SUBS = [("users", "تسجيل المستخدمين", "👥"),
        ("log", "سجلات المستخدمين", "📈"),
        ("notes", "المتابعة والملاحظات", "🗒️"),
        ("identity", "الهوية للمنظمة", "🖼️")]


def _sync_quiet(fn, *args, **kwargs):
    """مرايا الملفات المحلية لا تسقط الصفحة — الخطأ بيتسجل بس."""
    try:
        return fn(*args, **kwargs)
    except Exception:      # noqa: BLE001
        import logging
        logging.exception("settings fs sync failed")


def _sub():
    raw = request.values.get("sub") or "users"
    return raw if raw in {t[0] for t in SUBS} else "users"


def _rb(sub="users", ok=None, err=None):
    token = request.args.get("sid") or request.form.get("sid")
    params = {"sub": sub}
    if token:
        params["sid"] = token
    if ok:
        params["ok"] = ok
    if err:
        params["err"] = err
    return redirect(url_for("settings.page", **params))


@settings_bp.route("")
@settings_bp.route("/")
@login_required
def page():
    sub = _sub()
    if not tr.has_permission(g.user, f"settings:{sub}"):
        from flask import render_template as rt
        return rt("forbidden.html", tab=f"settings:{sub}"), 403
    # الأقسام المحمية (سجلات المستخدمين + المتابعة والملاحظات): الرمز الرئيسي
    # يفتحها مرة واحدة لباقي الجلسة (قرار المستخدم ١٤/١٠) — مفتاح الجلسة =
    # توكن sid في الرابط، أو «cookie:<id>» لو الدخول بكوكي.
    gate_key = g.sid or "cookie:%d" % g.user["id"]
    if sub in ("log", "notes") and not db.is_gate_open(gate_key, sub):
        # items(multi=True) يرجّع القيمة نفسها كنص؛ v[0] كان يقطع sid لأول حرف
        # وبعد فتح البوابة يتحول الطلب إلى جلسة منتهية ويرجع لتسجيل الدخول.
        keep = {k: v for k, v in request.args.items()
                if k not in ("open", "err", "ok")}
        return render_template("settings/lock.html", subs=SUBS, sub=sub,
                               sub_name=dict((t[0], t[1]) for t in SUBS)[sub], keep=keep)
    ctx = {
        "subs": SUBS, "sub": sub,
        "users": db_users.list_users(),
        "perm_tree": tr.perm_tree(),
        "notes_ctx": {"notes": [], "users_choices": []},
        "log_ctx": {},
        "log_users": [],
        "perm_user": None,
        "perm_tabs": set(),
    }
    if sub == "users":
        sel = arnum.parse_int(request.args.get("permuser"))
        sel_user = db_users.get_user_full(sel) if sel else None
        ctx["perm_user"] = sel_user
        ctx["perm_tabs"] = db_users.get_user_tabs(sel) if sel_user else set()
    elif sub == "log":
        users = ctx["users"]
        sel = arnum.parse_int(request.args.get("user")) or (
            users[0]["id"] if users else None)
        sel_user = db_users.get_user_full(sel) if sel else None
        today = egtime.today()
        if sel_user:
            from core import action_names
            ctx["log_ctx"] = {
                "user": dict(sel_user, events_count=db_users.count_activity(sel)),
                "day": db_users.day_stats(sel, today.year, today.month, today.day),
                "month": db_users.month_stats(sel, today.year, today.month),
                "year": db_users.year_stats(sel, today.year),
                "total": db_users.total_stats(sel),
                "events": db_users.list_activity(sel, 300),
                "fmt": db_users.fmt_dhm,            # شهر/سنة/إجمالي: يوم + ساعة + دقيقة
                "fmt_hm": db_users.fmt_hm,          # اليوم: ساعة + دقيقة
                "row": action_names.log_row,        # (اسم الإجراء, التفاصيل) بالعربي
                "time": action_names.fmt_log_time,  # «٢٠٢٦/١٠/١٠ م ١١:١٠:١٤ م»
                "role_ico": "👮" if sel_user["role"] == "admin" else "👤",
            }
        ctx["log_users"] = users
        from services import settings_fs
        try:
            settings_fs.sync_all_logs()      # مرايا الإكسل بتتحدّث مع كل كشف للسجلات
        except Exception:      # noqa: BLE001 — المرايا لا تسقط الصفحة
            import logging
            logging.exception("settings log mirror failed")
    elif sub == "notes":
        role = g.user["role"]
        ctx["notes_ctx"] = {
            "notes": db_users.list_notes(g.user["id"], role),
            "users_choices": [u for u in ctx["users"] if u["id"] != g.user["id"]],
            "unread": db_users.unread_counts(g.user["id"]),
        }
        nid = arnum.parse_int(request.args.get("thread"))
        if nid:
            t = db_users.note_thread(nid)
            if t:
                ctx["notes_ctx"]["thread"] = t
                if t["note"]["from_user"] == g.user["id"]:
                    db_users.mark_author_seen(nid, g.user["id"])
    elif sub == "identity":
        from data_access import db_identity
        logo_name = db_identity.get_logo()
        p = storage.identity_dir() / logo_name if logo_name else None
        ctx["identity_ctx"] = {
            "logo": logo_name,
            "v": int(p.stat().st_mtime) if p and p.exists() else 0,
            "updated_at": db_identity._read().get("updated_at") or "",
        }
    return render_template("settings/main.html", **ctx)


# ======================================================================
# ٥) الهوية للمنظمة — شعار واجهة البرنامج (تسجيل الدخول/القائمة/الرئيسية)
# ======================================================================

@settings_bp.route("/identity/logo")
def identity_logo():
    """ملف الشعار المرفوع (PNG) — يظهر في الواجهة كاملة.

    بلا login_required عمدًا: صفحة تسجيل الدخول نفسها بتعرضه (لا يوجد
    جلسة وقتها) — الشعار بيانات عامة زي شعار الـ static الأصلي،
    والحماية على الرفع/الحذف مش على العرض."""
    from data_access import db_identity
    name = db_identity.get_logo()
    if not name:
        return "لا يوجد شعار مرفوع", 404
    p = storage.identity_dir() / name
    if not p.exists():
        return "لا يوجد شعار مرفوع", 404
    return send_file(p, mimetype="image/png", conditional=True)


@settings_bp.route("/identity/logo/upload", methods=["POST"])
@login_required
def identity_logo_upload():
    if not tr.has_permission(g.user, "settings:identity"):
        return _rb("identity", err="لا تملك صلاحية هذا القسم")
    file = request.files.get("logo")
    if not file or not file.filename:
        return _rb("identity", err="اختر ملف الصورة أولًا")
    from services import images
    from data_access import db_identity
    try:
        name = images.save_logo(file.stream, storage.identity_dir())
    except ValueError as e:
        return _rb("identity", err=str(e))
    old = db_identity.get_logo()
    if old and old != name:
        try:
            (storage.identity_dir() / old).unlink()
        except OSError:
            pass
    db_identity.set_logo(name)
    db_users.log_activity(g.user["id"], "save", "settings:identity", "رفع شعار المنظومة")
    return _rb("identity", ok="رُفع الشعار — وظهر مباشرةً في تسجيل الدخول والشريط الجانبي والصفحة الرئيسية")


@settings_bp.route("/identity/logo/delete", methods=["POST"])
@login_required
def identity_logo_delete():
    if not tr.has_permission(g.user, "settings:identity"):
        return _rb("identity", err="لا تملك صلاحية هذا القسم")
    from data_access import db_identity
    db_identity.delete_logo()
    db_users.log_activity(g.user["id"], "delete", "settings:identity",
                          "حذف شعار المنظومة — العودة إلى الشعار الأصلي")
    return _rb("identity", ok="حُذف الشعار وعاد البرنامج إلى الشعار الأصلي")


# ======================================================================
# ١) تسجيل المستخدمين
# ======================================================================
@settings_bp.route("/gate", methods=["POST"])
@login_required
def gate():
    """بوابة الرمز الرئيسي للأقسام المحمية (log/notes).

    فتح: الرمز 7799 يفتح القسم لباقي الجلسة (مرة واحدة — قرار ١٤/١٠).
    قفل: action=lock يقفل القسم فورًا من أي زر «إغلاق وحماية» داخله.
    """
    import secrets
    from services import settings_fs
    sub = request.form.get("sub", "")
    if sub not in ("log", "notes") or not tr.has_permission(g.user, f"settings:{sub}"):
        return _rb("users")
    gate_key = g.sid or "cookie:%d" % g.user["id"]
    name = dict((t[0], t[1]) for t in SUBS)[sub]
    if request.form.get("action") == "lock":
        db.clear_gate(gate_key, sub)
        db_users.log_activity(g.user["id"], "gate", f"settings:{sub}",
                              "قفل القسم «" + name + "» يدويًا")
        return _rb(sub, ok="أُغلق القسم، وسيُطلب الرمز عند فتحه مرة أخرى")
    pw = (request.form.get("password") or "").strip()
    if pw and secrets.compare_digest(pw, settings_fs.MASTER_PASSWORD):
        db.set_gate_open(gate_key, sub)
        db_users.log_activity(g.user["id"], "gate", f"settings:{sub}",
                              "فتح القسم المحمي «" + name + "» بالرمز الرئيسي (مفتوح لباقي الجلسة)")
        keep = {k: v for k, v in request.form.items()
                if k not in ("sub", "password", "action")}
        return redirect(url_for("settings.page", sub=sub, **keep))
    return _rb(sub, err="الرمز غير صحيح — حاول مرة أخرى")


@settings_bp.route("/users/add", methods=["POST"])
@login_required
def users_add():
    uid, err = db_users.create_user(
        request.form.get("full_name", ""), request.form.get("username", ""),
        request.form.get("password", ""))
    if err:
        return _rb("users", err=err)
    db_users.log_activity(uid, "login", None, "إنشاء الحساب بواسطة " + g.user["full_name"])
    from services import settings_fs
    _sync_quiet(settings_fs.sync_user_file, db_users.get_user_full(uid), set())
    return _rb("users", ok=f"تم إنشاء حساب «{request.form.get('full_name').strip()}»")


@settings_bp.route("/users/update", methods=["POST"])
@login_required
def users_update():
    uid = arnum.parse_int(request.form.get("user_id"), 0)
    u_old = db_users.get_user_full(uid)
    if not u_old:
        return _rb("users", err="الحساب غير موجود")
    err = db_users.update_user(uid,
                               full_name=request.form.get("full_name") or None,
                               username=request.form.get("username") or None,
                               password=request.form.get("password") or None)
    if err:
        return _rb("users", err=err)
    from services import settings_fs
    u_new = db_users.get_user_full(uid)
    if u_old["full_name"] != u_new["full_name"] or u_old["username"] != u_new["username"]:
        _sync_quiet(settings_fs.delete_user_file, u_old)   # اسم الملف تغيّر → النسخ القديمة
    _sync_quiet(settings_fs.sync_user_file, u_new, db_users.get_user_tabs(uid))
    return _rb("users", ok="تم حفظ التعديل")


@settings_bp.route("/users/toggle", methods=["POST"])
@login_required
def users_toggle():
    uid = arnum.parse_int(request.form.get("user_id"), 0)
    u = db_users.get_user_full(uid)
    if not u:
        return _rb("users", err="الحساب غير موجود")
    if u["id"] == g.user["id"]:
        return _rb("users", err="لا يمكنك تعطيل حسابك بنفسك")
    if u["role"] == "admin" and not u["is_active"] and db_users.admin_count() <= 1:
        return _rb("users", err="آخر مدير نشط — لا يمكنك تعطيله")
    db_users.set_active(uid, not u["is_active"])
    from services import settings_fs
    _sync_quiet(settings_fs.sync_user_file, db_users.get_user_full(uid), db_users.get_user_tabs(uid))
    return _rb("users", ok=("تم تفعيل الحساب" if u["is_active"] else "تم تعطيل الحساب"))


@settings_bp.route("/users/delete", methods=["POST"])
@login_required
def users_delete():
    uid = arnum.parse_int(request.form.get("user_id"), 0)
    u = db_users.get_user_full(uid)
    if not u:
        return _rb("users", err="الحساب غير موجود")
    if u["id"] == g.user["id"]:
        return _rb("users", err="لا يمكنك حذف حسابك بنفسك")
    if u["role"] == "admin" and db_users.admin_count() <= 1:
        return _rb("users", err="آخر مدير — لا يمكنك حذفه")
    db_users.delete_user(uid)
    from services import settings_fs
    _sync_quiet(settings_fs.delete_user_file, u)
    return _rb("users", ok=f"تم حذف حساب «{u['full_name']}»")


@settings_bp.route("/users/tabs", methods=["POST"])
@login_required
def users_tabs():
    uid = arnum.parse_int(request.form.get("user_id"), 0)
    u = db_users.get_user_full(uid)
    if not u:
        return _rb("users", err="الحساب غير موجود")
    keys = {v for v in request.form.getlist("tab") if v}
    db_users.set_user_tabs(uid, keys)
    from services import settings_fs
    _sync_quiet(settings_fs.sync_user_file, u, keys)
    return _rb("users", ok=f"تم حفظ صلاحيات «{u['full_name']}»")


# ======================================================================
# ٢) سجلات المستخدمين
# ======================================================================
@settings_bp.route("/log/download")
@login_required
def log_download():
    uid = arnum.parse_int(request.args.get("user"), 0)
    u = db_users.get_user_full(uid)
    if not u:
        return _rb("log", err="اختر مستخدمًا أولًا")
    from core.downloads import attachment
    from services import settings_fs
    path = settings_fs.sync_log_file(u)
    from flask import send_file
    if not path or not path.is_file():
        return _rb("log", err="ملف السجل غير موجود")
    return attachment(path, fallback=path.name)


# ======================================================================
# ٣) المتابعة والملاحظات
# ======================================================================
@settings_bp.route("/notes/add", methods=["POST"])
@login_required
def notes_add():
    to = arnum.parse_int(request.form.get("to_user"), 0)
    to_u = db_users.get_user_full(to)
    nid = db_users.add_note(g.user["id"], to, request.form.get("text", ""))
    if not nid:
        return _rb("notes", err="اكتب نص الملحوظة واختر الشخص الموجهة إليه")
    db_users.log_activity(g.user["id"], "note", "settings:notes",
                          f"ملحوظة جديدة إلى: {to_u['full_name'] if to_u else 'مستخدم'}")
    from services import settings_fs
    settings_fs.sync_notes_file()
    return _rb("notes", ok="تم إرسال الملحوظة")


@settings_bp.route("/notes/reply", methods=["POST"])
@login_required
def notes_reply():
    nid = arnum.parse_int(request.form.get("note_id"), 0)
    if not db_users.reply_note(nid, g.user["id"], request.form.get("text", "")):
        return _rb("notes", err="اكتب نص الرد")
    from services import settings_fs
    settings_fs.sync_notes_file()
    return _rb("notes", ok="تم حفظ الرد")


@settings_bp.route("/notes/close", methods=["POST"])
@login_required
def notes_close():
    nid = arnum.parse_int(request.form.get("note_id"), 0)
    db_users.close_note(nid, g.user["id"])
    db_users.log_activity(g.user["id"], "note", "settings:notes", f"إغلاق الملحوظة #{nid}")
    from services import settings_fs
    settings_fs.sync_notes_file()
    return _rb("notes", ok="تم قفل الملحوظة")
