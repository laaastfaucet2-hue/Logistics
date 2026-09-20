"""منظومة مخازن التعيينات - ملف التشغيل الرئيسي."""
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps
import database as db

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


# تحويل الأرقام العربية/الفارسية إلى إنجليزية + إزالة المسافات الزيادة
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize(text):
    return (text or "").translate(AR_DIGITS).strip()


def current_session():
    """يرجع (المستخدم، التوكن) — من الكوكي أو من sid في الرابط/الفورم."""
    if "user" in session:
        return session["user"], request.args.get("sid") or None
    token = request.args.get("sid") or request.form.get("sid")
    if token:
        user = db.get_session_user(token)
        if user:
            return (
                {"id": user["id"], "username": user["username"],
                 "full_name": user["full_name"], "role": user["role"]},
                token,
            )
    return None, None


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user, token = current_session()
        if not user:
            # لو كان معاه توكن لكنه منتهي/ملغي → علّم الصفحة عشان تمسح المحفوظ ومتعملش حلقة تحويل
            if request.args.get("sid") or request.form.get("sid"):
                return redirect(url_for("login", expired=1))
            flash("من فضلك سجل الدخول أولاً", "error")
            return redirect(url_for("login"))
        g.user = user
        g.sid = token
        return view(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_auth():
    user = getattr(g, "user", None) or session.get("user")
    sid = getattr(g, "sid", None) or request.args.get("sid") or ""
    return {"current_user": user, "sid": sid}


@app.template_filter("fmt")
def fmt_number(value):
    try:
        n = float(value)
        return f"{int(n):,}" if n == int(n) else f"{n:,.1f}"
    except (TypeError, ValueError):
        return value


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


@app.route("/dashboard")
@login_required
def dashboard():
    stats = db.get_dashboard_stats()
    return render_template("dashboard.html", stats=stats)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
