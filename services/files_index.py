# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 خط — الترتيب المعماري موثّق في CONTRIBUTING.md
"""حصر ملفات الأقسام المحلية على القرص — شجرة كاملة لحظية (توجيه المستخدم ٠٦/١٠/٢٠٢٦).

المستخدم طلب «حصر كل الملفات المحلية في صفحتي التاميدات والراغبين على شكل شجرة،
والتأكد أنها كلها تتحدث لحظيًا مع البرنامج — ولو الملف مفتوح في Excel ولم يُقفل».

هذا الملف يقرأ ما هو موجود فعلًا على القرص (لا تخمين): الفولدرات والملفات بأسمائها
وحجمها ووقت آخر تحديث، مرتّبة عربيًا (فولدرات الأيام بترتيب رقمي عربي)، ويعلّم
الملفات التي اتحدثت في آخر ثوانٍ كي يراها المستخدم «اتحدثت الآن».
الكتابة نفسها تتم في `dataguard.atomic_save` بنظام live-sync (لو الملف مقفول عند
المستخدم يُحتفظ بالمحتوى ويُنزل أول ما يُقفل) — وهذا الملف للعرض فقط ولا يكتب شيئًا.
"""
import time
from pathlib import Path

from core import arabic_numbers as arnum
from core import egtime
from core.config import SECTIONS

# أقسام لوحة الحصر: مفتاح داخلي → مفتاح القسم في core.config.SECTIONS
SECTIONS_INDEX = {
    "tameedat": "tameedat",
    "raghibin": "raghebeen",
}

SECTION_TITLES = {
    "tameedat": "التاميدات",
    "raghibin": "قسم الراغبين",
}

# ترويسة كل قسم كما هي في فولدرات database/ (تُعرض أعلى الشجرة)
SECTION_HEADERS = {
    "tameedat": "قطاع وسط سيناء - قسم التميينات",
    "raghibin": "قطاع وسط سيناء - قسم الراغبين",
}


def _section_position(key):
    for index, section in enumerate(SECTIONS, start=1):
        if section["key"] == key:
            return index
    raise KeyError(key)


def section_root(section, year, month):
    """فولدر ملفات القسم داخل فولدر الشهر (يُنشأ إن لم يوجد — القراءة لا تفشل)."""
    key = SECTIONS_INDEX.get(section)
    if not key:
        raise KeyError(section)
    from data_access import storage
    path = storage.section_files_path(year, month, _section_position(key))
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def _is_noise(name):
    """ملفات مؤقتة لا تُعرض: قفل Excel (~$) وملفات الكتابة الذرّية (.tmp)."""
    return name.startswith("~$") or name.endswith(".tmp") or ".tmp-" in name


def _day_number(name):
    """رقم اليوم من اسم فولدر «يوم ١٢» — وإلا None."""
    digits = "".join(ch for ch in name if ch.isdigit())
    if not digits:
        return None
    return arnum.parse_int(digits)


def _sort_key(name, is_dir):
    """ترتيب عربي مفهوم: فولدرات الأيام بترتيبها الرقمي، ثم الفولدرات، ثم الملفات."""
    if is_dir and name.startswith("يوم"):
        number = _day_number(name)
        if number:
            return (0, number, "")
    return (1 if is_dir else 2, 0, name)


def size_text(size):
    """حجم مقروء بأرقام عربية — بايت / كيلوبايت / ميجابايت."""
    size = int(size or 0)
    if size < 1024:
        return f"{arnum.to_arabic_indic(str(size))} بايت"
    if size < 1024 * 1024:
        return f"{arnum.fmt_qty(round(size / 1024, 1))} كيلوبايت"
    return f"{arnum.fmt_qty(round(size / (1024 * 1024), 1))} ميجابايت"


def _time_text(mtime):
    """وقت آخر تحديث بتوقيت القاهرة نفسه الذي يظهر في البرنامج (لا توقيت السيرفر)."""
    return egtime.from_timestamp(mtime).strftime("%H:%M:%S")


def _walk(path, root, fresh_seconds, now):
    """عقدة واحدة (ملف أو فولدر) بمحتواها كما هو على القرص هذه اللحظة."""
    try:
        stat = path.stat()
    except OSError:
        return None
    is_dir = path.is_dir()
    node = {
        "name": path.name,
        "type": "dir" if is_dir else "file",
        "rel": "" if path == root else str(path.relative_to(root)),
        "ext": "" if is_dir else path.suffix.lower().lstrip("."),
        "mtime": stat.st_mtime,
        "mtime_text": _time_text(stat.st_mtime),
        "fresh": (now - stat.st_mtime) <= fresh_seconds,
        "files": 0,
        "children": [],
    }
    if not is_dir:
        node["size"] = stat.st_size
        node["size_text"] = size_text(stat.st_size)
        return node
    children, total, files = [], 0, 0
    try:
        entries = list(path.iterdir())
    except OSError:
        entries = []
    for child in entries:
        if _is_noise(child.name):
            continue
        item = _walk(child, root, fresh_seconds, now)
        if not item:
            continue
        children.append(item)
        total += item["size"]
        files += (1 if item["type"] == "file" else item["files"])
    children.sort(key=lambda item: _sort_key(item["name"], item["type"] == "dir"))
    node["children"] = children
    node["size"] = total
    node["size_text"] = size_text(total)
    node["files"] = files
    node["fresh"] = any(item["fresh"] for item in children)
    return node


def build_tree(section, year, month, fresh_seconds=25):
    """شجرة القسم كاملة — تُقرأ من القرص مباشرة (حصر حقيقي لا تخمين)."""
    root = section_root(section, year, month)
    now = time.time()
    children = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: _sort_key(p.name, p.is_dir()))
    except OSError:
        entries = []
    for child in entries:
        if _is_noise(child.name):
            continue
        node = _walk(child, root, fresh_seconds, now)
        if node:
            children.append(node)
    files = sum(1 for item in children if item["type"] == "file") + \
        sum(item["files"] for item in children)
    folders = sum(1 for item in children if item["type"] == "dir") + \
        sum(_count_dirs(item) for item in children)
    return {
        "ok": True,
        "section": section,
        "title": SECTION_TITLES.get(section, section),
        "header": SECTION_HEADERS.get(section, ""),
        "root": str(root),
        "root_name": root.name,
        "year": year,
        "month": month,
        "files": files,
        "folders": folders,
        "bytes": sum(item["size"] for item in children),
        "fresh_seconds": fresh_seconds,
        "checked_at": egtime.now().strftime("%H:%M:%S"),
        "children": children,
    }


def _count_dirs(node):
    """عدد الفولدرات الداخلية في عقدة (لا تحسب العقدة نفسها)."""
    if node["type"] == "file":
        return 0
    return sum((1 if child["type"] == "dir" else 0) + _count_dirs(child)
               for child in node["children"])
