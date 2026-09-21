"""Snapshot copying: never aliases files and never copies daily attendance."""
import hashlib
import json
import secrets
from pathlib import Path
from data_access import db_recruits as recruits, db_letterhead as lh, storage, dataguard


def valid_period(year, month):
    if year not in storage.list_years() or not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("اختر سنة موجودة وشهرًا صحيحًا")


def check_periods(source, target):
    valid_period(*source)
    valid_period(*target)
    if source == target:
        raise ValueError("شهر المصدر والوجهة متطابقان")


def selected_rows(source, ids=None):
    rows = recruits.list_recruits(*source)
    if ids is not None:
        rows = [row for row in rows if row["id"] in ids]
    if not rows:
        raise ValueError("لا يوجد مجندون محددون للنسخ")
    return rows


def preview(kind, source, target, ids=None):
    check_periods(source, target)
    if kind == "registry":
        rows = selected_rows(source, ids)
        destination = recruits.list_recruits(*target)
        numbers = {row["mil_no"] for row in destination}
        skip = sum(row["mil_no"] in numbers for row in rows)
        result = {"total": len(rows), "added": len(rows) - skip, "skipped": skip, "replace": False}
    elif kind == "letterhead":
        rows, destination = lh.get_all(*source), lh.get_all(*target)
        if not any(rows.values()):
            raise ValueError("دباجة شهر المصدر فارغة")
        result = {"total": 1, "added": 1, "skipped": 0, "replace": any(destination.values())}
    else:
        raise ValueError("نوع النسخ غير صالح")
    result["fingerprint"] = hashlib.sha256(json.dumps([kind, source, target, rows, destination],
                                                     sort_keys=True).encode()).hexdigest()
    return result


def clone_file(name, source_dir, target_dir, prefix):
    if not name:
        return ""
    if Path(name).name != name:
        raise ValueError("مسار مرفق غير صالح")
    path = source_dir / name
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"مرفق مفقود: {name}؛ لم يكتمل النسخ")
    new_name = f"{prefix}_{secrets.token_hex(4)}{path.suffix.lower()}"
    content = path.read_bytes()
    dataguard.atomic_save(lambda tmp: Path(tmp).write_bytes(content), target_dir / new_name, zip_check=False)
    return new_name


def insert_registry(rows, source_dir, target, preserve_ids=False):
    """Preserve legacy IDs only into an empty registry, keeping old daily links valid."""
    conn = recruits.get_conn(*target)
    files = []
    folder = storage.recruits_dir(*target)
    fields = recruits.FIELDS.split()
    added = skipped = 0
    try:
        conn.execute("BEGIN IMMEDIATE")
        if preserve_ids and conn.execute("SELECT 1 FROM recruits LIMIT 1").fetchone():
            raise ValueError("استيراد السجل القديم متاح لشهر أصل قوته فارغ فقط؛ حتى لا تختلط اليومية")
        for row in rows:
            if conn.execute("SELECT 1 FROM recruits WHERE mil_no=?", (row["mil_no"],)).fetchone():
                skipped += 1
                continue
            data = {key: row.get(key, "") for key in fields}
            for key, prefix in (("photo", "photo"), ("cert_photo", "cert")):
                data[key] = clone_file(data[key], source_dir, folder, prefix)
                if data[key]:
                    files.append(folder / data[key])
            if preserve_ids:
                data["id"] = row["id"]
            keys = list(data)
            conn.execute(f"INSERT INTO recruits ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
                         [data[key] for key in keys])
            added += 1
        conn.commit()
    except Exception:
        conn.rollback()
        for path in files:
            path.unlink(missing_ok=True)
        raise
    finally:
        conn.close()
    return {"added": added, "skipped": skipped}


def copy_letterhead(values, source_dir, target):
    values = dict(values)
    name = clone_file(values.get("logo_file"), source_dir, storage.letterhead_dir(*target), "logo")
    values["logo_file"] = name
    try:
        lh.save(*target, values)
    except Exception:
        if name:
            (storage.letterhead_dir(*target) / name).unlink(missing_ok=True)
        raise
    return {"added": 1, "skipped": 0}


def execute(kind, source, target, fingerprint, ids=None, replace=False):
    plan = preview(kind, source, target, ids)
    if fingerprint != plan["fingerprint"]:
        raise ValueError("تغيّرت البيانات بعد المعاينة؛ أعد معاينة النسخ قبل التأكيد")
    if plan["replace"] and not replace:
        raise ValueError("الوجهة بها دباجة؛ وافق صراحةً على استبدالها أولًا")
    dataguard.create_backup("pre-copy")
    if kind == "registry":
        return insert_registry(selected_rows(source, ids), storage.recruits_dir(*source), target)
    return copy_letterhead(lh.get_all(*source), storage.letterhead_dir(*source), target)
