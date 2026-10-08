# -*- coding: utf-8 -*-
"""مساعد الموديل المحلي — أدوات سطر أوامر للنموذج اللغوي الأوفلاين (اختياري تمامًا).

النظام (بتوجيه المستخدم ٠٨/١٠/٢٠٢٦): لا تنزيل ولا إعدادات داخل البرنامج — إنت
بتنزّل ملف GGUF بنفسك من اللينك وتحطه في فولدر الموديلات، وهذا السكربت مساعدة إضافية:

    python scripts/assistant_model.py --check
        يفحص الحالة الحقيقية: ملف الموديل + محرّك الاستنتاج + الجاهزية.

    python scripts/assistant_model.py --use "D:\\models\\qwen2.5-0.5b-q4.gguf"
        ينقل/ينسخ ملف GGUF الذي نزّلته إلى فولدر database/assistant/models
        (بلا إنترنت وبلا أي اعتمادية) ثم يفحص ويتأكد.

    python scripts/assistant_model.py --ask "قولي أعلى جهة في القوة"
        تجربة فعلية: يمرّ السؤال من نفس مسار المساعد في البرنامج ويعرض الرد.

وملف «اقرأني» داخل فولدر الموديلات نفسه فيه الخطوات كلها بالتفصيل الممل.
لا يُرفع النموذج على GitHub أبدًا، ولا يدخل مثبّت البرنامج (قاعدة: محلي فقط).
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _human(size_bytes):
    return f"{size_bytes / (1024 * 1024):.1f} ميجابايت"


def _store():
    from services.assistant import model_store
    return model_store


def _probe():
    from services.assistant import model as brain_model
    return brain_model.probe()


def cmd_check(_args):
    store = _store()
    store.ensure_folder()
    probe = _probe()
    print("=== حالة المساعد الذكي المحلي ===")
    print(f"فولدر الموديلات    : {store.models_dir()}")
    print(f"ملف النموذج        : {probe['path']}")
    print(f"موجود؟             : {'نعم — ' + _human(probe['size_mb'] * 1024 * 1024) if probe['file_found'] else 'لا'}")
    print(f"محرّك الاستنتاج     : {probe['engine'] or 'غير مثبّت'}"
          + (f" ({probe['engine_error']})" if probe['engine_error'] else ""))
    print(f"الجاهزية           : {probe['hint']}")
    models = store.list_models()
    if models:
        print("الموديلات الموجودة :")
        for row in models:
            mark = "← الفعّال" if row["active"] else ("" if row["valid"] else "(ملف غير صالح)")
            print(f"   - {row['name']}  ({row['size_mb']} م.ب) {mark}")
    if not probe["engine"]:
        print("\nللتثبيت مرة واحدة (بإنترنت):")
        print("    .venv\\Scripts\\pip install -r requirements-ai.txt")
    if not probe["file_found"]:
        print("لجلب نموذج صغير: نزّل ملف GGUF من اللينك وحطه في الفولدر الموضح فوق،")
        print("أو:  python scripts/assistant_model.py --use \"مسار الملف.gguf\"")
        print("(الخطوات بالتفصيل في ملف «اقرأني» جوه الفولدر)")
    if probe.get("ready"):
        from services.assistant import model as brain_model
        print(f"\nالموديل الفعّال: {brain_model.model_path().name}")
    return 0 if probe["ready"] else 1


def cmd_use(args):
    store = _store()
    source = Path(args.use).expanduser()
    if not source.is_file():
        print(f"⛔ الملف غير موجود: {source}")
        return 2
    target = store.models_dir() / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == target.resolve():
        print(f"✔ الملف بالفعل في مكانه: {target}")
    else:
        print(f"… نسخ {source.name} ({_human(source.stat().st_size)}) إلى فولدر الموديلات")
        shutil.copyfile(source, target)
        print(f"✔ تم: {target}")
    ok, name = store.set_active(target.name)
    if not ok:
        print(f"⚠ تعذّر التفعيل: {name}")
    probe = _probe()
    print(f"الحالة الآن: {probe['state']} — {probe['hint']}")
    if not probe["engine"]:
        print("ملاحظة: ثبّت المحرّك مرة واحدة — .venv\\Scripts\\pip install -r requirements-ai.txt")
    return 0


def cmd_ask(args):
    from services.assistant import model as brain_model
    from services import assistant as brain
    year = args.year
    month = args.month
    if year is None or month is None:
        from data_access import storage
        year, month = storage.active_month(1) if hasattr(storage, "active_month") else (None, None)
    reply = brain_model.try_answer(args.ask, year, month)
    if reply:
        print("=== رد النموذج المحلي ===")
        print(reply)
        return 0
    print("النموذج غير جاهز — ده رد المحرك المحلي (بلا نموذج):")
    payload = brain.answer(args.ask, year, month)
    print(payload.get("title", ""))
    for block in payload.get("blocks", []):
        if block.get("type") in ("p", "note"):
            print(" -", block.get("text"))
    return 1


def main():
    parser = argparse.ArgumentParser(description="مساعد الموديل المحلي (أوفلاين) — نفس قائمة «تبديل الموديل» في الشات")
    parser.add_argument("--check", action="store_true", help="فحص الحالة الحقيقية")
    parser.add_argument("--use", metavar="PATH", help="نسخ ملف GGUF إلى فولدر الموديلات")
    parser.add_argument("--ask", metavar="QUESTION", help="تجربة سؤال عبر نفس مسار المساعد")
    parser.add_argument("--year", type=int)
    parser.add_argument("--month", type=int)
    args = parser.parse_args()
    if args.check:
        return cmd_check(args)
    if args.use:
        return cmd_use(args)
    if args.ask:
        return cmd_ask(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
