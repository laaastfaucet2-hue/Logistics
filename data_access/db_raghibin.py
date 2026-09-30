# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""طبقة بيانات قسم «الراغبين» — داخل month.db للشهر النشط فقط.

قواعد العمل:
- الجهات = قاموس التأميدات نفسه (tameed_entities): مصدر واحد للربط ١٠٠٪
  بين زرار التأميدة وتاب الراغبين — أي تعديل من الجهتين على نفس الداتا.
- ragh_persons: قوة الجهة المعتمدة بالأسماء والرتب (ضباط/أفراد) مع حالة
  الاستثناء «غير راغب» وسببه — وهو الأساس لكل الكشوف.
- ragh_daily: تسجيل الراغبين يوم بيوم (وجبة واحدة لليوم — قرار المستخدم
  ٣٠/٠٩/٢٠٢٦): person راغب في يوم = وجبة واحدة في كشف الشهر.
- نسخ القوة بين الشهور/السنوات ينسخ الأسماء والرتب والحالات بلا تسجيلات يومية،
  ويطابق الجهة بالاسم (أرقام id تختلف بين قواميس الشهور).
"""
from core import arabic_numbers as arnum
from core import egtime
from data_access import months
from data_access import db_tameedat as db_tameedat   # SCHEMA قاموس الجهات — أساس الربط

SCHEMA = """
CREATE TABLE IF NOT EXISTS ragh_persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL REFERENCES tameed_entities(id) ON DELETE CASCADE,
    category TEXT NOT NULL DEFAULT 'officers',   -- officers ضباط / individuals أفراد
    rank TEXT NOT NULL DEFAULT '',               -- الرتبة (رائد / نقيب / مجند ...)
    full_name TEXT NOT NULL,
    excluded INTEGER NOT NULL DEFAULT 0,         -- ١ = غير راغب (مستثنى)
    exclude_note TEXT NOT NULL DEFAULT '',       -- سبب الاستثناء
    serial INTEGER NOT NULL DEFAULT 0,           -- الترتيب داخل الفئة
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ragh_persons_entity ON ragh_persons(entity_id, category);
CREATE TABLE IF NOT EXISTS ragh_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES ragh_persons(id) ON DELETE CASCADE,
    day INTEGER NOT NULL,                        -- ١..٣١
    willing INTEGER NOT NULL DEFAULT 1,          -- ١ راغب / ٠ لا
    source TEXT NOT NULL DEFAULT 'manual',       -- manual من التاب / tamida من الزرار
    updated_at TEXT NOT NULL,
    UNIQUE(person_id, day)
);
CREATE INDEX IF NOT EXISTS idx_ragh_daily_day ON ragh_daily(day);
"""

CATEGORIES = (("officers", "الضباط"), ("individuals", "الأفراد والصف"))
CATEGORY_KEYS = {k for k, _ in CATEGORIES}

# الرتب المعتمدة — من الأقدمية الأعلى للأدنى (توجيه المستخدم ٣٠/٠٩/٢٠٢٦:
# الضباط من اللواء إلى الملازم، والأفراد بنفس مبدأ الأقدمية)
RANKS = {
    "officers": ["فريق أول", "فريق", "لواء", "عميد", "عقيد", "مقدم",
                 "رائد", "نقيب", "ملازم أول", "ملازم"],
    "individuals": ["مساعد أول", "مساعد", "رئيس رقباء", "رقيب أول", "رقيب",
                    "عريف", "جندي أول", "جندي", "مجند"],
}
ALL_RANKS = RANKS["officers"] + RANKS["individuals"]


def _norm_rank(text):
    """توحيد نص الرتبة (همزات الألف ومسافات) لمطابقة القوائم."""
    t = (text or "").strip().replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    return " ".join(t.split())


def rank_weight(category, rank):
    """وزن الرتبة داخل فئتها: ٠ = الأقدمية الأعلى؛ غير المعروفة آخر الفئة."""
    ranks = [_norm_rank(r) for r in RANKS.get(category, [])]
    key = _norm_rank(rank)
    return ranks.index(key) if key in ranks else len(ranks) + 1


def _conn(year, month):
    conn = months.get_db(year, month)
    # قاموس التأميدات أساس الربط (FK) — يُضمن وجوده قبل جداول الراغبين
    conn.executescript(db_tameedat.SCHEMA)
    conn.executescript(SCHEMA)
    return conn


def _stamp():
    return egtime.now().isoformat(timespec="seconds")


def _clean_category(value):
    return value if value in CATEGORY_KEYS else "officers"


def _next_serial(conn, entity_id, category):
    row = conn.execute(
        "SELECT COALESCE(MAX(serial), 0) + 1 FROM ragh_persons "
        "WHERE entity_id = ? AND category = ?", (entity_id, category)).fetchone()
    return int(row[0])


# ======================================================================
# قوة الجهة (ragh_persons)
# ======================================================================
def list_persons(year, month, entity_id=None, category=None, query="", excluded=None):
    """قوة جهة (أو كل الجهات) — ترتيب الفئة ثم مسلسل الاسم.

    query يبحث في الاسم والرتبة؛ excluded=True/False يفلتر المستثنين/الراغبين فقط.
    """
    conn = _conn(year, month)
    sql = ("SELECT p.*, e.name AS entity_name, e.entity_type AS entity_type "
           "FROM ragh_persons p JOIN tameed_entities e ON e.id = p.entity_id WHERE 1=1")
    params = []
    if entity_id:
        sql += " AND p.entity_id = ?"
        params.append(entity_id)
    if category in CATEGORY_KEYS:
        sql += " AND p.category = ?"
        params.append(category)
    if excluded is not None:
        sql += " AND p.excluded = ?"
        params.append(1 if excluded else 0)
    query = (query or "").strip()
    if query:
        sql += " AND (p.full_name LIKE ? OR p.rank LIKE ?)"
        like = f"%{query}%"
        params.extend((like, like))
    sql += " ORDER BY p.entity_id, p.category DESC, p.serial, p.id"
    rows = [dict(r) for r in conn.execute(sql, params)]
    conn.close()

    def _key(person):
        # الضباط قبل الأفراد، وداخل الفئة بالأقدمية ثم مسلسل الإضافة
        return (person["entity_id"], 0 if person["category"] == "officers" else 1,
                rank_weight(person["category"], person["rank"]),
                person["serial"], person["id"])

    rows.sort(key=_key)
    return rows


def get_person(year, month, person_id):
    conn = _conn(year, month)
    row = conn.execute(
        "SELECT p.*, e.name AS entity_name FROM ragh_persons p "
        "JOIN tameed_entities e ON e.id = p.entity_id WHERE p.id = ?",
        (person_id,)).fetchone()
    return dict(row) if row else None


def find_person(year, month, entity_id, category, full_name):
    """بحث بالاسم المطابق داخل فئة جهة — لتجنب التكرار وللإضافة السريعة من الزرار."""
    name = (full_name or "").strip()
    if not name:
        return None
    conn = _conn(year, month)
    row = conn.execute(
        "SELECT * FROM ragh_persons WHERE entity_id = ? AND category = ? "
        "AND TRIM(full_name) = ?", (entity_id, _clean_category(category), name)).fetchone()
    return dict(row) if row else None


def add_person(year, month, entity_id, category, full_name, rank="",
               excluded=False, exclude_note=""):
    """إضافة عضو للقوة — يرجع (person_id, created)؛ التكرار يرجع الموجود دون إضافة."""
    name = (full_name or "").strip()
    category = _clean_category(category)
    if not name:
        raise ValueError("الاسم مطلوب")
    existing = find_person(year, month, entity_id, category, name)
    if existing:
        return existing["id"], False
    conn = _conn(year, month)
    cur = conn.execute(
        "INSERT INTO ragh_persons (entity_id, category, rank, full_name, excluded, "
        "exclude_note, serial, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (entity_id, category, (rank or "").strip(), name,
         1 if excluded else 0, (exclude_note or "").strip(),
         _next_serial(conn, entity_id, category), _stamp()))
    conn.commit()
    person_id = cur.lastrowid
    conn.close()
    return person_id, True


def update_person(year, month, person_id, full_name, rank="", exclude_note=None):
    """تعديل الاسم والرتبة؛ exclude_note تحديث اختياري (None = تركه كما هو)."""
    name = (full_name or "").strip()
    if not name:
        raise ValueError("الاسم مطلوب")
    conn = _conn(year, month)
    if exclude_note is None:
        conn.execute("UPDATE ragh_persons SET full_name = ?, rank = ? WHERE id = ?",
                     (name, (rank or "").strip(), person_id))
    else:
        conn.execute(
            "UPDATE ragh_persons SET full_name = ?, rank = ?, exclude_note = ? WHERE id = ?",
            (name, (rank or "").strip(), (exclude_note or "").strip(), person_id))
    conn.commit()
    conn.close()


def set_excluded(year, month, person_id, excluded, note=""):
    """تعليم «غير راغب» أو إرجاع الاسم للقوة.

    الاستثناء يسقط تسجيلاته اليومية كلها (غير الراغب لا يُحسب في أي وجبة) —
    والإرجاع للقوة لا يستعيدها (يعاد تسجيلها يدويًا).
    """
    conn = _conn(year, month)
    conn.execute("UPDATE ragh_persons SET excluded = ?, exclude_note = ? WHERE id = ?",
                 (1 if excluded else 0, (note or "").strip(), person_id))
    if excluded:
        conn.execute("DELETE FROM ragh_daily WHERE person_id = ?", (person_id,))
    conn.commit()
    conn.close()


def set_note(year, month, person_id, note):
    """تحرير ملاحظة الاسم مباشرة (من غير تغيير حالة الرغبة/الاستثناء)."""
    conn = _conn(year, month)
    conn.execute("UPDATE ragh_persons SET exclude_note = ? WHERE id = ?",
                 ((note or "").strip(), person_id))
    conn.commit()
    conn.close()


def delete_person(year, month, person_id):
    conn = _conn(year, month)
    conn.execute("DELETE FROM ragh_persons WHERE id = ?", (person_id,))
    conn.commit()
    conn.close()


def entity_force_counts(year, month, entity_id=None):
    """ملخص القوة: لكل جهة {officers, individuals, excluded} — للعدادات والتحذيرات."""
    conn = _conn(year, month)
    sql = ("SELECT entity_id, category, SUM(excluded) AS excluded_count, COUNT(*) AS total "
           "FROM ragh_persons")
    params = []
    if entity_id:
        sql += " WHERE entity_id = ?"
        params.append(entity_id)
    sql += " GROUP BY entity_id, category"
    out = {}
    for row in conn.execute(sql, params):
        item = out.setdefault(row["entity_id"], {
            "officers": 0, "individuals": 0, "officers_excluded": 0, "individuals_excluded": 0})
        key = "officers" if row["category"] == "officers" else "individuals"
        item[key] = row["total"]
        item[f"{key}_excluded"] = row["excluded_count"] or 0
    conn.close()
    return out


# ======================================================================
# تسجيل الراغبين اليومي (ragh_daily) — وجبة واحدة لليوم
# ======================================================================
def set_daily(year, month, person_id, day, willing, source="manual"):
    """تسجيل/إلغاء رغبة عضو في يوم — upsert بحالة person_day الواحدة."""
    day = max(1, min(31, int(day)))
    conn = _conn(year, month)
    conn.execute(
        "INSERT INTO ragh_daily (person_id, day, willing, source, updated_at) "
        "VALUES (?,?,?,?,?) ON CONFLICT(person_id, day) "
        "DO UPDATE SET willing = excluded.willing, source = excluded.source, "
        "updated_at = excluded.updated_at",
        (person_id, day, 1 if willing else 0, source, _stamp()))
    conn.commit()
    conn.close()


def day_state(year, month, day, entity_id=None):
    """حالة يوم كامل: {person_id: willing} للجهة (أو كل الجهات) — لبناء قائمة اليوم."""
    conn = _conn(year, month)
    sql = ("SELECT d.person_id, d.willing FROM ragh_daily d "
           "JOIN ragh_persons p ON p.id = d.person_id WHERE d.day = ?")
    params = [day]
    if entity_id:
        sql += " AND p.entity_id = ?"
        params.append(entity_id)
    out = {row["person_id"]: bool(row["willing"]) for row in conn.execute(sql, params)}
    conn.close()
    return out

def set_day_category(year, month, entity_id, day, category, person_ids, source="manual"):
    """تسجيل فئة كاملة في يوم: المرسل هم الراغبون بالأسماء (المربعات المملوءة).

    clear-and-set: من يُرسل صار راغبًا، وأي عضو آخر من نفس الجهة والفئة كان
    راغبًا في اليوم ويغيب عن القائمة يُلغى رغبته — المربعات هي الكشف الكامل.
    يرجع (عدد المسجلين، عدد الملغين).
    """
    day = max(1, min(31, int(day)))
    wanted = {int(pid) for pid in person_ids}
    conn = _conn(year, month)
    for pid in wanted:
        conn.execute(
            "INSERT INTO ragh_daily (person_id, day, willing, source, updated_at) "
            "VALUES (?,?,?,?,?) ON CONFLICT(person_id, day) "
            "DO UPDATE SET willing = 1, source = excluded.source, "
            "updated_at = excluded.updated_at",
            (pid, day, 1, source, _stamp()))
    if wanted:
        cur = conn.execute(
            "DELETE FROM ragh_daily WHERE day = ? AND willing = 1 AND person_id NOT IN "
            f"({','.join('?' for _ in wanted)}) "
            "AND person_id IN (SELECT id FROM ragh_persons WHERE entity_id = ? AND category = ?)",
            [day, *wanted, entity_id, _clean_category(category)])
    else:   # مفيش راغبين مرسلين: إلغاء كل راغبي الجهة/الفئة في اليوم
        cur = conn.execute(
            "DELETE FROM ragh_daily WHERE day = ? AND willing = 1 "
            "AND person_id IN (SELECT id FROM ragh_persons WHERE entity_id = ? AND category = ?)",
            [day, entity_id, _clean_category(category)])
    removed = cur.rowcount if cur.rowcount > 0 else 0
    conn.commit()
    conn.close()
    return len(wanted), removed


def range_mismatch_text(year, month, entity_id, day, day_to, officers, individuals):
    """فحص «عدم مطابقة الأسماء وتجاهل النقص» لمدة التأميدة: تنبيه فقط عند
    زيادة الراغبين (بالأسماء) عن أعداد التأميدة — النقص يُتجاهل (قرار المستخدم)."""
    persons = list_persons(year, month, entity_id=entity_id, excluded=False)
    problems = []
    for d in range(day, (day_to or day) + 1):
        state = day_state(year, month, d, entity_id)
        willing_o = sum(1 for p in persons
                        if p["category"] == "officers" and state.get(p["id"]))
        willing_i = sum(1 for p in persons
                        if p["category"] == "individuals" and state.get(p["id"]))
        day_txt = arnum.to_arabic_indic(str(d))
        if officers is not None and willing_o > officers:
            problems.append(f"يوم {day_txt}: راغبو الضباط ({arnum.to_arabic_indic(str(willing_o))}) "
                            f"أكثر من التأميدة ({arnum.to_arabic_indic(str(officers))})")
        if individuals is not None and willing_i > individuals:
            problems.append(f"يوم {day_txt}: راغبو الأفراد ({arnum.to_arabic_indic(str(willing_i))}) "
                            f"أكثر من التأميدة ({arnum.to_arabic_indic(str(individuals))})")
    if not problems:
        return None
    return "تنبيه الراغبين (عدم مطابقة): " + " — ".join(problems[:6]) +            (" — ومدة أخرى" if len(problems) > 6 else "") + " — تم الحفظ رغم ذلك"


def day_willing_counts(year, month, entity_id=None):
    """عدد الراغبين (ضباط+أفراد) في كل يوم: {day: count} — لتقويم التاب اليومي."""
    conn = _conn(year, month)
    sql = ("SELECT d.day, COUNT(*) AS c FROM ragh_daily d "
           "JOIN ragh_persons p ON p.id = d.person_id WHERE d.willing = 1")
    params = []
    if entity_id:
        sql += " AND p.entity_id = ?"
        params.append(entity_id)
    sql += " GROUP BY d.day"
    out = {row["day"]: row["c"] for row in conn.execute(sql, params)}
    conn.close()
    return out


def month_meals(year, month, entity_id=None, category=None):
    """عدد وجبات الشهر لكل عضو (راغب اليوم = وجبة): {person_id: count}."""
    conn = _conn(year, month)
    sql = ("SELECT d.person_id, COUNT(*) AS meals FROM ragh_daily d "
           "JOIN ragh_persons p ON p.id = d.person_id "
           "WHERE d.willing = 1")
    params = []
    if entity_id:
        sql += " AND p.entity_id = ?"
        params.append(entity_id)
    if category in CATEGORY_KEYS:
        sql += " AND p.category = ?"
        params.append(category)
    sql += " GROUP BY d.person_id"
    out = {row["person_id"]: row["meals"] for row in conn.execute(sql, params)}
    conn.close()
    return out


def copy_force(year, month, target_year, target_month, entity_ids=None):
    """نسخ قوة الجهات (الأسماء والرتب والحالات) لشهر/سنة آخر — بلا تسجيلات يومية.

    يطابق الجهة بالاسم في قاموس الشهر الهدف وينشئها إن لم توجد (بنفس النوع).
    يرجع (عدد الجهات المنسوخة, عدد الأسماء المنسوخة).
    """
    source = _conn(year, month)
    sql = "SELECT * FROM tameed_entities"
    params = []
    if entity_ids:
        marks = ",".join("?" for _ in entity_ids)
        sql += f" WHERE id IN ({marks})"
        params = list(entity_ids)
    entities = [dict(r) for r in source.execute(sql, params)]
    for entity in entities:
        entity["_persons"] = [dict(r) for r in source.execute(
            "SELECT * FROM ragh_persons WHERE entity_id = ? ORDER BY category, serial",
            (entity["id"],))]
    source.close()          # قراءة المصدر كاملة ثم إغلاقه — كل شهر اتصاله المستقل

    copied_names = 0
    copied_entities = 0
    for entity in entities:
        target = _conn(target_year, target_month)
        trow = target.execute("SELECT id FROM tameed_entities WHERE name = ?",
                              (entity["name"],)).fetchone()
        if trow:
            target_entity_id = trow["id"]
        else:
            cur = target.execute(
                "INSERT INTO tameed_entities (name, entity_type, serial, created_at) "
                "VALUES (?,?,?,?)",
                (entity["name"], entity["entity_type"] or "شرطية",
                 _next_entity_serial(target), _stamp()))
            target_entity_id = cur.lastrowid
        copied_entities += 1
        for person in entity["_persons"]:
            exists = target.execute(
                "SELECT 1 FROM ragh_persons WHERE entity_id = ? AND category = ? "
                "AND TRIM(full_name) = ?",
                (target_entity_id, person["category"], person["full_name"])).fetchone()
            if exists:
                continue
            target.execute(
                "INSERT INTO ragh_persons (entity_id, category, rank, full_name, excluded, "
                "exclude_note, serial, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (target_entity_id, person["category"], person["rank"], person["full_name"],
                 person["excluded"], person["exclude_note"], person["serial"], _stamp()))
            copied_names += 1
        target.commit()
        target.close()
    return copied_entities, copied_names


def _next_entity_serial(target_conn):
    row = target_conn.execute(
        "SELECT COALESCE(MAX(serial), 0) + 1 FROM tameed_entities").fetchone()
    return int(row[0])
