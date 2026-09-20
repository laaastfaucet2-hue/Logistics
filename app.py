# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""منظومة مخازن التعيينات - ملف التشغيل الرئيسي."""
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort
from werkzeug.security import check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps
from datetime import datetime
from urllib.parse import quote

import database as db
import storage
import arabic_numbers as arnum
from config import (MONTH_NAMES, SECTIONS, SECTION_MAP, month_folder, section_folder,
                    EXTRA_PAGES, EXTRA_MAP)

app = Flask(__name__)
app.secret_key = "rations-warehouse-2026-secret-key"

# إعدادات الجلسة عشان تشتغل داخل المعاينة (iframe) على HTTPS
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    PREFERRED_URL_SCHEME="https",
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

db.init_db()
storage.ensure_initialized(datetime.now().year)
storage.sync_section_folders()


# تحويل الأرقام العربية/الفارسية إلى إنجليزية + إزالة المسافات الزيادة
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize(text):
    return (text or "").translate(AR_DIGITS).strip()


# أدوات المصادقة والسياق منقولة إلى auth_core حتى تستخدمها الـBlueprints
from auth_core import current_session, login_required, current_context  # noqa: E402


@app.context_processor
def inject_auth():
    user = getattr(g, "user", None) or session.get("user")
    sid = getattr(g, "sid", None) or request.args.get("sid") or ""
    ctx = {"current_user": user, "sid": sid}
    if user:
        year, month = current_context(user["id"])
        ctx.update(
            sections=SECTIONS,
            extra_pages=EXTRA_PAGES,
            years=storage.list_years(),
            months=list(enumerate(MONTH_NAMES, start=1)),
            ctx_year=year,
            ctx_month=month,
        )
    return ctx


@app.template_filter("fmt")
def fmt_number(value):
    try:
        n = float(value)
        return f"{int(n):,}" if n == int(n) else f"{n:,.1f}"
    except (TypeError, ValueError):
        return value


@app.template_filter("aindic")
def aindic_number(value):
    """عرض الرقم بالأرقام العربية المشرقية: 2026 → ٢٠٢٦"""
    return arnum.to_arabic_indic(value)


def _back(ok=None, err=None):
    """يرجع للصفحة السابقة مع الحفاظ على التوكن + رسالة نجاح/خطأ اختيارية."""
    target = request.args.get("next", "")
    if not target.startswith("/"):
        target = url_for("dashboard")
    target = target.split("?")[0]
    params = []
    _, token = current_session()
    if token:
        params.append("sid=" + quote(token))
    if ok:
        params.append("ok=" + quote(ok))
    if err:
        params.append("err=" + quote(err))
    if params:
        target += "?" + "&".join(params)
    return redirect(target)


# ======================================================================
# الدخول والخروج
# ======================================================================
@app.route("/")
def index():
    user, token = current_session()
    if user:
        if token:
            return redirect(url_for("dashboard", sid=token))
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    user, token = current_session()
    if user:
        if token:
            return redirect(url_for("dashboard", sid=token))
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = normalize(request.form.get("username", "")).lower()
        password = normalize(request.form.get("password", ""))
        user = db.get_user(username)
        if user and check_password_hash(user["password"], password):
            session["user"] = {
                "id": user["id"],
                "username": user["username"],
                "full_name": user["full_name"],
                "role": user["role"],
            }
            remember = request.form.get("remember")
            token = db.create_session(user["id"], hours=(24 * 30 if remember else 12))
            flash(f"مرحباً {user['full_name']} 👋", "success")
            return redirect(url_for("dashboard", sid=token))
        flash("اسم المستخدم أو كلمة المرور غير صحيحة", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    token = request.args.get("sid") or request.form.get("sid")
    if token:
        db.delete_session(token)
    session.pop("user", None)
    flash("تم تسجيل الخروج بنجاح", "success")
    return redirect(url_for("login"))


# ======================================================================
# لوحة التحكم
# ======================================================================
@app.route("/dashboard")
@login_required
def dashboard():
    stats = db.get_dashboard_stats()
    return render_template("dashboard.html", stats=stats)


# ======================================================================
# صفحات الأقسام — المبنية منها لها صفحاتها الخاصة، والباقي «قيد التطوير»
# ======================================================================
RATION_SECTION_REDIRECTS = {
    "tamween_rations": "tamween",
    "contractor_rations": "contractor",
}


@app.route("/sections/<key>")
@login_required
def section_page(key):
    if key in RATION_SECTION_REDIRECTS:
        params = {"sid": request.args["sid"]} if request.args.get("sid") else {}
        return redirect(url_for("rations.page",
                                section=RATION_SECTION_REDIRECTS[key], **params))
    section = SECTION_MAP.get(key) or EXTRA_MAP.get(key)
    if not section:
        abort(404)
    year, month = current_context(g.user["id"])
    if SECTION_MAP.get(key):
        index = SECTIONS.index(section) + 1
        folder_path = "database/{}/{}/{}".format(
            year, month_folder(month), section_folder(index, section["name"]))
    else:
        folder_path = "database/الدباجة/" if key == "letterhead" else None
    return render_template(
        "section.html", section=section,
        month_name=MONTH_NAMES[month - 1],
        folder_path=folder_path,
    )


# ======================================================================
# إدارة السياق والسنوات (من شريط الأدوات العلوي)
# ======================================================================
@app.route("/context/set")
@login_required
def set_context():
    year = arnum.parse_int(request.args.get("year"))
    month = arnum.parse_int(request.args.get("month"))
    if year not in storage.list_years() or month is None or not (1 <= month <= 12):
        return _back(err="السنة أو الشهر المحدد غير صالح")
    db.set_user_context(g.user["id"], year, month)
    return _back()


@app.route("/years/create")
@login_required
def year_create():
    year = arnum.parse_int(request.args.get("year"))
    if year is None or not (2000 <= year <= 2100):
        return _back(err="قيمة السنة غير صالحة — مثال صحيح: ٢٠٢٧")
    if not storage.create_year(year):
        return _back(err=f"سنة {arnum.to_arabic_indic(year)} موجودة بالفعل")
    # انتقل إليها مباشرة مع الاحتفاظ بالشهر الحالي
    ctx = db.get_user_context(g.user["id"])
    keep_month = ctx["month"] if ctx else datetime.now().month
    db.set_user_context(g.user["id"], year, keep_month)
    return _back(ok=f"تم إنشاء سنة {arnum.to_arabic_indic(year)} ومجلداتها (12 شهرًا × 12 قسمًا) بنجاح")


@app.route("/years/delete")
@login_required
def year_delete():
    year = arnum.parse_int(request.args.get("year"))
    years = storage.list_years()
    if year is None or year not in years:
        return _back(err="السنة غير موجودة على النظام")
    if len(years) <= 1:
        return _back(err="لا يمكن حذف آخر سنة — أنشئ سنة جديدة أولًا")
    storage.delete_year(year)
    # أي مستخدم كان واقفًا على السنة المحذوفة ينتقل لأحدث سنة متبقية
    db.reset_context_year(year, storage.list_years()[0])
    return _back(ok=f"تم حذف سنة {arnum.to_arabic_indic(year)} وكل محتوياتها نهائيًا")


# صفحات الخطوات الجاية (عناوين مؤقتة)
PLACEHOLDERS = {
    "items": ("الأصناف", "إضافة وتعديل أصناف التعيينات والوحدات وحدود الطلب — الخطوة 2️⃣"),
    "warehouses": ("المخازن", "إدارة المخازن وأمنائها ومواقعها — الخطوة 2️⃣"),
    "entities": ("الجهات المستفيدة", "الوحدات والإدارات التي تُصرف لها التعيينات — الخطوة 2️⃣"),
    "supply": ("التوريد", "تسجيل توريدات الموردين واستلام الأصناف — الخطوة 3️⃣"),
    "disbursement": ("الصرف", "أوامر صرف التعيينات للجهات — الخطوة 3️⃣"),
    "reports": ("التقارير", "كشوف الحركة والأرصدة والطباعة — الخطوة 4️⃣"),
    "users": ("المستخدمون", "الحسابات والصلاحيات — الخطوة 5️⃣"),
}


@app.route("/<page>")
@login_required
def placeholder(page):
    if page not in PLACEHOLDERS:
        return redirect(url_for("dashboard"))
    title, desc = PLACEHOLDERS[page]
    return render_template("placeholder.html", title=title, desc=desc, active=page)


# تسجيل Blueprint صفحات المقررات — في نهاية الملف حتى تكتمل تعريفات app
from routes.rations import rations_bp  # noqa: E402
app.register_blueprint(rations_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
