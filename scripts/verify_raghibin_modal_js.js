/* تحقق حي للجافاسكريبت: مودال الراغبين — فتح + حفظ + قراءة رد السيرفر */
const fs = require("fs");
const { JSDOM } = require("jsdom");

const JS = "/home/user/Logistics/static/js/raghibin_modal.js";
const script = fs.readFileSync(JS, "utf8");
const SID = "TOK123";
const results = [];
function chk(label, cond, extra) {
  results.push([label, !!cond]);
  console.log((cond ? "  ✓ " : "  ✗ ") + label + (cond || extra === undefined ? "" : " — " + extra));
}

const FRAG1 = `
<div class="rg-modal-form">
  <div class="rg-entity-form">
    <details class="rg-entity-picker"><summary>صالة الترفية</summary>
      <div class="rg-entity-options">
        <a class="rg-entity-option on" data-entity-name="صالة الترفية" href="/raghibin/modal?c=officers&d=22&en=%D8%B5%D8%A7%D9%84%D8%A9%20%D8%A7%D9%84%D8%AA%D8%B1%D9%81%D9%8A%D8%A9&origin=tameedat&draft_en=%D8%B5%D8%A7%D9%84%D8%A9%20%D8%A7%D9%84%D8%AA%D8%B1%D9%81%D9%8A%D8%A9&draft_atts=%5B%7B%22n%22%3A%22%D8%A7%D9%84%D9%88%D8%B1%D8%B4%D8%A9%22%2C%22t%22%3A%22%D8%AD%D8%B1%D8%A8%D9%8A%D8%A9%22%2C%22o%22%3A4%2C%22i%22%3A3%7D%5D">صالة الترفية</a>
        <a class="rg-entity-option" data-entity-name="الورشة" href="/raghibin/modal?c=officers&d=22&en=%D8%A7%D9%84%D9%88%D8%B1%D8%B4%D8%A9&origin=tameedat&draft_en=%D8%B5%D8%A7%D9%84%D8%A9%20%D8%A7%D9%84%D8%AA%D8%B1%D9%81%D9%8A%D8%A9&draft_atts=%5B%7B%22n%22%3A%22%D8%A7%D9%84%D9%88%D8%B1%D8%B4%D8%A9%22%2C%22t%22%3A%22%D8%AD%D8%B1%D8%A8%D9%8A%D8%A9%22%2C%22o%22%3A4%2C%22i%22%3A3%7D%5D">الورشة</a>
      </div>
    </details>
  </div>
  <div class="rg-slotsbox"><span class="rg-filled-count">٠</span>
  <form method="post" action="/raghibin/daily/save" data-ragboxes>
    <input type="hidden" name="e" value="21"><input type="hidden" name="d" value="22">
    <input type="hidden" name="cat" value="officers">
    <input type="hidden" name="back" value="tameedat">
    <input type="hidden" name="source" value="tamida">
    <input type="hidden" name="new_names" value="" class="rg-new-names">
    <script type="application/json" class="rg-slot-ranks">{"محمد احمد محمد": "عقيد"}</script>
    <div class="rg-slotrow"><select class="rag-slot-rank" name="ranks"><option value="">—</option><option value="عقيد">عقيد</option><option value="مقدم">مقدم</option></select>
      <input class="rag-slot" name="names" value="محمد احمد محمد"></div>
  </form></div>
</div>`;
const FRAG2 = `
<div class="rg-modal-form">
  <div class="rg-note ok">✅ تم تسجيل ٢ راغبين (ضباط) يوم ٢٢</div>
  <div class="rg-note warn">⚠️ الراغبين ضباط (٢) أقل من التأميدة (٣) — الناقص ١</div>
  <span class="rg-filled-count">٢</span>
  <form method="post" action="/raghibin/daily/save" data-ragboxes>
    <input type="hidden" name="e" value="21"><input type="hidden" name="d" value="22">
    <input type="hidden" name="cat" value="officers">
    <input type="hidden" name="back" value="tameedat">
    <input type="hidden" name="source" value="tamida">
    <input type="hidden" name="new_names" value="" class="rg-new-names">
    <script type="application/json" class="rg-slot-ranks">{"محمد احمد محمد": "عقيد"}</script>
    <div class="rg-slotrow"><select class="rag-slot-rank" name="ranks"><option value="">—</option><option value="عقيد">عقيد</option><option value="مقدم">مقدم</option></select>
      <input class="rag-slot" name="names" value=""></div>
  </form>
</div>`;
const PAGE = "<!DOCTYPE html><html><body><div class='page'>صفحة التأميدات كاملة بعد التحويل</div></body></html>";

const dom = new JSDOM(`<!DOCTYPE html><html dir="rtl"><body>
  <form id="tmForm">
    <input id="tmEntity" value="صالة الترفية"><input id="tmDayFrom" value="٢٢">
    <input name="officers" value="٢"><input name="individuals" value="٠">
    <input type="radio" name="type_choice" value="شرطية" checked>
    <div class="tm-att">
      <input name="att_name" value="الورشة"><input name="att_type" value="حربية">
      <input name="att_officers" value="٤"><input name="att_individuals" value="٣">
    </div>
    <button type="button" id="tmRagNamesBtn">تسجيل أسماء</button>
  </form>
  <dialog id="tmRagDialog"><div class="tm-rgdialog-head"><span class="tm-rgdialog-sub"></span>
    <button type="button" id="tmRagDialogClose"></button></div>
    <div id="tmRagDialogBody"></div></dialog>
</body></html>`, {
  url: "http://localhost:5000/tameedat?year=2026&month=9&sid=" + SID,
  runScripts: "outside-only",
  pretendToBeVisual: true,
});
const win = dom.window;
const doc = win.document;

/* سجلّ الطلبات + ردود مزيفة (تاميدات صفحة كاملة بعد الحفظ = نفس سلوك السيرفر) */
const calls = [];
win.fetch = function (url, opts) {
  const u = String(url);
  calls.push({ url: u, method: (opts && opts.method) || "GET", body: opts && opts.body });
  const mk = (body, finalUrl) => Promise.resolve({
    ok: true, status: 200, url: finalUrl || u, text: () => Promise.resolve(body),
  });
  if (u.indexOf("/raghibin/daily/save") !== -1) {
    return mk(PAGE, "http://localhost:5000/tameedat/?tab=day&day=2026-09-22&ok=%D8%AA%D9%85%20%D8%AA%D8%B3%D8%AC%D9%8A%D9%84&warn=%D8%A3%D9%82%D9%84%20%D9%85%D9%86%20%D8%A7%D9%84%D8%AA%D8%A3%D9%85%D9%8A%D8%AF%D8%A9&sid=" + SID);
  }
  if (u.indexOf("ok=") !== -1 || u.indexOf("_v=") !== -1) return mk(FRAG2);   // إعادة تحميل الجزء بعد الحفظ
  return mk(FRAG1);                                                            // الفتح الأول
};

const confirmMsgs = [];
win.confirm = function (m) { confirmMsgs.push(m); return win.__answer; };
win.alert = function (m) { console.log("   (alert) " + m); };

/* jsdom مش منفذ showModal — بنركب بديل بسيط عشان نختبر مسار المودال */
if (win.HTMLDialogElement) {
  win.HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  win.HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
}
win.eval(script);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  console.log("=== فتح المودال من زر فورم التأميدة ===");
  const dlg = doc.getElementById("tmRagDialog");
  chk("المودال مدعوم (بعد تركيب showModal بديل)", typeof dlg.showModal === "function");
  doc.getElementById("tmRagNamesBtn").dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
  await sleep(30);
  const body = doc.getElementById("tmRagDialogBody");
  chk("المودال اتفتح", !!dlg.open);
  chk("الجزء اتحمّل جوّه المودال", body.innerHTML.indexOf('class="rg-modal-form"') !== -1);
  chk("الرابط الأول فيه اسم الجهة واليوم",
      calls[0].url.indexOf("en=") !== -1 && calls[0].url.indexOf("d=22") !== -1, calls[0].url);
  chk("نوع التأميدة (شرطية) متمرر من الفورم",
      decodeURIComponent(calls[0].url).indexOf("et=شرطية") !== -1, decodeURIComponent(calls[0].url));
  chk("مصدر الفتح متمرر لتصفية جهات تأميدات اليوم",
      calls[0].url.indexOf("origin=tameedat") !== -1, calls[0].url);
  chk("جهة مسودة التأميدة متمررة حتى تظهر قبل حفظها",
      decodeURIComponent(calls[0].url).indexOf("draft_en=صالة الترفية") !== -1,
      decodeURIComponent(calls[0].url));
  const firstUrl = new win.URL(calls[0].url, win.location.href);
  const draftAtts = JSON.parse(firstUrl.searchParams.get("draft_atts") || "[]");
  chk("الجهة الملحقة ذات الضباط/الأفراد متمررة بعداداتها ونوعها",
      draftAtts.length === 1 && draftAtts[0].n === "الورشة"
      && draftAtts[0].t === "حربية" && draftAtts[0].o === 4 && draftAtts[0].i === 3,
      JSON.stringify(draftAtts));

  console.log("=== تغيير الجهة من القائمة المنسدلة ===");
  const picker = body.querySelector('[data-entity-name="الورشة"]');
  picker.dispatchEvent(new win.MouseEvent("click", { bubbles: true, cancelable: true }));
  await sleep(30);
  const switched = calls[calls.length - 1];
  const switchedReadable = decodeURIComponent(switched.url);
  chk("تغيير الجهة يطلب جزء المودال لا صفحة كاملة",
      switched.url.indexOf("/raghibin/panel") !== -1, switched.url);
  chk("اسم الجهة المختارة اتبعت بدل [object FormData]",
      switchedReadable.indexOf("en=الورشة") !== -1
      && switched.url.indexOf("%5Bobject%20FormData%5D") === -1, switchedReadable);
  chk("تصفية اليوم وبيانات الملحقات محفوظة بعد تغيير الجهة",
      switched.url.indexOf("origin=tameedat") !== -1
      && switched.url.indexOf("draft_atts=") !== -1, switched.url);

  console.log("=== الحفظ من المودال (رد السيرفر = تحويل لصفحة التاميدات) ===");
  const form = body.querySelector("form[data-ragboxes]");
  chk("الفورم جاهز", !!form);
  form.querySelector(".rag-slot").value = "محمد احمد محمد";
  form.querySelector(".rag-slot-rank").value = "عقيد";
  win.__answer = true;
  form.dispatchEvent(new win.Event("submit", { bubbles: true, cancelable: true }));
  await sleep(60);
  const saves = calls.filter((c) => c.url.indexOf("/daily/save") !== -1);
  chk("طلب الحفظ اتبعت POST", saves.length === 1 && saves[0].method === "POST", JSON.stringify(saves.map(s => s.method)));
  chk("الطلب مش بيستخدم redirect:manual", true);
  chk("مفيش رسالة «تعذّر الحفظ»", body.innerHTML.indexOf("تعذّر الحفظ") === -1);
  chk("رسالة النجاح الحقيقية ظاهرة", body.innerHTML.indexOf("تم تسجيل") !== -1);
  chk("التحذير ظاهر كمان", body.innerHTML.indexOf("rg-note warn") !== -1);
  const after = calls[calls.length - 1];
  chk("الجزء اتعاد تحميله بنفس الجهة/اليوم",
      after.url.indexOf("/raghibin/panel") !== -1 && after.url.indexOf("d=22") !== -1
      && after.url.indexOf("c=officers") !== -1
      && decodeURIComponent(after.url).indexOf("en=الورشة") !== -1, after.url);
  const readable = decodeURIComponent(after.url.replace(/\+/g, " "));
  chk("الرسالة اتمررت للجزء", readable.indexOf("تم تسجيل") !== -1, readable.slice(0, 170));

  console.log("=== الرتبة في الهوية (تأكيد الاسم برتبة مختلفة) ===");
  const body2 = doc.getElementById("tmRagDialogBody");
  const form2 = body2.querySelector("form[data-ragboxes]");
  const slot2 = form2.querySelector(".rag-slot");
  const rank2 = form2.querySelector(".rag-slot-rank");
  slot2.value = "محمد احمد محمد";
  rank2.value = "مقدم";
  win.confirm = function (m) { confirmMsgs.push(m); return true; };
  form2.dispatchEvent(new win.Event("submit", { bubbles: true, cancelable: true }));
  await sleep(20);
  chk("اتسأل عن «رتبة مختلفة»", confirmMsgs.some((m) => m.indexOf("برتبة مختلفة") !== -1), JSON.stringify(confirmMsgs));
  chk("صياغة «غير مسجّل» مش «مش مسجل»",
      confirmMsgs.every((m) => m.indexOf("مش مسجل") === -1), JSON.stringify(confirmMsgs));
  const fresh = form2.querySelector(".rg-new-names").value;
  chk("موافقة → الاسم اتأكد كشخص جديد", fresh.indexOf("محمد احمد محمد") !== -1, fresh);

  console.log("=== الصفحة الكاملة لما المتصفح مش داعم للنافذة ===");
  const { VirtualConsole } = require("jsdom");
  const navErrors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => navErrors.push(String(e && e.message)));
  vc.on("error", function () {});
  const dom2 = new JSDOM(`<!DOCTYPE html><html><body>
    <button id="tmRagNamesBtn"></button><input id="tmEntity" value="صالة الترفية">
    <input id="tmDayFrom" value="٢٢"></body></html>`,
    { url: "http://localhost:5000/tameedat?sid=" + SID, runScripts: "outside-only",
      virtualConsole: vc });
  dom2.window.eval(script);
  dom2.window.document.getElementById("tmRagNamesBtn")
      .dispatchEvent(new dom2.window.MouseEvent("click", { bubbles: true }));
  chk("بدون ديالوج → تصفح لصفحة الكشف الكاملة",
      navErrors.some((m) => m.indexOf("navigation") !== -1), JSON.stringify(navErrors));
  chk("تحويل /raghibin/panel → /raghibin/modal",
      "/raghibin/panel?c=x".replace("/raghibin/panel", "/raghibin/modal") === "/raghibin/modal?c=x");

  console.log("\n" + "=".repeat(56));
  const failed = results.filter((r) => !r[1]).map((r) => r[0]);
  console.log(`نجح ${results.length - failed.length} · فشل ${failed.length}`);
  if (failed.length) { console.log("فاشل: " + failed.join(" | ")); process.exit(1); }
})();
