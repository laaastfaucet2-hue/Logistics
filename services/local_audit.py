# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الفحص الذكي للملفات المحلية — القواعد الذهبية الثلاث على كل ملف.

توجيه المستخدم ٠٦/١٠/٢٠٢٦: «يجب على قراءة القواعد الذهبية والفحص الذكي في البرنامج لكل
الملفات المحلية: وجودها على الدباجة ووجود التوقيعات الرسمية واللوجو على كل الملفات المحلية
وكذلك الملفات الداخلية في البرنامج».

الفحص **قراءة فقط** (لا يكتب ولا يصلح)، ويعمل على:
* كل ورقة إكسل (`.xlsx`) تحت فولدرات الشهر — الدباجة · التوقيعان · اللوجو · الشهر والسنة.
* كل ملف JSON بنيته الإلزامية (الجهة · القسم · الشهر · السنة · آخر تحديث).
* ملفات Word (`.docx`) — الدباجة والتوقيعان في نص المستند.

النتيجة: `{"checked", "ok", "problems": [ {file, kind, missing[]} ], "by_dir"}` وتُعرض
في تاب «الملفات المحلية» وفي «فحص الملفات» بالشريط الجانبي.
"""
from pathlib import Path
from zipfile import BadZipFile

from data_access import db_letterhead as lhdb
from core.config import MONTH_NAMES

# كلمات مطلوبة في كل ملف محلي (القواعد الذهبية)
CORE_WORDS = ("وزارة الداخلية", "قطاع وسط سيناء", "قسم التعيينات")
SIGNATURE_KEYS = ("sig_right_rank", "sig_right_name", "sig_left_rank", "sig_left_name")
JSON_REQUIRED = ("الجهة", "القسم", "الشهر", "السنة", "آخر تحديث")


def _norm(value):
    return " ".join(str(value or "").split())


def _sheet_text(ws, max_row=None, max_col=12):
    """نص الورقة كاملًا (الدباجة أعلى + التوقيعان آخر الجدول) — لفحص القواعد.

    كان الحد القديم ٢٠٠ صف فقط، فكانت الملفات الطويلة (إجمالي الشهر ٢٨٥ صفًا)
    تُبلَّغ خطأً بأن التوقيعين ناقصان وهما في آخرها (تصحيح ٠٧/١٠/٢٠٢٦).
    """
    last = max_row or min(getattr(ws, "max_row", 1) or 1, 5000)
    parts = []
    for row in ws.iter_rows(min_row=1, max_row=last, max_col=max_col, values_only=True):
        parts.extend(str(cell) for cell in row if cell not in (None, ""))
    return _norm(" ".join(parts))


def _has_logo(ws):
    """اللوجو إمّا صورة مضمّنة في الورقة أو خلية نصية فيها كلمة «لوجو/شعار»."""
    try:
        if getattr(ws, "_images", None):
            return True
    except Exception:                      # pragma: no cover — نسخ openpyxl القديمة
        pass
    return "لوجو" in _sheet_text(ws) or "شعار" in _sheet_text(ws)


def audit_workbook(path, year=None, month=None):
    """فحص ملف إكسل واحد — يرجّع قائمة النواقص (فارغة ⇒ الملف سليم)."""
    from openpyxl import load_workbook
    missing = []
    try:
        book = load_workbook(path, data_only=True)
    except (BadZipFile, OSError, ValueError) as exc:
        return [f"ملف إكسل غير قابل للقراءة ({type(exc).__name__})"]
    text = _norm(" ".join(_sheet_text(ws) for ws in book.worksheets))
    for word in CORE_WORDS:
        if word not in text:
            missing.append(f"الدباجة: «{word}»")
    if not any(_has_logo(ws) for ws in book.worksheets):
        missing.append("اللوجو المضمّن")
    signatures = _signatures_text(year, month)
    for label in signatures:
        if label and label not in text:
            missing.append(f"التوقيع: «{label}»")
    if year and month:
        stamp = f"{MONTH_NAMES[int(month) - 1]}"
        if stamp not in text:
            missing.append(f"اسم الشهر «{stamp}»")
    return missing


def _signatures_text(year, month):
    """رتب/أسماء التوقيعين المسجّلة في الدباجة — تُقارن بنص الملف."""
    if not year or not month:
        return ()
    out = []
    for key in SIGNATURE_KEYS:
        value = _norm(lhdb.get_setting(int(year), int(month), key))
        if value and "..." not in value:
            out.append(value)
    return tuple(out)


def audit_json(path):
    """فحص ملف JSON — البنية الإلزامية (أسماء عربية بالأرقام العربية في القيم)."""
    import json
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"ملف JSON غير قابل للقراءة ({type(exc).__name__})"]
    if not isinstance(payload, dict):
        return ["بنية JSON غير متوقعة (ليست قاموسًا)"]
    return [f"مفتاح ناقص: «{key}»" for key in JSON_REQUIRED if key not in payload]


def audit_docx(path, year=None, month=None):
    """فحص مستند Word — الدباجة والتوقيعان في نص المستند."""
    from zipfile import ZipFile
    import re
    try:
        with ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", "ignore")
    except (BadZipFile, KeyError, OSError) as exc:
        return [f"مستند Word غير قابل للقراءة ({type(exc).__name__})"]
    text = _norm(re.sub(r"<[^>]+>", " ", xml))
    missing = [f"الدباجة: «{word}»" for word in CORE_WORDS if word not in text]
    for label in _signatures_text(year, month):
        if label not in text:
            missing.append(f"التوقيع: «{label}»")
    return missing


def audit_path(path, year=None, month=None):
    """يفحص ملفًا واحدًا بنوعه — يرجّع [] لغير المدعوم (لا فشل زائف)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return audit_workbook(path, year, month)
    if suffix == ".json":
        return audit_json(path)
    if suffix == ".docx":
        return audit_docx(path, year, month)
    return []


def audit_tree(root, year=None, month=None, limit=None):
    """فحص كل الملفات تحت فولدر — تقرير كامل مرتّب بالمشاكل أولًا."""
    root = Path(root)
    report = {"root": str(root), "checked": 0, "ok": 0, "problems": [], "by_dir": {}}
    if not root.exists():
        return report
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("~$"):
            continue
        missing = audit_path(path, year, month)
        report["checked"] += 1
        rel = str(path.relative_to(root))
        if missing:
            report["problems"].append({"file": rel, "missing": missing})
            folder = str(path.parent.relative_to(root))
            report["by_dir"][folder] = report["by_dir"].get(folder, 0) + 1
        else:
            report["ok"] += 1
        if limit and report["checked"] >= limit:
            break
    report["problems"].sort(key=lambda p: p["file"])
    return report


def audit_month(year, month, sections=("tameedat", "raghibin")):
    """فحص ملفات الشهر المحلية في الأقسام المطلوبة — يُدمج الفولدرات معًا."""
    from services import files_index
    out = {"year": year, "month": month, "checked": 0, "ok": 0,
           "problems": [], "sections": {}}
    for section in sections:
        root = files_index.section_root(section, year, month)
        part = audit_tree(root, year, month)
        out["sections"][section] = {"checked": part["checked"], "ok": part["ok"],
                                    "problems": len(part["problems"]),
                                    "folder": str(root)}
        out["checked"] += part["checked"]
        out["ok"] += part["ok"]
        out["problems"].extend([{**p, "section": section} for p in part["problems"]])
    return out
