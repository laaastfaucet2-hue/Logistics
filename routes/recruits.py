# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""صفحة المجندين العاملين بوحدة التعيينات — أدوات عامة.
تبويبات: أصل القوة · اليومية العامة · الحضور · الإجازات · الغياب · أخرى · الإحصائيات.
سجل المجندين واليومية والدباجة معزولة داخل قاعدة الشهر.
"""
import re
from datetime import date
from urllib.parse import quote

from core.downloads import attachment
from flask import (Blueprint, abort, redirect, render_template, request,
                   send_file, url_for)

from core import arabic_numbers as arnum
from data_access import database as db
from services import recruits_fs
from data_access import dataguard
from data_access import db_attendance as da
from data_access import db_punishments as dpk
from data_access import db_recruits as dr
from data_access import db_health
from documents import docx_recruits, docx_milfile
from core import egtime, dates
from services import notifications
from data_access import storage, db_letterhead as lh
from services import legacy_months, recruit_dates
from services import recruit_file
from core.auth_core import current_context, current_session, login_required

recruits_bp = Blueprint("recruits", __name__, url_prefix="/recruits")

from core.config import MONTH_NAMES
TABS = [("registry", "أصل القوة", "👥"), ("journal", "اليومية العامة", "📝"),
        ("present", "الحضور", "✅"), ("leaves", "الإجازات", "🏖️"),
        ("absent", "الغياب", "🚫"), ("other", "أخرى", "🧭"),
        ("prison", "السجن", "⛓️"),
        ("stats", "الإحصائيات والإشعارات", "📊")]
ALLOWED_IMG = {"png", "jpg", "jpeg", "webp"}


# ==================== أدوات داخلية ====================
def _ctx():
    return current_context(__import__("flask").g.user["id"])


def _rb(ok=None, err=None, **params):
    _, token = current_session()
    year, month = _ctx()
    values = {"sid": token, "year": year, "month": month, "ok": ok, "err": err, **params}
    return redirect(url_for("recruits.page", **{k: v for k, v in values.items() if v not in (None, "")}))


def _lh_vars():
    year, month = _ctx()
    return lh.template_vars(year, month)


def _files_dir():
    return storage.recruits_dir(*_ctx())


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
        "legacy_registry": legacy_months.registry_available() if not legacy_months.imported("registry", year, month) else 0,
        "statuses": da.STATUSES, "recruits": dr.list_recruits(*_ctx()),
        "govs": dr.govs_for_ui(*_ctx()),
        "cities": dr.vocab(*_ctx(), "city"),
        "places_by_gov": dr.places_by_gov(*_ctx()),
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
    try:
        recruits_fs.ensure_folders(*_ctx())   # ٧ مجلدات بأسماء التويبات (توجيه ٢٨/٠٩)
    except OSError:
        pass
    v = _base_vars(tab)
    if tab == "journal":
        return _journal(v)
    if tab in ("present", "leaves", "absent", "other"):
        return _lists(v)
    if tab == "stats":
        return _stats(v)
    if tab == "file":
        return _file(v)
    if tab == "prison":
        return _prison(v)
    return _registry(v)


# ==================== التقرير الرسمى للمجند (Word + فولدر محلى) ====================
@recruits_bp.route("/milfile/<int:year>/<int:month>/<int:rid>")
@login_required
def milfile_report(year, month, rid):
    """توليد تقرير التتبع الرسمى (بالدباجة واللوجو والتوقيعين) في فولدر المجند المحلى وتنزيله."""
    r = dr.get_recruit(year, month, rid)
    if not r:
        abort(404)
    path = docx_milfile.build(year, month, rid)
    if not path:
        abort(404)
    return attachment(path, fallback="milfile" + path.suffix)


# ==================== تاب السجن والمحكمات والجزاءات (المراحل ٥ + ٠) ====================
def _prison(v):
    """٣ تابات فرعية (سجن/المحكمات/الجزاءات) — المدد مشتقة من اليومية العامة.

    التسجيل من «اليومية العامة» بحالة المجند (سجن/محكمة/جزاء) — مش من التاب.
    المدة = الأيام المتتالية للحالة · لو الحالة اتغيرت بتقفل · لو فاضية تبقى مفتوحة.
    """
    year, month = _ctx()
    pkind = request.args.get("pkind") or "prison"
    if pkind not in dpk.VALID_KINDS:
        pkind = "prison"
    meta = dpk.KIND_META[pkind]
    info = _today_info(year, month, 1)
    rd = info["real_day"]
    by_id = {r["id"]: r for r in v["recruits"]}
    rows = []
    for rid, f, t in dpk.month_spans(year, month, pkind):
        r = by_id.get(rid)
        if not r:
            continue
        rows.append((r, f, t, dpk.span_state(f, t, rd)))
    rows.sort(key=lambda x: (x[1], x[0]["name"]))
    v["prison_rows"] = rows
    v["pkind"] = pkind
    v["pkind_meta"] = meta
    v["pkinds"] = dpk.PUNISH_KINDS
    v["real_day"] = rd
    v["is_real_month"] = info["is_real_month"]
    v["prison_status"] = meta["status"]
    # تذكير النهارده وبكرة — نفس نص الجرس حرفيًا (المصدر المشترك)
    alerts = []
    if rd:
        _leaves, events = notifications._event_entries(
            year, month, da.month_matrix(year, month), by_id, rd, v["eom"], "")
        alerts = [e["text"] for e in events if "tab=prison" in e.get("href", "")]
    v["prison_alerts"] = alerts
    return render_template("recruits_prison.html", **v)


def _file(v):
    """ملف المجند الشامل — كل الشهور (المرحلة ٤) — بتواب فرعية:
    أساسى · يومي (كل يوم) · محطات · خط زمني."""
    rid = arnum.parse_int(request.args.get("rid"))
    v["ftab"] = request.args.get("ftab") or "daily"
    data = recruit_file.build(*_ctx(), rid) if rid else None
    if not data:
        abort(404)
    r = data["recruit"]
    today = egtime.today()
    info = _today_info(*_ctx(), 1)
    matrix = da.month_matrix(*_ctx())
    v["recruit"] = r
    v["file_data"] = data
    v["cert_badge"] = _cert_badge(r, today)
    v["discharge_days"] = dr.days_to_discharge(r, today)
    v["latest"] = da.latest_statuses(*_ctx(), matrix,
                                     info["real_day"] or v["eom"]).get(r["id"])
    v["print_title"] = "ملف المجند / {} — {} — كل الشهور".format(
        r["name"], r["mil_no"])
    return render_template("recruits_file.html", **v)


# ==================== تبويب أصل القوة ====================
def _registry(v, form_values=None, form_error=None):
    today = egtime.today()
    edit_id = arnum.parse_int(request.args.get("edit"))
    v["edit_item"] = form_values if form_values is not None else (dr.get_recruit(*_ctx(), edit_id) if edit_id else None)
    v["form_error"] = form_error
    v["badges"] = {r["id"]: _cert_badge(r, today) for r in v["recruits"]}
    v["discharge"] = {r["id"]: dr.days_to_discharge(r, today) for r in v["recruits"]}
    # عمود «الحالة»: آخر حالة مسجلة في اليومية حتى اليوم الحقيقي (آخر شهر كامل لو السياق شهر تاني)
    info = _today_info(*_ctx(), 1)
    v["latest"] = da.latest_statuses(*_ctx(), da.month_matrix(*_ctx()),
                                     info["real_day"] or v["eom"])
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
    old = dr.get_recruit(*_ctx(), rid) if rid else {}
    if rid and not old:
        abort(404)
    data = {k: (request.form.get(k) or "").strip() for k in
            ("name", "mil_no", "service_start", "service_end", "governorate",
             "city", "address", "cert_date", "cert_expiry")}
    data["mil_no"] = arnum.to_western(data["mil_no"])
    data["has_cert"] = 1 if request.form.get("has_cert") else 0
    if not data["name"] or not data["mil_no"]:
        return _rb(err="الاسم والرقم العسكري إلزاميان", tab="registry")
    twin = dr.find_by(*_ctx(), mil_no=data["mil_no"])
    if twin and (not rid or twin["id"] != rid):
        return _rb(err="الرقم العسكري «{}» مسجل بالفعل لمجند آخر".format(data["mil_no"]), tab="registry")
    try:
        data = recruit_dates.normalize(data)
    except ValueError as exc:
        draft = {**old, **data, "id": rid or ""}
        return _registry(_base_vars("registry"), draft, str(exc)), 400
    data["photo"] = old.get("photo", "")
    data["cert_photo"] = old.get("cert_photo", "")
    up = _save_upload("photo", "photo")
    if up:
        data["photo"] = up
    up = _save_upload("cert_photo", "cert") if data["has_cert"] else None
    if up:
        data["cert_photo"] = up
    if not data["has_cert"]:
        data.update(cert_date="", cert_expiry="", cert_photo="")
    if rid:
        dr.update_recruit(*_ctx(), rid, data)
        msg = "تم حفظ تعديل «{}» ✔".format(data["name"])
    else:
        rid = dr.add_recruit(*_ctx(), data)
        msg = "تم تسجيل المجند «{}» في أصل القوة ✔".format(data["name"])
    try:
        recruits_fs.snapshot_all(*_ctx())   # أصل القوة تغيّر — حدّث مرايا التويبات
    except OSError:
        pass
    dataguard.auto_backup("write", min_minutes=20)
    return _rb(ok=msg, tab="registry")


@recruits_bp.route("/delete/<int:rid>", methods=["POST"])
@login_required
def delete(rid):
    r = dr.get_recruit(*_ctx(), rid)
    if not r:
        abort(404)
    try:
        dr.delete_recruit(*_ctx(), rid)
    except ValueError as exc:
        return _rb(err=str(exc))
    try:
        recruits_fs.snapshot_all(*_ctx())
    except OSError:
        pass
    dataguard.auto_backup("write", min_minutes=20)
    return _rb(ok="حُذف «{}» من أصل القوة من الشهر الحالي فقط".format(r["name"]),
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
    matrix = da.month_matrix(year, month)
    by_id = {r["id"]: r for r in v["recruits"]}
    v.update({
        "day": day, "info": _today_info(year, month, day),
        "day_map": da.get_day_map(year, month, day), "meta": meta,
        "carried": carried, "carried_from": src,
        "missing": set(da.days_without_journal(year, month, min(day, v["eom"]))),
        "locked_days": _locked_days(year, month),
        # بنرات التذكير: أحداث اليوم + معاينة غدًا (نفس مصدر الجرس)
        "day_events": notifications.day_events(year, month, matrix, day, by_id),
        "next_events": (notifications.day_events(year, month, matrix, day + 1, by_id)
                        if day < v["eom"] else []),
    })
    return render_template("recruits_journal.html", **v)


def _locked_days(year, month):
    from data_access import months
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
    if not day or not (1 <= day <= egtime.days_in_month(year, month)):
        return _rb(err="يوم غير صالح", tab="journal")
    meta = da.get_meta(year, month, day)
    if meta["locked"]:
        return _rb(err="يومية يوم {} مُثبَّتة ومقفولة — اطلب «تعديلً رغم التثبيت» أولًا".format(arnum.to_arabic_indic(day)),
                   tab="journal", day=day)
    entries = []
    for r in dr.list_recruits(*_ctx()):
        st = request.form.get("st_{}".format(r["id"]))
        note = (request.form.get("note_{}".format(r["id"])) or "").strip()
        if st in da.STATUSES:
            entries.append((r["id"], st, note if st == "أخرى" else note))
    if not entries:
        return _rb(err="لم تُسجَّل أي حالة — اختر حالة مجند واحد على الأقل", tab="journal", day=day)
    da.save_day(year, month, day, entries, lock=True,
                source_day=arnum.parse_int(request.form.get("source_day")) or 0)
    _after_attendance_change(year, month)
    return _rb(ok="ثُبِّتت يومية يوم {} وقُفلت ✔ (مسجَّل {} مجندًا)".format(
                   arnum.to_arabic_indic(day), arnum.to_arabic_indic(str(len(entries)))),
               tab="journal", day=day)


@recruits_bp.route("/journal/unlock", methods=["POST"])
@login_required
def journal_unlock():
    year, month = _ctx()
    day = arnum.parse_int(request.form.get("day")) or 1
    da.unlock_day(year, month, day)
    _after_attendance_change(year, month)
    return _rb(ok="فُتحت يومية يوم {} للتعديل (بتأكيدك الصريح)".format(arnum.to_arabic_indic(day)), tab="journal", day=day)


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
        r = dr.find_by(*_ctx(), mil_no=mil.strip()) or dr.find_by(*_ctx(), name=name.strip())
    else:
        r = dr.find_by(*_ctx(), mil_no=ref) or dr.find_by(*_ctx(), name=ref)
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
    return _rb(ok="حُذف التسجيل من يوم {}".format(arnum.to_arabic_indic(day)), tab="journal", day=day)


@recruits_bp.route("/journal/confirm-leaves", methods=["POST"])
@login_required
def journal_confirm_leaves():
    """«أكّد ويتحطوا في اليومية» — تصاريح الإجازات الصادرة عن إجازة بتبدأ في اليوم
    ده ⇒ الحالة «إجازة» تنطبع عليهم في اليومية كامل مدتهم (قرار الجولة ٣٥)."""
    year, month = _ctx()
    day = arnum.parse_int(request.form.get("day"))
    eom = egtime.days_in_month(year, month)
    if not day or not (1 <= day <= eom):
        return _rb(err="يوم غير صالح", tab="journal")
    permits = da.month_leave_permits(year, month)
    targets = [(rid, f, t) for rid, rs in permits.items() for f, t in rs if f == day]
    if not targets:
        return _rb(err="لا يوجد تصريح إجازة صادر عن إجازة تبدأ في يوم {} — أنشئ التصريح أولًا".format(
            arnum.to_arabic_indic(day)), tab="journal", day=day)
    by_id = {r["id"]: r for r in dr.list_recruits(year, month)}
    names = [by_id[rid]["name"] for rid, _f, _t in targets if rid in by_id]
    locked = _locked_days(year, month)
    for rid, f, t in targets:
        hit = [d for d in range(f, t + 1) if d in locked]
        if hit:
            return _rb(err="يومية يوم {} (ضمن مدة الإجازة) مثبتة ومقفولة — افتحها الأول".format(
                arnum.to_arabic_indic(min(hit))), tab="journal", day=min(hit))
    for rid, f, t in targets:
        da.set_range(year, month, rid, "إجازة", f, t)
    _after_attendance_change(year, month)
    return _rb(ok="اتأكّد: {} — اتحطوا «إجازة» في اليومية من يوم {} لآخر مدة التصريح ✔".format(
        "، ".join(names), arnum.to_arabic_indic(day)), tab="journal", day=day)


def _after_attendance_change(year, month):
    """مرايا Excel السبعة + كشوف الوورد اللحظية + نسخة احتياطية مخنوقة."""
    try:
        recruits_fs.snapshot_all(year, month)
    except Exception:  # noqa: BLE001 — المرايا لا تُسقط الحفظ
        import logging
        logging.exception("recruits mirrors failed")
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
    by_id = {r["id"]: r for r in v["recruits"]}
    # صفوف يومية/تصاريح «عاوية» (مجندها اتحذف) — بتنسى من الشوفات عشان ما تقصعش الصفحة
    v["matrix"] = {rid: days for rid, days in da.month_matrix(year, month).items() if rid in by_id}
    v["by_id"] = by_id
    v["info"] = _today_info(year, month, 1)
    v["badges"] = {r["id"]: _cert_badge(r, today) for r in v["recruits"]}
    if tab == "present":
        day = arnum.parse_int(request.args.get("day")) or v["info"]["real_day"] or 1
        dmap = da.get_day_map(year, month, day)
        v["day"] = day
        # «إجازة مجمّعة» من الحضور (قرار ١٤/١٠): النافذة كلها بتلف حول اليوم الحقيقي
        v["jl_today"] = v["info"]["real_day"] or 1
        v["rows"] = [(v["by_id"][rid], st) for rid, st in dmap.items()
                     if rid in v["by_id"] and st["status"] == "حضور"]
        # «حضور من يوم كام + المدة + آخر إجازة»
        v["runs"] = da.attendance_runs(year, month, v["matrix"], day)
        past_leaves = da.leave_ranges(year, month, v["matrix"], 1, max(1, day - 1))
        v["last_leave"] = {
            rid: max(t for _f, t in rs)
            for rid, rs in past_leaves.items()
            if rid in v["runs"] and max(t for _f, t in rs) < v["runs"][rid][0]
        }
    elif tab == "leaves":
        v["ranges"] = da.leave_ranges(year, month, v["matrix"], 1, v["eom"])
        # تصاريح الشهر الصادرة — علامة «✓ تصريح» جنب كل صف اتعملت له تصريح
        v["permits"] = da.month_leave_permits(year, month)
        # قطوع الشهر — «🔪 قطع» جنب الإجازة المتقطعة: الصف المختصر يطابق
        # المدة الأصلية (بداية نفسها ونهاية الأصل ≥ نهاية الصف)
        cut_rows = da.month_leave_cuts(year, month)
        v["row_cut"] = {}
        for rid, rs in v["ranges"].items():
            for f, t in rs:
                for c in cut_rows.get(rid, []):
                    if c["period_from"] == f and c["period_to"] >= t:
                        v["row_cut"][(rid, f, t)] = c
                        break
        rd = v["info"]["real_day"] or 1
        # مرتقب مجمّع: {يوم البداية: «محمد وأحمد»} — «نازلين إجازة يوم ٥»
        # (فترات الشهر الكاملة — التقطيع على نافذة قصيرة كان بيعمل بدايات مزيفة)
        upcoming = {}
        if v["info"]["is_real_month"]:
            for rid, rs in da.leave_ranges(year, month, v["matrix"], 1, v["eom"]).items():
                if rid not in v["by_id"]:
                    continue
                for f, _t in rs:
                    if rd <= f <= rd + 2:
                        upcoming.setdefault(f, []).append(v["by_id"][rid]["name"])
        v["upcoming"] = {f: {"names": notifications.and_join(names), "n": len(names)}
                        for f, names in upcoming.items()}
        # «قادم الإجازات»: فترات بتخلص خلال ٧ أيام (اللي هيرجعوا قريب)
        v["leaving_soon"] = []
        if v["info"]["is_real_month"] and v["info"]["real_day"]:
            rd2 = v["info"]["real_day"]
            for rid, rs in v["ranges"].items():
                if rid not in v["by_id"]:
                    continue
                for f, t in rs:
                    if rd2 <= t <= rd2 + 7:
                        v["leaving_soon"].append((v["by_id"][rid], f, t))
            v["leaving_soon"].sort(key=lambda x: (x[2], x[0]["name"]))
    elif tab == "absent":
        rd = v["info"]["real_day"] or 1
        v["streaks"] = da.absence_streak(year, month, v["matrix"],
                                         max(1, rd - 1)) if v["info"]["is_real_month"] else {}
        # سجل الغياب = فترات (من → إلى + المدة) مش أيام متفرقة
        eps = []
        for rid, rs in da.absence_episodes(year, month, v["matrix"], 1, v["eom"]).items():
            if rid in v["by_id"]:
                for f, t in rs:
                    eps.append((v["by_id"][rid], f, t))
        eps.sort(key=lambda x: (x[1], x[0]["name"]))
        v["episodes"] = eps
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
        # لوحة المستشفى: يوم بيوم + الحالة الصحية + ملاحظة (قرار ١٢/١٠)
        v["hospital"] = da.hospital_rows(year, month)
        v["hospital_locked"] = _locked_days(year, month)
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
    # الإشعارات: فلترة مقروء/غير مقروء (المقروء بيتعلم بالضغط على الإشعار)
    uid = __import__("flask").g.user["id"]
    all_groups = notifications.build_groups(uid, token or "")
    v["total_n"] = sum(len(g["entries"]) for g in all_groups)
    v["unread_n"] = sum(1 for g in all_groups for it in g["entries"] if not it["read"])
    v["nf"] = "unread" if request.args.get("nf") == "unread" else "all"
    if v["nf"] == "unread":
        all_groups = [{**g, "entries": [it for it in g["entries"] if not it["read"]]}
                      for g in all_groups]
        all_groups = [g for g in all_groups if g["entries"]]
    v["notif_groups"] = all_groups
    v["counts_today"] = {st: sum(1 for x in dmap.values() if x["status"] == st) for st in da.STATUSES}
    v["certs"] = {"expired": [], "soon": []}
    for r in v["recruits"]:
        st = dr.cert_state(r, today)
        if st in ("expired", "soon"):
            v["certs"][st].append(r)
    # «تنتهي خلال ٦٠ يومًا» = لسه بخدمة وقرب خروج (٠ ≤ المتبقي ≤ ٦٠) —
    # اللي خدمته خلصت (سالبة) مالهاش مكان هنا — طاولة «الأقرب للخروج» بتعرضها «انتهت من X»
    v["discharging"] = [(r, dr.days_to_discharge(r, today)) for r in v["recruits"]
                        if 0 <= (dr.days_to_discharge(r, today) or 999) <= 60]
    # الأقرب للخروج من الخدمة — ترتيب بالأيام المتبقية (أول ٥ من عندهم تاريخ)
    ranked = [(r, dr.days_to_discharge(r, today)) for r in v["recruits"]
              if (r.get("service_end") or "").strip()]
    v["discharge_rank"] = sorted(
        ranked, key=lambda x: ((x[1] if x[1] is not None else 99999), x[0]["name"]))[:5]
    # إحصائيات المحافظات — تجميع أصل القوة بالمحافظة (الأكثر عددًا أولًا)
    gov_map = {}
    for r in v["recruits"]:
        g = (r.get("governorate") or "").strip() or "غير محدد"
        gov_map.setdefault(g, []).append(r)
    v["by_gov"] = [(g, sorted(rs, key=lambda x: x["name"]))
                   for g, rs in sorted(gov_map.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
    v["ranges"] = da.leave_ranges(year, month, matrix, 1, v["eom"])
    v["by_id"] = {r["id"]: r for r in v["recruits"]}
    v["sheet_matrix"], v["sheet_leaves"] = docx_recruits.month_sheets(year, month)
    v["missing"] = da.days_without_journal(year, month, rd or v["eom"])
    v["info"] = info
    # الصحة: كل من لم يُعمل له كشف طبي دوري هذا الشهر — حتى لو إجازة، لحين يومه
    done = db_health.month_checkup_ids(year, month)
    v["no_checkup"] = [r for r in v["recruits"] if r["id"] not in done]
    return render_template("recruits_stats.html", **v)


@recruits_bp.route("/stats/read")
@login_required
def stats_read():
    """تعليم إشعار كمقروء ثم فتحه — next لازم يكون رابط داخلي يبدأ بـ /."""
    k = (request.args.get("k") or "").strip()
    next_url = request.args.get("next") or "/recruits?tab=stats"
    if not (next_url.startswith("/") and "://" not in next_url):
        next_url = "/recruits?tab=stats"          # next خارجي = مرفوض
    if k and len(k) == 16:
        notifications.mark_read(__import__("flask").g.user["id"], [k])
    return redirect(next_url)


@recruits_bp.route("/stats/read-all", methods=["POST"])
@login_required
def stats_read_all():
    uid = __import__("flask").g.user["id"]
    _, token = current_session()
    groups = notifications.build_groups(uid, token or "")
    notifications.mark_read(uid, [it["key"] for g in groups for it in g["entries"]])
    return _rb(ok="تم تعليم كل الإشعارات الحالية كمقروءة", tab="stats")


# ======================================================================
# الإجازة المجمّعة من اليومية العامة (قرار ١٢/١٠):
# اختيار من جدول اليومية + نزول حالا (النهارده) أو بكرة + الأوقات
# في اليومية + التصريح (فردي/مجمّع) + فتح شاشة الطباعة
# ======================================================================
@recruits_bp.route("/send-leaves", methods=["POST"])
@login_required
def send_leaves():
    year, month = _ctx()
    rids = [x for x in (arnum.parse_int(v) for v in request.form.getlist("rid")) if x]
    start = request.form.get("start") or "today"
    t_present = (request.form.get("t_present") or "").strip()
    t_left = (request.form.get("t_left") or "").strip()
    info = _today_info(year, month, 1)
    real_day = info["real_day"] or 1
    eom = egtime.days_in_month(year, month)
    f = real_day if start == "today" else real_day + 1
    # «حتى يوم» اختياري: سيبتها فاضية = إجازة يوم واحد (نفس يوم النزول)
    t = arnum.parse_int(request.form.get("to")) or f
    if not rids:
        return _rb(err="حدد واحد على الأقل من المجندين (مربع الاختيار في جدول اليومية)", tab="journal", day=real_day)
    if not t or not (f <= t <= eom):
        return _rb(err="حدد «حتى يوم» صحيح (من يوم {} لآخر الشهر)".format(arnum.to_arabic_indic(f)),
                   tab="journal", day=real_day)
    by_id = {r["id"]: r for r in dr.list_recruits(year, month)}
    chosen = [by_id[i] for i in rids if i in by_id]
    if not chosen:
        return _rb(err="لم يُعرف أي من المجندين المختارين", tab="journal", day=real_day)
    matrix = da.month_matrix(year, month)
    bad = [c["name"] for c in chosen
           if any(matrix.get(c["id"], {}).get(d) == "إجازة" for d in range(f, t + 1))]
    if bad:
        return _rb(err="هؤلاء في إجازة بالفعل جوا المدة: {} — شيلهم من الاختيار".format("، ".join(bad)),
                   tab="journal", day=f)
    locked = _locked_days(year, month) & set(range(f, t + 1))
    if locked:
        return _rb(err="يومية يوم {} مثبتة ومقفولة — افتحها الأول («تعديل رغم التثبيت»)".format(
            arnum.to_arabic_indic(min(locked))), tab="journal", day=min(locked))
    # «حضروا لحد الساعة … ونزلوا الساعة …» — ليوم البداية لو النزول النهارده
    head_note = ""
    if f == real_day:
        if t_present and t_left:
            head_note = "حضروا لحد الساعة {} ونزلوا الإجازة الساعة {}".format(t_present, t_left)
        elif t_left:
            head_note = "نزلوا الإجازة الساعة {}".format(t_left)
    # نزول «بكرة» (قرار ١٤/١٠): التصريح يتعمل حالًا والتسجيل مُرجأ لضغطة واحدة
    # من بانر اليومية («سجّلهم في اليومية») — عشان الترحيل التلقائي لباقي المجندين
    # ليوم بكرة يشتغل عادي ما دام اليوم لسه فاضي.
    if start == "today":
        for c in chosen:
            if f < t:
                da.set_range(year, month, c["id"], "إجازة", f + 1, t)
            da.set_range(year, month, c["id"], "إجازة", f, f, head_note)
    _after_attendance_change(year, month)
    if len(chosen) >= 2:
        docx_recruits.build_joint_leave_permit(chosen, f, t, year, month)
    else:
        docx_recruits.build_leave_permit(chosen[0], f, t, year, month)
    da.record_leave_permits(year, month, [c["id"] for c in chosen], f, t)
    _, token = current_session()
    kw = {"from": f, "to": t, "year": year, "month": month, "sid": token}
    if len(chosen) >= 2:
        return redirect(url_for("recruits.print_doc", what="permit",
                                rids=",".join(str(c["id"]) for c in chosen), **kw))
    return redirect(url_for("recruits.print_doc", what="permit",
                            rid=chosen[0]["id"], **kw))


# ======================================================================
# قطع الإجازة (قرار ١٢/١٠):
# «فورا» → الأيام الجاية تصبح حضور + اليومية بتفتح وأنت بتكتب الساعة
# «غدا» → معلق، اليومية بتذكرك بكرة وزرار (حاضر/مستشفى)
# ======================================================================
@recruits_bp.route("/leaves/cut", methods=["POST"])
@login_required
def leaves_cut():
    year, month = _ctx()
    rid = arnum.parse_int(request.form.get("rid"))
    f = arnum.parse_int(request.form.get("from"))
    t = arnum.parse_int(request.form.get("to"))
    mode = request.form.get("mode")
    r = dr.get_recruit(year, month, rid) if rid else None
    info = _today_info(year, month, 1)
    real_day = info["real_day"] or 1
    eom = egtime.days_in_month(year, month)
    if not r or not f or not t or mode not in ("now", "tomorrow") or not (f <= t <= eom):
        return _rb(err="طلب غير صالح", tab="leaves")
    if f > real_day:
        return _rb(err="الإجازة لسه ما بدأتش — استخدم «إلغاء الإجازة»", tab="leaves")
    matrix = da.month_matrix(year, month)
    if not all(matrix.get(rid, {}).get(d) == "إجازة" for d in range(f, t + 1)):
        return _rb(err="الإجازة دي مش مسجلة «إجازة» كامل المدة في اليومية — أكمل تسجيلها الأول",
                   tab="leaves")
    if mode == "now":
        fut = list(range(real_day + 1, t + 1))
        locked = _locked_days(year, month) & set(fut)
        if locked:
            return _rb(err="يومية يوم {} مثبتة ومقفولة — افتحها الأول عشان أقطع الإجازة".format(
                arnum.to_arabic_indic(min(locked))), tab="leaves")
        if fut:
            da.set_range(year, month, rid, "حضور", fut[0], fut[-1])
        da.record_leave_cut(year, month, rid, f, t, real_day, "now")
        _after_attendance_change(year, month)
        return _rb(ok="اتقطعت إجازة {} — يومية النهارده اتفتحت: حط «حضور» واكتب الساعة "
                      "اللي رجع فيها، ثم ثبّت اليومية".format(r["name"]),
                   tab="journal", day=real_day)
    # mode == "tomorrow"
    if real_day + 1 > eom:
        return _rb(err="آخر يوم في الشهر — مفيش «غدًا»", tab="leaves")
    da.record_leave_cut(year, month, rid, f, t, real_day + 1, "tomorrow")
    return _rb(ok="اتسجل: إجازة {} هتقطع بكرة (يوم {}) — اليومية هتذكرك يومها "
                  "بزرارين: «حاضر في اليومية» / «حطه في المستشفى»".format(
                      r["name"], arnum.to_arabic_indic(real_day + 1)),
               tab="leaves")


@recruits_bp.route("/leaves/cut-apply", methods=["POST"])
@login_required
def leaves_cut_apply():
    """زرارين بنر اليومية: «حاضر في اليومية» (+ ساعة الرجوع) أو «حطه في المستشفى»."""
    year, month = _ctx()
    cut_id = arnum.parse_int(request.form.get("cut_id"))
    action = request.form.get("action")
    ret_time = (request.form.get("ret_time") or "").strip()
    if action not in ("present", "hospital") or not cut_id:
        return _rb(err="طلب غير صالح", tab="journal")
    cut = da.get_leave_cut(year, month, cut_id)
    if not cut:
        return _rb(err="القطع ده مش موجود", tab="journal")
    eff, to = cut["eff_day"], cut["period_to"]
    meta = da.get_meta(year, month, eff)
    if meta["locked"]:
        return _rb(err="يومية يوم {} مثبتة ومقفولة — افتحها الأول («تعديل رغم التثبيت»)".format(
            arnum.to_arabic_indic(eff)), tab="journal", day=eff)
    if action == "present":
        note = "رجع من الإجازة الساعة {}".format(ret_time) if ret_time else ""
        if eff < to:
            da.set_range(year, month, cut["recruit_id"], "حضور", eff + 1, to)
        da.set_range(year, month, cut["recruit_id"], "حضور", eff, eff, note)
        da.set_cut_applied(year, month, cut_id)
        _after_attendance_change(year, month)
        return _rb(ok="اتحط «حضور» من يوم {}{} — ثبّت اليومية لو لسه".format(
            arnum.to_arabic_indic(eff),
            " (رجع الساعة {})".format(ret_time) if ret_time else ""),
            tab="journal", day=eff)
    da.set_range(year, month, cut["recruit_id"], "مستشفى", eff, to)
    da.set_cut_applied(year, month, cut_id, hospital=1)
    _after_attendance_change(year, month)
    return _rb(ok="اتحط «مستشفى» من يوم {} — املأ الحالة الصحية والملاحظات من تاب "
                  "«أخرى» (لوحة المستشفى)".format(arnum.to_arabic_indic(eff)),
               tab="other")


@recruits_bp.route("/leaves/cancel", methods=["POST"])
@login_required
def leaves_cancel():
    """إلغاء إجازة «لم تبدأ» — الأيام بتبقى مفتوحة في اليومية."""
    year, month = _ctx()
    rid = arnum.parse_int(request.form.get("rid"))
    f = arnum.parse_int(request.form.get("from"))
    t = arnum.parse_int(request.form.get("to"))
    r = dr.get_recruit(year, month, rid) if rid else None
    info = _today_info(year, month, 1)
    real_day = info["real_day"] or 1
    eom = egtime.days_in_month(year, month)
    if not r or not f or not t or not (f <= t <= eom) or f <= real_day:
        return _rb(err="الإلغاء لإجازة «لم تبدأ» بس", tab="leaves")
    matrix = da.month_matrix(year, month)
    if not all(matrix.get(rid, {}).get(d) == "إجازة" for d in range(f, t + 1)):
        return _rb(err="الإجازة دي مش مسجلة «إجازة» كامل المدة في اليومية", tab="leaves")
    locked = sorted(_locked_days(year, month) & set(range(f, t + 1)))
    for d in locked:
        da.unlock_day(year, month, d)
    da.delete_status_range(year, month, rid, f, t, "إجازة")
    da.delete_leave_permit(year, month, rid, f, t)
    _after_attendance_change(year, month)
    msg = "اتلغت إجازة {} (من يوم {} لـ {}) والأيام دي بقيت مفتوحة في اليومية".format(
        r["name"], arnum.to_arabic_indic(f), arnum.to_arabic_indic(t))
    if locked:
        msg += " — فُتحت الأيام المثبتة: {}".format(
            "، ".join(arnum.to_arabic_indic(str(d)) for d in locked))
    return _rb(ok=msg, tab="leaves")


@recruits_bp.route("/other/save-hospital", methods=["POST"])
@login_required
def other_save_hospital():
    """حفظ الحالة الصحية + الملاحظة لكل يوم مستشفى (يوم بيوم)."""
    year, month = _ctx()
    rids = [arnum.parse_int(x) for x in request.form.getlist("hc_rid")]
    days = [arnum.parse_int(x) for x in request.form.getlist("hc_day")]
    conds = request.form.getlist("hc_cond")
    notes = request.form.getlist("hc_note")
    locked = _locked_days(year, month)
    saved, blocked = 0, set()
    for i, rid in enumerate(rids):
        d = days[i] if i < len(days) else 0
        if not (rid and d):
            continue
        if d in locked:
            blocked.add(d)
            continue
        da.set_hospital_day(year, month, d, rid,
                            (conds[i] if i < len(conds) else "").strip(),
                            (notes[i] if i < len(notes) else "").strip())
        saved += 1
    if saved and not blocked:
        return _rb(ok="اتحفظت الحالة الصحية والملاحظات ({} يومًا)".format(
            arnum.to_arabic_indic(saved)), tab="other")
    if saved:
        return _rb(ok="اتحفظ ({} يومًا) — الأيام دي مثبتة ومقفولة: {} (افتحهم الأول)".format(
            arnum.to_arabic_indic(saved),
            "، ".join(arnum.to_arabic_indic(str(d)) for d in sorted(blocked))), tab="other")
    return _rb(err="مفيش أيام اتحفظت — الأيام المثبتة: {} (افتحهم الأول)".format(
        "، ".join(arnum.to_arabic_indic(str(d)) for d in sorted(blocked)) or "—"),
        tab="other")


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
        f = arnum.parse_int(request.args.get("from"))
        t = arnum.parse_int(request.args.get("to"))
        joint_ids = [x for x in (arnum.parse_int(x) for x in
                                 (request.args.get("rids") or "").split(",")) if x]
        if len(joint_ids) >= 2 and f and t and 1 <= f <= t <= egtime.days_in_month(year, month):
            # تصريح إجازة مجمّع — أكثر من مجند بنفس المدة
            chosen = [r for r in (dr.get_recruit(year, month, i) for i in joint_ids) if r]
            if len(chosen) < 2:
                abort(404)
            path = docx_recruits.build_joint_leave_permit(chosen, f, t, year, month)
            da.record_leave_permits(year, month, [c["id"] for c in chosen], f, t)
            v["permit_recruits"] = chosen
            v["from_day"], v["to_day"] = f, t
            v["title"] = "تصريح إجازة مجمّع"
            v["docx_name"] = path.name
        else:
            rid = arnum.parse_int(request.args.get("rid"))
            r = dr.get_recruit(*_ctx(), rid)
            if not r or not f or not t or not 1 <= f <= t <= egtime.days_in_month(year, month):
                abort(404)
            v["recruit"] = r
            v["from_day"], v["to_day"] = f, t
            v["title"] = "تصريح إجازة"
            path = docx_recruits.build_leave_permit(r, f, t, year, month)
            da.record_leave_permits(year, month, [rid], f, t)
            v["docx_name"] = path.name
    elif what == "day":
        day = arnum.parse_int(request.args.get("day")) or info["real_day"] or 1
        dmap = da.get_day_map(year, month, day)
        v["day"] = day
        v["rows"] = [(by_id[rid], st) for rid, st in dmap.items() if rid in by_id]
        v["counts"] = {st: sum(1 for x in dmap.values() if x["status"] == st) for st in da.STATUSES}
        if not 1 <= day <= egtime.days_in_month(year, month):
            abort(400)
        v["title"] = "كشف اليومية العامة — " + dates.period_date(year, month, day)
    elif what == "month-leaves":
        v["ranges"] = da.leave_ranges(year, month, matrix, 1, v["eom"])
        v["by_id"] = by_id
        v["title"] = "كشف الإجازات — شهر {} {}".format(MONTH_NAMES[month - 1], arnum.to_arabic_indic(year))
    elif what == "certs":
        v["rows"] = [(r, dr.cert_state(r, today)) for r in v["recruits"]]
        v["title"] = "كشف موقف الشهادات الصحية"
    elif what == "recruit":
        rid = arnum.parse_int(request.args.get("rid"))
        r = dr.get_recruit(*_ctx(), rid)
        if not r:
            abort(404)
        v["recruit"] = r
        v["rows"] = sorted(matrix.get(rid, {}).items())
        v["title"] = "كشف حالة المجند / {} — شهر {} {}".format(r["name"], MONTH_NAMES[month - 1], arnum.to_arabic_indic(year))
    else:
        abort(404)
    v["month_name"] = MONTH_NAMES[month - 1]
    return render_template("recruits_print.html", **v)


@recruits_bp.route("/docx/<name>")
@login_required
def docx_download(name):
    if not re.match(r"^(كشف-(الحالات|الإجازات)-\d{4}-\d{2}|تصريح-.*-\d{4}-\d{2}-\d{2})\.docx$", name):
        abort(404)
    year, month = _ctx()
    if name in (f"كشف-الحالات-{year}-{month:02d}.docx", f"كشف-الإجازات-{year}-{month:02d}.docx"):
        try:
            docx_recruits.ensure_month_sheets(year, month)
        except OSError:
            return _rb(err="أغلق ملف الوورد المفتوح ثم أعد التنزيل لتحديث تنسيق التواريخ", tab="stats")
    path = next((p for p in (docx_recruits.docs_dir(year, month) / name,
                             docx_recruits.leaves_dir(year, month) / name,
                             docx_recruits.leaves_dir(year, month) / "تصاريح" / name)
                 if p.exists()), None)
    if path is None:
        abort(404)
    return attachment(path, "recruits-report.docx")


@recruits_bp.route("/docx/rebuild", methods=["POST"])
@login_required
def docx_rebuild():
    year, month = _ctx()
    p1, p2 = docx_recruits.rebuild_month(year, month)
    return _rb(ok="أُعيد بناء كشفي الوورد: «{}» + «{}»".format(p1.name, p2.name), tab="stats")
