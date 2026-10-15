# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تابات القوائم في صفحة المجندين (الحضور · الإجازات · الغياب · أخرى · السجن) — كلها
بمربعات الأيام زي اليومية العامة (توجيه ١٥/١٠): اليوم المفتوح، أو «الشهر كله» في القوائم.
الحضور: الإجازة المجمّعة/الطارئة على اليوم المفتوح + تنبيه «إجازتهم بكرة».
"""
from datetime import date

from flask import render_template, request

from core import egtime
from data_access import db_attendance as da
from data_access import db_punishments as dpk
from data_access import db_recruits as dr
from services import notifications
from services import recruit_periods as rp


def today_info(year, month, day):
    """حقائق «اليوم الحقيقي» بتوقيت القاهرة داخل شهر السياق."""
    t = egtime.today()
    is_real_month = (t.year == year and t.month == month)
    return {"today": t, "real_day": t.day if is_real_month else None,
            "is_real_month": is_real_month, "cur_day": day,
            "cur_weekday": egtime.weekday_ar(date(year, month, day))}


def cert_badge(r, today):
    st = dr.cert_state(r, today)
    return {"ok": ("🟢", "سارية"), "soon": ("🟠", "تنتهي قريبًا"),
            "expired": ("🔴", "منتهية!"), "none": ("⚪", "لا توجد")}[st]


def days_box(v, tab, day, marks=None, allow_all=True, extra=""):
    """سياق مربعات الأيام المشتركة (templates/recruits/_days.html)."""
    v["days_box"] = {"tab": tab, "day": day, "marks": marks or set(),
                     "allow_all": allow_all, "extra": extra}
    v["locked_days"] = da.locked_days(v["year"], v["month"])


# ======================================================================
# الحضور / الإجازات / الغياب / أخرى
# ======================================================================
def lists_view(v):
    tab, year, month = v["tab"], v["year"], v["month"]
    today = egtime.today()
    by_id = {r["id"]: r for r in v["recruits"]}
    # صفوف يومية/تصاريح «عاوية» (مجندها اتحذف) — بتنسى من الشوفات عشان ما تقصعش الصفحة
    v["matrix"] = {rid: days for rid, days in da.month_matrix(year, month).items() if rid in by_id}
    v["by_id"] = by_id
    v["info"] = today_info(year, month, 1)
    v["badges"] = {r["id"]: cert_badge(r, today) for r in v["recruits"]}
    rd = v["info"]["real_day"]
    if tab == "present":
        day = rp.selected_day(request.args.get("day"), rd, v["eom"], allow_all=False)
        _present(v, day)
        days_box(v, tab, day, rp.leave_marks(year, month, v["matrix"], by_id), allow_all=False)
        return render_template("recruits_lists.html", **v)
    day = rp.selected_day(request.args.get("day"), rd, v["eom"])
    one = day != rp.ALL_DAYS
    v["sel_day"] = day
    days_box(v, tab, day)
    if tab == "leaves":
        _leaves(v, day if one else None)
    elif tab == "absent":
        rows = []
        for rid, rs in da.absence_episodes(year, month, v["matrix"], 1, v["eom"]).items():
            for f, t in rs:
                if not one or rp.covers(f, t, day):
                    rows.append((by_id[rid], f, t))
        rows.sort(key=lambda x: (x[1], x[0]["name"]))
        v["episodes"] = rows
        upto = day if one else (max(1, rd - 1) if rd else 0)
        v["streaks"] = da.absence_streak(year, month, v["matrix"], upto) if upto else {}
    else:
        def pick(st):
            return [(by_id[rid], d) for rid, days in v["matrix"].items()
                    for d, s in sorted(days.items()) if s == st and (not one or d == day)]
        notes = da.month_rows(year, month)
        v["groups"] = [
            ("مأمورية", pick("مأمورية")),
            ("مستشفى", pick("مستشفى")),
            ("أخرى", [(r, d, notes.get(r["id"], {}).get(d, {}).get("note", "")) for r, d in pick("أخرى")]),
        ]
        # لوحة المستشفى: يوم بيوم + الحالة الصحية + ملاحظة (قرار ١٢/١٠)
        v["hospital"] = {rid: [x for x in rows if not one or x[0] == day]
                         for rid, rows in da.hospital_rows(year, month).items()}
        v["hospital_locked"] = v["locked_days"]
    return render_template("recruits_lists.html", **v)


def _present(v, day):
    """حاضرو اليوم المفتوح + «حضور من» (نفس «من» اليومية) + آخر إجازة + تنبيه إجازة بكرة."""
    year, month = v["year"], v["month"]
    dmap = da.get_day_map(year, month, day)
    v["day"] = day
    v["jl_day"] = day          # الإجازة المجمّعة/الطارئة على اليوم المفتوح (توجيه ١٥/١٠)
    v["rows"] = [(v["by_id"][rid], st) for rid, st in dmap.items()
                 if rid in v["by_id"] and st["status"] == "حضور"]
    per = rp.day_periods(year, month, day)
    v["runs"] = {r["id"]: {"from": per[r["id"]]["from"],
                           "days": rp.run_length(year, month, per[r["id"]]["from"], day)}
                 for r, _st in v["rows"] if r["id"] in per}
    past = da.leave_ranges(year, month, v["matrix"], 1, max(1, day - 1))
    v["last_leave"] = {}
    for rid, rs in past.items():
        run = v["runs"].get(rid)
        last = max(t for _f, t in rs)
        if run and rp.iso(year, month, last) < run["from"]:
            v["last_leave"][rid] = last
    v["leaving"] = rp.leaving_tomorrow(year, month, day, v["matrix"], v["by_id"])


def _leaves(v, day):
    """الإجازات: اليوم المفتوح (اللي في إجازة يومها) أو الشهر كله — بنفس الجدول والإجراءات."""
    year, month, by_id = v["year"], v["month"], v["by_id"]
    ranges = da.leave_ranges(year, month, v["matrix"], 1, v["eom"])
    # تصاريح الشهر الصادرة — علامة «✓ تصريح» جنب كل صف اتعملت له تصريح
    v["permits"] = da.month_leave_permits(year, month)
    # قطوع الشهر — «🔪 قطع» جنب الإجازة المتقطعة: الصف المختصر يطابق
    # المدة الأصلية (بداية نفسها ونهاية الأصل ≥ نهاية الصف)
    cut_rows = da.month_leave_cuts(year, month)
    v["row_cut"] = {}
    for rid, rs in ranges.items():
        for f, t in rs:
            for c in cut_rows.get(rid, []):
                if c["period_from"] == f and c["period_to"] >= t:
                    v["row_cut"][(rid, f, t)] = c
                    break
    v["ranges"] = {rid: [(f, t) for f, t in rs if day is None or rp.covers(f, t, day)]
                   for rid, rs in ranges.items()}
    v["ranges"] = {rid: rs for rid, rs in v["ranges"].items() if rs}
    # المرتقب والراجعين: بالنسبة للنهارده دايمًا (زي عمود الحالة والإجراءات)
    ref = v["info"]["real_day"] if v["info"]["is_real_month"] else None
    v["upcoming"], v["leaving_soon"] = {}, []
    if not ref:
        return
    upcoming = {}
    for rid, rs in ranges.items():
        for f, t in rs:
            if rid in by_id and ref <= f <= ref + 2:
                upcoming.setdefault(f, []).append(by_id[rid]["name"])
            if rid in by_id and ref <= t <= ref + 7:
                v["leaving_soon"].append((by_id[rid], f, t))
    # مرتقب مجمّع: {يوم البداية: «محمد وأحمد»} — «نازلين إجازة يوم ٥»
    v["upcoming"] = {f: {"names": notifications.and_join(names), "n": len(names)}
                     for f, names in sorted(upcoming.items())}
    v["leaving_soon"].sort(key=lambda x: (x[2], x[0]["name"]))
    v["ref_day"] = ref


# ======================================================================
# السجن والمحكمات والجزاءات (المراحل ٥ + ٠)
# ======================================================================
def prison_view(v):
    """٣ تبويبات فرعية (سجن/المحكمات/الجزاءات) — المدد مشتقة من اليومية العامة.

    التسجيل من «اليومية العامة» بحالة المجند (سجن/محكمة/جزاء) — مش من التاب.
    المدة = الأيام المتتالية للحالة · لو الحالة تغيّرت بتقفل · لو فارغة تبقى مفتوحة.
    """
    year, month = v["year"], v["month"]
    pkind = request.args.get("pkind") or "prison"
    if pkind not in dpk.VALID_KINDS:
        pkind = "prison"
    meta = dpk.KIND_META[pkind]
    info = today_info(year, month, 1)
    rd = info["real_day"]
    day = rp.selected_day(request.args.get("day"), rd, v["eom"])
    by_id = {r["id"]: r for r in v["recruits"]}
    rows = []
    for rid, f, t in dpk.month_spans(year, month, pkind):
        r = by_id.get(rid)
        if not r or (day != rp.ALL_DAYS and not rp.covers(f, t, day)):
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
    v["info"] = info
    v["sel_day"] = day
    days_box(v, "prison", day, extra="&pkind=" + pkind)
    # تذكير اليوم وغدًا — نفس نص الجرس حرفيًا (المصدر المشترك)
    alerts = []
    if rd:
        _leaves_ev, events = notifications._event_entries(
            year, month, da.month_matrix(year, month), by_id, rd, v["eom"], "")
        alerts = [e["text"] for e in events if "tab=prison" in e.get("href", "")]
    v["prison_alerts"] = alerts
    return render_template("recruits_prison.html", **v)
