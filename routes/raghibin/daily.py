# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تاب «الراغبين (يومي)» + كشف الراغبين في التأميدات (ربط بالاتجاهين).

النموذج (توجيه المستخدم ٣٠/٠٩/٢٠٢٦): حسب تأميدة اليوم تظهر مربعات فاضية ذكية —
١٠ ضباط في التأميدة = ١٠ مربعات ضباط و١٠ للأفراد — تكتب الاسم بالبحث الذكي من
«الجهات والكوادر»، وأي اسم جديد يسأل «هل تريد إضافته كقوة دائمة للجهة؟»
فيدخل تلقائيًا في قوة الكوادر. الحفظ clear-and-set: المربعات هي كشف الراغبين
كاملًا لذلك اليوم/الفئة — ومن يحذف من مربع يُلغى رغبته.

التوجيه النهائي (٣٠/٠٩/٢٠٢٦ مساءً): زرار التأميدة يفتح **صفحة كاملة عادية**
/modal — بنفس آلية كل صفحات النظام (sid في الرابط) — من غير أي جلب خفي:
fetch اتشال من المنظومة كلها لأنه مصدر العطل المتكرر مع الجلسات.
/modal: الصفحة الكاملة · /panel: جزء legacy · /panel/quick_add و/panel/delete:
إضافة سريعة وحذف يرجعون لصفحة الكشف بتحويل عادي · /daily/save: الحفظ الموحد.
"""
import json
import re

from flask import redirect, render_template, request, send_file
from urllib.parse import quote

from core import arabic_numbers as arnum
from core.auth_core import login_required
from data_access import db_raghibin as dr
from data_access import db_tameedat as dt
from services import raghibin as rfs
from services import tameed_alerts
from services.raghibin import modal as rg_modal

from . import raghibin_bp
from .context import (_category, _ctx, _draft_totals, _entity_or_back, _rb,
                      _selected_day, _selected_entity)


def _modal_page_url(entity, day, cat, sid=""):
    """رابط صفحة كشف الراغبين الكاملة (تصفح عادي — sid في الرابط)."""
    url = f"/raghibin/modal?c={cat}&d={day}&en={quote(entity['name'])}"
    et = (request.values.get("et") or "").strip()   # ١٤/١٠: نوع التأميدة يكمل للصفحة الكاملة
    if et:
        url += f"&et={quote(et)}"
    return url + (f"&sid={quote(sid)}" if sid else "")


# ١٤/١٠: أنواع القاموس المخزنة بالإنجليزية → عرض عربي (كانت تظهر workshop/salon)
ENTITY_TYPE_AR = {"salon": "صالة", "workshop": "ورشة", "gate": "بوابة",
                  "store": "مخزن", "hall": "صالة", "office": "مكتب"}


def _entity_type_label(entity):
    """نوع الجهة المعروض: نوع التأميدة المختار في فورم اليومية (شرطية/حربية)
    ولو مش ممرر → ترجمة نوع القاموس للعربي."""
    form_type = (request.values.get("et") or "").strip()
    if form_type:
        return form_type
    raw = ((entity or {}).get("entity_type") or "").strip()
    return ENTITY_TYPE_AR.get(raw.lower(), raw or "غير محدد")


@raghibin_bp.route("/modal")
@login_required
def modal_page():
    """صفحة «كشف وتسجيل أسماء الضباط والأفراد الراغبين» الكاملة."""
    from flask import url_for
    year, month = _ctx()
    entity = _selected_entity(year, month, by_name=True)
    day = _selected_day(year, month)
    cat = _category()
    sid = request.values.get("sid", "")
    # ١٤/١٠: عدّادات فورم التأميدة (o/i) — المربعات تتبع الرقم المكتوب
    # حتى لو التأميدة غير محفوظة (تفتح من زر «تسجيل أسماء» في التاميدات).
    variables = rg_modal.build(year, month, entity, day, cat, sid=sid,
                               draft_totals=_draft_totals(request))
    # الرجوع بعد الحفظ: من تاب الراغبين يرجع للراحبين (back=raghibin) —
    # ومن التأميدات يفضل في التاميدات (الافتراضي tameedat)
    variables["back"] = request.args.get("back", "tameedat")
    # url_for('tameedat.page') بيحمل ?year&month&sid تلقائيًا (url_defaults) — فالفاصل &
    back = url_for("tameedat.page")
    back += ("&" if "?" in back else "?") + "tab=day"
    variables["tameed_back"] = back + (f"&sid={quote(sid)}" if sid else "")
    variables["ok"] = request.args.get("ok", "")
    variables["err"] = request.args.get("err", "")
    # السجل المعتمد اتنقل لتاب «الجهات والكوادر» بس (توجيه ١٣/١٠) — هنا الاعتماد والممسح بس
    if entity:
        variables["approval"] = dr.get_approval(year, month, entity["id"], day)
        variables["scan_img_url"] = (
            f"/raghibin/scan/img?e={entity['id']}&d={day}"
            + (f"&sid={quote(sid)}" if sid else ""))
    else:
        variables["approval"] = None
        variables["scan_img_url"] = ""
    return render_template("raghibin/modal_page.html", **variables)


@raghibin_bp.route("/panel")
@login_required
def panel():
    """جزء المودال — نفس محتوى الصفحة الكاملة بدون هيكل الصفحة.
    ١٤/١٠: المودال المنبثق من فورم التاميدة بيجيب الجزء ده بـ fetch."""
    year, month = _ctx()
    entity = _selected_entity(year, month, by_name=True)
    day = _selected_day(year, month)
    return _modal_fragment(year, month, entity, day, _category(),
                           draft_totals=_draft_totals(request))


@raghibin_bp.route("/panel/quick_add", methods=["POST"])
@login_required
def panel_quick_add():
    """«إضافة عضو جديد سريع إلى قوة الجهة» — ثم رجوع لصفحة الكشف (تصفح عادي)."""
    year, month = _ctx()
    entity, back = _entity_or_back(year, month)
    if back:
        return back
    day = _selected_day(year, month)
    cat = request.form.get("qa_cat") if request.form.get("qa_cat") in dr.CATEGORY_KEYS \
        else _category()
    name = " ".join((request.form.get("qa_name") or "").split())
    if name:
        dr.add_person(year, month, entity["id"], cat, name,
                      rank=(request.form.get("qa_rank") or "").strip(),
                      exclude_note=(request.form.get("qa_note") or "").strip())
        rfs.write_entity_files(year, month, entity["id"], entity["name"], day=day)
    return redirect(_modal_page_url(entity, day, cat, request.form.get("sid", "")))


@raghibin_bp.route("/panel/delete/<int:person_id>", methods=["POST"])
@login_required
def panel_delete(person_id):
    """حذف اسم من القوة من صفحة الكشف — ثم رجوع إليها (تصفح عادي)."""
    year, month = _ctx()
    person = dr.get_person(year, month, person_id)
    if person:
        dr.delete_person(year, month, person_id)
        rfs.write_entity_files(year, month, person["entity_id"], person["entity_name"])
        entity = dt.get_entity(year, month, person["entity_id"])
        return redirect(_modal_page_url(entity, _selected_day(year, month),
                                        person["category"],
                                        request.form.get("sid", "")))
    entity, back = _entity_or_back(year, month)
    if back:
        return back
    return redirect(_modal_page_url(entity, _selected_day(year, month),
                                    _category(), request.form.get("sid", "")))


def _modal_fragment(year, month, entity, day, cat, draft_totals=None):
    """جزء المودال — عبر الخدمة المشتركة (نفس محتوى الصفحة الكاملة)."""
    variables = rg_modal.build(year, month, entity, day, cat,
                               sid=request.values.get("sid", ""),
                               draft_totals=draft_totals)
    # ١٤/١٠: المودال المنبثق بيحضر الجزء بـ fetch — رسائل الحفظ توصل هنا
    variables["ok"] = request.values.get("ok", "")
    variables["warn"] = request.values.get("warn", "")
    variables["err"] = request.values.get("err", "")
    variables["entity_type_label"] = _entity_type_label(entity)
    return render_template("raghibin/modal_body.html", **variables)


@raghibin_bp.route("/daily/save", methods=["POST"])
@login_required
def daily_save():
    year, month = _ctx()
    entity, back = _entity_or_back(year, month, "daily")
    if back:
        return back
    day = _selected_day(year, month)
    cat = _category()
    if request.form.get("cat") in dict(dr.CATEGORIES):
        cat = request.form.get("cat")
    source = "tamida" if request.form.get("source") == "tamida" else "manual"
    back_to = request.form.get("back", "raghibin")

    # ١٣/١٠: كل صف = مربع رتبة (منسدلة) + مربع اسم — الرتبة بالترتيب
    # نفسه لمربعات الاسم (getlist موازٍ).
    name_raws = request.form.getlist("names")
    rank_raws = request.form.getlist("ranks")
    rows = []       # (الاسم، الرتبة) فريدة بالترتيب — ١٤/١٠: الرتبة جزء من الاسم
    for i, raw in enumerate(name_raws):
        name = " ".join((raw or "").split())
        if not name:
            continue
        raw_rank = rank_raws[i] if i < len(rank_raws) else ""
        pair = (name, " ".join((raw_rank or "").split()))
        if pair in rows:      # نفس الاسم بنفس الرتبة = صف مكرر
            continue
        rows.append(pair)
    try:
        confirmed_new = {n for n in (json.loads(request.form.get("new_names") or "[]")
                                     if request.form.get("new_names") else [])}
    except json.JSONDecodeError:
        confirmed_new = set()

    warnings, added, resolved_ids = [], [], []
    for name, rank in rows:
        # ١٤/١٠: البحث بـ «الاسم + الرتبة» — نفس الاسم برتبة مختلفة شخص تاني
        person = dr.find_person(year, month, entity["id"], cat, name, rank=rank)
        if person is None and name in confirmed_new:
            dr.add_person(year, month, entity["id"], cat, name, rank=rank)
            added.append(name)
            person = dr.find_person(year, month, entity["id"], cat, name, rank=rank)
        elif person is not None and rank and not (person.get("rank") or "").strip():
            # المسجل من غير رتبة → تتكمّل رتبته بالرتبة المختارة في المربع
            dr.update_person(year, month, person["id"], name, rank=rank)
        if person is None:
            rank_txt = f" برتبة {rank}" if rank else ""
            warnings.append(f"«{name}»{rank_txt} غير مسجّل في قوة الجهة "
                            "ولم يؤكد إضافته — تجاهلناه")
            continue
        if person["excluded"]:
            reason = person["exclude_note"] or "بدون سبب"
            warnings.append(f"«{name}» مستثنى «غير راغب» ({reason}) — تجاهلناه")
            continue
        resolved_ids.append(person["id"])

    count, removed = dr.set_day_category(year, month, entity["id"], day, cat,
                                         resolved_ids, source=source)
    rfs.write_entity_files(year, month, entity["id"], entity["name"], day=day)

    label = dict(dr.CATEGORIES)[cat]
    day_txt = arnum.to_arabic_indic(str(day))
    ok = f"تم تسجيل {arnum.to_arabic_indic(str(count))} راغبين ({label}) يوم {day_txt}"
    if added:
        ok += f" — أُضيفوا للقوة الدائمة: {'، '.join(added)}"
    if removed:
        ok += f" — وأُلغيت رغبة {arnum.to_arabic_indic(str(removed))}" \
              f" محذوفين من المربعات"
    # الربط بتاب التاميدات: مقارنة أعداد اليوم بتأميدة الجهة (أو تنبيه غيابها)
    from routes.raghibin.context import _tameed_day_totals
    tameed_totals = _tameed_day_totals(year, month, entity["id"], day)
    state = dr.day_state(year, month, day, entity["id"])
    w_off = w_ind = 0
    for p in dr.list_persons(year, month, entity_id=entity["id"]):
        if state.get(p["id"]):
            if p["category"] == "officers":
                w_off += 1
            else:
                w_ind += 1
    if not tameed_totals:
        if w_off + w_ind:
            warnings.append(tameed_alerts.no_tameeda_issue(w_off + w_ind)["text"])
    else:
        cmp_msgs = []
        for lbl, w, t in (("ضباط", w_off, tameed_totals["officers"]),
                          ("أفراد", w_ind, tameed_totals["individuals"])):
            if w < t:
                cmp_msgs.append(f"الراغبين {lbl} ({arnum.to_arabic_indic(str(w))}) "
                                f"أقل من التأميدة ({arnum.to_arabic_indic(str(t))}) — "
                                f"الناقص {arnum.to_arabic_indic(str(t - w))}")
            elif w > t:
                cmp_msgs.append(f"الراغبين {lbl} ({arnum.to_arabic_indic(str(w))}) "
                                f"أكتر من التأميدة ({arnum.to_arabic_indic(str(t))}) — "
                                f"التجاوز {arnum.to_arabic_indic(str(w - t))}")
        if not cmp_msgs and (w_off + w_ind) == (tameed_totals["officers"] +
                                               tameed_totals["individuals"]):
            ok += " — مطابق للتأميدة ✓"
        warnings.extend(cmp_msgs)
    warn = " | ".join(warnings) if warnings else None

    if back_to == "tameedat":
        from core.auth_core import current_session
        from flask import url_for
        _, token = current_session()
        params = {"tab": "day", "day": f"{year:04d}-{month:02d}-{day:02d}"}
        base = url_for("tameedat.page")
        if token and "sid=" not in base:   # ١٤/١٠: بلا تكرار للتوكن في الرابط
            params["sid"] = token
        if ok:
            params["ok"] = ok
        if warn:
            params["warn"] = warn
        separator = "&" if "?" in base else "?"
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return redirect(f"{base}{separator}{query}")
    return _rb("daily", e=entity["id"], d=day, c=cat, ok=ok, warn=warn)


@raghibin_bp.route("/daily/copy", methods=["POST"])
@login_required
def daily_copy():
    """نسخ كشف راغب يوم كامل ليوم تانى — الجهة من الفورم أولًا (دايالوج النسخ)."""
    year, month = _ctx()
    eid = arnum.parse_int(request.form.get("e"))
    if eid:
        entity = dt.get_entity(year, month, eid)
        if not entity:
            return _rb("daily", err="الجهة المحددة في نافذة النسخ غير موجودة")
    else:
        entity, back = _entity_or_back(year, month, "daily")
        if back:
            return back
    try:
        from_day = int(request.form.get("from_d") or _selected_day(year, month))
        to_day = int(request.form.get("to_d") or 0)
        if not (1 <= to_day <= 31):
            raise ValueError
    except ValueError:
        return _rb("daily", e=entity["id"], d=_selected_day(year, month),
                   err="حدد يوم الهدف صحيح (١ حتى ٣١) عشان نسخ الكشف له")
    moved = dr.copy_day(year, month, entity["id"], from_day, to_day)
    rfs.write_entity_files(year, month, entity["id"], entity["name"], day=to_day)
    ok = (f"تم نسخ كشف راغب يوم {arnum.to_arabic_indic(str(from_day))} كاملًا "
          f"({arnum.to_arabic_indic(str(moved))} عضو) إلى يوم "
          f"{arnum.to_arabic_indic(str(to_day))} — {entity['name']}")
    return _rb("daily", e=entity["id"], d=to_day, c=_category(), ok=ok)


@raghibin_bp.route("/approval/save", methods=["POST"])
@login_required
def approval_save():
    """حفظ توقيتات اعتماد كشف اليوم: المقدم + الاسم العروني + الرتبة + الحالة."""
    year, month = _ctx()
    entity, back = _entity_or_back(year, month, "daily")
    if back:
        return back
    try:
        day = int(request.form.get("d") or _selected_day(year, month))
    except ValueError:
        day = _selected_day(year, month)
    submit_rank = (request.form.get("submit_rank") or "").strip()
    submit_name = (request.form.get("submit_name") or "").strip()
    submit_grade = (request.form.get("submit_grade") or "").strip()
    doc_rank = (request.form.get("doc_rank") or "").strip()
    doc_name = (request.form.get("doc_name") or "").strip()
    doc_roster = (request.form.get("doc_roster_name") or "").strip()
    # توافق مع الفورم القديم (صف اعتماد المودال السابق)
    if not (submit_rank or submit_name or doc_rank or doc_name):
        submit_grade = (request.form.get("approver_rank") or "").strip()
        submit_name = (request.form.get("approver_name") or "").strip()
    status = (request.form.get("status") or "موثقة").strip() or "موثقة"
    dr.save_approval(year, month, entity["id"], day,
                     submit_rank=submit_rank, submit_name=submit_name,
                     submit_grade=submit_grade, doc_rank=doc_rank,
                     doc_name=doc_name, doc_roster_name=doc_roster,
                     status=status)
    ok = (f"تم حفظ توقيتات اعتماد كشف يوم {arnum.to_arabic_indic(str(day))} "
          f"({entity['name']}) — الحالة: {status}")
    sid = request.form.get("sid", "")
    if request.form.get("back") == "cadres":
        return _rb("cadres", e=entity["id"], d=day, ok=ok)
    return redirect(_modal_page_url(entity, day, _category(), sid) + f"&ok={quote(ok)}")


@raghibin_bp.route("/scan/upload", methods=["POST"])
@login_required
def scan_upload():
    """رفع صورة كشف/بطاقة اليوم للجهة — محفوظة في فولدر المسح الضوئي المحلي."""
    year, month = _ctx()
    entity, back = _entity_or_back(year, month, "daily")
    if back:
        return back
    try:
        day = int(request.form.get("d") or _selected_day(year, month))
    except ValueError:
        day = _selected_day(year, month)
    back_tab = "cadres" if request.form.get("back") == "cadres" else "daily"
    upload = request.files.get("scan_file")
    if not upload or not upload.filename:
        return _rb(back_tab, e=entity["id"], d=day, err="اختر صورة الكشف الأول قبل الحفظ")
    match = re.search(r"\.([a-zA-Z0-9]{2,5})$", upload.filename)
    ext = (match.group(1).lower() if match else "jpg")
    if ext not in ("jpg", "jpeg", "png", "webp", "bmp"):
        ext = "jpg"
    safe_name = re.sub(r"[^\w\s\-]", "", entity["name"]).strip() or "جهة"
    folder = rfs.tab_dir(year, month, "daily") / "المسح الضوئي" / f"يوم {day}"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{safe_name}.{ext}"
    upload.save(dest)
    ok = f"تم حفظ صورة كشف {entity['name']} ليوم {arnum.to_arabic_indic(str(day))} في فولدر المسح الضوئي المحلي"
    sid = request.form.get("sid", "")
    if back_tab == "cadres":
        return _rb("cadres", e=entity["id"], d=day, ok=ok)
    return redirect(_modal_page_url(entity, day, _category(), sid) + f"&ok={quote(ok)}")


@raghibin_bp.route("/scan/img")
@login_required
def scan_img():
    """عرض أحدث صورة مسح ضوئي محفوظة ليوم الجهة."""
    year, month = _ctx()
    entity = _selected_entity(year, month)
    try:
        day = int(request.values.get("d") or _selected_day(year, month))
    except ValueError:
        day = _selected_day(year, month)
    if not entity:
        from flask import abort
        abort(404)
    folder = (rfs.tab_dir(year, month, "daily") / "المسح الضوئي" / f"يوم {day}")
    if not folder.is_dir():
        from flask import abort
        abort(404)
    candidates = sorted(folder.iterdir(), key=lambda p: p.stat().st_mtime,
                        reverse=True)
    candidates = [p for p in candidates if p.is_file()
                  and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp")]
    if not candidates:
        from flask import abort
        abort(404)
    return send_file(candidates[0])
