# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""أسماء الحركات بالعربي — مصدر واحد لعرض السجلات (توجيه ١١/١٠: الدفتر زي الأسكرين شوت).

كل endpoint فيه اسم عربي واضح + دالة عرض تحوّل السطر الخام
(الحدث، المفتاح، التفاصيل الخام) إلى:
  اسم الإجراء | التفاصيل والملخص الفني لنشاط المستخدم
"""
from core import arabic_numbers as arnum

# ==================== أسماء الحركات (كل endpoint في البرنامج) ====================
ACTION_NAMES = {
    # ---- الإعدادات ----
    "settings.users_add": "إنشاء حساب مستخدم",
    "settings.users_update": "تعديل حساب مستخدم",
    "settings.users_toggle": "تفعيل/تعطيل حساب مستخدم",
    "settings.users_delete": "حذف حساب مستخدم",
    "settings.users_tabs": "تعديل صلاحيات تابات مستخدم",
    "settings.notes_add": "إرسال ملحوظة",
    "settings.notes_reply": "رد على ملحوظة",
    "settings.notes_close": "إغلاق ملحوظة",
    "settings.gate": "فتح قسم محمي",
    # ---- مستودعات وسجلات ----
    "warehouses.suppliers_add": "إضافة شركة موردة",
    "warehouses.suppliers_save": "تعديل شركة موردة",
    "warehouses.suppliers_delete": "حذف شركة موردة",
    "warehouses.wh1_add": "إضافة بند لمخزن ١ (إذن الإضافة)",
    "warehouses.wh1_edit": "تعديل بند بمخزن ١",
    "warehouses.wh3_opener": "تسجيل إذن مخزن ٣",
    "warehouses.wh3_unit": "تسجيل وحدة مخزن ٣",
    "warehouses.wh3_row_note": "ملاحظة على بند مخزن ٣",
    "wh4.strike_save": "شطب بند بدفتر ٤ مخازن",
    "wh4.price_save": "تسجيل سعر بدفتر ٤ مخازن",
    "wh4.meta_save": "تعديل بيانات دفتر ٤ مخازن",
    "inv6.apply": "تطبيق محضر جرد 6 مخازن",
    "inv6.delete": "حذف سطر من محضر 6 مخازن",
    # ---- الترفية ----
    "tarfea.items_save": "حفظ أصناف الترفية",
    "tarfea.items_delete": "حذف صنف ترفية",
    "tarfea.wh2_add": "إضافة بند لمخزن ٢ ترفية",
    "tarfea.wh2_delete": "حذف بند من مخزن ٢ ترفية",
    # ---- التاميدات ----
    "tameedat.record_add": "إضافة تأميدة",
    "tameedat.record_edit": "تعديل تأميدة",
    "tameedat.record_delete": "حذف تأميدة",
    "tameedat.record_paste": "لصق تأميدة (نسخ)",
    "tameedat.entity_add": "إضافة جهة لقامة التاميدات",
    "tameedat.entity_edit": "تعديل جهة بقامة التاميدات",
    "tameedat.entity_delete": "حذف جهة من قامة التاميدات",
    "tameedat.alert_ignore": "تجاهل تنبيه تاميد",
    "tameedat.alert_restore": "استعادة تنبيه تاميد",
    # ---- آلة الحاسبة ٢ مخازن ----
    "calc2.save": "حساب ٢ مخازن (آلة الحاسبة)",
    "calc2_free.free_save": "حساب حر",
    "calc2_free.free_delete": "حذف حساب حر",
    "calc2_free.free_rates_save": "تعديل أسعار الحساب الحر",
    "dowail.save_tafreeda": "حفظ تفريعة",
    "dowail.save_delete": "إلغاء حفظ تفريعة",
    "dowail.add_line": "إضافة سطر تفريعة",
    "dowail.delete_line": "حذف سطر تفريعة",
    "dowail.add_point": "إضافة نقطة",
    "dowail.update_point": "تعديل نقطة",
    "dowail.delete_point": "حذف نقطة",
    "dowail.paper_meta_save": "تعديل بيانات ورقية",
    "dowail.rates_add": "إضافة سعر",
    "dowail.rates_update": "تعديل سعر",
    "dowail.rates_delete": "حذف سعر",
    "dowail.rates_toggle": "تفعيل/تعطيل سعر",
    "dowail.custom_save": "حفظ مخصص",
    # ---- المجندين ----
    "recruits.save": "حفظ بيانات المجندين",
    "recruits.delete": "حذف بيانات مجندين",
    "recruits.journal_save": "تسجيل اليومية",
    "recruits.journal_delete_entry": "حذف بند من اليومية",
    "recruits.journal_confirm_leaves": "تثبيت الإجازات في اليومية",
    "recruits.journal_range": "فتح نطاق يومي",
    "recruits.journal_unlock": "فتح قفل اليومية",
    "recruits.stats_read_all": "قراءة كل الإحصائيات",
    "recruits.docx_rebuild": "إعادة بناء ملفات المجندين",
    "recruits.joint_permit": "تسجيل إذن مشترك",
    # ---- المخازن والثلاجات ----
    "stores.save": "حفظ حركة/رصيد في المخازن والثلاجات",
    "stores.delete": "حذف من المخازن والثلاجات",
    # ---- المقررات ----
    "rations.item_add": "إضافة صنف مقرر",
    "rations.item_edit": "تعديل صنف مقرر",
    "rations.item_delete": "حذف صنف مقرر",
    "rations.entity_add": "إضافة جهة مقررات",
    "rations.entity_delete": "حذف جهة مقررات",
    "rations.entity_resync": "مزامنة جهات المقررات",
    "rations.eitem_add": "إضافة بند لجهة مقرر",
    "rations.eitem_edit": "تعديل بند لجهة مقرر",
    "rations.eitem_delete": "حذف بند لجهة مقرر",
    "rations.eitem_days": "تعديل أيام بند مقرر",
    "rations.custom_save": "حفظ مخصص مقررات",
    "rations.activate": "تفعيل مقرر",
    "rations.copy_kind": "نسخ نوع مقرر",
    # ---- الدباجة ----
    "letterhead.save": "حفظ دباجة/توقيع رسمي",
    "letterhead.logo_delete": "حذف شعار الدباجة",
    # ---- النسخ الاحتياطي ----
    "backups.create": "إنشاء نسخة احتياطية",
    "backups.restore": "استعادة نسخة احتياطية",
    "backups.delete": "حذف نسخة احتياطية",
    # ---- المناسبات ----
    "occasions.create": "إنشاء مناسبات/وثائق",
    "occasions.save": "تعديل مناسبات/وثائق",
    "occasions.delete": "حذف مناسبات/وثائق",
    "occasions.media_upload": "رفعة ملفات وسائط",
    "occasions.media_upload_json": "رفعة وسائط (JSON)",
    "occasions.media_delete": "حذف وسائط",
    # ---- الراغبين ----
    "raghibin.cadres_add": "إضافة كادر راغب",
    "raghibin.cadres_copy": "نسخ كادر",
    "raghibin.cadres_delete": "حذف كادر",
    "raghibin.cadres_exclude": "استبعاد كادر",
    "raghibin.cadres_note": "ملاحظة على كادر",
    "raghibin.cadres_entity_add": "إضافة جهة كادر",
    "raghibin.cadres_entity_delete": "حذف جهة كادر",
    "raghibin.approval_save": "حفظ اعتماد",
    "raghibin.daily_save": "تسجيل يومي الراغبين",
    "raghibin.daily_copy": "نسخ يومي",
    "raghibin.panel_quick_add": "إضافة سريعة للوحة",
    "raghibin.panel_delete": "حذف من اللوحة",
    "raghibin.files_rebuild": "إعادة بناء ملفات الراغبين",
    "raghibin.scan_upload": "رفعة سكاني",
    # ---- الصحة ----
    "health.save_days": "حفظ أيام الصحة",
    "health.save_fields": "تعديل حقول الصحة",
    "health.reset_fields": "تصفير حقول الصحة",
    "health.select_checkup": "اختيار كشف دوري",
    "health.tanks_add": "إضافة خزان",
    "health.tanks_delete": "حذف خزان",
    "health.logo_upload": "رفعة شعار الصحة",
    "health.logo_delete": "حذف شعار الصحة",
    # ---- نسخ شهر ----
    "month_copy.copy": "نسخ شهر",
    "month_copy.legacy": "نسخ شهر (نظام قديم)",
    # ---- المساعد ----
    "assistant.ask": "سؤال المساعد",
    "assistant.model_select": "اختيار نموذج المساعد",
}

# أقسام بلا خريطة صريحة — أسماء عربية للأقسام نفسها
SECTION_NAMES = {}
def _load_section_names():
    if SECTION_NAMES:
        return
    from core.config import SECTIONS, EXTRA_PAGES
    for s in list(SECTIONS) + list(EXTRA_PAGES):
        SECTION_NAMES[s["key"]] = s["name"]
    from core import tabs_registry as tr
    for sec, subs in tr.SUBTABS.items():
        if sec not in SECTION_NAMES:
            SECTION_NAMES[sec] = sec

_LOAD_CACHE = {}
def _sub_labels():
    if not _LOAD_CACHE:
        from core import tabs_registry as tr
        for sec, subs in tr.SUBTABS.items():
            for k, label in subs:
                _LOAD_CACHE[(sec, k)] = label
    return _LOAD_CACHE


def page_name(tab_key):
    """الاسم العربي لصفحة/تاب من مفتاحه: warehouses_records:wh1 → «مستودعات وسجلات — مخزن ١»."""
    _load_section_names()
    if not tab_key or tab_key == "dashboard":
        return "الرئيسية"
    section, _, sub = str(tab_key).partition(":")
    sec_name = SECTION_NAMES.get(section, section)
    if not sub:
        return sec_name
    sub_label = _sub_labels().get((section, sub))
    return f"{sec_name} — {sub_label}" if sub_label else sec_name


# ==================== تنسيق الوقت/التاريخ (زي الدفتر بالضبط) ====================
def fmt_log_time(ts):
    """2026-10-10 23:10:14 → «٢٠٦/١٠/١٠ م ١:١٠:١٤ م» (سنة/شهر/يوم + ١٢ ساعة + ص/م — زي الدفتر)."""
    try:
        d, t = (str(ts).split(" ") + [""])[:2]
        y, m, dd = d.split("-")
        h, mi, s = (t.split(":") + ["0", "0"])[:3]
        h = int(h)
        ampm = "ص" if h < 12 else "م"
        h12 = h % 12 or 12
        base = f"{h12:02d}:{mi}:{s}"
        return f"{arnum.to_arabic_indic(f'{y}/{m}/{dd}')} م {arnum.to_arabic_indic(base)} {ampm}"
    except Exception:      # noqa: BLE001
        return str(ts or "")


# ==================== عرض السطر ====================
def _extract_endpoint(raw_details):
    """endpoint من تفاصيل خام: 'حفظ/تعديل (settings.notes_reply) — الرد' → 'settings.notes_reply'."""
    if not raw_details:
        return None, ""
    import re
    m = re.search(r"\(([a-z0-9_]+\.[a-z0-9_]+)\)", raw_details)
    rest = raw_details
    name = ""
    if m:
        ep = m.group(1)
        rest = rest[m.end():]
    else:
        ep = None
    if "—" in rest:
        parts = rest.split("—", 1)
        rest = parts[0]
        name = parts[1].strip()
    failed = raw_details.startswith("فشل:")
    return (ep, name, failed) if ep else (None, name, failed)


def log_row(event, tab_key, raw_details):
    """سجل خام → (اسم الإجراء, التفاصيل والملخص الفني) بالعربي زي الدفتر."""
    ep, name, failed = (None, "", False)
    if event == "action":
        ep, name, failed = _extract_endpoint(raw_details)
    if event == "login":
        act, det = "تسجيل دخول", "دخول على المنظومة — بداية جلسة العمل"
    elif event == "logout":
        act, det = "تسجيل خروج", "خروج من المنظومة — نهاية جلسة العمل"
    elif event == "note":
        import re
        m = re.search(r"#(\d+)", raw_details or "")
        num = arnum.to_arabic_indic(m.group(1)) if m else "—"
        if "رد" in (raw_details or ""):
            act, det = "رد على ملحوظة", f"تم الرد على الملحوظة رقم {num}"
        elif "إغلاق" in (raw_details or ""):
            act, det = "إغلاق ملحوظة", f"تم إغلاق الملحوظة رقم {num}"
        else:
            act = "إرسال ملحوظة"
            who = (raw_details or "").split("إلى:", 1)[-1].strip()
            det = f"تم إرسال ملحوظة إلى: {who or 'مستخدم'}"
    elif event == "page":
        pn = page_name(tab_key)
        act, det = "فتح صفحة", f"تصفح صفحة {pn}"
    else:
        act = ACTION_NAMES.get(ep, "إجراء") if ep else "إجراء"
        det = f"إجراء على {page_name(tab_key)}"
    # حركات الحفظ: التفاصيل = «تم {الإجراء}» + اسم العنصر لو اتسجل
    if event == "action":
        act = ACTION_NAMES.get(ep, act) if ep else act
        det = _done(act)
        if name:
            det += f": {name}"
        if failed:
            det = f"محاولة {act}: فشلت العملية (خطأ في الطلب)"
    if failed:
        act = "فشل: " + act
    return act, det


def _done(act):
    """«تم/تمت/تم الرد» حسب الإجراء (عربي صحيح)."""
    if act.startswith("رد "):
        return "تم " + act.replace("رد", "الرد", 1)
    if any(act.startswith(w) for w in ("إضافة", "استعادة", "مزامنة", "قراءة",
                                       "رفعة", "ملاحظة", "تصفيرة")):
        return "تمت " + act
    return "تم " + act


# ==================== اسم العنصر من الفورم (لالتفاصيل) ====================
_NAME_FIELDS = ("name", "full_name", "item_name", "entity_name", "warehouse_name",
                "title", "text", "rank", "description", "permit_no", "username")
_SKIP = {"sid", "year", "month", "day", "tab", "sub", "user_id", "note_id", "record_id",
         "entity_id", "serial", "cycle", "issue_id", "permit_id", "fmt", "kind",
         "remember", "password"}


def form_name(form):
    """أول حقل فيه اسم/نص واضح من الفورم (لتفاصيل السجل)."""
    try:
        for f in _NAME_FIELDS:
            v = (form.get(f) or "").strip()
            if v and f not in _SKIP and len(v) <= 80:
                return v
    except Exception:      # noqa: BLE001
        pass
    return ""
