# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""أدوات المصادقة والسياق — منفصلة حتى تستخدمها app وأي Blueprint بدون استيراد دائري."""
from functools import wraps
from datetime import datetime

from flask import session, request, redirect, url_for, flash, g, abort
from core import arabic_numbers as arnum

from data_access import database as db
from data_access import storage


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


def current_context(user_id):
    """يرجع (year, month) الصحيحين لهذا المستخدم، ويصحّح أي قيمة باطلة."""
    years = storage.list_years()
    default_year = years[0] if years else datetime.now().year
    explicit_year = arnum.parse_int(request.values.get("year"))
    explicit_month = arnum.parse_int(request.values.get("month"))
    if request.values.get("year") is not None or request.values.get("month") is not None:
        if explicit_year not in years or explicit_month is None or not 1 <= explicit_month <= 12:
            abort(400, "السنة أو الشهر غير صالح")
        return explicit_year, explicit_month
    ctx = db.get_user_context(user_id)
    year = ctx["year"] if ctx else default_year
    month = ctx["month"] if ctx else datetime.now().month
    if year not in years:
        year = default_year
    month = max(1, min(12, int(month)))
    if not ctx or ctx["year"] != year or ctx["month"] != month:
        db.set_user_context(user_id, year, month)
    return year, month
