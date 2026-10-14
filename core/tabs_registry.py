# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""سجل التابات — مصدر واحد لصلاحيات المستخدمين.

كل تاب في البرنامج له مفتاح:
- قسم بلا تابات داخلية: مفتاحه = مفتاح القسم (مثال: «tameedat» لو مش عنده توابت)
- قسم بتوابت داخلية: «القسم:التاب» (مثال: «warehouses_records:wh1»)

الـ admin عنده كل الصلاحيات تلقائيًا. المستخدم العادي: صلاحية التاب أو
صلاحية القسم كله (المفتاح الأساسي) تفتح التابات الداخلية كلها.
"""
from core.config import EXTRA_PAGES, SECTIONS, nav_monthly

# التابات الداخلية لكل قسم (اللي عندنا تنقّل تويتات جوهه)
SUBTABS = {
    "warehouses_records": [
        ("suppliers", "الشركات الموردة"),
        ("wh1", "١ مخازن — إذون الإضافة"),
        ("wh2", "٢ مخازن"),
        ("wh3", "٣ مخازن"),
        ("wh4", "دفتر 4 مخازن"),
        ("wh5", "٥ مخازن"),
        ("inv6", "6 مخازن (جرد الأصناف)"),
    ],
    "tarfea": [
        ("items", "الأصناف"),
        ("wh1", "١ مخازن"),
        ("wh2", "٢ مخازن"),
        ("wh3", "٣ مخازن"),
        ("wh5", "٥ مخازن"),
        ("store", "مخزن الترفية"),
    ],
    "tameedat": [
        ("day", "التأميدة اليومية"),
        ("momoda", "الجهات المومدة"),
        ("dict", "قاموس ودليل الجهات"),
        ("report", "التقرير الشامل"),
    ],
    "calc2": [
        ("main", "آلة الحاسبة"),
        ("dowail", "دوايل الحاسبة"),
        ("free", "حساب حر"),
    ],
    "settings": [
        ("users", "تسجيل المستخدمين"),
        ("log", "سجلات المستخدمين"),
        ("notes", "المتابعة والملاحظات"),
        ("identity", "الهوية للمنظمة"),
    ],
}

# (بادئة المسار، مفتاح القسم، باراميتر التاب الداخلي من الرابط/الفورم)
ROUTE_MAP = [
    ("/warehouses", "warehouses_records", "sub"),
    ("/inv6", "warehouses_records", "inv6"),
    ("/tarfea", "tarfea", "sub"),
    ("/tameedat", "tameedat", "tab"),
    ("/rations/tamween", "tamween_rations", None),
    ("/rations/contractor", "contractor_rations", None),
    ("/calc2/free", "calc2", "free"),
    ("/calc2/dowail", "calc2", "dowail"),
    ("/calc2", "calc2", "main"),
    ("/recruits", "mojandeen", None),
    ("/stores", "cold_stores", None),
    ("/stats", "statistics", None),
    ("/health", "health", None),
    ("/letterhead", "letterhead", None),
    ("/occasions", "occasions", None),
    ("/files", "files", None),
    ("/settings", "settings", "sub"),
]

# روابط النظام اللي مش تاب (مايتطلبش صلاحية)
SKIP_PREFIXES = (
    "/static/", "/assistant/", "/context/", "/years/", "/month-copy",
    "/login", "/logout", "/dashboard", "/sections/", "/api/", "/favicon",
)


def section_of(tab_key):
    return (tab_key or "").split(":")[0]


def tab_key_for_request(path, args=None, form=None):
    """يمسك المفتاح الصحيح للطلبات: GET صفحة أو POST إجراء.
    يرجع None لو الرابط مش تاب (نظام/مساعد/ملفات ثابتة)."""
    args = args or {}
    form = form or {}

    def _val(key):
        v = args.get(key)
        if v in (None, "") and form:
            v = form.get(key)
        return v or ""

    if any(path.startswith(p) for p in SKIP_PREFIXES):
        return None
    if path in ("/", "/index", "/dashboard"):
        return "dashboard"
    for prefix, section, sub_param in ROUTE_MAP:
        if path == prefix or path.startswith(prefix + "/"):
            if sub_param is None:
                return section
            sub = _val(sub_param) if sub_param != "sub" else _val("sub")
            if sub_param == "main":      # /calc2 (الرئيسية) → تويب «main»
                sub = "main"
            if sub_param == "inv6":      # /inv6 → تبويب 6 مخازن دايمًا
                sub = "inv6"
            if sub_param == "free" and path.startswith("/calc2/free"):
                sub = "free"
            if sub_param == "dowail" and path.startswith("/calc2/dowail"):
                sub = "dowail"
            sub = sub.strip()
            if sub and sub in dict(SUBTABS.get(section, [])):
                return f"{section}:{sub}"
            if sub:                      # تاب غير معروف → صلاحية القسم
                return section
            # بدون باراميتر: نحاول نفهم التويب من شكل الرابط (فواعل الحفظ مش بتبعت sub)
            sub = _sub_from_path(section, path)
            if sub:
                return f"{section}:{sub}"
            # بدون باراميتر: لو القسم عنده توابت، الصلاحية المطلوبة = القسم كله
            return section
    return None


def _sub_from_path(section, path):
    """التويب الداخلي من شكل المسار — للفواعل (POST) اللي مش بتبعت باراميتر tab/sub."""
    p = path
    if section == "warehouses_records":
        for sub in ("suppliers", "wh1", "wh2", "wh3", "wh4", "wh5"):
            if f"/{sub}" in p:
                return sub
        return None
    if section == "settings":
        for sub in ("users", "log", "notes"):
            if p.startswith(f"/settings/{sub}"):
                return sub
        return None
    if section == "calc2":
        if p.startswith("/calc2/free"):
            return "free"
        if p.startswith("/calc2/dowail"):
            return "dowail"
        return "main"
    if section == "tameedat":
        if p.startswith(("/tameedat/records", "/tameedat/rations",
                         "/tameedat/alerts", "/tameedat/day-file", "/tameedat/print")):
            return "day"
        if p.startswith("/tameedat/entities"):
            return "dict"
        if p.startswith("/tameedat/report"):
            return "report"
        return None
    if section == "tarfea":
        for sub in ("items", "wh1", "wh2", "wh3", "wh5", "store"):
            if f"/{sub}" in p:
                return sub
        return None
    return None


def has_permission(user, tab_key, allowed=None):
    """الـ admin دايمًا. الباقي: مفتاح التاب أو مفتاح القسم."""
    if not user or not tab_key or tab_key == "dashboard":
        return True
    if user.get("role") == "admin":
        return True
    allowed = allowed if allowed is not None else _allowed(user)
    if tab_key in allowed:
        return True
    return section_of(tab_key) in allowed


def _allowed(user):
    from data_access import db_users
    return db_users.get_user_tabs(user["id"])


def section_visible(user, key, allowed=None):
    """القسم يظهر في الشريط الجانبي: صلاحية القسم كله أو تويب واحد على الأقل جواه."""
    if not user or not key or key == "dashboard":
        return True
    if user.get("role") == "admin":
        return True
    allowed = allowed if allowed is not None else _allowed(user)
    if key in allowed:
        return True
    return any(f"{key}:{s}" in allowed for s, _n in SUBTABS.get(key, []))


def first_allowed_sub(user, key, allowed=None):
    """أول تويب مسموح جوه القسم (None = افتراضي القسم مناسب)."""
    if not user or user.get("role") == "admin":
        return None
    allowed = allowed if allowed is not None else _allowed(user)
    if key in allowed:
        return None
    for s, _n in SUBTABS.get(key, []):
        if f"{key}:{s}" in allowed:
            return s
    return None


def allowed_subtabs(user, section):
    """التابات الداخلية المسموحة (لإخفاء التويتات المحجوبة)."""
    subs = [k for k, _n in SUBTABS.get(section, [])]
    if not subs:
        return subs
    if user.get("role") == "admin":
        return subs
    allowed = _allowed(user)
    if section in allowed:
        return subs
    return [s for s in subs if f"{section}:{s}" in allowed]


def perm_tree():
    """شجرة الصلاحيات للعرض: [ {key, name, icon, subs: [(sub, label)]} ]."""
    items = []
    seen = set()
    for s in nav_monthly():
        items.append(s)
        seen.add(s["key"])
    for s in SECTIONS:
        if s["key"] not in seen:
            items.append(s)
            seen.add(s["key"])
    for p in EXTRA_PAGES:
        if p["key"] not in seen:
            items.append(p)
            seen.add(p["key"])
    tree = []
    for s in items:
        tree.append({
            "key": s["key"],
            "name": s["name"],
            "icon": s.get("icon", ""),
            "subs": SUBTABS.get(s["key"], []),
        })
    tree.append({"key": "files", "name": "حصر الملفات", "icon": "🗄️", "subs": []})
    return tree
