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
CREATE TABLE IF NOT EXISTS ragh_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL REFERENCES tameed_entities(id) ON DELETE CASCADE,
    day INTEGER NOT NULL,
    approver_rank TEXT NOT NULL DEFAULT '',
    approver_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'موثقة',
    submit_rank TEXT NOT NULL DEFAULT '',
    submit_name TEXT NOT NULL DEFAULT '',
    submit_grade TEXT NOT NULL DEFAULT '',
    doc_rank TEXT NOT NULL DEFAULT '',
    doc_name TEXT NOT NULL DEFAULT '',
    doc_roster_name TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    UNIQUE(entity_id, day)
);
"""

CATEGORIES = (("officers", "الضباط"), ("individuals", "فرد"))
CATEGORY_KEYS = {k for k, _ in CATEGORIES}

# الرتب المعتمدة — من الأقدمية الأعلى للأدنى (توجيه المستخدم ٣٠/٠٩/٢٠٢٦:
# الضباط من اللواء إلى الملازم، والأفراد بنفس مبدأ الأقدمية)
RANKS = {
    "officers": ["فريق أول", "فريق", "لواء", "عميد", "عقيد", "مقدم",
                 "رائد", "نقيب", "ملازم أول", "ملازم"],
    # رتب الأفراد — كل الرتب بكل الدرجات حسب قانون هيئة الشرطة (١٠ لسنة ١٩٧١
    # وتعديلاته حتى ٢٠٢٤): أمناء → مساعدون → مراقبون ومناديب → ضباط صف وجنود
    # → معاونو الأمن (الدرجة الجديدة ٢٠٢١) — بالأسماء المختصرة زي قائمة الضباط
    "individuals": [
        "أمين ممتاز أول", "أمين ممتاز ثان", "أمين ممتاز",
        "أمين أول", "أمين ثان", "أمين ثالث",
        "مساعد ممتاز", "مساعد أول", "مساعد ثان", "مساعد ثالث",
        "مراقب ممتاز", "مراقب أول", "مراقب ثان", "مراقب ثالث",
        "مندوب ممتاز", "مندوب أول", "مندوب ثان", "مندوب ثالث",
        "رئيس رقباء", "رقيب أول", "رقيب", "عريف", "جندي أول", "جندي",
        "معاون ممتاز أول", "معاون ممتاز ثان", "معاون ممتاز",
        "معاون أول", "معاون ثان", "معاون ثالث",
        "مجند",
    ],
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
    _migrate_approvals(conn)
    return conn


def _migrate_approvals(conn):
    """إضافة أعمدة توقيتات الاعتماد الجديدة للملفات القديمة (١٠/١٠/٢٠٦)."""
    have = {r[1] for r in conn.execute("PRAGMA table_info(ragh_approvals)")}
    for col in ("submit_rank", "submit_name", "submit_grade",
                "doc_rank", "doc_name", "doc_roster_name"):
        if col not in have:
            conn.execute(f"ALTER TABLE ragh_approvals ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
    conn.commit()


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


def find_person(year, month, entity_id, category, full_name, rank=None):
    """بحث بالاسم المطابق داخل فئة جهة — لتجنب التكرار وللإضافة السريعة من الزرار.
    ١٤/١٠: لو اتحددت رتبة، الشخص بيتعرّف بـ «الاسم + الرتبة» — نفس الاسم برتبة
    مختلفة = شخص تاني (والمسجل من غير رتبة يُعتبر نفسه وتتكمّل رتبته)."""
    name = (full_name or "").strip()
    if not name:
        return None
    rank = (rank or "").strip() if rank is not None else ""
    conn = _conn(year, month)
    if rank:
        row = conn.execute(
            "SELECT * FROM ragh_persons WHERE entity_id = ? AND category = ? "
            "AND TRIM(full_name) = ? AND (TRIM(rank) = ? OR TRIM(rank) = '')",
            (entity_id, _clean_category(category), name, rank)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM ragh_persons WHERE entity_id = ? AND category = ? "
            "AND TRIM(full_name) = ?", (entity_id, _clean_category(category), name)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_person(year, month, entity_id, category, full_name, rank="",
               excluded=False, exclude_note=""):
    """إضافة عضو للقوة — يرجع (person_id, created)؛ التكرار يرجع الموجود دون إضافة.
    ١٤/١٠: التكرار بالأسماء + الرتبة — «محمد أحمد محمد» برتبة مقدم وبرتبة عقيد
    شخصان مختلفان؛ والاسم المسجل من غير رتبة تتكمّل رتبته بدل ما يتكرر."""
    name = (full_name or "").strip()
    rank = (rank or "").strip()
    category = _clean_category(category)
    if not name:
        raise ValueError("الاسم مطلوب")
    existing = find_person(year, month, entity_id, category, name, rank=rank)
    if existing:
        if rank and not (existing.get("rank") or "").strip():
            update_person(year, month, existing["id"], name, rank=rank)
        return existing["id"], False
    conn = _conn(year, month)
    cur = conn.execute(
        "INSERT INTO ragh_persons (entity_id, category, rank, full_name, excluded, "
        "exclude_note, serial, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (entity_id, category, rank, name,
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


def active_day_entities(year, month):
    """{entity_id: [أيام فيها سجل رغبة]} — لإعادة بناء الملفات المحلية."""
    conn = _conn(year, month)
    out = {}
    for row in conn.execute(
            "SELECT p.entity_id, d.day FROM ragh_daily d "
            "JOIN ragh_persons p ON p.id = d.person_id"):
        out.setdefault(row["entity_id"], set()).add(int(row["day"]))
    conn.close()
    return {k: sorted(v) for k, v in out.items()}

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


def copy_day(year, month, entity_id, from_day, to_day, source="copy"):
    """نسخ كشف راغب يوم كامل ليوم تانى لنفس الجهة (قرار المستخدم ١٠/١٠/٢٠٢٦).

    ينقل حالة كل عضو (راغب ✓ / غير راغب) من يوم المصدر ويكتبها في يوم الهدف
    بوضع clear-and-set (يحوّل كشف الهدف لما هو كشف المصدر تمامًا).
    يرجع عدد الأعضاء المنقولين.
    """
    from_day = max(1, min(31, int(from_day)))
    to_day = max(1, min(31, int(to_day)))
    conn = _conn(year, month)
    persons = [dict(r) for r in conn.execute(
        "SELECT id, category FROM ragh_persons WHERE entity_id = ? ORDER BY category, serial",
        (entity_id,))]
    src_state = {}
    for row in conn.execute(
            "SELECT person_id, willing FROM ragh_daily WHERE day = ? AND person_id IN "
            "(SELECT id FROM ragh_persons WHERE entity_id = ?)", (from_day, entity_id)):
        src_state[row["person_id"]] = bool(row["willing"])
    for p in persons:
        conn.execute(
            "INSERT INTO ragh_daily (person_id, day, willing, source, updated_at) "
            "VALUES (?,?,?,?,?) ON CONFLICT(person_id, day) "
            "DO UPDATE SET willing = excluded.willing, source = excluded.source, "
            "updated_at = excluded.updated_at",
            (p["id"], to_day, 1 if src_state.get(p["id"]) else 0, source, _stamp()))
    # إلغاء رغبة أي عضو في يوم الهدف لم يكن في كشف المصدر (clear-and-set كامل)
    src_ids = ",".join(str(p["id"]) for p in persons) or "0"
    conn.execute(
        "DELETE FROM ragh_daily WHERE day = ? AND willing = 1 AND person_id NOT IN "
        f"({src_ids}) AND person_id IN (SELECT id FROM ragh_persons WHERE entity_id = ?)",
        (to_day, entity_id))
    conn.commit()
    conn.close()
    return len(persons)


def save_approval(year, month, entity_id, day,
                  submit_rank="", submit_name="", submit_grade="",
                  doc_rank="", doc_name="", doc_roster_name="",
                  status="موثقة"):
    """حفظ توقيتات اعتماد كشف اليوم (تصميم الاسكرين شوت ١٠/١٠):
    فورم «مقدم قسم الراغبين» (رتبة + اسم عروني + رتبة) + فورم «وثيقة القطاع»
    (رتبة + اسم عروني + اسم بالكشف) — واحد لجهة/يوم ويظهر أسفل التسلسل."""
    day = max(1, min(31, int(day)))
    s_rank = (submit_rank or "").strip()
    s_name = " ".join((submit_name or "").split())
    s_grade = (submit_grade or "").strip()
    d_rank = (doc_rank or "").strip()
    d_name = " ".join((doc_name or "").split())
    d_roster = (doc_roster_name or "").strip()
    conn = _conn(year, month)
    conn.execute(
        "INSERT INTO ragh_approvals (entity_id, day, approver_rank, approver_name, "
        "status, submit_rank, submit_name, submit_grade, doc_rank, doc_name, "
        "doc_roster_name, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(entity_id, day) DO UPDATE SET "
        "approver_rank = excluded.approver_rank, "
        "approver_name = excluded.approver_name, status = excluded.status, "
        "submit_rank = excluded.submit_rank, submit_name = excluded.submit_name, "
        "submit_grade = excluded.submit_grade, doc_rank = excluded.doc_rank, "
        "doc_name = excluded.doc_name, doc_roster_name = excluded.doc_roster_name, "
        "updated_at = excluded.updated_at",
        (entity_id, day, s_grade or s_rank, s_name or d_name,
         (status or "موثقة").strip(),
         s_rank, s_name, s_grade, d_rank, d_name, d_roster, _stamp()))
    conn.commit()
    conn.close()


def get_approval(year, month, entity_id, day):
    """آخر اعتماد محفوظ ليوم الجهة — كل الحقول أو None."""
    conn = _conn(year, month)
    row = conn.execute(
        "SELECT approver_rank, approver_name, status, submit_rank, submit_name, "
        "submit_grade, doc_rank, doc_name, doc_roster_name, updated_at "
        "FROM ragh_approvals WHERE entity_id = ? AND day = ?",
        (entity_id, int(day))).fetchone()
    conn.close()
    if not row:
        return None
    return {"rank": row["approver_rank"], "name": row["approver_name"],
            "status": row["status"], "updated_at": row["updated_at"],
            "submit_rank": row["submit_rank"], "submit_name": row["submit_name"],
            "submit_grade": row["submit_grade"], "doc_rank": row["doc_rank"],
            "doc_name": row["doc_name"], "doc_roster_name": row["doc_roster_name"]}


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


def month_willing_split(year, month, entity_id=None):
    """راغبو كل يوم مفصولين فئة: {day: {officers, individuals}} — استعلام واحد للشهر.

    يخدم جدول تنبيهات الشهر كله (لا يوم واحد) بلا استعلام لكل يوم.
    """
    conn = _conn(year, month)
    sql = ("SELECT d.day AS day, p.category AS category, COUNT(*) AS c "
           "FROM ragh_daily d JOIN ragh_persons p ON p.id = d.person_id "
           "WHERE d.willing = 1")
    params = []
    if entity_id:
        sql += " AND p.entity_id = ?"
        params.append(entity_id)
    sql += " GROUP BY d.day, p.category"
    out = {}
    for row in conn.execute(sql, params):
        item = out.setdefault(row["day"], {"officers": 0, "individuals": 0})
        key = "officers" if row["category"] == "officers" else "individuals"
        item[key] = row["c"]
    conn.close()
    return out


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


def month_meal_days(year, month, entity_id=None, category=None):
    """أيام الوجبات الفعلية لكل عضو: {person_id: [day, ...]} مرتبة تصاعديًا."""
    conn = _conn(year, month)
    sql = ("SELECT d.person_id, d.day FROM ragh_daily d "
           "JOIN ragh_persons p ON p.id = d.person_id "
           "WHERE d.willing = 1")
    params = []
    if entity_id:
        sql += " AND p.entity_id = ?"
        params.append(entity_id)
    if category in CATEGORY_KEYS:
        sql += " AND p.category = ?"
        params.append(category)
    sql += " ORDER BY d.person_id, d.day"
    out = {}
    for row in conn.execute(sql, params):
        out.setdefault(row["person_id"], []).append(int(row["day"]))
    conn.close()
    return out


def month_meals(year, month, entity_id=None, category=None):
    """عدد وجبات الشهر لكل عضو (راغب اليوم = وجبة): {person_id: count}."""
    return {person_id: len(days) for person_id, days in
            month_meal_days(year, month, entity_id, category).items()}


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
