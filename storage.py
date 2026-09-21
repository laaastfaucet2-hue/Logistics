# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مدير هيكل مجلد البيانات database/ — السنوات والشهور والأقسام.

الهيكل المعتمد:
    database/
    ├── system.db            ← قاعدة النظام (المستخدمون، الجلسات، السياق)
    └── <السنة>/            ← مثل 2026 (تُدار من شريط الأدوات العلوي)
        └── 01-يناير/       ← كل شهر منعزل تمامًا عن باقي الشهور
            └── 01-التموين/ ← مجلد ملفات القسم (Excel / Word) ... حتى 12-السيارات
"""
import re
import shutil
from pathlib import Path

from config import SECTIONS, month_folder, section_folder

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "database"
YEAR_RE = re.compile(r"^\d{4}$")


def year_path(year):
    return DATA_DIR / str(year)


def list_years():
    """يرجع السنوات الموجودة فعليًا على القرص، مرتبة تنازليًا."""
    if not DATA_DIR.is_dir():
        return []
    years = [int(p.name) for p in DATA_DIR.iterdir()
             if p.is_dir() and YEAR_RE.match(p.name)]
    return sorted(years, reverse=True)


def create_year(year):
    """ينشئ مجلد السنة كاملًا (12 شهرًا × 12 قسمًا). False لو موجودة مسبقًا."""
    if year_path(year).exists():
        return False
    for month in range(1, 13):
        for index, section in enumerate(SECTIONS, start=1):
            folder = (year_path(year) / month_folder(month)
                      / section_folder(index, section["name"]))
            folder.mkdir(parents=True, exist_ok=True)
    return True


def delete_year(year):
    """يحذف مجلد السنة وكل محتوياته نهائيًا. False لو غير موجودة."""
    path = year_path(year)
    if not path.is_dir():
        return False
    shutil.rmtree(path)
    return True


def section_files_path(year, month, section_index):
    """مسار مجلد ملفات قسم معين داخل شهر معين (لرفع/توليد الملفات لاحقًا)."""
    return (year_path(year) / month_folder(month)
            / section_folder(section_index, SECTIONS[section_index - 1]["name"]))


def ensure_initialized(current_year):
    """عند أول تشغيل يُنشئ مجلد البيانات والسنة الحالية افتراضيًا."""
    DATA_DIR.mkdir(exist_ok=True)
    # مجلد صفحة الدباجة والتوقيعات الرسمية (اللوجو + ملف Word لاحقًا)
    (DATA_DIR / "الدباجة").mkdir(exist_ok=True)
    if not list_years():
        create_year(current_year)


def letterhead_dir():
    """مجلد الدباجة والتوقيعات الرسمية: اللوجو + ملف Word الدباجة."""
    path = DATA_DIR / "الدباجة"
    path.mkdir(exist_ok=True)
    return path


SECTION_DIR_RE = re.compile(r"^(\d{2})-")


def sync_section_folders():
    """يوائم مجلدات الأقسام داخل كل سنة/شهر مع الأسماء المعتمدة في config.

    - مجلد قسم قديم بنفس الرقم لكن باسم مختلف → يُعاد تسميته (محتواه محفوظ).
    - مجلد قسم ناقص → يُنشأ.
    """
    for year in list_years():
        for month in range(1, 13):
            month_dir = year_path(year) / month_folder(month)
            month_dir.mkdir(parents=True, exist_ok=True)
            existing = {}
            for p in month_dir.iterdir():
                m = SECTION_DIR_RE.match(p.name)
                if p.is_dir() and m:
                    existing[int(m.group(1))] = p
            for index, section in enumerate(SECTIONS, start=1):
                want = section_folder(index, section["name"])
                cur = existing.get(index)
                if cur is None:
                    (month_dir / want).mkdir(exist_ok=True)
                elif cur.name != want and not (month_dir / want).exists():
                    cur.rename(month_dir / want)
