/* Tameedat browser acceptance — runs only against tests/browser/serve.py.
   Never points at the user's real database/. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const tools = path.resolve(process.env.BROWSER_MODULES || '.arena/browser/node_modules');
const { chromium: playwright } = require(path.join(tools, 'playwright'));
// @sparticuz/chromium ≥ 153 أصبح ESM بلا main قديم — نوجّه للملف ونأخذ default
const chromiumModule = require(path.join(tools, '@sparticuz', 'chromium', 'build', 'index.js'));
const chromium = chromiumModule.default || chromiumModule;
const base = process.env.BROWSER_URL || 'http://127.0.0.1:5001';
const output = path.resolve('.arena/tameedat-results');

(async () => {
  const scope = await fetch(base + '/__test_scope').then(r => r.json());
  assert.equal(scope.isolated_appearance_test, true, 'Refusing to write browser fixtures into non-test data');
  fs.mkdirSync(output, { recursive: true });
  const browser = await playwright.launch({ executablePath: await chromium.executablePath(), args: chromium.args, headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true, locale: 'ar-EG' });
    const errors = [], external = [];
    context.on('page', p => p.on('pageerror', e => errors.push(e.message)));
    context.on('request', request => {
      if (/^https?:/.test(request.url()) && new URL(request.url()).origin !== new URL(base).origin) external.push(request.url());
    });
    const page = await context.newPage();
    await page.goto(base + '/login');
    await page.locator('[name=username]').fill('mostafa');
    await page.locator('[name=password]').fill('779');
    await Promise.all([page.waitForURL('**/dashboard**'), page.locator('form button[type=submit]').click()]);
    const year = await page.locator('body').getAttribute('data-year');
    const stamp = String(Date.now()).slice(-6);
    const entityName = 'وحدة اختبار المتصفح ' + stamp;   // اسم فريد لإعادة التشغيل
    const attName = 'سرية ملحقة اختبار ' + stamp;         // الملحقة فريدة أيضًا (تُضاف للقاموس)
    const period = `year=${year}&month=9`;

    // ===================================================== الترويسة والتويبات
    await page.getByText('مساحة العمل').first().waitFor();                       // لوحة القيادة جاهزة
    await page.getByText('وزارة الداخلية').first().waitFor();             // الهوية الجديدة في الترويسة
    await page.locator('#addYearBtn.ctx-add').waitFor();                 // مربع «+» الأصفر للسنة الجديدة (بحسب الشكل المعتمد)
    await page.getByText('نقل إلى الأرشيف').first().waitFor();            // والأرشفة بعد الانتهاء
    await page.locator('#delYearBtn.ctx-del').waitFor();                 // حذف السنة بالسلة الحمراء
    await page.goto(base + '/tameedat/?' + period);
    await page.getByText('قطاع وسط سيناء - قسم التميينات', { exact: true }).waitFor();
    await page.getByText('منطقة وسط وجنوب للأمن المركزي', { exact: true }).waitFor();
    for (const tab of ['تأميدات اليوم المحدد', 'الجهات المومدة بالشهر الحالي', 'قاموس ودليل الجهات', 'طباعة التقرير الشامل'])
      assert(await page.getByText(tab, { exact: true }).count(), tab);
    assert((await page.locator('.tm-cell:not(.empty)').count()) >= 28, 'calendar days');
    const bodyFont = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
    assert(bodyFont.includes('Tajawal'), bodyFont);
    await page.screenshot({ path: path.join(output, 'tameedat-day.png'), fullPage: true });

    // ============================================ تسجيل تأميدة بجهة غير مسجلة + ملحقة
    // زرّ «إضافة تأميدة جديدة لهذا اليوم» يفتح النموذج ويقفله (طلب المستخدم)
    await page.locator('#tmNewToggle').click();
    await page.locator('#tmFormCard:not([hidden])').waitFor();
    await page.locator('#tmNewToggle').click();                    // يقفل
    await page.locator('#tmFormCard').waitFor({ state: 'hidden' });
    await page.locator('#tmNewToggle').click();                    // يفتح مجددًا للتسجيل
    await page.locator('#tmFormCard:not([hidden])').waitFor();
    assert.equal(await page.locator('input[name=save_token]').count(), 1, 'حارس الازدواج موجود');
    await page.locator('#tmDayFrom').fill('٢٢');                   // من يوم ٢٢ إلى يوم ٢٤ (لا تاريخ ولا مفتاح مدة)
    await page.locator('#tmDayTo').fill('٢٤');
    await page.locator('#tmDayFrom').press('Tab');
    assert((await page.locator('#tmRangeDaysHint').textContent()).includes('٣'), 'تلميح «سارية ٣ أيام»');
    await page.locator('#tmEntity').fill(entityName);
    assert.equal(await page.locator('#tmUnknownWarn').isVisible(), true, 'unknown-entity warning');
    await page.locator('[name=officers]').fill('٥');
    await page.locator('[name=individuals]').fill('٤٠');
    await page.locator('[name=recruits]').fill('١٢٠');
    assert.equal(await page.locator('#tmTotal').inputValue(), '١٦٥');
    await page.locator('#tmAttAdd').click();
    assert(await page.locator('.tm-att [name=att_type]').last().evaluate(e => e.dataset.comboReady), 'قائمة النوع كومبو متمثّم');
    await page.locator('[name=att_name]').last().fill(attName);
    await page.locator('[name=att_officers]').last().fill('٢');
    await page.locator('[name=att_individuals]').last().fill('١٠');
    await page.locator('[name=att_recruits]').last().fill('٣٠');
    await Promise.all([page.waitForURL('**/tameedat/**'), page.locator('.tm-save').click()]);
    await page.getByText('وتسجيلها في البيانات المحلية.').waitFor();
    await page.getByText('فأُضيفت إلى قاموس الشهر').waitFor();
    await page.getByText('المدة الزمنية مفعّلة').waitFor();
    await page.getByText('أُضيفت هي الأخرى إلى قاموس الشهر').waitFor();  // الملحقة انضمت للقاموس
    const toastsBefore = await page.locator('.toast').count();
    await page.locator('.toast .toast-x').first().click();                 // الرسائل تُغلق بـ ✕ (بلاغ المستخدم «لا استطيع اغلاقها»)
    assert.equal(await page.locator('.toast').count(), toastsBefore - 1, 'رسالة تُغلق بزر ✕');
    assert.equal(await page.locator('.tm-table tbody tr.tm-main').count(), 1, 'تأميدة واحدة فقط — بلا ازدواج');
    await page.locator('.tm-range-chip').waitFor();                      // شارة «من ٢٢ إلى ٢٤»
    await page.getByText(entityName).first().waitFor();
    await page.locator('td.num b', { hasText: '٢٠٧' }).first().waitFor(); // الإجمالي مع الملحقة: 165+42 = 207 → ٢٠٧ — يظهر بلا فواصل
    await page.locator('.tm-table td.num.stack .stk.att').first().waitFor(); // صف واحد: أم + ملحقة + إجمالي مكدّس
    await page.getByText('إجمالي التأميدة — تأميدة').first().waitFor();
    await page.getByText('ملحقة: ' + attName).first().waitFor();
    for (const hook of ['.tm-act-edit', '.tm-act-copy', '.tm-act-permit', '.tm-act-delete'])
      await page.locator(hook).first().waitFor(); // الأزرار الأربعة: تعديل/نسخ/إذن ٢ مخازن/حذف
    await page.screenshot({ path: path.join(output, 'tameedat-record.png'), fullPage: true });

    // ===================================================== نسخ ثم لصق يوم آخر
    await page.locator('.tm-copy').first().click();
    await page.locator('.tm-copybar').waitFor();
    const day24 = page.locator('.tm-cell:not(.empty):not(.sel)').nth(23);
    await day24.scrollIntoViewIfNeeded();
    await day24.click();
    await Promise.all([page.waitForURL('**/tameedat/**'), page.locator('.tm-paste').click()]);
    await page.getByText('تم لصق نسخة منفصلة').waitFor();
    const pastedDay = new URL(page.url()).searchParams.get('day'); // يوم النسخة المنفصلة

    // ===================================================== المومدة والقاموس
    await page.goto(base + `/tameedat/?${period}&tab=momoda`);
    await page.getByText(entityName).first().waitFor();
    await page.getByText('إجمالي القوة').first().waitFor();
    await page.locator('.tm-att-momoda .tm-att-badge').first().waitFor(); // الملحقة صف مستقل بشارتها
    assert.equal(await page.getByText('متوسط ضباط').count(), 0, 'المتوسطات أُزيلت من جدول المومدة');
    await page.getByText(attName).first().waitFor();
    await page.locator('.tm-days-open').first().click();                    // افتح الأيام بالتواريخ
    await page.locator('#tmDaysModal:not([hidden])').waitFor();
    await page.getByText('أيام التميد بالتواريخ —').waitFor();
    await page.locator('#tmDaysList li').first().waitFor();
    await page.getByText('تأميدة رقم').first().waitFor();                   // كل تأميدة بتاريخها الدقيق
    assert(await page.locator('#tmDaysList .tm-print-mini').count() > 0, 'روابط طباعة داخل القائمة');
    await page.locator('#tmDaysPrint').waitFor();                           // زر طباعة القائمة نفسها
    await page.locator('#tmDaysClose').click();
    await page.locator('#tmDaysModal').waitFor({ state: 'hidden' });
    await page.goto(base + `/tameedat/?${period}&tab=dict`);
    await page.getByText(entityName).first().waitFor();
    await page.getByText('متوسط ضباط').first().waitFor();                 // المتوسطات هنا الآن (قرار المستخدم)
    await page.getByText('متوسط مجندين').first().waitFor();
    await page.getByText('عدد التأميدات').first().waitFor();
    await page.getByText('ملحقة؟').first().waitFor();
    await page.locator('.tm-days-open').first().click();                  // نفس نافذة التواريخ تعمل في القاموس
    await page.locator('#tmDaysModal:not([hidden])').waitFor();
    await page.locator('#tmDaysClose').click();
    await page.locator('#tmDaysModal').waitFor({ state: 'hidden' });
    await page.locator('#tmDictSearch').fill('زئبق');
    assert.equal(await page.locator('#tmDictTable tbody tr:visible').count(), 0, 'dict search hides');
    await page.locator('#tmDictSearch').fill('');
    await page.screenshot({ path: path.join(output, 'tameedat-dict.png'), fullPage: true });

    // ============================================ التقرير الشامل: Excel حقيقي بالدباجة واللوجو
    await page.goto(base + `/tameedat/?${period}&tab=report`);
    await page.getByText('بناء Excel بالدباجة واللوجو وتنزيله').waitFor();
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.locator('.tm-report-actions a').first().click(),
    ]);
    const target = path.join(output, 'tameedat-report.xlsx');  // اسم ثابت — الاقتراح العربي لا يُعتمد هنا
    await download.saveAs(target);
    assert(fs.statSync(target).size > 3000, 'xlsx downloaded');
    assert(fs.readFileSync(target).subarray(0, 2).equals(Buffer.from('PK')), 'valid xlsx zip');

    // ===================================================== طباعة تأميدة واحدة
    await page.goto(base + `/tameedat/?${period}&tab=day&day=${year}-09-22`);
    const printHref = await page.locator('.tm-print-mini').first().getAttribute('href');
    await page.goto(base + new URL(printHref, base).pathname + new URL(printHref, base).search);
    await page.getByText('تأميدة رقم', { exact: false }).waitFor();
    await page.getByText('للاسترشاد بهذه التأميدة فقط').waitFor();
    await page.getByText('مدة زمنية مفعّلة: من يوم').waitFor();
    await page.screenshot({ path: path.join(output, 'tameedat-print.png'), fullPage: true });

    // ===================================================== حذف تأميدة النسخة المنفصلة
    page.on('dialog', (dialog) => dialog.accept());
    await page.goto(base + `/tameedat/?${period}&tab=day&day=${pastedDay}`);
    await page.locator('.tm-act-delete').first().waitFor();
    const rowsBefore = await page.locator('.tm-table tbody tr.tm-main').count();
    await page.locator('.tm-act-delete').first().click();
    await page.getByText('تم حذف تأميدة').waitFor();
    await page.getByText('من البيانات المحلية.').waitFor();
    assert.equal(await page.locator('.tm-table tbody tr.tm-main').count(), rowsBefore - 1, 'record deleted');
    await page.screenshot({ path: path.join(output, 'tameedat-after-delete.png'), fullPage: true });

    // بلاغ المستخدم: أزرار السنة تبقى ظاهرة على الشاشات الضيقة — مجرد تغيير حجم العارض نفسه
    await page.goto(base + '/dashboard');
    await page.setViewportSize({ width: 640, height: 900 });
    assert(await page.locator('#addYearBtn').isVisible(), 'إنشاء سنة جديدة مخفي على العرض الضيق!');
    assert(await page.locator('#archiveYearBtn').isVisible(), 'نقل إلى الأرشيف مخفي على العرض الضيق!');
    assert(await page.locator('#delYearBtn').isVisible(), 'زر حذف السنة مخفي على العرض الضيق!');

    assert.deepEqual(errors, [], 'JS errors: ' + errors.join(' | '));
    assert.deepEqual(external, [], 'external requests: ' + external.join(','));
    console.log('BROWSER_TAMEEDAT_OK: header, 4 tabs, calendar, collapsible entry form + from-day/to-day tameedah (single, no duplicate), aligned attachment row auto-registered, 4 pro action buttons, copy/paste with attachments, independent attachment momoda row + averages moved to dictionary (count/from-to dates popup/attachment-state) + days popup (printable), dict search, letterhead xlsx download, print with duration, delete with confirm, narrow-screen year ops stay visible + tab open bars + new identity, zero external requests');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
