/* نوافذ التفاريد وتبويبات عرض المخازن. */
/* نوافذ التفاريد المنبثقة: فتح من أي سطر/زر، وإغلاق بزر أو Esc أو الضغط بالخارج */
document.addEventListener("click", function (ev) {
    var openBtn = ev.target.closest("[data-taf-open]");
    if (openBtn) {
      var dlg = document.getElementById(openBtn.getAttribute("data-taf-open"));
      if (dlg && dlg.showModal) { dlg.showModal(); }
      return;
    }
    var closeBtn = ev.target.closest("[data-taf-close]");
    if (closeBtn) {
      var d2 = document.getElementById(closeBtn.getAttribute("data-taf-close"));
      if (d2 && d2.close) d2.close();
      return;
    }
    if (ev.target instanceof HTMLDialogElement) ev.target.close();  /* ضغط بالخارج */
  });

/* تبويبات الأصناف داخل كارت المخزن (تبويب المخازن): تبويب لكل صنف — الضغط يعرض حركته فقط (توجيه ٢٧/٠٩ ليلًا) */
document.addEventListener("click", function (ev) {
  var btn = ev.target.closest("[data-st-sub]");
  if (!btn) return;
  var scope = btn.closest(".wh-store-card");
  if (!scope) return;
  Array.prototype.forEach.call(scope.querySelectorAll("[data-st-sub]"), function (b) {
    b.classList.toggle("active", b === btn);
  });
  Array.prototype.forEach.call(scope.querySelectorAll("[data-st-panel]"), function (p) {
    p.hidden = p.getAttribute("data-st-panel") !== btn.getAttribute("data-st-sub");
  });
});

/* التبويبات الفرعية (٢ و٣ مخازن): تبديل بلا إعادة تحميل */
document.addEventListener("click", function (ev) {
  var btn = ev.target.closest("[data-wh2sub],[data-wh3sub]");
  if (!btn) return;
  var scope = btn.closest(".panel");
  if (!scope) return;
  var sub = btn.hasAttribute("data-wh2sub") ? "data-wh2sub" : "data-wh3sub";
  var pan = btn.hasAttribute("data-wh2sub") ? "data-wh2panel" : "data-wh3panel";
  Array.prototype.forEach.call(scope.querySelectorAll("[" + sub + "]"), function (b) {
    b.classList.toggle("active", b === btn);
  });
  Array.prototype.forEach.call(scope.querySelectorAll("[" + pan + "]"), function (p) {
    p.hidden = p.getAttribute(pan) !== btn.getAttribute(sub);
  });
});

/* ٣ مخازن — التابان الرئيسيان الفرعيان: «٣ مخازن» + «٣ مخازن تفاريد» (توجيه ٠٨/١٠) */
document.addEventListener("click", function (ev) {
  var btn = ev.target.closest("[data-wh3top]");
  if (!btn) return;
  var scope = btn.closest(".wh-wh3top");
  if (!scope) return;
  Array.prototype.forEach.call(scope.querySelectorAll("[data-wh3top]"), function (b) {
    b.classList.toggle("active", b === btn);
  });
  Array.prototype.forEach.call(scope.querySelectorAll("[data-wh3toppanel]"), function (p) {
    p.hidden = p.getAttribute("data-wh3toppanel") !== btn.getAttribute("data-wh3top");
  });
});

/* ٣ مخازن تفاريد — تبويب لكل صنف: الضغط يعرض دفتر التغليف الخاص بيه فقط (توجيه ٠٨/١٠) */
document.addEventListener("click", function (ev) {
  var btn = ev.target.closest("[data-wh3tab]");
  if (!btn) return;
  var scope = btn.closest(".wh-wh3taf");
  if (!scope) return;
  Array.prototype.forEach.call(scope.querySelectorAll("[data-wh3tab]"), function (b) {
    b.classList.toggle("active", b === btn);
  });
  Array.prototype.forEach.call(scope.querySelectorAll("[data-wh3tabpanel]"), function (p) {
    p.hidden = p.getAttribute("data-wh3tabpanel") !== btn.getAttribute("data-wh3tab");
  });
});

/* من التاميدات: «عرض الإذن» يفتح ٢ مخازن على «سجلات ٢ مخازن» عند إذنها مباشرة (توجيه ٢٧/٠٩) */
(function () {
  try {
    var q = new URLSearchParams(window.location.search);
    var sub2 = q.get("wh2sub"), no = q.get("wh2permit");
    if (!sub2 && !no) return;
    if (sub2) {
      var btn = document.querySelector('[data-wh2sub="' + sub2 + '"]');
      if (btn) btn.click();
    }
    if (no) {
      var row = document.querySelector('[data-taf-open="sijDialog-' + no + '"]');
      if (row) row.click();
    }
  } catch (err) {}
})();

(function () {
  /* ============ كارت الصنف على الموبايل: الضغط على صنف ينزل على الكارت على طول
  (القائمة فوقه والكارت تحتها — من غيرها يبان «الجدول مختفي» وهو تحت) ============ */
  try {
    var q3 = new URLSearchParams(window.location.search);
    if (q3.get("item")) {
      var cardEl = document.getElementById("whCard");
      if (cardEl && cardEl.scrollIntoView) {
        window.setTimeout(function () {
          cardEl.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 150);
      }
    }
  } catch (err) {}

})();
