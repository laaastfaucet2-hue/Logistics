# حصر جداول الواجهة ومراجعة لغة العرض

آخر مراجعة: 14 أكتوبر 2026.

## النتيجة التنفيذية

- حُصر **101 جدولًا** موزعة على **46 قالبًا**، وجميعها مشمولة بفحص المحاذاة التلقائي.
- يستخدم **83 جدول واجهة تفاعليًا** قواعد القراءة والتمرير المشتركة.
- احتفظ **18 جدولًا رسميًا/ورقيًا متخصصًا** بمقاسات الطباعة وتصميمه الخاص، مع تطبيق مطابقة محاذاة الرأس والقيم دون تغيير بنية المستند.
- أُضيف تمرير أفقي منضبط للجداول الطويلة، ومحاذاة تلقائية لرأس العمود مع الأرقام والتواريخ والإجراءات.
- أُصلح خروج خلايا «إجراءات» من شبكة الجدول بسبب تطبيق `display:flex` على الخلية نفسها.

## القوالب التي تحتوي على جداول

| القالب | الإجمالي | نمط واجهة مشترك | ورقي/متخصص |
|---|---:|---:|---:|
| `templates/calc2/page.html` | 1 | 1 | 0 |
| `templates/calc2/tab_free.html` | 4 | 4 | 0 |
| `templates/dowail/_paper_doc.html` | 1 | 0 | 1 |
| `templates/dowail/tab_lines.html` | 1 | 1 | 0 |
| `templates/dowail/tab_papers.html` | 3 | 3 | 0 |
| `templates/dowail/tab_rates.html` | 2 | 1 | 1 |
| `templates/dowail/tab_totals.html` | 2 | 2 | 0 |
| `templates/files_audit.html` | 1 | 1 | 0 |
| `templates/health.html` | 2 | 2 | 0 |
| `templates/health_paper.html` | 3 | 0 | 3 |
| `templates/letterhead.html` | 4 | 0 | 4 |
| `templates/occasions/paper_view.html` | 2 | 0 | 2 |
| `templates/occasions/print_report.html` | 1 | 0 | 1 |
| `templates/partials/alerts_table.html` | 1 | 1 | 0 |
| `templates/raghibin/tab_cadres.html` | 1 | 1 | 0 |
| `templates/raghibin/tab_excluded.html` | 1 | 1 | 0 |
| `templates/raghibin/tab_monthly.html` | 1 | 1 | 0 |
| `templates/rations.html` | 2 | 1 | 1 |
| `templates/rations_dist.html` | 1 | 1 | 0 |
| `templates/recruits_file.html` | 2 | 2 | 0 |
| `templates/recruits_journal.html` | 1 | 1 | 0 |
| `templates/recruits_lists.html` | 6 | 6 | 0 |
| `templates/recruits_print.html` | 4 | 4 | 0 |
| `templates/recruits_prison.html` | 1 | 1 | 0 |
| `templates/recruits_registry.html` | 1 | 1 | 0 |
| `templates/recruits_stats.html` | 3 | 3 | 0 |
| `templates/settings/tab_log.html` | 1 | 1 | 0 |
| `templates/settings/tab_users.html` | 1 | 1 | 0 |
| `templates/stats_master.html` | 5 | 5 | 0 |
| `templates/stats_print.html` | 5 | 4 | 1 |
| `templates/stores/_store_card.html` | 5 | 5 | 0 |
| `templates/stores/main.html` | 2 | 2 | 0 |
| `templates/tameedat/print_one.html` | 3 | 1 | 2 |
| `templates/tameedat/print_report.html` | 2 | 2 | 0 |
| `templates/tameedat/tab_day.html` | 1 | 1 | 0 |
| `templates/tameedat/tab_dict.html` | 1 | 1 | 0 |
| `templates/tameedat/tab_momoda.html` | 1 | 1 | 0 |
| `templates/tameedat/tab_report.html` | 1 | 1 | 0 |
| `templates/tarfea.html` | 8 | 8 | 0 |
| `templates/warehouses/_inv6_paper.html` | 1 | 0 | 1 |
| `templates/warehouses/tab_suppliers.html` | 1 | 1 | 0 |
| `templates/warehouses/tab_wh1.html` | 2 | 2 | 0 |
| `templates/warehouses/tab_wh2.html` | 4 | 4 | 0 |
| `templates/warehouses/tab_wh3.html` | 2 | 2 | 0 |
| `templates/warehouses/tab_wh4.html` | 2 | 1 | 1 |
| `templates/warehouses/tab_wh5.html` | 1 | 1 | 0 |

## قاموس توحيد لغة الواجهة

| اللفظ السابق | الصياغة المعتمدة |
|---|---|
| فولدر | مجلد |
| شيت | ورقة عمل |
| لوجو | شعار |
| فورم | نموذج |
| تاب / تابات | تبويب / تبويبات |
| زرار | زر |
| لينك | رابط |
| كارت / كروت | بطاقة / بطاقات |
| موديل | نموذج لغوي |
| باسورد | كلمة المرور |
| فطار | إفطار |
| فلترة | تصفية |
| توب | الأعلى / أعلى الأصناف |
| بنر / بانر | شريط تنبيه |
| فاضي | فارغ |
| مفيش / ما فيش | لا يوجد / لا توجد |
| النهارده / بكرة | اليوم / غدًا |
| علطول / دايمًا | مباشرةً / دائمًا |
| جوه | داخل |
| اختار | اختر |
| حط | ضع / سجّل، وفق السياق |
| مش | غير / ليس، وفق السياق |
| اللي | الذي / التي / ما، وفق السياق |
| عشان | لكي / لأن، وفق السياق |

تظل الألفاظ العامية موجودة فقط داخل مرادفات فهم أسئلة المستخدم في المساعد المحلي، حتى يفهم السؤال المكتوب باللهجة، بينما تكون الإجابة ونصوص الواجهة بالعربية الواضحة.

## الإحصائيات

حُذفت من تبويبات دورة الإمداد:

- الراغبين.
- مقررات التموين.
- مستودعات الإمداد.

وأي رابط قديم إلى أحد هذه التبويبات يعود تلقائيًا إلى تبويب «التتبع».
