# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""مخزن الموديلات المحلية للمساعد — فولدر واحد يضع فيه المستخدم ملفات GGUF بنفسه.

بتوجيه المستخدم: لا إعدادات ذكاء اصطناعي ولا تنزيل من داخل البرنامج. المستخدم ينزّل
ملف الموديل من اللينك بنفسه ويضعه في:

    database/assistant/models/

ويُنشأ الفولدر تلقائيًا عند تشغيل البرنامج ومعه ملف «اقرأني — خطوات تشغيل النموذج.txt»
بالخطوات بالتفصيل الممل. كل ملفات `*.gguf` الموجودة تُدرج، والموديل الفعّال يُحفظ في
إعدادات البرنامج (`assistant_model`)، وقائمة «تبديل الموديل» المنسدلة في الشات تختار
إما «المكتبة الذكية» (محرك البرنامج بلا أي موديل لغوي) وإما موديلًا منها باسمه.

لا شيء يُنزَّل تلقائيًا ولا في الخلفية، والملفات لا تُرفع على GitHub أبدًا.
"""
import os
from pathlib import Path

SETTING_KEY = "assistant_model"
README_NAME = "اقرأني — خطوات تشغيل النموذج.txt"

# «المكتبة الذكية» = محرك البرنامج نفسه (بلا أي موديل لغوي). اختيارها يُحفظ في الإعدادات
# كقيمة خاصة، فيعرف المساعد أن المستخدم اختارها عن قصد ولا يرجع تلقائيًا لأول ملف موجود.
LOCAL_ONLY = "__local_engine__"
LOCAL_LABEL = "المكتبة الذكية"
LOCAL_VALUE = ""            # قيمة الخيار في القائمة المنسدلة (فارغة = محرك البرنامج)

# روابط التنزيل المباشرة — تُطبع في ملف «اقرأني» ليحمّل المستخدم بنفسه.
DOWNLOADS = [
    ("Qwen2.5-0.5B-Instruct (Q4_K_M)", "≈ ٤٠٠ ميجا",
     "الترشيح الأول — أصغر واحد يفهم عربي معقول",
     "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/"
     "qwen2.5-0.5b-instruct-q4_k_m.gguf"),
    ("SmolLM2-135M-Instruct (Q4_K_M)", "≈ ١٠٠ ميجا",
     "الأخف خالص — للتجربة السريعة، عربي بسيط",
     "https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct-GGUF/resolve/main/"
     "SmolLM2-135M-Instruct-Q4_K_M.gguf"),
    ("Gemma-3-270M-it (Q4)", "≈ ٢٠٠ ميجا",
     "وسط — يدعم لغات متعددة ومنها العربية",
     "https://huggingface.co/unsloth/gemma-3-270m-it-GGUF/resolve/main/"
     "gemma-3-270m-it-Q4_K_M.gguf"),
    ("Qwen2.5-1.5B-Instruct (Q4_K_M)", "≈ ١ جيجا",
     "الأقوى — للأجهزة اللي رامها ٨ جيجا أو أكتر",
     "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
     "qwen2.5-1.5b-instruct-q4_k_m.gguf"),
]


def _data_dir():
    from core.paths import DATA_DIR
    return Path(DATA_DIR)


def models_dir():
    """فولدر الموديلات داخل بيانات المستخدم — يُنشأ عند أول تشغيل."""
    return _data_dir() / "assistant" / "models"


def legacy_path():
    """المكان البديل (يدوي): database/assistant/model.gguf — مدعوم كما هو."""
    return _data_dir() / "assistant" / "model.gguf"


def instructions_text():
    """نص ملف «اقرأني» — الخطوات بالتفصيل الممل (يُكتب مرة عند أول تشغيل)."""
    folder = str(models_dir())
    lines = [
        "اقرأني — خطوات تشغيل النموذج الذكي المحلي",
        "========================================",
        "",
        "الفولدر اللي إنت فيه دلوقتي هو مكان ملفات الموديل:",
        f"    {folder}",
        "",
        "حط هنا أي ملف نموذج بصيغة GGUF (اسمه ينتهي بـ .gguf) وهيشتغل مع المساعد اللي",
        "جوه البرنامج. مش لازم تغيّر اسمه — سيبه زي ما نزّلته.",
        "",
        "--------------------------------------------------------------------",
        "الخطوة ١ — نزّل ملف الموديل من اللينك (مرة واحدة، وبعدها مفيش إنترنت خلاص)",
        "--------------------------------------------------------------------",
        "",
        "اختار موديل واحد من دول وانزّله على جهازك:",
        "",
    ]
    for index, (name, size, note, url) in enumerate(DOWNLOADS, 1):
        lines += [f"[{index}] {name} — الحجم {size}", f"     {note}", f"     {url}", ""]
    lines += [
        "ملاحظات على التنزيل:",
        "- انسخ اللينك والصقه في المتصفح؛ لو المتصفح سألك «حفظ باسم» احفظه على سطح",
        "  المكتب الأول وبعدين انقله للفولدر ده.",
        "- حمّل ملف واحد بس للبداية؛ ولو نزّلت أكتر من واحد البرنامج هيشوفهم كلهم",
        "  وقائمة «تبديل الموديل» في لوحة المساعد هيخليك تختار بينهم بالاسم.",
        "- الملف حجمه كبير — استنى لحد ما التنزيل يخلص ١٠٠٪.",
        "- لو حسيت إن التنزيل واقف جرّب تاني أو استخدم متصفحًا تانيًا.",
        "",
        "--------------------------------------------------------------------",
        "الخطوة ٢ — انقل الملف للفولدر ده",
        "--------------------------------------------------------------------",
        "",
        "1) خد الملف اللي نزلته (مثال: qwen2.5-0.5b-instruct-q4_k_m.gguf).",
        "2) حطه جوه الفولدر ده نفسه (نفس الفولدر اللي فيه ملف «اقرأني» ده).",
        "3) تأكد إن:",
        "   - اسم الملف بينتهي بـ .gguf",
        "   - حجمه معقول لموديله (٤٠٠ ميجا للموديل الكبير، ١٠٠ ميجا للصغير … إلخ)",
        "   - مفيش ملف جنبه بنفس الاسم وامتداد غريب زي .crdownload (ده معناه أن",
        "     التنزيل لسه ما خلصش)",
        "4) لو الملف جالك مضغوط (zip) فكّ الضغط الأول وحط ملف الـ gguf نفسه.",
        "",
        "--------------------------------------------------------------------",
        "الخطوة ٣ — ثبّت محرّك التشغيل مرة واحدة (بإنترنت لآخر مرة)",
        "--------------------------------------------------------------------",
        "",
        "من فولدر البرنامج الرئيسي (اللي فيه START.bat) افتح نافذة أوامر: اكتب cmd في",
        "شريط عنوان الفولدر ثم Enter، وبعدها نفّذ:",
        "",
        "    .venv\\Scripts\\pip install -r requirements-ai.txt",
        "",
        "ولو ظهرت أي مشكلة جرّب السطر ده بدلًا منه:",
        "",
        "    .venv\\Scripts\\pip install llama-cpp-python "
        "--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu",
        "",
        "استنى لحد ما يقول Successfully installed. ولو مكتوب already satisfied فده",
        "معناه أن المحرّك متثبّت خلاص — تمام، كمّل.",
        "",
        "--------------------------------------------------------------------",
        "الخطوة ٤ — شغّل البرنامج وتأكد",
        "--------------------------------------------------------------------",
        "",
        "1) افتح البرنامج بـ START.bat وسجّل الدخول عادي.",
        "2) افتح لوحة «المساعد المحلي» (الزر الجانبي بتاع الضابط).",
        "3) فوق اللوحة هتلاقي قائمة منسدلة اسمها «تبديل الموديل» — اختار منها اسم",
        "   الموديل اللي حطيته فكل حاجة تمام. ولو مختارتش حاجة (أو اخترت «المكتبة",
        "   الذكية») المساعد يشتغل بمحرك البرنامج نفسه بلا أي موديل.",
        "4) اسأل المساعد سؤالًا مفتوحًا (مثلًا: اكتبلي جملة ترحيب قصيرة) — لو ردّ",
        "   ردًّا طبيعيًّا من النموذج فكله شغال.",
        "5) القائمة دي نفسها للتبديل: حاطط أكتر من موديل؟ اختار أي واحد منهم بالاسم.",
        "6) وجنب القائمة بيعرّفك حالة محرّك التشغيل: «المكتبة ✓ شغالة» أو «✗ ناقصة».",
        "",
        "--------------------------------------------------------------------",
        "أسئلة شائعة",
        "--------------------------------------------------------------------",
        "",
        "- لازم الموديل؟ لا. البرنامج كامل من غيره: المساعد بيفهم عربي، بيفتح التابات،",
        "  وبيجيب كل أرقام الشهر من البرنامج نفسه. الموديل بيزوّد ردود الأسئلة المفتوحة بس.",
        "- والأرقام والإحصاءات؟ دايمًا من طبقات البرنامج نفسه — النموذج مستحيل يخترع رقم.",
        "- هيترفع على GitHub أو يدخل ملف التحميل؟ لا أبدًا — الملفات دي على جهازك بس.",
        "- لو مسحت الملف؟ البرنامج يشتغل عادي بمحرك النوايا المحلي، وتقدر تحط ملف",
        "  تاني في أي وقت.",
        "- إزاي أعرف إن الموديل اشتغل فعلًا؟ اسأل سؤالًا مفتوحًا (زي طلب جملة ترحيب)؛",
        "  الرد الطبيعي من النموذج بيبان مختلف عن ردود المحرك العادي.",
        "",
        "بعد الخطوات دي البرنامج يعمل أوفلاين ١٠٠٪ بلا أي إنترنت.",
    ]
    return "\r\n".join(lines) + "\r\n"


def ensure_folder():
    """ينشئ فولدر الموديلات وملف «اقرأني» عند أول تشغيل (ويحدّث الملف لو تغيّر).

    لا شبكة ولا تنزيل — مجرد فولدر محلي + نص الخطوات، ويعمل داخل try في app.py
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
    """كل ملفات GGUF في المخزن (الفولدر الأساسي ثم المكان البديل)."""
    found = []
    for folder in (models_dir(), legacy_path().parent):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.gguf")):
            found.append(path)
    return found


def find_model(name):
    """يبحث عن ملف موديل باسمه داخل المخزن — حماية من أي مسار خارجي."""
    if not name:
        return None
    safe = Path(name).name
    for path in _gguf_files():
        if path.name == safe:
            return path
    return None


def _setting(value=None):
    """قراءة/كتابة الموديل الفعّال في إعدادات البرنامج (بلا مساس ببيانات الشهر)."""
    from data_access import database
    if value is None:
        return (database.get_setting(SETTING_KEY) or "").strip()
    database.set_setting(SETTING_KEY, (value or "").strip())
    return value


def active_name():
    """اسم الموديل الفعّال: الإعداد أولًا، ثم المكان البديل، ثم أول ملف موجود.

    اختيار «المكتبة الذكية» من القائمة يُلغي الموديل اللغوي عن قصد (يُرجع "").
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
    """هل اختار المستخدم «المكتبة الذكية» من قائمة تبديل الموديل (بلا موديل لغوي)؟"""
    try:
        return _setting() == LOCAL_ONLY
    except Exception:      # noqa: BLE001 — مشكلة إعدادات لا تُسقط المساعد
        return False


def active_path():
    """مسار الموديل الفعّال (أو المسار المتوقع لو لا يوجد أي موديل بعد)."""
    name = active_name()
    if name:
        found = find_model(name)
        if found:
            return found
    return models_dir() / "model.gguf"


def set_active(name):
    """يبدّل الموديل الفعّال — بشرط أن الملف موجود فعلًا."""
    path = find_model(name)
    if not path:
        return False, "الملف غير موجود في فولدر الموديلات"
    _setting(path.name)
    _reset_cache()
    return True, path.name


def label():
    """اسم قصير للموديل الفعّال — يظهر على زر التبديل في لوحة المساعد."""
    name = active_name()
    if not name:
        return ""
    short = name[:-5] if name.lower().endswith(".gguf") else name
    if len(short) > 40:
        short = short[:38] + "…"
    return short


def list_models():
    """جدول الموديلات الموجودة على الجهاز مع حجمها وهل هي فعّالة."""
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
    """يفعّل «المكتبة الذكية»: المساعد يرد بمحرك البرنامج نفسه بلا أي موديل لغوي."""
    _setting(LOCAL_ONLY)
    _reset_cache()
    return True, ("تم اختيار «المكتبة الذكية» — المساعد يعمل بمحرك البرنامج نفسه "
                  "بلا أي موديل لغوي.")


def select(value):
    """قائمة «تبديل الموديل» في الشات: «المكتبة الذكية» أو موديل GGUF باسمه.

    - فارغ أو «local» ⇒ المكتبة الذكية (محرك البرنامج بلا موديل).
    - اسم ملف موجود (بامتداد .gguf أو بدونه) ⇒ يُفعَّل ويُحفظ في الإعدادات.
    - اسم غير موجود أو ملف غير صالح ⇒ رسالة صريحة بلا تفعيل وهمي.
    """
    wanted = (value or "").strip()
    if wanted in (LOCAL_VALUE, LOCAL_ONLY, LOCAL_LABEL, "local"):
        return set_local_only()
    path = find_model(wanted) or find_model(wanted + ".gguf")
    if not path:
        return False, ("مفيش ملف بالاسم ده في فولدر الموديلات — حدّث القائمة، أو حط ملف "
                       "GGUF في database/assistant/models والخطوات في ملف «اقرأني» جواه.")
    if not looks_like_gguf(path):
        return False, ("الملف اللي اخترته مش ملف GGUF صالح — غالبًا التنزيل ما كمّلش. "
                       "أعد تنزيل ملف النموذج كاملًا (الخطوات في ملف «اقرأني»).")
    chosen, name = set_active(path.name)
    if not chosen:
        return False, f"{name} — حط الملف في فولدر الموديلات تاني."
    return True, f"تم تفعيل الموديل: {name} — الأسئلة المفتوحة هيرد عليها من جهازك."


def state():
    """حالة قائمة «تبديل الموديل» — تُبنى منها الخيارات في الشات (مصدر واحد للحقيقة)."""
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
