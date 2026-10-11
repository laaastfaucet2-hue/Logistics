# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""«دفتر 6 مخازن (جرد الأصناف)» — بيانات أيام الجرد جوا قاعدة الشهر.

جدولان صغيران:
- inv6_day: رأس يوم الجرد (الجهة/المخزن/صاحب المعدة + التوقيعات الخمسة) — سطر لليوم.
- inv6_row: أصناف اليوم — لقطة الرصيد الافتراضي (من دفتر ٣ مخازن لحظة الجرد) +
  الموجود الفعلي من واقع الجرد + سعر الوحدة + الحالتين. UNIQUE(day, cycle, item_id).

الرصيد الافتراضي لقطة لحظة الجرد (مستند تاريخي) — مش قيمة محسوبة لحظي.
"""
import json

from core import egtime
from data_access import months

SCHEMA = """
CREATE TABLE IF NOT EXISTS inv6_day (
    day INTEGER PRIMARY KEY,
    sector TEXT NOT NULL DEFAULT '',
    warehouse TEXT NOT NULL DEFAULT '',
    owner_rank TEXT NOT NULL DEFAULT '',
    owner_name TEXT NOT NULL DEFAULT '',
    sig_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inv6_row (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day INTEGER NOT NULL,
    cycle TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    book REAL NOT NULL DEFAULT 0,
    counted REAL NOT NULL DEFAULT 0,
    price REAL NOT NULL DEFAULT 0,
    status_item TEXT NOT NULL DEFAULT 'جيدة',
    status_issue TEXT NOT NULL DEFAULT 'جيدة',
    serial INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (day, cycle, item_id)
);
"""

# التوقيعات الخمسة (تصميم الدفتر): رئيس المصلحة / مدبر المخازن /
# لجنة الجرد (٣ أسطر) / صاحب المعدة / كاتب الشطب
SIG_KEYS = ("chief", "manager", "committee", "owner", "writer")


def _conn(year, month):
    conn = months.get_db(year, month)
    conn.executescript(SCHEMA)
    return conn


def _stamp():
    return egtime.now().isoformat(timespec="seconds")


def _clean_sigs(sigs):
    """تطبيع خريطة التوقيعات: chief/manager/owner/writer = {rank,name}؛ committee = ٣ أسطر."""
    out = {}
    sigs = sigs or {}
    for k in ("chief", "manager", "owner", "writer"):
        v = sigs.get(k) or {}
        out[k] = {
            "rank": " ".join(str(v.get("rank") or "").split()),
            "name": " ".join(str(v.get("name") or "").split()),
            "extra": " ".join(str(v.get("extra") or "").split()),
        }
    lines = sigs.get("committee") or []
    if isinstance(lines, dict):
        lines = [lines.get("rank"), lines.get("name")]
    out["committee"] = [" ".join(str(x or "").split()) for x in list(lines)[:3]]
    while len(out["committee"]) < 3:
        out["committee"].append("")
    return out


def save_day(year, month, day, header, rows):
    """يحفظ يوم جرد كاملًا (رأس + أصناف) — استبدال كامل لليوم."""
    day = int(day)
    h = header or {}
    sigs = _clean_sigs(h.get("sigs"))
    conn = _conn(year, month)
    stamp = _stamp()
    with conn:
        conn.execute(
            "INSERT INTO inv6_day (day, sector, warehouse, owner_rank, owner_name, "
            "sig_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(day) DO UPDATE SET sector=excluded.sector, "
            "warehouse=excluded.warehouse, owner_rank=excluded.owner_rank, "
            "owner_name=excluded.owner_name, sig_json=excluded.sig_json, "
            "updated_at=excluded.updated_at",
            (day, " ".join(str(h.get("sector") or "").split()),
             " ".join(str(h.get("warehouse") or "").split()),
             " ".join(str(h.get("owner_rank") or "").split()),
             " ".join(str(h.get("owner_name") or "").split()),
             json.dumps(sigs, ensure_ascii=False), stamp, stamp))
        conn.execute("DELETE FROM inv6_row WHERE day=?", (day,))
        for r in rows:
            conn.execute(
                "INSERT INTO inv6_row (day, cycle, item_id, name, unit, book, counted, "
                "price, status_item, status_issue, serial, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (day, r["cycle"], int(r["item_id"]), r["name"], r.get("unit") or "",
                 float(r.get("book") or 0), float(r.get("counted") or 0),
                 float(r.get("price") or 0), r.get("status_item") or "جيدة",
                 r.get("status_issue") or "جيدة", int(r.get("serial") or 0),
                 stamp, stamp))
    conn.close()
    return True


def load_day(year, month, day):
    """{header: {..., sigs}, rows: [...]} أو None لو اليوم مش محفوظ."""
    day = int(day)
    conn = _conn(year, month)
    d = conn.execute("SELECT * FROM inv6_day WHERE day=?", (day,)).fetchone()
    if not d:
        conn.close()
        return None
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM inv6_row WHERE day=? ORDER BY serial, id", (day,))]
    conn.close()
    try:
        sigs = json.loads(d["sig_json"] or "{}")
    except (ValueError, TypeError):
        sigs = {}
    header = {
        "day": day,
        "sector": d["sector"], "warehouse": d["warehouse"],
        "owner_rank": d["owner_rank"], "owner_name": d["owner_name"],
        "sigs": _clean_sigs(sigs),
    }
    return {"header": header, "rows": rows}


def list_days(year, month):
    """الأيام المحفوظة مرتبة."""
    conn = _conn(year, month)
    days = [r["day"] for r in conn.execute("SELECT day FROM inv6_day ORDER BY day")]
    conn.close()
    return days


def delete_day(year, month, day):
    day = int(day)
    conn = _conn(year, month)
    with conn:
        conn.execute("DELETE FROM inv6_row WHERE day=?", (day,))
        conn.execute("DELETE FROM inv6_day WHERE day=?", (day,))
    conn.close()
    return True
