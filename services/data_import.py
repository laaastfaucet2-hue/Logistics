"""First-install import into an empty data directory. Source is never moved/deleted."""
import os
import shutil
import tempfile
from pathlib import Path
from data_access import database, dataguard


def import_database(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("اختر مجلد database للنسخة القديمة، وليس مجلد البرنامج الجديد")
    if not (source / "system.db").is_file():
        raise ValueError("المجلد لا يحتوي system.db؛ اختر مجلد database نفسه")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("مجلد الوجهة ليس فارغًا؛ لن نستبدل بياناتك الحالية")
    files = [p for p in source.rglob("*") if p.is_file() and not p.name.endswith(("-wal", "-shm"))
             and ".tmp" not in p.name and ".corrupt-" not in p.name]
    if any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError("المصدر يحتوي روابط ملفات؛ استخدم نسخة محلية كاملة")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination.parent).free < sum(p.stat().st_size for p in files) * 1.2:
        raise ValueError("المساحة المتاحة لا تكفي لنسخة آمنة من البيانات")
    stage = Path(tempfile.mkdtemp(prefix=".import-", dir=destination.parent))
    try:
        for path in files:
            target = stage / path.relative_to(source)
            ok, error = dataguard.verify_file(path)
            if not ok:
                raise ValueError(f"ملف المصدر غير سليم: {path.name} — {error}")
            if path.suffix.lower() == ".db":
                def snapshot(tmp, path=path):
                    src, dst = database.get_conn(path, readonly=True), database.get_conn(tmp)
                    try:
                        src.backup(dst)
                    finally:
                        dst.close()
                        src.close()
                dataguard.atomic_save(snapshot, target, zip_check=False)
            else:
                dataguard.atomic_save(lambda tmp, path=path: shutil.copyfile(path, tmp), target,
                                      zip_check=path.suffix.lower() in (".xlsx", ".docx", ".zip"))
        if destination.exists():
            destination.rmdir()  # Only an empty directory; never remove populated user data.
        os.replace(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return len(files)
