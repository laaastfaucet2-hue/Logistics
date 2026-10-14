# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""أدوات النص العربي المساعدة للمساعد المحلي: تطبيع، أرقام، تشابه، واستخراج أيام.

محلي ١٠٠٪ بلا أي اعتماديات خارجية — كل شيء من مكتبة Python القياسية.
"""
import re
from difflib import SequenceMatcher

from core import arabic_numbers as arnum

# ══════════════════════════════════════════════════════════════════════
# التطبيع — يوحّد الهمزات والياء والتاء المربوطة ويشيل التشكيل والعلامات
# ══════════════════════════════════════════════════════════════════════
_DIACRITICS = re.compile(r"[\u0617-\u061a\u064b-\u0652\u0670\u0640]")
_PUNCT = re.compile(r"[^\w\s\u0600-\u06ff]")
_TATWEEL = re.compile(r"\s+")
_EQUIVALENT = (("أإآٱ", "ا"), ("ىئ", "ي"), ("ة", "ه"), ("ؤ", "و"),
               ("گ", "ك"), ("ی", "ي"), ("ک", "ك"), ("ۀ", "ه"))


def normalize(text):
    """نص موحّد للمقارنة: بلا تشكيل ولا علامات، بألف وياء وهاء موحّدة، بأرقام غربية."""
    value = arnum.to_western(text or "")
    value = _DIACRITICS.sub("", value)
    value = _PUNCT.sub(" ", value)
    for source, target in _EQUIVALENT:
        for char in source:
            value = value.replace(char, target)
    value = _TATWEEL.sub(" ", value)
    return value.strip().lower()


def tokens(text):
    """كلمات السؤال مطبّعة — للمطابقة الضبابية والتحمل الأخطاء المطبعية."""
    return [token for token in normalize(text).split() if token]


def _strip_article(word):
    """يشيل «ال» التعريف للسماح بمقارنة الجذر: «التامدات» ≈ «تاميدات»."""
    if word.startswith("ال") and len(word) > 4:
        return word[2:]
    return word


def similarity(left, right):
    """نسبة تشابه ٠–١ بين كلمتين (تحمّل الأخطاء المطبعية وأدوات التعريف).

    «التامدات» ≈ «تاميدات» (٠٫٩٢) · «الرغبين» ≈ «راغبين» (٠٫٩١) · «المومده» = «مومده».
    ولا تُقارَن الجذور إلا إذا كان الطرفان ≥ ٤ أحرف بعد التجريد، حتى لا تُطابق
    «الجهات» فعلَ الأمر القصير «هات» بغير حق.
    """
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    # مكافأة الاحتواء للألفاظ الطويلة فقط: «راغبين» داخل «الراغبين» ✓ —
    # أما «هات» داخل «الجهات» فلا (فعل أمر قصير لا يُطابق بغير حقه).
    if min(len(left), len(right)) >= 5 and (left in right or right in left):
        return 0.92
    direct = SequenceMatcher(None, left, right).ratio()
    left_root, right_root = _strip_article(left), _strip_article(right)
    if len(left_root) >= 4 and len(right_root) >= 4:
        rooted = SequenceMatcher(None, left_root, right_root).ratio()
        return max(direct, rooted)
    return direct


def phrase_in(question, phrase, threshold=0.82):
    """هل العبارة موجودة في السؤال (حرفيًا أو بمطابقة ضبابية على مستوى الكلمات)؟

    «تاميدات» تُطابق «تاميدات» و«التاميدات»، و«تنبيه» تُطابق «تنبيهات».
    """
    phrase = normalize(phrase)
    if not phrase:
        return False
    # العبارات القصيرة (مثل أفعال الأمر «هات») لا تُطابق كجزء من كلمة أطول،
    # حتى لا تُطابق «الجهات» فعلَ الأمر «هات» بغير حق.
    if len(phrase) >= 5 and phrase in question:
        return True
    words = phrase.split()
    qwords = question.split()
    if len(words) == 1:
        return any(word == words[0] or similarity(word, words[0]) >= threshold
                   for word in qwords)
    # عبارة مركّبة: كل كلماتها تُطابق بالترتيب داخل نافذة من كلمات السؤال
    for index in range(len(qwords) - len(words) + 1):
        window = qwords[index:index + len(words)]
        if all(similarity(a, b) >= threshold for a, b in zip(window, words)):
            return True
    return False


def any_in(question, *phrases):
    """هل أي من العبارات موجود في السؤال."""
    return any(phrase_in(question, phrase) for phrase in phrases)


# ══════════════════════════════════════════════════════════════════════
# الأرقام وأسماء الأعداد العربية (ليفهم «يوم سبعة» و«كام ضابط»)
# ══════════════════════════════════════════════════════════════════════
UNITS = {"صفر": 0, "واحد": 1, "واحده": 1, "احد": 1, "اول": 1, "اثنين": 2, "اتنين": 2,
         "اثنان": 2, "ثاني": 2, "تاني": 2, "ثلاثه": 3, "ثلاث": 3, "تلاته": 3, "ثالث": 3,
         "تالت": 3, "اربعه": 4, "اربع": 4, "رابع": 4, "خمسه": 5, "خمس": 5, "خامس": 5,
         "سته": 6, "ست": 6, "سادس": 6, "سبعه": 7, "سبع": 7, "سابع": 7, "ثمانيه": 8,
         "ثمان": 8, "تمانيه": 8, "ثامن": 8, "تامن": 8, "تسعه": 9, "تسع": 9, "تاسع": 9,
         "عشره": 10, "عشر": 10, "عاشر": 10, "احدعشر": 11, "حدعشر": 11, "اثناعشر": 12,
         "اتناعشر": 12, "خمستاشر": 15, "خمسه عشر": 15, "عشرين": 20, "تلاتين": 30,
         "ثلاثين": 30}

_DAY_WORDS = ("يوم", "اليوم", "في يوم", "بتاريخ")


def day_number(question):
    """اليوم المقصود في السؤال: «يوم ٧» · «يوم سبعة» · «السابع» → 7، وإلا None."""
    for match in re.finditer(r"(?:^|\s)(\d{1,2})(?:\s|$|/)", question):
        value = int(match.group(1))
        if 1 <= value <= 31:
            return value
    result = None
    for word in question.split():
        if word in UNITS and 1 <= UNITS[word] <= 31:
            result = UNITS[word]
    if result is not None and any_in(question, *_DAY_WORDS):
        return result
    return None


def numbers_in(question):
    """كل الأرقام الصريحة في السؤال (غربية بعد التطبيع)."""
    return [int(value) for value in re.findall(r"\d+", question)]


def to_ar(value):
    """عرض أي رقم بالأرقام العربية المشرقية."""
    return arnum.to_arabic_indic(str(value))


def qty(value):
    """الكميات بثلاث خانات عشرية عربية (قاعدة المنظومة الموحّدة)."""
    return arnum.fmt_qty(value)
