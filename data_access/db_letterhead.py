"""The only source of official letterhead/signatures.

📝 الأسطر الأربعة واللوجو: لكل شهر على حدة (month_settings).
✍️ التوقيعان الرسميان (يمين/شمال أسفل الصفحة): على مستوى المنظومة **كلها** ومحفوظان في
`app_settings` داخل `system.db` — قابلان للتعديل من صفحة «الدباجة والتوقيعات»، وأي تعديل
يسري فورًا على كل الشهور وكل ملفات Excel/Word والطباعة (توجيه المستخدم ٠٨/١٠/٢٠٢٦:
كانا مثبّتين نهائيًا — وأصبحا قابلين للتغيير مع القيم الافتراضية نفسها).
"""
from data_access import database, months, storage

KEYS = ["lh_1", "lh_2", "lh_3", "lh_4", "sig_right_rank", "sig_right_name",
        "sig_left_rank", "sig_left_name", "logo_file"]
SIG_KEYS = ["sig_right_rank", "sig_right_name", "sig_left_rank", "sig_left_name"]

# 🏛️ سطور الدباجة الافتراضية (توجيه ٠٦/١٠/٢٠٢٦ — القواعد الذهبية): تُطبَّق تلقائيًا
# إذا لم يسجّل المستخدم سطورًا خاصة بالشهر، فلا يخرج أي ملف محلي بدون دباجة رسمية.
DEFAULT_LETTERHEAD = {
    "lh_1": "وزارة الداخلية",
    "lh_2": "قطاع الأمن المركزي",
    "lh_3": "قطاع وسط سيناء",
    "lh_4": "قسم التعيينات",
}

# ✍️ القيم الافتراضية للتوقيعين — تظهر حتى يعدّلهما المستخدم من الواجهة (بلا فراغ أبدًا):
# يمين الصفحة: المسؤول المباشر — شمالها: جهة الاعتماد.
DEFAULT_SIGNATURES = {
    "sig_right_rank": "رائد",
    "sig_right_name": "مصطفى نصرالله",
    "sig_left_rank": "مقدم",
    "sig_left_name": "اسامة العجرودى",
}


def get_conn(year, month):
    conn = months.get_db(year, month)
    conn.execute("CREATE TABLE IF NOT EXISTS month_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '')")
    return conn


def get_signatures():
    """التوقيعان الرسميان لكل الشهور — تعديل المستخدم يعلو على الافتراضي، ولا فراغ."""
    conn = database.get_conn()
    try:
        marks = ",".join("?" for _ in SIG_KEYS)
        saved = dict(conn.execute(f"SELECT key, value FROM app_settings WHERE key IN ({marks})",
                                  SIG_KEYS))
    finally:
        conn.close()
    values = {}
    for key in SIG_KEYS:
        text = (saved.get(key, "") or "").strip()
        values[key] = text or DEFAULT_SIGNATURES[key]
    return values


def save_signatures(values):
    """يحفظ توقيعي اليمين والشمال على مستوى المنظومة كلها (system.db)."""
    rows = [(key, str(values.get(key) or "").strip()) for key in SIG_KEYS
            if key in values and str(values.get(key) or "").strip()]
    if not rows:
        return
    conn = database.get_conn()
    try:
        with conn:
            conn.executemany("INSERT OR REPLACE INTO app_settings(key,value) VALUES(?,?)", rows)
    finally:
        conn.close()


def get_all(year, month):
    conn = get_conn(year, month)
    try:
        saved = dict(conn.execute("SELECT key, value FROM month_settings"))
    finally:
        conn.close()
    base = {key: (saved.get(key, "") or "").strip() for key in KEYS if key not in SIG_KEYS}
    for key, text in DEFAULT_LETTERHEAD.items():          # الدباجة لا تفرغ أبدًا
        if not base.get(key):
            base[key] = text
    return {**base, **get_signatures()}                    # التوقيعان من مستوى المنظومة


def get_setting(year, month, key):
    return get_all(year, month).get(key, "")


def save(year, month, values):
    """دباجة الشهر (الأسطر + اللوجو) في قاعدة الشهر، والتوقيعان على مستوى المنظومة."""
    month_values = [(key, str(value or "").strip()) for key, value in values.items()
                    if key in KEYS and key not in SIG_KEYS]
    if month_values:
        conn = get_conn(year, month)
        try:
            with conn:
                conn.executemany("INSERT OR REPLACE INTO month_settings(key,value) VALUES(?,?)",
                                 month_values)
        finally:
            conn.close()
    if any(key in values for key in SIG_KEYS):
        save_signatures(values)


def logo_path(year, month):
    name = get_setting(year, month, "logo_file")
    base = storage.letterhead_dir(year, month).resolve()
    if not name or name != __import__('pathlib').Path(name).name:
        return None
    path = base / name
    return path if path.is_file() else None


def template_vars(year, month):
    values = get_all(year, month)
    return {**values, "lh": [values[f"lh_{i}"] for i in range(1, 5)],
            "sig_right": (values["sig_right_rank"], values["sig_right_name"]),
            "sig_left": (values["sig_left_rank"], values["sig_left_name"]),
            "has_logo": bool(logo_path(year, month))}
