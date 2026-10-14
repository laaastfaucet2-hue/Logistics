# -*- coding: utf-8 -*-
"""تحقق حي Task 106 على داتا مؤقتة (الداتا الحقيقية لا تُلمس)."""
import json
import os
import pathlib
import sys
import tempfile

REPO = "/home/user/Logistics"
sys.path.insert(0, REPO)
os.chdir(REPO)

base = pathlib.Path(tempfile.mkdtemp(prefix="v106_"))
data = base / "database"
os.environ["LOGISTICS_DATA_DIR"] = str(data)
os.environ.pop("LOGISTICS_PREVIEW", None)
os.environ.pop("LOGISTICS_DESKTOP", None)

from core import paths                      # noqa: E402
from data_access import storage, database, dataguard   # noqa: E402

paths.DATA_DIR = data
storage.DATA_DIR = data
database.DATA_DIR = data
dataguard.DATA_DIR = data
database.DB_PATH = data / "system.db"
dataguard.BACKUP_DIR = data / "backups"

from app import create_app                   # noqa: E402
from services.bootstrap import bootstrap_year_files   # noqa: E402

app = create_app()
app.config["TESTING"] = True
if storage.create_year(2031):
    bootstrap_year_files(2031)
database.set_user_context(1, 2031, 9)

from data_access import db_tameedat as dt, db_raghibin as drg   # noqa: E402
from data_access import database as _db      # noqa: E402

Y, M = 2031, 9
ok = []
bad = []


def chk(label, cond, extra=""):
    (ok if cond else bad).append(label)
    print(("  ✓ " if cond else "  ✗ ") + label + ((" — " + str(extra)) if extra and not cond else ""))


c = app.test_client()
r = c.post("/login", data={"username": "mostafa", "password": "779"})
chk("تسجيل الدخول", r.status_code == 302, r.status_code)
token = _db.create_session(1)
ENT = "قطاع الشهادة التجريبي"
eid = dt.add_entity(Y, M, ENT, "شرطية")

print("\n=== ② الرتبة جزء من الهوية (مستوى الداتا) ===")
pid_3id, created = drg.add_person(Y, M, eid, "officers", "محمد احمد محمد", "عقيد")
chk("إضافة عقيد محمد احمد محمد", created)
chk("نفس الاسم برتبة عقيد = نفسه (لا تكرار)",
    drg.find_person(Y, M, eid, "officers", "محمد احمد محمد", rank="عقيد")["id"] == pid_3id)
chk("نفس الاسم برتبة مقدم = لا يطابق العقيد",
    drg.find_person(Y, M, eid, "officers", "محمد احمد محمد", rank="مقدم") is None)
chk("البحث بلا رتبة (سلوك قديم) يلقاه",
    drg.find_person(Y, M, eid, "officers", "محمد احمد محمد")["id"] == pid_3id)
pid_new, created_new = drg.add_person(Y, M, eid, "officers", "محمد احمد محمد", "مقدم")
chk("إضافة الرتبة التانية = شخص جديد", created_new and pid_new != pid_3id, (pid_new, created_new))
chk("بقى فيه شخصان بنفس الاسم",
    len([p for p in drg.list_persons(Y, M, entity_id=eid, category="officers")
         if p["full_name"] == "محمد احمد محمد"]) == 2)
# الرتبة الفاضية تتكمّل ما تتكررش
pid_blank, _ = drg.add_person(Y, M, eid, "individuals", "سيد بلا رتبة", "")
pid_again, created_again = drg.add_person(Y, M, eid, "individuals", "سيد بلا رتبة", "أمين شرطة")
chk("الرتبة الفاضية تتكمّل بدل التكرار",
    (not created_again) and pid_again == pid_blank
    and (drg.get_person(Y, M, pid_blank)["rank"] or "") == "أمين شرطة",
    drg.get_person(Y, M, pid_blank))

print("\n=== ① الحفظ عبر HTTP (رد السيرفر الحقيقي) ===")
other, _ = drg.add_person(Y, M, eid, "officers", "ابراهيم ناجى عطا الله", "رائد")
dt.add_record(Y, M, 22, {"id": eid, "name": ENT, "entity_type": "شرطية"}, 3, 2, 5,
              notes="تأميدة تجريبية")
form = {
    "e": str(eid), "d": "22", "cat": "officers", "source": "tamida",
    "back": "tameedat", "sid": token,
    "names": ["محمد احمد محمد", "محمد احمد محمد", "ابراهيم ناجى عطا الله", "حسن الجديد"],
    "ranks": ["مقدم", "عقيد", "رائد", "ملازم أول"],
    "new_names": json.dumps(["حسن الجديد"], ensure_ascii=False),
}
r = c.post("/raghibin/daily/save", data=form, follow_redirects=True)
chk("الحفظ رجع 200 بعد التحويل", r.status_code == 200, r.status_code)
print("     الرابط النهائي:", r.request.path + "?" + r.request.query_string.decode()[:180])
body = r.get_data(as_text=True)
chk("الرد النهائي صفحة كاملة (تاميدات)", r.request.path.startswith("/tameedat"), r.request.path)
qs = r.request.query_string.decode()
chk("رسالة النجاح موجودة في التحويل", "ok=" in qs)
chk("التحذيرات موجودة في التحويل", "warn=" in qs)
chk("«حسن الجديد» أُضيف للقوة الدائمة", "أُضيفوا للقوة الدائمة" in body or "حسن الجديد" in body)
hass = drg.find_person(Y, M, eid, "officers", "حسن الجديد", rank="ملازم أول")
chk("الشخص الجديد مسجّل برتبته", hass is not None)
per = [p for p in drg.list_persons(Y, M, entity_id=eid, category="officers")
       if p["full_name"] == "محمد احمد محمد"]
chk("نفس الاسم برتبتين = شخصان في القوة",
    set((p["rank"] or "") for p in per) == {"مقدم", "عقيد"},
    [p["rank"] for p in per])

print("\n=== ① الجزء يعرض الرسائل (اللي الجافاسكريبت بيحمّله) ===")
frag_url = ("/raghibin/panel?en=" + ENT + "&d=22&c=officers&e=" + str(eid)
            + "&ok=" + "تم الحفظ" + "&warn=" + "تنبيه تجريبي" + "&sid=" + token)
r2 = c.get(frag_url)
fb = r2.get_data(as_text=True)
chk("جزء المودال رجع 200", r2.status_code == 200, r2.status_code)
chk("الجزء فيه .rg-modal-form", 'class="rg-modal-form"' in fb)
chk("الجزء بيعرض رسالة النجاح", "تم الحفظ" in fb)
chk("الجزء بيعرض التحذير", "تنبيه تجريبي" in fb and "rg-note warn" in fb)
chk("مربعات الرتب بالرتب الجديدة موجودة", "مقدم" in fb and "عقيد" in fb)

print("\n=== ② رسالة «رتبة مختلفة» + الرتبة في رسائل النقص ===")
form2 = dict(form)
form2["names"] = ["محمد احمد محمد"]
form2["ranks"] = ["عقيد"]
form2["new_names"] = "[]"
r3 = c.post("/raghibin/daily/save", data=form2, follow_redirects=True)
q3 = r3.request.query_string.decode()
chk("نفس الاسم برتبته الموجودة = قبول بلا تحذير تكرار", "غير موجود في القوة" not in q3, q3[:120])
form3 = dict(form)
form3["names"] = ["محمود الغائب"]
form3["ranks"] = ["مقدم"]
form3["new_names"] = "[]"
r4 = c.post("/raghibin/daily/save", data=form3, follow_redirects=True)
q4 = r4.request.query_string.decode()
from urllib.parse import unquote_plus, quote   # noqa: E402
chk("رسالة «غير مسجّل» فيها الرتبة", "برتبة مقدم" in unquote_plus(q4)
    and "غير مسجّل" in unquote_plus(q4), unquote_plus(q4)[:200])

print("\n=== ③ نوع الجهة بالعربي من نوع التأميدة (١٤/١٠) ===")
r_t = c.get("/raghibin/panel?en=" + ENT + "&d=22&c=officers&et=" + quote("شرطية") + "&sid=" + token)
tb = r_t.get_data(as_text=True)
chk("نوع التأميدة الممرر يظهر زي ما هو", "نوع الجهة: شرطية معتمدة" in tb)
chk("مفيش «جهة» مكررة في الشريط", "نوع الجهة: جهة " not in tb)
chk("مفيش نوع إنجليزي في الشريط", "workshop" not in tb and "salon" not in tb)
chk("النوع الحقل الخفي يكمل مع تغيير الجهة", 'name="et" value="شرطية"' in tb)
eid_w = dt.add_entity(Y, M, "الورشة التجريبية", "workshop")
r_w = c.get("/raghibin/panel?en=" + quote("الورشة التجريبية") + "&d=22&c=officers&sid=" + token)
wb = r_w.get_data(as_text=True)
chk("بدون نوع تأميدة → نوع القاموس بالعربي", "نوع الجهة: ورشة معتمدة" in wb,
    [ln for ln in wb.splitlines() if "نوع الجهة" in ln][:1])

print("\n=== ④ قائمة الجهة من التأميدات = جهات اليوم فقط ===")
eid_day = dt.add_entity(Y, M, "بوابة تأميدة اليوم", "حربية")
eid_att = dt.add_entity(Y, M, "ملحقة لها راغبين", "شرطية")
eid_rec_only = dt.add_entity(Y, M, "ملحقة مجندين فقط", "شرطية")
dt.add_record(Y, M, 22, dt.get_entity(Y, M, eid_day), 1, 1, 0,
              attachments=[
                  {"name": "ملحقة لها راغبين", "entity_type": "شرطية",
                   "officers": 2, "individuals": 3, "recruits": 0},
                  {"name": "ملحقة مجندين فقط", "entity_type": "شرطية",
                   "officers": 0, "individuals": 0, "recruits": 5},
              ])
eid_other = dt.add_entity(Y, M, "مخزن يوم آخر", "شرطية")
dt.add_record(Y, M, 23, dt.get_entity(Y, M, eid_other), 1, 0, 0)
eid_dict = dt.add_entity(Y, M, "جهة في القاموس فقط", "شرطية")
scoped_url = ("/raghibin/panel?en=" + quote(ENT) + "&d=22&c=officers"
              + "&origin=tameedat&draft_en=" + quote(ENT) + "&et=" + quote("شرطية")
              + "&o=3&i=2&sid=" + token)
scoped = c.get(scoped_url).get_data(as_text=True)
chk("جهة مسودة الفورم موجودة في القائمة", f'value="{ENT}"' in scoped)
chk("جهة لها تأميدة في نفس اليوم موجودة", 'value="بوابة تأميدة اليوم"' in scoped)
chk("جهة ملحقة لها ضباط/أفراد موجودة", 'value="ملحقة لها راغبين"' in scoped)
chk("جهة ملحقة مجندين فقط غير موجودة", 'value="ملحقة مجندين فقط"' not in scoped)
chk("جهة يوم آخر غير موجودة", 'value="مخزن يوم آخر"' not in scoped)
chk("جهة القاموس بلا تأميدة غير موجودة", 'value="جهة في القاموس فقط"' not in scoped)
chk("سياق التأميدات محفوظ عند تغيير الجهة",
    'name="origin" value="tameedat"' in scoped and "origin=tameedat" in scoped)
chk("اسم اليوم والتاريخ الكامل ظاهر بدل «ضبط اليوم»",
    "يوم <b>الاثنين</b>" in scoped and "٢٢/٠٩/٢٠٣١" in scoped
    and "ضبط اليوم" not in scoped)
saved_att = c.get("/raghibin/panel?en=" + quote("ملحقة لها راغبين")
                  + "&d=22&c=officers&origin=tameedat&draft_en=" + quote(ENT)
                  + "&sid=" + token).get_data(as_text=True)
chk("الملحقة المحفوظة تأخذ مربعات ضباطها هي",
    saved_att.count('name="ranks"') == 2, saved_att.count('name="ranks"'))
draft_payload = json.dumps([{"n": "الورشة التجريبية", "t": "شرطية", "o": 4, "i": 3}],
                           ensure_ascii=False)
draft_att_url = ("/raghibin/panel?en=" + quote(ENT)
                 + "&d=22&c=officers&origin=tameedat&draft_en=" + quote(ENT)
                 + "&o=3&i=2&draft_atts=" + quote(draft_payload) + "&sid=" + token)
draft_att_list = c.get(draft_att_url).get_data(as_text=True)
chk("ملحقة الفورم غير المحفوظة تظهر فورًا", 'value="الورشة التجريبية"' in draft_att_list)
draft_att_selected = c.get(draft_att_url.replace("en=" + quote(ENT),
                                                  "en=" + quote("الورشة التجريبية"), 1)).get_data(as_text=True)
chk("ملحقة الفورم تأخذ عدّاداتها ونوعها هي",
    draft_att_selected.count('name="ranks"') == 4
    and "نوع الجهة: شرطية معتمدة" in draft_att_selected,
    draft_att_selected.count('name="ranks"'))
draft_only = c.get("/raghibin/panel?en=" + quote("الورشة التجريبية")
                   + "&d=22&c=officers&origin=tameedat&draft_en="
                   + quote("الورشة التجريبية") + "&sid=" + token).get_data(as_text=True)
chk("جهة الفورم غير المحفوظة كتأميدة تظهر مؤقتًا", 'value="الورشة التجريبية"' in draft_only)
normal = c.get("/raghibin/panel?en=" + quote(ENT)
               + "&d=22&c=officers&sid=" + token).get_data(as_text=True)
chk("الفتح العادي من الراغبين يظل يعرض كل القاموس", 'value="جهة في القاموس فقط"' in normal)
selected_other = c.get("/raghibin/panel?en=" + quote("بوابة تأميدة اليوم")
                       + "&d=22&c=officers&origin=tameedat&draft_en=" + quote(ENT)
                       + "&et=" + quote("شرطية") + "&sid=" + token).get_data(as_text=True)
chk("نوع مسودة الفورم لا ينتقل لجهة أخرى من القائمة",
    "نوع الجهة: حربية معتمدة" in selected_other)
css = pathlib.Path("static/css/raghibin.css").read_text(encoding="utf-8")
chk("قائمة الجهة المفتوحة عالية التباين في فايرفوكس/ويندوز",
    ".rg-entity-select { color-scheme: light; }" in css
    and ".rg-entity-select option" in css and "background: #fff" in css)

print("\n=== ③ تحميل ستايل الراغبين في صفحات التأميدات ===")
pg = c.get("/tameedat?tab=day").get_data(as_text=True)
chk("raghibin.css محمّل في اليومية", "css/raghibin.css" in pg)
chk("STATIC_VER = 230", "?v=230" in pg)
chk("الديالوج فيه شرح فرعي", "tm-rgdialog-sub" in pg)
chk("حقل نوع التأميدة ممرر من الزر", "type_choice" in pg)
chk("زر فتح الراغبين موجود", 'id="tmRagNamesBtn"' in pg)


print("\n=== ① محاكاة ما بيعمله الجافاسكريبت بعد الحفظ ===")
chk("الرد النهائي مش صفحة مودال (فالفرع = إعادة تحميل الجزء)",
    'class="rg-modal-form"' not in body)
from urllib.parse import urlparse, parse_qs, urlencode
last_panel = ("/raghibin/panel?en=" + ENT + "&d=22&c=officers&year=2031&month=9&sid=" + token)
p = urlparse(last_panel)
q = parse_qs(p.query)
for k in ("ok", "warn", "err"):
    q.pop(k, None)
final = urlparse(r.request.url)
for k in ("ok", "warn", "err", "sid"):
    v = parse_qs(final.query).get(k)
    if v:
        q[k] = v
sim_url = p.path + "?" + urlencode({k: v[0] for k, v in q.items()})
sim = c.get(sim_url)
sb = sim.get_data(as_text=True)
chk("الجزء المعاد تحميله رجع 200", sim.status_code == 200, sim.status_code)
chk("فيه الجزء", 'class="rg-modal-form"' in sb)
chk("فيه رسالة الحفظ الحقيقية", "تم تسجيل" in sb)
print("     رابط المحاكاة:", sim_url[:150])

print("\n" + "=" * 60)
print(f"نجح {len(ok)} · فشل {len(bad)}")
if bad:
    print("فاشل:", " | ".join(bad))
sys.exit(1 if bad else 0)
