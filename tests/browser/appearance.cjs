/* Run only against tests/browser/serve.py: fixtures must never enter real user data.
   Tooling is deliberately separate from the offline production application. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const tools = path.resolve(process.env.BROWSER_MODULES || '.arena/browser/node_modules');
const { chromium: playwright } = require(path.join(tools, 'playwright'));
// @sparticuz/chromium ≥ 153 أصبح ESM بلا main قديم — نوجّه للملف ونأخذ default
const chromiumModule = require(path.join(tools, '@sparticuz', 'chromium', 'build', 'index.js'));
const chromium = chromiumModule.default || chromiumModule;
const base = process.env.BROWSER_URL || 'http://127.0.0.1:5001';
const output = path.resolve('.arena/appearance-results');
const FONT = 'Tajawal';

async function theme(page, nativeWelcome = false) {
  const result = await page.evaluate(async () => {
    await Promise.all([400, 500, 700, 800].map(weight =>
      document.fonts.load(`${weight} 16px "Tajawal"`, 'المجندين ٠٫١٢٠ ٧٥٫٠٠٠')));
    const style = getComputedStyle(document.body);
    const button = document.querySelector('.btn-gold, .rt-btn.gold');
    return {
      font: style.fontFamily,
      frame: getComputedStyle(document.querySelector('.windowbar, .bar')).backgroundColor,
      accent: button && getComputedStyle(button).backgroundColor,
      text: button && getComputedStyle(button).color,
      overflow: document.documentElement.scrollWidth > innerWidth + 1,
      fonts: [...document.fonts].filter(f => f.status === 'loaded').length,
    };
  });
  assert(result.font.includes(FONT), JSON.stringify(result));
  assert.equal(result.frame, 'rgb(2, 6, 23)');
  assert.equal(result.fonts, 4);
  if (result.accent) {
    assert.equal(result.accent, 'rgb(245, 158, 11)');
    assert.equal(result.text, 'rgb(2, 6, 23)');
  }
  assert.equal(result.overflow, false, `Horizontal overflow: ${page.url()}`);
  if (!nativeWelcome && !page.url().includes('/login')) {
    assert.equal(await page.locator('.sidebar').evaluate(e => getComputedStyle(e).backgroundColor), 'rgb(15, 23, 42)');
  }
}

async function actualFont(page, selector) {
  const cdp = await page.context().newCDPSession(page);
  try {
    await cdp.send('DOM.enable');
    await cdp.send('CSS.enable');
    const { root } = await cdp.send('DOM.getDocument');
    const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: root.nodeId, selector });
    const { fonts } = await cdp.send('CSS.getPlatformFontsForNode', { nodeId });
    assert(fonts.some(f => f.isCustomFont && f.familyName.includes(FONT) && f.glyphCount > 0), JSON.stringify(fonts));
    return fonts;
  } finally { await cdp.detach(); }
}

(async () => {
  // This endpoint does not exist in the real application. Refuse unsafe targets.
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
    await page.goto(base + '/__welcome');
    await theme(page, true);
    await actualFont(page, 'h1');
    await page.screenshot({ path: path.join(output, 'native-welcome.png'), fullPage: true });
    await page.goto(base + '/login');
    await theme(page);
    await actualFont(page, '.login-hero h1');
    await page.screenshot({ path: path.join(output, 'login.png'), fullPage: true });
    await page.locator('[name=username]').fill('mostafa');
    await page.locator('[name=password]').fill('779');
    await Promise.all([page.waitForURL('**/dashboard**'), page.locator('form button[type=submit]').click()]);
    await theme(page);
    const year = await page.locator('body').getAttribute('data-year');
    const period = `year=${year}&month=9`;
    await page.screenshot({ path: path.join(output, 'dashboard.png'), fullPage: true });

    await page.goto(base + '/recruits/?' + period);
    await page.locator('[name=name]').fill('اسم اختبار للخط العربي');
    await page.locator('[name=mil_no]').fill('١٢٣٤٥٦٧٨٩٠');
    await page.locator('#hasCertCb').check();
    assert(await page.locator('#certDetails').isVisible());
    await page.locator('[name=cert_date]').fill('01/09/2026');
    await page.locator('#hasCertCb').uncheck();
    assert.equal(await page.locator('[name=cert_date]').inputValue(), '');
    assert.equal(await page.locator('#certDetails').isVisible(), false);
    await Promise.all([page.waitForURL('**/recruits/**'), page.locator('.rc-save').click()]);
    await page.locator('.rc-table-panel table').waitFor();
    await theme(page);
    const numericFonts = await actualFont(page, '.rc-table-panel td.num');
    assert(await page.getByText('١٢٣٤٥٦٧٨٩٠', { exact: true }).count());
    await page.screenshot({ path: path.join(output, 'recruits.png'), fullPage: true });

    for (const tab of ['registry', 'journal', 'present', 'leaves', 'absent', 'other', 'stats']) {
      await page.goto(`${base}/recruits/?${period}&tab=${tab}`);
      await theme(page);
      assert.equal(await page.locator('.rc-tab').count(), 7);
      if (tab === 'journal') {
        const day = page.locator('.rc-daybox.on');
        for (const state of ['locked', 'missing']) {
          await day.evaluate((el, value) => el.classList.add(value), state);
          assert.equal(await day.evaluate(el => getComputedStyle(el).color), 'rgb(252, 211, 77)');
          await day.evaluate((el, value) => el.classList.remove(value), state);
        }
      }
    }

    await page.goto(base + '/rations/tamween?' + period);
    for (const [field, value] of Object.entries({name:'صنف لاختبار وضوح الأرقام',unit:'كجم',breakfast:'٠٫١٢٠',lunch:'٧٥٫٠٠٠',dinner:'١٫٢٥٠'})) {
      await page.locator(`.rt-form [name=${field}]`).fill(value);
    }
    await Promise.all([page.waitForURL('**/rations/tamween?**'), page.locator('.rt-form button[type=submit]').click()]);
    await page.getByText('٠٫١٢٠', { exact: true }).first().waitFor();
    await theme(page);
    assert(await page.getByText('٧٥٫٠٠٠', { exact: true }).count());
    await actualFont(page, '.rt-table tbody .num');
    assert.equal(await page.locator('.rt-table th').first().evaluate(e => getComputedStyle(e).color), 'rgb(252, 211, 77)');
    await page.screenshot({ path: path.join(output, 'rations.png'), fullPage: true });
    await page.emulateMedia({ media: 'print' });
    assert.equal(await page.locator('body').evaluate(e => getComputedStyle(e).color), 'rgb(22, 22, 22)');
    assert.equal(await page.locator('body').evaluate(e => getComputedStyle(e).backgroundColor), 'rgb(255, 255, 255)');
    await page.emulateMedia({ media: 'screen' });

    const routes = ['/dashboard','/rations/tamween','/rations/contractor?tab=dist','/letterhead/','/recruits/','/recruits/?tab=stats','/backups/'];
    for (const route of routes) {
      await page.goto(base + route);
      await theme(page);
    }
    await page.goto(base + '/letterhead/?' + period);
    const paper = await page.locator('.a4').first().evaluate(e => ({
      background: getComputedStyle(e).backgroundColor,
      text: getComputedStyle(e).getPropertyValue('--text').trim(),
    }));
    assert.equal(paper.background, 'rgb(253, 253, 255)');
    assert.equal(paper.text, '#161616');
    await page.screenshot({ path: path.join(output, 'letterhead.png'), fullPage: true });
    await page.goto(base + '/dashboard');
    await page.locator('#ctxMonth').click();
    await page.locator('.ctx .combo-list:not([hidden]) .combo-item').first().hover();
    const item = page.locator('.ctx .combo-list:not([hidden]) .combo-item').first();
    assert.equal(await item.evaluate(e => getComputedStyle(e).color), 'rgb(252, 211, 77)');
    assert.equal(await item.evaluate(e => getComputedStyle(e).backgroundColor), 'rgb(32, 23, 8)');
    await page.keyboard.press('Escape');
    await page.locator('#bellBtn').click();
    assert(await page.locator('#bellPanel').isVisible());
    await page.locator('#bellBtn').click();

    await page.setViewportSize({ width: 390, height: 844 });
    for (const route of routes) {
      await page.goto(base + route);
      await theme(page);
    }
    await page.goto(base + '/dashboard');
    await page.screenshot({ path: path.join(output, 'mobile-dashboard.png'), fullPage: true });
    await page.locator('#menuBtn').click();
    await page.waitForFunction(() => {
      const r = document.getElementById('sidebar').getBoundingClientRect();
      return r.left >= 0 && r.right <= innerWidth + 1;
    });
    await page.screenshot({ path: path.join(output, 'mobile-menu.png') });
    const mobileLogin = await browser.newPage({ viewport: { width: 390, height: 844 } });
    await mobileLogin.goto(base + '/login');
    await theme(mobileLogin);
    await mobileLogin.screenshot({ path: path.join(output, 'mobile-login.png'), fullPage: true });
    await mobileLogin.close();
    assert.deepEqual(errors, []);
    assert.deepEqual(external, []);
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify({ result:'BROWSER_APPEARANCE_OK', numericFonts, errors, external }, null, 2));
    console.log('BROWSER_APPEARANCE_OK: unchanged Arabic font glyphs, reference slate/amber + Tajawal بأرقامه الأصلية, native welcome, seven tabs, form save, Arabic quantities, combos, mobile, zero external requests');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
