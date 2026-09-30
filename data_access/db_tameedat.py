# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""طبقة بيانات «التاميدات» — كلها داخل month.db للشهر النشط فقط.

قواعد العمل:
- الشهر وحدة العزل: القاموس والسجلات والملحقات محلية لهذا الشهر تمامًا،
  وتبدأ فاضية في كل شهر — لا نسخ تلقائي بين الشهور.
- القاموس الشهري «قاموس ودليل الجهات»: يبدأ فارغًا؛ أي جهة غير معروفة تُضاف
  من شاشة التأميدات نفسها بعد تنبيه المستخدم، عند الحفظ الفعلي فقط.
- تعدد السجلات مسموح: نفس الجهة في نفس اليوم يمكن أن يكون لها أكثر من تأميدة
  مستقلة، وكل عملية لصق تُنشئ سجلًا جديدًا منفصلًا.
- الجهات الملحقة تُحفظ مع سجل التأميدة نفسه وتُدمج أعدادها في إجمالي تأميدتها.
- راغبين الجهة (ضباط/أفراد) اختيارية في القاموس؛ المقارنة عند الحفظ تنبيه فقط
  ولا تمنع التسجيل، ولا تشمل المجندين أبدًا.
"""
from core import egtime
from data_access import months

SCHEMA = """
CREATE TABLE IF NOT EXISTS tameed_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'شرطية',
    rag_officers INTEGER,
    rag_individuals INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    serial INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tameed_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day INTEGER NOT NULL,
    day_to INTEGER,
    entity_id INTEGER NOT NULL REFERENCES tameed_entities(id) ON DELETE CASCADE,
    entity_name TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'شرطية',
    officers INTEGER NOT NULL DEFAULT 0,
    individuals INTEGER NOT NULL DEFAULT 0,
    recruits INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tameed_records_day ON tameed_records(day);
CREATE INDEX IF NOT EXISTS idx_tameed_records_entity ON tameed_records(entity_id);
CREATE TABLE IF NOT EXISTS tameed_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL REFERENCES tameed_records(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT '',
    officers INTEGER NOT NULL DEFAULT 0,
    individuals INTEGER NOT NULL DEFAULT 0,
    recruits INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tameed_save_tokens (
    token TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
"""

BASE_TYPES = ("شرطية", "حربية")          # «أخرى» = أي نوع حر خارج هذين
FILTER_LABELS = {"all": "الكل", "police": "شرطية", "war": "حربية", "other": "أخرى"}


def _conn(year, month):
    conn = months.get_db(year, month)
    conn.executescript(SCHEMA)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(tameed_records)")}
    if "day_to" not in columns:
        conn.execute("ALTER TABLE tameed_records ADD COLUMN day_to INTEGER")
        conn.commit()
    return conn


def _stamp():
    return egtime.now().isoformat(timespec="seconds")


def _clean_count(value):
    """عدد صحيح غير سالب؛ القيم التالفة تُعامل كصفر (التحقق الحقيقي في routes)."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def type_group(entity_type):
    """فئة الفلتر: police / war / other — أي نص حر يقع في «أخرى»."""
    text = (entity_type or "").strip()
    if text == "شرطية":
        return "police"
    if text == "حربية":
        return "war"
    return "other"


def matches_filter(entity_type, filter_key):
    """filter_key: all / police / war / other"""
    if filter_key in (None, "", "all"):
        return True
    return type_group(entity_type) == filter_key


# ======================================================================
# قاموس ودليل الجهات (شهري)
# ======================================================================
def list_entities(year, month):
    conn = _conn(year, month)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM tameed_entities ORDER BY serial, id").fetchall()]
    conn.close()
    return rows


def entity_names(year, month):
    return [e["name"] for e in list_entities(year, month)]


def get_entity(year, month, entity_id):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM tameed_entities WHERE id=?",
                       (entity_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def find_entity_by_name(year, month, name):
    """بحث بالاسم بعد تطبيع المسافات — لاكتشاف «جهة غير مسجلة» قبل الحفظ."""
    target = " ".join((name or "").split())
    conn = _conn(year, month)
    row = conn.execute(
        "SELECT * FROM tameed_entities WHERE TRIM(name)=? LIMIT 1", (target,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_entity(year, month, name, entity_type, rag_officers=None,
               rag_individuals=None, notes=""):
    """يضيف جهة للقاموس الشهري ويرجع معرّفها. الراغبون اختياريون (None = غير مسجل)."""
    conn = _conn(year, month)
    serial = conn.execute(
        "SELECT COALESCE(MAX(serial),0)+1 s FROM tameed_entities").fetchone()["s"]
    cur = conn.execute(
        "INSERT INTO tameed_entities (name, entity_type, rag_officers, rag_individuals,"
        " notes, serial, created_at) VALUES (?,?,?,?,?,?,?)",
        (" ".join(name.split()), (entity_type or "").strip() or "شرطية",
         rag_officers, rag_individuals, (notes or "").strip(), serial, _stamp()))
    conn.commit()
    entity_id = cur.lastrowid
    conn.close()
    return entity_id


def update_entity(year, month, entity_id, name, entity_type,
                  rag_officers=None, rag_individuals=None, notes=""):
    """تعديل بيانات جهة — وتحديث لقطة الاسم/النوع في سجلات شهرها حتى تظل متسقة."""
    conn = _conn(year, month)
    clean_name = " ".join(name.split())
    clean_type = (entity_type or "").strip() or "شرطية"
    with conn:
        conn.execute(
            "UPDATE tameed_entities SET name=?, entity_type=?, rag_officers=?,"
            " rag_individuals=?, notes=? WHERE id=?",
            (clean_name, clean_type, rag_officers, rag_individuals,
             (notes or "").strip(), entity_id))
        conn.execute(
            "UPDATE tameed_records SET entity_name=?, entity_type=? WHERE entity_id=?",
            (clean_name, clean_type, entity_id))
    conn.close()


def entity_record_count(year, month, entity_id):
    """عدد تأميدات الشهر للجهة — كجهة رئيسية أو كجهة ملحقة بنفس الاسم."""
    conn = _conn(year, month)
    name = conn.execute("SELECT name FROM tameed_entities WHERE id=?",
                        (entity_id,)).fetchone()
    main = conn.execute(
        "SELECT COUNT(*) c FROM tameed_records WHERE entity_id=?",
        (entity_id,)).fetchone()["c"]
    attached = 0
    if name:
        attached = conn.execute(
            "SELECT COUNT(DISTINCT a.record_id) c FROM tameed_attachments a"
            " JOIN tameed_records r ON r.id = a.record_id"
            " WHERE a.name=? AND r.entity_id!=?", (name["name"], entity_id)
        ).fetchone()["c"]
    conn.close()
    return main + attached


def delete_entity(year, month, entity_id):
    """حذف جهة من قاموس الشهر + كل تأميداتها وملحقاتها في هذا الشهر فقط.

    يرجع عدد سجلات التأميدات التي حُذفت معها (للرسالة التحذيرية بعد التنفيذ).
    """
    conn = _conn(year, month)
    count = conn.execute(
        "SELECT COUNT(*) c FROM tameed_records WHERE entity_id=?",
        (entity_id,)).fetchone()["c"]
    with conn:
        conn.execute("DELETE FROM tameed_entities WHERE id=?", (entity_id,))
    conn.close()
    return count


# ======================================================================
# سجلات التأميدات اليومية
# ======================================================================
def _attach_many(conn, record_id, attachments):
    for att in attachments:
        name = " ".join((att.get("name") or "").split())
        if not name:
            continue
        conn.execute(
            "INSERT INTO tameed_attachments (record_id, name, entity_type,"
            " officers, individuals, recruits) VALUES (?,?,?,?,?,?)",
            (record_id, name, (att.get("entity_type") or "").strip(),
             _clean_count(att.get("officers")), _clean_count(att.get("individuals")),
             _clean_count(att.get("recruits"))))


def _row_to_record(conn, row):
    record = dict(row)
    record["day_to"] = record.get("day_to") or record["day"]
    record["range_days"] = max(1, record["day_to"] - record["day"] + 1)
    record["attachments"] = [dict(a) for a in conn.execute(
        "SELECT * FROM tameed_attachments WHERE record_id=? ORDER BY id",
        (record["id"],)).fetchall()]
    att_tot = sum(a["officers"] + a["individuals"] + a["recruits"]
                  for a in record["attachments"])
    record["attached_total"] = att_tot
    record["grand_total"] = record["total"] + att_tot
    return record


def add_record(year, month, day, entity, officers, individuals, recruits,
               notes="", attachments=(), day_to=None):
    """يسجّل تأميدة داخل الشهر النشط؛ day_to النهاية حين تُفعّل مدة زمنية."""
    conn = _conn(year, month)
    stamp = _stamp()
    total = _clean_count(officers) + _clean_count(individuals) + _clean_count(recruits)
    with conn:
        cur = conn.execute(
            "INSERT INTO tameed_records (day, day_to, entity_id, entity_name, entity_type,"
            " officers, individuals, recruits, total, notes, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (int(day), int(day_to) if day_to else None, entity["id"], entity["name"],
             entity["entity_type"], _clean_count(officers), _clean_count(individuals),
             _clean_count(recruits), total, (notes or "").strip(), stamp, stamp))
        _attach_many(conn, cur.lastrowid, attachments)
        record_id = cur.lastrowid
    conn.close()
    return record_id


def update_record(year, month, record_id, day, officers, individuals, recruits,
                  notes="", attachments=(), day_to=None):
    """تعديل تأميدة: المدة والأعداد والملاحظات والملحقات (الجهة نفسها لا تتغير)."""
    conn = _conn(year, month)
    total = _clean_count(officers) + _clean_count(individuals) + _clean_count(recruits)
    with conn:
        conn.execute(
            "UPDATE tameed_records SET day=?, day_to=?, officers=?, individuals=?,"
            " recruits=?, total=?, notes=?, updated_at=? WHERE id=?",
            (int(day), int(day_to) if day_to else None,
             _clean_count(officers), _clean_count(individuals),
             _clean_count(recruits), total, (notes or "").strip(), _stamp(), record_id))
        conn.execute("DELETE FROM tameed_attachments WHERE record_id=?", (record_id,))
        _attach_many(conn, record_id, attachments)
    conn.close()


def claim_save_token(year, month, token):
    """مقاومة الإرسال المكرر (ضغطتان/إعادة إرسال): يرجع True إذا كان التوكن جديدًا."""
    token = (token or "").strip()[:64]
    if not token:
        return True
    conn = _conn(year, month)
    try:
        with conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO tameed_save_tokens (token, created_at)"
                " VALUES (?,?)", (token, _stamp()))
            conn.execute(
                "DELETE FROM tameed_save_tokens WHERE created_at < datetime('now','-1 day')")
        return cur.rowcount == 1
    finally:
        conn.close()


def get_record(year, month, record_id):
    conn = _conn(year, month)
    row = conn.execute("SELECT * FROM tameed_records WHERE id=?",
                       (record_id,)).fetchone()
    record = _row_to_record(conn, row) if row else None
    conn.close()
    return record


def delete_record(year, month, record_id):
    conn = _conn(year, month)
    with conn:
        conn.execute("DELETE FROM tameed_attachments WHERE record_id=?", (record_id,))
        conn.execute("DELETE FROM tameed_records WHERE id=?", (record_id,))
    conn.close()


def copy_record(year, month, record_id, to_day):
    """لصق نسخة منفصلة من التأميدة في يوم آخر من الشهر نفسه — بنفس مدتها الزمنية."""
    source = get_record(year, month, record_id)
    if not source:
        return None
    entity = {"id": source["entity_id"], "name": source["entity_name"],
              "entity_type": source["entity_type"]}
    span = source["range_days"] - 1
    end_day = min(to_day + span, egtime.days_in_month(year, month))
    return add_record(year, month, to_day, entity, source["officers"],
                      source["individuals"], source["recruits"], source["notes"],
                      source["attachments"], day_to=end_day if end_day > to_day else None)


def _list_records(conn, where="", params=()):
    rows = conn.execute(
        "SELECT * FROM tameed_records " + where +
        " ORDER BY day, entity_name, id", params).fetchall()
    return [_row_to_record(conn, r) for r in rows]


def records_for_day(year, month, day, filter_key="all", query=""):
    """تأميدات يوم محدد — تضم السارية المفعّلة بمدة زمنية تغطي هذا اليوم."""
    conn = _conn(year, month)
    records = _list_records(
        conn, "WHERE day<=? AND COALESCE(day_to, day)>=?", (int(day), int(day)))
    conn.close()
    needle = " ".join((query or "").split())
    out = []
    for rec in records:
        if not matches_filter(rec["entity_type"], filter_key):
            continue
        if needle and needle not in rec["entity_name"]:
            continue
        out.append(rec)
    return out


def day_counts(year, month):
    """عدد التأميدات السارية في كل يوم من الشهر — لعلامات التقويم."""
    conn = _conn(year, month)
    try:
        rows = conn.execute(
            "SELECT day, COALESCE(day_to, day) AS day_to"
            " FROM tameed_records").fetchall()
        counts = {}
        for row in rows:
            for day in range(row["day"], row["day_to"] + 1):
                counts[day] = counts.get(day, 0) + 1
        return counts
    finally:
        conn.close()


def month_records(year, month):
    """كل سجلات الشهر بالملحقات — أساس اللقطة المحلية والتقارير."""
    conn = _conn(year, month)
    records = _list_records(conn)
    conn.close()
    return records


# ======================================================================
# الجهات المومدة بالشهر الحالي (ملخص لكل جهة)
# ======================================================================
def month_summary(year, month, filter_key="all"):
    """صف لكل جهة شاركت في التميد — ومنها الملحقات تعامل كجهة مستقلة تمامًا.

    القاعدة الجديدة بطلب المستخدم: الجهة الملحقة جهة قائمة بنفسها في الإحصائيات
    والمومدة والقاموس، لا تُدمج في جهتها الأم؛ أما عرض اليوم نفسه فيبقى تأميدة
    واحدة بإجمالي مدمج — التأميدات غير الجهات.
    الإجماليات = الأعداد × أيام السريان الفعلية (المدة الزمنية تزيدهما بعدول).
    """
    records = month_records(year, month)
    entities = {e["id"]: e for e in list_entities(year, month)}
    days_in_month = egtime.days_in_month(year, month)
    grouped = {}

    def _fresh_row(key, name, entity_type, kind, entity_id=None):
        return {"key": key, "entity_id": entity_id, "name": name,
                "entity_type": entity_type, "kind": kind,
                "records": 0, "days": set(), "participations": [],
                "officers": 0, "individuals": 0, "recruits": 0}

    def _participation(rec, attachment=None):
        """بطاقة مشاركة واحدة: تأميدة رقم كذا والأيام بالتواريخ الدقيقة."""
        part = {"record_id": rec["id"], "day": rec["day"],
                "day_to": rec["day_to"], "range_days": rec["range_days"],
                "parent_name": rec["entity_name"]}
        if attachment is not None:
            part["attachment"] = attachment["name"]
        return part

    for rec in records:
        span = range(rec["day"], rec["day_to"] + 1)
        weight = rec["range_days"]
        if matches_filter(rec["entity_type"], filter_key):
            row = grouped.setdefault(
                ("entity", rec["entity_id"]),
                _fresh_row(("entity", rec["entity_id"]),
                           entities.get(rec["entity_id"], {}).get("name",
                                                                  rec["entity_name"]),
                           rec["entity_type"], "entity", rec["entity_id"]))
            row["records"] += 1
            row["days"].update(span)
            row["officers"] += rec["officers"] * weight
            row["individuals"] += rec["individuals"] * weight
            row["recruits"] += rec["recruits"] * weight
            row["participations"].append(_participation(rec))
        for att in rec["attachments"]:
            att_type = (att["entity_type"] or rec["entity_type"]).strip()
            if not matches_filter(att_type, filter_key):
                continue
            key = ("attachment", att["name"].strip().casefold())
            row = grouped.setdefault(
                key, _fresh_row(key, att["name"], att_type or "—", "attachment"))
            row["records"] += 1
            row["days"].update(span)
            row["officers"] += _clean_count(att["officers"]) * weight
            row["individuals"] += _clean_count(att["individuals"]) * weight
            row["recruits"] += _clean_count(att["recruits"]) * weight
            row["participations"].append(_participation(rec, att))
    summary = []
    for row in grouped.values():
        active_days = len(row["days"])
        total = row["officers"] + row["individuals"] + row["recruits"]
        row.update(
            total_officers=row["officers"], total_individuals=row["individuals"],
            total_recruits=row["recruits"], grand_total=total,
            active_days=active_days, days_in_month=days_in_month,
            avg_officers=row["officers"] / active_days if active_days else 0,
            avg_individuals=row["individuals"] / active_days if active_days else 0,
            avg_recruits=row["recruits"] / active_days if active_days else 0,
        )
        summary.append(row)
    summary.sort(key=lambda r: (r["kind"] != "entity", r["name"]))
    totals = {
        "entities": len(summary),
        "records": sum(r["records"] for r in summary if r["kind"] == "entity"),
        "officers": sum(r["total_officers"] for r in summary),
        "individuals": sum(r["total_individuals"] for r in summary),
        "recruits": sum(r["total_recruits"] for r in summary),
        "grand": sum(r["grand_total"] for r in summary),
        "active_days": len({d for r in summary for d in r["days"]}),
    }
    return summary, totals

# ======================================================================
# إحصاءات تبويب القاموس — مصدر موحد للجدول ولمرآة الإكسل
# ======================================================================
def dict_month_stats(year, month):
    """مصدر الإحصاء الموحد لتبويب القاموس (قاعدة «إحصاء واحد» — دفعة ٢٣/٠٩):
    لكل جهة متوسطاتها (ضباط/أفراد/مجندين) وعدد مرات تأميدها وتواريخها (من – إلى)
    وما إن كانت ملحقة في أي تسجيل وعلى مَن — الملحقة جهة مستقلة بإحصاء خاص.

    يُستهلك من routes (جدول القاموس) ومن مرآة Excel المحلية (tameedat_fs) معًا.

    يرجع قاموسًا بمفتاح id الجهة: own (صف المشاركة الرئيسية)، att (صف الملحقة)،
    parts (كل المشاركات مرتبة)، records_total، att_count، att_parents.
    """
    full_summary, _ = month_summary(year, month)
    entities = list_entities(year, month)
    by_name = {}
    for row in full_summary:
        bucket = by_name.setdefault(row["name"], {"own": None, "att": None})
        if row["kind"] == "attachment":
            bucket["att"] = row
        else:
            bucket["own"] = row
    stats = {}
    for entity in entities:
        pair = by_name.get(entity["name"], {"own": None, "att": None})
        own, att = pair["own"], pair["att"]
        parts = sorted((own["participations"] if own else []) +
                       (att["participations"] if att else []),
                       key=lambda p: (p["day"], p["record_id"]))
        att_parts = [p for p in parts if p.get("attachment")]
        stats[entity["id"]] = {
            "own": own, "att": att, "parts": parts,
            "records_total": len(parts),
            "att_count": len(att_parts),
            "att_parents": sorted({p.get("parent_name", "") for p in att_parts
                                   if p.get("parent_name")}),
        }
    return stats



