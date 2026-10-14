# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مخزن النماذج المحلية للمساعد — مجلد واحد يضع فيه المستخدم ملفات GGUF بنفسه.

بتوجيه المستخدم: لا إعدادات ذكاء اصطناعي ولا تنزيل من داخل البرنامج. المستخدم ينزّل
ملف النموذج من الرابط بنفسه ويضعه في:

    database/assistant/models/

ويُنشأ المجلد تلقائيًا عند تشغيل البرنامج ومعه ملف «اقرأني — خطوات تشغيل النموذج.txt»
بالخطوات بالتفصيل الكامل. كل ملفات `*.gguf` الموجودة تُدرج، والنموذج الفعّال يُحفظ في
إعدادات البرنامج (`assistant_model`)، وقائمة «تبديل النموذج» المنسدلة في لوحة المحادثة تختار
إما «المكتبة الذكية» (محرك البرنامج بلا أي نموذج لغوي) وإما نموذجًا منها باسمه.

لا شيء يُنزَّل تلقائيًا ولا في الخلفية، والملفات لا تُرفع على GitHub أبدًا.
"""
import os
from pathlib import Path

SETTING_KEY = "assistant_model"
README_NAME = "اقرأني — خطوات تشغيل النموذج.txt"

# «المكتبة الذكية» = محرك البرنامج نفسه (بلا أي نموذج لغوي). اختيارها يُحفظ في الإعدادات
# كقيمة خاصة، فيعرف المساعد أن المستخدم اختارها عن قصد ولا يرجع تلقائيًا لأول ملف موجود.
LOCAL_ONLY = "__local_engine__"
LOCAL_LABEL = "المكتبة الذكية"
LOCAL_VALUE = ""            # قيمة الخيار في القائمة المنسدلة (فارغة = محرك البرنامج)

# روابط التنزيل المباشرة — تُطبع في ملف «اقرأني» ليحمّل المستخدم بنفسه.
DOWNLOADS = [
    ("Qwen2.5-0.5B-Instruct (Q4_K_M)", "≈ ٤٠٠ ميجابايت",
     "الخيار الأول — الأصغر الذي يفهم العربية بشكل مقبول",
     "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/"
     "qwen2.5-0.5b-instruct-q4_k_m.gguf"),
    ("SmolLM2-135M-Instruct (Q4_K_M)", "≈ ١٠٠ ميجابايت",
     "الأخف — للتجربة السريعة، عربي بسيط",
     "https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct-GGUF/resolve/main/"
     "SmolLM2-135M-Instruct-Q4_K_M.gguf"),
    ("Gemma-3-270M-it (Q4)", "≈ ٢٠٠ ميجابايت",
     "وسط — يدعم لغات متعددة ومنها العربية",
     "https://huggingface.co/unsloth/gemma-3-270m-it-GGUF/resolve/main/"
     "gemma-3-270m-it-Q4_K_M.gguf"),
    ("Qwen2.5-1.5B-Instruct (Q4_K_M)", "≈ ١ جيجابايت",
     "الأقوى — للأجهزة التي ذاكرتها ٨ جيجا أو أكثر",
     "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
     "qwen2.5-1.5b-instruct-q4_k_m.gguf"),
]


def _data_dir():
    from core.paths import DATA_DIR
    return Path(DATA_DIR)


def models_dir():
    """مجلد النماذج داخل بيانات المستخدم — يُنشأ عند أول تشغيل."""
    return _data_dir() / "assistant" / "models"


def legacy_path():
    """المكان البديل (يدوي): database/assistant/model.gguf — مدعوم كما هو."""
    return _data_dir() / "assistant" / "model.gguf"


def instructions_text():
    """نص ملف «اقرأني» — الخطوات بالتفصيل الكامل (يُكتب مرة عند أول تشغيل)."""
    folder = str(models_dir())
    lines = [
        "اقرأني — خطوات تشغيل النموذج الذكي المحلي",
        "========================================",
        "",
        "أنت الآن داخل المجلد الذي تُحفظ فيه ملفات النموذج:",
        f"    {folder}",
        "",
        "ضع هنا أي ملف نموذج بصيغة GGUF (اسمه ينتهي بـ .gguf) وسيُستخدم من المساعد",
        "داخل البرنامج. لا يلزم تغيير اسمه — اتركه كما نزّلته.",
        "",
        "--------------------------------------------------------------------",
        "الخطوة ١ — نزّل ملف النموذج من الرابط (مرة واحدة، ثم يعمل البرنامج بلا إنترنت)",
        "--------------------------------------------------------------------",
        "",
        "اختر نموذجًا واحدًا من القائمة التالية وانزّله على جهازك:",
        "",
    ]
    for index, (name, size, note, url) in enumerate(DOWNLOADS, 1):
        lines += [f"[{index}] {name} — الحجم {size}", f"     {note}", f"     {url}", ""]
    lines += [
        "ملاحظات على التنزيل:",
        "- انسخ الرابط والصقه في المتصفح؛ إذا سألك المتصفح «حفظ باسم» فاحفظه على سطح",
        "  المكتب أولًا ثم انقله إلى هذا المجلد.",
        "- نزّل ملفًا واحدًا للبداية؛ وإذا نزّلت أكثر من ملف فسيدرجها البرنامج كلها،",
        "  وتتيح لك قائمة «تبديل النموذج» في لوحة المساعد الاختيار بينها بالاسم.",
        "- الملف كبير الحجم — انتظر حتى يكتمل التنزيل ١٠٠٪.",
        "- إذا توقّف التنزيل فعاود المحاولة أو استخدم متصفحًا آخر.",
        "",
        "--------------------------------------------------------------------",
        "الخطوة ٢ — انقل الملف إلى هذا المجلد",
        "--------------------------------------------------------------------",
        "",
        "1) خذ الملف الذي نزّلته (مثال: qwen2.5-0.5b-instruct-q4_k_m.gguf).",
        "2) ضعه داخل هذا المجلد نفسه (نفس المجلد الذي يحتوي على ملف «اقرأني» هذا).",
        "3) تأكد من أن:",
        "   - اسم الملف ينتهي بـ .gguf",
        "   - حجمه قريب من الحجم التقريبي المذكور بجوار النموذج في القائمة أعلاه",
        "   - لا يوجد ملف بجانبه بنفس الاسم مع امتداد غريب مثل .crdownload (فهو مؤشر على أن",
        "     التنزيل لم يكتمل بعد)",
        "4) إذا وصلك الملف مضغوطًا (zip) فك الضغط أولًا ثم ضع ملف الـ gguf نفسه.",
        "",
        "--------------------------------------------------------------------",
        "الخطوة ٣ — ثبّت محرّك التشغيل مرة واحدة (بإنترنت للمرة الأخيرة)",
        "--------------------------------------------------------------------",
        "",
        "من المجلد الرئيسي للبرنامج (الذي يحتوي على START.bat) افتح نافذة أوامر: اكتب cmd في",
        "شريط عنوان المجلد ثم Enter، ثم نفّذ:",
        "",
        "    .venv\\Scripts\\pip install -r requirements-ai.txt",
        "",
        "وإذا ظهرت أي مشكلة فجرّب هذا السطر بدلًا منه:",
        "",
        "    .venv\\Scripts\\pip install llama-cpp-python "
        "--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu",
        "",
        "انتظر حتى تظهر Successfully installed. وإذا كُتب already satisfied فمعنى ذلك أن",
        "المحرّك مثبّت بالفعل — أكمل الخطوات التالية.",
        "",
        "--------------------------------------------------------------------",
        "الخطوة ٤ — شغّل البرنامج وتأكد",
        "--------------------------------------------------------------------",
        "",
        "1) افتح البرنامج عبر START.bat وسجّل الدخول بشكل طبيعي.",
        "2) افتح لوحة «المساعد المحلي» (الزر الجانبي الخاص بالضابط).",
        "3) فوق اللوحة ستجد قائمة منسدلة اسمها «تبديل النموذج» — اختر منها اسم",
        "   النموذج الذي وضعته وسيكون كل شيء على ما يرام. وإن لم تختر شيئًا (أو اخترت «المكتبة",
        "   الذكية») سيعمل المساعد بمحرك البرنامج نفسه دون أي نموذج.",
        "4) اسأل المساعد سؤالًا مفتوحًا (مثل: اكتب لي جملة ترحيب قصيرة) — إذا ظهرت",
        "   إجابة طبيعية من النموذج فهذا يعني أن كل شيء يعمل.",
        "5) القائمة نفسها مخصصة للتبديل: وضعت أكثر من نموذج؟ اختر أيًا منها بالاسم.",
        "6) وبجانب القائمة ستعرف حالة محرّك التشغيل: «المكتبة ✓ تعمل» أو «✗ غير متاحة».",
        "",
        "--------------------------------------------------------------------",
        "أسئلة شائعة",
        "--------------------------------------------------------------------",
        "",
        "- هل النموذج إلزامي؟ لا. البرنامج مكتمل بدونه: المساعد يفهم العربية ويفتح التبويبات،",
        "  ويجلب كل أرقام الشهر من البرنامج نفسه. النموذج يضيف فقط ردودًا للأسئلة المفتوحة.",
        "- والأرقام والإحصاءات؟ دائمًا من طبقات البرنامج نفسه — لا يمكن للنموذج اختراع رقم.",
        "- هل تُرفع على GitHub أو تدخل في ملف التحميل؟ لا أبدًا — هذه الملفات على جهازك فقط.",
        "- ماذا لو حذفت الملف؟ يعمل البرنامج بشكل طبيعي بمحرك النوايا المحلي، ويمكنك وضع ملف",
        "  آخر في أي وقت.",
        "- كيف أعرف أن النموذج يعمل فعلًا؟ اسأل سؤالًا مفتوحًا (مثل طلب جملة ترحيب)؛",
        "  تختلف إجابة النموذج الطبيعية عن إجابات المحرك المعتادة.",
        "",
        "بعد هذه الخطوات يعمل البرنامج دون اتصال بالإنترنت.",
    ]
    return "\r\n".join(lines) + "\r\n"


def ensure_folder():
    """ينشئ مجلد النماذج وملف «اقرأني» عند أول تشغيل (ويحدّث الملف لو تغيّر).

    لا شبكة ولا تنزيل — مجرد مجلد محلي + نص الخطوات، ويعمل داخل try في app.py
    بحيث لا يعطّل التشغيل أبدًا. يُرجع المسار أو None عند تعذّر الكتابة.
    """
    try:
        folder = models_dir()
        folder.mkdir(parents=True, exist_ok=True)
        readme = folder / README_NAME
        text = instructions_text()
        old = ""
        if readme.is_file():
            try:
                old = readme.read_text(encoding="utf-8-sig")
            except OSError:
                old = ""
        if old.replace("\r\n", "\n") != text.replace("\r\n", "\n"):
            readme.write_text(text, encoding="utf-8-sig")
        return folder
    except OSError:
        return None


def _gguf_files():
    """كل ملفات GGUF في المخزن (المجلد الأساسي ثم المكان البديل)."""
    found = []
    for folder in (models_dir(), legacy_path().parent):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.gguf")):
            found.append(path)
    return found


def find_model(name):
    """يبحث عن ملف نموذج باسمه داخل المخزن — حماية من أي مسار خارجي."""
    if not name:
        return None
    safe = Path(name).name
    for path in _gguf_files():
        if path.name == safe:
            return path
    return None


def _setting(value=None):
    """قراءة/كتابة النموذج الفعّال في إعدادات البرنامج (بلا مساس ببيانات الشهر)."""
    from data_access import database
    if value is None:
        return (database.get_setting(SETTING_KEY) or "").strip()
    database.set_setting(SETTING_KEY, (value or "").strip())
    return value


def active_name():
    """اسم النموذج الفعّال: الإعداد أولًا، ثم المكان البديل، ثم أول ملف موجود.

    اختيار «المكتبة الذكية» من القائمة يُلغي النموذج اللغوي عن قصد (يُرجع "").
    """
    chosen = _setting()
    if chosen == LOCAL_ONLY:
        return ""
    if chosen and find_model(chosen):
        return chosen
    if legacy_path().is_file():
        return legacy_path().name
    files = _gguf_files()
    return files[0].name if files else ""


def is_local_only():
    """هل اختار المستخدم «المكتبة الذكية» من قائمة تبديل النموذج (بلا نموذج لغوي)؟"""
    try:
        return _setting() == LOCAL_ONLY
    except Exception:      # noqa: BLE001 — مشكلة إعدادات لا تُسقط المساعد
        return False


def active_path():
    """مسار النموذج الفعّال (أو المسار المتوقع لو لا يوجد أي نموذج بعد)."""
    name = active_name()
    if name:
        found = find_model(name)
        if found:
            return found
    return models_dir() / "model.gguf"


def set_active(name):
    """يبدّل النموذج الفعّال — بشرط أن الملف موجود فعلًا."""
    path = find_model(name)
    if not path:
        return False, "الملف غير موجود في مجلد النماذج"
    _setting(path.name)
    _reset_cache()
    return True, path.name


def label():
    """اسم قصير للنموذج الفعّال — يظهر على زر التبديل في لوحة المساعد."""
    name = active_name()
    if not name:
        return ""
    short = name[:-5] if name.lower().endswith(".gguf") else name
    if len(short) > 40:
        short = short[:38] + "…"
    return short


def list_models():
    """جدول النماذج الموجودة على الجهاز مع حجمها وهل هي فعّالة."""
    active = active_name()
    rows = []
    for path in _gguf_files():
        try:
            size_mb = round(path.stat().st_size / (1024 * 1024), 1)
        except OSError:
            continue
        short = path.name[:-5] if path.name.lower().endswith(".gguf") else path.name
        rows.append({"name": path.name, "label": short, "size_mb": size_mb,
                     "active": path.name == active,
                     "valid": looks_like_gguf(path)})
    return rows


def looks_like_gguf(path):
    """بصمة «GGUF» + حجم أدنى معقول — نفس فحص model.py (بلا استيراد دائري)."""
    from .model import MIN_GGUF_BYTES
    try:
        if path.stat().st_size < MIN_GGUF_BYTES:
            return False
        with open(path, "rb") as handle:
            return handle.read(4) == b"GGUF"
    except OSError:
        return False


def set_local_only():
    """يفعّل «المكتبة الذكية»: المساعد يرد بمحرك البرنامج نفسه بلا أي نموذج لغوي."""
    _setting(LOCAL_ONLY)
    _reset_cache()
    return True, ("تم اختيار «المكتبة الذكية» — المساعد يعمل بمحرك البرنامج نفسه "
                  "بلا أي نموذج لغوي.")


def select(value):
    """قائمة «تبديل النموذج» في لوحة المحادثة: «المكتبة الذكية» أو نموذج GGUF باسمه.

    - فارغ أو «local» ⇒ المكتبة الذكية (محرك البرنامج بلا نموذج).
    - اسم ملف موجود (بامتداد .gguf أو بدونه) ⇒ يُفعَّل ويُحفظ في الإعدادات.
    - اسم غير موجود أو ملف غير صالح ⇒ رسالة صريحة بلا تفعيل وهمي.
    """
    wanted = (value or "").strip()
    if wanted in (LOCAL_VALUE, LOCAL_ONLY, LOCAL_LABEL, "local"):
        return set_local_only()
    path = find_model(wanted) or find_model(wanted + ".gguf")
    if not path:
        return False, ("لا يوجد ملف بهذا الاسم في مجلد النماذج — حدّث القائمة، أو ضع ملف "
                       "GGUF في database/assistant/models، والخطوات في ملف «اقرأني» داخله.")
    if not looks_like_gguf(path):
        return False, ("الملف الذي اخترته ليس ملف GGUF صالحًا — على الأرجح لم يكتمل التنزيل. "
                       "أعد تنزيل ملف النموذج كاملًا (الخطوات في ملف «اقرأني»).")
    chosen, name = set_active(path.name)
    if not chosen:
        return False, f"{name} — ضع الملف في مجلد النماذج مرة أخرى."
    return True, f"تم تفعيل النموذج: {name} — الأسئلة المفتوحة يُجاب عنها من جهازك."


def state():
    """حالة قائمة «تبديل النموذج» — تُبنى منها الخيارات في لوحة المحادثة (مصدر واحد للحقيقة)."""
    rows = list_models()
    active = active_name()
    return {"mode": "model" if active else "local",
            "value": active,
            "label": label() or LOCAL_LABEL,
            "local_value": LOCAL_VALUE,
            "local_label": LOCAL_LABEL,
            "count": len(rows),
            "models": rows,
            "folder": str(models_dir())}


def _reset_cache():
    """تصفير كاش النموذج المحمّل حتى يُحمل الملف الفعّال الجديد فورًا."""
    try:
        from . import model as bridge
        bridge._CACHE.update({"path": None, "llm": None, "failed": False})
    except Exception:      # noqa: BLE001 — تصفير الكاش لا يُسقط شيئًا
        pass
