"""منظومة مخازن التعيينات - ملف التشغيل الرئيسي."""
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from functools import wraps
import database as db

app = Flask(__name__)
app.secret_key = "rations-warehouse-2026-secret-key"

db.init_db()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            flash("من فضلك سجل الدخول أولاً", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_user():
    return {"current_user": session.get("user")}


@app.template_filter("fmt")
def fmt_number(value):
    try:
        n = float(value)
        return f"{int(n):,}" if n == int(n) else f"{n:,.1f}"
    except (TypeError, ValueError):
        return value


@app.route("/")
def index():
    return redirect(url_for("dashboard" if "user" in session else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.get_user(username)
        if user and check_password_hash(user["password"], password):
            session["user"] = {
                "id": user["id"],
                "username": user["username"],
                "full_name": user["full_name"],
                "role": user["role"],
            }
            flash(f"مرحباً {user['full_name']} 👋", "success")
            return redirect(url_for("dashboard"))
        flash("اسم المستخدم أو كلمة المرور غير صحيحة", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
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
