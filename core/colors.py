# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""الألوان الثابتة للأصناف والجهات والأشخاص — مصدر واحد لكل البرنامج.

توجيه المستخدم ٠٦/١٠/٢٠٢٦ (أمر عسكري): «لكل صنف لون معين مختلف عن ألوان الأصناف
الأخرى، والصنف يظهر بنفس اللون في كل مكان، وكذلك الجهات وأسماء الضباط — ولا يشبه
لون صنف لون ضابط».

القواعد:
* ثلاثة مدايات **منفصلة تمامًا**: الأصناف (ألوان غذائية) · الجهات (ألوان رسمية
  داكنة) · الأشخاص (ألوان شخصية فاتحة + قوس) — فلا يتشابه نوع بنوع.
* اللون **يُسجَّل مرة واحدة** عند أول ظهور للاسم ويبقى مدى الحياة (`<DATA>/colors.json`
  عبر `dataguard.atomic_save`) ⇒ نفس الصنف/الجهة/الشخص بنفس اللون في كل الشاشات
  وفي ملفات الإكسل والطباعة.
* التسجيل الجديد ياخد **أول لون غير مستخدم** في مداه (لا تكرار داخل النوع).
التنسيقات المستخدمة في القوالب عبر `core.web`:
    {{ color('item', it.name) }}       → كود HEX للتلوين في CSS
    {{ color_ring('person', name) }}   → style جاهز للقوس حول الاسم
"""
import json
import threading
from pathlib import Path

from core.paths import DATA_DIR
from data_access import dataguard

_LOCK = threading.Lock()
_STORE = "colors.json"

# ── المدى ١: الأصناف (غذائية — ألوان واضحة متمايزة) ──────────────────────
ITEM_COLORS = [
    "#8E44AD", "#E67E22", "#16A085", "#C0392B", "#2980B9", "#F39C12",
    "#27AE60", "#D35400", "#7F8C8D", "#B03A2E", "#1F618D", "#A04000",
    "#117A65", "#884EA0", "#CA6F1E", "#0E6655",
]

# ── المدى ٢: الجهات (رسمية داكنة — لا تلمس ألوان الأصناف) ─────────────────
ENTITY_COLORS = [
    "#1F2A44", "#2C3E50", "#34495E", "#1B3A57", "#22303C", "#3B2F4A",
    "#243B36", "#402B2B", "#2E3A46", "#333F2C", "#452E3F", "#1E3A34",
]

# ── المدى ٣: الأشخاص (ضباط/أفراد — ألوان شخصية فاتحة، تُعرض كقوس) ────────
PERSON_COLORS = [
    "#E74C3C", "#9B59B6", "#3498DB", "#1ABC9C", "#F1C40F", "#E91E63",
    "#00BCD4", "#FF7043", "#8BC34A", "#BA68C8",
]

PALETTES = {"item": ITEM_COLORS, "entity": ENTITY_COLORS, "person": PERSON_COLORS}
KIND_LABELS = {"item": "صنف", "entity": "جهة", "person": "شخص"}


def _store_path():
    return DATA_DIR / _STORE


def _load():
    path = _store_path()
    if not path.exists():
        return {"item": {}, "entity": {}, "person": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):   # noqa: BLE001 — ملف تالف لا يوقف الشاشة
        return {"item": {}, "entity": {}, "person": {}}
    for kind in PALETTES:
        data.setdefault(kind, {})
    return data


def _save(data):
    """كتابة ذرّية JSON (نفس نمط ملفات القسم: zip_check=False)."""
    payload = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")
    try:
        dataguard.atomic_save(
            lambda tmp: Path(tmp).write_bytes(payload),
            str(_store_path()), zip_check=False)
    except Exception:   # noqa: BLE001 — اللون الجمالي لا يُسقط أي عملية
        pass


def color_for(kind, key):
    """لون ثابت للاسم — يُسجَّل عند أول ظهور ويبقى في كل الشاشات والملفات."""
    key = (key or "").strip()
    if not key or key in ("—", "-") or kind not in PALETTES:
        return ""
    with _LOCK:
        data = _load()
        existing = (data[kind] or {}).get(key)
        if existing:
            return existing
        palette = PALETTES[kind]
        used = set((data[kind] or {}).values())
        color = next((c for c in palette if c not in used), None)
        if color is None:                       # المدى كله مستخدم ⇒ توزيع بالدور
            color = palette[len(data[kind]) % len(palette)]
        data[kind][key] = color
        _save(data)
        return color


def many(kind, keys):
    """{الاسم: اللون} لقائمة أسماء — تمريرة واحدة بلا قراءة متكررة للملف."""
    out = {}
    for key in keys or []:
        out[(key or "").strip()] = color_for(kind, key)
    return out


def ring_style(kind, key):
    """style جاهز للقوس الملوّن حول الاسم (توجيه: الضابط بلون وحواليه قوس)."""
    color = color_for(kind, key)
    if not color:
        return ""
    return f"--ring:{color};border-color:{color};box-shadow:0 0 0 2px {color}33"


def css_vars(kind, keys):
    """متغيرات CSS لكل أسماء نوع واحد — تُمرَّر للقالب مرة واحدة."""
    return " ".join(f"--c-{i}:{color};" for i, color in enumerate(many(kind, keys).values()))
