# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""جسر النموذج المحلي الاختياري للمساعد — GGUF صغير داخل بيانات المستخدم.

الفكرة: البرنامج يعمل بمحرك النوايا المحلي دائمًا (بلا أي تحميل وبلا أي اعتمادية)،
وإذا وضع المستخدم ملف نموذج لغوي صغير بصيغة GGUF في:
    database/assistant/model.gguf        (أو مسار في المتغير LOGISTICS_ASSISTANT_MODEL)
وكانت حزمة `llama-cpp-python` مثبتة على جهازه، يُستخدم النموذج **للأسئلة المفتوحة
التي لا يفهمها المحرك فقط** — ببيانات الشهر الحقيقية كسياق، وبلا أي إنترنت.

لماذا لا يُضمَّن النموذج في المستودع: أوزان حتى أصغر نموذج عربي مفيد تزن ١٠٠–٤٠٠
ميجابايت وتُثقل المثبّت وتخالف قاعدة «محلي بلا إنترنت ولا وصول لخدمات خارجية»
وقاعدة عدم رفع البيانات/الملفات الضخمة على GitHub. لذلك يُحمَّل اختياريًا بيد
المستخدم ويبقى خارج Git تمامًا.
"""
import os
from pathlib import Path

ENV_PATH = "LOGISTICS_ASSISTANT_MODEL"
MAX_TOKENS = 320
_CACHE = {"path": None, "llm": None, "failed": False}


def model_path():
    """مسار ملف النموذج الفعّال: متغير البيئة ← الموديل المختار من المخزن ← البديل."""
    override = (os.environ.get(ENV_PATH) or "").strip()
    if override:
        return Path(override).expanduser()
    try:
        from . import model_store
        return model_store.active_path()
    except Exception:      # noqa: BLE001 — غياب المسار لا يعطّل المساعد
        from core.paths import DATA_DIR
        return Path(DATA_DIR) / "assistant" / "model.gguf"


def _backend():
    """محرّك الاستنتاج المحلي المتاح — None لو غير مثبّت."""
    try:
        import llama_cpp  # noqa: F401
        return "llama.cpp"
    except Exception:      # noqa: BLE001
        return None


def is_local_only():
    """هل اختار المستخدم «المكتبة الذكية» من قائمة «تبديل الموديل» (بلا موديل لغوي)؟"""
    try:
        from . import model_store
        return model_store.is_local_only()
    except Exception:      # noqa: BLE001 — مشكلة إعدادات لا تعطّل المساعد
        return False


def _store_state():
    """حالة قائمة «تبديل الموديل» — فارغة لو تعذّرت القراءة (بلا أي سقوط)."""
    try:
        from . import model_store
        return model_store.state()
    except Exception:      # noqa: BLE001
        return {}


def status():
    """حالة النموذج المحلي — تُعرض على الواجهة بصدق (بلا تظاهر بالتوفّر)."""
    path = model_path()
    exists = path.is_file()
    valid = looks_like_gguf(path) if exists else False
    engine = _backend()          # محرّك المكتبة الذكية — تُعرض حالته جنب قائمة التبديل
    backend = engine if valid else None
    local_only = is_local_only()
    store = _store_state()
    return {
        "enabled": bool(valid and backend and not _CACHE["failed"] and not local_only),
        "file_found": exists,
        "engine": engine,
        "backend": backend,
        "path": str(path),
        "name": path.name if exists else "",
        "query_var": ENV_PATH,
        "mode": store.get("mode") or ("local" if local_only else ""),
        "local_only": local_only,
        "local_label": store.get("local_label", "المكتبة الذكية"),
        "local_value": store.get("local_value", ""),
        "models": store.get("models", []),
        "folder": store.get("folder", ""),
        "note": ("نموذج محلي صغير جاهز داخل جهازك — يُستخدم للأسئلة المفتوحة فقط."
                 if (exists and backend) else
                 ("ملف النموذج موجود لكن حزمة llama-cpp-python غير مثبتة على الجهاز."
                  if exists else
                  "مفيش نموذج محلي — المساعد يعمل بمحرك النوايا المحلي بلا أي اعتمادية.")),
    }


def _load():
    """يحمّل النموذج مرة واحدة ويحتفظ به في الذاكرة (بلا أي اتصال شبكي)."""
    if is_local_only():          # «المكتبة الذكية» مختارة عن قصد ⇒ بلا أي موديل لغوي
        return None
    path = model_path()
    if _CACHE["failed"] or not path.is_file() or not looks_like_gguf(path):
        return None
    if _CACHE["llm"] is not None and _CACHE["path"] == str(path):
        return _CACHE["llm"]
    try:
        from llama_cpp import Llama
        _CACHE["llm"] = Llama(model_path=str(path), n_ctx=2048, verbose=False,
                              n_threads=max(2, (os.cpu_count() or 4) - 1))
        _CACHE["path"] = str(path)
        return _CACHE["llm"]
    except Exception:      # noqa: BLE001 — أي فشل يعود للمحرك المحلي بهدوء
        _CACHE["failed"] = True
        return None


GGUF_MAGIC = b"GGUF"


MIN_GGUF_BYTES = 65536  # 64 ك.ب — أصغر نموذج GGUF حقيقي أكبر من ذلك بمراحل


def looks_like_gguf(path):
    """فحص أن الملف نموذج GGUF حقيقي: بصمة «GGUF» + حجم أدنى معقول.

    يمنع أن تُقرأ صفحة تنزيل أو ملف مبتور أو ملف سطر LFS على أنه «جاهز».
    """
    try:
        if path.stat().st_size < MIN_GGUF_BYTES:
            return False
        with open(path, "rb") as handle:
            return handle.read(4) == GGUF_MAGIC
    except OSError:
        return False


def probe():
    """فحص تفصيلي لحالة النموذج الذكي المحلي — يخدم صفحة الإعداد والواجهة.

    بلا أي محاولة تحميل: يفحص وجود الملف وحجمه، وتوفّر محرّك الاستنتاج فقط،
    ويُرجع كذلك سبب التعطّل الحقيقي (إن وُجد) ليتصرّف المستخدم بمعرفة.
    """
    path = model_path()
    exists = path.is_file()
    size_mb = round(path.stat().st_size / (1024 * 1024), 1) if exists else 0.0
    engine = _backend()
    engine_error = ""
    if engine is None:
        try:
            import llama_cpp  # noqa: F401
        except Exception as exc:      # noqa: BLE001
            engine_error = type(exc).__name__
        else:
            engine_error = "unknown"
    valid = looks_like_gguf(path) if exists else False
    local_only = is_local_only()
    ready = bool(valid and engine and not _CACHE["failed"] and not local_only)
    if local_only:
        state = "local_engine"
        hint = ("«المكتبة الذكية» مختارة من قائمة «تبديل الموديل» — المساعد يرد بمحرك "
                "البرنامج نفسه بلا أي موديل لغوي. عايز موديلًا؟ اختاره من القائمة نفسها.")
    elif exists and not valid:
        state = "bad_file"
        hint = ("الملف الموجود ليس نموذج GGUF صحيحًا (صفحة تنزيل أو ملف تالف) — "
                "أعد تنزيل ملف النموذج واستخدم --use لنسخه في مكانه.")
    elif ready:
        state, hint = "ready", "النموذج جاهز — المساعد يجاوب الأسئلة المفتوحة من جهازك."
    elif not exists and engine:
        state, hint = "no_model", "المحرّك مثبّت، ناقص ملف النموذج (100–400 ميجابايت) في مكانه."
    elif exists and not engine:
        state, hint = "no_engine", "ملف النموذج موجود، ناقص تثبيت محرّك الاستنتاج المحلي."
    else:
        state, hint = "empty", "لا محرّك ولا نموذج — والمساعد يعمل الآن بمحرك النوايا المحلي."
    return {"state": state, "hint": hint, "file_found": exists, "file_valid": valid,
            "size_mb": size_mb, "local_only": local_only,
            "engine": engine, "engine_error": engine_error, "ready": ready,
            "failed_once": bool(_CACHE["failed"]), "path": str(path),
            "env_var": ENV_PATH,
            "dir": str(path.parent)}


def version():
    """إصدار محرّك الاستنتاج المحلي إن كان مثبتًا (يُعرض على صفحة الإعداد)."""
    try:
        import llama_cpp     # noqa: F401
        return getattr(llama_cpp, "__version__", "") or "مثبّت"
    except Exception:        # noqa: BLE001
        return ""


def digest(year, month):
    """سياق مختصر من بيانات الشهر الحقيقية يُمرَّر للنموذج (أرقام لا تُخترع)."""
    try:
        from data_access import db_tameedat as dt
        from data_access import db_raghibin as rp
        from data_access import db_recruits, db_rations as dr
        from data_access import db_warehouses as dw
        from services import tameed_alerts
        from core.config import MONTH_NAMES

        records = dt.month_records(year, month)
        totals = dt.month_summary(year, month)[1]
        stats = tameed_alerts.summary(year, month)
        forces = rp.entity_force_counts(year, month)
        force_o = sum(row["officers"] for row in forces.values())
        force_i = sum(row["individuals"] for row in forces.values())
        items = sum(len(dw.list_items(year, month, cycle))
                    for cycle in ("supply", "contractor"))
        active = []
        for section, label in (("tamween", "التمونيية"), ("contractor", "المتعهد")):
            kind = dr.get_activation(year, month, section)
            if kind:
                active.append(f"{label}={len(dr.get_items(year, month, section, kind)[0])} صنف")
        lines = [
            f"الشهر النشط: {MONTH_NAMES[month - 1]} {year}",
            f"عدد التأميدات: {len(records)} — جهات مومدة: {totals['entities']}",
            f"إجمالي القوة: ض {totals['officers']} · أ {totals['individuals']} "
            f"· م {totals['recruits']} (الإجمالي {totals['grand']})",
            f"أيام التميد الفعلية: {totals['active_days']}",
            f"تنبيهات الشهر: {stats['problem_rows']} (خطر {stats['danger']})",
            f"الكوادر المعتمدة: {len(forces)} جهة — ض {force_o} · أ {force_i}",
            f"المقررات النشطة: {' · '.join(active) or 'لا يوجد'}",
            f"أصناف المخازن: {items}",
            f"المجندون: {len(db_recruits.list_recruits(year, month))}",
        ]
        return "\n".join(lines)
    except Exception:      # noqa: BLE001 — فشل السياق يعني ببساطة «لا نموذج»
        return ""


SYSTEM_PROMPT = (
    "أنت مساعد منظومة «مخازن التعيينات» التابعة لقطاع وسط سيناء (قسم التعيينات). "
    "أجب بالعربية الفصحى المبسطة وبإيجاز شديد (سطران إلى خمسة). "
    "استخدم الأرقام الواردة في «بيانات الشهر» فقط ولا تخترع أي رقم أو اسم جهة، "
    "ولو السؤال خارج المنظومة اشرح ذلك في سطر واحد واقترح ما تستطيع فعله."
)


def try_answer(question, year, month):
    """رد النموذج المحلي إن كان متاحًا فعلًا، وإلا None (المحرك المحلي يتولى)."""
    llm = _load()
    if llm is None or not (question or "").strip():
        return None
    context = digest(year, month)
    if not context:
        return None
    try:
        response = llm.create_chat_completion(
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "system", "content": "بيانات الشهر الحقيقية:\n" + context},
                      {"role": "user", "content": question.strip()}],
            max_tokens=MAX_TOKENS, temperature=0.2)
        text = (response["choices"][0]["message"]["content"] or "").strip()
        return text or None
    except Exception:      # noqa: BLE001 — النموذج لا يُسقط المساعد أبدًا
        _CACHE["failed"] = True
        return None
