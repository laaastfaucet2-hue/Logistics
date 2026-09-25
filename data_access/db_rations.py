# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""طبقة بيانات جداول المقررات (أصناف + مقرر مخصص + تفعيل) — كلها داخل month.db."""
from data_access import months


# ---------- قراءة الأصناف مع تخصيصاتها ----------
def get_items(year, month, section, kind):
    conn = months.get_db(year, month)
    rows = conn.execute(
        "SELECT * FROM ration_items WHERE section=? AND kind=? ORDER BY serial",
        (section, kind)).fetchall()
    custom = {}
    for r in conn.execute(
            "SELECT rc.* FROM ration_custom rc JOIN ration_items ri ON ri.id=rc.item_id "
            "WHERE ri.section=? AND ri.kind=? ORDER BY rc.weekday", (section, kind)):
        custom.setdefault(r["item_id"], []).append(
            {"weekday": r["weekday"], "meal": r["meal"], "qty": r["qty"]})
    conn.close()
    return [dict(r) for r in rows], custom


def get_item(year, month, item_id):
    conn = months.get_db(year, month)
    row = conn.execute("SELECT * FROM ration_items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------- إضافة/تعديل/حذف ----------
def add_item(year, month, section, kind, name, unit, breakfast, lunch, dinner):
    conn = months.get_db(year, month)
    serial = (conn.execute(
        "SELECT COALESCE(MAX(serial),0)+1 s FROM ration_items WHERE section=? AND kind=?",
        (section, kind)).fetchone()["s"])
    conn.execute(
        "INSERT INTO ration_items (section,kind,serial,name,unit,breakfast,lunch,dinner) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (section, kind, serial, name, unit, breakfast, lunch, dinner))
    conn.commit()
    conn.close()


def update_item(year, month, item_id, name, unit, breakfast, lunch, dinner):
    conn = months.get_db(year, month)
    conn.execute(
        "UPDATE ration_items SET name=?, unit=?, breakfast=?, lunch=?, dinner=? WHERE id=?",
        (name, unit, breakfast, lunch, dinner, item_id))
    conn.commit()
    conn.close()


def delete_item(year, month, item_id):
    conn = months.get_db(year, month)
    conn.execute("DELETE FROM ration_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()


# ---------- المقرر المخصص (أيام × وجبات لصنف واحد) ----------
def issuance_map(item, custom_entries):
    """خريطة الصرف لآلة 2 مخازن: {(رقم_اليوم, الوجبة): الكمية}.

    - بلا تخصيص: رقم الفطار/الغداء/العشاء (>0) يُصرف **كل يوم**.
    - مع تخصيص: الخانات المملوءة فقط — حتى لو الرقم العام في الجدول صفر.
    """
    meals = ("breakfast", "lunch", "dinner")

    def positive(value):
        if value in (None, ""):
            return 0.0
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return number if number > 0 else 0.0

    out = {}
    if custom_entries:
        for entry in custom_entries:
            qty = positive(entry.get("qty"))
            if qty:
                out[(int(entry["weekday"]), entry["meal"])] = qty
        return out
    for day in range(7):
        for meal in meals:
            qty = positive(item.get(meal))
            if qty:
                out[(day, meal)] = qty
    return out


def save_custom(year, month, item_id, entries):
    """يستبدل تخصيصات الصنف بقائمة [(weekday, meal, qty)] الجديدة."""
    conn = months.get_db(year, month)
    conn.execute("DELETE FROM ration_custom WHERE item_id=?", (item_id,))
    conn.executemany(
        "INSERT INTO ration_custom (item_id, weekday, meal, qty) VALUES (?,?,?,?)",
        [(item_id, d, m, q) for d, m, q in entries])
    conn.commit()
    conn.close()


# ---------- التفعيل: مقرر واحد فقط لكل قسم ----------
def get_activation(year, month, section):
    conn = months.get_db(year, month)
    row = conn.execute(
        "SELECT kind FROM ration_activation WHERE section=?", (section,)).fetchone()
    conn.close()
    return row["kind"] if row else None


def set_activation(year, month, section, kind):
    conn = months.get_db(year, month)
    conn.execute("INSERT OR REPLACE INTO ration_activation (section, kind) VALUES (?,?)",
                 (section, kind))
    conn.commit()
    conn.close()


# ---------- نسخ المقرر إلى شهر/سنة أخرى (يستبدل الموجود هناك) ----------
def copy_kind(year, month, section, kind, to_year, to_month):
    conn = months.get_db(year, month)
    rows = conn.execute(
        "SELECT serial,name,unit,breakfast,lunch,dinner FROM ration_items "
        "WHERE section=? AND kind=? ORDER BY serial", (section, kind)).fetchall()
    custom_rows = conn.execute(
        "SELECT ri.serial, rc.weekday, rc.meal, rc.qty FROM ration_custom rc "
        "JOIN ration_items ri ON ri.id=rc.item_id WHERE ri.section=? AND ri.kind=?",
        (section, kind)).fetchall()
    conn.close()

    target = months.get_db(to_year, to_month)
    target.execute("DELETE FROM ration_items WHERE section=? AND kind=?", (section, kind))
    for r in rows:
        target.execute(
            "INSERT INTO ration_items (section,kind,serial,name,unit,breakfast,lunch,dinner) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (section, kind, r["serial"], r["name"], r["unit"],
             r["breakfast"], r["lunch"], r["dinner"]))
    id_by_serial = {x["serial"]: x["id"] for x in target.execute(
        "SELECT serial,id FROM ration_items WHERE section=? AND kind=?",
        (section, kind)).fetchall()}
    for c in custom_rows:
        new_id = id_by_serial.get(c["serial"])
        if new_id:
            target.execute(
                "INSERT INTO ration_custom (item_id, weekday, meal, qty) VALUES (?,?,?,?)",
                (new_id, c["weekday"], c["meal"], c["qty"]))
    target.commit()
    target.close()
    return len(rows)


def item_exists(year, month, section, kind, name):
    """منع تكرار اسم الصنف داخل نفس القسم ونفس نوع المقرر."""
    conn = months.get_db(year, month)
    row = conn.execute(
        "SELECT 1 FROM ration_items WHERE section=? AND kind=? AND TRIM(name)=TRIM(?)",
        (section, kind, name)).fetchone()
    conn.close()
    return row is not None


def known_item_names(year, month, section):
    """أسماء أصناف هذا القسم نفسه في هذا الشهر (كل الأنواع) — لاقتراحات الإدخال الذكية.

    فصل تام: صفحة المتعهد تقترح أصناف المتعهد فقط، والتمونيية أصناف التمونيية فقط.
    """
    conn = months.get_db(year, month)
    rows = conn.execute(
        "SELECT DISTINCT name FROM ration_items WHERE section=? ORDER BY name",
        (section,)).fetchall()
    conn.close()
    return [r["name"] for r in rows]


def remember_unit(unit):
    """يحفظ وحدة قياس مخصصة في القاموس المشترك — تظهر في التموين والمتعهد."""
    from data_access import database as db
    db.vocab_add("unit", unit)


def collect_units(year, month):
    """قائمة وحدات موحّدة: الثوابت + ما كُتب في التموين والمتعهد + الوحدات المخصصة.

    مصدر واحد للحقيقة يُعرض في صفحتي المقررات وفي توزيع الجهات.
    """
    from core.config import UNITS
    from data_access import database as db
    seen = []

    def add(value):
        value = (value or "").strip()
        if value and value not in seen:
            seen.append(value)

    for unit in UNITS:
        add(unit)
    for unit in db.vocab_list("unit"):
        add(unit)
    conn = months.get_db(year, month)
    for sql in (
        "SELECT DISTINCT unit FROM ration_items WHERE TRIM(COALESCE(unit,'')) != ''",
        "SELECT DISTINCT unit FROM entity_items WHERE TRIM(COALESCE(unit,'')) != ''",
    ):
        try:
            for row in conn.execute(sql):
                add(row["unit"])
        except Exception:
            pass
    conn.close()
    return seen
