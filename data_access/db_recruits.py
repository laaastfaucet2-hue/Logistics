"""Monthly recruits registry. All callers must supply year and month explicitly."""
from data_access import months
from core.recruit_vocab import GOV_CITIES
from core import arabic_numbers as arnum, dates

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

def get_conn(year, month):
    conn = months.get_db(year, month)
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='recruits'").fetchone():
        conn.executescript(SCHEMA)
        for gov, cities in GOV_CITIES.items():
            conn.execute("INSERT OR IGNORE INTO vocab(kind, value) VALUES('gov', ?)", (gov,))
            conn.executemany("INSERT OR IGNORE INTO vocab(kind, value) VALUES('city', ?)",
                             [(city,) for city in cities])
        conn.commit()
    return conn


# ==================== القواميس (محافظات/مدن) ====================
def vocab(year, month, kind):
    conn = get_conn(year, month)
    rows = conn.execute(
        "SELECT value FROM vocab WHERE kind=? ORDER BY id", (kind,)).fetchall()
    conn.close()
    return [r["value"] for r in rows]


def add_vocab(year, month, kind, value):
    value = (value or "").strip()
    if not value:
        return
    conn = get_conn(year, month)
    conn.execute("INSERT OR IGNORE INTO vocab(kind, value) VALUES(?, ?)", (kind, value))
    conn.commit()
    conn.close()


def govs_for_ui(year, month):
    """المحافظات الـ٢٧ دائمًا + أي محافظة كتبها المستخدم (قاموس مشترك أو شهري)."""
    from data_access import database as db
    seen = list(GOV_CITIES.keys())
    extra = []
    for src in (db.vocab_list("gov"), vocab(year, month, "gov")):
        for name in src:
            if name and name not in seen and name not in extra:
                extra.append(name)
    return seen + extra


def places_by_gov(year, month):
    """خريطة محافظة → مدن/قرى (المرجع + المضاف يدويًا). المفتاح '' للأسماء بلا محافظة."""
    from data_access import database as db
    mapping = {gov: list(cities) for gov, cities in GOV_CITIES.items()}
    for parent, places in db.vocab_places_map().items():
        mapping.setdefault(parent, [])
        for place in places:
            if place not in mapping[parent]:
                mapping[parent].append(place)
    mapping.setdefault("", [])
    for city in vocab(year, month, "city"):
        if city not in mapping[""]:
            mapping[""].append(city)
    return mapping


# ==================== المجندون ====================
FIELDS = ("name mil_no service_start service_end governorate city address "
          "photo has_cert cert_date cert_expiry cert_photo")


def list_recruits(year, month):
    conn = get_conn(year, month)
    rows = conn.execute("SELECT * FROM recruits ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recruit(year, month, rid):
    conn = get_conn(year, month)
    row = conn.execute("SELECT * FROM recruits WHERE id=?", (rid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def find_by(year, month, name=None, mil_no=None):
    conn = get_conn(year, month)
    if mil_no:
        row = conn.execute("SELECT * FROM recruits WHERE mil_no=?", (mil_no,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM recruits WHERE name=?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_recruit(year, month, data):
    conn = get_conn(year, month)
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
    _remember_place(year, month, data)
    return rid


def update_recruit(year, month, rid, data):
    conn = get_conn(year, month)
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
    _remember_place(year, month, data)


def _remember_place(year, month, data):
    from data_access import database as db
    gov = data.get("governorate")
    city = data.get("city")
    add_vocab(year, month, "gov", gov)
    add_vocab(year, month, "city", city)
    db.vocab_add("gov", gov)
    db.vocab_add("place", city, parent=gov or "")


def delete_recruit(year, month, rid):
    conn = get_conn(year, month)
    has_attendance = conn.execute("SELECT 1 FROM sqlite_master WHERE name='attendance'").fetchone()
    if has_attendance and conn.execute("SELECT 1 FROM attendance WHERE recruit_id=? LIMIT 1", (rid,)).fetchone():
        conn.close()
        raise ValueError("لا يمكن حذف مجند له يوميات في هذا الشهر؛ للحفاظ على الكشوف السابقة")
    conn.execute("DELETE FROM recruits WHERE id=?", (rid,))
    conn.commit()
    conn.close()


# ==================== حالة الشهادة الصحية والخدمة ====================
def cert_state(recruit, today):
    """ok | soon(<=٣٠ يوم) | expired | none"""
    if not recruit.get("has_cert") or not recruit.get("cert_expiry"):
        return "none"
    try:
        expiry = dates.parse_date(recruit["cert_expiry"])
        if expiry is None:
            return "none"
        delta = (expiry - today).days
    except (ValueError, AttributeError):
        return "none"
    if delta < 0:
        return "expired"
    return "soon" if delta <= 30 else "ok"


def days_to_discharge(recruit, today):
    """أيام متبقية على انتهاء الخدمة أو None."""
    end = recruit.get("service_end") or ""
    try:
        parsed = dates.parse_date(end)
        return (parsed - today).days if parsed else None
    except (ValueError, AttributeError):
        return None
