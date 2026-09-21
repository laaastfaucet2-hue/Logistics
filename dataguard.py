# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""طبقة حماية البيانات (قاعدة ١٣):
- كتابة ذرّية: أي ملف بيانات يُكتب إلى ملف مؤقت ثم يُستبدل ذرّيًا — مستحيل ملف نصف-مكتوب.
- فحص سلامة: قواعد SQLite بـ quick_check، والإكسل/الوورد بفحص ZIP.
- نسخ احتياطية ZIP في database/backups/ (محلية فقط — لا تُرفع لجيتهاب) مع تدوير تلقائي.
- حارس تشغيل: يحجز أي ملف تالف جانبًا ويسترجع آخر نسخة سليمة تلقائيًا.
"""
import os
import re
import sqlite3
import threading
import time
import zipfile
from pathlib import Path

DATA_DIR = Path("database")
BACKUP_DIR = DATA_DIR / "backups"
KEEP_N = 40                       # أقصى عدد نسخ محفوظة قبل التدوير
_LOCK = threading.Lock()
_NAME_RE = re.compile(r"^backup_\d{4}-\d{2}-\d{2}_\d{6}(_\d+)?_[a-z-]+\.zip$")

REASON_LABELS = {
    "manual": "نسخة يدوية",
    "write": "تلقائي بعد تعديل",
    "boot": "عند تشغيل النظام",
    "pre-restore": "أمان قبل استرجاع",
}


# ==================== مسارات أساسية ====================
def backup_dir():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def data_files():
    """كل ملفات البيانات (قواعد + إكسل + دباجة) عدا النسخ الاحتياطية والملفات المؤقتة."""
    if not DATA_DIR.exists():
        return []
    out = []
    for p in sorted(DATA_DIR.rglob("*")):
        if not p.is_file():
            continue
        if "backups" in p.relative_to(DATA_DIR).parts:
            continue
        if p.name.endswith(("-wal", "-shm", ".tmp")) or ".corrupt-" in p.name:
            continue
        out.append(p)
    return out


def valid_name(name):
    """يمنع أي مسار غريب (حماية من Directory Traversal)."""
    return bool(name) and bool(_NAME_RE.match(name))


# ==================== الكتابة الذرّية ====================
def atomic_save(writer, path, zip_check=True):
    """يكتب عبر ملف مؤقت ثم استبدال ذرّي. writer دالة تستقبل مسار الملف المؤقت.
    zip_check يتحقق من سلامة ملفات الإكسل/الوورد (ZIP) قبل الاعتماد."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("{}.tmp-{}".format(path.name, os.getpid()))
    with _LOCK:
        try:
            writer(str(tmp))
            if zip_check:
                with zipfile.ZipFile(str(tmp)) as zf:
                    bad = zf.testzip()
                    if bad:
                        raise IOError("ملف تالف بعد الكتابة: {}".format(bad))
            os.replace(str(tmp), str(path))   # استبدال ذرّي — القديم لا يضيع إلا بعد اكتمال الجديد
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
    return path


def _atomic_write_bytes(path, data):
    atomic_save(lambda t: _write_bytes(t, data), path, zip_check=False)


def _write_bytes(target, data):
    with open(target, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


# ==================== فحص السلامة ====================
def _checkpoint_all():
    """يدمج أي بيانات عالقة في WAL داخل ملفات .db قبل أخذ النسخة."""
    for p in DATA_DIR.rglob("*.db"):
        if "backups" in p.relative_to(DATA_DIR).parts:
            continue
        try:
            conn = sqlite3.connect(str(p))
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except sqlite3.Error:
            pass


def verify_file(path):
    """يرجع (سليم?, رسالة خطأ أو '')."""
    path = Path(path)
    if not path.exists():
        return False, "الملف غير موجود"
    if path.stat().st_size == 0:
        return False, "ملف فارغ"
    name = path.name.lower()
    try:
        if name.endswith(".db"):
            conn = sqlite3.connect(str(path))
            rows = conn.execute("PRAGMA quick_check(1)").fetchall()
            conn.close()
            if rows and rows[0][0] == "ok":
                return True, ""
            return False, "فحص SQLite فشل: {}".format(rows[0][0] if rows else "غير معروف")
        if name.endswith((".xlsx", ".docx")):
            if not zipfile.is_zipfile(str(path)):
                return False, "الملف ليس حزمة ZIP/Office سليمة"
            with zipfile.ZipFile(str(path)) as zf:
                bad = zf.testzip()
                if bad:
                    return False, "جزء تالف داخل الملف: {}".format(bad)
            return True, ""
        return True, ""            # صور اللوجو وخلافه: الوجود يكفي
    except (sqlite3.Error, zipfile.BadZipFile, OSError) as exc:
        return False, str(exc)


def verify_all():
    """يفحص كل ملفات البيانات → {المسار النسبي: (سليم?, الخطأ)}."""
    return {str(p.relative_to(DATA_DIR)): verify_file(p) for p in data_files()}


# ==================== النسخ الاحتياطي ====================
def list_backups():
    """النسخ مرتبة من الأحدث للأقدم: [{name, path, size, mtime, reason, label}]."""
    out = []
    for p in sorted(backup_dir().glob("backup_*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
        m = re.match(r"^backup_\d{4}-\d{2}-\d{2}_\d{6}(?:_\d+)?_([a-z-]+)\.zip$", p.name)
        reason = m.group(1) if m else "manual"
        out.append({
            "name": p.name, "path": p, "size": p.stat().st_size,
            "mtime": p.stat().st_mtime, "reason": reason,
            "label": REASON_LABELS.get(reason, reason),
        })
    return out


def rotate():
    olds = list_backups()[KEEP_N:]
    for b in olds:
        try:
            b["path"].unlink()
        except OSError:
            pass
    return len(olds)


def create_backup(reason="manual"):
    """أرشيف ZIP كامل لكل ملفات البيانات + تدوير تلقائي."""
    _checkpoint_all()
    ts = time.strftime("%Y-%m-%d_%H%M%S")
    name = "backup_{}_{}.zip".format(ts, reason)
    dest = backup_dir() / name
    i = 1
    while dest.exists():                    # تفادي التصادم في نفس الثانية
        name = "backup_{}_{}_{}.zip".format(ts, i, reason)
        dest = backup_dir() / name
        i += 1
    files = data_files()
    with zipfile.ZipFile(str(dest), "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(str(p), p.relative_to(DATA_DIR).as_posix())
    rotate()
    return {"name": name, "path": dest, "count": len(files),
            "size": dest.stat().st_size}


def auto_backup(reason, min_minutes=30):
    """نسخة تلقائية ذكية — لا تتكرر إلا بعد مرور min_minutes من آخر نسخة."""
    newest = list_backups()
    if newest and (time.time() - newest[0]["mtime"]) < min_minutes * 60:
        return None
    return create_backup(reason)


# ==================== الاسترجاع ====================
def _safe_members(zf):
    names = []
    for n in zf.namelist():
        if n.endswith("/") or n.startswith("/") or ".." in n.split("/"):
            continue
        if n.split("/")[0] == "backups":
            continue
        names.append(n)
    return names


def restore_backup(name):
    """يسترجع كل محتويات نسخة فوق البيانات الحالية (بعد أخذ نسخة أمان من الحالي).
    الكتابة ذرّية ملفًا ملفًا. يرجع (عدد الملفات, اسم نسخة الأمان)."""
    if not valid_name(name):
        raise ValueError("اسم نسخة غير صالح")
    path = backup_dir() / name
    if not path.exists():
        raise FileNotFoundError("النسخة غير موجودة")
    with zipfile.ZipFile(str(path)) as zf:
        bad = zf.testzip()
        if bad:
            raise IOError("النسخة نفسها تالفة عند: {}".format(bad))
        members = _safe_members(zf)
        pre = create_backup("pre-restore")
        restored = 0
        for member in members:
            _atomic_write_bytes(DATA_DIR / member, zf.read(member))
            restored += 1
    return restored, pre["name"]


def delete_backup(name):
    if not valid_name(name):
        raise ValueError("اسم نسخة غير صالح")
    path = backup_dir() / name
    if path.exists():
        path.unlink()


# ==================== حارس التشغيل ====================
def startup_guard():
    """يفحص كل الملفات؛ التالف يُحجز بامتداد ‎.corrupt-الوقت‎ ويُسترجع تلقائيًا
    آخرُ نسخةٍ سليمة من الأرشيف (من الأحدث للأقدم). يرجع قائمة أحداث لطباعتها."""
    events = []
    ts = time.strftime("%Y%m%d-%H%M%S")
    for p in data_files():
        ok, err = verify_file(p)
        if ok:
            continue
        rel = p.relative_to(DATA_DIR).as_posix()
        quarantine = p.with_name("{}.corrupt-{}".format(p.name, ts))
        try:
            os.replace(str(p), str(quarantine))
        except OSError as exc:
            events.append("⚠️ تعذّر حجز الملف التالف {}: {}".format(rel, exc))
            continue
        restored_from = None
        for b in list_backups():
            try:
                with zipfile.ZipFile(str(b["path"])) as zf:
                    if rel in zf.namelist():
                        data = zf.read(rel)
                        _atomic_write_bytes(p, data)
                        restored_from = b["name"]
                        break
            except (zipfile.BadZipFile, KeyError, OSError):
                continue
        if restored_from:
            events.append("🛡️ «{}» كان تالفًا ({}) — استُرجع من «{}» والتالف محجوز بجانبه."
                          .format(rel, err, restored_from))
        else:
            events.append("⚠️ «{}» تالف ({}) ولا نسخة تحويه — حُجز جانبًا باسم «{}»."
                          .format(rel, err, quarantine.name))
    return events

# ==================== أرشيف مجلد مؤقت للتنزيل ====================
def zip_folder_tmp(folder, prefix="folder"):
    """يضغط مجلدًا كاملًا في ZIP مؤقت (لإرساله تنزيلًا) ويرجع مساره.
    الملف يُحذف بعد الإرسال بواسطة الطبقة المستدعية."""
    import tempfile
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError("المجلد غير موجود: {}".format(folder))
    target = Path(tempfile.gettempdir()) / "{}-{}-{}.zip".format(
        prefix, os.getpid(), int(time.time() * 1000))

    def _write(tmp_name):
        with zipfile.ZipFile(tmp_name, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(folder.rglob("*")):
                if p.is_file():
                    zf.write(str(p), p.relative_to(folder).as_posix())

    atomic_save(_write, target)
    return target
