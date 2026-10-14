# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""محرك إشعارات الجرس 🔔 — العناصر «الحارة» تُحسب بتاريخ القاهرة الحقيقي دائمًا:
نسيان اليومية · الإجازات (قبلها بيوم / يومها / قبل الرجوع بيوم) ·
مأمورية/مستشفى/أخرى (قبلها بيوم ويومها) · شهادة صحية (قبلها بأسبوعين) ·
غياب متواصل · خدمة تنتهي قريبًا · لم يُكشفوا (آخر الشهر).

مصدر واحد للحقائق: day_events() — يستخدمه الجرس وبنرات اليومية وكشف الإجازات المرتقب.
"""
import hashlib
import json

from data_access import database as db, storage
from data_access import db_attendance as da
from data_access import db_punishments as dpk
from data_access import db_recruits as dr
from data_access import db_health
from core import egtime, dates, arabic_numbers as arnum

EVENT_STATUSES = ("مأمورية", "مستشفى", "أخرى")
EVENT_ICONS = {"مأمورية": "🧭", "مستشفى": "🏥", "أخرى": "➕"}


# ==================== مقروء/غير مقروء (لكل مستخدم) ====================
def entry_key(group, text):
    """مفتاح ثابت لإشعار (المجموعة + النص) — النص ثابت ما دامت الحالة شغالة."""
    return hashlib.sha1((group + "|" + text).encode("utf-8")).hexdigest()[:16]


def read_keys(user_id):
    try:
        return set(json.loads(db.get_setting("notif_read_%d" % user_id, "[]")))
    except ValueError:
        return set()


def mark_read(user_id, keys):
    cur = read_keys(user_id)
    cur.update(k for k in keys if k)
    db.set_setting("notif_read_%d" % user_id, json.dumps(sorted(cur)))


def _sid_qs(token):
    return ("?sid=" + token) if token else ""


def and_join(names):
    """دمج أسماء بالعربي: «أحمد» / «محمد وأحمد» / «محمد، أحمد، وعلي»."""
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return "، ".join(names[:-1]) + " و" + names[-1]


def day_events(year, month, matrix, day, by_id=None):
    """كل أحداث يوم محدد من الشهر — مصدر الحقيقة الوحيد للجرس وبنرات اليومية:

    - leave_start:  إجازة تبدأ اليوم (اليوم اللي لازم يتعمل فيه التصريح)
    - leave_return: آخر يوم إجازة اليوم (الرجوع غدًا)
    - status:       أحداث اليوم المفرد (مأمورية / مستشفى / أخرى)
    يرجع [{kind, status?, names, note?, return_day?}] مرتبة.
    """
    if by_id is None:
        by_id = {r["id"]: r for r in dr.list_recruits(year, month)}
    eom = egtime.days_in_month(year, month)
    if not (1 <= day <= eom):
        return []
    out = []
    ranges = da.leave_ranges(year, month, matrix, 1, eom)
    permits = da.month_leave_permits(year, month)
    starting, returning = [], []
    for rid, rs in ranges.items():
        if rid not in by_id:
            continue
        for f, t in rs:
            if f == day:
                starting.append((rid, f, t))
            # elif ممنوع: إجازة يوم واحد (٥–٥) حدث بداية وحدث رجوع بنفس اليوم
            if t == day and t + 1 <= eom:
                returning.append(rid)
    if starting:
        starting.sort(key=lambda x: by_id[x[0]]["name"])
        permitted = [(rid, f, t) for rid, f, t in starting
                     if (f, t) in permits.get(rid, [])]
        out.append({
            "kind": "leave_start",
            "names": [by_id[rid]["name"] for rid, _f, _t in starting],
            "permitted_names": [by_id[rid]["name"] for rid, _f, _t in permitted],
            "all_permitted": bool(starting) and len(permitted) == len(starting)})
    if returning:
        out.append({"kind": "leave_return", "return_day": day + 1,
                    "names": [by_id[rid]["name"] for rid in
                              sorted(returning, key=lambda i: by_id[i]["name"])]})
    # ── تصاريح إجازة صادرة لكن اليومية ما كتملتش (مرحلة ٣) ──
    p_start, p_gap, p_end = [], [], []
    for rid, rs in permits.items():
        if rid not in by_id:
            continue
        days = matrix.get(rid, {})
        for f, t in rs:
            if days.get(f) != "إجازة" and f == day:
                p_start.append(rid)          # الإجازة بتبدأ النهارده والتصريح متعمل — حطّهم في اليومية
            elif days.get(day) != "إجازة" and f < day <= t:
                p_gap.append(rid)            # التصريح صادر والمدة شغالة بس النهارده من غير «إجازة»
            elif days.get(t) != "إجازة" and t + 1 == day:
                p_end.append(rid)            # التصريح خلص أمس واليومية ما كتملتش — أكّد الحضور
    if p_start:
        out.append({"kind": "permit_start",
                    "names": [by_id[i]["name"] for i in sorted(p_start, key=lambda i: by_id[i]["name"])],
                    "ranges": {i: (f, t) for i, rs in permits.items() for f, t in rs
                               if i in p_start and f == day}})
    if p_gap:
        out.append({"kind": "permit_gap",
                    "names": [by_id[i]["name"] for i in sorted(p_gap, key=lambda i: by_id[i]["name"])],
                    "ranges": {i: next((f, t) for f, t in permits[i] if f < day <= t) for i in p_gap}})
    if p_end:
        out.append({"kind": "permit_end",
                    "names": [by_id[i]["name"] for i in sorted(p_end, key=lambda i: by_id[i]["name"])],
                    "ranges": {i: (day - 1, day - 1) for i in p_end}})
    ending_by_status = {}
    if day + 1 <= eom:
        for st in ("مأمورية", "مستشفى"):
            ending_by_status[st] = {rid for rid, days in matrix.items()
                                    if rid in by_id and days.get(day) == st
                                    and days.get(day + 1) != st}
    dmap = da.get_day_map(year, month, day)
    groups = {}
    for rid, info in dmap.items():
        if info["status"] in EVENT_STATUSES:
            # اللي حالته بتخلص النهارده ياخد بنر «بتخلص» بس — من غير تكرار
            if rid in ending_by_status.get(info["status"], ()):
                continue
            name = by_id[rid]["name"] if rid in by_id else str(rid)
            groups.setdefault(info["status"], []).append((name, info.get("note") or ""))
    for st in EVENT_STATUSES:
        if st in groups:
            items = sorted(groups[st], key=lambda x: x[0])
            out.append({"kind": "status", "status": st,
                        "names": [n for n, _n in items], "note": items[0][1]})
    # ── قطع إجازات: يسري اليوم (حدّد الحالة) / يسري بكرة (معلق) ──
    cuts = da.month_leave_cuts(year, month)
    for rid in sorted(cuts, key=lambda i: by_id[i]["name"] if i in by_id else ""):
        if rid not in by_id:
            continue
        for c in cuts[rid]:
            if c["eff_day"] == day:
                done_st = dmap.get(rid, {}).get("status")
                if c["applied"] and done_st in ("حضور", "مستشفى"):
                    continue  # اتطبّق وحالته اتسجلت — التنبيه بيتنسي
                out.append({"kind": "leave_cut", "names": [by_id[rid]["name"]], "cut": c})
            elif c["eff_day"] == day + 1 and not c["applied"]:
                out.append({"kind": "leave_cut_soon", "names": [by_id[rid]["name"]], "cut": c})
    # ── مأمورية/مستشفى بتخلص النهارده (نفس منطق رجوع الإجازة) ──
    for st in ("مأمورية", "مستشفى"):
        ending = ending_by_status.get(st)
        if ending:
            out.append({"kind": "status_end", "status": st, "names": [by_id[i]["name"] for i in sorted(ending, key=lambda i: by_id[i]["name"])]})
    # ── السجن/المحكمات/الجزاءات: مدد مشتقة من اليومية (توجيه ١٠/١٠) ──
    # كل يوم جوا المدة: تنبيه (يوم الدخول / يومي / آخر يوم) + «غدًا» قبل الحدث بيوم
    for pk, pmeta in dpk.KIND_META.items():
        spans = [s for s in dpk.month_spans(year, month, pk) if s[0] in by_id]
        covering = [(rid, f, t) for rid, f, t in spans
                    if f <= day and (t is None or day <= t)]
        if not covering:
            continue
        starts = {rid: (f, t) for rid, f, t in covering if f == day}
        ends = {rid: (f, t) for rid, f, t in covering if t == day}
        actives = {rid: (f, t) for rid, f, t in covering if f != day and t != day}
        for evkind, sub in (("pun_start", starts), ("pun_active", actives),
                            ("pun_end", ends)):
            if sub:
                out.append({"kind": evkind, "pk": pk,
                            "icon": pmeta["icon"], "noun": pmeta["noun"],
                            "names": [by_id[i]["name"] for i in
                                      sorted(sub, key=lambda i: by_id[i]["name"])],
                            "ranges": sub})
    return out


def _when_word(evday, today_day):
    if evday == today_day:
        return "اليوم"
    if evday == today_day + 1:
        return "غدًا"
    return "بعد غد"  # المندوح الوحيد في هذا المحرك (d+2)


def _event_entries(year, month, matrix, recruits, d, eom, q):
    """إدخالات الجرس لأحداث أيام (اليوم/غدًا/بعد غد) — مجمعة بالأسماء."""
    leaves, events = [], []
    for evday in (d, d + 1, d + 2):
        if not (1 <= evday <= eom):
            continue
        for ev in day_events(year, month, matrix, evday, recruits):
            if ev["kind"] == "leave_start":
                names = and_join(ev["names"])
                if evday == d:
                    # في يوم الإجازة نفسه ينبغي أن يكون التصريح قد أُعد أمس.
                    if ev["all_permitted"]:
                        leaves.append({
                            "text": "🏖️ {} في إجازة اليوم — التصريح مُعدّ ✓ — أكّد تسجيلهم في اليومية".format(names),
                            "href": "/recruits?tab=journal&day={}".format(d) + q.replace("?", "&")})
                    else:
                        done = "، ".join(ev["permitted_names"]) if ev["permitted_names"] else "—"
                        leaves.append({
                            "text": "🏖️ {} في إجازة اليوم — صدر التصريح لـ{} — أكّد التسجيل في اليومية".format(names, done),
                            "href": "/recruits?tab=journal&day={}".format(d) + q.replace("?", "&")})
                else:
                    # قبلها بيوم أو يومين: يُجهّز التصريح الآن.
                    permit_part = " والتصريح مُعدّ ✓" if ev["all_permitted"] else " — أنشئ التصريح اليوم"
                    leaves.append({
                        "text": "🛎️ {} {} إجازة {} ({}){}".format(
                            names, "يبدأ" if len(ev["names"]) == 1 else "تبدأ لهم",
                            _when_word(evday, d), dates.period_date(year, month, evday),
                            permit_part),
                        "href": "/recruits?tab=leaves" + q})
            elif ev["kind"] == "leave_return":
                leaves.append({
                    "text": "↩️ {} {} من الإجازة {} ({})".format(
                        and_join(ev["names"]),
                        "يعود" if len(ev["names"]) == 1 else "يعودون",
                        "غدًا" if ev["return_day"] == d + 1 else "بعد غد",
                        dates.period_date(year, month, ev["return_day"])),
                    "href": "/recruits?tab=leaves" + q})
            elif ev["kind"] == "permit_start":
                f, t = next(iter(ev["ranges"].values()))
                if evday == d:
                    leaves.append({
                        "text": "🏖️ {} — تصريح المدة {}–{} مُعدّ ✓ — سجّل كامل المدة في اليومية".format(
                            and_join(ev["names"]),
                            dates.period_date(year, month, f), dates.period_date(year, month, t)),
                        "href": "/recruits?tab=journal&day={}".format(evday) + q.replace("?", "&")})
                else:
                    # التصريح صادر وينتظر موعده؛ الرابط يفتح اليومية المختارة.
                    leaves.append({
                        "text": "🛎️ {} — تبدأ الإجازة {} ({}) — التصريح مُعدّ ✓".format(
                            and_join(ev["names"]), _when_word(evday, d),
                            dates.period_date(year, month, evday)),
                        "href": "/recruits?tab=journal&day={}".format(evday) + q.replace("?", "&")})
            elif ev["kind"] == "permit_gap" and evday == d:
                f, t = next(iter(ev["ranges"].values()))
                leaves.append({
                    "text": "⚠️ {} — تصريح يوم {}–{} صادر، ولم تُسجَّل «إجازة» في اليومية اليوم — أكمل التسجيل".format(
                        and_join(ev["names"]),
                        dates.period_date(year, month, f), dates.period_date(year, month, t)),
                    "href": "/recruits?tab=journal&day={}".format(d) + q.replace("?", "&")})
            elif ev["kind"] == "permit_end" and evday == d:
                leaves.append({
                    "text": "↩️ {} — انتهى تصريح الإجازة أمس — أكّد حضورهم في يومية اليوم".format(
                        and_join(ev["names"])),
                    "href": "/recruits?tab=journal&day={}".format(d) + q.replace("?", "&")})
            elif ev["kind"] == "leave_cut" and evday == d:
                c = ev["cut"]
                leaves.append({
                    "text": "🔪 {} — قُطعت إجازته وعاد اليوم (كانت {}–{}) — حدّد حالته في اليومية (حضور/مستشفى)".format(
                        and_join(ev["names"]),
                        dates.period_date(year, month, c["period_from"]),
                        dates.period_date(year, month, c["period_to"])),
                    "href": "/recruits?tab=journal&day={}".format(evday) + q.replace("?", "&")})
            elif ev["kind"] == "leave_cut_soon":
                leaves.append({
                    "text": "🛎️ غدًا: {} — قطع إجازة، والعودة غدًا".format(and_join(ev["names"])),
                    "href": "/recruits?tab=journal&day={}".format(evday + 1) + q.replace("?", "&")})
            elif ev["kind"] == "status_end":
                events.append({
                    "text": "{} {} — تنتهي حالة «{}» اليوم — سجّل «حضور» في يومية الغد".format(
                        EVENT_ICONS[ev["status"]], and_join(ev["names"]), ev["status"]),
                    "href": "/recruits?tab=other" + q})
            elif ev["kind"] in ("pun_start", "pun_active", "pun_end"):
                icon, noun = ev["icon"], ev["noun"]
                f, t = next(iter(ev["ranges"].values()))
                period = ("من يوم {} — مفتوح".format(dates.period_date(year, month, f))
                          if t is None else
                          "المدة {}–{}".format(dates.period_date(year, month, f),
                                               dates.period_date(year, month, t)))
                href = "/recruits?tab=prison&pkind={}".format(ev["pk"]) + q
                if ev["kind"] == "pun_start":
                    v_in = "يدخل" if len(ev["names"]) == 1 else "يدخلون"
                    if evday == d:
                        events.append({"text": "{} {} — {} {} اليوم ({})".format(
                            icon, and_join(ev["names"]), v_in, noun, period), "href": href})
                    else:
                        events.append({"text": "{} {} — {} {} {} ({})".format(
                            icon, and_join(ev["names"]), v_in, noun,
                            _when_word(evday, d), period), "href": href})
                elif ev["kind"] == "pun_active":
                    if evday == d:   # التنبيه اليومي داخل المدة، وليس تنبيه الغد
                        events.append({"text": "{} {} — في {} من يوم {} ({})".format(
                            icon, and_join(ev["names"]), noun,
                            dates.period_date(year, month, f), period), "href": href})
                else:  # pun_end
                    v_end = "يقضي" if len(ev["names"]) == 1 else "يقضون"
                    if evday == d:
                        events.append({"text": "{} {} — {} آخر يوم من {} اليوم ({}) — سجّل حالتهم في يومية الغد".format(
                            icon, and_join(ev["names"]), v_end, noun, period), "href": href})
                    else:
                        events.append({"text": "{} {} — تنتهي حالة {} {} ({})".format(
                            icon, and_join(ev["names"]), noun, _when_word(evday, d), period),
                            "href": href})
            elif ev["kind"] == "status":
                note = (" — " + ev["note"]) if ev["note"] else ""
                events.append({
                    "text": "{} {} — {} {} ({}){}".format(
                        EVENT_ICONS[ev["status"]], and_join(ev["names"]),
                        ev["status"], _when_word(evday, d),
                        dates.period_date(year, month, evday), note),
                    "href": "/recruits?tab=other" + q})
    return leaves, events


def build_groups(user_id, sid=""):
    """يرجع مجموعات الجرس: [{key, icon, title, level, items:[{text, href}]}]."""
    try:
        today = egtime.today()
        y, m, d = today.year, today.month, today.day
        if y not in storage.list_years():
            return []  # Reading notifications must not re-create a deleted/absent year.
        eom = egtime.days_in_month(y, m)
        recruits = {r["id"]: r for r in dr.list_recruits(y, m)}
        matrix = da.month_matrix(y, m)
        q = _sid_qs(sid)
        groups = {"journal": [], "leaves": [], "events": [], "certs": [],
                  "nocheckup": [], "absents": [], "service": []}

        # ١) يومية اليوم/الأمس (حقيقية دائمًا)
        missing = da.days_without_journal(y, m, d)
        if d in missing:
            groups["journal"].append({
                "text": "لم تُسجّل يومية اليوم حتى الآن",
                "href": "/recruits?tab=journal&day={}{}" .format(d, "&sid=" + sid if sid else "")})
        if d > 1 and (d - 1) in missing:
            groups["journal"].append({
                "text": "يومية أمس ({}) لم تُثبَّت — تُرحَّل تلقائيًا عند فتح اليوم".format(dates.period_date(y, m, d - 1)),
                "href": "/recruits?tab=journal&day={}".format(d - 1) + q.replace("?", "&")})
        earlier = [x for x in missing if x < d - 1][:3]
        for x in earlier:
            groups["journal"].append({
                "text": "يومية {} غير موجودة".format(dates.period_date(y, m, x)),
                "href": "/recruits?tab=journal&day={}".format(x) + q.replace("?", "&")})

        # ٢) الإجازات + ٣) مأمورية/مستشفى/أخرى (مجموعة بالأسماء)
        groups["leaves"], groups["events"] = _event_entries(y, m, matrix, recruits, d, eom, q)

        # ٤) الشهادات الصحية — قبلها بأسبوعين (قرار المستخدم)
        for r in recruits.values():
            st = dr.cert_state(r, today)
            if st == "expired":
                groups["certs"].append({
                    "text": "🔴 الشهادة الصحية لـ {} منتهية!".format(r["name"]),
                    "href": "/recruits?tab=registry&edit={}{}".format(r["id"], q.replace("?", "&"))})
            elif st == "soon":
                try:
                    left = (dates.parse_date(r["cert_expiry"]) - today).days
                except (ValueError, AttributeError, TypeError):
                    left = 14
                groups["certs"].append({
                    "text": "🟠 شهادة {} تنتهي خلال {} يومًا (أسبوعين)".format(r["name"], arnum.to_arabic_indic(left)),
                    "href": "/recruits?tab=registry&edit={}{}".format(r["id"], q.replace("?", "&"))})

        # ٥) لم يُكشفوا — آخر الشهر (بعد آخر يوم كشف) — قرار المستخدم
        try:
            hdays = db_health.get_days(y, m)
            if hdays and d >= max(hdays):
                done = db_health.month_checkup_ids(y, m)
                un = sorted(r["name"] for r in recruits.values() if r["id"] not in done)
                if un:
                    shown = and_join(un[:5]) + (
                        " +{} آخرين".format(arnum.to_arabic_indic(len(un) - 5)) if len(un) > 5 else "")
                    groups["nocheckup"].append({
                        "text": "⚕️ لم يخضعوا لكشف طبي هذا الشهر: {}".format(shown),
                        "href": "/health/?tab=checkups" + q.replace("?", "&")})
        except Exception:  # noqa: BLE001 — قسم الصحة اختياري على الجرس
            pass

        # ٦) غياب متواصل ≥ ٣ أيام
        streaks = da.absence_streak(y, m, matrix, d - 1 if d > 1 else d)
        for rid, streak in streaks.items():
            r = recruits.get(rid)
            if streak >= 3 and r:
                groups["absents"].append({
                    "text": "🚫 {} غائب منذ {} أيام متواصلة".format(r["name"], arnum.to_arabic_indic(streak)),
                    "href": "/recruits?tab=absent" + q})

        # ٧) خدمة تنتهي خلال ٦٠ يومًا
        for r in recruits.values():
            dd = dr.days_to_discharge(r, today)
            if dd is not None and 0 <= dd <= 60:
                groups["service"].append({
                    "text": "⏳ خدمة {} تنتهي خلال {} يومًا".format(r["name"], arnum.to_arabic_indic(dd)),
                    "href": "/recruits?tab=registry" + q})

        for entries in groups.values():
            for entry in entries:
                entry["href"] += f"&year={y}&month={m}"

        meta = {
            "journal": ("📝", "اليومية العامة", "danger"),
            "leaves": ("🏖️", "الإجازات — البدء/التصريح/العودة", "warn"),
            "events": ("🧭", "مأمورية / مستشفى / أخرى", "warn"),
            "certs": ("📋", "الشهادات الصحية (تنبيه قبل أسبوعين)", "warn"),
            "nocheckup": ("⚕️", "عدم إجراء الكشف الطبي (آخر الشهر)", "danger"),
            "absents": ("🚫", "غياب متواصل", "danger"),
            "service": ("⏳", "انتهاء الخدمة", "info"),
        }
        read = read_keys(user_id)
        out = []
        for key, (icon, title, level) in meta.items():
            if groups[key]:
                for it in groups[key]:
                    it["key"] = entry_key(key, it["text"])
                    it["read"] = it["key"] in read
                out.append({"key": key, "icon": icon, "title": title,
                            "level": level, "entries": groups[key]})
        return out
    except Exception:  # noqa: BLE001 — الجرس لا يسقط أي صفحة أبدًا
        return []


def summarize(user_id, sid=""):
    groups = build_groups(user_id, sid)
    return groups, sum(len(gr["entries"]) for gr in groups)
