# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""المساعد المحلي للمنظومة — فهم عربي حقيقي وإجابات من بيانات الشهر النشط.

محلي ١٠٠٪: لا إنترنت، لا CDN، ولا أي خدمة خارجية في أي خطوة (قاعدة ٢٠).
بلا اعتماديات إضافية: كل شيء من مكتبة Python القياسية + طبقات المنظومة نفسها،
ووزنه صفر على المثبّت. ويدعم — اختياريًا — نموذجًا محليًا صغيرًا (GGUF) يضعه
المستخدم في بياناته، فيُستخدم للأسئلة المفتوحة فقط (services/assistant/model.py).

الواجهة العامة:
    answer(text, year, month) → {reply, blocks, links, followups, kind[, navigate]}
    quick_prompts()           → الاقتراحات السريعة للواجهة
    capabilities(y, m)        → كتالوج القدرات + حالة النموذج المحلي
    DESTINATIONS              → وجهات التنقل (نفس شكل routes/tameedat المشترك)

البنية (كل ملف مسؤولية واحدة):
    text.py          تطبيع النص العربي والأرقام والتشابه الضبابي
    destinations.py  وجهات التنقل بكلماتها الدارجة
    knowledge.py     المعجم + الأدلة + القدرات
    data_answers.py  إجابات بيانات الشهر من الطبقات الرسمية
    data_files.py    ملفات الجهاز: ملف يوم محدد + حصر الملفات من القرص
    data_rank.py     المقارنة والترتيب: أكبر/أقل الجهات + الأيام الناقصة في التسجيل
    model.py         جسر النموذج المحلي الاختياري (GGUF، بلا إنترنت)
    engine.py        تصنيف النية والترتيب النهائي للرد
"""
from .destinations import DESTINATIONS, OPEN_VERBS          # noqa: F401
from .engine import answer, capabilities, quick_prompts      # noqa: F401

__all__ = ["answer", "capabilities", "quick_prompts", "DESTINATIONS", "OPEN_VERBS"]
