# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثق في CONTRIBUTING.md
"""هوية المنظومة (تاب «الهوية للمنظمة» في الإعدادات).

اللوجو هنا هو شعار المنظومة في واجهة البرنامج (تسجيل الدخول، القائمة
الجانبية، الرئيسية، شريط النافذة) — مستقل عن لوجو الدباجة المرتبط بالشهر.
التخزين: database/الهوية/ (ثابت، غير مرتبط بسنة أو شهر) + وصف JSON صغير.
"""
import json

from data_access import storage

CONFIG_NAME = "identity.json"


def _path():
    return storage.identity_dir() / CONFIG_NAME


def _read():
    p = _path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data):
    import datetime
    data = dict(data)
    data["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    storage.identity_dir().joinpath(CONFIG_NAME).write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def get_logo():
    """اسم ملف اللوجو الحالي أو ''."""
    name = (_read().get("logo") or "").strip()
    if name and not (storage.identity_dir() / name).exists():
        return ""
    return name


def set_logo(filename):
    _write({"logo": filename})


def delete_logo():
    name = get_logo()
    if name:
        try:
            (storage.identity_dir() / name).unlink()
        except OSError:
            pass
    _write({"logo": ""})
