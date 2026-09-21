# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحة المجندين العاملين بوحدة التعيينات — أدوات عامة.
تبويبات: أصل القوة · اليومية العامة · الحضور · الإجازات · الغياب · أخرى · الإحصائيات.
سجل المجندين عالمي (recruits.db) واليومية شهرية معزولة داخل قاعدة الشهر (قاعدة العزل).
"""
import re
from datetime import date
from urllib.parse import quote

from flask import (Blueprint, abort, redirect, render_template, request,
                   send_file, url_for)

import arabic_numbers as arnum
import database as db
import dataguard
import db_attendance as da
import db_recruits as dr
import docx_recruits
import egtime
import notifications
import storage
from auth_core import current_context, current_session, login_required

recruits_bp = Blueprint("recruits", __name__, url_prefix="/recruits")

MONTH_NAMES = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
               "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
TABS = [("registry", "أصل القوة", "👥"), ("journal", "اليومية العامة", "📝"),
        ("present", "الحضور", "✅"), ("leaves", "الإجازات", "🏖️"),
        ("absent", "الغياب", "🚫"), ("other", "أخرى", "🧭"),
        ("stats", "الإحصائيات والإشعارات", "📊")]
ALLOWED_IMG = {"png", "jpg", "jpeg", "webp"}


# ==================== أدوات داخلية ====================
def _ctx():
    return current_context(__import__("flask").g.user["id"])


def _rb(ok=None, err=None, **params):
    _, token = current_session()
    qs = [f"sid={quote(token)}"] if token else []
    if ok:
        qs.append("ok=" + quote(ok))
    if err:
        qs.append("err=" + quote(err))
    qs += ["{}={}".format(k, quote(str(v))) for k, v in params.items() if v not in (None, "")]
    return redirect(url_for("recruits.page") + ("?" + "&".join(qs) if qs else ""))


def _lh_vars():
    v = {"lh": [db.get_setting(f"lh_{i}") or "" for i in range(1, 5)],
         "sig_right": (db.get_setting("sig_right_rank"), db.get_setting("sig_right_name")),
         "sig_left": (db.get_setting("sig_left_rank"), db.get_setting("sig_left_name"))}
    logo = db.get_setting("logo_file")
    v["has_logo"] = bool(logo and (storage.letterhead_dir() / logo).exists())
    return v


def _files_dir():
    p = storage.DATA_DIR / "المجندون" / "ملفات"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _today_info(year, month, day):
    """حقائق «اليوم الحقيقي» بتوقيت القاهرة داخل شهر السياق."""
    t = egtime.today()
    is_real_month = (t.year == year and t.month == month)
    return {"today": t, "real_day": t.day if is_real_month else None,
            "is_real_month": is_real_month, "cur_day": day,
            "cur_weekday": egtime.weekday_ar(date(year, month, day))}


def _base_vars(tab):
    year, month = _ctx()
    today = egtime.today()
    return {
        "tab": tab, "tabs": TABS, "year": year, "month": month,
        "month_name": MONTH_NAMES[month - 1], "eom": egtime.days_in_month(year, month),
        "today_ar": egtime.fmt_ar(today), "time_now": egtime.now().strftime("%H:%M:%S"),
        "statuses": da.STATUSES, "recruits": dr.list_recruits(),
        "govs": dr.vocab("gov"), "cities": dr.vocab("city"),
        **_lh_vars(),
    }


def _cert_badge(r, today):
    st = dr.cert_state(r, today)
    return {"ok": ("🟢", "سارية"), "soon": ("🟠", "تنتهي قريبًا"),
            "expired": ("🔴", "منتهية!"), "none": ("⚪", "لا توجد")}[st]


# ======================================================================
# الصفحة الرئيسية — موزّع التبويبات
# ======================================================================
@recruits_bp.route("")
@recruits_bp.route("/")
@login_required
def page():
    tab = request.args.get("tab", "registry")
    v = _base_vars(tab)
    if tab == "journal":
        return _journal(v)
    if tab in ("present", "leaves", "absent", "other"):
        return _lists(v)
    if tab == "stats":
        return _stats(v)
    return _registry(v)


# ==================== تبويب أصل القوة ====================
def _registry(v):
    today = egtime.today()
    edit_id = arnum.parse_int(request.args.get("edit"))
    v["edit_item"] = dr.get_recruit(edit_id) if edit_id else None
    v["badges"] = {r["id"]: _cert_badge(r, today) for r in v["recruits"]}
    v["discharge"] = {r["id"]: dr.days_to_discharge(r, today) for r in v["recruits"]}
    return render_template("recruits_registry.html", **v)


def _save_upload(field, prefix):
    f = request.files.get(field)
    if not f or not f.filename:
        return None
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_IMG:
        return None
    import secrets
    name = "{}_{}.{}".format(prefix, secrets.token_hex(4), ext)
    dataguard.atomic_save(f.save, _files_dir() / name, zip_check=False)
    return name


@recruits_bp.route("/save", methods=["POST"])
@login_required
def save():
    rid = arnum.parse_int(request.form.get("id"))
    old = dr.get_recruit(rid) if rid else {}
    data = {k: (request.form.get(k) or "").strip() for k in
            ("name", "mil_no", "service_start", "service_end", "governorate",
             "city", "address", "cert_date", "cert_expiry")}
    data["has_cert"] = 1 if request.form.get("has_cert") else 0
    if not data["name"] or not data["mil_no"]:
        return _rb(err="الاسم والرقم العسكري إلزاميان", tab="registry")
    twin = dr.find_by(mil_no=data["mil_no"])
    if twin and (not rid or twin["id"] != rid):
        return _rb(err="الرقم العسكري «{}» مسجل بالفعل لمجند آخر".format(data["mil_no"]), tab="registry")
    data["photo"] = old.get("photo", "")
    data["cert_photo"] = old.get("cert_photo", "")
    up = _save_upload("photo", "photo")
    if up:
        data["photo"] = up
    up = _save_upload("cert_photo", "cert")
    if up:
        data["cert_photo"] = up
    if rid:
        dr.update_recruit(rid, data)
        msg = "تم حفظ تعديل «{}» ✔".format(data["name"])
    else:
        rid = dr.add_recruit(data)
        msg = "تم تسجيل المجند «{}» في أصل القوة ✔".format(data["name"])
    dataguard.auto_backup("write", min_minutes=20)
    return _rb(ok=msg, tab="registry")


@recruits_bp.route("/delete/<int:rid>", methods=["POST"])
@login_required
def delete(rid):
    r = dr.get_recruit(rid)
    if not r:
        abort(404)
    dr.delete_recruit(rid)
    dataguard.auto_backup("write", min_minutes=20)
    return _rb(ok="حُذف «{}» من أصل القوة (سجلات يوميته السابقة محفوظة في شهورها)".format(r["name"]),
               tab="registry")


# ==================== ملفات المجند (صوره/شهادته) ====================
@recruits_bp.route("/file/<name>")
@login_required
def file_view(name):
    if not re.match(r"^(photo|cert)_[0-9a-f]{8}\.(png|jpg|jpeg|webp)$", name):
        abort(404)
    path = _files_dir() / name
    if not path.exists():
        abort(404)
    return send_file(str(path), conditional=False, max_age=3600)


# ======================================================================
# تبويب اليومية العامة
# ======================================================================
def _journal(v):
    year, month = v["year"], v["month"]
    info = _today_info(year, month, 1)
    day = arnum.parse_int(request.args.get("day")) or info["real_day"] or 1
    day = max(1, min(v["eom"], day))
    carried, src = da.carry_over_if_needed(year, month, day)
    meta = da.get_meta(year, month, day)
    v.update({
        "day": day, "info": _today_info(year, month, day),
        "day_map": da.get_day_map(year, month, day), "meta": meta,
        "carried": carried, "carried_from": src,
        "missing": set(da.days_without_journal(year, month, min(day, v["eom"]))),
        "locked_days": _locked_days(year, month),
    })
    return render_template("recruits_journal.html", **v)


def _locked_days(year, month):
    import months
    conn = months.get_db(year, month)
    da.ensure_tables(conn)
    rows = conn.execute("SELECT day FROM journal_meta WHERE locked=1").fetchall()
    conn.close()
    return {r["day"] for r in rows}


@recruits_bp.route("/journal/save", methods=["POST"])
@login_required
def journal_save():
    year, month = _ctx()
    day = arnum.parse_int(request.form.get("day"))
    if not day or not (1 <= day <= 31):
        return _rb(err="يوم غير صالح", tab="journal")
    meta = da.get_meta(year, month, day)
    if meta["locked"]:
        return _rb(err="يومية يوم {} مُثبَّتة ومقفولة — اطلب «تعديلً رغم التثبيت» أولًا".format(day),
                   tab="journal", day=day)
    entries = []
    for r in dr.list_recruits():
        st = request.form.get("st_{}".format(r["id"]))
        note = (request.form.get("note_{}".format(r["id"])) or "").strip()
        if st in da.STATUSES:
            entries.append((r["id"], st, note if st == "أخرى" else note))
    if not entries:
        return _rb(err="لم تُسجَّل أي حالة — اختر حالة مجند واحد على الأقل", tab="journal", day=day)
    da.save_day(year, month, day, entries, lock=True,
                source_day=arnum.parse_int(request.form.get("source_day")) or 0)
    _after_attendance_change(year, month)
    return _rb(ok="ثُبِّتت يومية يوم {} وقُفلت ✔ (مسجَّل {} مجندًا)".format(day, len(entries)),
               tab="journal", day=day)


@recruits_bp.route("/journal/unlock", methods=["POST"])
@login_required
def journal_unlock():
    year, month = _ctx()
    day = arnum.parse_int(request.form.get("day")) or 1
    da.unlock_day(year, month, day)
    return _rb(ok="فُتحت يومية يوم {} للتعديل (بتأكيدك الصريح)".format(day), tab="journal", day=day)


@recruits_bp.route("/journal/range", methods=["POST"])
@login_required
def journal_range():
    year, month = _ctx()
    ref = (request.form.get("recruit_ref") or "").strip()
    status = (request.form.get("status") or "").strip()
    note = (request.form.get("note") or "").strip()
    from_d = arnum.parse_int(request.form.get("from_day"))
    to_d = arnum.parse_int(request.form.get("to_day"))
    recruit = _resolve_recruit(ref)
    if not recruit:
        return _rb(err="لم يُعرف المجند «{}» — اكتب الاسم كما في أصل القوة".format(ref), tab="journal")
    if status not in da.STATUSES:
        return _rb(err="اختر حالة صحيحة", tab="journal")
    if not from_d or not to_d or not (1 <= from_d <= to_d <= egtime.days_in_month(year, month)):
        return _rb(err="مدى الأيام غير صالح", tab="journal")
    locked = _locked_days(year, month) & set(range(from_d, to_d + 1))
    if locked:
        return _rb(err="يوم {} داخل المدى مُثبَّت ومقفول — افتحه أولًا إن أردت تعديله".format(min(locked)),
                   tab="journal", day=min(locked))
    n = da.set_range(year, month, recruit["id"], status, from_d, to_d, note)
    _after_attendance_change(year, month)
    return _rb(ok="سُجِّلت «{}» لـ {} من يوم {} إلى {} ({} يومًا)".format(
        status, recruit["name"], from_d, to_d, n), tab="journal", day=to_d)


def _resolve_recruit(ref):
    if " — " in ref:
        name, mil = ref.rsplit(" — ", 1)
        r = dr.find_by(mil_no=mil.strip()) or dr.find_by(name=name.strip())
    else:
        r = dr.find_by(mil_no=ref) or dr.find_by(name=ref)
    return r


@recruits_bp.route("/journal/delete-entry", methods=["POST"])
@login_required
def journal_delete_entry():
    year, month = _ctx()
    day = arnum.parse_int(request.form.get("day"))
    rid = arnum.parse_int(request.form.get("recruit_id"))
    meta = da.get_meta(year, month, day)
    if meta["locked"]:
        return _rb(err="اليومية مُثبَّتة — افتحها أولًا", tab="journal", day=day)
    da.delete_recruit_day(year, month, day, rid)
    _after_attendance_change(year, month)
    return _rb(ok="حُذف التسجيل من يوم {}".format(day), tab="journal", day=day)


def _after_attendance_change(year, month):
    """كشوف الوورد اللحظية + نسخة احتياطية مخنوقة بعد أي تعديل يومية/سجل."""
    try:
        docx_recruits.rebuild_month(year, month)
    except Exception as exc:  # noqa: BLE001 — الوورد لا يُسقط الحفظ
        print("⚠️ تعذّر تحديث كشوف الوورد:", exc)
    dataguard.auto_backup("write", min_minutes=20)


# ======================================================================
# تبويبات القوائم: الحضور / الإجازات / الغياب / أخرى
# ======================================================================
def _lists(v):
    tab, year, month = v["tab"], v["year"], v["month"]
    today = egtime.today()
    v["matrix"] = da.month_matrix(year, month)
    v["by_id"] = {r["id"]: r for r in v["recruits"]}
    v["info"] = _today_info(year, month, 1)
    v["badges"] = {r["id"]: _cert_badge(r, today) for r in v["recruits"]}
    if tab == "present":
        day = arnum.parse_int(request.args.get("day")) or v["info"]["real_day"] or 1
        dmap = da.get_day_map(year, month, day)
        v["day"] = day
        v["rows"] = [(v["by_id"][rid], st) for rid, st in dmap.items()
                     if rid in v["by_id"] and st["status"] == "حضور"]
        v["counts"] = {st: sum(1 for x in dmap.values() if x["status"] == st) for st in da.STATUSES}
    elif tab == "leaves":
        v["ranges"] = da.leave_ranges(year, month, v["matrix"], 1, v["eom"])
        rd = v["info"]["real_day"] or 1
        v["upcoming"] = da.leave_ranges(year, month, v["matrix"], rd, min(rd + 2, v["eom"])) \
            if v["info"]["is_real_month"] else {}
    elif tab == "absent":
        rd = v["info"]["real_day"] or 1
        v["streaks"] = da.absence_streak(year, month, v["matrix"],
                                         max(1, rd - 1)) if v["info"]["is_real_month"] else {}
        v["rows"] = [(v["by_id"][rid], d) for rid, days in v["matrix"].items()
                     for d, st in sorted(days.items()) if st == "غياب" and rid in v["by_id"]]
    else:
        v["groups"] = [
            ("مأمورية", [(v["by_id"][rid], d) for rid, days in v["matrix"].items()
                         for d, st in sorted(days.items()) if st == "مأمورية" and rid in v["by_id"]]),
            ("مستشفى", [(v["by_id"][rid], d) for rid, days in v["matrix"].items()
                        for d, st in sorted(days.items()) if st == "مستشفى" and rid in v["by_id"]]),
            ("أخرى", [(v["by_id"][rid], d, da.get_day_map(year, month, d)[rid]["note"])
                      for rid, days in v["matrix"].items()
                      for d, st in sorted(days.items()) if st == "أخرى" and rid in v["by_id"]]),
        ]
    return render_template("recruits_lists.html", **v)


# ======================================================================
# تبويب الإحصائيات والإشعارات
# ======================================================================
def _stats(v):
    year, month = v["year"], v["month"]
    today = egtime.today()
    _, token = current_session()
    info = _today_info(year, month, 1)
    matrix = da.month_matrix(year, month)
    rd = info["real_day"] or 0
    dmap = da.get_day_map(year, month, rd) if rd else {}
    v["notif_groups"] = notifications.build_groups(__import__("flask").g.user["id"], token or "")
    v["counts_today"] = {st: sum(1 for x in dmap.values() if x["status"] == st) for st in da.STATUSES}
    v["certs"] = {"expired": [], "soon": []}
    for r in v["recruits"]:
        st = dr.cert_state(r, today)
        if st in ("expired", "soon"):
            v["certs"][st].append(r)
    v["discharging"] = [(r, dr.days_to_discharge(r, today)) for r in v["recruits"]
                        if (dr.days_to_discharge(r, today) or 999) <= 60]
    v["ranges"] = da.leave_ranges(year, month, matrix, 1, v["eom"])
    v["by_id"] = {r["id"]: r for r in v["recruits"]}
    v["sheet_matrix"], v["sheet_leaves"] = docx_recruits.month_sheets(year, month)
    v["missing"] = da.days_without_journal(year, month, rd or v["eom"])
    v["info"] = info
    return render_template("recruits_stats.html", **v)


# ======================================================================
# الطباعة الرسمية (A4 بالدباجة والتوقيعين) + الوورد اللحظي
# ======================================================================
@recruits_bp.route("/print/<what>")
@login_required
def print_doc(what):
    year, month = _ctx()
    v = _base_vars("stats")
    today = egtime.today()
    matrix = da.month_matrix(year, month)
    by_id = {r["id"]: r for r in v["recruits"]}
    info = _today_info(year, month, 1)
    v["print_kind"] = what

    if what == "permit":
        rid = arnum.parse_int(request.args.get("rid"))
        f = arnum.parse_int(request.args.get("from"))
        t = arnum.parse_int(request.args.get("to"))
        r = dr.get_recruit(rid)
        if not r or not f or not t or f > t:
            abort(404)
        v["recruit"] = r
        v["from_day"], v["to_day"] = f, t
        v["title"] = "تصريح إجازة"
        path = docx_recruits.build_leave_permit(r, f, t, year, month)
        v["docx_name"] = path.name
    elif what == "day":
        day = arnum.parse_int(request.args.get("day")) or info["real_day"] or 1
        dmap = da.get_day_map(year, month, day)
        v["day"] = day
        v["rows"] = [(by_id[rid], st) for rid, st in dmap.items() if rid in by_id]
        v["counts"] = {st: sum(1 for x in dmap.values() if x["status"] == st) for st in da.STATUSES}
        v["title"] = "كشف اليومية العامة — يوم {} {} {}".format(
            day, MONTH_NAMES[month - 1], year)
    elif what == "month-leaves":
        v["ranges"] = da.leave_ranges(year, month, matrix, 1, v["eom"])
        v["by_id"] = by_id
        v["title"] = "كشف الإجازات — شهر {} {}".format(MONTH_NAMES[month - 1], year)
    elif what == "certs":
        v["rows"] = [(r, dr.cert_state(r, today)) for r in v["recruits"]]
        v["title"] = "كشف موقف الشهادات الصحية"
    elif what == "recruit":
        rid = arnum.parse_int(request.args.get("rid"))
        r = dr.get_recruit(rid)
        if not r:
            abort(404)
        v["recruit"] = r
        v["rows"] = sorted(matrix.get(rid, {}).items())
        v["title"] = "كشف حالة المجند / {} — شهر {} {}".format(r["name"], MONTH_NAMES[month - 1], year)
    else:
        abort(404)
    v["month_name"] = MONTH_NAMES[month - 1]
    return render_template("recruits_print.html", **v)


@recruits_bp.route("/docx/<name>")
@login_required
def docx_download(name):
    if not re.match(r"^(كشف-(الحالات|الإجازات)-\d{4}-\d{2}|تصريح-.*-\d{4}-\d{2}-\d{2})\.docx$", name):
        abort(404)
    base = docx_recruits.docs_dir()
    path = base / name
    if not path.exists():
        path = base / "تصاريح" / name
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name=name,
                     conditional=False, max_age=0)


@recruits_bp.route("/docx/rebuild", methods=["POST"])
@login_required
def docx_rebuild():
    year, month = _ctx()
    p1, p2 = docx_recruits.rebuild_month(year, month)
    return _rb(ok="أُعيد بناء كشفي الوورد: «{}» + «{}»".format(p1.name, p2.name), tab="stats")
