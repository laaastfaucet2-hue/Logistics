# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""سجل المجندين العاملين بوحدة التعيينات — «أصل القوة» (سجل عالمي لا يتكرر شهريًا).

قاعدة مستقلة database/recruits.db: بيانات المجند + محافظته/مدينته (قابلة للإضافة)
+ صوره وشهادته الصحية. اليومية الشهرية تعيش في قاعدة الشهر (db_attendance).
"""
import sqlite3
from pathlib import Path

DB_PATH = Path("database/recruits.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS recruits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    mil_no TEXT NOT NULL UNIQUE,
    service_start TEXT DEFAULT '',
    service_end TEXT DEFAULT '',
    governorate TEXT DEFAULT '',
    city TEXT DEFAULT '',
    address TEXT DEFAULT '',
    photo TEXT DEFAULT '',
    has_cert INTEGER DEFAULT 0,
    cert_date TEXT DEFAULT '',
    cert_expiry TEXT DEFAULT '',
    cert_photo TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vocab (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,          -- gov | city
    value TEXT NOT NULL,
    UNIQUE(kind, value)
);
"""

# محافظات مصر الـ٢٧ + أشهر مدن كل محافظة (ويقدر المستخدم يضيف أي اسم ناقص)
GOV_CITIES = {
    "القاهرة": ["مدينة نصر", "المعادي", "حلوان", "شبرا", "عين شمس", "الزمالك", "مصر الجديدة", "الشروق", "بدر", "١٥ مايو", "العاصمة الإدارية الجديدة"],
    "الجيزة": ["الهرم", "فيصل", "إمبابة", "العجوزة", "الدقي", "6 أكتوبر", "الشيخ زايد", "البدرشين", "الصف", "أطفيح", "أبو النمرس", "الواحات البحرية"],
    "الإسكندرية": ["سموحة", "المنتزه", "العجمي", "برج العرب", "العامرية", "ميامي", "المندرة", "الإبراهيمية", "كرموز", "الدخيلة"],
    "القليوبية": ["بنها", "شبرا الخيمة", "القناطر الخيرية", "طوخ", "قليوب", "الخانكة", "كفر شكر", "العبور"],
    "الدقهلية": ["المنصورة", "طلخا", "ميت غمر", "دكرنس", "أجا", "السنبلاوين", "بلقاس", "شربين", "نبروه", "جمصة"],
    "الشرقية": ["الزقازيق", "بلبيس", "العاشر من رمضان", "منيا القمح", "فاقوس", "أبو كبير", "ههيا", "ديرب نجم", "الإبراهيمية", "مشتول السوق"],
    "الغربية": ["طنطا", "المحلة الكبرى", "كفر الزيات", "زفتى", "السنطة", "بسيون", "سمنود", "قطور"],
    "المنوفية": ["شبين الكوم", "السادات", "منوف", "سرس الليان", "أشمون", "الباجور", "بركة السبع", "تلا", "قويسنا"],
    "البحيرة": ["دمنهور", "كفر الدوار", "رشيد", "إدكو", "أبو المطامير", "أبو حمص", "إيتاي البارود", "حوش عيسى", "وادي النطرون", "النوبارية"],
    "كفر الشيخ": ["كفر الشيخ", "دسوق", "فوه", "مطوبس", "بيلا", "سيدي سالم", "الحامول", "بلطيم", "الرياض", "قلين"],
    "دمياط": ["دمياط", "دمياط الجديدة", "رأس البر", "فارسكور", "كفر سعد", "الزرقا", "عزبة البرج"],
    "بورسعيد": ["بورسعيد", "بورفؤاد"],
    "الإسماعيلية": ["الإسماعيلية", "فايد", "القنطرة شرق", "القنطرة غرب", "التل الكبير", "أبو صوير", "القصاصين"],
    "السويس": ["السويس", "الأربعين", "عتاقة", "الجناين"],
    "شمال سيناء": ["العريش", "الشيخ زويد", "رفح", "بئر العبد", "الحسنة", "نخل"],
    "جنوب سيناء": ["شرم الشيخ", "دهب", "نويبع", "طابا", "سانت كاترين", "أبو رديس", "رأس سدر"],
    "الفيوم": ["الفيوم", "الفيوم الجديدة", "طامية", "سنورس", "إطسا", "إبشواي", "يوسف الصديق"],
    "بني سويف": ["بني سويف", "بني سويف الجديدة", "الواسطى", "ناصر", "إهناسيا", "ببا", "سمسطا", "الفشن"],
    "المنيا": ["المنيا", "المنيا الجديدة", "ملوي", "دير مواس", "مغاغة", "بني مزار", "مطاي", "سمالوط", "أبو قرقاص"],
    "أسيوط": ["أسيوط", "أسيوط الجديدة", "ديروط", "منفلوط", "القوصية", "أبنوب", "أبو تيج", "الغنايم", "ساحل سليم", "البداري"],
    "سوهاج": ["سوهاج", "سوهاج الجديدة", "أخميم", "جرجا", "البلينا", "المراغة", "المنشأة", "طما", "طهطا", "دار السلام"],
    "قنا": ["قنا", "نجع حمادي", "دشنا", "الوقف", "قفط", "أبو تشت", "فرشوط", "قوص", "نقادة"],
    "الأقصر": ["الأقصر", "الأقصر الجديدة", "إسنا", "أرمنت", "الطود", "الزينية", "البياضية", "القرنة"],
    "أسوان": ["أسوان", "أسوان الجديدة", "إدفو", "كوم أمبو", "نصر النوبة", "دراو", "السباعية", "أبو سمبل"],
    "البحر الأحمر": ["الغردقة", "رأس غارب", "سفاجا", "القصير", "مرسى علم", "الشلاتين", "حلايب", "مرسى حميرة"],
    "الوادي الجديد": ["الخارجة", "الداخلة", "الفرافرة", "باريس", "بلاط", "موط"],
    "مطروح": ["مرسى مطروح", "الحمام", "العلمين", "الضبعة", "سيدي براني", "السلوم", "سيوة", "النجيلة"],
}


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 8000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    for gov, cities in GOV_CITIES.items():
        conn.execute("INSERT OR IGNORE INTO vocab(kind, value) VALUES('gov', ?)", (gov,))
        for city in cities:
            conn.execute("INSERT OR IGNORE INTO vocab(kind, value) VALUES('city', ?)", (city,))
    conn.commit()
    conn.close()


# ==================== القواميس (محافظات/مدن) ====================
def vocab(kind):
    conn = get_conn()
    rows = conn.execute(
        "SELECT value FROM vocab WHERE kind=? ORDER BY id", (kind,)).fetchall()
    conn.close()
    return [r["value"] for r in rows]


def add_vocab(kind, value):
    value = (value or "").strip()
    if not value:
        return
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO vocab(kind, value) VALUES(?, ?)", (kind, value))
    conn.commit()
    conn.close()


# ==================== المجندون ====================
FIELDS = ("name mil_no service_start service_end governorate city address "
          "photo has_cert cert_date cert_expiry cert_photo")


def list_recruits():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM recruits ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recruit(rid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM recruits WHERE id=?", (rid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def find_by(name=None, mil_no=None):
    conn = get_conn()
    if mil_no:
        row = conn.execute("SELECT * FROM recruits WHERE mil_no=?", (mil_no,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM recruits WHERE name=?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_recruit(data):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO recruits (name, mil_no, service_start, service_end, governorate, city,"
        " address, photo, has_cert, cert_date, cert_expiry, cert_photo, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'))",
        (data.get("name", ""), data.get("mil_no", ""), data.get("service_start", ""),
         data.get("service_end", ""), data.get("governorate", ""), data.get("city", ""),
         data.get("address", ""), data.get("photo", ""), int(data.get("has_cert") or 0),
         data.get("cert_date", ""), data.get("cert_expiry", ""), data.get("cert_photo", "")))
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    # أي محافظة/مدينة جديدة كتبها المستخدم تنضم للقواميس
    add_vocab("gov", data.get("governorate"))
    add_vocab("city", data.get("city"))
    return rid


def update_recruit(rid, data):
    conn = get_conn()
    conn.execute(
        "UPDATE recruits SET name=?, mil_no=?, service_start=?, service_end=?, governorate=?,"
        " city=?, address=?, photo=?, has_cert=?, cert_date=?, cert_expiry=?, cert_photo=?"
        " WHERE id=?",
        (data.get("name", ""), data.get("mil_no", ""), data.get("service_start", ""),
         data.get("service_end", ""), data.get("governorate", ""), data.get("city", ""),
         data.get("address", ""), data.get("photo", ""), int(data.get("has_cert") or 0),
         data.get("cert_date", ""), data.get("cert_expiry", ""), data.get("cert_photo", ""), rid))
    conn.commit()
    conn.close()
    add_vocab("gov", data.get("governorate"))
    add_vocab("city", data.get("city"))


def delete_recruit(rid):
    conn = get_conn()
    conn.execute("DELETE FROM recruits WHERE id=?", (rid,))
    conn.commit()
    conn.close()


# ==================== حالة الشهادة الصحية والخدمة ====================
def cert_state(recruit, today):
    """ok | soon(<=٣٠ يوم) | expired | none"""
    if not recruit.get("has_cert") or not recruit.get("cert_expiry"):
        return "none"
    try:
        from datetime import date as _d
        y, m, d = (int(x) for x in recruit["cert_expiry"].split("-"))
        delta = (_d(y, m, d) - today).days
    except (ValueError, AttributeError):
        return "none"
    if delta < 0:
        return "expired"
    return "soon" if delta <= 30 else "ok"


def days_to_discharge(recruit, today):
    """أيام متبقية على انتهاء الخدمة أو None."""
    end = recruit.get("service_end") or ""
    try:
        from datetime import date as _d
        y, m, d = (int(x) for x in end.split("-"))
        return (_d(y, m, d) - today).days
    except (ValueError, AttributeError):
        return None
