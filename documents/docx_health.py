# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""ملفات الوورد الرسمية لقسم «الصحة» — محلية لحظية في 13-الصحة/ بأربعة تقارير:

- محضر رش وتقفيم                       (تاب الرش والتعقيم)
- كشف الدوري — يوم <ن>.docx ×٣         (تاب الكشف الدوري على المجندين)
- محضر تطهير خزانات                    (تاب تطهير الخزانات)
- تقرير فحص عينة مياة الشرب            (تاب فحص مياة الشرب)

كل النصوص افتراضيات من نماذج الورق الرسمية، وكل حقل قابل للتعديل من الصفحة —
المخزَّن في health_fields يعلو الافتراضي، والحقول الفارغة ترجع للافتراضي.
"""
from datetime import date as _date

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from core import arabic_numbers as arnum
from core import egtime
from core.config import MONTH_NAMES, month_folder
from data_access import db_health
from data_access import db_recruits
from services import health_fs

NAVY = RGBColor(0x0A, 0x12, 0x30)
GOLD = RGBColor(0xB8, 0x86, 0x0B)

# ==================== الترويسة الرسمية (قابلة للتعديل) ====================
HEADER_FIELDS = [("h1", "السطر الأول", "محافظة شمال سيناء"),
                 ("h2", "السطر الثاني", "مديرية الصحة والإسكان"),
                 ("h3", "السطر الثالث", "إدارة نخل الصحة"),
                 ("def_right_rank", "الرتبة الافتراضية يمين (التوقيع)", "المراقب الصحي"),
                 ("def_right_name", "الاسم الافتراضي يمين", ""),
                 ("def_left_rank", "الرتبة الافتراضية شمال (الاعتماد)", ""),
                 ("def_left_name", "الاسم الافتراضي شمال", "")]

# نصوص النماذج الورقية الحرفية (كل حقل قابل للتعديل من الصفحة)
BODY_SPRAY = ("تم رش وتقفيم قسم التعيينات بالكامل التابع للإدارة العامة للأمن المركزى "
              "– قطاع وسط سيناء بالمنطقة «ج» الحدودية، وذلك لجميع المبانى والغرف المخصصة "
              "للضباط والأفراد والمجندين وجميع المخازن التابعة للقسم وأماكن التوزيع وخلافه، "
              "وذلك بالمواد الكيميائية اللازمة للرش والتقفيم بالنسب المقررة والمسموح بها، "
              "وذلك ضد الحشرات الزاحفة والطائرة والقوارض والجرذان، وتمت عمل التهوية اللازمة "
              "عقب انتهاء العملية السابقة، وذلك تحت إشراف وبمعرفة المراقب الصحي بالوحدة "
              "الصحة بالكونتلا.")
BODY_WATER = ("تم فحص عينة مياة الشرب الخاصة بقسم التعيينات بالكامل التابع للإدارة العامة "
              "للأمن المركزى – قطاع وسط سيناء بالمنطقة «ج» الحدودية، وتبين أنها مطابقة "
              "للمعايير المقررة، وذلك تحت إشراف وبمعرفة المراقب الصحي بالوحدة الصحة "
              "بالكونتلا.")
BODY_CHECKUP = ("تم الكشف الطبى على مجندى قسم التعيينات التابع للإدارة العامة للأمن "
                "المركزى – قطاع وسط سيناء بالمنطقة «ج» الحدودية، وذلك من قبل طبيب الوحدة "
                "الصحة بالكونتلا، وتبين بأنهم خاليين من الأمراض الجلدية المعدية والزهرية "
                "والاتى اسمانهم.")
BODY_TANKS = ("قام المراقب الصحي بالاشراف على عملية تطهير خزانات مياه مخزن التموين "
              "(المجندين) بعدد ٤ خزانات على النحو التالي:")

TANK_COLS = [("place", "مكان الخزان"), ("cap", "سعة الخزان"),
             ("mat", "نوع مادة الصنع"), ("cover", "مزود بغطاء محكم الإغلاق"),
             ("man", "بفتحة للتريبخ"), ("wash", "بفتحة لصرف مياة الغسيل"),
             ("vent", "بفتحة التهوية"), ("cl", "نسبة الكلور الحر المتبقى")]
TANK_DEFAULT = {"place": "بجوار مطبخ", "cap": "3×3 م³", "mat": "فايبر جلاكس",
                "cover": "نعم", "man": "نعم", "wash": "نعم", "vent": "نعم", "cl": "—"}
TANK_COUNT_DEFAULT = 4
TANK_MAX = 12


def tank_count(year, month):
    """عدد الخزانات المعروض (افتراضي ٤ — يُخزَّن في health_fields)."""
    stored = db_health.get_fields(year, month, "tanks")
    try:
        n = int((stored.get("tank_count") or "").strip() or TANK_COUNT_DEFAULT)
    except ValueError:
        n = TANK_COUNT_DEFAULT
    return max(1, min(TANK_MAX, n))


def set_tank_count(year, month, n):
    n = max(1, min(TANK_MAX, int(n)))
    db_health.set_fields(year, month, "tanks", {"tank_count": str(n)})
    return n

# مواصفات حقول كل تقرير: (fkey, label, kind, default) — kind: line/area/date
FIELDS = {
    "spray": [
        ("date_text", "التاريخ (فارغ = تاريخ اليوم تلقائيًا)", "date", ""),
        ("title", "عنوان المحضر", "line", "محضر رش وتقفيم"),
        ("body", "نص المحضر", "area", BODY_SPRAY),
        ("sig_right_rank", "الرتبة يمين", "line", "المراقب الصحي"),
        ("sig_right_name", "الاسم يمين", "line", ""),
        ("sig_left_rank", "رتبة الاعتماد شمال", "line", "قائد مخزن التموين"),
        ("sig_left_name", "الاسم شمال", "line", ""),
    ],
    "water": [
        ("date_text", "التاريخ (فارغ = تاريخ اليوم تلقائيًا)", "date", ""),
        ("title", "عنوان التقرير", "line", "تقرير نتيجة فحص عينة مياة الشرب"),
        ("body", "نص التقرير", "area", BODY_WATER),
        ("sig_right_rank", "الرتبة يمين", "line", "المراقب الصحي"),
        ("sig_right_name", "الاسم يمين", "line", ""),
        ("sig_left_rank", "رتبة الاعتماد شمال", "line", ""),
        ("sig_left_name", "الاسم شمال", "line", ""),
    ],
    "tanks": [
        ("date_text", "التاريخ (فارغ = تاريخ اليوم تلقائيًا)", "date", ""),
        ("time_text", "الساعة", "line", "الساعة ١٢ ظهرًا"),
        ("title", "عنوان المحضر", "line", "محضر تطهير خزانات المياه"),
        ("body", "نص المقدمة", "area", BODY_TANKS),
        ("sig_right_rank", "الرتبة يمين", "line", "المراقب الصحي"),
        ("sig_right_name", "الاسم يمين", "line", ""),
        ("sig_left_rank", "الجهة شمال", "line", "الجهة التالي لها الخزان"),
        ("sig_left_name", "الاسم شمال", "line", ""),
        ("approve_rank", "سطر الاعتماد", "line", "قائد مخزن التموين"),
    ],
    "checkup": [
        ("title", "عنوان التقرير", "line", "تقرير بالكشف الطبى الدورى على المجندين"),
        ("day_label", "بادئة سطر اليوم", "line", "إنه فى يوم"),
        ("day_text", "بقية سطر اليوم (فارغ = تاريخ يوم الكشف تلقائيًا)", "date", ""),
        ("body", "نص التقرير", "area", BODY_CHECKUP),
        ("tail", "الخاتمة", "line", "وذلك للعلم والإحاطة واتخاذ اللازم."),
        ("sig_right_rank", "الرتبة يمين", "line", "المراقب الصحي"),
        ("sig_right_name", "الاسم يمين", "line", ""),
        ("sig_left_rank", "رتبة الاعتماد شمال", "line", ""),
        ("sig_left_name", "الاسم شمال", "line", ""),
    ],
}


# ==================== مساعدات القيم والتواريخ ====================
def _long_date(d):
    """الأربعاء ١٥ أبريل ٢٠٢٦ م."""
    return "{} {} {} {}م".format(egtime.weekday_ar(d), arnum.to_arabic_indic(d.day),
                                 MONTH_NAMES[d.month - 1], arnum.to_arabic_indic(d.year))


def field_values(year, month, report, day=None):
    """{fkey: قيمة فعلية} — المخزَّن يعلو الافتراضي، وdate_text الفارغ يتولد تلقائيًا،
    والتوقيعات الفارغة ترجع للقيم الافتراضية للدباجة."""
    stored = db_health.get_fields(year, month, report)
    hdr = header_values(year, month)
    vals = {}
    for key, _label, _kind, default in FIELDS[report]:
        raw = (stored.get(key) or "").strip()
        if not raw and key.startswith("sig_"):
            raw = (hdr.get("def_" + key[4:]) or "").strip()
        vals[key] = raw if raw else default
        if key in ("date_text", "day_text") and not raw:
            if report == "checkup" and day:
                d = _date(year, month, min(day, egtime.days_in_month(year, month)))
            else:
                d = egtime.today()
            vals[key] = _long_date(d)
    return vals


def header_values(year, month):
    stored = db_health.get_fields(year, month, "header")
    return {k: (stored.get(k) or "").strip() or default
            for k, _l, default in HEADER_FIELDS}


# ==================== بناء المستند المشترك ====================
def _bidi(p):
    """اتجاه الفقرة من اليمين لليسار في الوورد (مطابقة الكتابة العربية)."""
    pPr = p._p.get_or_add_pPr()
    pPr.insert(0, OxmlElement("w:bidi"))
    return p


def _rule(p, color="B8860B", sz="8"):
    """خط سفلي ذهبي تحت فقرة (فاصل الترويسة)."""
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), sz)
    bottom.set(qn("w:space"), "6")
    bottom.set(qn("w:color"), color)
    pbdr.append(bottom)
    pPr.append(pbdr)
    return p


def _page_frame(doc):
    """فريم مزدوج كحلي حول صفحة الوورد كلها (زي الأوراق الرسمية)."""
    sect = doc.sections[0]._sectPr
    pg = OxmlElement("w:pgBorders")
    pg.set(qn("w:offsetFrom"), "page")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement("w:" + side)
        el.set(qn("w:val"), "double")
        el.set(qn("w:sz"), "18")
        el.set(qn("w:space"), "24")
        el.set(qn("w:color"), "0A1230")
        pg.append(el)
    sect.append(pg)


def _run(p, text, size=12, bold=True, color=NAVY):
    r = p.add_run(text)
    r.font.name = "Cairo"
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    return r


def _para(doc, text, size=12, bold=True, color=NAVY,
          align=WD_ALIGN_PARAGRAPH.RIGHT):
    p = doc.add_paragraph()
    p.alignment = align
    _bidi(p)
    if text:
        _run(p, text, size, bold, color)
    return p


def _cell(cell, text, size=9, color=NAVY):
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _bidi(p)
    _run(p, text, size, True, color)


def _health_header(doc, year, month):
    """ترويسة الورق: اللوجو شمالًا + أسطر الدباجة يمينًا + خط ذهبي فاصل."""
    from data_access import db_letterhead as lhdb
    logo = lhdb.logo_path(year, month)
    if logo and logo.exists():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.add_run().add_picture(str(logo), width=Cm(2.6))
    hdr = header_values(year, month)
    last = None
    for i, key in enumerate(("h1", "h2", "h3")):
        last = _para(doc, hdr[key], 14 if i == 0 else 12, True, NAVY)
    _rule(last)


def _approve(doc, right_rank, right_name, left_rank, left_name):
    """سطر «يعتمد،،» + جدول التوقيعين يمين وشمال."""
    _para(doc, "يعتمد،،", 12, True, NAVY)
    doc.add_paragraph("\n")
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for idx, (rank, name) in enumerate(((left_rank, left_name),
                                        (right_rank, right_name))):
        cell = table.cell(0, idx)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        for text in (rank, name or "........................"):
            p = cell.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _run(p, text, 12)


# ==================== التقارير الأربعة ====================
def build_spray(year, month):
    v = field_values(year, month, "spray")
    doc = Document()
    _page_frame(doc)
    _health_header(doc, year, month)
    _para(doc, v["title"], 15, True, GOLD, WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph("")
    _para(doc, v["date_text"], 12)
    _para(doc, "")
    for line in v["body"].splitlines():
        _para(doc, line, 12)
    _approve(doc, v["sig_right_rank"], v["sig_right_name"],
             v["sig_left_rank"], v["sig_left_name"])
    return health_fs.report_file(year, month, "spray"), doc


def build_water(year, month):
    v = field_values(year, month, "water")
    doc = Document()
    _page_frame(doc)
    _health_header(doc, year, month)
    _para(doc, v["title"], 15, True, GOLD, WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph("")
    _para(doc, v["date_text"], 12)
    _para(doc, "")
    for line in v["body"].splitlines():
        _para(doc, line, 12)
    _approve(doc, v["sig_right_rank"], v["sig_right_name"],
             v["sig_left_rank"], v["sig_left_name"])
    return health_fs.report_file(year, month, "water"), doc


def build_tanks(year, month):
    v = field_values(year, month, "tanks")
    stored = db_health.get_fields(year, month, "tanks")
    count = tank_count(year, month)
    doc = Document()
    _page_frame(doc)
    _health_header(doc, year, month)
    _para(doc, v["title"], 15, True, GOLD, WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph("")
    _para(doc, v["date_text"], 12)
    _para(doc, v["time_text"], 12)
    _para(doc, "")
    for line in v["body"].splitlines():
        _para(doc, line, 12)
    table = doc.add_table(rows=1, cols=len(TANK_COLS))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (_key, label) in enumerate(TANK_COLS):
        _cell(table.rows[0].cells[i], label, 9)
    for t in range(1, count + 1):
        cells = table.add_row().cells
        for i, (key, _label) in enumerate(TANK_COLS):
            raw = (stored.get(f"t{t}_{key}") or "").strip()
            _cell(cells[i], raw or TANK_DEFAULT[key], 9)
    _approve(doc, v["sig_right_rank"], v["sig_right_name"],
             v["sig_left_rank"], v["sig_left_name"])
    if v["approve_rank"]:
        _para(doc, v["approve_rank"], 12, True, NAVY, WD_ALIGN_PARAGRAPH.CENTER)
    return health_fs.report_file(year, month, "tanks"), doc


def build_checkup(year, month, day):
    v = field_values(year, month, "checkup", day)
    entries = db_health.get_day_entries(year, month, day)
    recruits = {r["id"]: r["name"] for r in db_recruits.list_recruits(year, month)}
    ids = [(e["name"] or recruits.get(e["recruit_id"], "—")) for e in entries]
    doc = Document()
    _page_frame(doc)
    _health_header(doc, year, month)
    _para(doc, v["title"], 15, True, GOLD, WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph("")
    _para(doc, "{} {}،".format(v["day_label"], v["day_text"]), 12)
    _para(doc, "")
    for line in v["body"].splitlines():
        _para(doc, line, 12)
    doc.add_paragraph("")
    for i, name in enumerate(ids, 1):
        _para(doc, "{}- {}".format(arnum.to_arabic_indic(i), name), 12)
    if not ids:
        _para(doc, "(لم يُحدَّد مكتوشون لهذا اليوم بعد)", 11, False, GOLD)
    doc.add_paragraph("")
    _para(doc, v["tail"], 12)
    _approve(doc, v["sig_right_rank"], v["sig_right_name"],
             v["sig_left_rank"], v["sig_left_name"])
    return health_fs.day_file(year, month, day), doc


# ==================== الحفظ الذرّي + إعادة البناء ====================
def _save(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    doc.save(str(tmp))
    tmp.replace(path)
    return path


def rebuild(year, month, report, day=None):
    """توليد/تحديث ملف وورد لتقرير — يُستدعى عند فتح الصفحة وعند كل حفظ."""
    builder = {"spray": build_spray, "water": build_water, "tanks": build_tanks,
               "checkup": build_checkup}[report]
    path, doc = builder(year, month, day) if report == "checkup" else builder(year, month)
    return _save(path, doc)


def rebuild_all(year, month):
    """الفولدرات والملفات الأربعة الثابتة + كشوف الأيام الثلاثة."""
    health_fs.ensure_month(year, month)
    built = []
    for rep in ("spray", "tanks", "water"):
        built.append(rebuild(year, month, rep))
    from data_access import db_health as db
    for d in db.get_days(year, month):
        built.append(rebuild(year, month, "checkup", d))
    return built


def folder_hint(year, month):
    return "database/{}/{}/13-الصحة/".format(year, month_folder(month))
