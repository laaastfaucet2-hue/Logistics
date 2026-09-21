# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""محرك إشعارات الجرس 🔔 — العناصر «الحارة» تُحسب بتاريخ القاهرة الحقيقي دائمًا:
نسيان اليومية · إجازات مرتقبة · شهادات صحية · غياب متواصل · خدمة تنتهي قريبًا.
"""
import database as db
import db_attendance as da
import db_recruits as dr
import egtime


def _sid_qs(token):
    return ("?sid=" + token) if token else ""


def build_groups(user_id, sid=""):
    """يرجع مجموعات الجرس: [{key, icon, title, level, items:[{text, href}]}]."""
    try:
        today = egtime.today()
        y, m, d = today.year, today.month, today.day
        recruits = {r["id"]: r for r in dr.list_recruits()}
        matrix = da.month_matrix(y, m)
        q = _sid_qs(sid)
        groups = {"journal": [], "leaves": [], "certs": [], "absents": [], "service": []}

        # ١) يومية اليوم/الأمس (حقيقية دائمًا)
        missing = da.days_without_journal(y, m, d)
        if d in missing:
            groups["journal"].append({
                "text": "لم تقم بعمل يومية اليوم حتى الآن",
                "href": "/recruits?tab=journal&day={}{}".format(d, "&sid=" + sid if sid else "")})
        if d > 1 and (d - 1) in missing:
            groups["journal"].append({
                "text": "يومية أمس (يوم {}) لم تُثبَّت — تُرحَّل تلقائيًا عند فتح اليوم".format(d - 1),
                "href": "/recruits?tab=journal&day={}".format(d - 1) + q.replace("?", "&")})
        earlier = [x for x in missing if x < d - 1][:3]
        for x in earlier:
            groups["journal"].append({
                "text": "يومية يوم {} غير موجودة".format(x),
                "href": "/recruits?tab=journal&day={}".format(x) + q.replace("?", "&")})

        # ٢) إجازات مرتقبة (تبدأ خلال يومين)
        ranges = da.leave_ranges(y, m, matrix, from_day=d + 1, to_day=min(d + 2, 31))
        for rid, rs in ranges.items():
            r = recruits.get(rid)
            if not r:
                continue
            for f, t in rs:
                when = "غدًا" if f - d == 1 else "بعد غد"
                groups["leaves"].append({
                    "text": "🛎️ إجازة {} تبدأ {} (يوم {})".format(r["name"], when, f),
                    "href": "/recruits?tab=leaves" + q})

        # ٣) الشهادات الصحية
        for r in recruits.values():
            st = dr.cert_state(r, today)
            if st == "expired":
                groups["certs"].append({
                    "text": "🔴 الشهادة الصحية لـ {} منتهية!".format(r["name"]),
                    "href": "/recruits?tab=registry&edit={}{}".format(r["id"], q.replace("?", "&"))})
            elif st == "soon":
                try:
                    ey, em, ed = (int(x) for x in r["cert_expiry"].split("-"))
                    left = (egtime.date(ey, em, ed) - today).days
                except (ValueError, AttributeError):
                    left = 30
                groups["certs"].append({
                    "text": "🟠 شهادة {} تنتهي خلال {} يومًا".format(r["name"], left),
                    "href": "/recruits?tab=registry&edit={}{}".format(r["id"], q.replace("?", "&"))})

        # ٤) غياب متواصل ≥ ٣ أيام
        streaks = da.absence_streak(y, m, matrix, d - 1 if d > 1 else d)
        for rid, streak in streaks.items():
            r = recruits.get(rid)
            if streak >= 3 and r:
                groups["absents"].append({
                    "text": "🚫 {} غائب منذ {} أيام متواصلة".format(r["name"], streak),
                    "href": "/recruits?tab=absent" + q})

        # ٥) خدمة تنتهي خلال ٦٠ يومًا
        for r in recruits.values():
            dd = dr.days_to_discharge(r, today)
            if dd is not None and 0 <= dd <= 60:
                groups["service"].append({
                    "text": "⏳ خدمة {} تنتهي خلال {} يومًا".format(r["name"], dd),
                    "href": "/recruits?tab=registry" + q})

        meta = {
            "journal": ("📝", "اليومية العامة", "danger"),
            "leaves": ("🏖️", "إجازات مرتقبة", "warn"),
            "certs": ("📋", "الشهادات الصحية", "warn"),
            "absents": ("🚫", "غياب متواصل", "danger"),
            "service": ("⏳", "انتهاء الخدمة", "info"),
        }
        out = []
        for key, (icon, title, level) in meta.items():
            if groups[key]:
                out.append({"key": key, "icon": icon, "title": title,
                            "level": level, "entries": groups[key]})
        return out
    except Exception:  # noqa: BLE001 — الجرس لا يسقط أي صفحة أبدًا
        return []


def summarize(user_id, sid=""):
    groups = build_groups(user_id, sid)
    return groups, sum(len(gr["entries"]) for gr in groups)
