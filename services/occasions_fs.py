# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الملفات المحلية لصفحة «التوثيق والمناسبات» — صفحة دائمة لا تتبع الشهر ولا السنة.

توجيه ٠٦/١٠/٢٠٢٦: «لكل زيارة ملف محلي داخل مسمى الزيارة — فولدر للصور وفولدر
للفيديو، والتقرير على دباجة وتوقيعات ولوجو».

التوزيعة على القرص (مستقلة تمامًا عن فولدرات الأشهر):
    database/occasions/<السنة>/<المسمى>/
        بيانات.json          ← النوع · التاريخ · المكان · القوة · الوصف · الإطار
        صور/                 ← كل صور المناسبة (jpg/png/webp)
        فيديو/               ← كل فيديوهاتها (mp4/webm/mov)
        التقرير.xlsx          ← التقرير الرسمي (بون المناسبة)
        التقرير.docx          ← نفس التقرير Word

كل كتابة بيانات عبر dataguard.atomic_save (كتابة ذرّية) — وقاعدة ذهبية:
كل ملف محلي بدباجة + لوجو + توقيعين.
"""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from core import arabic_numbers as arnum
from core import paths
from data_access import dataguard

ROOT_NAME = "occasions"
SUB_PHOTOS = "صور"
SUB_VIDEOS = "فيديو"
DATA_FILE = "بيانات.json"
REPORT_XLSX = "التقرير.xlsx"
REPORT_DOCX = "التقرير.docx"

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}

# حدود الرفع (قرار المستخدم ٠٨/١٠/٢٠٢٦): ٣٠ ملفًا في الرفعة — وحتى ٢ جيجا للفيديو
MAX_FILES_PER_UPLOAD = 30
MAX_UPLOAD_BYTES = 2048 * 1024 * 1024
UPLOAD_LIMIT_TEXT = "٢ جيجابايت"

# أنواع المناسبات المحفوظة (يختارها المستخدم من قائمة، ويمكنه كتابة مسمّى حر)
KINDS = ["زيارة رسمية", "تفتيش", "زيارة ميدانية", "اجتماع", "حفل", "مناسبة أخرى"]

Path = Path   # يعاد تصديره لاستخدام المسارات في المسارات (routes)

FIELD_KEYS = [
    ("title", "المسمى"), ("kind", "النوع"), ("date_iso", "التاريخ"),
    ("place", "المكان"), ("force_text", "القوة/الوفد"), ("notes", "الوصف"),
    ("frame", "إطار"),
]


def root():
    """جذر المناسبات — يُقرأ ديناميًا (الاختبارات تغيّر مسار البيانات)."""
    path = Path(paths.DATA_DIR) / ROOT_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe(name):
    """اسم فولدر آمن من أي رموز تكسر المسار."""
    clean = re.sub(r'[<>:"/\\|?*\n\r\t]+', " ", str(name or "")).strip(" .")
    return clean[:80] or "مناسبة"


def occasion_dir(title, date_iso):
    """فولدر المناسبة: occasions/<السنة>/<التاريخ> — <المسمى> (يُنشأ أول مرة)."""
    year = (str(date_iso or "").split("-")[0]) or str(datetime.now().year)
    slug = f"{date_iso} — {_safe(title)}" if date_iso else _safe(title)
    path = root() / _safe(year) / _safe(slug)
    for sub in ("", SUB_PHOTOS, SUB_VIDEOS):
        (path / sub).mkdir(parents=True, exist_ok=True)
    return path


def data_path(folder):
    return Path(folder) / DATA_FILE


def _save_json(path, payload):
    """كتابة ذرّية لأي ملف بيانات (قاعدة المشروع: لا كتابة مباشرة)."""
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    dataguard.atomic_save(lambda tmp: Path(tmp).write_bytes(data), path, zip_check=False)


def load(folder):
    """بيانات مناسبة من فولدرها — مع القيم الافتراضية فلا يظهر None في الواجهة."""
    path = data_path(folder)
    payload = {}
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            payload = {}
    out = {key: (payload.get(key) or "") for key, _label in FIELD_KEYS}
    out["title"] = out["title"] or Path(folder).name.split(" — ")[-1]
    out["kind"] = out["kind"] or KINDS[0]
    out["folder"] = str(folder)
    out["photos"] = media_list(folder, "photo")
    out["videos"] = media_list(folder, "video")
    return out


def save(folder, values):
    """حفظ/تعديل بيانات المناسبة (تُستخدم في الإنشاء والتعديل)."""
    payload = {key: str(values.get(key) or "").strip() for key, _l in FIELD_KEYS}
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_json(data_path(folder), payload)
    return payload


def create(values):
    """إنشاء مناسبة جديدة: فولدر بمسمى المناسبة + الملفات الفرعية + بيانات.json."""
    title = (values.get("title") or "").strip() or "مناسبة جديدة"
    folder = occasion_dir(title, (values.get("date_iso") or "").strip())
    payload = save(folder, {**values, "title": title})
    return folder, payload


def _media_kind(path):
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_EXT:
        return "photo"
    if suffix in VIDEO_EXT:
        return "video"
    return ""


def size_text(size):
    """حجم مقروء بأرقام عربية — بايت / كيلوبايت / ميجابايت / جيجابايت."""
    size = int(size or 0)
    if size < 1024:
        return f"{arnum.to_arabic_indic(str(size))} بايت"
    if size < 1024 * 1024:
        return f"{arnum.fmt_qty(round(size / 1024, 1))} كيلوبايت"
    if size < 1024 * 1024 * 1024:
        return f"{arnum.fmt_qty(round(size / (1024 * 1024), 1))} ميجابايت"
    return f"{arnum.fmt_qty(round(size / (1024 * 1024 * 1024), 2))} جيجابايت"


def media_list(folder, kind=None):
    """قائمة الوسائط داخل المناسبة (صور/فيديو) بترتيب زمني — قابلة للفلترة."""
    out = []
    pairs = [("photo", SUB_PHOTOS), ("video", SUB_VIDEOS)]
    for key, sub in pairs:
        if kind and key != kind:
            continue
        target = Path(folder) / sub
        if not target.is_dir():
            continue
        for path in sorted(target.iterdir()):
            if path.is_file() and not path.name.startswith("~$"):
                size = path.stat().st_size
                out.append({"kind": key, "name": path.name, "sub": sub,
                            "size": size, "size_text": size_text(size),
                            "modified": datetime.fromtimestamp(
                                path.stat().st_mtime).isoformat(timespec="seconds")})
    return out


def media_path(folder, kind, name):
    """مسار وسيط واحد بفحص أمان المسار (لا خروج من فولدر المناسبة)."""
    sub = SUB_PHOTOS if kind == "photo" else SUB_VIDEOS
    base = (Path(folder) / sub).resolve()
    target = (base / _safe(name)).resolve()
    if base not in target.parents or not target.is_file():
        return None
    return target


def add_media(folder, kind, storage_file):
    """إضافة صورة/فيديو: تُنسخ داخل فولدرها الفرعي باسمها الأصلي (بعد تجنّب التكرار).

    تُرجع المسار النهائي — أو None لو كان الملف بلا اسم أو بامتداد غير مدعوم
    (فلا يدخل فولدر المناسبة أي ملف غريب لا يفتحه البرنامج).
    """
    name = _safe(Path(storage_file.filename).name)
    if not name or name.startswith("~$"):
        return None
    if _media_kind(name) != kind:
        return None
    sub = SUB_PHOTOS if kind == "photo" else SUB_VIDEOS
    target = Path(folder) / sub / name
    stem, suffix = target.stem, target.suffix
    counter = 2
    while target.exists():
        target = target.with_name(f"{stem} ({arnum.to_arabic_indic(str(counter))}){suffix}")
        counter += 1
    storage_file.save(str(target))
    return target


def delete_media(folder, kind, name):
    path = media_path(folder, kind, name)
    if path is None:
        return False
    path.unlink()
    return True


def list_occasions(date_from=None, date_to=None, query=""):
    """كل المناسبات مرتبة بالأحدث — مع فلتر التاريخ والبحث الذكي (نوع/مسمى/مكان)."""
    items = []
    for folder in sorted(root().glob("*/*"), reverse=True):
        if not folder.is_dir():
            continue
        item = load(folder)
        if date_from and (item["date_iso"] or "") < date_from:
            continue
        if date_to and (item["date_iso"] or "") > date_to:
            continue
        if query:
            hay = " ".join([item["title"], item["kind"], item["place"], item["notes"]])
            if query.strip() not in hay:
                continue
        items.append(item)
    items.sort(key=lambda i: (i["date_iso"] or "", i["title"]), reverse=True)
    return items


def kinds_in_use():
    """الأنواع المستخدمة فعلًا (+ الأنواع الأساسية) — لقائمة البحث الذكي والفلاتر."""
    found = list(KINDS)
    for item in list_occasions():
        if item["kind"] and item["kind"] not in found:
            found.append(item["kind"])
    return found


def stats():
    """أرقام الصفحة: عدد المناسبات · الصور · الفيديو — لبطاقات أعلى الصفحة."""
    occ = list_occasions()
    return {
        "occasions": len(occ),
        "photos": sum(len(i["photos"]) for i in occ),
        "videos": sum(len(i["videos"]) for i in occ),
        "kinds": len({i["kind"] for i in occ if i["kind"]}),
    }


def delete_occasion(folder):
    """حذف مناسبة كاملة بكل صورها وفيديوهاتها."""
    path = Path(folder).resolve()
    base = root().resolve()
    if base not in path.parents or not path.is_dir():
        return False
    shutil.rmtree(path, ignore_errors=True)
    return True
