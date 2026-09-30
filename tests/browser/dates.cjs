/* Gregorian dd/mm/yyyy must survive an English-US browser and non-Cairo OS zone. */
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const military = '99' + require('node:crypto').randomInt(100000, 1000000);
const tools = path.resolve(process.env.BROWSER_MODULES || '.arena/browser/node_modules');
const { chromium: playwright } = require(path.join(tools, 'playwright'));
// @sparticuz/chromium ≥ 153 أصبح ESM بلا main قديم — نوجّه للملف ونأخذ default
const chromiumModule = require(path.join(tools, '@sparticuz', 'chromium', 'build', 'index.js'));
const chromium = chromiumModule.default || chromiumModule;
const base = process.env.BROWSER_URL || 'http://127.0.0.1:5001';
const output = path.resolve('.arena/date-results');
const arabicDate = /^[٠-٩]{2}\/[٠-٩]{2}\/[٠-٩]{4}$/;

(async () => {
  assert.equal((await fetch(base + '/__test_scope').then(r => r.json())).isolated_appearance_test, true);
  fs.mkdirSync(output, { recursive: true });
  const browser = await playwright.launch({ executablePath: await chromium.executablePath(), args: chromium.args, headless: true });
  try {
    const context = await browser.newContext({ locale:'en-US', timezoneId:'America/Los_Angeles', viewport:{width:1440,height:1000} });
    const page = await context.newPage(), errors = [], external = [];
    page.on('pageerror', e => errors.push(e.message));
    context.on('request', r => { if (/^https?:/.test(r.url()) && new URL(r.url()).origin !== new URL(base).origin) external.push(r.url()); });
    await page.clock.install({ time: new Date('2026-09-21T22:30:00Z') });
    await page.goto(base + '/login');
    await page.locator('[name=username]').fill('mostafa');
    await page.locator('[name=password]').fill('779');
    await Promise.all([page.waitForURL('**/dashboard**'), page.locator('form button[type=submit]').click()]);
    assert.equal(await page.locator('#todayDate').innerText(), '٢٢/٠٩/٢٠٢٦'); // Not September 21 in Los Angeles.
    const year = await page.locator('body').getAttribute('data-year');
    const period = `year=${year}&month=9`;
    await page.goto(base + '/recruits/?' + period);
    await page.evaluate(() => document.fonts.ready);
    assert.equal(await page.locator('input[type=date]').count(), 0);
    assert.equal(await page.locator('input[data-date]').count(), 4);
    assert.equal(await page.locator('[name=service_start]').getAttribute('placeholder'), 'يوم/شهر/سنة');
    assert.equal(await page.locator('[name=service_start]').evaluate(e => getComputedStyle(e).direction), 'ltr');
    assert.deepEqual(await page.evaluate(() => ({
      ambiguous: LogisticsDates.iso('03/04/2031'),
      invalid: LogisticsDates.iso('12/31/2031'),
      leap: LogisticsDates.format('29/02/2032'),
      dateOnly: LogisticsDates.format('2031-04-03'),
    })), {ambiguous:'2031-04-03',invalid:'',leap:'٢٩/٠٢/٢٠٣٢',dateOnly:'٠٣/٠٤/٢٠٣١'});

    const start = page.locator('[name=service_start]');
    await start.locator('..').locator('.date-trigger').click();
    const picker = page.locator('#arabicDatePicker');
    assert(await picker.isVisible());
    await picker.locator('.date-month-input').fill('فبراير');
    await picker.locator('.combo-item').filter({hasText:'فبراير'}).click();
    await picker.locator('.date-year-input').fill('٢٠٣٢');
    await picker.locator('.date-period-go').click();
    const leap = picker.locator('[data-iso="2032-02-29"]');
    assert.equal(await leap.getAttribute('aria-label'), '٢٩/٠٢/٢٠٣٢');
    assert.equal(await picker.locator('.date-day').count(), 29);
    await page.screenshot({path:path.join(output,'arabic-calendar-en-US.png'),fullPage:true});
    await leap.click();
    assert.equal(await start.inputValue(), '٢٩/٠٢/٢٠٣٢');
    assert.equal(await picker.isVisible(), false);
    await start.press('ArrowDown');
    assert(await picker.isVisible());
    await page.keyboard.press('Escape');
    assert.equal(await picker.isVisible(), false);
    await start.locator('..').locator('.date-trigger').click();
    await picker.locator('[data-date-clear]').click();
    assert.equal(await start.inputValue(), '');

    await page.locator('[name=name]').fill('اختبار تنسيق التاريخ');
    await page.locator('[name=mil_no]').fill(military);
    await start.fill('03/04/2031'); await start.press('Tab');
    assert.equal(await start.inputValue(), '٠٣/٠٤/٢٠٣١');
    await page.locator('[name=service_end]').fill('31/12/2033');
    await page.locator('#hasCertCb').check();
    await page.locator('[name=cert_date]').fill('01/02/2031');
    await page.locator('[name=cert_expiry]').fill('03/04/2032');
    const post = page.waitForResponse(r => r.request().method()==='POST' && r.url().includes('/recruits/save'));
    await page.locator('.rc-save').click();
    assert.equal((await post).status(), 302);
    const displayMilitary = await page.evaluate(value => LogisticsDates.arabic(value), military);
    const record = page.locator('.rc-table-panel tbody tr').filter({hasText:displayMilitary});
    await record.waitFor();
    assert((await record.innerText()).includes('٠٣/٠٤/٢٠٣١'));
    assert((await record.innerText()).includes('٣١/١٢/٢٠٣٣'));
    await record.locator('.icon-btn.edit').click();
    await page.locator('[name=service_start]').waitFor();
    assert.equal(await start.inputValue(), '٠٣/٠٤/٢٠٣١');
    assert.equal(await page.locator('[name=cert_date]').inputValue(), '٠١/٠٢/٢٠٣١');
    await page.screenshot({path:path.join(output,'day-first-edit-form.png'),fullPage:true});

    // Invalid calendar values cannot pass HTML validation, then certificate reset clears errors.
    const before = [];
    page.on('request', r => { if (r.method()==='POST' && r.url().includes('/recruits/save')) before.push(r.url()); });
    await page.locator('[name=cert_date]').fill('31/02/2031');
    await page.locator('[name=cert_date]').press('Tab');
    assert.equal(await page.locator('[name=cert_date]').evaluate(e => e.checkValidity()), false);
    await page.locator('.rc-save').click();
    assert.equal(before.length, 0);
    await page.locator('#hasCertCb').uncheck();
    assert.equal(await page.locator('[name=cert_date]').inputValue(), '');
    assert.equal(await page.locator('[name=cert_date]').evaluate(e => e.checkValidity()), true);
    await page.locator('#hasCertCb').check();

    await page.setViewportSize({width:390,height:844});
    await start.scrollIntoViewIfNeeded();
    await start.locator('..').locator('.date-trigger').click();
    assert(await picker.isVisible());
    const bounds = await picker.boundingBox();
    assert(bounds.x>=0 && bounds.x+bounds.width<=391);
    assert(bounds.y>=0 && bounds.y+bounds.height<=845);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth>innerWidth+1),false);
    await page.screenshot({path:path.join(output,'mobile-arabic-calendar.png')});
    await page.keyboard.press('Escape');
    assert.deepEqual(errors, []); assert.deepEqual(external, []);
    // Keep this context alive until the shared Chromium process is closed.
    // Single-process headless builds may exit when their final live context closes.

    // An Arabic browser uses the exact same textual format as English-US.
    const arabic = await browser.newContext({locale:'ar-EG',timezoneId:'Asia/Tokyo',
      viewport:{width:1440,height:1000}, storageState:await context.storageState()});
    const arPage = await arabic.newPage();
    arPage.on('pageerror', e => errors.push(e.message));
    arabic.on('request', r => { if (/^https?:/.test(r.url()) && new URL(r.url()).origin !== new URL(base).origin) external.push(r.url()); });
    await arPage.clock.install({ time: new Date('2026-09-21T22:30:00Z') });
    await arPage.goto(base+'/dashboard');
    assert.equal(await arPage.locator('#todayDate').innerText(),'٢٢/٠٩/٢٠٢٦');
    await arPage.goto(base+'/recruits/?'+period);
    await arPage.locator('[name=service_start]').fill('٠٣٠٤٢٠٣١');
    assert.equal(await arPage.locator('[name=service_start]').inputValue(),'٠٣/٠٤/٢٠٣١');
    assert.equal(await arPage.locator('input[type=date]').count(),0);
    assert.deepEqual(errors, []); assert.deepEqual(external, []);
    // browser.close() in finally releases both contexts together (headless-shell safe).
    console.log('BROWSER_DATES_OK: en-US/ar-EG, Cairo date, dd/mm/yyyy entry + round-trip, Arabic leap calendar, validation, certificate reset, keyboard, mobile, no external requests');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
